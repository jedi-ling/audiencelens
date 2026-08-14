// owner: agent-11。见 zh/page.verify.ts 的文件头。
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Email verification',

  'pending.loading': 'Verifying…',

  'ok.title': 'Email verified',
  'ok.cta': 'Start a review',

  'fail.title': 'Verification did not go through',
  // 中文原文用「」包着"设置"，英文侧用引号而不是中文书名号（契约 6.9）。
  'fail.hint':
    'A verification link expires after 24 hours and works only once. You can send a new one from “Settings”.',
  'fail.link': 'Go to settings',

  'no_token.error': 'This link is incomplete — the verification token is missing',
  'confirm.error': 'Could not verify your email',
} satisfies Messages
