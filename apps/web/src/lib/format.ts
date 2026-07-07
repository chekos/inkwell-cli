export function formatDate(value?: string | null) {
  if (!value) {
    return "Not yet";
  }

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

export function stageLabel(stage?: string | null) {
  switch (stage) {
    case "fetching_source":
      return "Fetching source";
    case "extracting_transcript":
      return "Extracting transcript";
    case "generating_notes":
      return "Generating notes";
    case "saving_result":
      return "Saving result";
    case "done":
      return "Done";
    case "queued":
    default:
      return "Queued";
  }
}
