# Plugin Security

Understanding the security implications of Inkwell's plugin system.

---

## Trust Model

Inkwell uses Python's entry point mechanism for plugin discovery. This means:

1. **Any installed package can register plugins** - When you install a Python package that declares Inkwell entry points, its plugins are automatically discovered and loaded.

2. **Plugins run with full privileges** - Plugin code executes with the same permissions as the Inkwell process itself. There is no sandboxing.

3. **Automatic loading** - Plugins are loaded when Inkwell starts, without explicit user confirmation.

---

## Security Implications

### What This Means for Users

- **Only install trusted packages** - Before installing a package that provides Inkwell plugins, verify its source and reputation.
- **Review what's installed** - Use `inkwell plugins list` to see all discovered plugins.
- **Disable untrusted plugins** - Use `inkwell plugins disable <name>` to prevent a plugin from loading.

### Attack Vectors to Be Aware Of

A malicious actor could create a PyPI package (e.g., `inkwell-awesome-transcriber`) that:

- Registers itself as an Inkwell plugin
- Executes arbitrary code when loaded
- Accesses files, network, or credentials with your user permissions

This is not unique to Inkwell - it's inherent to Python's packaging ecosystem. The same risks apply to any Python package you install.

### Current Mitigations

Inkwell provides several safeguards:

- **Type validation**: Plugins must be valid `InkwellPlugin` subclasses
- **API version compatibility**: Version checks prevent loading incompatible plugins
- **Graceful degradation**: Broken plugins are tracked and reported without crashing
- **Disable mechanism**: Users can disable plugins via `inkwell plugins disable <name>`

---

## Best Practices for Users

1. **Audit your plugins** - Regularly run `inkwell plugins list` to review installed plugins
2. **Install from trusted sources** - Prefer plugins from known authors or organizations
3. **Check package metadata** - Review PyPI pages for project links, maintainer info, and download stats
4. **Use virtual environments** - Isolate Inkwell installations to limit exposure
5. **Keep plugins updated** - Security fixes are distributed through package updates

---

## Best Practices for Plugin Authors

When developing plugins, follow these security principles:

1. **Principle of least privilege** - Only request the permissions your plugin actually needs
2. **Minimize dependencies** - Each dependency is a potential attack surface
3. **Audit dependencies** - Use tools like `pip-audit` to check for known vulnerabilities
4. **Document behavior** - Clearly explain what your plugin does, especially network access or file operations
5. **Handle secrets carefully** - Never log API keys or sensitive configuration values
6. **Validate inputs** - Don't trust data from external sources without validation

---

## Future Improvements

The following security enhancements are being considered for future releases:

- Plugin signature verification
- Explicit opt-in for third-party plugins
- Capability-based permission system
- Plugin sandboxing for untrusted code

---

## Reporting Security Issues

If you discover a security vulnerability in Inkwell or a plugin:

1. **Do not** open a public GitHub issue
2. Contact the maintainers directly
3. Provide details about the vulnerability and steps to reproduce

For third-party plugins, contact the plugin author directly.
