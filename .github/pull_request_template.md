## Description

<!--
Provide a clear and concise description of what this PR does.
Include the motivation and context for the changes.
-->

## Type of Change

<!-- Check the relevant boxes with [x] -->

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring/code quality improvement
- [ ] Performance improvement
- [ ] Test additions/improvements
- [ ] Build/CI/tooling changes

## Related Issues

<!-- Link to related issues using "Closes #123" or "Fixes #456" to auto-close them when merged -->

Closes #

## Changes Made

<!--
Provide a bullet-point list of changes made in this PR.
Be specific about what was added, modified, or removed.
-->

-
-
-

## Testing

<!--
Describe the testing you've performed to verify your changes.
Include test commands and results.
-->

**Test commands run:**
```bash
# List commands you ran to test
uv run pytest
uv run ruff check .
```

**Test results:**
- [ ] All tests pass
- [ ] New tests added (if applicable)
- [ ] Manual testing performed

**Manual testing steps:**
<!-- If applicable, describe manual testing performed -->
1.
2.
3.

## Documentation

<!-- Check all that apply -->

- [ ] User guide updated (`docs/user-guide.md`)
- [ ] Tutorial updated (`docs/tutorial.md`)
- [ ] Examples added (`docs/examples.md`)
- [ ] API documentation updated
- [ ] CHANGELOG.md updated under "Unreleased" section
- [ ] ADR created (if architectural decision made)
- [ ] Devlog created (if feature implementation)
- [ ] README.md updated (if major feature)
- [ ] No documentation needed for this change

## Pre-submission Checklist

<!--
Review and check all items before submitting.
All items must be checked for the PR to be considered complete.
-->

### Code Quality

- [ ] Pre-commit hooks pass locally
- [ ] All tests pass locally (`uv run pytest`)
- [ ] Type checking passes (`uv run mypy src/`)
- [ ] Linting passes (`uv run ruff check .`)
- [ ] Code formatted (`uv run ruff format .`)
- [ ] No debug print statements or commented code
- [ ] Type hints added for new functions/methods

### Testing

- [ ] New tests added for new functionality
- [ ] Existing tests updated if behavior changed
- [ ] Test coverage maintained or improved (95%+ target)
- [ ] Edge cases tested
- [ ] Error cases tested

### Documentation

- [ ] User-facing documentation updated
- [ ] Code comments added for complex logic
- [ ] Docstrings added/updated (Google style)
- [ ] CHANGELOG.md updated
- [ ] Examples added if new feature

### DKS (Developer Knowledge System)

- [ ] ADR created for architectural decisions (use `docs/adr/NNN-title.md`)
- [ ] Devlog entry created for feature work (use `docs/devlog/YYYY-MM-DD-title.md`)
- [ ] Research documented if technology evaluation performed
- [ ] Lessons learned documented after completion (if applicable)
- [ ] No DKS documentation needed for this change

### Security

- [ ] No API keys or secrets committed
- [ ] No sensitive information in code or tests
- [ ] Dependencies reviewed for vulnerabilities
- [ ] Input validation added for user inputs
- [ ] No new security vulnerabilities introduced

### Performance

- [ ] No performance regressions introduced
- [ ] Expensive operations optimized or cached
- [ ] Database queries optimized (if applicable)
- [ ] API calls minimized and cached (if applicable)

## Screenshots/Terminal Output

<!--
If your changes include UI/CLI output changes, include screenshots or terminal output.
Use tools like asciinema for terminal recordings if helpful.
-->

<!-- Paste screenshots or terminal output here -->

## Breaking Changes

<!--
If this PR includes breaking changes, describe:
1. What breaks
2. Why the breaking change is necessary
3. Migration path for users
-->

<!-- Delete this section if no breaking changes -->

## Additional Notes

<!--
Add any additional context, considerations, or notes for reviewers.
Examples:
- Trade-offs made and why
- Alternative approaches considered
- Future work planned
- Known limitations
-->

## Reviewer Notes

<!--
Optional: Add notes for reviewers about what to focus on during review.
Example: "Please pay special attention to the error handling in function X"
-->

---

**By submitting this PR, I confirm that:**
- [ ] My code follows the project's coding standards and style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code where necessary, particularly in hard-to-understand areas
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published
