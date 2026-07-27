import { cn } from '@/lib/utils'

interface CalibrationGaugeProps {
  label: string
  value: number
  max?: number
}

export default function CalibrationGauge({ label, value, max = 1 }: CalibrationGaugeProps) {
  const percentage = (value / max) * 100
  const angle = (percentage / 100) * 180

  const getColor = () => {
    // 梯度靠明度递增表达"越高越好"，顶档必须比 80 分以下更亮，故用绸缎金而非偏暗的品牌主色
    if (percentage >= 80) return '#F9D67D'
    if (percentage >= 60) return '#ffbb33'
    if (percentage >= 40) return '#ff6b35'
    return '#ff3355'
  }

  const color = getColor()

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="140" height="80" viewBox="0 0 140 80">
        <path
          d="M 10 75 A 60 60 0 0 1 130 75"
          fill="none"
          stroke="#2a2a3a"
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
          style={{ filter: `drop-shadow(0 0 6px ${color}40)` }}
        />
        <line
          x1="70"
          y1="75"
          x2={70 + 55 * Math.cos((angle - 90) * (Math.PI / 180) - Math.PI)}
          y2={75 + 55 * Math.sin((angle - 90) * (Math.PI / 180) - Math.PI)}
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 4px ${color}60)` }}
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
