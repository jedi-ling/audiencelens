import { useRef, useEffect, useState } from 'react'
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer, Legend } from 'recharts'
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

  return (
    <div ref={containerRef}>
      <ResponsiveContainer width={computedSize} height={computedSize}>
        <RadarChart data={chartData} cx="50%" cy="50%" outerRadius="70%">
          {/* 深色底配色：网格用 border 色，刻度用次要/弱文字色；
              #e5e5ea 网格在 #1c1c1e 卡片上会亮得刺眼 */}
          <PolarGrid stroke="#38383a" strokeDasharray="3 3" />
          <PolarAngleAxis dataKey="axis" tick={{ fill: '#8e8e93', fontSize, fontFamily: 'Noto Sans SC' }} />
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
