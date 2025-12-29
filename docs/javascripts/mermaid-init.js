// Initialize mermaid for dynamically generated content (from mkdocs-material-adr plugin)
document.addEventListener('DOMContentLoaded', async () => {
  const mermaidBlocks = document.querySelectorAll('pre.mermaid');
  if (mermaidBlocks.length > 0) {
    const mermaid = await import('https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs');
    mermaid.default.initialize({
      startOnLoad: false,
      theme: 'default',
      securityLevel: 'loose'
    });
    mermaid.default.run({ nodes: mermaidBlocks });
  }
});
