import { useRef, useEffect, useState } from 'react'
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer, Legend } from 'recharts'
import type { BehaviorAxis } from '@/lib/mock-data'

const AXIS_LABEL_MAP: Record<string, string> = {
  patience: '耐心',
  genre_literacy: '品类理解力',
  novelty_seeking: '新鲜感追求',
  risk_tolerance: '风险承受度',
  social_influence: '社交影响度',
  completion_drive: '完成驱动',
  price_sensitivity: '价格敏感度',
  criticism_style: '批评风格',
  emotional_engagement: '情感投入度',
  agency_preference: '自主偏好',
  tolerance_for_ambiguity: '模糊容忍度',
  platform_loyalty: '平台忠诚度',
}

type ChartData = BehaviorAxis[] | Record<string, number>

function normalizeData(data: ChartData): BehaviorAxis[] {
  if (Array.isArray(data)) {
    return data.map((d) => ({ ...d, axis: AXIS_LABEL_MAP[d.axis] ?? d.axis }))
  }
  return Object.entries(data).map(([axis, value]) => ({
    axis: AXIS_LABEL_MAP[axis] ?? axis,
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

export default function PersonaRadarChart({ data, compareData, name1 = '角色 A', name2 = '角色 B', size = 300, mobileSize }: PersonaRadarChartProps) {
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

  const chartData = normalizedData.map((d, i) => ({
    axis: d.axis,
    value1: d.value,
    value2: normalizedCompare?.[i]?.value ?? undefined,
  }))

  const fontSize = computedSize < 200 ? 8 : computedSize < 300 ? 9 : 10

  return (
    <div ref={containerRef}>
      <ResponsiveContainer width={computedSize} height={computedSize}>
        <RadarChart data={chartData} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke="#2a2a3a" />
          <PolarAngleAxis dataKey="axis" tick={{ fill: '#8888a0', fontSize, fontFamily: 'Noto Sans SC' }} />
          <PolarRadiusAxis angle={30} domain={[0, 1]} tick={false} axisLine={false} />
          <Radar name={name1} dataKey="value1" stroke="#D4A94E" fill="#D4A94E" fillOpacity={0.15} strokeWidth={2} />
          {normalizedCompare && (
            <Radar name={name2} dataKey="value2" stroke="#4ECDC4" fill="#4ECDC4" fillOpacity={0.15} strokeWidth={2} />
          )}
          {normalizedCompare && (
            <Legend wrapperStyle={{ fontSize: 12, fontFamily: 'Noto Sans SC', color: '#8888a0' }} />
          )}
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
