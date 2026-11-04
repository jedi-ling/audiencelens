# Screenshots

One folder per UI language. `README.md` and `README_ja.md` use `en/`; `README_zh.md` uses `zh/`.
The app has no Japanese UI yet, so the Japanese README shows the English screenshots.

| File | `en/` | `zh/` |
|---|---|---|
| `hero.png` | homepage (conversational review entry), `/?lang=en` | same page, `/?lang=zh` |
| `samples.png` | `/samples?lang=en` | `/samples?lang=zh` |
| `report.png` | stored sample report `examples/reports/steam-page-abyss-echo/report.html` | same file (byte-identical) |

`report.png` is the same image in both folders. The report text is model output in Chinese:
the engine currently generates reports in Chinese only (`SUPPORTED_REPORT_LANGS = ("zh-CN",)`,
see `docs/I18N_CONTRACT.md` §8 and §10), so no English sample report exists yet.

Captured 2026-11-04 at 1440×900 with headless Chrome (`--window-size=1440,900`) from a local
instance in single-user mode, with no API key loaded into the web process. Both UI languages were
enabled at build time with `VITE_AL_LOCALES=zh,en` and selected with `?lang=`. The app ships a
single (dark) theme.
