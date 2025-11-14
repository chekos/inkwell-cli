---
status: pending
priority: p1
issue_id: "021"
tags: [code-review, security, credentials, critical, immediate-action]
dependencies: []
---

# URGENT: Revoke Committed API Keys in Git History

## Problem Statement

**CRITICAL SECURITY ISSUE**: API keys for Anthropic, Google AI, and OpenAI were committed to the repository in the `.env` file and are visible in git history. These keys are now publicly exposed and must be revoked immediately.

**Severity**: CRITICAL (CWE-798: Use of Hard-coded Credentials)

## Findings

- Discovered during comprehensive security audit by security-sentinel agent
- Location: `.env` file (committed to git)
- Exposed keys:
  - `ANTHROPIC_API_KEY=sk-ant-api03-[REDACTED]`
  - `GOOGLE_GENERATIVE_AI_API_KEY=AIzaSyC[REDACTED]`
  - `OPENAI_API_KEY=sk-proj-[REDACTED]`

**Impact:**
- Unauthorized API usage at your expense
- Potential data exfiltration through API access
- Financial liability from fraudulent API calls
- Compromised AI model interactions

**Attack Scenarios:**
- Attacker uses exposed keys to make expensive API calls
- Keys used to access/extract data from your AI interactions
- Keys sold on dark web marketplaces
- Rate limits exhausted, preventing legitimate usage

## Proposed Solutions

### Option 1: Immediate Revocation + History Cleanup (REQUIRED)

**Steps (URGENT - Do within 1 hour):**

1. **Revoke all exposed API keys immediately:**
   ```bash
   # Anthropic
   open https://console.anthropic.com/settings/keys
   # Click "Revoke" on exposed key

   # Google AI
   open https://makersuite.google.com/app/apikey
   # Delete exposed key

   # OpenAI
   open https://platform.openai.com/api-keys
   # Revoke exposed key
   ```

2. **Generate new API keys:**
   - Create new keys in each console
   - Store in password manager (1Password, LastPass, etc.)
   - Set as environment variables only (never commit)

3. **Remove .env from git history:**
   ```bash
   # Using git-filter-repo (recommended)
   pip install git-filter-repo
   git filter-repo --invert-paths --path .env

   # OR using BFG Repo-Cleaner
   brew install bfg
   bfg --delete-files .env
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   ```

4. **Force push to remote (if applicable):**
   ```bash
   git push origin --force --all
   git push origin --force --tags
   ```

5. **Add pre-commit hook to prevent future commits:**
   ```bash
   # Add to .pre-commit-config.yaml
   - repo: https://github.com/Yelp/detect-secrets
     rev: v1.4.0
     hooks:
       - id: detect-secrets
         args: ['--baseline', '.secrets.baseline']
   ```

6. **Verify .env is in .gitignore:**
   ```bash
   grep -q "^\.env$" .gitignore || echo ".env" >> .gitignore
   git add .gitignore
   git commit -m "chore: Ensure .env is gitignored"
   ```

**Pros**:
- Prevents unauthorized access
- Removes keys from git history
- Prevents future accidental commits

**Cons**:
- Requires force push (breaks others' clones if public repo)
- History rewrite is irreversible

**Effort**: Small (1 hour)
**Risk**: High if not done, Low if completed properly

## Recommended Action

**IMMEDIATE ACTION REQUIRED (WITHIN 1 HOUR):**

1. Stop all work and revoke keys first
2. Generate new keys and set as environment variables
3. Clean git history
4. Add secret detection to pre-commit hooks

**Priority**: P1 CRITICAL - This is a security emergency

## Technical Details

**Affected Files:**
- `.env` (entire file should never be committed)
- Any git commits containing `.env`

**Related Components:**
- `src/inkwell/utils/api_keys.py` - API key validation
- `src/inkwell/config/manager.py` - Configuration loading
- All LLM integrations (extraction, interview, transcription)

**Database Changes**: No

## Resources

- Security audit report: See security-sentinel agent findings
- CWE-798: https://cwe.mitre.org/data/definitions/798.html
- git-filter-repo: https://github.com/newren/git-filter-repo
- detect-secrets: https://github.com/Yelp/detect-secrets

## Acceptance Criteria

- [ ] All exposed API keys revoked in provider consoles
- [ ] New API keys generated and stored securely
- [ ] New keys set as environment variables (verified with `echo $ANTHROPIC_API_KEY`)
- [ ] `.env` file removed from git history (verify with `git log --all --full-history -- .env`)
- [ ] `.env` confirmed in `.gitignore`
- [ ] Pre-commit secret detection hook installed and tested
- [ ] All LLM features tested with new keys
- [ ] Documentation updated with environment variable setup instructions

## Work Log

### 2025-11-14 - Security Audit Discovery
**By:** Claude Code Review System (security-sentinel agent)
**Actions:**
- Discovered hardcoded API keys in `.env` file
- Identified exposure in git history
- Classified as CRITICAL security issue
- Flagged for immediate remediation

**Learnings:**
- `.env` files should NEVER be committed
- Secret scanning should be part of CI/CD pipeline
- API keys should only exist as environment variables
- Pre-commit hooks are essential for security

## Notes

**URGENCY**: This is the highest priority issue in the codebase. All other work should stop until this is resolved.

**If repository is public on GitHub**: The keys are already compromised and likely scraped by bots. Revocation is mandatory, not optional.

**If repository is private**: Keys are still at risk if repository is ever made public or if collaborators' machines are compromised.

**Cost Impact**: Check API provider usage dashboards immediately for unexpected activity:
- Anthropic: https://console.anthropic.com/settings/usage
- Google AI: https://console.cloud.google.com/billing
- OpenAI: https://platform.openai.com/usage

**Timeline**: From discovery to resolution should be < 2 hours maximum.
