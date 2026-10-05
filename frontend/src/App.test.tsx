import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("renders app name", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ json: () => Promise.resolve({ status: "ok" }) }),
    );
    render(<App />);
    expect(screen.getByRole("heading", { name: "Email Assistant Chat" })).toBeInTheDocument();
    expect(await screen.findByText("API: ok")).toBeInTheDocument();
  });

  it("shows unreachable when health fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    render(<App />);
    expect(await screen.findByText("API: unreachable")).toBeInTheDocument();
  });
});
