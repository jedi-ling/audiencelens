import { cn } from '@/lib/utils'
import { t } from '@/i18n/runtime'
import type { PlainMessageKey } from '@/i18n/keys.gen'
import type { Severity } from '@/lib/mock-data'

interface SeverityBadgeProps {
  severity: Severity
}

/**
 * 存的是 **key 不是文案**：这个对象在模块求值时就固定了，存翻译结果的话
 * 切换语言不会重新求值，徽章会一直停在打开页面时的那种语言。
 * 同 Layout.tsx 的 navItems，任何模块级常量里的文案都必须存 key，在渲染处才 t()。
 */
const severityConfig: Record<Severity, { labelKey: PlainMessageKey; className: string }> = {
  critical: { labelKey: 'enum.severity.critical', className: 'bg-severity-critical/20 text-severity-critical border-severity-critical/30' },
  high: { labelKey: 'enum.severity.high', className: 'bg-severity-high/20 text-severity-high border-severity-high/30' },
  medium: { labelKey: 'enum.severity.medium', className: 'bg-severity-medium/20 text-severity-medium border-severity-medium/30' },
  low: { labelKey: 'enum.severity.low', className: 'bg-severity-low/20 text-severity-low border-severity-low/30' },
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
      {t(config.labelKey)}
    </span>
  )
}
