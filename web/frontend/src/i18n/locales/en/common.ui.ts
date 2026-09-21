// owner: batch-0（与 zh/common.ui.ts 同一个 owner）
import type { Messages } from '@/i18n/types'

export default {
  loading: 'Loading…',
  submitting: 'Submitting…',
  saving: 'Saving…',
  sending: 'Sending…',
  deleting: 'Deleting…',
  processing: 'Working…',

  empty: 'Nothing here yet',
  error: 'Something went wrong',
  unknown_error: 'That did not work',
  success: 'Done',
  copied: 'Copied',
  copy_failed: 'Could not copy',

  required_mark: 'Required',
  optional_mark: 'Optional',
  not_recorded: 'Not recorded',

  // 见 zh 侧：中英列表分隔符不同形，不能在 tsx 里 join 死。
  list_separator: ', ',

  language: 'Language',
  language_aria: 'Change interface language',
  language_hint: 'Changes the interface only — reports keep the language they were generated in',
} satisfies Messages
