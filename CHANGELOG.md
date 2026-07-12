# Changelog

All notable changes to this project are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org/).

## [1.0.0] - 2026-07-11

### Added

- MCP tools: `generate_image`, `generate_images_batch`, `generate_text`, `generate_texts_batch`, `get_settings`, `update_settings`
- Batch generation of up to 10 images or text responses in parallel
- Image editing via input image plus prompt
- Persistent defaults (models, aspect ratio, image size, output directory) in `settings.json`

### Changed

- Migrated to uv-managed packaging: `pyproject.toml`, `uv.lock`, `src/banana_mcp/` layout, `banana-mcp` console script
