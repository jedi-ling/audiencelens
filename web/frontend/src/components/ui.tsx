/**
 * 全站共享的布局基元 —— 「结果与辅助」一组页面的统一规格落地处。
 *
 * 为什么收在这里：这 9 个页面过去各自手写「容器宽度 + 页面标题 + 空状态 +
 * 区块卡片」，同一个意思写出了 4 套容器（max-w-4xl/5xl/6xl/7xl 混用、
 * px-4/px-6 混用、py-6/8/12 混用）、4 套标题字号（text-xl/2xl/3xl/4xl）。
 * 每多一套写法，下一次改视觉就得漏改几处——规格只有一份才有意义。
 *
 * 规格：
 * - 容器分档：阅读/表单型（正文越窄越好读）用 max-w-3xl~4xl；
 *   卡片网格型用 max-w-6xl~7xl。通过 size 属性锁死这两档，不许各页自选。
 * - 页首：标题 font-display text-2xl font-bold、副标题 text-sm text-text-secondary，
 *   页首与内容间距统一 mb-8。
 * - 空状态：居中图标 + 一行说明 + 至多一个主行动按钮（PrimaryButton）。
 */

import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

/* ---------- 页面壳 ---------- */

type PageShellSize = 'reading' | 'grid'

// 容器档位与内容类型一一对应，中间不设别的档：
// reading = 正文阅读/表单（长文行宽控制在 ~64ch 以内才好读）
// grid = 卡片网格（三列卡片在大屏需要 ~1152px+ 才不挤）
const SHELL_WIDTH: Record<PageShellSize, string> = {
  reading: 'max-w-4xl',
  grid: 'max-w-6xl',
}

interface PageShellProps {
  size: PageShellSize
  /** 默认 true；loading/错误等整页居中的分支可关掉（那不属于正常页面排版） */
  animate?: boolean
  className?: string
  children: ReactNode
}

export function PageShell({ size, animate = true, className, children }: PageShellProps) {
  return (
    <div className={cn('mx-auto px-4 py-8', SHELL_WIDTH[size], animate && 'animate-fade-in', className)}>
      {children}
    </div>
  )
}

interface PageHeaderProps {
  title: ReactNode
  subtitle?: ReactNode
  /** 标题左侧的返回/装饰区（如返回箭头按钮） */
  leading?: ReactNode
  /** 标题行右侧的操作区（如「对比模式」「共 N 条」），在 375px 下折到下一行 */
  actions?: ReactNode
  center?: boolean
}

export function PageHeader({ title, subtitle, leading, actions, center }: PageHeaderProps) {
  return (
    <div className={cn('mb-8 flex flex-wrap items-center gap-3', center && 'justify-center text-center')}>
      {leading}
      <div className="min-w-0 flex-1">
        <h1 className="font-display text-2xl font-bold text-text-primary">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-text-secondary">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

/* ---------- 区块卡片 ---------- */

/** 页面内的内容区块：统一的圆角/边框/内边距，避免各页 p-5/p-6 混用 */
export function SectionCard({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <section className={cn('rounded-xl border border-border bg-bg-card p-5 md:p-6', className)}>
      {children}
    </section>
  )
}

/* ---------- 空状态 ---------- */

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  /** 主行动（Link/button），空状态至多一个 */
  action?: ReactNode
  /** 错误/警示态把图标换成危险色，与「真的没有数据」区分开 */
  tone?: 'default' | 'error'
  className?: string
}

export function EmptyState({ icon: Icon, title, description, action, tone = 'default', className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-16 text-center rounded-xl border border-border bg-bg-card px-4', className)}>
      <Icon
        className={cn('w-10 h-10 mb-4', tone === 'error' ? 'text-severity-critical' : 'text-text-muted')}
        strokeWidth={1.25}
      />
      <p className="text-sm font-medium text-text-primary">{title}</p>
      {description && <p className="mt-1 max-w-sm text-xs leading-relaxed text-text-secondary">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

/* ---------- 主行动按钮 ---------- */

/** 全站统一的主行动按钮（实心系统蓝）。Link/button 都用它包一层，
 *  免得有的页写 font-bold、有的页写 font-semibold。 */
export const PRIMARY_BUTTON_CLASS =
  'inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-primary text-sm font-semibold text-white transition-colors hover:bg-brand-primary-dim'

/** 次级行动按钮（描边），用于重试、清除筛选等 */
export const SECONDARY_BUTTON_CLASS =
  'inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-bg-card text-sm text-text-secondary transition-colors hover:border-brand-primary/30 hover:text-text-primary'

/* ---------- 卡片网格 ---------- */

/** 卡片网格页的统一断点与间距：小屏一列、平板两列、桌面三列。
 *  卡片自身记得挂 h-full + flex 才能等高（见 PersonaCard/TaskTypeCard）。 */
export const CARD_GRID_CLASS = 'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3'
