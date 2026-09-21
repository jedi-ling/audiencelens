// 见 zh/common.report_charts.ts 的文件头（为什么拆成「整句 + 逐项」两条 key）。
import type { Messages } from '@/i18n/types'

export default {
  'stance_pie.aria': 'Stance distribution: {{items}}',
  // 中文那条的量词是「人」，英文这里必须是可数复数——正是拼字符串做不到、
  // 而拆出逐项 key 之后白得的那件事。
  'stance_pie_item.value_one': '{{name}} {{count}} persona',
  'stance_pie_item.value_other': '{{name}} {{count}} personas',

  'scorecard_bars.aria': 'Dimension scores: {{items}}',
  'scorecard_bars_item.value': '{{name}} {{score}}/{{max}}',
} satisfies Messages
