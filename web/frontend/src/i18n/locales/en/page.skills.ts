// owner: 集成验收 agent（见 zh/page.skills.ts 的文件头，含"为什么这份是补做的"）
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Skills',

  'header.title': 'Skills',
  // 与 zh 同理：只承诺"换一种视角"这件确实发生的事，不说"差异化的评审策略和角色配置"。
  'header.subtitle':
    'Pick a review skill. The skill decides what angle the reviewers read your material from — you still choose how many of them and which roles when you set the review up',

  'list_error.title': 'Could not load your skills',
  'list_error.desc':
    '{{reason}} — this does not mean your skills were turned off, only that the list did not come back this time. Try again.',
  'list_error.cta': 'Reload',

  'list.empty': 'No review skills are available on this account',

  'card_task_types.label_one': 'Works with {{count}} task type',
  'card_task_types.label_other': 'Works with {{count}} task types',
  'card_use_cases.label': 'Typical uses',
  'card.cta': 'Start a review with this skill',
  'card_disabled.hint':
    'This skill is not wired into the review pipeline yet: starting a review from here would not change how the review runs, so the entry point stays closed until it actually does something.',
} satisfies Messages
