/**
 * CalibrationGauge 的读数与脚注。owner: agent-10。
 * 落在 common.* 的理由与 common.persona_card.ts 相同（域是闭集）。
 *
 * 脚注三分支对应组件里已有的三种事实，翻译时不要把它们揉成一句：
 *   missing            → 这项指标**根本没算出来**（不是 0，也不是不合格）
 *   passLine 未定义    → 这项指标没有已定义的合格线，组件刻意不表态、只用中性色
 *   passLine 有值      → 把线的位置如实说出来，用户才看得懂 35% 为什么是绿的
 * 组件文件头的注释记录了这三档是怎么来的（视角覆盖度 0.35 合格却被涂成红色的
 * 那次事故），改文案前先读它。
 */
import type { Messages } from '@/i18n/types'

export default {
  // 指标没算出来时的大号读数。破折号在中英文里同形，i18n:check 的
  // "en 不许与 zh 逐字相同"只对含汉字的值生效，所以这条两侧写一样是合法的。
  // 它仍然要进 key 表：写死在 tsx 里的话，将来想改成 "N/A" 就得改代码。
  'readout.empty': '—',

  'missing.hint': '这项没算出来',
  'no_pass_line.hint': '无合格线',
  // {{value}} 是 formatPercent() 的产物，已含 % 号。
  'pass_line.value': '合格线 {{value}}',
} satisfies Messages
