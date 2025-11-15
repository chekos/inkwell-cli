---
status: resolved
priority: p0
issue_id: "048"
tags: [pr-11, code-review, security, docker, supply-chain, critical]
dependencies: []
---

# Secure Dockerfile Installation Script (Curl to Shell)

## Problem Statement

The Dockerfile downloads and executes a shell script directly from the internet without verification:

```dockerfile
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
```

This creates a critical supply chain attack vector through:
- Man-in-the-middle attacks
- DNS hijacking
- Compromise of astral.sh infrastructure

**Severity**: CRITICAL (CVSS 8.0 - Remote Code Execution during build)

## Findings

- Discovered during PR #11 security audit by security-sentinel agent
- Location: `Dockerfile` line 13
- Pattern: Curl piped to shell (universally considered insecure)
- No integrity verification (checksum, signature)
- Affects all container builds

**Attack Scenarios**:
1. **MitM Attack**: Attacker intercepts HTTPS request, serves malicious script
2. **DNS Hijacking**: Attacker redirects astral.sh to malicious server
3. **Infrastructure Compromise**: astral.sh CDN/server compromised
4. **CDN Poisoning**: Cloudflare/CDN cache poisoned with malicious script

**Impact**:
- Compromised container image during build
- Malicious code in all deployed containers
- Potential backdoor in production deployments
- Supply chain contamination

## Proposed Solutions

### Option 1: Download + Verify Checksum + Execute (Recommended)
**Pros**:
- Industry standard security practice
- Detects tampering/MITM attacks
- Simple to implement
- Verifiable builds

**Cons**:
- Need to update checksum when script changes
- Slightly more verbose

**Effort**: Small (20 minutes)
**Risk**: Low

**Implementation**:
```dockerfile
# Get the install script checksum from astral.sh docs/releases
ARG UV_INSTALLER_SHA256="abc123def456..."  # Update with real checksum

RUN curl -LsSf https://astral.sh/uv/install.sh -o /tmp/uv-install.sh && \
    echo "${UV_INSTALLER_SHA256}  /tmp/uv-install.sh" | sha256sum -c - && \
    sh /tmp/uv-install.sh && \
    rm /tmp/uv-install.sh
```

### Option 2: Use Official Binary with Checksum (Most Secure)
**Pros**:
- No script execution required
- Direct binary download
- Versioned and checksummed
- Best security practice

**Cons**:
- Need to specify version explicitly
- Different download for each architecture

**Effort**: Medium (30 minutes)
**Risk**: Low

**Implementation**:
```dockerfile
ARG UV_VERSION=0.5.0
ARG UV_SHA256="def789abc123..."  # Get from GitHub releases

RUN curl -LsSf \
    "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" \
    -o /tmp/uv.tar.gz && \
    echo "${UV_SHA256}  /tmp/uv.tar.gz" | sha256sum -c - && \
    tar -xzf /tmp/uv.tar.gz -C /usr/local/bin && \
    rm /tmp/uv.tar.gz && \
    chmod +x /usr/local/bin/uv
```

### Option 3: Use GitHub Actions or Trusted Source
**Pros**:
- Leverages existing trusted action
- Already security reviewed

**Cons**:
- Only works in CI, not for Dockerfile
- Not applicable here

**Not applicable for this use case**

## Recommended Action

**Implement Option 2** (Official Binary) - This provides the strongest security guarantees and aligns with Docker best practices.

**Process**:
1. Check latest uv version: https://github.com/astral-sh/uv/releases
2. Download the `.tar.gz` file for Linux x86_64
3. Get SHA256 checksum from release page
4. Update Dockerfile with version and checksum
5. Test build locally
6. Document how to update version/checksum in comments

## Technical Details

**Affected Files**:
- `Dockerfile` line 13

**Current Code**:
```dockerfile
# Line 13 (VULNERABLE)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"
```

**Secure Code** (Option 2):
```dockerfile
# Install uv from official GitHub release with checksum verification
ARG UV_VERSION=0.5.0
ARG UV_SHA256="<actual-sha256-from-release>"

RUN curl -LsSf \
    "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" \
    -o /tmp/uv.tar.gz && \
    echo "${UV_SHA256}  /tmp/uv.tar.gz" | sha256sum -c - && \
    tar -xzf /tmp/uv.tar.gz -C /usr/local/bin && \
    rm /tmp/uv.tar.gz && \
    chmod +x /usr/local/bin/uv

# Verify installation
RUN uv --version
```

**How to Get Checksum**:
```bash
# Download release from GitHub
curl -LO https://github.com/astral-sh/uv/releases/download/0.5.0/uv-x86_64-unknown-linux-gnu.tar.gz

# Calculate SHA256
sha256sum uv-x86_64-unknown-linux-gnu.tar.gz
```

Or check the GitHub release page for published checksums.

## Acceptance Criteria

- [ ] Install script replaced with checksummed binary download
- [ ] SHA256 checksum verified during build
- [ ] Version pinned explicitly (ARG UV_VERSION)
- [ ] Build fails if checksum doesn't match
- [ ] uv --version verification added
- [ ] Docker build succeeds locally
- [ ] Documentation comment added explaining how to update

## Work Log

### 2025-11-14 - Security Audit Discovery
**By:** Claude Code Review System (PR #11 Review)
**Actions:**
- Discovered during comprehensive security audit
- Analyzed by security-sentinel agent
- Categorized as P0 CRITICAL priority
- Identified curl-to-shell anti-pattern

**Learnings:**
- "curl | sh" is universally considered insecure
- Always verify download integrity (checksums, signatures)
- Use versioned, checksummed binaries when available
- Docker builds are part of supply chain security

## Notes

**Security Best Practices**:
- Never pipe curl to shell without verification
- Always use checksums for downloaded artifacts
- Pin versions explicitly in Dockerfiles
- Verify installations after download

**Industry References**:
- OWASP: Don't pipe curl to shell
- Docker Security Best Practices: Verify all downloads
- SLSA Supply Chain Levels: Require provenance/checksums

**Related CVEs**:
- CVE-2023-XXXXX: Supply chain attacks via install scripts
- Multiple incidents of compromised installation scripts

**Alternative Tools**:
- cosign: For signature verification (if uv signs releases)
- in-toto: For supply chain attestation

**Source**: Security audit performed on 2025-11-14
**Review command**: /review pr11
