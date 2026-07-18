import type { AdminOverview } from '@/lib/types'

export function OverviewCards({ data }: { data: AdminOverview }) {
  const usageBySource = Object.entries(data.usage_24h.cost_usd_by_source)
  return (
    <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Stat label="评审总数" value={data.reviews.total} sub={statusBreakdown(data.reviews.by_status)} />
      <Stat
        label="24h 用量成本"
        value={`$${data.usage_24h.cost_usd_total.toFixed(4)}`}
        sub={usageBySource.map(([k, v]) => `${k}: $${v.toFixed(4)}`).join(' · ') || '—'}
      />
      <Stat
        label="判断留档"
        value={data.judgments.total}
        sub={`已验证 ${data.judgments.verified} (${percent(data.judgments.verified, data.judgments.total)})`}
      />
      <Stat
        label="任务队列"
        value={Object.values(data.jobs_by_status).reduce((a, b) => a + b, 0)}
        sub={statusBreakdown(data.jobs_by_status)}
      />
    </section>
  )
}

function statusBreakdown(rec: Record<string, number>): string {
  const entries = Object.entries(rec)
  return entries.length ? entries.map(([k, v]) => `${k}:${v}`).join(' · ') : '—'
}

function percent(n: number, total: number): string {
  return total ? `${Math.round((n / total) * 100)}%` : '—'
}

function Stat({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="rounded-xl border border-border bg-bg-card p-4">
      <div className="font-mono text-2xl font-bold tabular-nums text-text-primary">{value}</div>
      <div className="mt-1 text-xs text-text-muted">{label}</div>
      {sub && <div className="mt-2 font-mono text-[10px] text-text-secondary">{sub}</div>}
    </div>
  )
}
