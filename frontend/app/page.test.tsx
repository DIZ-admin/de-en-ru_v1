import React, { act } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, beforeEach, afterEach } from "vitest";
import Home from "./page";

const mockGetAuthToken = vi.fn();
const mockTranslateStream = vi.fn();

vi.mock("@/lib/api", () => ({
  getAuthToken: (...args: unknown[]) => mockGetAuthToken(...args),
  translateTextStream: (...args: unknown[]) => mockTranslateStream(...args),
}));

async function* mockGenerator(chunks: string[]) {
  for (const chunk of chunks) {
    yield chunk;
  }
}

describe("Home page", () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockGetAuthToken.mockReset();
    mockTranslateStream.mockReset();
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it("shows validation error when text is empty", async () => {
    mockGetAuthToken.mockResolvedValue("token-abc");

    render(<Home />);
    await act(async () => {
      await userEvent.click(
        screen.getByRole("button", { name: /get auth token/i }),
      );
    });
    expect(await screen.findByText(/authenticated/i)).toBeInTheDocument();

    const translateButton = screen.getByRole("button", { name: /translate/i });
    await act(async () => {
      await userEvent.click(translateButton);
    });
    expect(
      await screen.findByText(/please enter text to translate/i),
    ).toBeInTheDocument();
  });

  it("streams translation increments text", async () => {
    mockGetAuthToken.mockResolvedValue("token-123");
    mockTranslateStream.mockImplementation(() =>
      mockGenerator(["Hallo", " Welt"]),
    );

    render(<Home />);

    const tokenButton = screen.getByRole("button", { name: /get auth token/i });
    await act(async () => {
      await userEvent.click(tokenButton);
    });
    expect(await screen.findByText(/authenticated/i)).toBeInTheDocument();

    const textarea = screen.getByPlaceholderText(/enter text/i);
    await act(async () => {
      await userEvent.type(textarea, "Hello");
    });

    const translateButton = screen.getByRole("button", { name: /translate/i });
    await act(async () => {
      await userEvent.click(translateButton);
    });

    await waitFor(() => {
      expect(screen.getByText(/Hallo Welt/)).toBeInTheDocument();
    });

    expect(mockTranslateStream).toHaveBeenCalledWith(
      expect.objectContaining({
        text: "Hello",
        target_lang: "de",
      }),
      "token-123",
    );
  });

  it("handles token retrieval error", async () => {
    mockGetAuthToken.mockRejectedValue(new Error("network down"));

    render(<Home />);
    const tokenButton = screen.getByRole("button", { name: /get auth token/i });
    await act(async () => {
      await userEvent.click(tokenButton);
    });

    expect(
      await screen.findByText(/failed to get auth token/i),
    ).toBeInTheDocument();
  });
});
