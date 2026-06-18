import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import type { Language } from "../types";
import en from "./locales/en/translation";
import hi from "./locales/hi/translation";
import te from "./locales/te/translation";

export const languageStorageKey = "ciet-ai-language";

const supportedLanguages: Language[] = ["en", "te", "hi"];

function isLanguage(value: string | null | undefined): value is Language {
  return supportedLanguages.includes(value as Language);
}

function browserLanguage(): Language {
  const candidates = [navigator.language, ...navigator.languages].filter(Boolean);
  for (const candidate of candidates) {
    const code = candidate.toLowerCase().split("-")[0];
    if (isLanguage(code)) return code;
  }
  return "en";
}

export function initialLanguage(): Language {
  try {
    const saved = window.localStorage.getItem(languageStorageKey);
    if (isLanguage(saved)) return saved;
  } catch {
    // Storage can be blocked in embedded contexts.
  }
  return browserLanguage();
}

export function persistLanguage(language: Language): void {
  try {
    window.localStorage.setItem(languageStorageKey, language);
  } catch {
    // The widget still works when storage is blocked.
  }
}

void i18n.use(initReactI18next).init({
  lng: initialLanguage(),
  fallbackLng: "en",
  supportedLngs: supportedLanguages,
  resources: {
    en: { translation: en },
    te: { translation: te },
    hi: { translation: hi },
  },
  interpolation: {
    escapeValue: false,
  },
});

export { i18n };
