// owner: agent-1（见 zh/enum.verdict.ts 的文件头）
import type { Messages } from '@/i18n/types'

export default {
  pass: 'Pass',
  // "Fail" 而不是 "Failed"：后者会被读成"这一步跑挂了"，
  // 而这里说的是"没达到合格线"，两件事在本仓其它地方是分开的。
  fail: 'Fail',
} satisfies Messages
