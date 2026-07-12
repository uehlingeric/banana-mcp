# Banana MCP

MCP server for AI image and text generation via Google's Gemini models. Built for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

![MCP Server](https://img.shields.io/badge/MCP_Server-1E3A8A) ![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white) ![License: MIT](https://img.shields.io/badge/License-MIT-green)

## What It Does

Exposes Gemini's image and text generation as MCP tools, letting Claude Code generate images and offload text tasks to Gemini directly in your terminal session.

- **Image generation** — single or batch (up to 10 in parallel)
- **Text generation** — single or batch, with system instructions for repeatable tasks
- **Image editing** — pass an input image + prompt to modify existing images
- **Configurable defaults** — models, aspect ratio, image size, output directory
- **Persistent settings** — saved to `settings.json` between sessions

## MCP Tools

| Tool | Description |
|------|-------------|
| `generate_image` | Generate a single image from a text prompt |
| `generate_images_batch` | Generate up to 10 images in parallel |
| `generate_text` | Generate text from a prompt (supports vision via `input_image_path`) |
| `generate_texts_batch` | Generate up to 10 text responses in parallel (supports vision) |
| `get_settings` | Retrieve current defaults |
| `update_settings` | Change models, output dir, aspect ratio, image size |

## Models

**Image** (default: `gemini-3.1-flash-image-preview`):
- `gemini-3.1-flash-image-preview` — fast iterations, drafts
- `gemini-3-pro-image-preview` — final assets, hero images

**Text** (default: `gemini-3-flash-preview`):
- `gemini-3-flash-preview` — fast, multimodal, bulk tasks
- `gemini-3.1-pro-preview` — best reasoning, agentic
- `gemini-3.1-flash-lite-preview` — cheapest, high volume

## Image Sizes & Aspect Ratios

**Sizes:** `512`, `1K`, `2K` (default), `4K`

**Aspect Ratios:** `16:9` (default), `9:16`, `1:1`, `4:3`, `3:4`

Actual pixel dimensions scale with aspect ratio (e.g., `16:9` at `2K` = 2048x1152).

## Setup

### Prerequisites

- Python 3.10+
- A [Gemini API key](https://aistudio.google.com/apikey)

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Claude Code

Add to your Claude Code MCP settings (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "banana": {
      "command": "python3",
      "args": ["/path/to/banana-mcp/server.py"],
      "env": {
        "GEMINI_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Skill (Optional)

Copy `SKILL.md` to `~/.claude/skills/banana/SKILL.md` to enable the `/banana` slash command with formatted output and natural language mode.

## Usage

Once configured, Claude Code can call the tools directly:

```
> Generate a hero banner for my landing page

[banana] generate_image .................... 8.2s
  Saved: ./output/hero-banner.png
```

```
> Make 3 icon variations for a settings gear

[banana] generate_images_batch ............ 18.4s
  3/3 succeeded
  [0] ./output/gear-1.png (6.1s)
  [1] ./output/gear-2.png (5.9s)
  [2] ./output/gear-3.png (6.4s)
```

```
> Score these 5 essays against the rubric

[banana] generate_texts_batch ............ 12.1s
  5/5 succeeded
  [0] OK (2.3s): {"score": 8, "feedback": "Strong thesis..."}
  [1] OK (2.5s): {"score": 6, "feedback": "Needs more ev..."}
  ...
```

## Architecture

Single-file MCP server (`server.py`, ~360 lines) using the Python MCP SDK with stdio transport. Gemini API calls run in a thread executor for async compatibility. Settings persist to a local `settings.json` file.

## License

MIT — see [LICENSE](LICENSE).
