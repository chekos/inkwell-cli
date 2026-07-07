export type MarkdownHeading = {
  id: string;
  text: string;
  level: 1 | 2 | 3;
};

export function slugifyHeading(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[`*_~[\]()]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function extractMarkdownHeadings(markdown: string): MarkdownHeading[] {
  return markdown
    .split("\n")
    .map((line) => {
      const match = /^(#{1,3})\s+(.+)$/.exec(line.trim());
      if (!match) {
        return null;
      }

      const level = match[1].length as 1 | 2 | 3;
      const text = match[2].replace(/\s+#+$/, "").trim();
      const id = slugifyHeading(text);

      return id ? { id, text, level } : null;
    })
    .filter((heading): heading is MarkdownHeading => Boolean(heading));
}

export function filenameFromTitle(title: string) {
  const slug = slugifyHeading(title);
  return `${slug || "inkwell-note"}.md`;
}
