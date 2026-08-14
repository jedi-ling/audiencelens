// owner: agent-9。分工与"为什么不与 page.ask 合并"见 zh/page.progress.ts 的文件头。
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Review progress',

  'header.title': 'Review',
  'header.subtitle': 'Review progress',
  'skill.label': 'Skill',
  'selected_personas.badge_one': 'Hand-picked · {{count}} persona',
  'selected_personas.badge_other': 'Hand-picked · {{count}} personas',
  'project.badge': 'Project · {{key}}',
  'report.cta': 'View report',

  'load_error.title': 'Couldn’t load this review',
  'load_error.desc': 'That doesn’t mean it was deleted — the review keeps running in the background.',
  'not_found.empty': 'No review found',
  'back.cta': 'Back to history',

  'overall.label': 'Overall',
  'status.label': 'Status',
  'persona_count.label': 'Personas',
  'cost.label': 'Spent',

  // 英文侧刻意用 "keeps running" 而不是直译的 "will not be interrupted"：
  // 用户此刻担心的是"我的钱和时间是不是白花了"，正面陈述比否定句更快消掉这个担心。
  'poll_failure.error_one':
    'Can’t sync progress from the server ({{count}} failed attempt so far) — retrying automatically. The review keeps running in the background.',
  'poll_failure.error_other':
    'Can’t sync progress from the server ({{count}} failed attempts so far) — retrying automatically. The review keeps running in the background.',
  'ws_unavailable.hint_one':
    'Live updates are unavailable, so this page now checks for progress every {{count}} second. Progress still comes through, just a little slower.',
  'ws_unavailable.hint_other':
    'Live updates are unavailable, so this page now checks for progress every {{count}} seconds. Progress still comes through, just a little slower.',
  'ws_reconnect.hint': 'Live updates dropped out. Reconnecting — polling for progress in the meantime.',
  'stall.hint_one':
    'Nothing new for {{count}} second — still working (one persona may be partway through a long stretch of reasoning). This page re-checks every {{interval}} seconds.',
  'stall.hint_other':
    'Nothing new for {{count}} seconds — still working (one persona may be partway through a long stretch of reasoning). This page re-checks every {{interval}} seconds.',

  'failed.title': 'Review failed',
  'failed.desc': 'The run didn’t finish. Try again in a moment.',
  'failed.cta': 'Start another review',
  'done.title': 'Review finished — the report is ready',
  'done.cta': 'View full report',

  'running_card.title': 'Review under way',
  'running_card.pending': 'Waiting for the panel to assemble…',

  'personas.title': 'Persona progress',
  'personas.empty': 'This review has no per-persona detail to show',
  'personas.pending': 'The panel is convening — each persona lights up as it finishes…',
  'persona_cost.label': 'Cost {{amount}}',
  'persona_failed.error': 'Run failed',
  'persona_done.badge': 'Done',
  'persona_remaining.pending_one': '{{count}} persona still reviewing…',
  'persona_remaining.pending_other': '{{count}} personas still reviewing…',

  'cross_exam.title': 'Cross-examination',
  'aggregation.title': 'Aggregation',
  'stage.waiting': 'Queued',
  'stage.running': 'Running',
  'stage.completed': 'Done',
} satisfies Messages
