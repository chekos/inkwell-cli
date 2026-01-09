# Dataview Query Examples for Inkwell Notes

This guide provides ready-to-use Dataview queries for organizing and discovering your podcast notes created by Inkwell.

## Table of Contents

- [Setup](#setup)
- [Basic Queries](#basic-queries)
- [Episode Discovery](#episode-discovery)
- [Content Analysis](#content-analysis)
- [Task Management](#task-management)
- [Advanced Queries](#advanced-queries)
- [Dashboard Examples](#dashboard-examples)

---

## Setup

### Prerequisites

1. Install [Dataview plugin](https://github.com/blacksmithgu/obsidian-dataview) in Obsidian
2. Enable Dataview in Settings → Community Plugins
3. Process episodes with Inkwell (automatically creates Dataview-compatible frontmatter)

### Frontmatter Fields

Inkwell generates rich frontmatter for every episode:

```yaml
---
template: summary
podcast: Lex Fridman Podcast
episode: Cal Newport on Deep Work
episode_number: 261
created_date: 2025-11-10
episode_date: 2023-05-15
duration_minutes: 180
url: https://example.com/episode
host: Lex Fridman
guest: Cal Newport
people:
  - Cal Newport
  - Andrew Huberman
tags:
  - podcast/lex-fridman
  - topic/ai
  - theme/productivity
topics:
  - ai
  - productivity
status: inbox
priority: high
rating: 5
extracted_with: gemini
cost_usd: 0.0045
word_count: 25000
has_wikilinks: true
has_interview: true
---
```

---

## Basic Queries

### 1. List All Podcast Episodes

```dataview
TABLE podcast, episode, created_date
FROM "podcasts"
WHERE template = "summary"
SORT created_date DESC
```

### 2. Episodes by Specific Podcast

```dataview
TABLE episode, episode_date, duration_minutes, rating
FROM "podcasts"
WHERE podcast = "Lex Fridman Podcast"
SORT episode_date DESC
```

### 3. Recent Episodes (Last 30 Days)

```dataview
TABLE podcast, episode, created_date
FROM "podcasts"
WHERE template = "summary"
  AND date(created_date) >= date(today) - dur(30 days)
SORT created_date DESC
```

### 4. Episodes with Ratings

```dataview
TABLE podcast, episode, rating, episode_date
FROM "podcasts"
WHERE rating != null
SORT rating DESC, episode_date DESC
```

---

## Episode Discovery

### 5. Find Episodes by Guest

```dataview
TABLE podcast, episode, episode_date, duration_minutes
FROM "podcasts"
WHERE contains(guest, "Cal Newport") OR contains(people, "Cal Newport")
SORT episode_date DESC
```

### 6. Episodes by Topic

```dataview
TABLE podcast, episode, topics, episode_date
FROM "podcasts"
WHERE contains(topics, "ai")
SORT episode_date DESC
```

### 7. Find Long Episodes (Over 2 Hours)

```dataview
TABLE podcast, episode, duration_minutes, episode_date
FROM "podcasts"
WHERE duration_minutes > 120
SORT duration_minutes DESC
```

### 8. Episodes with Specific Tag

```dataview
TABLE podcast, episode, tags, episode_date
FROM "podcasts"
WHERE contains(tags, "topic/productivity")
SORT episode_date DESC
```

### 9. Find Episodes Mentioning Specific Person

```dataview
TABLE podcast, episode, people, episode_date
FROM "podcasts"
WHERE contains(people, "Andrew Huberman")
SORT episode_date DESC
```

---

## Content Analysis

### 10. Episodes with Interview Notes

```dataview
TABLE podcast, episode, has_interview, created_date
FROM "podcasts"
WHERE has_interview = true
SORT created_date DESC
```

### 11. Episodes with Wikilinks

```dataview
TABLE podcast, episode, has_wikilinks, created_date
FROM "podcasts"
WHERE has_wikilinks = true
SORT created_date DESC
```

### 12. Most Expensive Extractions

```dataview
TABLE podcast, episode, cost_usd, extracted_with
FROM "podcasts"
WHERE template = "summary"
SORT cost_usd DESC
LIMIT 20
```

### 13. Episodes by Extraction Provider

```dataview
TABLE podcast, episode, extracted_with, cost_usd
FROM "podcasts"
WHERE extracted_with = "gemini"
SORT created_date DESC
```

### 14. Total Extraction Cost

```dataviewjs
const pages = dv.pages('"podcasts"')
  .where(p => p.template === "summary");

const totalCost = pages
  .map(p => p.cost_usd || 0)
  .reduce((sum, cost) => sum + cost, 0);

const avgCost = totalCost / pages.length;

dv.header(3, "Extraction Statistics");
dv.paragraph(`**Total episodes:** ${pages.length}`);
dv.paragraph(`**Total cost:** $${totalCost.toFixed(4)}`);
dv.paragraph(`**Average cost per episode:** $${avgCost.toFixed(4)}`);
```

### 15. Word Count Statistics

```dataviewjs
const pages = dv.pages('"podcasts"')
  .where(p => p.word_count != null);

const totalWords = pages
  .map(p => p.word_count)
  .reduce((sum, count) => sum + count, 0);

const avgWords = totalWords / pages.length;
const maxWords = Math.max(...pages.map(p => p.word_count));

dv.header(3, "Word Count Statistics");
dv.paragraph(`**Total words transcribed:** ${totalWords.toLocaleString()}`);
dv.paragraph(`**Average words per episode:** ${Math.round(avgWords).toLocaleString()}`);
dv.paragraph(`**Longest transcript:** ${maxWords.toLocaleString()} words`);
```

---

## Task Management

### 16. Inbox: Unprocessed Episodes

```dataview
TABLE podcast, episode, created_date, priority
FROM "podcasts"
WHERE status = "inbox"
SORT priority DESC, created_date DESC
```

### 17. Currently Reading

```dataview
TABLE podcast, episode, created_date, rating
FROM "podcasts"
WHERE status = "reading"
SORT created_date DESC
```

### 18. Completed Episodes

```dataview
TABLE podcast, episode, rating, episode_date
FROM "podcasts"
WHERE status = "completed"
SORT episode_date DESC
```

### 19. High Priority Episodes

```dataview
TABLE podcast, episode, priority, status, created_date
FROM "podcasts"
WHERE priority = "high" AND status != "completed"
SORT created_date DESC
```

### 20. Episodes to Review (Unrated)

```dataview
TABLE podcast, episode, created_date
FROM "podcasts"
WHERE rating = null AND status = "completed"
SORT created_date DESC
```

---

## Advanced Queries

### 21. Episodes by Podcast with Stats

```dataviewjs
const podcasts = dv.pages('"podcasts"')
  .where(p => p.template === "summary")
  .groupBy(p => p.podcast);

const stats = podcasts.map(group => {
  const episodes = group.rows;
  const avgRating = episodes
    .where(e => e.rating != null)
    .map(e => e.rating)
    .reduce((sum, r, _, arr) => sum + r / arr.length, 0);

  return {
    podcast: group.key,
    count: episodes.length,
    avgRating: avgRating.toFixed(1),
    totalDuration: episodes
      .map(e => e.duration_minutes || 0)
      .reduce((sum, d) => sum + d, 0)
  };
});

dv.table(
  ["Podcast", "Episodes", "Avg Rating", "Total Hours"],
  stats
    .sort((a, b) => b.count - a.count)
    .map(s => [
      s.podcast,
      s.count,
      s.avgRating || "N/A",
      Math.round(s.totalDuration / 60)
    ])
);
```

### 22. Topics Matrix

```dataviewjs
const pages = dv.pages('"podcasts"')
  .where(p => p.topics && p.topics.length > 0);

const topicCounts = {};
pages.forEach(p => {
  p.topics.forEach(topic => {
    topicCounts[topic] = (topicCounts[topic] || 0) + 1;
  });
});

const topTopics = Object.entries(topicCounts)
  .sort((a, b) => b[1] - a[1])
  .slice(0, 15);

dv.header(3, "Top 15 Topics");
dv.table(
  ["Topic", "Episodes", "Percentage"],
  topTopics.map(([topic, count]) => [
    topic,
    count,
    `${Math.round(count / pages.length * 100)}%`
  ])
);
```

### 23. Guest Appearances

```dataviewjs
const pages = dv.pages('"podcasts"')
  .where(p => p.guest != null);

const guestCounts = {};
pages.forEach(p => {
  guestCounts[p.guest] = (guestCounts[p.guest] || 0) + 1;
});

const topGuests = Object.entries(guestCounts)
  .sort((a, b) => b[1] - a[1])
  .slice(0, 10);

dv.header(3, "Top 10 Guests");
dv.table(
  ["Guest", "Appearances"],
  topGuests.map(([guest, count]) => [guest, count])
);
```

### 24. Listening Time by Podcast

```dataviewjs
const pages = dv.pages('"podcasts"')
  .where(p => p.duration_minutes != null)
  .groupBy(p => p.podcast);

const listeningTime = pages.map(group => {
  const totalMinutes = group.rows
    .map(e => e.duration_minutes)
    .reduce((sum, d) => sum + d, 0);

  return {
    podcast: group.key,
    episodes: group.rows.length,
    hours: Math.round(totalMinutes / 60),
    days: (totalMinutes / 60 / 24).toFixed(1)
  };
}).sort((a, b) => b.hours - a.hours);

dv.table(
  ["Podcast", "Episodes", "Hours", "Days"],
  listeningTime.map(p => [p.podcast, p.episodes, p.hours, p.days])
);
```

### 25. Timeline: Episodes Over Time

```dataviewjs
const pages = dv.pages('"podcasts"')
  .where(p => p.created_date != null);

const byMonth = {};
pages.forEach(p => {
  const month = p.created_date.substring(0, 7); // YYYY-MM
  byMonth[month] = (byMonth[month] || 0) + 1;
});

const timeline = Object.entries(byMonth)
  .sort((a, b) => a[0].localeCompare(b[0]));

dv.header(3, "Episodes Processed Over Time");
dv.table(
  ["Month", "Episodes", "Trend"],
  timeline.map(([month, count]) => {
    const bar = "█".repeat(Math.min(count, 20));
    return [month, count, bar];
  })
);
```

---

## Dashboard Examples

### 26. Personal Podcast Dashboard

Create a note called `Podcast Dashboard.md`:

````markdown
# Podcast Dashboard

## Stats

```dataviewjs
const pages = dv.pages('"podcasts"').where(p => p.template === "summary");
const inbox = pages.where(p => p.status === "inbox").length;
const reading = pages.where(p => p.status === "reading").length;
const completed = pages.where(p => p.status === "completed").length;

const totalHours = pages
  .map(p => p.duration_minutes || 0)
  .reduce((sum, m) => sum + m, 0) / 60;

dv.paragraph(`📚 **Total Episodes:** ${pages.length}`);
dv.paragraph(`📥 **Inbox:** ${inbox}`);
dv.paragraph(`📖 **Reading:** ${reading}`);
dv.paragraph(`✅ **Completed:** ${completed}`);
dv.paragraph(`⏱️ **Total Hours:** ${Math.round(totalHours)}`);
```

## Inbox (Need to Process)

```dataview
TABLE episode, priority, created_date
FROM "podcasts"
WHERE status = "inbox"
SORT priority DESC, created_date DESC
LIMIT 10
```

## Currently Reading

```dataview
TABLE podcast, episode, created_date
FROM "podcasts"
WHERE status = "reading"
SORT created_date DESC
```

## Top Rated Episodes

```dataview
TABLE podcast, episode, rating, episode_date
FROM "podcasts"
WHERE rating >= 4
SORT rating DESC, episode_date DESC
LIMIT 10
```

## Recent Activity

```dataview
TABLE podcast, episode, status, created_date
FROM "podcasts"
SORT created_date DESC
LIMIT 15
```
````

### 27. Topic Explorer Dashboard

Create a note called `Topic Explorer.md`:

````markdown
# Topic Explorer

## AI & Machine Learning

```dataview
TABLE podcast, episode, rating, episode_date
FROM "podcasts"
WHERE contains(topics, "ai") OR contains(topics, "machine-learning")
SORT episode_date DESC
```

## Productivity & Focus

```dataview
TABLE podcast, episode, rating, episode_date
FROM "podcasts"
WHERE contains(topics, "productivity") OR contains(topics, "focus")
SORT episode_date DESC
```

## Business & Entrepreneurship

```dataview
TABLE podcast, episode, rating, episode_date
FROM "podcasts"
WHERE contains(topics, "business") OR contains(topics, "entrepreneurship")
SORT episode_date DESC
```

## Science & Research

```dataview
TABLE podcast, episode, rating, episode_date
FROM "podcasts"
WHERE contains(topics, "science") OR contains(topics, "research")
SORT episode_date DESC
```
````

---

## Tips & Best Practices

### Folder Structure

Organize your notes for better queries:

```
podcasts/
├── lex-fridman-podcast/
│   ├── episode-001-summary.md
│   ├── episode-001-quotes.md
│   └── ...
├── huberman-lab/
│   └── ...
└── ...
```

### Status Workflow

Use status field to track processing:
1. **inbox**: Just downloaded, not reviewed yet
2. **reading**: Currently reviewing
3. **completed**: Finished reviewing
4. **archived**: Reference only, low priority

### Rating System

Consistent rating helps discovery:
- **5 stars**: Must-listen, share with others
- **4 stars**: Very good, highly relevant
- **3 stars**: Good, some useful insights
- **2 stars**: Okay, limited value
- **1 star**: Not relevant, skip

### Custom Fields

Add your own fields to frontmatter:

```yaml
custom:
  project: "AI Research"
  shared_with: ["Alice", "Bob"]
  action_items: 3
```

Query custom fields:

```dataview
TABLE podcast, episode, custom.project
FROM "podcasts"
WHERE custom.project = "AI Research"
```

---

## Troubleshooting

### Query Returns No Results

1. **Check folder path**: Ensure `"podcasts"` matches your folder name
2. **Verify field names**: Frontmatter fields are case-sensitive
3. **Check Dataview settings**: Enable JS queries if using `dataviewjs`

### Fields Not Showing

1. **Run Dataview index refresh**: Cmd/Ctrl + P → "Dataview: Reload JavaScript Engine"
2. **Check frontmatter syntax**: YAML must be valid
3. **Verify Inkwell generated metadata**: Check `.metadata.yaml` file

### Performance Issues

1. **Limit results**: Add `LIMIT 50` to large queries
2. **Use WHERE clauses**: Filter before TABLE/LIST
3. **Cache results**: Store complex calculations in note properties

---

## Resources

- [Dataview Documentation](https://blacksmithgu.github.io/obsidian-dataview/)
- [Dataview Query Language](https://blacksmithgu.github.io/obsidian-dataview/queries/structure/)
- [DataviewJS Examples](https://blacksmithgu.github.io/obsidian-dataview/api/intro/)
- [Inkwell Documentation](./USER_GUIDE.md)

---

**Need help?** Share your query questions in [Inkwell Discussions](https://github.com/chekos/inkwell-cli/discussions)
