import { describe, expect, it } from "vitest";
import en from "./locales/en/translation";
import hi from "./locales/hi/translation";
import te from "./locales/te/translation";

function leafKeys(value: unknown, prefix = ""): string[] {
  if (typeof value === "string") return [prefix];
  if (!value || typeof value !== "object") return [];

  return Object.entries(value as Record<string, unknown>)
    .flatMap(([key, child]) => leafKeys(child, prefix ? `${prefix}.${key}` : key))
    .sort();
}

describe("widget translations", () => {
  const englishKeys = leafKeys(en);

  it.each([
    ["Telugu", te],
    ["Hindi", hi],
  ])("keeps the %s UI translation complete", (_language, translation) => {
    expect(leafKeys(translation)).toEqual(englishKeys);
  });
});
