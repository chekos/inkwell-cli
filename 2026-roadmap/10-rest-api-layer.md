# REST API Layer

**Category:** Architecture | Integration
**Quarter:** Q4
**T-shirt Size:** L

## Why This Matters

Inkwell's value is locked inside a CLI tool. You can't build a mobile app that processes podcasts on-the-go, integrate with Zapier for automated workflows, or create a Slack bot that summarizes episodes on demand. Every new interface (web dashboard, mobile app, browser extension) would need to reimplement core logic.

A REST API layer unlocks programmatic access to Inkwell's capabilities. It enables the web dashboard (#06) to share logic with the CLI, powers third-party integrations, and creates opportunities for a hosted service. It's the foundation for Inkwell becoming a platform rather than just a tool.

This is how Inkwell scales beyond individual users to team deployments, enterprise integrations, and a developer ecosystem building on top of your work.

## Current State

**Current architecture:**
- CLI is the only interface
- Core logic coupled to CLI command handlers
- No HTTP server infrastructure
- No authentication/authorization layer
- No rate limiting for programmatic access

**What exists:**
- Well-structured internal modules that could be exposed
- Configuration management
- Cost tracking
- Processing pipeline

**What's missing:**
- No REST API endpoints
- No HTTP server
- No API authentication
- No webhook support
- No async job queue
- No API documentation

## Proposed Future State

A comprehensive REST API that:

1. **Exposes all CLI functionality:**
   - Feeds: CRUD operations
   - Episodes: list, process, get details
   - Templates: list, get, apply
   - Search: semantic and keyword
   - Graph: query entities and relationships
   - Costs: retrieve spending data

2. **Supports async operations:**
   - Long-running jobs (transcription, extraction)
   - Job status polling
   - Webhook callbacks on completion
   - Batch processing endpoints

3. **Provides developer experience:**
   - OpenAPI 3.0 specification
   - Interactive documentation (Swagger UI)
   - Client libraries (Python, TypeScript)
   - Rate limiting and quotas

4. **Enables integrations:**
   - Webhook notifications
   - Zapier/Make/n8n compatibility
   - Slack/Discord bot integration
   - Mobile app backend

## Key Deliverables

- [ ] Design REST API specification (OpenAPI 3.0)
- [ ] Implement FastAPI application with core endpoints
- [ ] Create feed management endpoints (GET/POST/PUT/DELETE /feeds)
- [ ] Create episode endpoints (GET /episodes, POST /episodes/process)
- [ ] Create search endpoint (POST /search)
- [ ] Create graph query endpoints (GET /graph/entities, /graph/connections)
- [ ] Implement async job queue for long-running operations
- [ ] Add job status and webhook callback endpoints
- [ ] Implement API key authentication
- [ ] Add rate limiting and usage tracking
- [ ] Generate OpenAPI documentation
- [ ] Create Python client library
- [ ] Create TypeScript client library
- [ ] Add `inkwell serve --api` command
- [ ] Document API usage and integration patterns

## Prerequisites

- **Initiative #01 (CI/CD Pipeline Excellence):** API testing infrastructure
- **Initiative #04 (Knowledge Graph Engine):** Graph query endpoints
- **Initiative #05 (Semantic Search):** Search endpoints
- **Initiative #06 (Web Dashboard):** Primary API consumer

## Risks & Open Questions

- **Risk:** API versioning complexity. Mitigation: URL versioning (/v1/), deprecation policy.
- **Risk:** Security vulnerabilities in exposed API. Mitigation: Auth, rate limiting, input validation, security audit.
- **Risk:** Performance under concurrent load. Mitigation: Async architecture, job queue, caching.
- **Question:** Should the API be local-only or support remote access?
- **Question:** How to handle API keys vs OAuth for different use cases?
- **Question:** Should there be a hosted/cloud version of the API?

## Notes

**API design principles:**
- RESTful with standard HTTP methods
- JSON request/response bodies
- Consistent error format
- Pagination for list endpoints
- Filtering and sorting support

**Endpoint structure:**
```
# Feeds
GET    /v1/feeds              # List feeds
POST   /v1/feeds              # Add feed
GET    /v1/feeds/{id}         # Get feed details
PUT    /v1/feeds/{id}         # Update feed
DELETE /v1/feeds/{id}         # Remove feed

# Episodes
GET    /v1/feeds/{id}/episodes    # List episodes
POST   /v1/episodes/process       # Start processing
GET    /v1/jobs/{id}              # Get job status
GET    /v1/episodes/{id}          # Get processed episode

# Search
POST   /v1/search                 # Semantic search
GET    /v1/search/suggest         # Autocomplete

# Graph
GET    /v1/graph/entities         # List entities
GET    /v1/graph/entities/{id}    # Entity details
GET    /v1/graph/connections      # Entity connections

# Costs
GET    /v1/costs                  # Cost summary
GET    /v1/costs/history          # Cost history

# Templates
GET    /v1/templates              # List templates
GET    /v1/templates/{id}         # Template details
```

**Authentication:**
```bash
# API key in header
curl -H "Authorization: Bearer ink_xxx" https://localhost:8080/v1/feeds

# Or in query param (for webhooks)
curl "https://localhost:8080/v1/feeds?api_key=ink_xxx"
```

**Async job pattern:**
```json
// POST /v1/episodes/process
{
  "feed_id": "podcast-123",
  "episode": "latest",
  "templates": ["summary", "quotes"],
  "webhook_url": "https://my-app.com/webhook"
}

// Response
{
  "job_id": "job_abc123",
  "status": "pending",
  "status_url": "/v1/jobs/job_abc123"
}
```

**Files to create:**
- `src/inkwell/api/` - API module
- `src/inkwell/api/app.py` - FastAPI application
- `src/inkwell/api/routers/` - Endpoint routers
- `src/inkwell/api/auth.py` - Authentication
- `src/inkwell/api/jobs.py` - Job queue management
- `src/inkwell/api/schemas.py` - Request/response schemas
- `clients/python/` - Python client library
- `clients/typescript/` - TypeScript client library
