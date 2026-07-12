---
name: banana
description: "Generate images and text with Gemini via the Banana MCP server. Use when the user wants to: generate images, create visual assets, batch-generate images, offload text generation to Gemini (scoring, extraction, transformation, summarization), or run parallel text prompts. Triggers on: /banana, image generation, text generation offload, batch processing."
---

# Banana — Gemini Image + Text Generation

Orchestrates the `mcp__banana__*` tools to generate images and text with formatted output and timing.

## CLI Interface

```
/banana <command> [args]
```

## Commands

| Command | Description |
|---------|-------------|
| `generate <prompt>` | Generate a single image |
| `batch <prompts...>` | Generate multiple images in parallel |
| `text <prompt>` | Generate text from a prompt |
| `text-batch <prompts...>` | Generate multiple text responses in parallel |
| `settings` | Show current defaults |
| `set <key> <value>` | Update a setting (image_model, text_model, output_dir, aspect_ratio, image_size) |
| (no command) | Natural language — infer the intent and execute |

## Execution Rules

### Timing

Track elapsed time for every Banana MCP tool call. Print timing inline:

```
[banana] generate_image .................... 8.2s
  Saved: /home/eric/output/hero-banner.png

[banana] generate_images_batch ............ 24.1s
  3/3 succeeded
  [0] /home/eric/output/slide-1.png (7.8s)
  [1] /home/eric/output/slide-2.png (8.1s)
  [2] /home/eric/output/slide-3.png (8.2s)
```

Use `date +%s%N` before and after each `mcp__banana__*` tool call to compute elapsed time. Format as `Xs` for under 60s, `Xm Ys` for 60s+.

### Output Format

After every MCP tool call, immediately print a formatted summary block. NEVER let a tool call go unreported. The format is:

```
[banana] <tool_name> ....................... <elapsed>
  <summary lines>
```

Field summaries per tool:

| Tool | Summary Fields |
|------|---------------|
| `generate_image` | File path saved to |
| `generate_images_batch` | Success count, per-image paths and times |
| `generate_text` | Response text (or file path if output_file used) |
| `generate_texts_batch` | Success count, per-response previews and times |
| `get_settings` | Current settings |
| `update_settings` | Updated settings values |

### Batch Generation

When generating multiple images:
- Use `generate_images_batch` with up to 10 images per call
- Set `max_concurrency` to avoid rate limiting (default: 3)
- For more than 10 images, split into multiple batch calls
- Report per-image results (path + time) and overall success rate

When generating multiple text responses:
- Use `generate_texts_batch` with up to 10 requests per call
- Each request can have its own `system_instruction`, `model`, `output_file`, etc.
- Set `max_concurrency` to avoid rate limiting (default: 3)
- For more than 10 texts, split into multiple batch calls

### Text Generation

Use `generate_text` and `generate_texts_batch` to offload repeatable tasks to Gemini — scoring, extraction, transformation, summarization — without burning Claude Code's context window.

- `system_instruction`: steers Gemini's behavior (e.g., "You are a JSON extractor. Return only valid JSON.")
- `output_file`: saves response to a file instead of returning text directly
- `input_image_path`: pass an image for vision/multimodal analysis (e.g., validate a generated slide, describe a screenshot)
- `model`: override the default text model per-request
- `max_output_tokens` / `temperature`: optional generation controls

### Pipeline Summary

When executing multi-step workflows (e.g., batch of images for a project), print a summary:

```
──── Banana Pipeline Complete ────
  Images: 5/5 succeeded
  Total: 42.3s
  Output: ./output/
──────────────────────────────────
```

### Natural Language Mode

When no explicit command is given, infer the user's intent. Examples:

- "generate a hero image for my landing page" -> generate_image
- "make 5 icons for these features" -> generate_images_batch
- "score these 8 essays against this rubric" -> generate_texts_batch with system_instruction
- "summarize this document" -> generate_text
- "extract all email addresses from this text" -> generate_text with system_instruction
- "set the text model to gemini-2.5-pro" -> update_settings
- "what are my current settings" -> get_settings
- "generate a background in 16:9" -> generate_image with aspect_ratio

### Image Display

After generating an image, use the Read tool to display it to the user so they can see the result without leaving the session.

### Models

Image and text tools accept a `model` param. If omitted, the default from settings is used.

All models below are validated working on Vertex AI in `vital-sandbox-anika` / `global` as of 2026-04. `gemini-3-pro-preview` and `gemini-3-pro-image-preview` were retired 2026-03-09; `gemini-3.1-pro-preview` is the successor.

**Image models** (default: `gemini-3.1-flash-image-preview`):

| Model | Best For |
|-------|----------|
| `gemini-2.5-flash-image` | Fastest (~4s), good for high-volume drafts |
| `gemini-3.1-flash-image-preview` | Highest-quality default, slower (~18s) |

**Text models** (default: `gemini-3-flash-preview`):

| Model | Best For |
|-------|----------|
| `gemini-2.5-flash-lite` | Lowest latency (~1.3s), simple extraction |
| `gemini-2.5-flash` | Fast (~1.5s) with thinking, balanced |
| `gemini-2.5-pro` | Stable reasoning, ~2.5s |
| `gemini-3-flash-preview` | Frontier flash, multimodal — bulk tasks, scoring |
| `gemini-3.1-flash-lite-preview` | Cheapest 3.x, highest volume |
| `gemini-3.1-pro-preview` | Best reasoning, agentic workflows |

### Image Sizes

| Value | Resolution | Tokens | Notes |
|-------|-----------|--------|-------|
| `512` | 512x512 | — | Flash only |
| `1K` | 1024x1024 | 1120 | — |
| `2K` | 2048x2048 | 1120 | Default |
| `4K` | 4096x4096 | 2000 | — |

Must be uppercase `K`. Actual pixels scale with aspect ratio (e.g., `16:9` at `2K` = 2048x1152).

### Aspect Ratios

| Value | Use Case |
|-------|----------|
| `16:9` | Presentations, hero banners, desktop wallpapers (default) |
| `9:16` | Mobile, stories, vertical posters |
| `1:1` | Icons, avatars, social media |
| `4:3` | Standard slides, classic format |
| `3:4` | Portraits, book covers |

### Error Handling

If a generation fails (filtered content, no image returned), print clearly:

```
[banana] generate_image ................... FAILED (2.1s)
  Error: No image generated (may have been filtered)
```

Then suggest the user adjust the prompt and retry.

### File Naming

- The PreToolUse hook auto-appends `.png` if missing — no need to handle in the skill
- If no `file_name` is given, banana auto-generates one: `banana-{hex}.png`
- Files save to the configured `outputDir` (default: `./output`) unless an absolute path is given
