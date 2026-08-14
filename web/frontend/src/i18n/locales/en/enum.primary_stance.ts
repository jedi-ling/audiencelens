// owner: agent-10。见 zh/enum.primary_stance.ts（这不是 stance_enum，那组永不翻译）。
// 用形容词而不是动词：这四个词描述的是这位人格**处在什么立场上**，
// 不是他做了什么动作。"Advocate / Block" 读起来像按钮，会被当成可点的操作。
import type { Messages } from '@/i18n/types'

export default {
  advocate: 'Supportive',
  neutral: 'Neutral',
  skeptic: 'Skeptical',
  blocker: 'Opposed',
} satisfies Messages
