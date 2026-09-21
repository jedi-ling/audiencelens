// owner: agent-11。见 zh/page.login.ts 的文件头。
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Sign in',

  'header.title': 'Sign in',
  'header.desc': 'Sign in to read full review reports and keep your review history',

  'email.label': 'Email',
  'email.placeholder': 'you@example.com',
  'password.label': 'Password',
  'password.placeholder': '········',

  'forgot.link': 'Forgot your password?',

  'submit.cta': 'Sign in',
  'submit.pending': 'Signing in…',
  'submit.error': 'Could not sign you in',

  'signup.hint': 'No account yet? <link>Create one</link>',

  'qq_error.error': 'QQ sign-in did not complete',
  // 原因串是后端中文原文，这里只说清楚它是什么，不假装它已经被翻译过。
  'qq_error.hint': 'Reason reported by the server (in Chinese): {{reason}}',

  'guest_notice.title': 'You are a guest on this browser',
  'guest_notice.desc':
    'Signing in to another account switches you over, and the guest reviews and remaining credits on this browser do not come with you. To keep them, first <link>bind an email in Settings</link> so this guest becomes a full account — binding keeps the same user_id, so your history and credits stay where they are.',

  'oauth_divider.label': 'or',
  'qq.cta': 'Sign in with QQ',
} satisfies Messages
