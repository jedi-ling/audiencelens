/**
 * ReportCharts（StancePie / ScorecardBars）的无障碍标签。
 *
 * 落在 common.* 而不是 page.report.*：理由与 common.calibration_gauge.ts /
 * common.persona_radar.ts 相同——组件在 components/ 下，谁都可以复用它，
 * 文案不该锁死在某一页的资源文件里（域是闭集，组件只能落 common）。
 *
 * 为什么拆成「整句 + 逐项」两条 key 而不是在 tsx 里拼字符串：
 * 原来的写法是 `立场分布: ${data.map(d => `${d.name} ${d.value}人`).join(', ')}`，
 * 里面的「人」和冒号都是**中文字面量**，英文界面上读屏软件会念出
 * "Stance distribution" 之外的一串中文量词。逐项单独成 key 之后，
 * 英文侧还能顺带把量词做成复数（1 persona / 2 personas），
 * 拼字符串是做不到这件事的（契约 D9 / §6.9）。
 */
import type { Messages } from '@/i18n/types'

export default {
  // {{items}} 是逐项文案用 common.ui.list_separator 连起来的结果。
  'stance_pie.aria': '立场分布：{{items}}',
  'stance_pie_item.value': '{{name}} {{count}} 人',

  'scorecard_bars.aria': '评估维度得分：{{items}}',
  // 分子分母都是数，不是可数名词，所以这条不挂复数。
  'scorecard_bars_item.value': '{{name}} {{score}}/{{max}}',
} satisfies Messages
