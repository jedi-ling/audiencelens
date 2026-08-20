/**
 * 判断复利页（LedgerPage.tsx）的英文文案。owner: agent 6（与 zh/page.ledger.ts 同一个人）。
 *
 * 译名口径：页面标题沿用 nav.item.ledger 的 "Track record"。
 * 那条 key 的注释里写明了理由（"judgment compounding" 直译在英文里读不通，
 * 用产品实际做的事命名），导航、页面标题、教程必须是同一个词。
 *
 * 复数：带 {{count}} 的 key 在 en 侧必须同时有 _one 和 _other。
 * 调用方永远只写逻辑 key，后缀是运行时按 Intl.PluralRules 选的。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Track record',

  'header.title': 'Track record',
  'header.desc':
    'Every prediction a review makes is timestamped and filed. When real playtesting comes back, record what actually happened — so how good these calls are stops being a matter of opinion.',

  'error.title': 'Could not load your track record',
  'error.hint':
    'This page holds the predictions that belong to you. While you are signed out the backend cannot tell whose ledger is whose, so it declines to return one.',
  'error.pending': 'Retrying…',
  'error.cta': 'Sign in / Sign up',

  'value.title': 'Product value check',
  'feedback_coverage.label': 'Feedback coverage',
  'useful_rate.label': 'Found useful',
  'decision_change.label': 'Changed a decision',
  'adoption.label': 'Suggestions adopted',
  'hours_saved.label': 'Hours saved',
  'hours_saved.value': '{{hours}}h',
  'avg_model_cost.label': 'Avg. model cost',
  'cost_per_useful.label': 'Cost per useful report',
  'cost_per_adopted.label': 'Cost per adopted fix',
  'avg_willingness.label': 'Avg. willingness to pay',

  'by_task_type.title': 'Which task type earns its keep',
  'task_useful.value': 'Useful {{value}}',
  'task_adopted.value': 'Adopted {{value}}',
  'top_fixes.title': 'Suggestions that actually got acted on',
  'top_fixes.value': '×{{times}}',

  'total_judgments.label': 'Predictions filed',
  'pending_verification.label': 'Awaiting outcome',
  'verified.label': 'Verified',
  'hit_rate.label': 'Hit rate',

  'leaderboard.title': 'Whose calls are worth listening to',
  'sample.value': 'n={{size}}',

  'calibration.title': 'Confidence calibration',
  'calibration.desc':
    'When a review says how sure it is, does reality agree? The hit rate above answers “how often was it right”; this answers “was it actually right when it said it was sure”.',
  'calibration.hint':
    'Confidence comes from the synthetic panel’s heuristic weights and has never been recalibrated against real outcomes — this table is how that gets done.',
  'mean_confidence.label': 'Claimed confidence',
  'observed_hit.label': 'Actual hit score',
  'observed_hit.hint': 'hit=1 / partial=0.5 / miss=0',
  'brier.label': 'Brier score',
  'brier.hint': 'Lower is better, 0 = perfect',
  'ece.label': 'Calibration error',
  'ece.hint': 'Average gap between claimed and actual',
  'bins.title': 'By confidence band',
  'bins.value': '{{lower}}–{{upper}}%',
  'bin_claimed.value': 'Said {{value}}',
  'bin_observed.value': 'Actual {{value}}',
  'over_estimate.value': 'Overconfident by {{value}}',
  'under_estimate.value': 'Underconfident by {{value}}',
  'low_confidence.hint_one':
    'Only {{count}} sample so far — treat the numbers below as indicative, they carry no statistical weight.',
  'low_confidence.hint_other':
    'Only {{count}} samples so far — treat the numbers below as indicative, they carry no statistical weight.',
  'verified_rows.value_one': '{{count}} outcome recorded.',
  'verified_rows.value_other': '{{count}} outcomes recorded.',
  // 两个计数在同一句里时 plural 只能挂一个（ICU 同限制）。这里挂被排除的条数，
  // 因为"1 条被排除"与"3 条被排除"在英文里的差别正好落在括号内那句上。
  'excluded_rows.value_one':
    '{{verified}} outcomes recorded ({{count}} left out — no confidence value, or an outcome that could not be mapped).',
  'excluded_rows.value_other':
    '{{verified}} outcomes recorded ({{count}} left out — no confidence value, or outcomes that could not be mapped).',

  'list.title': 'Past predictions',
  'list.label': 'Only those awaiting an outcome',
  'list.hint':
    'Verdicts you record here have teeth: a finding marked “did not happen” stops being carried into this project’s next review.',
  'list.error': 'Could not load your predictions — the reason is above.',
  'list_empty.title': 'No predictions yet',
  'list_empty.desc': 'Run a review and its conclusions get filed here automatically.',
  'item.meta': '{{author}} · {{severity}} · {{time}}',
  'panel.label': 'Panel consensus',

  // 见 zh 侧那段归属说明：enum.verdict.* 交付后这四条整体迁走。
  'state.hit': 'Called it',
  'state.partial': 'Partly right',
  'state.miss': 'Did not happen',
  'state.unknown': 'Too early to tell',

  'verify_error.title': 'Could not record that — this prediction is still awaiting an outcome',
  'verify_error.cta': 'Sign in / Sign up, then record it',

  'stat.empty': '—',
} satisfies Messages
