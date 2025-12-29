# Installation

Complete installation instructions for Inkwell.

---

## Requirements

- **Python 3.10+** - Check with `python --version`
- **ffmpeg** - Required for audio processing
- **pip or pipx** - Python package installer

---

## Install Inkwell

### Using pip (Recommended)

```bash
pip install inkwell-cli
```

### Using pipx (Isolated)

```bash
pipx install inkwell-cli
```

### From Source

```bash
# Clone the repository
git clone https://github.com/chekos/inkwell-cli.git
cd inkwell-cli

# Install with uv (recommended for development)
uv sync --dev

# Or with pip
pip install -e .
```

### Verify Installation

```bash
inkwell --version
# Output: Inkwell CLI vX.X.X
```

---

## Install ffmpeg

ffmpeg is required for audio processing.

### macOS

```bash
brew install ffmpeg
```

### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

### Windows

Download from [ffmpeg.org](https://ffmpeg.org/download.html) or use:

```bash
# With Chocolatey
choco install ffmpeg

# With Scoop
scoop install ffmpeg
```

### Verify ffmpeg

```bash
ffmpeg -version
```

---

## API Keys

Inkwell requires API keys for transcription and extraction.

### Google AI (Required)

Used for transcription (Gemini) and content extraction.

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click "Create API Key"
3. Copy your API key

**Configure via CLI (Recommended):**

```bash
inkwell config set transcription.api_key "your-google-ai-api-key"
```

**Or via environment variable:**

```bash
export GOOGLE_API_KEY="your-google-ai-api-key"

# Make permanent (add to ~/.bashrc or ~/.zshrc)
echo 'export GOOGLE_API_KEY="your-key"' >> ~/.zshrc
```

### Anthropic (Optional)

Required only for Interview Mode.

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Create an API key
3. Configure:

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

---

## Configuration

Inkwell creates configuration files automatically on first run.

### Default Locations

| Platform | Config Directory |
|----------|-----------------|
| Linux/macOS | `~/.config/inkwell/` |
| Windows | `%APPDATA%\inkwell\` |

### Files Created

```
~/.config/inkwell/
├── config.yaml    # Global settings
├── feeds.yaml     # Feed definitions
└── .keyfile       # Encryption key (auto-generated)
```

### Verify Setup

```bash
inkwell config show
```

---

## Next Steps

- [Quick Start](quickstart.md) - Process your first episode
- [Managing Feeds](../user-guide/feeds.md) - Add your podcasts
- [Configuration](../user-guide/configuration.md) - Customize settings
