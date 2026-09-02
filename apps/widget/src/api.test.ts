import { afterEach, describe, expect, it, vi } from "vitest";
import { sendFeedback } from "./api";
import type { WidgetConfig } from "./types";

const config: WidgetConfig = {
  apiUrl: "http://localhost:8000",
  tenant: "ciet",
  position: "bottom-right",
};

afterEach(() => vi.restoreAllMocks());

describe("feedback API", () => {
  it("accepts a successful 204 response without attempting JSON parsing", async () => {
    const json = vi.fn();
    vi.spyOn(window, "fetch").mockResolvedValue({ ok: true, status: 204, json } as unknown as Response);
    await expect(sendFeedback(config, "message-1", "up")).resolves.toBeUndefined();
    expect(json).not.toHaveBeenCalled();
  });
});
