# Phase 1 Architecture Overview

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER (Terminal)                          │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CLI Layer (typer)                           │
│  ┌──────────┬──────────┬──────────┬────────────────────────┐   │
│  │ add      │ list     │ remove   │ config (show/set/edit) │   │
│  └──────────┴──────────┴──────────┴────────────────────────┘   │
│                   [Rich output formatting]                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
                ▼                               ▼
┌────────────────────────────┐   ┌──────────────────────────────┐
│    Config Manager          │   │    Feed Manager              │
│  ┌──────────────────────┐  │   │  ┌────────────────────────┐  │
│  │ - Load/save YAML     │  │   │  │ - Add/remove feeds     │  │
│  │ - Validate config    │  │   │  │ - List feeds           │  │
│  │ - Merge defaults     │  │   │  │ - Get feed by name     │  │
│  └──────────┬───────────┘  │   │  └───────────┬────────────┘  │
│             │              │   │              │               │
│             ▼              │   │              ▼               │
│  ┌──────────────────────┐  │   │  ┌────────────────────────┐  │
│  │ Credential Encryptor │  │   │  │ RSS Parser             │  │
│  │ - Fernet encryption  │  │   │  │ - Fetch feed (httpx)   │  │
│  │ - Key management     │  │   │  │ - Parse (feedparser)   │  │
│  └──────────────────────┘  │   │  │ - Extract metadata     │  │
│                            │   │  └────────────────────────┘  │
│  ┌──────────────────────┐  │   │  ┌────────────────────────┐  │
│  │ Pydantic Models      │  │   │  │ Feed Validator         │  │
│  │ - GlobalConfig       │  │   │  │ - URL validation       │  │
│  │ - FeedConfig         │  │   │  │ - Auth verification    │  │
│  │ - AuthConfig         │  │   │  └────────────────────────┘  │
│  └──────────────────────┘  │   │                              │
└────────────┬───────────────┘   └──────────────┬───────────────┘
             │                                  │
             ▼                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Filesystem (XDG Compliant)                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ ~/.config/inkwell/                                       │   │
│  │   ├── config.yaml        (GlobalConfig)                  │   │
│  │   ├── feeds.yaml         (Feed configurations)           │   │
│  │   └── .keyfile           (Encryption key, 600 perms)     │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ ~/.cache/inkwell/                                        │   │
│  │   └── inkwell.log        (Debug logs)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Examples

### Adding a Feed

```
User: inkwell add https://feed.url/rss --name "podcast" --auth
  │
  ├─► CLI: Parse arguments, prompt for credentials
  │
  ├─► FeedValidator: Validate URL is accessible
  │     │
  │     └─► httpx: Fetch feed with auth headers
  │
  ├─► RSSParser: Verify feed has episodes
  │     │
  │     └─► feedparser: Parse RSS/Atom feed
  │
  ├─► CredentialEncryptor: Encrypt username/password
  │     │
  │     └─► Fernet: Symmetric encryption
  │
  ├─► ConfigManager: Add feed to feeds.yaml
  │     │
  │     └─► Pydantic: Validate FeedConfig
  │
  └─► Rich: Display success message
```

### Listing Feeds

```
User: inkwell list
  │
  ├─► CLI: Invoke list command
  │
  ├─► ConfigManager: Load all feeds
  │     │
  │     ├─► Read ~/.config/inkwell/feeds.yaml
  │     │
  │     ├─► Pydantic: Validate each FeedConfig
  │     │
  │     └─► CredentialEncryptor: Decrypt credentials (for auth status)
  │
  └─► Rich: Display table with feed details
        │
        └─► Terminal: Pretty formatted table
```

### Loading Configuration

```
Application Start
  │
  ├─► ConfigManager: Load config
  │     │
  │     ├─► Check ~/.config/inkwell/config.yaml exists
  │     │     │
  │     │     ├─► If missing: Create from defaults
  │     │     └─► If exists: Load and parse YAML
  │     │
  │     ├─► Pydantic: Validate GlobalConfig
  │     │     │
  │     │     └─► If invalid: Show helpful error message
  │     │
  │     └─► Return validated config
  │
  └─► Setup logging based on config.log_level
```

## Security Architecture

### Credential Encryption Flow

```
┌─────────────────────────────────────────────────────────────┐
│ First Run: Key Generation                                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  CredentialEncryptor.__init__()                              │
│    │                                                          │
│    ├─► Check ~/.config/inkwell/.keyfile exists               │
│    │                                                          │
│    ├─► If missing:                                           │
│    │     │                                                    │
│    │     ├─► Fernet.generate_key() → 32-byte key             │
│    │     │                                                    │
│    │     ├─► Write to .keyfile                               │
│    │     │                                                    │
│    │     └─► chmod 0o600 (owner read/write only)             │
│    │                                                          │
│    └─► Load key into memory                                  │
│                                                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Encryption (Adding Feed)                                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  User enters: username="alice" password="secret123"          │
│    │                                                          │
│    ├─► CredentialEncryptor.encrypt("alice")                  │
│    │     │                                                    │
│    │     ├─► Fernet(key).encrypt(b"alice")                   │
│    │     │                                                    │
│    │     └─► Return: "gAAAAABl..." (base64 ciphertext)       │
│    │                                                          │
│    ├─► CredentialEncryptor.encrypt("secret123")              │
│    │     │                                                    │
│    │     └─► Return: "gAAAAABl..." (different ciphertext)    │
│    │                                                          │
│    └─► Save to feeds.yaml:                                   │
│          auth:                                               │
│            type: basic                                       │
│            username: gAAAAABl...                             │
│            password: gAAAAABl...                             │
│                                                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Decryption (Using Feed)                                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  RSSParser needs credentials to fetch feed                   │
│    │                                                          │
│    ├─► Load FeedConfig from feeds.yaml                       │
│    │     │                                                    │
│    │     └─► auth.username = "gAAAAABl..."                   │
│    │                                                          │
│    ├─► CredentialEncryptor.decrypt("gAAAAABl...")            │
│    │     │                                                    │
│    │     ├─► Fernet(key).decrypt(b"gAAAAABl...")             │
│    │     │                                                    │
│    │     └─► Return: "alice" (plaintext)                     │
│    │                                                          │
│    ├─► Build HTTP Basic Auth header                          │
│    │                                                          │
│    └─► httpx.get(url, auth=("alice", "secret123"))           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Security Properties

✅ **At Rest**: All credentials encrypted in `feeds.yaml`
✅ **Key Storage**: Encryption key protected with 600 permissions
✅ **In Transit**: HTTPS enforced for feed fetching
✅ **In Memory**: Credentials decrypted only when needed, not persisted
✅ **Logging**: No plaintext credentials ever logged

⚠️ **Limitations**:
- Key stored on disk (vs hardware security module)
- Single encryption key for all feeds
- No key rotation mechanism (Phase 1)

🔮 **Future Enhancements** (v0.2+):
- Optional system keyring integration
- Per-feed encryption keys
- Key rotation support
- Hardware security module support

## Error Handling Strategy

### Exception Hierarchy

```
InkwellError (base)
  │
  ├─► ConfigError
  │     ├─► InvalidConfigError
  │     ├─► ConfigNotFoundError
  │     └─► EncryptionError
  │
  ├─► FeedError
  │     ├─► FeedNotFoundError
  │     ├─► DuplicateFeedError
  │     ├─► FeedParseError
  │     └─► AuthenticationError
  │
  └─► NetworkError
        ├─► ConnectionError
        └─► TimeoutError
```

### User-Facing Error Messages

**Bad**: Generic error
```
Error: Failed to add feed
```

**Good**: Helpful error with context
```
✗ Failed to add feed 'my-podcast'

  Could not connect to https://feed.url/rss

  Possible causes:
    • URL is incorrect or unreachable
    • Network connection is down
    • Feed requires authentication (try --auth flag)

  Debug log: ~/.cache/inkwell/inkwell.log
```

## Testing Architecture

### Test Pyramid

```
                    ┌────────────┐
                    │ Manual E2E │  ← Day 7
                    │  Testing   │
                    └────────────┘
                   ┌──────────────┐
                   │ Integration  │  ← Day 5
                   │  Tests       │
                   │ (CLI cmds)   │
                   └──────────────┘
              ┌───────────────────────┐
              │    Unit Tests         │  ← Days 2-4
              │  (90%+ coverage)      │
              │                       │
              │ - Config Manager      │
              │ - Crypto              │
              │ - Feed Parser         │
              │ - Validators          │
              └───────────────────────┘
```

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures
│     ├─► tmp_config_dir()
│     ├─► sample_feed()
│     └─► mock_httpx()
│
├── fixtures/
│   ├── valid_feed.xml       # Real RSS 2.0 feed
│   ├── atom_feed.xml        # Atom format
│   ├── malformed_feed.xml   # Bozo test
│   └── sample_config.yaml   # Pre-configured
│
├── unit/
│   ├── test_config.py       # ConfigManager
│   │     ├─► test_load_default_config()
│   │     ├─► test_save_and_load_roundtrip()
│   │     ├─► test_invalid_config_raises()
│   │     └─► test_merge_user_defaults()
│   │
│   ├── test_crypto.py       # CredentialEncryptor
│   │     ├─► test_encrypt_decrypt_roundtrip()
│   │     ├─► test_key_generation()
│   │     ├─► test_key_permissions()
│   │     └─► test_empty_string_handling()
│   │
│   └── test_feeds.py        # RSSParser
│         ├─► test_parse_valid_rss()
│         ├─► test_parse_atom_feed()
│         ├─► test_extract_episode_metadata()
│         └─► test_auth_header_construction()
│
└── integration/
    └── test_cli.py          # End-to-end CLI tests
          ├─► test_add_feed_command()
          ├─► test_list_feeds_output()
          ├─► test_remove_feed_confirmation()
          ├─► test_config_commands()
          └─► test_error_messages()
```

## Dependencies Graph

```
┌──────────────────────────────────────────────────────────────┐
│                        inkwell                                │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  typer[all] ────────► rich ──────────┐                       │
│                                       │                       │
│  feedparser ──────────────────────────┤                       │
│                                       │                       │
│  pydantic ────────► pydantic-settings ┤                       │
│                                       ├──► Terminal Output    │
│  platformdirs ────────────────────────┤                       │
│                                       │                       │
│  httpx ────────────────────────────────┤                       │
│                                       │                       │
│  cryptography ────────────────────────┘                       │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Dev Dependencies                                        │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │                                                         │ │
│  │  ruff ──────────► Linting & Formatting                 │ │
│  │  mypy ──────────► Type Checking                        │ │
│  │  pytest ────────► Testing                              │ │
│  │  pytest-cov ───► Coverage Reporting                    │ │
│  │  pytest-mock ──► Mocking                               │ │
│  │  respx ────────► HTTP Mocking                          │ │
│  │  pre-commit ───► Git Hooks                             │ │
│  │                                                         │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
└──────────────────────────────────────────────────────────────┘

Total Production Dependencies: 6 packages
Total Dev Dependencies: 7 packages
```

## Configuration Schema

### Complete Type Definitions

```python
# Literal types for enums
AuthType = Literal["none", "basic", "bearer"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

# Auth configuration
class AuthConfig(BaseModel):
    type: AuthType = "none"
    username: Optional[str] = None  # Encrypted
    password: Optional[str] = None  # Encrypted
    token: Optional[str] = None     # Encrypted (for bearer)

# Individual feed
class FeedConfig(BaseModel):
    url: HttpUrl
    auth: AuthConfig = Field(default_factory=AuthConfig)
    category: Optional[str] = None
    custom_templates: list[str] = Field(default_factory=list)

# Global settings
class GlobalConfig(BaseModel):
    version: str = "1"
    default_output_dir: Path = Path("~/podcasts")
    transcription_model: str = "gemini-2.0-flash-exp"
    interview_model: str = "claude-sonnet-4-5"
    youtube_check: bool = True
    log_level: LogLevel = "INFO"
    default_templates: list[str] = Field(
        default_factory=lambda: ["summary", "quotes", "key-concepts"]
    )
    template_categories: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "tech": ["tools-mentioned", "frameworks-mentioned"],
            "interview": ["books-mentioned", "people-mentioned"],
        }
    )

# Feed collection
class Feeds(BaseModel):
    feeds: dict[str, FeedConfig] = Field(default_factory=dict)
```

---

## Next Steps

With this architecture in place, we're ready to:

1. **Scaffold the project** (Day 1)
2. **Implement each module** (Days 2-6)
3. **Test and polish** (Day 7)

See [Phase 1 Implementation Plan](../devlog/2025-11-06-phase-1-implementation-plan.md) for the detailed breakdown.
