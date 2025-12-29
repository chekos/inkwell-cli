# Template Marketplace

**Category:** New Feature | Integration
**Quarter:** Q4
**T-shirt Size:** M

## Why This Matters

Inkwell's template system is powerful but underutilized. Creating effective extraction templates requires understanding LLM prompting, experimenting with output formats, and testing across different content types. Most users won't invest this effort—they'll use the defaults and miss the full potential.

A template marketplace transforms templates from an advanced feature into a community-driven ecosystem. Subject matter experts create templates for their domains: "Tech Tool Tracker" for developer podcasts, "Book Club Extractor" for literary discussions, "Startup Insights" for business content. Users browse, install, and rate templates without writing prompts themselves.

This creates a flywheel: better templates attract more users; more users create more templates. It's how Inkwell becomes the definitive podcast processing platform rather than just a tool.

## Current State

**Template system capabilities:**
- YAML-based template configuration
- Template variables with Jinja2 rendering
- Category-specific templates (`tech/`, `interview/`)
- Template versioning for incremental regeneration
- Priority-based template ordering

**Current templates (5 defaults):**
- `summary.yaml` - Episode summary
- `quotes.yaml` - Memorable quotes
- `key-concepts.yaml` - Main ideas
- `tools-mentioned.yaml` (tech category)
- `books-mentioned.yaml` (interview category)

**What's missing:**
- No template discovery mechanism
- No template sharing infrastructure
- No quality ratings or reviews
- No version management for shared templates
- No template testing/preview
- No category/tag filtering

**Related files:**
- `src/inkwell/templates/` - Built-in templates
- `src/inkwell/extraction/templates.py` - Template loading
- `src/inkwell/extraction/template_selector.py` - Category selection

## Proposed Future State

A thriving template ecosystem with:

1. **Template discovery:**
   - Browse by category, popularity, rating
   - Search by keyword, podcast type, content focus
   - Curated "Staff Picks" and "Rising" collections
   - Preview template output examples

2. **Easy installation:**
   - `inkwell templates install startup-insights`
   - One-click install from web dashboard
   - Automatic updates with version pinning
   - Dependency management between templates

3. **Quality assurance:**
   - User ratings and reviews
   - Usage statistics
   - Output quality scoring
   - Verified creator badges

4. **Creator tools:**
   - `inkwell templates create` scaffolding
   - Local testing and preview
   - Publishing workflow
   - Analytics for template creators

5. **Hosting infrastructure:**
   - GitHub-based template registry
   - CDN for template distribution
   - API for search and metadata

## Key Deliverables

- [ ] Design template package specification (metadata, versioning, dependencies)
- [ ] Create `inkwell templates` command group (search, install, update, list, create, publish)
- [ ] Build GitHub-based template registry (inkwell-templates org)
- [ ] Implement template discovery API
- [ ] Create web interface for browsing templates (#06 integration)
- [ ] Add rating and review system
- [ ] Build template preview functionality
- [ ] Implement dependency resolution between templates
- [ ] Create template creator documentation and tutorials
- [ ] Build template testing framework
- [ ] Add template update notifications
- [ ] Create featured/curated collections

## Prerequisites

- **Initiative #02 (Plugin Architecture):** Templates as a plugin type
- **Initiative #06 (Web Dashboard):** Visual browsing interface

## Risks & Open Questions

- **Risk:** Low quality templates could degrade user experience. Mitigation: Rating system, moderation, verified creators.
- **Risk:** Template maintenance burden on creators. Mitigation: Clear ownership, fork/adoption model.
- **Risk:** Security concerns with executing community templates. Mitigation: Templates are prompts, not code—sandboxed by design.
- **Question:** Should the registry be centralized (inkwell.dev) or decentralized (GitHub)?
- **Question:** How to handle template monetization if creators want to charge?
- **Question:** Should there be a verification/review process for published templates?

## Notes

**Template package specification:**
```yaml
# template.yaml
name: startup-insights
version: "1.0.0"
description: "Extract startup lessons, funding mentions, and founder advice"
author: "@chekos"
license: MIT
categories: [business, startup, entrepreneurship]
tags: [funding, founder, vc, lessons]
dependencies: []

templates:
  - startup-lessons.yaml
  - funding-mentioned.yaml
  - founder-quotes.yaml

examples:
  - input: "How I Built This episode about Canva"
    output: "startup-lessons-example.md"
```

**CLI interface:**
```bash
# Browse templates
inkwell templates search "startup"
inkwell templates browse --category business

# Install and manage
inkwell templates install startup-insights
inkwell templates update startup-insights
inkwell templates list --installed

# Create and publish
inkwell templates create my-template
inkwell templates test my-template --episode podcast/ep-1
inkwell templates publish my-template
```

**Registry structure (GitHub-based):**
```
inkwell-templates/
├── registry.json              # Master index
├── categories/
│   ├── tech.json
│   ├── business.json
│   └── education.json
└── templates/
    ├── startup-insights/
    │   ├── template.yaml
    │   ├── templates/
    │   └── examples/
    └── tech-stack-analyzer/
```

**Files to create:**
- `src/inkwell/marketplace/` - Marketplace module
- `src/inkwell/marketplace/registry.py` - Registry client
- `src/inkwell/marketplace/package.py` - Package management
- `src/inkwell/marketplace/publisher.py` - Publishing workflow
