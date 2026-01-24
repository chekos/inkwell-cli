"""MkDocs hook to fix mermaid graphs from mkdocs-material-adr plugin.

Fixes issues:
1. Removes duplicate `classDef mermaid-common` lines (plugin bug)
2. Removes <code> wrapper - Material expects content directly in <pre class="mermaid">
3. Fixes nested brackets in node labels (mermaid syntax error)
4. Decodes HTML entities
"""

import html
import re


def on_post_page(output: str, page, config) -> str:
    """Fix mermaid graphs for proper rendering.

    Uses on_post_page to run AFTER all plugins (including mkdocs-material-adr)
    have finished modifying the page content.
    """

    def fix_node_label(match):
        """Fix node labels by quoting them to avoid mermaid syntax errors."""
        node_id = match.group(1)
        label = match.group(2)
        # Wrap label in quotes to prevent mermaid from parsing special chars
        # Also escape any existing quotes in the label
        escaped_label = label.replace('"', "'")
        return f'{node_id}["{escaped_label}"]'

    def fix_mermaid(match):
        content = match.group(1)

        # Decode HTML entities (e.g., &amp; -> &)
        content = html.unescape(content)

        # Fix nested brackets in node definitions: id[label with [nested] brackets]
        # Pattern: node-id[...text...[nested]...text...]
        content = re.sub(r"^(\S+)\[(.+)\]$", fix_node_label, content, flags=re.MULTILINE)

        # Split into lines, deduplicate while preserving order
        lines = content.split("\n")
        seen = set()
        unique_lines = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)

        # content directly inside <pre class="mermaid">
        return f'<pre class="mermaid">\n{chr(10).join(unique_lines)}\n</pre>'

    # Fix mermaid blocks - remove <code> wrapper and deduplicate
    output = re.sub(
        r'<pre class="mermaid"><code>(.*?)</code></pre>', fix_mermaid, output, flags=re.DOTALL
    )

    return output
