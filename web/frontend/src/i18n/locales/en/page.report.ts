// owner: agent-1（见 zh/page.report.ts 的文件头——那里写了这份语料的三条边界：
// 只有前端文案进这里、枚举只做浅层映射、导出件也是一份报告）。
//
// 翻译口径：这是给英文用户读的产品文案，不是中文的逐字对应。凡是中文里
// 「破折号 + 补一句为什么」的地方，英文用了 em dash 或分号，保留那半句的信息量；
// 凡是中文用「」引原词的地方，英文用 “ ”（U+201C/201D），不留中文书名号。
import type { Messages } from '@/i18n/types'

export default {
  /* ---------------- 页面框架 ---------------- */
  'meta.title': 'Review report',
  'header.title': 'Review report',
  'header.subtitle': 'Review report',
  'header.badge': '{{mode}} mode',
  'body.loading': 'Loading the report…',
  'pending.title': 'No report yet',
  'pending.desc': 'The review may still be running, or may not have started — open the detail page for live progress.',
  'pending.cta': 'View progress',

  /* ---------------- 反复出现的链接 ---------------- */
  'link_detail.cta': 'Review details',
  'link_new_review.cta': 'Start a new review',
  // "Sign in" 而不是 "Log in"：全站（nav.session / page.ask / page.ledger）都用
  // Sign in，同一个动作在报告页换个说法会读成两件事。
  'link_login.cta': 'Sign in / Sign up',

  sep_enum: ', ',
  sep_semicolon: '; ',
  sep_colon: ': ',

  'unknown_level.value': 'Unrecognized level ({{raw}})',

  /* ---------------- ETHICS.md 强制项：合成声明 ---------------- */
  'synthetic_banner.title':
    'Synthetic review panel: every opinion below was written by AI personas, not by real players or users.',
  'synthetic_banner.desc':
    'This report must not be shown or cited as “player research”, “user survey data”, or “how real players actually feel”. It is a pre-screening tool for use before you put anything in front of real people: it does not replace a playtest or a user interview, and it should never be the only basis for a release decision.',

  /* ---------------- 人格降级 ---------------- */
  'degradation.desc_one':
    '{{count}} persona could not finish this review. Everything below rests on the output of the {{succeeded}} personas that did.',
  'degradation.desc_other':
    '{{count}} personas could not finish this review. Everything below rests on the output of the {{succeeded}} personas that did.',
  'degradation_partial.desc_one':
    '{{count}} persona could not finish this review. Everything below rests only on the personas that did.',
  'degradation_partial.desc_other':
    '{{count}} personas could not finish this review. Everything below rests only on the personas that did.',
  'degradation.label': 'Did not finish: {{names}}',

  /* ---------------- 三层校验门控 ---------------- */
  'gate.title_one': '{{count}} persona’s output failed quality validation and is excluded from every conclusion below',
  'gate.title_other': '{{count}} personas’ output failed quality validation and is excluded from every conclusion below',
  'gate.label': 'Unrecognized failure type ({{raw}})',
  'gate.empty': 'The engine did not report a failure type',

  /* ---------------- 可证伪预测 ---------------- */
  'predictions.title': 'Falsifiable predictions',
  'predictions.badge_one': '{{count}} prediction',
  'predictions.badge_other': '{{count}} predictions',
  'predictions.desc':
    'Each one names a target metric and a pass/fail bar, so you can actually go and test it. Fill in the real outcome after a playtest and it feeds back into calibrating how accurate this panel is.',
  'predictions.hint':
    'Heuristic confidence {{pct}} — computed from synthetic-panel rules, <emph>never calibrated against real outcomes</emph>, and not a historical hit rate',
  'prediction_metric.label': 'Target metric',
  // 不留前导空格：外层 span 已经有 ml-1，再加一个空格会变成两个间距。
  'prediction_metric.hint': '({{direction}})',
  'prediction_window.label': 'Verification window',
  'prediction_criterion.label': 'Pass/fail bar',
  'prediction_method.label': 'How to verify',

  /* ---------------- 自适应面板 ---------------- */
  'adaptive.title': 'Adaptive panel',
  'adaptive.empty': 'Not used for this run.',
  'adaptive_reason.label': 'Unrecognized reason code: {{raw}}',
  'adaptive_executed.label': 'Personas that reviewed',
  'adaptive_saved.label': 'Calls saved',
  'adaptive_initial.label': 'Starting panel',
  'adaptive_step.label_one': 'after {{count}} persona',
  'adaptive_step.label_other': 'after {{count}} personas',
  'adaptive_step.value': 'added {{persona}}',
  'adaptive_step.hint': 'the next persona',
  'adaptive_stop.label': 'stopped expanding',
  'adaptive.hint':
    'The expansion score is an explainable heuristic, not measured information gain; its weights still need calibrating against real outcomes.',

  /* ---------------- 显式点名人格 ---------------- */
  'panel_selection.title': 'Not every persona you named took part in this review',
  'panel_selection.label': 'Took part: {{names}}',

  /* ---------------- 预算刹车 ---------------- */
  'budget.title': 'Cost cap reached — this run skipped some stages',
  'budget.desc':
    'The persona stage of this review cost about {{spent}}, hitting the per-run cap of {{cap}} (max_cost_per_run_usd in budget.yaml).',
  'budget_generic.desc': 'This review hit the per-run cost cap.',
  'budget.hint':
    'Cross-examination did not run. The absence of a “Cross-examination” section below does not mean the personas agreed — it only means no debate was run this time.',

  /* ---------------- 评审失败 ---------------- */
  'failed.title': 'This review failed. No report was produced.',
  'failed.desc':
    'This is not a report that “found no problems” — the review never finished, so there is no risk level, no consensus, no stance distribution. Do not make a release decision on it.',
  'failed.label': 'Reviewed: {{title}}',
  'failed.hint': 'Failure reason (backend, verbatim)',
  'failed.empty':
    'The backend did not return a reason. The per-persona execution log on the review detail page may have something more specific.',

  /* ---------------- 报告加载失败 ---------------- */
  'load_error.title': 'Could not load the report',
  'load_error.desc':
    'We could not fetch this report, so nothing is shown below — that does not mean the review has no results.',

  /* ---------------- ETHICS.md 强制项：局限与注意事项 ---------------- */
  'limitations.title': 'Limitations & Caveats',
  limitation_synthetic:
    'Synthetic personas are not people: the stance distribution reflects what the AI personas wrote, not how any real audience is split.',
  limitation_variance:
    'Over-agreement: when an LLM simulates a group, its output varies less than real people do, so real-world disagreement is probably understated here.',
  limitation_materials:
    'Your materials set the ceiling: when the materials lack a kind of evidence, personas answer “not specified” and the report flags an information gap — “not specified” is not “no problem here”.',
  limitation_demographic:
    'Demographics do not explain anything: gender, age and region are not causes of preference. Do not generalise these findings to a real population on that basis.',
  limitation_feedback_loop:
    'Feedback-loop risk: reviewing every iteration with the same personas can push a product towards a simulated “average taste”. Rotate the persona mix periodically.',

  /* ---------------- 交叉质询 ---------------- */
  'cross_exam.title': 'Cross-examination',
  'cross_exam.badge_one': '{{count}} round run',
  'cross_exam.badge_other': '{{count}} rounds run',
  'cross_exam_legacy.desc_one':
    'This report came from an older version: its cross-examination record is stored in the old format ({{count}} raw entry), so the disputes, rebuttals and vote changes cannot be recovered. Run a new review to get the full record.',
  'cross_exam_legacy.desc_other':
    'This report came from an older version: its cross-examination record is stored in the old format ({{count}} raw entries), so the disputes, rebuttals and vote changes cannot be recovered. Run a new review to get the full record.',
  'cross_exam_mode_unknown.label': 'Unknown mode',
  'cross_exam_mode_unknown.value': 'Unknown mode ({{raw}})',
  'cross_exam_mode_unknown.desc':
    'This report does not say how cross-examination was run, so there is no way to tell whether a rebuttal actually happened — read it as “no rebuttal took place”.',
  'cross_exam_fallback.desc': '“{{requested}}” was requested; this run fell back to “{{actual}}”.',
  'cross_exam_limitation.label': 'Engine note: ',
  'cross_exam_absent.desc':
    'This report has no cross-examination record, and it does not say why. It could be that this review tier has no rebuttal stage, or that no two personas held opposing views worth debating. Please do not read it as “everyone agreed”.',
  'cross_exam_skipped.desc':
    'No cross-examination was run: the persona stage had already hit the per-run cost cap, so it was skipped rather than spending more (see the cost notice at the top of the page). That does not mean the personas agreed — it only means no debate was run this time.',
  'cross_exam_failures.title_one': 'Failure during cross-examination ({{count}})',
  'cross_exam_failures.title_other': 'Failures during cross-examination ({{count}})',
  'cross_exam_failures.label': 'stage not recorded',
  'cross_exam_failures.empty': 'no reason given',

  'dispute.empty': 'Untitled dispute',
  'dispute.error': 'Cross-examination did not finish for this dispute: {{reason}}',
  'dispute_empty.desc':
    'No dispute needed cross-examining this time — the personas did not diverge enough on any key judgement.',
  'dispute_empty.hint': 'No presentable disputes came out of this run; see the note above for why.',

  // pro / con 说的是"认为问题多严重"，不是"支持/反对某个方案"。
  // 译成 for / against 会把两边的意思整个说反。
  'argument_pro.label': 'Says the problem is worse',
  'argument_con.label': 'Says the problem is milder',
  'argument.label': 'This side’s rebuttal to the other',
  'argument.empty': 'This side produced no rebuttal.',

  'change.empty': 'Unknown persona',
  'change.badge': 'model claimed a switch to {{stance}}',
  'change.label': 'Confidence {{before}} → {{after}} (change {{delta}})',
  'change_threshold.label': 'Confidence {{before}} → {{after}} (change {{delta}}, accept threshold θ={{threshold}})',
  'change.error': 'Not accepted because: {{reason}}',
  'change.desc': 'Basis (rebuttal, verbatim): {{reason}}',

  'vote.title': 'Vote changes',
  'vote.badge_one': '{{count}} change',
  'vote.badge_other': '{{count}} changes',
  'vote_threshold.badge_one': '{{count}} change · accept threshold θ={{threshold}}',
  'vote_threshold.badge_other': '{{count}} changes · accept threshold θ={{threshold}}',
  'vote.empty':
    'No rebuttal round ran, so there are no vote changes. A vote change can only come from a rebuttal that actually happened.',
  'vote_unchanged.desc':
    'Neither side moved this round. That is a completely normal — and common — outcome of cross-examination, and it does not mean the rebuttal failed to happen.',
  'suppressed.desc_one':
    '{{count}} further stance change was proposed by the model but not accepted (vote changes are decided in code; the model’s own claim is not taken at face value)',
  'suppressed.desc_other':
    '{{count}} further stance changes were proposed by the model but not accepted (vote changes are decided in code; the model’s own claim is not taken at face value)',
  'suppressed_no_update.desc_one':
    '{{count}} further stance change was proposed by the model but not accepted (vote changes are decided in code; the model’s own claim is not taken at face value); this run was configured not to accept stance updates',
  'suppressed_no_update.desc_other':
    '{{count}} further stance changes were proposed by the model but not accepted (vote changes are decided in code; the model’s own claim is not taken at face value); this run was configured not to accept stance updates',

  'confidence.title': 'Confidence before and after the rebuttal',
  'confidence.unit': '{{delta}} pts',

  'usage.desc':
    'This section made {{calls}} model calls (failed attempts included) · {{input}} input tokens · {{output}} output tokens',
  'usage.hint': ' (token usage was not fully reported, so the real cost may be higher than shown)',
  'threshold.error':
    'The vote-change threshold could not be read from config; this run used the built-in default ({{source}}).',

  /* ---------------- 只读分享 ---------------- */
  'share.cta': 'Share',
  'share.badge': 'Public link',
  'share.title': 'Read-only share link',
  'share.desc':
    'Send one link to a co-founder or your team — <emph>they do not need an account to open it</emph>. Anyone who has the link can read it, so do not post it publicly.',
  'share_visible.label': 'They can see',
  'share_item_report.label': '· The full report (summary, priority fixes, each persona’s view, consensus and disagreements)',
  'share_item_meta.label': '· The title and task type of this review',
  'share_item_calibration.label': '· When it ran, and the calibration metrics',
  'share_hidden.label': 'They cannot see',
  'share_item_account.label': '· Your account or email address',
  'share_item_cost.label': '· What this review cost, or its token usage',
  'share_item_material.label': '· The materials you uploaded',
  'share.aria': 'Share link',
  'share_create.cta': 'Create share link',
  'share_revoke.cta': 'Revoke',
  'share.hint':
    'Revoking kills the link immediately — even people who already opened it lose access. Sharing again creates a new link.',
  'share.error': 'Could not create the share link',
  'share_revoke.error': 'Could not revoke the link',
  'share_copy.error': 'The browser refused clipboard access — please select the link above and copy it manually',

  /* ---------------- HTML 可视化版本 ---------------- */
  'html.cta': 'HTML report',
  'html.aria': 'HTML report',
  'html.tooltip': 'The HTML version is still being generated',
  'html.empty': 'The backend did not return an HTML version of this report, and did not say why.',
  'html.error': 'Could not fetch the HTML version: {{reason}}',
  'html.desc':
    'There is no HTML version of this report: {{reason}} The web view above and the JSON / Markdown exports are unaffected.',

  /* ---------------- 执行摘要 ---------------- */
  'summary.title': 'Release risk: {{risk}}',
  'summary_risk_missing.desc':
    'This report gives no release-risk level (the value it returned, “{{raw}}”, is not one we recognise). We are not going to guess one for it.',
  'summary_risk_absent.desc':
    'This report gives no release-risk level (the executive summary has no release_risk field). We are not going to guess one for it.',
  'summary_stance.label': 'Panel’s prevailing stance',
  'summary_evidence.label': 'Evidence strength',
  'summary_consensus.label': 'Shared issues / raised by one persona only',
  'summary_consensus.hint': 'Counted as shared when ≥{{min}} of {{total}} personas raised it independently',

  /* ---------------- 立场分布 ---------------- */
  'stance.title_one': 'Stance distribution ({{count}} persona)',
  'stance.title_other': 'Stance distribution ({{count}} personas)',
  'stance.empty': 'No persona stances to show',
  'stance.value': 'No stance given',

  /* ---------------- 校准指标 ---------------- */
  'calibration.title': 'Calibration',
  'calibration.success': 'Calibration passed',
  'calibration.error': 'Calibration below the bar — treat the conclusions with care',
  'calibration.empty': 'No calibration check was run for this review',

  /* ---------------- 优先修复项 ---------------- */
  'fixes.title': 'Priority fixes',
  'fix_why.label': 'Why it matters',
  'fix_suggestion.label': 'Suggested fix',
  'fix_personas.label': 'Raised by',

  /* ---------------- 人格视角 ---------------- */
  'personas.title': 'Persona views',
  'persona_issues.label': 'Key issues',
  'persona_evidence.label': 'Key evidence',

  /* ---------------- 议题共识明细 ---------------- */
  'consensus.title': 'Shared issues in detail',
  'consensus.hint': 'Shared = the same issue raised independently by ≥{{min}} of {{total}} personas',
  'consensus.badge': 'Shared',
  'consensus_single.badge': 'One persona',
  'consensus.meta_one': 'raised by {{count}}',
  'consensus.meta_other': 'raised by {{count}}',
  'consensus_unknown.meta': 'raiser count not recorded',
  'consensus.desc': 'Merged wordings: {{variants}}',

  /* ---------------- 主要分歧 ---------------- */
  'disagreements.title': 'Major disagreements',
  'disagreement.hint': 'Suggested resolution: {{text}}',

  /* ---------------- 信息缺口 / 下一步 ---------------- */
  'gaps.title': 'Information gaps',
  'next_test.title': 'Suggested next step with real people',
  'next_test_tasks.label': 'Tasks to test',
  'next_test_audience.label': 'Audience traits this panel covered',
  'next_test_materials.label': 'Materials to add',

  /* ---------------- 伦理合规 ---------------- */
  'compliance.title': 'Persona ethics compliance',
  'compliance.badge': '{{status}} · score {{score}}',

  /* ---------------- 评估评分卡 ---------------- */
  'evaluation.title': 'Evaluation scorecard',
  'evaluation_critical.title': 'Critical failures',
  'evaluation_overall.label': 'Overall score (out of 100)',
  'evaluation.meta': '{{passed}}/{{total}} dimensions passed',
  'evaluation_dimension.label': 'Per-dimension score (out of 3, pass mark 2)',
  'evaluation_dimension.empty': 'This dimension is not in the local table, so there is no description for it',
  'evaluation_dimension.value': '{{id}} (unknown dimension)',
  'evaluation.cta': 'Run evaluation',
  'evaluation_full.cta': 'Open full evaluation',
  'evaluation.error': 'Could not run the quality evaluation',
  'evaluation_run.error': 'Evaluation failed: {{reason}}',

  /* ---------------- 伦理报告 ---------------- */
  'ethics.title': 'Ethics report',
  'ethics_score.label': 'Ethics score',
  'ethics_stereotype.label': 'Stereotype risk',
  'ethics_violations.label_one': '{{count}} violation',
  'ethics_violations.label_other': '{{count}} violations',

  /* ---------------- 价值回填 ---------------- */
  'feedback.title': 'Was this report actually useful?',
  'feedback.desc':
    'We use this to measure adopted suggestions and changed decisions — we are not going to pass usage counts off as value.',
  'feedback_useful.cta': 'Useful',
  'feedback_useless.cta': 'Not helpful',
  'feedback_adopted.label': 'Which suggestions are you actually going to act on?',
  'feedback_fix.value': 'Suggestion {{index}}',
  'feedback_hours.label': 'Hours you expect to save',
  'feedback_pay.label': 'What this run was worth to you (USD)',
  'feedback_decision.label': 'This report changed a product or release decision of mine',
  'feedback.cta': 'Send feedback',
  'feedback.error': 'Could not send your feedback',
  'feedback.success': 'Recorded. The value metrics show up under “{{section}}”.',

  /* ---------------- 匿名体验版 ---------------- */
  'gated.subtitle': 'Preview report',
  'gated_summary.title': 'Executive summary',
  'gated_risk.label': 'Release risk',
  'gated_recommendation.label': 'Main recommendation',
  'gated_fix.title': 'Priority fixes (preview)',
  'gated.hint_one': '{{count}} more priority fix and {{notes}} more persona views are still hidden',
  'gated.hint_other': '{{count}} more priority fixes and {{notes}} more persona views are still hidden',
  'gated.desc':
    'Log in or sign up on this device and the report moves to your account automatically — the full text and your history are then available under “History”.',
  'gated.cta': 'Log in / Sign up to read it all',

  /* ---------------- Markdown 导出件 ---------------- */
  'md_banner.desc':
    'This report must not be shown or cited as “player research”, “user survey data”, or “how real players actually feel”.',
  'md_lang.value': 'Report body language: {{lang}}',
  'md_lang.empty': 'Report body language: not recorded (this report predates the field that records it)',
  'md_lang_zh.value': 'Chinese',
  'md_lang_en.value': 'English',
  'md_gate.title_one': '{{count}} persona’s output failed quality validation and is not counted below:',
  'md_gate.title_other': '{{count}} personas’ output failed quality validation and is not counted below:',
  'md_budget.hint':
    'Cross-examination did not run — this report has no such section, which does not mean the personas agreed.',
  'md_risk.title': 'Release risk: {{risk}}',
  'md_risk.empty': 'unknown',
  'md_stance.label': 'Prevailing stance: {{value}}',
  'md_evidence.label': 'Evidence strength: {{value}}',
  'md_fix.label': 'Suggested fix',
  'md_cross_exam_legacy.desc':
    'This report came from an older version; its cross-examination record is too old a format to recover rebuttals and vote changes from.',
  'md_cross_exam.label': 'How it ran: {{mode}}',
  'md_cross_exam.empty': 'There is no way to tell whether a rebuttal actually happened.',
  'md_cross_exam.hint': 'Engine note: {{text}}',
  'md_vote.label_one': 'Vote changes: {{count}}',
  'md_vote.label_other': 'Vote changes: {{count}}',
  'md_vote_none.label_one': 'Vote changes: {{count}} (neither side moved this round, which is a normal outcome)',
  'md_vote_none.label_other': 'Vote changes: {{count}} (neither side moved this round, which is a normal outcome)',
  'md_vote.empty': 'Vote changes: not applicable (no rebuttal round ran)',
  'md_failures.label_one': '{{count}} failure along the way: {{list}}',
  'md_failures.label_other': '{{count}} failures along the way: {{list}}',
  'md_cross_exam_skipped.desc':
    'No cross-examination ran: the per-run cost cap was reached, so it was skipped rather than spending more. That does not mean the personas agreed.',
  'md_cross_exam_absent.desc':
    'This report has no cross-examination record, and it does not say why (it may be a review tier with no rebuttal stage, or no opposing views worth debating came up). Please do not read it as “everyone agreed”.',
} satisfies Messages
