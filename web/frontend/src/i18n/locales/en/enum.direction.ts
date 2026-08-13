// owner: agent-1（见 zh/enum.direction.ts 的文件头）
// 小写：它出现在指标名后面的括号里（"Wishlist rate (up)"），大写会读成一个标题。
import type { Messages } from '@/i18n/types'

export default {
  increase: 'up',
  decrease: 'down',
} satisfies Messages
