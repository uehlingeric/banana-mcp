#!/usr/bin/env python3
"""Banana — minimal Gemini image generation MCP server."""

import json
import os
import asyncio
import time
from pathlib import Path
from secrets import token_hex
from typing import Any

from google import genai
from google.genai import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Settings ─────────────────────────────────────────────────────────────────

SETTINGS_PATH = Path(__file__).parent / "settings.json"

DEFAULTS = {
    "quality": "fast",
    "outputDir": "./output",
    "aspectRatio": "16:9",
    "imageSize": "2K",
}

_settings: dict[str, Any] = {}


def load_settings():
    global _settings
    try:
        _settings = {**DEFAULTS, **json.loads(SETTINGS_PATH.read_text())}
    except (FileNotFoundError, json.JSONDecodeError):
        _settings = {**DEFAULTS}


def save_settings():
    SETTINGS_PATH.write_text(json.dumps(_settings, indent=2))


# ── Gemini Client ────────────────────────────────────────────────────────────

MODELS = {
    "fast": "gemini-3.1-flash-image-preview",
    "quality": "gemini-3-pro-image-preview",
}

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("GEMINI_API_KEY required")

client = genai.Client(api_key=api_key)


def _generate_one_sync(
    prompt: str,
    file_name: str = "",
    input_image_path: str = "",
    aspect_ratio: str = "",
    image_size: str = "",
    quality: str = "",
) -> tuple[str, float]:
    t0 = time.perf_counter()
    q = quality or _settings["quality"]
    model = MODELS.get(q, MODELS["fast"])

    parts: list = []
    if input_image_path:
        p = Path(input_image_path)
        mime = {".png": "image/png", ".webp": "image/webp"}.get(p.suffix.lower(), "image/jpeg")
        parts.append(types.Part.from_bytes(data=p.read_bytes(), mime_type=mime))
    parts.append(types.Part.from_text(text=prompt))

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
        model=model,
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


# ── Tool Schemas (hand-crafted for minimal token footprint) ──────────────────

TOOLS = [
    Tool(
        name="generate_image",
        description="Generate an image from a text prompt.",
        inputSchema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "file_name": {"type": "string"},
                "input_image_path": {"type": "string"},
                "aspect_ratio": {"type": "string"},
                "image_size": {"type": "string"},
                "quality": {"type": "string"},
            },
            "required": ["prompt"],
        },
    ),
    Tool(
        name="generate_images_batch",
        description="Generate up to 5 images in parallel.",
        inputSchema={
            "type": "object",
            "properties": {
                "requests": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string"},
                            "file_name": {"type": "string"},
                            "input_image_path": {"type": "string"},
                            "aspect_ratio": {"type": "string"},
                            "image_size": {"type": "string"},
                            "quality": {"type": "string"},
                        },
                        "required": ["prompt"],
                    },
                },
                "max_concurrency": {"type": "integer"},
            },
            "required": ["requests"],
        },
    ),
    Tool(
        name="get_settings",
        description="Get current banana defaults (quality, outputDir, aspectRatio, imageSize).",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="update_settings",
        description="Update banana defaults. Only provided fields change.",
        inputSchema={
            "type": "object",
            "properties": {
                "quality": {"type": "string"},
                "output_dir": {"type": "string"},
                "aspect_ratio": {"type": "string"},
                "image_size": {"type": "string"},
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
            if len(reqs) > 5:
                raise ValueError(f"Max 5 images per batch (got {len(reqs)})")
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

        elif name == "get_settings":
            return [TextContent(type="text", text=json.dumps(_settings))]

        elif name == "update_settings":
            for k, v in arguments.items():
                mapped = {"output_dir": "outputDir", "aspect_ratio": "aspectRatio", "image_size": "imageSize"}.get(k, k)
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

if __name__ == "__main__":
    asyncio.run(main())
