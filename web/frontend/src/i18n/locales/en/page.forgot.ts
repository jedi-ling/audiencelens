// owner: agent-11。见 zh/page.forgot.ts 的文件头（sent.success 的含糊措辞是防邮箱枚举，不是没写清楚）。
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Reset password',

  'header.title': 'Reset your password',
  'header.desc': 'Enter the email you signed up with and we will send you a reset link',

  'email.label': 'Account email',
  'email.placeholder': 'you@example.com',

  'submit.cta': 'Send reset link',
  'submit.error': 'Could not send the reset link',

  'sent.success': 'If that email is registered, the reset link is on its way.',
  'sent.hint':
    'The link expires in 60 minutes and works only once. If it does not arrive, check your spam folder.',
  'sent.link': 'Back to sign in',

  'signin.hint': 'Remembered it? <link>Sign in</link>',
} satisfies Messages
