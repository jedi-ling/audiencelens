/**
 * 评估报告页（EvaluationPage.tsx）的英文文案。owner: agent 6。
 *
 * "维度" 统一译成 dimension（雷达图轴、记分卡条目、伦理摘要里的提法必须一致）。
 * "评估" 是 evaluation（对报告本身打分），与 "评审" review（面板评你的材料）
 * 是两件事，英文里绝不能混用同一个词——这一页同时出现两者。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Evaluation report',

  'header.title': 'Evaluation report',
  'header.loading': 'Loading the evaluation report…',
  'header.aria': 'Back to the review report',
  'back.cta': 'Back to review report',

  'not_generated.title': 'No evaluation report yet',
  'not_generated.desc': 'Run the evaluation from the review report page first',
  'load_error.title': 'Could not load the evaluation report',
  'load_error.desc':
    '{{message}} — that does not mean the evaluation never ran; the request may simply have failed this time',

  'overall.title': 'Overall score',
  'overall.desc_one': '{{passed}} of {{count}} dimension passed',
  'overall.desc_other': '{{passed}} of {{count}} dimensions passed',
  'overall.hint': 'out of 100',
  'state.overall_pass': '✅ Evaluation passed',
  'state.overall_fail': '❌ Evaluation failed',
  'state.pass': 'Passed',
  'state.fail': 'Failed',

  'radar.title': 'Dimension radar',
  'radar.label': 'Score',
  // 见 zh 侧：整句 + 逐项两条 key，不在 tsx 里拼。
  'radar.aria': 'Evaluation dimension radar chart: {{items}}',
  'radar_item.value': '{{dimension}} {{score}}/{{max}}',

  'critical.title': 'Critical failures',

  'dimensions.title': 'Dimension detail',
  'unknown_dimension.label': '{{id}} (unknown dimension)',
  'dimension.hint': 'The local table has no description for this dimension',
  'score.label': 'Score (pass mark 2)',
  'score.value': '{{score}}/{{max}}',

  'ethics_error.desc_one':
    'The ethics summary failed to load ({{message}}) — that does not mean there are no ethics issues, only that this section did not come back. The {{count}} dimension score above is unaffected.',
  'ethics_error.desc_other':
    'The ethics summary failed to load ({{message}}) — that does not mean there are no ethics issues, only that this section did not come back. The {{count}} dimension scores above are unaffected.',
  'ethics.title': 'Ethics summary',
  'ethics_score.label': 'Ethics score',
  'stereotype.label': 'Stereotype risk',
  'violations.label_one': '{{count}} violation',
  'violations.label_other': '{{count}} violations',

  'timeline.title': 'Evaluation timeline',
  'created.label': 'Review created',
  'completed.label': 'Review completed',
  'skill.label': 'Skill used',

  'time.empty': '—',
} satisfies Messages
