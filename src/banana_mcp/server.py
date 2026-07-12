#!/usr/bin/env python3
"""Banana — Gemini image + text generation MCP server."""

import json
import os
import asyncio
import socket
import time
from pathlib import Path
from secrets import token_hex
from typing import Any

# Force IPv4 resolution. On hosts where the IPv6 route to *.googleapis.com
# black-holes, Python's getaddrinfo returns AAAA records first and httpx/grpc
# stall indefinitely (curl works because of Happy Eyeballs fallback). Filter
# AF_INET6 out so the SDK only attempts IPv4. Override with BANANA_FORCE_IPV4=0.
if os.environ.get("BANANA_FORCE_IPV4", "1") == "1":
    _orig_getaddrinfo = socket.getaddrinfo

    def _ipv4_only(host, port, family=0, *args, **kwargs):
        return _orig_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)

    socket.getaddrinfo = _ipv4_only  # type: ignore[assignment]

from google import genai
from google.genai import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Settings ─────────────────────────────────────────────────────────────────

SETTINGS_PATH = Path(__file__).parent / "settings.json"

DEFAULTS = {
    "outputDir": "./output",
    "imageModel": "gemini-3.1-flash-image-preview",
    "textModel": "gemini-3-flash-preview",
    "aspectRatio": "16:9",
    "imageSize": "2K",
    "maxOutputTokens": 16384,
    "thinkingLevel": "LOW",
}

_settings: dict[str, Any] = {}


def load_settings():
    global _settings
    try:
        raw = json.loads(SETTINGS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        raw = {}
    # Migrate legacy "quality" preset to imageModel
    if "quality" in raw and "imageModel" not in raw:
        legacy = {"fast": "gemini-3.1-flash-image-preview", "quality": "gemini-3-pro-image-preview"}
        raw["imageModel"] = legacy.get(raw.pop("quality"), DEFAULTS["imageModel"])
    elif "quality" in raw:
        raw.pop("quality")
    _settings = {**DEFAULTS, **raw}


def save_settings():
    SETTINGS_PATH.write_text(json.dumps(_settings, indent=2))


# ── Gemini Client ────────────────────────────────────────────────────────────

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("GEMINI_API_KEY required")

client = genai.Client(api_key=api_key)


def _read_text_input(direct: str, file_path: str, field: str, required: bool = True) -> str:
    """Resolve one of direct text or file_path. At most one may be set. `required` means one must be set."""
    if direct and file_path:
        raise ValueError(f"Provide {field} or {field}_file, not both")
    if file_path:
        p = Path(file_path)
        if not p.is_file():
            raise ValueError(f"{field}_file not found: {file_path}")
        return p.read_text()
    if required and not direct:
        raise ValueError(f"{field} or {field}_file is required")
    return direct


def _strip_code_fences(text: str) -> str:
    """Strip a single surrounding markdown code fence if the ENTIRE response is wrapped in one.

    Handles ``` and ```lang openers. Leaves untouched if the text doesn't both open
    and close with a fence (so embedded code blocks inside a longer response survive)."""
    s = text.strip()
    if not (s.startswith("```") and s.endswith("```")) or len(s) < 6:
        return text
    lines = s.split("\n")
    if len(lines) < 2:
        return text
    first, last = lines[0].strip(), lines[-1].strip()
    # First line is ``` or ```lang; last line is bare ```
    if not first.startswith("```") or last != "```":
        return text
    return "\n".join(lines[1:-1])


def _generate_one_sync(
    prompt: str = "",
    prompt_file: str = "",
    file_name: str = "",
    input_image_path: str = "",
    aspect_ratio: str = "",
    image_size: str = "",
    model: str = "",
) -> tuple[str, float]:
    t0 = time.perf_counter()
    m = model or _settings["imageModel"]
    prompt_text = _read_text_input(prompt, prompt_file, "prompt", required=True)

    parts: list = []
    if input_image_path:
        p = Path(input_image_path)
        mime = {".png": "image/png", ".webp": "image/webp"}.get(p.suffix.lower(), "image/jpeg")
        parts.append(types.Part.from_bytes(data=p.read_bytes(), mime_type=mime))
    parts.append(types.Part.from_text(text=prompt_text))

    cfg: dict[str, Any] = {"response_modalities": ["IMAGE"]}
    ar = aspect_ratio or _settings["aspectRatio"]
    sz = image_size or _settings["imageSize"]
    if ar or sz:
        ic: dict[str, str] = {}
        if ar:
            ic["aspect_ratio"] = ar
        if sz:
            ic["image_size"] = sz
        cfg["image_config"] = ic

    resp = client.models.generate_content(
        model=m,
        contents=[types.Content(parts=parts)],
        config=cfg,
    )

    if not resp.candidates:
        raise RuntimeError("No image generated (may have been filtered)")
    img = next((p for p in resp.candidates[0].content.parts if p.inline_data and p.inline_data.data), None)
    if not img:
        txt = next((p.text for p in resp.candidates[0].content.parts if p.text), "No image in response")
        raise RuntimeError(txt)

    name = file_name or f"banana-{token_hex(4)}.png"
    out = Path(name) if os.path.isabs(name) else Path(_settings["outputDir"]) / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img.inline_data.data)
    return str(out.resolve()), time.perf_counter() - t0


async def generate_one(**kwargs) -> str:
    return await asyncio.get_running_loop().run_in_executor(
        None, lambda: _generate_one_sync(**kwargs)
    )


def _generate_text_sync(
    prompt: str = "",
    prompt_file: str = "",
    system_instruction: str = "",
    system_instruction_file: str = "",
    model: str = "",
    output_file: str = "",
    input_image_path: str = "",
    max_output_tokens: int = 0,
    temperature: float | None = None,
    thinking_level: str = "",
) -> tuple[str, float]:
    t0 = time.perf_counter()
    m = model or _settings["textModel"]
    prompt_text = _read_text_input(prompt, prompt_file, "prompt", required=True)
    si_text = _read_text_input(system_instruction, system_instruction_file, "system_instruction", required=False)

    cfg: dict[str, Any] = {}
    cfg["max_output_tokens"] = max_output_tokens or _settings["maxOutputTokens"]
    if temperature is not None:
        cfg["temperature"] = temperature
    if si_text:
        cfg["system_instruction"] = si_text
    tl = thinking_level or _settings.get("thinkingLevel", "")
    # thinking_level is Gemini 3.x only. Gemini 2.5 uses thinking_budget (int) and
    # 2.5-flash-lite has no thinking at all — passing thinking_level there 400s.
    if tl and m.startswith("gemini-3"):
        cfg["thinking_config"] = {"thinking_level": tl}

    parts: list = []
    if input_image_path:
        p = Path(input_image_path)
        mime = {".png": "image/png", ".webp": "image/webp"}.get(p.suffix.lower(), "image/jpeg")
        parts.append(types.Part.from_bytes(data=p.read_bytes(), mime_type=mime))
    parts.append(types.Part.from_text(text=prompt_text))

    resp = client.models.generate_content(
        model=m,
        contents=[types.Content(parts=parts)],
        config=cfg,
    )

    if not resp.candidates:
        raise RuntimeError("No response generated (may have been filtered)")
    cand = resp.candidates[0]
    fr = cand.finish_reason
    text = "".join(p.text for p in (cand.content.parts or []) if p.text) if cand.content else ""
    text = _strip_code_fences(text)
    # Surface non-STOP finishes as errors — silently returning partial output
    # was the root cause of prompt-engineer truncation bugs.
    if fr and fr.name != "STOP":
        u = resp.usage_metadata
        thinking = getattr(u, "thoughts_token_count", 0) or 0
        raise RuntimeError(
            f"Truncated (finish={fr.name}, cand={u.candidates_token_count}, "
            f"thinking={thinking}, budget={cfg['max_output_tokens']}). "
            f"Retry with higher max_output_tokens or lower thinking_level."
        )
    if not text:
        raise RuntimeError("No text in response")

    elapsed = time.perf_counter() - t0
    if output_file:
        out = Path(output_file) if os.path.isabs(output_file) else Path(_settings["outputDir"]) / output_file
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        u = resp.usage_metadata
        return f"Saved: {out.resolve()} ({u.candidates_token_count} tokens)", elapsed

    return text, elapsed


async def generate_text(**kwargs) -> tuple[str, float]:
    return await asyncio.get_running_loop().run_in_executor(
        None, lambda: _generate_text_sync(**kwargs)
    )


# ── Tool Schemas (hand-crafted for minimal token footprint) ──────────────────

_IMAGE_PROPS = {
    "prompt": {"type": "string", "description": "Inline prompt text. Use prompt_file instead to pass a path."},
    "prompt_file": {"type": "string", "description": "Path to a file containing the prompt. Alternative to inline prompt — keeps large prompts out of the MCP wire."},
    "file_name": {"type": "string"},
    "input_image_path": {"type": "string"},
    "aspect_ratio": {"type": "string"},
    "image_size": {"type": "string"},
    "model": {"type": "string"},
}

_TEXT_PROPS = {
    "prompt": {"type": "string", "description": "Inline prompt text. Use prompt_file instead to pass a path."},
    "prompt_file": {"type": "string", "description": "Path to a file containing the prompt. Alternative to inline prompt."},
    "system_instruction": {"type": "string", "description": "Inline system instruction. Use system_instruction_file to pass a path."},
    "system_instruction_file": {"type": "string", "description": "Path to a file containing the system instruction. Keeps big skill prompts out of the MCP wire."},
    "model": {"type": "string"},
    "output_file": {"type": "string"},
    "input_image_path": {"type": "string"},
    "max_output_tokens": {"type": "integer"},
    "temperature": {"type": "number"},
    "thinking_level": {"type": "string", "enum": ["MINIMAL", "LOW", "MEDIUM", "HIGH"]},
}

TOOLS = [
    Tool(
        name="generate_image",
        description="Generate an image from a text prompt. Provide prompt OR prompt_file.",
        inputSchema={"type": "object", "properties": _IMAGE_PROPS},
    ),
    Tool(
        name="generate_images_batch",
        description="Generate up to 10 images in parallel. Each request provides prompt OR prompt_file.",
        inputSchema={
            "type": "object",
            "properties": {
                "requests": {"type": "array", "items": {"type": "object", "properties": _IMAGE_PROPS}},
                "max_concurrency": {"type": "integer"},
            },
            "required": ["requests"],
        },
    ),
    Tool(
        name="generate_text",
        description="Generate text from a prompt using Gemini. Provide prompt OR prompt_file.",
        inputSchema={"type": "object", "properties": _TEXT_PROPS},
    ),
    Tool(
        name="generate_texts_batch",
        description="Generate up to 10 text responses in parallel. Each request provides prompt OR prompt_file.",
        inputSchema={
            "type": "object",
            "properties": {
                "requests": {"type": "array", "items": {"type": "object", "properties": _TEXT_PROPS}},
                "max_concurrency": {"type": "integer"},
            },
            "required": ["requests"],
        },
    ),
    Tool(
        name="get_settings",
        description="Get current banana defaults.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="update_settings",
        description="Update banana defaults. Only provided fields change.",
        inputSchema={
            "type": "object",
            "properties": {
                "output_dir": {"type": "string"},
                "image_model": {"type": "string"},
                "text_model": {"type": "string"},
                "aspect_ratio": {"type": "string"},
                "image_size": {"type": "string"},
                "max_output_tokens": {"type": "integer"},
                "thinking_level": {"type": "string", "enum": ["MINIMAL", "LOW", "MEDIUM", "HIGH"]},
            },
        },
    ),
]


# ── Handlers ─────────────────────────────────────────────────────────────────

app = Server("banana")


@app.list_tools()
async def list_tools():
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "generate_image":
            path, secs = await generate_one(**arguments)
            return [TextContent(type="text", text=f"Saved: {path} ({secs:.1f}s)")]

        elif name == "generate_images_batch":
            reqs = arguments.get("requests", [])
            if not reqs:
                raise ValueError("requests must be non-empty")
            if len(reqs) > 10:
                raise ValueError(f"Max 10 images per batch (got {len(reqs)})")
            mc = arguments.get("max_concurrency")

            t0 = time.perf_counter()
            if mc and 0 < mc < len(reqs):
                sem = asyncio.Semaphore(mc)
                async def limited(r):
                    async with sem:
                        return await generate_one(**r)
                results = await asyncio.gather(*[limited(r) for r in reqs], return_exceptions=True)
            else:
                results = await asyncio.gather(*[generate_one(**r) for r in reqs], return_exceptions=True)
            total = time.perf_counter() - t0

            lines = []
            ok = 0
            for i, r in enumerate(results):
                if isinstance(r, Exception):
                    lines.append(f"[{i}] FAIL: {r}")
                else:
                    path, secs = r
                    lines.append(f"[{i}] OK: {path} ({secs:.1f}s)")
                    ok += 1
            return [TextContent(type="text", text=f"{ok}/{len(reqs)} succeeded in {total:.1f}s\n" + "\n".join(lines))]

        elif name == "generate_text":
            text, secs = await generate_text(**arguments)
            return [TextContent(type="text", text=f"{text}\n({secs:.1f}s)")]

        elif name == "generate_texts_batch":
            reqs = arguments.get("requests", [])
            if not reqs:
                raise ValueError("requests must be non-empty")
            if len(reqs) > 10:
                raise ValueError(f"Max 10 texts per batch (got {len(reqs)})")
            mc = arguments.get("max_concurrency")

            t0 = time.perf_counter()
            if mc and 0 < mc < len(reqs):
                sem = asyncio.Semaphore(mc)
                async def limited_text(r):
                    async with sem:
                        return await generate_text(**r)
                results = await asyncio.gather(*[limited_text(r) for r in reqs], return_exceptions=True)
            else:
                results = await asyncio.gather(*[generate_text(**r) for r in reqs], return_exceptions=True)
            total = time.perf_counter() - t0

            lines = []
            ok = 0
            for i, r in enumerate(results):
                if isinstance(r, Exception):
                    lines.append(f"[{i}] FAIL: {r}")
                else:
                    text, secs = r
                    # When output_file is used, text already reads "Saved: /path (N tokens)".
                    # Otherwise truncate for inline preview.
                    if text.startswith("Saved: "):
                        lines.append(f"[{i}] OK ({secs:.1f}s) {text}")
                    else:
                        preview = text[:120].replace("\n", " ")
                        if len(text) > 120:
                            preview += "..."
                        lines.append(f"[{i}] OK ({secs:.1f}s): {preview}")
                    ok += 1
            return [TextContent(type="text", text=f"{ok}/{len(reqs)} succeeded in {total:.1f}s\n" + "\n".join(lines))]

        elif name == "get_settings":
            return [TextContent(type="text", text=json.dumps(_settings))]

        elif name == "update_settings":
            field_map = {
                "output_dir": "outputDir",
                "image_model": "imageModel",
                "text_model": "textModel",
                "aspect_ratio": "aspectRatio",
                "image_size": "imageSize",
                "max_output_tokens": "maxOutputTokens",
                "thinking_level": "thinkingLevel",
            }
            for k, v in arguments.items():
                mapped = field_map.get(k, k)
                if mapped in DEFAULTS:
                    _settings[mapped] = v
            save_settings()
            return [TextContent(type="text", text=json.dumps(_settings))]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        return [TextContent(type="text", text=str(e))]


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    load_settings()
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
