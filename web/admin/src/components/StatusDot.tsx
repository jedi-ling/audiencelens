export function StatusDot({ status }: { status: string }) {
  const color =
    status === 'completed' || status === 'done'
      ? 'bg-brand-primary'
      : status === 'failed'
        ? 'bg-severity-critical'
        : status === 'running'
          ? 'bg-cyan'
          : status === 'cancelled'
            ? 'bg-warm-orange'
            : 'bg-text-muted'
  const label =
    status === 'completed' || status === 'done'
      ? '完成'
      : status === 'failed'
        ? '失败'
        : status === 'running'
          ? '运行中'
          : status === 'cancelled'
            ? '已取消'
            : status
  return <span className={`h-2 w-2 shrink-0 rounded-full ${color}`} aria-label={label} title={label} />
}
