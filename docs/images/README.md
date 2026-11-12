# Screenshots

One folder per UI language. `README.md` and `README_ja.md` use `en/`; `README_zh.md` uses `zh/`.
The app has no Japanese UI yet, so the Japanese README shows the English screenshots.

| File | `en/` | `zh/` |
|---|---|---|
| `hero.png` | homepage (conversational review entry), `/?lang=en` | same page, `/?lang=zh` |
| `samples.png` | `/samples?lang=en` | `/samples?lang=zh` |
| `report.png` | top of the stored sample report `examples/reports/steam-page-abyss-echo/report.html`, exactly as generated | same file (byte-identical) |

`report.png` is the same image in both folders. The report text is model output in Chinese:
the engine currently generates reports in Chinese only (`SUPPORTED_REPORT_LANGS = ("zh-CN",)`,
see `docs/I18N_CONTRACT.md` §8 and §10), so no English sample report exists yet.

`hero.png` was captured on 2026-11-04; `samples.png` and `report.png` were recaptured on
2026-11-12 after the samples were regenerated. All at 1440×900 with headless Chrome (`--window-size=1440,900`) from a local
instance in single-user mode, with no API key loaded into the web process. Both UI languages were
enabled at build time with `VITE_AL_LOCALES=zh,en` and selected with `?lang=`. The app ships a
single (dark) theme.

`report.png` shows the top of the report only. The persona section further down, where each
`direct` entry's quotation appears above the comment, is not in the screenshot: the stored
`report.html` files were generated with a stylesheet bug that leaves that section unstyled
(fixed in `src/templates/report-template.html` for later runs; the stored files are kept as
generated). The Markdown reports (`report.md`) show the quotations as block quotes.
