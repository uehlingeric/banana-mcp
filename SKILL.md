---
name: banana
description: "Generate images with Gemini via the Banana MCP server. Use when the user wants to generate, create, or edit images, create visual assets, render illustrations, or batch-generate multiple images. Triggers on: /banana, image generation requests, visual asset creation, illustration requests."
---

# Banana — Gemini Image Generation

Orchestrates the `mcp__banana__*` tools to generate images with formatted output and timing.

## CLI Interface

```
/banana <command> [args]
```

## Commands

| Command | Description |
|---------|-------------|
| `generate <prompt>` | Generate a single image |
| `batch <prompts...>` | Generate multiple images in parallel |
| `settings` | Show current defaults |
| `set <key> <value>` | Update a setting (quality, output_dir, aspect_ratio, image_size) |
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
| `get_settings` | Current quality, outputDir, aspectRatio (default 16:9), imageSize (default 2K) |
| `update_settings` | Updated settings values |

### Batch Generation

When generating multiple images:
- Use `generate_images_batch` with up to 5 images per call
- Set `max_concurrency` to avoid rate limiting (default: 3)
- For more than 5 images, split into multiple batch calls
- Report per-image results (path + time) and overall success rate

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
- "set quality to balanced" -> update_settings
- "what are my current settings" -> get_settings
- "generate a background in 16:9" -> generate_image with aspect_ratio

### Image Display

After generating an image, use the Read tool to display it to the user so they can see the result without leaving the session.

### Quality Presets

| Preset | Model | Best For |
|--------|-------|----------|
| `fast` | gemini-3.1-flash-image-preview | Quick iterations, drafts |
| `quality` | gemini-3-pro-image-preview | Final assets, hero images |

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
