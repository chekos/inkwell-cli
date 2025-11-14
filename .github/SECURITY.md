# Security Policy

## Supported Versions

We actively support the following versions of Inkwell CLI with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

**DO NOT** report security vulnerabilities through public GitHub issues.

Instead, please report security vulnerabilities by email to:

**[chekos@users.noreply.github.com]**

Please include the following information in your report:

- **Description** of the vulnerability
- **Steps to reproduce** the issue
- **Potential impact** of the vulnerability
- **Suggested fix** (if you have one)
- **Your contact information** for follow-up

### What to Expect

- We will acknowledge receipt of your vulnerability report within **48 hours**
- We will provide a more detailed response within **5 business days** indicating next steps
- We will keep you informed of the progress towards a fix and announcement
- We may ask for additional information or guidance

### Disclosure Policy

- We request that you give us reasonable time to investigate and fix the issue before public disclosure
- We will credit you in the security advisory (unless you prefer to remain anonymous)
- Once a fix is available, we will publish a security advisory on GitHub

## Security Best Practices for Users

### API Keys

**CRITICAL**: Never commit API keys to version control.

```bash
# ✅ Good: Use environment variables
export GOOGLE_API_KEY="your-api-key"
export ANTHROPIC_API_KEY="your-api-key"

# ✅ Good: Use .env file (add to .gitignore)
echo "GOOGLE_API_KEY=your-api-key" > .env
echo "ANTHROPIC_API_KEY=your-api-key" >> .env
echo ".env" >> .gitignore

# ❌ Bad: Hardcoding in config files that are committed
```

### Credential Storage

Inkwell stores credentials using encrypted storage:

- **Location**: `~/.config/inkwell/credentials.json`
- **Encryption**: Fernet (symmetric encryption)
- **Key derivation**: PBKDF2 with SHA256

**To manage credentials**:

```bash
# Add encrypted credential
inkwell config set-credential <provider-name>

# Remove credential
inkwell config remove-credential <provider-name>

# View stored credentials (encrypted)
cat ~/.config/inkwell/credentials.json
```

### Private Podcast Feeds

When using private/paid podcast feeds with authentication:

1. **Use encrypted credential storage**:
   ```bash
   inkwell add "https://private-feed.com/rss" --name premium --auth
   ```

2. **Never share feed URLs** that contain authentication tokens
3. **Rotate credentials regularly** if the feed provider supports it

### File Permissions

Ensure proper file permissions on sensitive files:

```bash
# Config directory should be readable only by you
chmod 700 ~/.config/inkwell

# Credential files should be readable only by you
chmod 600 ~/.config/inkwell/credentials.json
chmod 600 ~/.config/inkwell/config.yaml
```

### API Key Rotation

**Best practice**: Rotate your API keys regularly (every 90 days recommended)

```bash
# 1. Generate new API key from provider
# 2. Update environment variables
export GOOGLE_API_KEY="new-key"
export ANTHROPIC_API_KEY="new-key"

# 3. Or update encrypted credentials
inkwell config set-credential google
inkwell config set-credential anthropic

# 4. Revoke old API keys from provider dashboard
```

### Network Security

- Inkwell makes HTTPS requests to:
  - Google AI (Gemini) API: `https://generativelanguage.googleapis.com`
  - Anthropic (Claude) API: `https://api.anthropic.com`
  - YouTube: `https://www.youtube.com`
  - Podcast RSS feeds (user-provided)

- **Verify** RSS feed URLs before adding them to avoid malicious feeds
- Use **HTTPS** URLs when possible for podcast feeds

### Docker Security

When running Inkwell in Docker:

```bash
# ✅ Good: Use environment variables
docker run -e GOOGLE_API_KEY -e ANTHROPIC_API_KEY inkwell-cli

# ✅ Good: Use Docker secrets
echo "your-api-key" | docker secret create google_api_key -

# ❌ Bad: Hardcoding in Dockerfile or docker-compose.yml
```

## Known Security Considerations

### API Keys in Memory

- API keys are stored in memory during runtime
- Keys are passed to LLM provider SDKs
- Keys are **never** logged or written to disk (except encrypted storage)

### Transcript Caching

- Transcripts are cached locally in `~/.cache/inkwell/transcripts/`
- Cache files are **not encrypted** (contains public podcast content)
- Cache files use SHA256 hashes as filenames (no PII)

### Cost Tracking

- Cost data is stored in `~/.config/inkwell/costs.json`
- Contains: operation type, provider, cost, timestamp
- **Does not contain**: API keys, transcript content, or PII

## Security Hardening Checklist

For production deployments:

- [ ] API keys stored in environment variables or encrypted storage
- [ ] File permissions restricted (`chmod 600` on sensitive files)
- [ ] `.env` files added to `.gitignore`
- [ ] API keys rotated regularly (90 day policy)
- [ ] Docker secrets used for containerized deployments
- [ ] HTTPS used for all podcast feed URLs
- [ ] Pre-commit hooks enabled to prevent accidental key commits
- [ ] Security updates applied promptly

## Security Update Process

We follow responsible disclosure practices:

1. **Security issue reported** (via email)
2. **Issue confirmed** and severity assessed
3. **Fix developed** and tested
4. **Security advisory published** on GitHub Security Advisories
5. **Patch released** with version bump
6. **Users notified** via GitHub release notes

## Questions?

If you have questions about security practices or this policy, please open a [GitHub Discussion](https://github.com/chekos/inkwell-cli/discussions) or email the maintainers.

---

**Last updated**: 2025-11-14
