/**
 * ReportPage 里仅有的两个 recharts 图表，抽出来单独成 chunk。
 *
 * 为什么值得抽：recharts（PolarChart chunk，约 256KB min）此前由 ReportPage
 * 顶部静态 import，于是**打开任何一份报告**都要先下完整个图表库才能渲染正文
 * ——而正文（风险评估、优先修复项、争议点）全是纯文本，一个像素的图都不需要。
 * 抽出后 ReportPage 主体先渲染，两张图各自在滚到时补上；图表 chunk 加载期间
 * 占位高度与真实图一致，不跳版。
 *
 * 边界约定：这两个组件只收**已经算好的数据**（stanceData / rows），不收
 * report 原始对象——数据加工留在 ReportPage，这里只管画。否则 EVALUATION_
 * DIMENSIONS 之类的常量会被拖进这个 chunk，两边各一份。
 */
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'
import { t } from '@/i18n/runtime'

const TOOLTIP_STYLE = {
  backgroundColor: '#1c1c1e',
  border: '1px solid #38383a',
  borderRadius: '12px',
  fontSize: '12px',
  boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
} as const

export interface StanceDatum {
  name: string
  value: number
  color: string
}

/** 每段外侧的直接标签："立场 人数"。
 *
 *  为什么必须有：环形图是"任意两段互相比对"的场景（读者拿一段去对图例），
 *  这种场景下经验证只有前 3 个槽位能过色盲/正常视力区分闸，第 4 槽起
 *  #d55181↔#199e70 的 ΔE 只有 1.6。直接标签是规范要求的第二重编码——
 *  有了它，身份就不再由颜色独自承担，段数才能安全地超过 3 段。
 *  文字一律用 text token 色（不用序列色）：颜色属于色块，文字属于文字。 */
function sliceLabel(props: {
  cx?: number; cy?: number; midAngle?: number; outerRadius?: number
  name?: string; value?: number
}) {
  const { cx = 0, cy = 0, midAngle = 0, outerRadius = 0, name = '', value } = props
  const rad = Math.PI / 180
  const r = outerRadius + 14
  const x = cx + r * Math.cos(-midAngle * rad)
  const y = cy + r * Math.sin(-midAngle * rad)
  return (
    <text
      x={x}
      y={y}
      // 落在圆心左侧的标签右对齐、右侧的左对齐，标签才不会压到图上
      textAnchor={x > cx ? 'start' : 'end'}
      dominantBaseline="central"
      fill="#c4cce0"
      fontSize={11}
    >
      {`${name} ${value ?? ''}`}
    </text>
  )
}

/** 立场分布环形图。图例由 ReportPage 自己画（纯 DOM，不需要图表库）。 */
export function StancePie({ data }: { data: StanceDatum[] }) {
  // 逐项各走一条 key 再连起来，不在这里拼中文量词：原来的 `${d.value}人`
  // 在英文界面上会让读屏念出一串中文，而拆开之后英文侧还能做单复数。
  const ariaLabel = t('common.report_charts.stance_pie.aria', {
    items: data
      .map((d) => t('common.report_charts.stance_pie_item.value', { name: d.name, count: d.value }))
      .join(t('common.ui.list_separator')),
  })
  return (
    // 高度从 220 提到 260、半径留出外圈标签的位置——标签被裁掉等于没加。
    <ResponsiveContainer width="100%" height={260}>
      <PieChart role="img" aria-label={ariaLabel}>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={38}
          outerRadius={62}
          // 段间留缝用描边色=底色实现（规范：2px 表面色间隙），
          // 不再靠 paddingAngle 撑出的空白——那个缝在深色底上会糊在一起。
          paddingAngle={2}
          dataKey="value"
          label={sliceLabel}
          labelLine={false}
          isAnimationActive={false}
        >
          {data.map((d, i) => (
            // 不再用 fillOpacity：半透明会把色值冲淡、偏离验证过的 hex，
            // 那套色盲/对比度的数学就全作废了。填实色 + 底色描边分隔。
            <Cell key={i} fill={d.color} stroke="#1c1c1e" strokeWidth={2} />
          ))}
        </Pie>
        <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: '#ffffff' }} />
      </PieChart>
    </ResponsiveContainer>
  )
}

export interface ScorecardBarDatum {
  name: string
  score: number
  fill: string
}

/** 评估评分卡条形图。maxScore 从调用方传（DIMENSION_MAX_SCORE 留在 ReportPage）。 */
export function ScorecardBars({ data, maxScore }: { data: ScorecardBarDatum[]; maxScore: number }) {
  const ariaLabel = t('common.report_charts.scorecard_bars.aria', {
    items: data
      .map((d) =>
        t('common.report_charts.scorecard_bars_item.value', {
          name: d.name,
          score: d.score,
          max: maxScore,
        }),
      )
      .join(t('common.ui.list_separator')),
  })
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} role="img" aria-label={ariaLabel}>
        <CartesianGrid strokeDasharray="3 3" stroke="#38383a" />
        <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#86868b' }} />
        <YAxis domain={[0, maxScore]} ticks={[0, 1, 2, 3]} tick={{ fontSize: 10, fill: '#86868b' }} />
        <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: '#ffffff' }} />
        <Bar dataKey="score" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
