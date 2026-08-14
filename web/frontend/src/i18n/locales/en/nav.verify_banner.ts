// owner: batch-0。见 zh/nav.verify_banner.ts 的文件头（四态各一条 key，不是插值）。
import type { Messages } from '@/i18n/types'

export default {
  // 带 count 的 key 在 en 侧必须同时有 _one 和 _other。
  // 调用方永远只写逻辑 key 'hint'，不写后缀——后缀是运行时按 Intl.PluralRules 选的。
  hint_one: 'Your email is not verified yet, so you get {{count}} review per day. Verify to unlock your full quota.',
  hint_other: 'Your email is not verified yet, so you get {{count}} reviews per day. Verify to unlock your full quota.',
  // reviews_limit 为 null 时用这条。不许拿 0 顶上去（见 zh 侧的注释）。
  hint_unknown:
    'Your email is not verified yet, so your daily review quota is reduced. Verify to unlock your full quota.',
  cta: 'Resend verification email',
  sending: 'Sending…',
  success: 'Sent — check your inbox and spam folder · tap to send again',
  error: 'Could not send — tap to retry',
} satisfies Messages
