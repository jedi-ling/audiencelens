/**
 * 管理后台的共享面板原语——所有 Panel 的外观规格只在这里定义一份。
 *
 * 为什么单独抽出来：后台有十几个面板，此前每个都手写
 * "rounded-xl border border-border bg-bg-card p-5" 和各种各样的空态/表头样式，
 * 任何一处想调规格都要改十几遍，漏一处就是视觉裂缝。
 * 运维工具的核心是扫读效率——同类信息必须在同一位置、同一格式。
 *
 * 规格约定（各 Panel 只传内容，不传样式）：
 * - 容器卡片：rounded-lg border border-border bg-bg-card p-5
 * - 面板标题（<PanelShell title>）：text-sm font-semibold text-text-primary，非等宽
 * - 标题副标注（hint）：font-mono text-[10px] text-text-muted
 * - 面板内分区间距：标题/描述 → 正文 mt-4；分区之间 mt-5（SubHeading 自带）
 * - 空态统一文案「暂无数据」，加载态统一「加载中…」，居中 text-xs text-text-muted py-6
 * - 表格：TableWrap 横向滚动；表头 font-mono text-[10px] text-text-muted 左对齐，
 *   数值列由调用方加 text-right tabular-nums
 */
import type { LucideIcon } from 'lucide-react'

/** 图标位置统一渲染 h-4 w-4、strokeWidth 1.5——此前各面板手写这两行，数值偶有漂移。 */
function PanelIcon({ icon: Icon, tone }: { icon: LucideIcon; tone: string }) {
  return <Icon className={`h-4 w-4 ${tone}`} strokeWidth={1.5} />
}

export function PanelShell({
  icon,
  iconTone = 'text-brand-primary',
  title,
  hint,
  actions,
  className = '',
  children,
}: {
  icon: LucideIcon
  iconTone?: string
  title: React.ReactNode
  /** 标题行右侧的等宽小字副标注，如「改动无需重启」 */
  hint?: React.ReactNode
  /** 标题行右侧的控件区（筛选器/时间窗下拉等），宽度不够时整行换到下一行 */
  actions?: React.ReactNode
  className?: string
  children: React.ReactNode
}) {
  return (
    <section className={`rounded-lg border border-border bg-bg-card p-5 ${className}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <PanelIcon icon={icon} tone={iconTone} />
          {title}
          {hint && <span className="font-mono text-[10px] font-normal text-text-muted">{hint}</span>}
        </h2>
        {actions && <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </section>
  )
}

/** 面板顶部的说明段（标题正下方），正文级次要文字用 text-text-secondary 保证对比度。 */
export function PanelDesc({ children }: { children: React.ReactNode }) {
  return <p className="mt-1.5 text-xs leading-relaxed text-text-secondary">{children}</p>
}

/** 面板内错误条：mt-2 font-mono text-xs text-severity-critical，全站一档。 */
export function PanelError({ children }: { children: React.ReactNode }) {
  if (children == null || children === '') return null
  return <p className="mt-2 font-mono text-xs text-severity-critical">{children}</p>
}

/** 统一空态：文案全站固定「暂无数据」，调用方不传文案，避免各写各的。 */
export function PanelEmpty({ text = '暂无数据' }: { text?: string }) {
  return <p className="py-6 text-center text-xs text-text-muted">{text}</p>
}

/** 统一加载态：与空态同位同样式，占位文案固定「加载中…」。 */
export function PanelLoading() {
  return <p className="py-6 text-center text-xs text-text-muted">加载中…</p>
}

/** 卡片式记录列表里的空态项（Jobs/Reviews/AuditLog 这类 ul 列表用）。 */
export function EmptyRow() {
  return <li className="py-6 text-center text-xs text-text-muted">暂无数据</li>
}

/** 描边空态块（抽屉/聚合面板里的分区空态，视觉上比纯文字更"封得住"）。 */
export function EmptyPill({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-lg border border-border bg-bg-secondary px-3 py-3 text-center text-xs text-text-muted">
      {children}
    </p>
  )
}

/** 面板内次级分区标题：mt-5 自带与上一分区的间距，全站统一。 */
export function SubHeading({ children }: { children: React.ReactNode }) {
  return <h3 className="mt-5 font-mono text-xs text-text-secondary">{children}</h3>
}

/** 面板内小型统计格（命中率/P50/余额 等"标签下大数"的格子），全站一种样式。 */
export function MiniStat({
  label,
  value,
  hint,
  warn,
  tone,
}: {
  label: string
  value: string
  hint?: string
  warn?: boolean
  tone?: 'good' | 'warn' | 'bad' | 'muted'
}) {
  const valueColor = warn
    ? 'text-warm-orange'
    : tone === 'good'
      ? 'text-brand-primary'
      : tone === 'warn'
        ? 'text-warm-orange'
        : tone === 'bad'
          ? 'text-severity-critical'
          : 'text-text-primary'
  return (
    <div className="rounded-lg border border-border bg-bg-secondary p-3">
      <p className="font-mono text-[10px] uppercase tracking-wide text-text-muted">{label}</p>
      <p className={`mt-1 font-mono text-lg font-bold tabular-nums ${valueColor}`}>{value}</p>
      {hint && <p className="mt-0.5 font-mono text-[10px] text-text-muted">{hint}</p>}
    </div>
  )
}

/** 表格横向滚动容器：窄屏不挤压列宽，最小宽度用内联 style（Tailwind 不接受动态类名）。 */
export function TableWrap({ minWidth, children }: { minWidth?: string; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left font-mono text-xs" style={minWidth ? { minWidth } : undefined}>
        {children}
      </table>
    </div>
  )
}

/** 表头行：表头字号字色全站一档。数值列表头由调用方在 th 上加 text-right。 */
export function TableHead({ children }: { children: React.ReactNode }) {
  return (
    <thead className="text-[10px] text-text-muted">
      {children}
    </thead>
  )
}
