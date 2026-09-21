// owner: agent-11。见 zh/page.register.ts 的文件头。
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Sign up',

  'header.title': 'Create your account',
  'header.desc':
    'You can try a review without an account — signing up is what unlocks the full report and your history',

  'name.label': 'Display name (optional)',
  'name.placeholder': 'What should we call you?',
  'email.label': 'Email',
  'email.placeholder': 'you@example.com',
  'password.label': 'Password (at least {{min}} characters)',
  'password.placeholder': '········',

  'submit.cta': 'Create account',
  'submit.pending': 'Creating your account…',
  'submit.error': 'Could not create your account',

  'terms.consent':
    'By signing up you agree to our <terms>Terms of Service</terms> and <privacy>Privacy Policy</privacy>',

  'guest_notice.title': 'You are a guest on this browser',
  'guest_notice.desc':
    'Signing up here creates a new account rather than promoting your current guest: the guest reviews and remaining credits on this browser will not come with you. To keep them, <link>bind an email in Settings</link> instead — that path keeps the same user_id, so your history and credits stay where they are.',

  'signin.hint': 'Already have an account? <link>Sign in</link>',
} satisfies Messages
