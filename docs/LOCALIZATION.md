# Localization

Agent-Me ships a dependency-free, typed localization layer for the web interface and translated project overviews for readers.

## Supported locales

| Locale | Language | Project overview |
| --- | --- | --- |
| <code>en</code> | English | [README](../README.md) |
| <code>zh-CN</code> | 简体中文 | [README](i18n/README.zh-CN.md) |
| <code>zh-TW</code> | 繁體中文 | [README](i18n/README.zh-TW.md) |
| <code>ja</code> | 日本語 | [README](i18n/README.ja.md) |
| <code>ko</code> | 한국어 | [README](i18n/README.ko.md) |
| <code>es</code> | Español | [README](i18n/README.es.md) |
| <code>fr</code> | Français | [README](i18n/README.fr.md) |
| <code>de</code> | Deutsch | [README](i18n/README.de.md) |
| <code>pt-BR</code> | Português (Brasil) | [README](i18n/README.pt-BR.md) |

## Runtime behavior

- Browser locale is used on the first visit.
- Traditional Chinese is selected for <code>zh-TW</code>, <code>zh-HK</code>, and <code>zh-Hant</code>.
- Other Chinese locales fall back to Simplified Chinese.
- Portuguese locales use Brazilian Portuguese.
- Unknown locales fall back to English.
- Manual selection is stored in local storage and updates the document language.
- No question, answer, or user identity is stored by the locale preference.

## Adding a locale

1. Add the locale and its self-name to <code>supportedLocales</code> in <code>frontend/src/i18n.ts</code>.
2. Implement every typed message key in <code>messages</code>.
3. Update locale resolution when the language needs region or script handling.
4. Add a translated overview under <code>docs/i18n</code>.
5. Add the new language link to every overview header.
6. Add or update tests for detection, selection, and fallback.
7. Run frontend linting, type checking, tests, and the production build.

## Translation standards

- Translate meaning rather than sentence structure.
- Keep commands, paths, environment variables, and API fields unchanged.
- Do not translate brand names or protocol names.
- Prefer terminology commonly used by software developers in the target locale.
- Preserve security and privacy statements without weakening them.
- English is the canonical technical specification when a translation is temporarily outdated.

## Course translations

The project overview and web interface may have broader coverage than the complete course. Full
lesson coverage is tracked separately in [`course/LANGUAGES.md`](../course/LANGUAGES.md).

A full course translation lives under `course/translations/<locale>/` and mirrors the English
syllabus, 8 numbered lessons, glossary, and rubric. Follow the contribution and human-review rules
in [`CONTRIBUTING.md`](../CONTRIBUTING.md#translate-the-course). Do not label a partial or
unreviewed lesson set as complete.
