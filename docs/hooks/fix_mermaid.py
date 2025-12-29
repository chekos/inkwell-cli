"""MkDocs hook to fix mermaid graphs from mkdocs-material-adr plugin.

Fixes issues:
1. Removes duplicate `classDef mermaid-common` lines (plugin bug)
2. Removes <code> wrapper - Material expects content directly in <pre class="mermaid">
3. Fixes nested brackets in node labels (mermaid syntax error)
4. Decodes HTML entities
"""

import html
import re


def on_page_content(page_html: str, page, config, files) -> str:
    """Fix mermaid graphs for proper rendering."""

    def fix_node_label(match):
        """Fix node labels with nested brackets."""
        node_id = match.group(1)
        label = match.group(2)
        # Replace inner brackets with parentheses to avoid mermaid syntax errors
        fixed_label = label.replace('[', '(').replace(']', ')')
        return f'{node_id}[{fixed_label}]'

    def fix_mermaid(match):
        content = match.group(1)

        # Decode HTML entities (e.g., &amp; -> &)
        content = html.unescape(content)

        # Fix nested brackets in node definitions: id[label with [nested] brackets]
        # Pattern: node-id[...text...[nested]...text...]
        content = re.sub(
            r'^(\S+)\[(.+)\]$',
            fix_node_label,
            content,
            flags=re.MULTILINE
        )

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
    page_html = re.sub(
        r'<pre class="mermaid"><code>(.*?)</code></pre>',
        fix_mermaid,
        page_html,
        flags=re.DOTALL
    )

    return page_html
