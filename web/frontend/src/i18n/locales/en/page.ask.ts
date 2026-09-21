/**
 * 对话评审页（/ask）。owner: agent-2，与 zh/page.ask.ts 同一个人。
 * 分工与「哪些中文故意不抽」见 zh 侧的文件头，那里是唯一一份说明，不在这里重复。
 *
 * 英文侧的两条：
 *   · 带 {{count}} 的 key 必须同时有 _one 和 _other（i18n:check 卡这条）。
 *     调用方永远只写逻辑 key，后缀由 Intl.PluralRules 选（契约 D9）。
 *   · aria-label 里的「」一律改成 “”（U+201C/201D），不要把中文书名号带进英文界面（契约 6.9）。
 */
import type { Messages } from '@/i18n/types'

export default {
  // ---- 页面骨架 ----
  'meta.title': 'Chat review',
  'header.title': 'Chat review',
  'header.desc': 'Describe what you want reviewed — the panel takes it from there',
  'sidebar_collapse.aria': 'Collapse the history sidebar',
  'sidebar_collapse.tooltip': 'Collapse the history sidebar',
  'sidebar_expand.aria': 'Expand the history sidebar',
  'sidebar_expand.tooltip': 'Expand the history sidebar',

  // ---- 开场白与示例 ----
  'greeting.value':
    "Hi — tell me what you'd like reviewed. A page, a piece of copy, a product concept, anything works.",
  // 跟着 zh 改回原文案「从一句话开始」，见 zh 侧注释。
  'examples.title': 'Start with one sentence',
  'examples.hint': 'Or just describe what you want reviewed in the box below',

  /* ---------------- 待验证追踪卡 ---------------- */
  'tracking.title_one': '{{count}} prediction awaiting verification',
  'tracking.title_other': '{{count}} predictions awaiting verification',
  'tracking.meta_one': '{{count}} unverified · oldest on record {{days}} days',
  'tracking.meta_other': '{{count}} unverified · oldest on record {{days}} days',
  'tracking.hint':
    'What you record here shapes the next review: findings a real playtest has refuted stop being carried into this project’s review context.',
  'tracking_unnamed.label': 'Unnamed project',
  'tracking_more.title': '{{total}}+ predictions awaiting verification',
  'verify_nudge.hint':
    'This project still has {{total}} unverified predictions — record their outcomes first, and this review will stop repeating findings a playtest has already refuted.',
  'verify_nudge.cta': 'Record now',

  /* 对话链路的高级选项 */
  'advanced.label': 'Advanced',
  'wide_screen.badge': 'Two-tier',
  'wide_screen.tooltip':
    'Every persona in the pack skims the materials in one cheap short call first; the deep-review panel is then picked by disagreement signal. Adds one cheap-tier round, itemised separately in the report.',
  'adaptive.badge': 'Adaptive panel',
  'adaptive.tooltip':
    'Starts small and adds personas by marginal value, stopping below the threshold instead of filling the tier quota. The expansion score is an explainable heuristic, not measured information gain.',
  'examples.cta': 'Try an example',
  /* 这三条点一下就当作用户消息发出去，所以写的是英文用户真会打出来的话，
     不是中文句子的逐字对应。 */
  'example_pricing.value': "Review this product's pricing page — will people think it's too expensive?",
  'example_onboarding.value': "Here's our onboarding flow. Would users drop off partway through?",
  'example_pitch.value': 'This is my startup application — go through it the way an investor would.',

  // ---- 未配置 Key 的软拦横幅 ----
  'no_key.title': 'Add an API key first',
  'no_key.desc': 'A review calls a real model, so nothing can start until a key is configured.',
  'no_key.cta': 'Add one in Settings',

  'count.credits_remaining_one': '{{count}} review credit left',
  'count.credits_remaining_other': '{{count}} review credits left',
  'credits_zero.hint': 'Out of review credits — redeem a CDK code or add your own API key to keep going',
  'credits.cta': 'Redeem a code',

  // ---- 附件：拖拽、预览、随消息发送 ----
  'drop.hint': 'Drop to upload a screenshot or file',
  'attach.hint': 'Drag files into the chat, or paste a screenshot with Ctrl+V',
  'attachment_preview.tooltip': 'Click to enlarge',
  'attachment_remove.aria': 'Remove {{filename}}',
  'attachment_image.aria': 'Attached image {{index}}',
  'attachment_note_review.hint_one':
    '{{count}} image will be sent with the review to a vision-capable model',
  'attachment_note_review.hint_other':
    '{{count}} images will be sent with the review to a vision-capable model',
  'attachment_note_follow_up.hint_one':
    '{{count}} image will be sent with your follow-up to a vision-capable model',
  'attachment_note_follow_up.hint_other':
    '{{count}} images will be sent with your follow-up to a vision-capable model',
  'attachment_limit.error_one': 'You can attach at most {{count}} image — remove it before uploading more',
  'attachment_limit.error_other': 'You can attach at most {{count}} images — remove a few before uploading more',
  'preview_close.aria': 'Close preview',

  // ---- 输入区 ----
  'upload.aria': 'Upload a screenshot or file',
  'upload.tooltip':
    'Upload a screenshot, demo image or file (images go to the model as multimodal material)',
  'upload.error': '“{{filename}}” failed to upload: {{detail}}',
  'skill_picker.aria': 'Choose a skill',
  'skill_picker.tooltip': "Pick a skill — don't wait for the AI to guess, name the angle yourself",
  'skill_quota.badge_one': '{{count}} free use left',
  'skill_quota.badge_other': '{{count}} free uses left',
  'skill_quota.empty': 'No free uses left',
  'skill_quota.hint':
    "Couldn't load your remaining free uses. You can still pick the skill — whether it counts against the quota is decided by the server when the review is created.",
  'type_picker.aria': 'Choose a review type',
  'type_picker.tooltip': "Pick the review type — name it yourself instead of letting the AI guess",
  'type_picker.placeholder': 'Search review types…',
  'input.aria': 'Review input',
  'input.placeholder': 'Tell me what you want reviewed… (Enter to send, Shift+Enter for a new line)',
  'input_follow_up.placeholder': 'Ask {{label}}… (Enter to send)',
  'send.aria': 'Send',

  // ---- 钉住的技能 / 类型 / 项目 ----
  'pinned_skill.badge': 'Skill · {{name}}',
  'pinned_skill.aria': 'Clear the pinned skill',
  'pinned_type.badge': 'Type · {{name}}',
  'pinned_type.aria': 'Clear the pinned type',
  'pinned_project.badge': 'Project · {{name}}',
  'pinned_project.aria': 'Remove from project',
  'pinned_project.tooltip': 'Move back to Ungrouped',
  'project_select.aria': 'Move to a project',
  'project_select.placeholder': 'Move to project…',
  'project_select.empty': 'No projects yet — create one in the sidebar',

  // ---- 追问模式 ----
  'follow_up.badge': 'Following up · {{label}}',
  'follow_up.label': 'this report',
  'follow_up.cta': 'Follow up',
  'follow_up.tooltip': 'Keep asking right here in this chat — no need to open the report',
  'follow_up.error': "Your follow-up didn't go through. Try again.",
  'follow_up_exit.aria': 'Leave follow-up mode',
  'follow_up_report.cta': 'Follow up on this report',

  // ---- 侧栏：对话树与项目 ----
  'new_conversation.cta': 'New chat',
  'new_project.cta': 'New project',
  'new_project.confirm': 'Create',
  'new_project.placeholder': 'Name this project…',
  'projects.loading': 'Loading projects…',
  'project.empty': 'Drag a chat here',
  'conversation_untitled.label': 'Untitled chat',
  'ungrouped.title': 'Ungrouped',
  'ungrouped.empty': 'No ungrouped chats',
  'legacy.title': 'Earlier reviews',
  'login_required.title': 'Sign in to see your review history',
  'login_required.desc': 'Reviews you run while signed out are not attached to any account',
  'login_required.cta': 'Sign in',
  'sidebar_empty.title': 'No chats or reviews yet',
  'sidebar_empty.desc': 'Start a new chat and it will show up here',

  // ---- 侧栏：改名 / 删除 / 拖拽的结果与二次确认 ----
  'project_rename.aria': 'Rename “{{name}}”',
  'project_rename.tooltip': 'Rename',
  'project_delete.aria': 'Delete “{{name}}”',
  'project_delete.tooltip': 'Delete project (its chats move back to Ungrouped)',
  'project_delete_confirm.aria': 'Confirm deleting project “{{name}}”',
  'project_delete_confirm.confirm_one':
    'Delete project “<name>{{name}}</name>”?<br/>The {{count}} chat inside moves back to “Ungrouped” — it is not deleted.',
  'project_delete_confirm.confirm_other':
    'Delete project “<name>{{name}}</name>”?<br/>The {{count}} chats inside move back to “Ungrouped” — they are not deleted.',
  'project_delete_confirm.cta': 'Delete project',
  'review_delete.aria': 'Delete “{{title}}”',
  'review_delete.tooltip': 'Delete this review (you will be asked to confirm)',
  'review_delete_confirm.aria': 'Confirm deleting “{{title}}”',
  'review_delete_confirm.confirm':
    'Delete “<name>{{title}}</name>”?<br/>The report, every persona note and all follow-up messages go with it. This cannot be undone.',

  // ---- 失败态 ----
  'history.error': "Couldn't load your history",
  'history_delete.error': 'Delete failed: {{detail}}',
  'history_delete.hint': 'check your connection and try again',
  'project_create.error': "Couldn't create the project",
  'project_rename.error': "Couldn't rename it",
  'project_delete.error': "Couldn't delete the project",
  'conversation_move.error': "Couldn't move the chat",
  'parse.error': "I didn't catch that — say it again?",
  'create.error': "Couldn't start the review",
  'need_key.cta': 'Add an API key',

  // ---- 落库用的消息文本（写入那一刻冻结语言，见 zh 侧注释）----
  'persisted_review.value': '[Review created]',
  'persisted_confirm.value': '[Review plan confirmed: {{taskType}}]',
  'persisted_confirm.empty': 'not set',
  'restored_review.label': '(past review)',

  // ---- 意图解析结果 ----
  'clarify.hint': 'Could you be a bit more specific?',
  'confirm.label': "Got it — here's what you want",
  'mode.badge': 'Depth · {{mode}}',
  'pack.badge': 'Panel · {{pack}}',
  'skill.badge': 'Skill · {{name}}',
  'project.badge': 'Project · {{name}}',
  'personas.label': 'Chosen personas (click × to drop one; drop them all to go back to automatic selection)',
  'persona_restore.aria': 'Restore {{name}}',
  'persona_restore.tooltip': 'Click to restore',
  'persona_remove.aria': 'Remove {{name}}',
  'persona_remove.tooltip': 'Click to remove',
  'confidence.label': 'Match confidence',
  'confidence.value': '{{level}} ({{percent}})',
  'confidence_high.label': 'High',
  'confidence_medium.label': 'Medium',
  'confidence_low.label': 'Low',
  'rule_parse.hint':
    'No API key configured, so this was parsed by rules and the task type may be off. Add a key and the model does the parsing instead.',
  'submit.cta': 'Convene the panel →',
  'submit.pending': 'Convening…',
  'skill_degraded.value':
    '{{reason}} — redeem a CDK code to keep using it, or add your own API key in Settings (BYOK is not subject to this limit).',

  // ---- 评审卡片：进度与连接交代 ----
  'progress.pending': 'The panel is reviewing…',
  'progress.hint': "You can keep chatting while it runs — I won't interrupt you.",
  'sync_failed.error_one':
    "Can't sync review progress ({{count}} failed attempt so far), retrying automatically. The review keeps running on the server either way.",
  'sync_failed.error_other':
    "Can't sync review progress ({{count}} failed attempts so far), retrying automatically. The review keeps running on the server either way.",
  'realtime_unavailable.hint':
    'The realtime connection is unavailable, so progress is polled every {{seconds}} seconds instead. It still updates, just a little slower.',
  'realtime_reconnecting.hint':
    'The realtime connection dropped and is reconnecting; progress is polled in the meantime.',
  'stalled.hint':
    'No new progress for {{idle}} seconds — still working (one persona may be on a long stretch of reasoning). Status is re-checked every {{seconds}} seconds.',
  'review_failed.title': 'The review failed',
  'review_failed.error': 'Review failed',

  // ---- 评审卡片：报告摘要 ----
  'report_card.title': 'Review report',
  'report_card.loading': 'Loading the report…',
  'report_card.empty': 'The report is empty (no persona notes came back)',
  'report_card.cta': 'View summary',
  'count.fixes_one': '{{count}} fix',
  'count.fixes_other': '{{count}} fixes',
  'count.personas_one': '{{count}} persona',
  'count.personas_other': '{{count}} personas',
  'token.tooltip': 'Input {{input}} · output {{output}} tokens',
  'token.unit': '{{value}} tok',
  'cost.value': 'Spent {{amount}}',

  // ---- 报告弹窗 ----
  'report_modal.subtitle': 'Quick summary',
  'report_modal.link': 'Full report page',
  'conclusion.title': 'Verdict',
  'evidence.badge': 'Evidence · {{quality}}',
  'count.priority_fixes_one': 'Priority fix · {{count}}',
  'count.priority_fixes_other': 'Priority fixes · {{count}}',
  'fix.hint': 'Suggested fix: {{text}}',
  'count.persona_notes_one': 'Persona brief · {{count}}',
  'count.persona_notes_other': 'Persona briefs · {{count}}',
  'count.issues_one': ' · {{count}} issue',
  'count.issues_other': ' · {{count}} issues',
  'stance.empty': 'No stance',
  'stance_row.empty': '—',
  'persona_chat.cta': 'Talk to them',
  'count.disagreements_one': 'Major disagreement · {{count}}',
  'count.disagreements_other': 'Major disagreements · {{count}}',
  'disagreement_stance.value': '{{persona}}: {{stance}}',
  'disagreement_evidence.value': ' ({{evidence}})',
  'disagreement.hint': 'How to resolve: {{text}}',
  'count.information_gaps_one': 'Information gap · {{count}}',
  'count.information_gaps_other': 'Information gaps · {{count}}',

  // ---- 匿名体验版的截断提示 ----
  'gated.hint_one': '{{count}} more character is hidden',
  'gated.hint_other': '{{count}} more characters are hidden',
  'gated.cta': 'Sign in to read the full answer',
} satisfies Messages
