import { describe, expect, it } from "vitest";
import { messages, resolveLocale, supportedLocales } from "./i18n";

function leafStrings(value: object): string[] {
  return Object.values(value).flatMap((item) =>
    typeof item === "string" ? [item] : leafStrings(item),
  );
}

describe("localization", () => {
  it.each([
    ["zh-Hans-CN", "zh-CN"],
    ["zh-Hant", "zh-TW"],
    ["zh-HK", "zh-TW"],
    ["pt-PT", "pt-BR"],
    ["ja-JP", "ja"],
    ["es-MX", "es"],
    ["unknown", "en"],
  ] as const)("maps %s to %s", (browserLocale, expected) => {
    expect(resolveLocale(browserLocale)).toBe(expected);
  });

  it("keeps every locale complete", () => {
    const canonicalKeys = Object.keys(messages.en).sort();
    expect(supportedLocales).toHaveLength(9);

    for (const { code } of supportedLocales) {
      expect(Object.keys(messages[code]).sort()).toEqual(canonicalKeys);
      expect(leafStrings(messages[code]).every((value) => value.trim().length > 0)).toBe(true);
      expect(Object.keys(messages[code].personalWorkspace).sort()).toEqual(
        Object.keys(messages.en.personalWorkspace).sort(),
      );
    }
  });

  it("keeps a backend-supported literal prefix in localized private chat guidance", () => {
    for (const { code } of supportedLocales) {
      expect(messages[code].personalWorkspace.chatGuidance).toMatch(/Remember:|记住：/);
    }
  });
});
