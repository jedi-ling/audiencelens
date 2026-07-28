export function StatusDot({ status }: { status: string }) {
  const color =
    status === 'completed' || status === 'done'
      ? 'bg-brand-primary'
      : status === 'failed'
        ? 'bg-severity-critical'
        : status === 'running'
          ? 'bg-cyan'
          : 'bg-text-muted'
  return <span className={`h-2 w-2 shrink-0 rounded-full ${color}`} />
}
