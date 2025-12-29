# Troubleshooting

Common issues and their solutions.

---

## Installation Issues

### "command not found: inkwell"

**Cause:** Inkwell is not in your PATH.

**Solutions:**

1. If installed with pip:
   ```bash
   # Check if installed
   pip show inkwell-cli

   # Reinstall
   pip install --upgrade inkwell-cli
   ```

2. If installed with pipx:
   ```bash
   pipx ensurepath
   # Restart your terminal
   ```

3. If installed from source:
   ```bash
   cd inkwell-cli
   pip install -e .
   ```

### "ffmpeg not found"

**Cause:** ffmpeg is not installed.

**Solutions:**

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg
```

Verify: `ffmpeg -version`

### "Python 3.10+ required"

**Cause:** Python version too old.

**Solution:**

```bash
# Check version
python --version

# Install newer Python
# macOS
brew install python@3.11

# Ubuntu
sudo apt-get install python3.11
```

---

## API Key Issues

### "GOOGLE_API_KEY not set"

**Cause:** Google AI API key not configured.

**Solutions:**

1. Via CLI (recommended):
   ```bash
   inkwell config set transcription.api_key "your-key"
   ```

2. Via environment:
   ```bash
   export GOOGLE_API_KEY="your-key"
   ```

Get a key: [Google AI Studio](https://aistudio.google.com/app/apikey)

### "ANTHROPIC_API_KEY not set"

**Cause:** Anthropic API key not configured (needed for interview mode).

**Solution:**

```bash
export ANTHROPIC_API_KEY="your-key"
```

Get a key: [Anthropic Console](https://console.anthropic.com/)

### "Invalid API key"

**Cause:** API key is incorrect or expired.

**Solutions:**

1. Verify the key is correct (no extra spaces)
2. Generate a new key from the provider console
3. Check API key permissions/quotas

---

## Feed Issues

### "Feed already exists"

**Cause:** A feed with that name already exists.

**Solutions:**

1. Use a different name:
   ```bash
   inkwell add URL --name different-name
   ```

2. Remove existing feed first:
   ```bash
   inkwell remove existing-name
   inkwell add URL --name existing-name
   ```

### "Feed not found"

**Cause:** No feed with that name exists.

**Solution:**

```bash
# List available feeds
inkwell list

# Use correct name from list
inkwell fetch correct-name --latest
```

### "Failed to fetch RSS feed"

**Cause:** Network error or invalid URL.

**Solutions:**

1. Verify the URL is correct
2. Check your internet connection
3. Try the URL in a browser
4. For private feeds, use `--auth`

---

## Processing Issues

### "Failed to transcribe episode"

**Possible causes:**

1. **Network timeout:**
   ```
   Reason: Network connection timeout
   ```
   Solution: Check internet connection and retry.

2. **No YouTube transcript:**
   ```
   Reason: No transcript available
   ```
   Solution: Gemini fallback should trigger automatically. Ensure API key is set.

3. **Audio download failed:**
   ```
   Reason: Failed to download audio
   ```
   Solution: Verify ffmpeg is installed. Check if URL is accessible.

### "Episode directory already exists"

**Cause:** You've already processed this episode.

**Solutions:**

1. Use `--overwrite` to replace:
   ```bash
   inkwell fetch URL --overwrite
   ```

2. Delete manually:
   ```bash
   rm -rf ~/inkwell-notes/podcast-date-title/
   ```

### "Invalid episode URL"

**Cause:** URL is not a valid podcast/YouTube URL.

**Solution:** Verify you're using a complete, valid URL:
- YouTube: `https://youtube.com/watch?v=...`
- Direct audio: `https://example.com/episode.mp3`

### "Rate limit exceeded"

**Cause:** Too many API requests.

**Solutions:**

1. Wait a few minutes and retry
2. Use a different provider:
   ```bash
   inkwell fetch URL --provider gemini
   ```
3. Check your API quota in the provider console

---

## Configuration Issues

### "Invalid configuration"

**Cause:** config.yaml has invalid values.

**Solution:**

```bash
inkwell config edit
```

Fix the invalid values shown in the error message.

### "YAML syntax error"

**Cause:** Malformed YAML in config file.

**Common issues:**

1. **Bad indentation:**
   ```yaml
   # Wrong
   interview:
   enabled: true

   # Correct
   interview:
     enabled: true
   ```

2. **Missing quotes:**
   ```yaml
   # Wrong (if value has special chars)
   api_key: AIza:key

   # Correct
   api_key: "AIza:key"
   ```

3. **Tab characters:**
   Use spaces only, not tabs.

**Solution:** Validate YAML online or use `inkwell config edit` to fix.

### "Encryption key not found"

**Cause:** `.keyfile` is missing (needed for encrypted credentials).

**Solution:**

```bash
# Re-add feeds with auth
inkwell remove my-feed
inkwell add URL --name my-feed --auth
```

The keyfile is auto-generated. Don't delete it if you have encrypted credentials.

---

## Interview Issues

### "Interview session lost"

**Cause:** Session was interrupted and can't be found.

**Solution:**

```bash
# List all sessions
inkwell interview sessions

# Resume by ID
inkwell interview resume <session-id>
```

### "Interview cost too high"

**Solutions:**

1. Reduce question count:
   ```bash
   inkwell fetch URL --interview --max-questions 3
   ```

2. Set cost limit in config:
   ```yaml
   interview:
     max_cost_per_interview: 0.20
   ```

---

## Output Issues

### "Wikilinks not working in Obsidian"

**Cause:** Obsidian wikilinks setting disabled.

**Solution:**

1. Open Obsidian Settings
2. Go to Files & Links
3. Enable "Use [[Wikilinks]]"

### "Dataview queries not working"

**Cause:** Dataview plugin not installed.

**Solution:**

1. Open Obsidian Settings
2. Go to Community plugins
3. Browse and install "Dataview"
4. Enable the plugin

### "Frontmatter not parsed"

**Cause:** Malformed YAML frontmatter.

**Solution:** Check for:
- Proper `---` delimiters at start and end
- No tabs (use spaces)
- Valid YAML syntax

---

## Debug Mode

Enable verbose logging to troubleshoot issues:

```bash
# Set debug level
inkwell config set log_level DEBUG

# View logs
tail -f ~/.local/state/inkwell/inkwell.log

# Run command
inkwell fetch URL --latest

# Check logs for details
```

---

## Getting Help

If you can't resolve an issue:

1. **Check logs:**
   ```bash
   cat ~/.local/state/inkwell/inkwell.log
   ```

2. **Search existing issues:**
   [GitHub Issues](https://github.com/chekos/inkwell-cli/issues)

3. **Open a new issue** with:
   - Inkwell version (`inkwell version`)
   - Python version (`python --version`)
   - OS and version
   - Full error message
   - Steps to reproduce
   - Relevant log output

---

## Common Error Codes

| Code | Meaning | Common Cause |
|------|---------|--------------|
| 1 | General error | Various - check message |
| 2 | Configuration error | Invalid config.yaml |
| 3 | Network error | Connection issues |
| 4 | API error | Invalid key or rate limit |
