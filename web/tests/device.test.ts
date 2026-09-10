import { beforeEach, describe, expect, it } from "vitest";
import { getOrCreateDeviceId } from "@/lib/device";

describe("getOrCreateDeviceId", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("creates and persists a device id across calls", () => {
    const first = getOrCreateDeviceId();
    expect(first).toMatch(/^[0-9a-f-]{36}$/);
    const second = getOrCreateDeviceId();
    expect(second).toBe(first);
  });

  it("stores the id in localStorage under a stable key", () => {
    const id = getOrCreateDeviceId();
    expect(window.localStorage.getItem("hu-guidebook-device-id")).toBe(id);
  });
});
