export type SourceKind = "youtube" | "rss" | "podcast" | "web" | "media" | "unknown";

const YOUTUBE_HOSTS = new Set(["youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"]);

export function detectSourceKind(value?: string | null): SourceKind {
  if (!value) {
    return "unknown";
  }

  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    const pathname = url.pathname.toLowerCase();

    if (YOUTUBE_HOSTS.has(host)) {
      return "youtube";
    }

    if (pathname.endsWith(".rss") || pathname.endsWith(".xml") || pathname.includes("/feed")) {
      return "rss";
    }

    if (/\.(mp3|m4a|wav|mp4|webm|aac)$/i.test(pathname)) {
      return "media";
    }

    if (host.includes("podcasts.") || host.includes("podcast")) {
      return "podcast";
    }

    return "web";
  } catch {
    return "unknown";
  }
}

export function sourceKindLabel(kind?: string | null) {
  switch (kind) {
    case "youtube":
      return "YouTube";
    case "rss":
      return "RSS feed";
    case "podcast":
      return "Podcast";
    case "media":
      return "Media file";
    case "web":
      return "Web source";
    default:
      return "Source";
  }
}

export function sourceHost(value?: string | null) {
  if (!value) {
    return "Unknown source";
  }

  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return value;
  }
}
