import { Activity, CircleDollarSign, ClipboardCheck, ListChecks } from 'lucide-react'
import type { AdminOverview } from '@/lib/types'

/** 概览统计卡：数字 + 图形化的构成展示（分段条/环形进度），不再是纯文字罗列。 */
export function OverviewCards({ data }: { data: AdminOverview }) {
  const jobsTotal = Object.values(data.jobs_by_status).reduce((a, b) => a + b, 0)
  const bySource = data.usage_24h.cost_usd_by_source
  const serverCost = bySource['server'] ?? 0
  const byokCost = bySource['byok'] ?? 0

  return (
    <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        icon={<ClipboardCheck className="h-4 w-4" strokeWidth={1.5} />}
        accent="text-neon-green"
        label="评审总数"
        value={data.reviews.total}
      >
        <StatusBar
          items={[
            { key: 'completed', label: '完成', count: data.reviews.by_status['completed'] ?? 0, cls: 'bg-neon-green/80' },
            { key: 'failed', label: '失败', count: data.reviews.by_status['failed'] ?? 0, cls: 'bg-severity-critical/80' },
          ]}
          rest={{ label: '进行中', cls: 'bg-text-muted/40' }}
          total={data.reviews.total}
          statuses={data.reviews.by_status}
        />
      </StatCard>

      <StatCard
        icon={<CircleDollarSign className="h-4 w-4" strokeWidth={1.5} />}
        accent="text-warm-orange"
        label="24h 用量成本"
        value={`$${data.usage_24h.cost_usd_total.toFixed(4)}`}
      >
        <CostSplit server={serverCost} byok={byokCost} />
      </StatCard>

      <StatCard
        icon={<Activity className="h-4 w-4" strokeWidth={1.5} />}
        accent="text-cyan"
        label="判断留档"
        value={data.judgments.total}
      >
        <VerifyRing verified={data.judgments.verified} total={data.judgments.total} />
      </StatCard>

      <StatCard
        icon={<ListChecks className="h-4 w-4" strokeWidth={1.5} />}
        accent="text-neon-green"
        label="任务队列"
        value={jobsTotal}
      >
        <StatusBar
          items={[
            { key: 'done', label: '完成', count: data.jobs_by_status['done'] ?? 0, cls: 'bg-neon-green/80' },
            { key: 'failed', label: '失败', count: data.jobs_by_status['failed'] ?? 0, cls: 'bg-severity-critical/80' },
            { key: 'running', label: '运行中', count: data.jobs_by_status['running'] ?? 0, cls: 'bg-cyan/70' },
          ]}
          rest={{ label: '排队', cls: 'bg-text-muted/40' }}
          total={jobsTotal}
          statuses={data.jobs_by_status}
        />
      </StatCard>
    </section>
  )
}

function StatCard({
  icon,
  accent,
  label,
  value,
  children,
}: {
  icon: React.ReactNode
  accent: string
  label: string
  value: number | string
  children?: React.ReactNode
}) {
  return (
    <div className="group relative overflow-hidden rounded-xl border border-border bg-bg-card p-4 transition-colors hover:border-border-hover">
      <div className={`pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-current to-transparent opacity-30 ${accent}`} />
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-muted">{label}</span>
        <span className={`${accent} opacity-70`}>{icon}</span>
      </div>
      <div className="mt-1.5 font-mono text-2xl font-bold tabular-nums text-text-primary">{value}</div>
      {children && <div className="mt-3">{children}</div>}
    </div>
  )
}

/** 分段条：一眼看出状态构成占比，代替 "completed:3 · failed:1" 的纯文字。 */
function StatusBar({
  items,
  rest,
  total,
  statuses,
}: {
  items: { key: string; label: string; count: number; cls: string }[]
  rest: { label: string; cls: string }
  total: number
  statuses: Record<string, number>
}) {
  const known = items.reduce((a, i) => a + i.count, 0)
  const restCount = Math.max(0, total - known)
  const segments = [...items.filter((i) => i.count > 0), ...(restCount > 0 ? [{ key: '_rest', label: rest.label, count: restCount, cls: rest.cls }] : [])]

  if (total === 0) return <p className="font-mono text-[10px] text-text-muted">暂无数据</p>

  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full bg-bg-secondary">
        {segments.map((s) => (
          <div key={s.key} className={s.cls} style={{ flex: s.count }} title={`${s.label} ${s.count}`} />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[10px] text-text-muted">
        {segments.map((s) => (
          <span key={s.key} className="flex items-center gap-1">
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${s.cls}`} />
            {s.label} {s.count}
          </span>
        ))}
        {/* 罕见状态兜底：分段之外还有别的状态时按文字列出 */}
        {Object.entries(statuses)
          .filter(([k, v]) => v > 0 && !items.some((i) => i.key === k) && !['queued', 'pending', 'running'].includes(k))
          .map(([k, v]) => (
            <span key={k}>{k}:{v}</span>
          ))}
      </div>
    </div>
  )
}

/** 服务端垫付 vs BYOK 的成本占比条。 */
function CostSplit({ server, byok }: { server: number; byok: number }) {
  const total = server + byok
  if (total <= 0) return <p className="font-mono text-[10px] text-text-muted">窗口期内暂无用量</p>
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full bg-bg-secondary">
        {server > 0 && <div className="bg-warm-orange/80" style={{ flex: server }} title={`服务端垫付 $${server.toFixed(4)}`} />}
        {byok > 0 && <div className="bg-cyan/70" style={{ flex: byok }} title={`BYOK $${byok.toFixed(4)}`} />}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 font-mono text-[10px] text-text-muted">
        <span className="flex items-center gap-1">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-warm-orange/80" />
          垫付 ${server.toFixed(4)}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-cyan/70" />
          BYOK ${byok.toFixed(4)}
        </span>
      </div>
    </div>
  )
}

/** 已验证占比环——SVG 手绘，无图表库。 */
function VerifyRing({ verified, total }: { verified: number; total: number }) {
  const pct = total > 0 ? verified / total : 0
  const r = 16
  const c = 2 * Math.PI * r
  return (
    <div className="flex items-center gap-3">
      <svg viewBox="0 0 40 40" className="h-10 w-10 -rotate-90">
        <circle cx="20" cy="20" r={r} fill="none" strokeWidth="4" className="stroke-bg-secondary" />
        <circle
          cx="20"
          cy="20"
          r={r}
          fill="none"
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={`${c * pct} ${c}`}
          className="stroke-cyan transition-all duration-500"
        />
      </svg>
      <div className="font-mono text-[10px] leading-relaxed text-text-muted">
        <div>
          已验证 <span className="text-text-secondary">{verified}</span>
          {total > 0 && <span className="ml-1 text-cyan">{Math.round(pct * 100)}%</span>}
        </div>
        <div>待验证 {Math.max(0, total - verified)}</div>
      </div>
    </div>
  )
}
