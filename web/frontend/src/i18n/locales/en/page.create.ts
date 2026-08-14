// owner: agent 4（见 zh/page.create.ts 的文件头，三条边界同样适用于这里）。
//
// 带 {{count}} 的 key 在 en 侧必须同时有 _one 和 _other（契约 D9），
// 即使两个变体的英文完全一样也要写全——i18n:check 卡这条。
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'New review',

  // ---- Stepper。中文侧是动宾短语（"选择技能"），英文侧用名词：
  //      步骤条横向空间很紧，动词开头的标签在窄屏上会被挤掉。 ----
  'stage.skill': 'Skill',
  'stage.task_type': 'Task type',
  'stage.material': 'Materials',
  'stage.persona': 'Personas',
  'stage.option': 'Options',
  'stage.confirm': 'Confirm',

  // ---- Step 0: skill ----
  'skill.title': 'Pick a review skill',
  'skill.desc': 'Each skill reviews your work from a different angle',
  'dropped_skill.title': '“{{skill}}” can’t start a review yet',
  'dropped_skill.desc':
    'It doesn’t change how a review runs, so picking it would change nothing — we left it unselected. Choose another skill.',
  'skill_list.error': 'Couldn’t load the skill list',
  'skill_error.title': 'The skill list didn’t load',
  'skill_error.cta': 'Reload',
  'skill_list.empty': 'This account has no skills that can start a review.',
  'skill_card.meta_one': '{{count}} task type',
  'skill_card.meta_other': '{{count}} task types',

  // ---- Step 1: task type ----
  'task_type.title': 'Pick a task type',
  'task_type.desc': 'Choose what kind of work you want reviewed',
  'task_type_scoped.desc': 'Skill: {{skill}} · these are the task types it declares support for',
  'task_type_open.desc': 'Skill: {{skill}} · it sets no task-type limit, so all of them are open',
  'category_all.tab': 'All',

  // ---- Review mode ----
  'mode.title': 'Review mode',
  // 档位名读 enum.mode_badge.*，不在这里重抽。
  'mode_name.value': '{{mode}} mode',
  // range 是 "3" 或 "4-6"，最小值是 3，所以这里不会出现 "1 personas"。
  'mode_card.unit': '{{range}} personas',
  'feature_cross_exam.badge': 'Cross-examination',
  'feature_calibration.badge': 'Calibration check',
  'feature_none.badge': 'No extra steps',

  // ---- Step 2: material ----
  'material.title': 'Add your material',
  'material.desc': 'Type it in, or upload a file and let AI pull the material out',
  'input_mode_text.tab': 'Text input',
  'input_mode_file.tab': 'File upload',
  'dropzone.cta': 'Drop a file here, or <click>click to upload</click>',
  'dropzone.hint':
    '.txt .md .json .pdf .docx supported (legacy .doc isn’t) · AI pulls out structured material',
  'extract.pending': 'AI is reading your file and pulling out the material...',
  'extract.hint': 'This usually takes 5–10 seconds',
  'extract.error':
    'AI extraction failed: {{reason}}. You can also fill in the fields below by hand.',
  // 只出现在上面那句的 {{reason}} 位置上，所以小写。
  'extract_reason_unknown.error': 'unknown reason',
  'extract.success_one': '{{count}} field extracted · edit it below',
  'extract.success_other': '{{count}} fields extracted · edit them below',
  'examples.cta': 'Quick start: import sample data',
  'target.label': 'Review target',
  'target.placeholder': 'e.g. “Stellar Drift” concept design doc',
  'fields.title': 'Edit material details',
  'fields.hint_one': 'AI extracted {{count}} field — check it over',
  'fields.hint_other': 'AI extracted {{count}} fields — check them over',
  'generic_field.label': 'Material',
  'generic_field.placeholder':
    'Paste the full text you want reviewed (this task type has no per-field form yet, so paste it all in one go)...',
  'extra_fields.desc':
    'The text below came out of your file and isn’t a standard field for “{{taskType}}”, but it will still be sent to the reviewers. Clear anything you don’t want submitted.',
  'extra_fields_unknown.label': 'the current task type',

  // ---- Step 3: personas ----
  'persona.title': 'Pick a persona pack',
  'persona.desc': 'Pick a pack to fill the panel in one click, or choose personas yourself',
  'mode_summary.title': 'Current review mode',
  'mode_summary.unit': '· {{range}} personas',
  'pack_card.unit_one': '{{count}} persona',
  'pack_card.unit_other': '{{count}} personas',
  'pack_intro.desc': '<name>{{name}}</name>: {{desc}}',
  'persona_list.title': 'Personas',
  'persona_list.meta_one': '{{count}} selected · max {{max}}',
  'persona_list.meta_other': '{{count}} selected · max {{max}}',
  'pack_conflict.title_one':
    'Personas from different packs can’t be mixed (you have {{count}} pack: {{packs}})',
  'pack_conflict.title_other':
    'Personas from different packs can’t be mixed (you have {{count}} packs: {{packs}})',
  'pack_conflict.desc':
    'A review runs on one persona pack only — mix packs and everything outside one of them is dropped. Keep the personas from a single pack, or just click a pack above to select it in one go.',
  'pack_conflict.value': ', ',
  'over_max.title': 'Over the persona limit for {{mode}} mode ({{max}} max)',
  'over_max.desc_one':
    'This mode runs at most {{max}} reviewers — deselect {{count}} of them, or go back to the task type step and pick a mode that seats more.',
  'over_max.desc_other':
    'This mode runs at most {{max}} reviewers — deselect {{count}} of them, or go back to the task type step and pick a mode that seats more.',

  // ---- Step 4: options ----
  'option.title': 'Review options',
  'option.desc': 'Add extra passes to this review',
  'evaluation.label': 'Add an evaluation report',
  'evaluation.desc_one':
    'When the review finishes, run a {{count}}-dimension evaluation and produce a scorecard plus an ethics report.',
  'evaluation.desc_other':
    'When the review finishes, run a {{count}}-dimension evaluation and produce a scorecard plus an ethics report.',
  'red_team.label': 'Add a red-team pass',
  'red_team.desc':
    'Once the standard review is done, a red team goes after your product on purpose: it attacks the weak points, plays your harshest users and the worst-case scenarios, and surfaces the risks that stay hidden otherwise.',
  'red_team_case_pricing.badge': 'Monetization stress test',
  'red_team_case_community.badge': 'Community backlash rehearsal',
  'red_team_case_localization.badge': 'Cultural and localization risk',
  'red_team_case_pr.badge': 'PR crisis simulation',

  // ---- Step 5: confirm ----
  'confirm.title': 'Confirm your setup',
  'confirm.desc': 'Check everything below, then launch the review',
  'confirm_skill.title': 'Review skill',
  'confirm_task_type.title': 'Task type',
  'confirm_mode.title': 'Review mode',
  'confirm_target.title': 'Review target',
  'confirm_target.empty': 'Not filled in',
  'confirm_material.title': 'Material',
  'confirm_material.meta_one': '<filled>{{count}}</filled> / {{total}} field filled in',
  'confirm_material.meta_other': '<filled>{{count}}</filled> / {{total}} fields filled in',
  // 中英冒号不是同一个字符，中文侧是全角"："，这里是半角冒号。
  'confirm_field.label': '{{name}}:',
  'confirm_field.empty': 'Not filled in',
  'confirm_persona.title_one': 'Selected persona ({{count}})',
  'confirm_persona.title_other': 'Selected personas ({{count}})',
  'confirm_persona.meta': '· Persona pack: {{pack}}',
  'confirm_extra.title': 'Extra passes',
  'confirm_extra_evaluation.badge': 'Evaluation report',
  'confirm_extra_red_team.badge': 'Red team',
  'cost.title': 'Cost',
  'cost.desc':
    'What this run costs depends on how long your material is, how many personas take part and which model they use — there is no accurate estimate before it starts. Once the review is done, the report page and your review history show the tokens and the money it actually spent.',

  // ---- Footer actions ----
  'launch.cta': '🚀 Launch review',
  'launch.error': 'Couldn’t start the review',
  'launch_pack_mismatch.error':
    'The personas you picked don’t match the persona pack or the review mode. Go back to step 3, adjust, then launch.',
  'launch_no_material.error':
    'No review material yet. Go back to step 2 and add some, then launch.',
} satisfies Messages
