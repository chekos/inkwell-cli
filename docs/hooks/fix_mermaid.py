"""MkDocs hook to fix duplicate classDef lines in mermaid graphs.

The mkdocs-material-adr plugin has a bug where it generates duplicate
`classDef mermaid-common` lines inside a loop. This hook removes duplicates.
"""

import re


def on_page_content(html: str, page, config, files) -> str:
    """Remove duplicate classDef lines from mermaid graphs."""

    # Find mermaid code blocks
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

        return f'<pre class="mermaid"><code>{chr(10).join(unique_lines)}</code></pre>'

    # Fix mermaid blocks
    html = re.sub(
        r'<pre class="mermaid"><code>(.*?)</code></pre>',
        fix_mermaid,
        html,
        flags=re.DOTALL
    )

    return html
