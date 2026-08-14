import { useRef, useEffect, useState } from 'react'
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer, Legend, Text } from 'recharts'
import { t, missingMarker } from '@/i18n/runtime'
import { getLocale } from '@/i18n/locale'
import type { PlainMessageKey } from '@/i18n/keys.gen'
import type { BehaviorAxis } from '@/lib/mock-data'

/**
 * 轴键 → **key 不是文案**（模块级常量存文案的话，切语言不会重新求值，
 * 雷达图会一直停在打开页面时的那种语言）。
 */
const AXIS_KEYS: Record<string, PlainMessageKey> = {
  patience: 'enum.behavior_axis.patience',
  genre_literacy: 'enum.behavior_axis.genre_literacy',
  novelty_seeking: 'enum.behavior_axis.novelty_seeking',
  risk_tolerance: 'enum.behavior_axis.risk_tolerance',
  social_influence: 'enum.behavior_axis.social_influence',
  completion_drive: 'enum.behavior_axis.completion_drive',
  price_sensitivity: 'enum.behavior_axis.price_sensitivity',
  criticism_style: 'enum.behavior_axis.criticism_style',
  emotional_engagement: 'enum.behavior_axis.emotional_engagement',
  agency_preference: 'enum.behavior_axis.agency_preference',
  tolerance_for_ambiguity: 'enum.behavior_axis.tolerance_for_ambiguity',
  platform_loyalty: 'enum.behavior_axis.platform_loyalty',
}

/**
 * 轴名。查不到就**显式标记缺失**，不回落成后端的英文键。
 *
 * 这里原来写的是 `AXIS_LABEL_MAP[d.axis] ?? d.axis`——后端加一条新轴（或改了键名）
 * 时，雷达图上就会画出一圈 "novelty_seeking" 这样的下划线标识符，看起来像
 * "这个维度本来就叫这个名字"，没有任何人会发现是缺译。契约 D8 点名了这处，
 * 规定改成 ⟦missing:<locale>:<key>⟧：一条 grep、一条断言、一眼截图就能抓住。
 * **不要**因为"图上出现方括号不好看"把 `?? axis` 加回来。
 */
function axisLabel(axis: string): string {
  const key = AXIS_KEYS[axis]
  if (key === undefined) return missingMarker(`enum.behavior_axis.${axis}`, getLocale())
  return t(key)
}

/* ------------------------------------------------------------------ *
 * 轴名排版
 *
 * 12 条轴均分 360°，轴名沿圆周排，每条能用的横向空间只有
 * 「盒子半宽 − 轴名锚点半径」。recharts 的几何是写死的：
 *   maxRadius   = (size − margin 10) / 2
 *   outerRadius = 百分比 × maxRadius            （本组件原来给 70%）
 *   轴名锚点    = outerRadius + tickSize(默认 8)
 * 代进 120px 的人格卡片：maxRadius 55 → outerRadius 38.5 → 锚点 46.5，
 * 离盒子边只剩 13.5px ≈ 两个字母。
 *
 * 中文轴名（"平台忠诚度" 5 字）本来就已经在被 svg 裁边，只是裁掉的是外侧、
 * 看着像故意留白；换成英文（最长 "Emotional engagement" 20 字符）之后，
 * 一条轴名要横跨大半张图，顶部那三条（platform loyalty / patience /
 * genre literacy）纵向只差 0.134×半径 ≈ 6px，于是被裁剩的残段互相压在一起，
 * 读出来就是用户截图里的 "yaltyatienceenr"。
 *
 * 所以这里做三件事，且**只在这个组件里**做（不动全站设计系统）：
 *   1. 画轴名时把 outerRadius 从 70% 收到 55%、tickSize 从 8 收到 3，
 *      把省下来的半径让给轴名；
 *   2. 逐条算预算再截断（左右两侧看盒子边，顶底两条看邻轴，见 AxisTick），
 *      截断后挂 <title> 存全名；
 *   3. 预算连三个字母都放不下的尺寸（<140px 的卡片缩略图）干脆不画轴名——
 *      12 个三字母残根不是信息，是噪声。此时 outerRadius 保持 70%。
 *
 * 截断用 recharts 自己的 <Text width maxLines={1}>：它拿**真实字体度量**
 * （隐藏 DOM 节点测宽）做二分裁剪并补 '…'，所以中英文、任何字体都不用我们
 * 自己估字宽；而且它按词边界收，"Genre literacy" 截出来是 "Genre…"
 * 而不是 "Genre l…"。
 * ------------------------------------------------------------------ */

/** 低于这个宽度不画轴名（推导见上：120px 卡片只剩 ~13px 预算）。 */
const AXIS_LABEL_MIN_SIZE = 140
/** 画轴名时的外圈半径：让出 15% 给轴名。不画轴名时用 PLAIN_OUTER_RADIUS。 */
const LABELED_OUTER_RADIUS = '55%'
const PLAIN_OUTER_RADIUS = '70%'
/**
 * 轴名锚点离外圈多远（recharts 的 tickSize，默认 8）。
 * 收到 3 是白捡的 5px 预算：轴名往里挪 5px，横向轴（正左/正右那两条，
 * 预算最紧）就能多放一个词，而且刻度线本来就没描边、看不见。
 */
const AXIS_TICK_SIZE = 3
/** 轴名与盒子边之间留的安全距离，避免抗锯齿把最后一个像素蹭掉。 */
const AXIS_LABEL_PAD = 2
const AXIS_TICK_FILL = '#8e8e93'
const AXIS_FONT_FAMILY = 'Noto Sans SC'

interface AxisTickProps {
  /** 以下四个由 recharts cloneElement 注入，调用处不传。 */
  x?: number | string
  y?: number | string
  textAnchor?: 'start' | 'middle' | 'end' | 'inherit'
  verticalAnchor?: 'start' | 'middle' | 'end'
  payload?: { value?: unknown }
  /** 图表盒子宽度（= 高度），用来算每条轴名到边还剩多少像素。 */
  boxSize: number
  /** 轴条数。顶/底那两条轴名的可用宽度由**相邻轴**决定，不是由盒子边决定。 */
  axisCount: number
  labelFontSize: number
  labelsHidden: boolean
}

/**
 * 一条轴名。
 *
 * ⚠ 缺译标记 ⟦missing:…⟧ **既不截断也不隐藏**。
 * 截断会把它裁成 "⟦missin…"、隐藏会让它彻底消失——两种都是"悄悄不显示缺译"，
 * 正是纪律 2 和契约 D8 要防的那件事（axisLabel() 的注释里写了完整来由）。
 * 它显示出来必然很丑、还会被裁边，那是**要的效果**：一眼截图就能抓住。
 */
function AxisTick({
  x,
  y,
  textAnchor,
  verticalAnchor,
  payload,
  boxSize,
  axisCount,
  labelFontSize,
  labelsHidden,
}: AxisTickProps) {
  const label = String(payload?.value ?? '')
  const isMissing = label.startsWith('⟦')
  if (labelsHidden && !isMissing) return null

  const px = Number(x)
  const py = Number(y)
  const anchor = textAnchor ?? 'middle'
  // 左右两侧的轴名从锚点朝外长，能用多宽就是锚点到盒子边还有多远。
  //
  // 顶/底那两条不一样：它们是居中锚点，两侧都空着，盒子边根本管不住它们，
  // 真正的约束是**相邻轴的轴名**——邻轴锚点在 x = cx ± R·sin(2π/轴数) 处、
  // 并且朝外长，所以居中轴名最多长到那儿。12 条轴时 sin(30°)=0.5，
  // 即宽度上限正好等于 R。漏掉这一条的后果是实测出来的：只按盒子边算时
  // 底部的 "Price sensitivity" 拿到近乎整个盒宽的预算，不截断，
  // 于是和左右两条邻轴各叠一次（见本次改动的验证记录）。
  // 容器是正方形，recharts 的 cx/cy 就是 50%，所以圆心 = 盒子中心。
  const center = boxSize / 2
  const radius = Math.hypot(px - center, py - center)
  const neighborSpan = 2 * radius * Math.sin((2 * Math.PI) / Math.max(axisCount, 3))
  const budget =
    anchor === 'start'
      ? boxSize - px - AXIS_LABEL_PAD
      : anchor === 'end'
        ? px - AXIS_LABEL_PAD
        : Math.min(neighborSpan, 2 * Math.min(px, boxSize - px)) - AXIS_LABEL_PAD

  return (
    <>
      {/* 截断后全名靠原生 tooltip 找回来。<title> 挂在 recharts 给的 <g> 上。 */}
      <title>{label}</title>
      <Text
        x={x}
        y={y}
        textAnchor={anchor}
        verticalAnchor={verticalAnchor ?? 'middle'}
        fill={AXIS_TICK_FILL}
        // 字体必须写进 style：recharts 用它测宽，测宽用的样式和渲染用的样式
        // 不是同一份的话，截出来的长度就是错的。
        style={{ fontSize: labelFontSize, fontFamily: AXIS_FONT_FAMILY }}
        width={isMissing ? undefined : Math.max(budget, labelFontSize)}
        maxLines={1}
      >
        {label}
      </Text>
    </>
  )
}

type ChartData = BehaviorAxis[] | Record<string, number>

function normalizeData(data: ChartData): BehaviorAxis[] {
  if (Array.isArray(data)) {
    return data.map((d) => ({ ...d, axis: axisLabel(d.axis) }))
  }
  return Object.entries(data).map(([axis, value]) => ({
    axis: axisLabel(axis),
    value,
  }))
}

interface PersonaRadarChartProps {
  data: ChartData
  compareData?: ChartData
  name1?: string
  name2?: string
  size?: number
  mobileSize?: number
}

export default function PersonaRadarChart({
  data,
  compareData,
  // 默认参数在**每次调用时**求值，所以这两个 t() 会跟着 ui_lang 走。
  // 提到模块级常量里就会退化成"打开页面时那种语言"，这正是 navItems 那条注释说的坑。
  name1 = t('common.persona_radar.series_a.label'),
  name2 = t('common.persona_radar.series_b.label'),
  size = 300,
  mobileSize,
}: PersonaRadarChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState<number | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width)
      }
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const computedSize = (() => {
    if (containerWidth !== null && containerWidth < 300) {
      if (mobileSize) return Math.min(mobileSize, containerWidth)
      return Math.min(60, containerWidth)
    }
    if (mobileSize && containerWidth !== null && containerWidth < 640) {
      return mobileSize
    }
    return size
  })()

  const normalizedData = normalizeData(data)
  const normalizedCompare = compareData ? normalizeData(compareData) : undefined

  // 对比数据按轴名（已归一化成中文 label）配对，而不是按数组下标：
  // 不同角色包 behavior_profile 的键序可能不同，按下标配对会整条错位。
  // 找不到对应维度就留给 recharts 按缺失值处理（不画该顶点），不硬凑错位数据。
  const compareByAxis = new Map((normalizedCompare ?? []).map((c) => [c.axis, c.value]))
  const chartData = normalizedData.map((d) => ({
    axis: d.axis,
    value1: d.value,
    value2: compareByAxis.get(d.axis),
  }))

  const fontSize = computedSize < 200 ? 8 : computedSize < 300 ? 9 : 10

  // 缺译标记必须画出来，多小都画（AxisTick 里对 ⟦ 开头的串一律不隐藏、不截断）。
  // 但它**不会**把其余 11 条轴名一起拽回来：80px 的缩略图上把它们打开，
  // 得到的是 "N…" "…" 这种一个省略号的残根，只会盖住那条真正要看的标记。
  // 这里只做一件事——有标记时按带轴名的那一档收半径，给标记腾地方。
  const hasMissingAxis = chartData.some((d) => d.axis.startsWith('⟦'))
  const showAxisLabels = computedSize >= AXIS_LABEL_MIN_SIZE

  return (
    <div ref={containerRef}>
      <ResponsiveContainer width={computedSize} height={computedSize}>
        <RadarChart
          data={chartData}
          cx="50%"
          cy="50%"
          outerRadius={
            showAxisLabels || hasMissingAxis ? LABELED_OUTER_RADIUS : PLAIN_OUTER_RADIUS
          }
        >
          {/* 深色底配色：网格用 border 色，刻度用次要/弱文字色；
              #e5e5ea 网格在 #1c1c1e 卡片上会亮得刺眼 */}
          <PolarGrid stroke="#38383a" strokeDasharray="3 3" />
          <PolarAngleAxis
            dataKey="axis"
            tickSize={AXIS_TICK_SIZE}
            tick={
              <AxisTick
                boxSize={computedSize}
                axisCount={chartData.length}
                labelFontSize={fontSize}
                labelsHidden={!showAxisLabels}
              />
            }
          />
          <PolarRadiusAxis angle={30} domain={[0, 1]} tick={false} axisLine={false} />
          <Radar name={name1} dataKey="value1" stroke="#0a84ff" fill="#0a84ff" fillOpacity={0.25} strokeWidth={2} dot={{ r: 2.5, fill: '#0a84ff' }} />
          {normalizedCompare && (
            <Radar name={name2} dataKey="value2" stroke="#32ade6" fill="#32ade6" fillOpacity={0.20} strokeWidth={2} dot={{ r: 2.5, fill: '#32ade6' }} />
          )}
          {normalizedCompare && (
            <Legend wrapperStyle={{ fontSize: 12, fontFamily: 'Noto Sans SC', color: '#8e8e93' }} />
          )}
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
