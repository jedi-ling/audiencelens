// owner: agent-10。见 zh/common.persona_card.ts。
// 英文把数值放前面（"78% confidence"），这正是不能把"置信度"和数字拆成两条 key
// 的原因——拆了语序就锁死在中文那一种了。
import type { Messages } from '@/i18n/types'

export default {
  'confidence.value': '{{value}} confidence',
} satisfies Messages
