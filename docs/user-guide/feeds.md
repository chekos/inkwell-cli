# Managing Feeds

Add, list, and remove podcast feeds in Inkwell.

---

## Adding Feeds

### Basic Feed

```bash
inkwell add <RSS_URL> --name <FEED_NAME>
```

**Example:**

```bash
inkwell add https://feeds.example.com/tech-podcast.rss --name tech-show
```

**Output:**

```
✓ Feed 'tech-show' added successfully
```

### Feed with Category

Organize feeds with categories for automatic template selection:

```bash
inkwell add https://example.com/feed.rss --name startup-podcast --category business
```

**Common categories:**

| Category | Description | Auto-selected Templates |
|----------|-------------|------------------------|
| `tech` | Technology podcasts | summary, quotes, tools-mentioned |
| `business` | Business & entrepreneurship | summary, quotes, key-concepts |
| `interview` | Interview shows | summary, quotes |
| `education` | Educational content | summary, key-concepts |

### Private/Paid Feeds

For premium podcasts requiring authentication:

```bash
inkwell add https://private.com/feed.rss --name premium-show --auth
```

Inkwell prompts for credentials:

```
Authentication required
Auth type (basic/bearer): basic
Username: user@example.com
Password: ********

✓ Feed 'premium-show' added successfully
  Credentials encrypted and stored securely
```

**Authentication types:**

- **Basic Auth** - Username + password (most common)
- **Bearer Token** - API token or key

!!! note "Security"
    All credentials are encrypted using Fernet symmetric encryption before storage.

---

## Listing Feeds

View all configured feeds:

```bash
inkwell list
```

**Output:**

```
╭─────────────────────────────────────────────────────────╮
│           Configured Podcast Feeds                      │
├────────────────┬───────────────────┬──────┬─────────────┤
│ Name           │ URL               │ Auth │ Category    │
├────────────────┼───────────────────┼──────┼─────────────┤
│ tech-show      │ feeds.example...  │ —    │ tech        │
│ premium-show   │ private.com/...   │ ✓    │ —           │
╰────────────────┴───────────────────┴──────┴─────────────╯

Total: 2 feed(s)
```

---

## Removing Feeds

### With Confirmation

```bash
inkwell remove my-podcast
```

```
Feed: my-podcast
URL:  https://example.com/feed.rss

Are you sure you want to remove this feed? [y/N]: y

✓ Feed 'my-podcast' removed
```

### Skip Confirmation

```bash
inkwell remove my-podcast --force
```

---

## Feed Organization Strategies

### By Category

```bash
inkwell add https://tech1.com/feed.rss --name tech-podcast-1 --category tech
inkwell add https://tech2.com/feed.rss --name tech-podcast-2 --category tech
inkwell add https://biz.com/feed.rss --name business-show --category business
```

### By Priority (Naming Convention)

```bash
inkwell add https://example.com/feed.rss --name 1-daily-podcast
inkwell add https://example.com/feed.rss --name 2-weekly-podcast
inkwell add https://example.com/feed.rss --name 3-archive-podcast
```

---

## Batch Operations

Add multiple feeds from a script:

```bash
#!/bin/bash

inkwell add https://feed1.com/rss --name podcast-1 --category tech
inkwell add https://feed2.com/rss --name podcast-2 --category business
inkwell add https://feed3.com/rss --name podcast-3 --category interview

echo "All feeds added!"
```

---

## Naming Best Practices

- Use **lowercase and hyphens**: `tech-podcast`, `startup-stories`
- Keep names **short but descriptive**
- Avoid special characters: `my_podcast!` → `my-podcast`

---

## Troubleshooting

### "Feed already exists"

```
✗ Feed 'my-podcast' already exists. Use update to modify it.
  Use 'inkwell remove my-podcast' first, or choose a different name
```

**Solution:** Remove the existing feed first or use a different name.

### "Feed not found"

```
✗ Feed 'non-existent' not found

Available feeds:
  • my-podcast
  • tech-show
```

**Solution:** Check feed name with `inkwell list`.

---

## Next Steps

- [Processing Episodes](processing.md) - Fetch and process episodes
- [Configuration](configuration.md) - Configure default settings
