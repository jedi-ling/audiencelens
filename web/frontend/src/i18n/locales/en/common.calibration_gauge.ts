// owner: agent-10。见 zh/common.calibration_gauge.ts（三分支不许揉成一句）。
import type { Messages } from '@/i18n/types'

export default {
  // 与 zh 侧同形，理由见 zh 侧注释（破折号不是文案，是"这里没有数"的排版符号）。
  'readout.empty': '—',

  // "Not measured" 而不是 "N/A"：N/A 读起来像"这项不适用"，
  // 而真相是这项指标本轮根本没被算出来——两者对用户的含义完全不同。
  'missing.hint': 'Not measured this run',
  'no_pass_line.hint': 'No pass mark defined',
  'pass_line.value': 'Pass mark {{value}}',
} satisfies Messages
