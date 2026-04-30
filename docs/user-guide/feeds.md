# Managing Feeds

Add, list, and remove podcast feeds in Inkwell.

---

## Adding Feeds

### Basic Feed

```bash
inkwell add <RSS_URL> --feed-name <FEED_NAME>
```

**Example:**

```bash
inkwell add https://feeds.example.com/tech-podcast.rss --feed-name tech-show
```

Feed names can be human-readable. Inkwell stores a slug as the config key and keeps the original as the display name:

```bash
inkwell add https://feeds.example.com/show.rss --feed-name "Oren Meets World"
```

That feed is stored as `oren-meets-world`, but you can fetch or remove it with either the slug or the display name.

**Output:**

```
✓ Feed 'tech-show' added successfully
```

### Feed with Category

Organize feeds with categories for automatic template selection:

```bash
inkwell add https://example.com/feed.rss --feed-name startup-podcast --category business
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
inkwell add https://private.com/feed.rss --feed-name premium-show --auth
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

### YouTube Channels

Inkwell accepts any standard YouTube URL in `inkwell add` — paste a video URL, channel URL, `@handle`, `/c/`, or `/user/` link and inkwell resolves the right media-RSS endpoint for you:

```bash
# Any of these work — inkwell figures out the channel's RSS feed
inkwell add https://www.youtube.com/@orenmeetsworld --feed-name oren-meets-world
inkwell add https://www.youtube.com/watch?v=pKeZ5XK2vp4 --feed-name oren-meets-world
inkwell add https://www.youtube.com/channel/UC_tSQ6UQy2pROm-I0J7UBoA --feed-name oren-meets-world
```

If you just want to process one video without tracking the channel, use `inkwell fetch <video-url>`. You'll see a hint at the end inviting you to save the channel:

```
Want to track this channel? Re-run with --save-feed to save it as a feed.
```

To take it up on the offer, re-run with `--save-feed` — the feed name is auto-derived from the channel name, so you don't have to invent one:

```bash
inkwell fetch https://www.youtube.com/watch?v=pKeZ5XK2vp4 --save-feed
# → ✓ Saved channel as feed 'oren-meets-world'
#     Auto-named from channel metadata. To rename: inkwell rename oren-meets-world <new-name>.
```

Pass `--feed-name` if you want a specific name:

```bash
inkwell fetch https://www.youtube.com/watch?v=pKeZ5XK2vp4 --save-feed --feed-name oren
```

!!! note "Playlist URLs"
    Playlist URLs (`?list=…`) aren't supported yet — `inkwell add` rejects them with a clear error. Use the channel URL instead.

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

## Renaming Feeds

Rename a saved feed without losing its URL, category, or encrypted authentication settings:

```bash
inkwell rename old-name new-name
```

Feed names are normalized to lowercase slugs, so `inkwell rename old-name "New Name!"` becomes `new-name`.
The human-readable name is kept as the feed's display name in `inkwell list`.

Use `--force` only when you intentionally want to replace an existing destination feed:

```bash
inkwell rename old-name new-name --force
```

---

## Feed Organization Strategies

### By Category

```bash
inkwell add https://tech1.com/feed.rss --feed-name tech-podcast-1 --category tech
inkwell add https://tech2.com/feed.rss --feed-name tech-podcast-2 --category tech
inkwell add https://biz.com/feed.rss --feed-name business-show --category business
```

### By Priority (Naming Convention)

```bash
inkwell add https://example.com/feed.rss --feed-name 1-daily-podcast
inkwell add https://example.com/feed.rss --feed-name 2-weekly-podcast
inkwell add https://example.com/feed.rss --feed-name 3-archive-podcast
```

---

## Batch Operations

Add multiple feeds from a script:

```bash
#!/bin/bash

inkwell add https://feed1.com/rss --feed-name podcast-1 --category tech
inkwell add https://feed2.com/rss --feed-name podcast-2 --category business
inkwell add https://feed3.com/rss --feed-name podcast-3 --category interview

echo "All feeds added!"
```

---

## Naming Best Practices

- Use **lowercase and hyphens**: `tech-podcast`, `startup-stories`
- Keep names **short but descriptive**
- Special characters are normalized automatically: `my_podcast!` → `my-podcast`

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
