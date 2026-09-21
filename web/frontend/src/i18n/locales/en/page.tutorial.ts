/**
 * Tutorial page (TutorialPage.tsx). owner: agent 7.
 *
 * ⚠ 任务类型名与材料字段名不在这里，理由见 zh/page.tutorial.ts 的文件头：
 * 它们是目录数据，英文事实源是 catalog.* overlay。
 *
 * 页面标题用 nav.item.tutorial 已经定下的 "Guide"，不再另起一个说法——
 * 导航写 Guide、页面标题写 Tutorial 会让人以为点错了地方。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Guide',
  'header.title': 'Guide',
  'header.subtitle': 'How an AudienceLens review works end to end, and what material each task type needs',

  // ---- Review flow ----
  'flow.title': 'How a review runs',
  'flow.desc': 'Upload a file → AI extracts → you confirm → the review runs',
  'flow.step': 'Step {{n}}',

  'step_select_type.label': 'Pick a task type',
  'step_select_type.desc': 'Choose the task type that matches what you want reviewed',
  'step_upload.label': 'Upload a file',
  'step_upload.desc': 'Upload any document and the AI pulls out structured material',
  'step_edit.label': 'Edit the material',
  'step_edit.desc': 'Check what the AI extracted, then correct or add to it',
  'step_panel.label': 'Pick personas and run',
  'step_panel.desc': 'Choose a persona pack, start the review, read the report',

  // ---- Which review mode to pick. Tier names read enum.mode_badge.*,
  //      descriptions read i18n/catalog.ts::getReviewModes() — not duplicated here ----
  'modes.title': 'Which review mode to pick',
  'modes.desc': 'The three tiers differ in persona count and whether cross-examination / confidence calibration run — price scales with that',
  'modes_personas.label': 'Personas',
  'modes_cross_exam.label': 'Cross-examination',
  'modes_calibration.label': 'Confidence calibration',
  'modes_yes.value': '✓ Yes',
  'modes_no.value': '—',

  // ---- Upload and extract ----
  'upload.title': 'Upload a file, let the AI extract',
  'upload.desc': 'The main path: upload a document → the AI reads and extracts → you confirm',
  'upload.hint':
    'Every field stays editable after extraction. Add what the AI missed, correct anything it got wrong, write in extra context — what you submit is what gets reviewed.',

  'method.badge': 'Recommended',

  'method_file.title': 'File upload (recommended)',
  'method_file.desc': 'Upload any document; the AI reads it and extracts structured material',
  'method_file_formats.hint': 'Supports .txt .md .json .pdf .docx (save a legacy .doc as .docx first)',
  'method_file_autofill.hint': 'The AI reads the document and fills in every field',
  'method_file_editable.hint': 'Each field can still be edited once extraction finishes',
  'method_file_any_doc.hint': 'GDDs, design docs, devlogs — upload them as they are',

  'method_example.title': 'Import an example',
  'method_example.desc': 'Load a ready-made sample in one click and see the whole flow',
  'count.with_number_one': '{{count}} ready-made example to start from',
  'count.with_number_other': '{{count}} ready-made examples covering a range of task types',
  'count.unknown': 'Ready-made examples covering a range of task types',
  'method_example_first_use.hint': 'A good way to see what the system does on your first run',

  'method_manual.title': 'Fill it in yourself',
  'method_manual.desc': 'Each task type generates its own form — fill it in field by field',
  'method_manual_fields.hint': 'Every task type has its own required and optional fields',
  'method_manual_when.hint': 'Best when you have little material, or want exact control over it',

  // ---- What to upload ----
  'filetypes.title': 'What is worth uploading',
  'filetypes.desc': 'Any document that says something about your game will do',
  'filetype_gdd.title': 'Game design doc (GDD)',
  'filetype_gdd.desc': 'Core loop, system design, character setup, and so on',
  'filetype_devlog.title': 'Devlog / patch notes',
  'filetype_devlog.desc': 'What shipped, where development stands, the roadmap',
  'filetype_store.title': 'Steam / store page copy',
  'filetype_store.desc': 'Description, tags, screenshot captions, pricing',
  'filetype_crowdfunding.title': 'Crowdfunding page',
  'filetype_crowdfunding.desc': 'The pitch, reward tiers, team background',
  'filetype_community.title': 'Community plans',
  'filetype_community.desc': 'Discord channel layout, community strategy, event plans',
  'filetype_localization.title': 'Localization files',
  'filetype_localization.desc': 'Sample translations, culture notes, UI fit problems',
  'limits.hint':
    'What the system actually accepts: text files {{text_ext}} (up to {{text_max}} each), images {{image_ext}} (up to {{image_max}} each). Convert anything else to one of these formats before uploading.',

  // ---- Material each task type needs ----
  'materials.title': 'What each task type needs',
  'materials.desc': 'The AI extracts the fields for the task type you picked; you can always add more by hand',
  'materials_task_type.label': 'Task type',
  'materials_required.label': 'Required fields',
  'materials_optional.label': 'Optional fields',

  // ---- What the report contains ----
  'results.title': "What's in the report",
  'results.desc': 'Every review report covers the following',
  'result_risk.label': 'Risk level',
  'result_risk.desc': 'A four-level rating: green, yellow, orange, red',
  'result_stance.label': 'Stance breakdown',
  'result_stance.desc': 'Where each persona lands (the available stances depend on the task type)',
  'result_issues.label': 'Prioritized issues',
  'result_issues.desc': 'The key problems, ordered by severity',
  'result_persona.label': 'Every persona in full',
  'result_persona.desc': 'The independent read from each persona on the panel',
  'result_calibration.label': 'Calibration metrics',
  'result_calibration.desc': 'Quality signals: agreement, coverage, hallucination rate',

  'start.cta': 'Create a review',

  // ---- More features. These already ship but aren't mentioned on any tutorial-like page ----
  'more.title': 'More features',
  'more.desc': "Beyond running a review, these are worth a look",
  'more_ledger.title': 'Judgment ledger · Prediction review',
  'more_ledger.desc': "Save both the panel's judgment and your own, then verify against reality once it lands and see who called it",
  // 见 zh 侧：/dashboard 已并进设置页，key 与文案一起改名。
  'more_overview.title': 'Track record & shortcuts',
  'more_overview.desc': 'A quick look at your track record, recent reviews, and shortcuts (the first section of Settings)',
  'more_byok.title': 'Bring your own key (BYOK)',
  'more_byok.desc': 'Plug in your own API key to skip platform quotas — billing goes straight to your own account',
  'more_cdk.title': 'Redeem code',
  'more_cdk.desc': 'Got a redeem code? Add it on the settings page and your balance tops up in seconds',
} satisfies Messages
