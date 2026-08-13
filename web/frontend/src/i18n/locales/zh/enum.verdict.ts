/**
 * 二值判定的徽标文案。owner: agent-1（ReportPage）。
 *
 * 报告页有三处结构完全一样的"通过 / 未通过"（评估记分卡总分、单维度、伦理报告），
 * 三处的判定口径不同但**说法逐字相同**，所以共用一条 key，不各写一份。
 * 这不是 D10 意义上的"意思差不多就合并"：它们是同一个布尔值的同一句渲染。
 *
 * 刻意不叫 pass/failed：failed 在英文里读起来像"跑挂了"，
 * 而这里说的是"没达到合格线"。
 */
import type { Messages } from '@/i18n/types'

export default {
  pass: '通过',
  fail: '未通过',
} satisfies Messages
