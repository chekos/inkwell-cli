# Installation

Complete installation instructions for Inkwell.

---

## Requirements

- **Python 3.10+** - Check with `python --version`
- **ffmpeg** - Required for audio processing
- **uv** - Modern Python package installer ([install uv](https://docs.astral.sh/uv/getting-started/installation/))
- **Tesseract + the `ocr` extra** - Optional; required for local image/scanned-PDF OCR

---

## Install Inkwell

### Using uv (Recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install inkwell as a tool
uv tool install inkwell-cli
```

To include local OCR support:

```bash
uv tool install 'inkwell-cli[ocr]'
```

### Using pip

```bash
pip install inkwell-cli
```

### From Source

```bash
# Clone the repository
git clone https://github.com/chekos/inkwell-cli.git
cd inkwell-cli

# Install with uv (recommended)
uv sync --dev

# Include local OCR development dependencies
uv sync --dev --extra ocr

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

## Install Local OCR Support

The Python extra supplies Pillow, `pytesseract`, and PDFium rendering. Tesseract
itself is a local system executable and must also be installed.

### macOS

```bash
brew install tesseract
```

Install additional language packs when needed:

```bash
brew install tesseract-lang
```

### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

Language data is packaged separately on many distributions, for example
`tesseract-ocr-spa` for Spanish.

### Windows

Install a current Tesseract distribution and add its installation directory to
`PATH`, then install the Inkwell `ocr` extra shown above.

### Verify OCR

```bash
tesseract --version
inkwell plugins validate tesseract
inkwell plugins list --type ocr
```

OCR has no hosted-account requirement. Image/PDF bytes remain local during text
recognition.

---

## API Keys

Inkwell requires API keys for transcription and extraction.

### Google AI (Required)

Used for Gemini transcription and content extraction.

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click "Create API Key"
3. Copy your API key

**Configure via CLI (Recommended):**

```bash
inkwell config set transcription.api_key "your-google-ai-api-key"
```

This key is also used for Gemini extraction unless you set
`extraction.gemini_api_key` separately. The Gemini transcription model is
configurable at `transcription.model_name`; generated config files currently
default to `gemini-2.5-flash`.

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

---

## Distribution

| Method | Status |
|--------|--------|
| `uv tool install inkwell-cli` | **Supported** (recommended) |
| PyPI package (`pip install inkwell-cli`) | **Supported** |
| Docker image | Not yet supported |
| Homebrew formula | Not yet supported |

Docker and Homebrew packaging are not currently provided. If either install
path would help your workflow, open a [GitHub issue](https://github.com/chekos/inkwell-cli/issues)
so demand can be tracked.

---

## Next Steps

- [Quick Start](quickstart.md) - Process your first episode
- [Managing Feeds](../user-guide/feeds.md) - Add your podcasts
- [Configuration](../user-guide/configuration.md) - Customize settings
