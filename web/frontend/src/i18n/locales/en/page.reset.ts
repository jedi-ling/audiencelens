// owner: agent-11。见 zh/page.reset.ts 的文件头。
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Set a new password',

  'header.title': 'Set a new password',

  'no_token.error': 'This link is incomplete — the reset token is missing.',
  'no_token.link': 'Request a new reset link',

  'password.label': 'New password (at least {{min}} characters)',
  'password.placeholder': '········',
  'confirm.label': 'Type it again',
  'confirm.placeholder': '········',

  'submit.cta': 'Reset password',
  'submit.error': 'Could not reset your password',

  'done.success': 'Your password has been reset.',
  'done.hint': 'Sign in with your new password.',
  'done.cta': 'Go to sign in',
} satisfies Messages
