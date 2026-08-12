import { cn } from '@/lib/utils'
import type { Severity } from '@/lib/mock-data'

interface SeverityBadgeProps {
  severity: Severity
}

const severityConfig: Record<Severity, { label: string; className: string }> = {
  critical: { label: '严重', className: 'bg-severity-critical/20 text-severity-critical border-severity-critical/30' },
  high: { label: '高', className: 'bg-severity-high/20 text-severity-high border-severity-high/30' },
  medium: { label: '中', className: 'bg-severity-medium/20 text-severity-medium border-severity-medium/30' },
  low: { label: '低', className: 'bg-severity-low/20 text-severity-low border-severity-low/30' },
}

export default function SeverityBadge({ severity }: SeverityBadgeProps) {
  const config = severityConfig[severity]
  return (
    // rounded-md：与全站徽章圆角统一（原 rounded=0.25rem 偏小）。
    // 语义 token 类名必须是完整字面量，Tailwind 才扫得到——severityConfig 里的
    // 拼接已经满足这一点，别改成模板字符串组装。
    <span className={cn(
      'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
      config.className
    )}>
      {config.label}
    </span>
  )
}
