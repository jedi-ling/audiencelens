// owner: batch-0。见 zh/error.store.ts 的文件头（含"已翻好的字符串存进 store"的已知限制）。
import type { Messages } from '@/i18n/types'

export default {
  bootstrap: 'Could not reach the backend',
  review_list: 'Could not load your reviews',
  examples: 'Could not load the examples',
  personas: 'Could not load the personas',
} satisfies Messages
