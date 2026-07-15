import { cn } from '@/lib/utils'

interface CalibrationGaugeProps {
  label: string
  value: number
  max?: number
}

export default function CalibrationGauge({ label, value, max = 1 }: CalibrationGaugeProps) {
  const percentage = (value / max) * 100
  const angle = (percentage / 100) * 180

  // 语义色 —— 镜像 index.css token（SVG stroke 无法用 Tailwind 类）
  const getColor = () => {
    if (percentage >= 80) return '#2f9e6f' // 成功（status-completed）
    if (percentage >= 60) return '#c1841f' // 警告（severity-medium）
    if (percentage >= 40) return '#e0603f' // 偏低（severity-high / warm-orange）
    return '#d34b3d' // 严重（severity-critical）
  }

  const color = getColor()

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="140" height="80" viewBox="0 0 140 80">
        <path
          d="M 10 75 A 60 60 0 0 1 130 75"
          fill="none"
          stroke="#dfe3ea"
          strokeWidth="10"
          strokeLinecap="round"
        />
        <path
          d="M 10 75 A 60 60 0 0 1 130 75"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${(angle / 180) * 188.5} 188.5`}
        />
        <line
          x1="70"
          y1="75"
          x2={70 + 55 * Math.cos((angle - 90) * (Math.PI / 180) - Math.PI)}
          y2={75 + 55 * Math.sin((angle - 90) * (Math.PI / 180) - Math.PI)}
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
        />
        <circle cx="70" cy="75" r="4" fill={color} />
      </svg>
      <div className="text-center">
        <span className="font-display text-lg font-bold" style={{ color }}>{(percentage).toFixed(0)}%</span>
        <p className="text-xs text-text-secondary mt-0.5">{label}</p>
      </div>
    </div>
  )
}
