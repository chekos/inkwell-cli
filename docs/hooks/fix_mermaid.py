"""MkDocs hook to fix mermaid graphs from mkdocs-material-adr plugin.

Fixes two issues:
1. Removes duplicate `classDef mermaid-common` lines (plugin bug)
2. Removes <code> wrapper - Material expects content directly in <pre class="mermaid">
"""

import re


def on_page_content(html: str, page, config, files) -> str:
    """Fix mermaid graphs for proper rendering."""

    def fix_mermaid(match):
        content = match.group(1)

        # Split into lines, deduplicate while preserving order
        lines = content.split('\n')
        seen = set()
        unique_lines = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)

        # Return WITHOUT <code> wrapper - Material for MkDocs expects
        # content directly inside <pre class="mermaid">
        return f'<pre class="mermaid">\n{chr(10).join(unique_lines)}\n</pre>'

    # Fix mermaid blocks - remove <code> wrapper and deduplicate
    html = re.sub(
        r'<pre class="mermaid"><code>(.*?)</code></pre>',
        fix_mermaid,
        html,
        flags=re.DOTALL
    )

    return html
