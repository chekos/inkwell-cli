import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImportCommand } from "@/components/ImportCommand";

const { push } = vi.hoisted(() => ({
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

describe("ImportCommand", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("disables the form immediately and prevents duplicate import requests", async () => {
    let resolveFetch: (response: Response) => void = () => undefined;
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<ImportCommand />);

    fireEvent.change(screen.getByRole("textbox", { name: "Source URL" }), {
      target: { value: "https://example.com/episode.mp3" },
    });

    const input = screen.getByRole("textbox", { name: "Source URL" });
    const button = screen.getByRole("button", { name: "Start import" });
    const form = button.closest("form");
    expect(form).not.toBeNull();

    fireEvent.submit(form!);
    fireEvent.submit(form!);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(input).toBeDisabled();
    expect(screen.getByRole("button", { name: "Creating import..." })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Creating import job");
    expect(form).toHaveAttribute("aria-busy", "true");

    await act(async () => {
      resolveFetch(
        new Response(JSON.stringify({ statusUrl: "/app/jobs/job-1" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      );
    });

    await waitFor(() => {
      expect(push).toHaveBeenCalledWith("/app/jobs/job-1");
    });
  });

  it("re-enables the form when the import API fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: "Could not create the import job." }), {
        status: 500,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<ImportCommand />);

    fireEvent.change(screen.getByRole("textbox", { name: "Source URL" }), {
      target: { value: "https://example.com/episode.mp3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start import" }));

    expect(screen.getByRole("button", { name: "Creating import..." })).toBeDisabled();

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not create the import job.");
    expect(screen.getByRole("button", { name: "Start import" })).toBeEnabled();
    expect(screen.getByRole("textbox", { name: "Source URL" })).toBeEnabled();
  });
});
