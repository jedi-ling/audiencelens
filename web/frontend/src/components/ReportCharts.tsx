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

/** 立场分布环形图。图例由 ReportPage 自己画（纯 DOM，不需要图表库）。 */
export function StancePie({ data }: { data: StanceDatum[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={40}
          outerRadius={70}
          paddingAngle={3}
          dataKey="value"
        >
          {data.map((d, i) => (
            <Cell key={i} fill={d.color} fillOpacity={0.8} stroke={d.color} strokeWidth={1} />
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
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5ea" />
        <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#86868b' }} />
        <YAxis domain={[0, maxScore]} ticks={[0, 1, 2, 3]} tick={{ fontSize: 10, fill: '#86868b' }} />
        <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: '#ffffff' }} />
        <Bar dataKey="score" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
