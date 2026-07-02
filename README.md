# Banana MCP

MCP server for AI image generation via Google's Gemini models. Built for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

![MCP Server](https://img.shields.io/badge/MCP_Server-1E3A8A) ![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white) ![License: MIT](https://img.shields.io/badge/License-MIT-green)

## What It Does

Exposes Gemini's image generation capabilities as MCP tools, letting Claude Code generate images from text prompts directly in your terminal session.

- **Single image generation** from text prompts
- **Batch generation** — up to 5 images in parallel with concurrency control
- **Image editing** — pass an input image + prompt to modify existing images
- **Configurable defaults** — quality, aspect ratio, image size, output directory
- **Persistent settings** — saved to `settings.json` between sessions

## MCP Tools

| Tool | Description |
|------|-------------|
| `generate_image` | Generate a single image from a text prompt |
| `generate_images_batch` | Generate up to 5 images in parallel |
| `get_settings` | Retrieve current defaults |
| `update_settings` | Change quality, output dir, aspect ratio, image size |

## Quality Presets

| Preset | Model | Best For |
|--------|-------|----------|
| `fast` | `gemini-3.1-flash-image-preview` | Quick iterations, drafts |
| `quality` | `gemini-3-pro-image-preview` | Final assets, hero images |

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

## Architecture

Single-file MCP server (`server.py`, ~250 lines) using the Python MCP SDK with stdio transport. Gemini API calls run in a thread executor for async compatibility. Settings persist to a local `settings.json` file.

## License

MIT — see [LICENSE](LICENSE).
