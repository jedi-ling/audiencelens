import { useCallback, useEffect, useState } from 'react'
import { ListChecks } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminJobStats } from '@/lib/types'

const STATUS_COLOR: Record<string, string> = {
  done: 'var(--color-brand-primary)',
  running: 'var(--color-cyan)',
  queued: 'var(--color-warm-orange)',
  failed: 'var(--color-severity-critical)',
  cancelled: 'var(--color-text-muted)',
}

function fmtSeconds(s: number | null): string {
  if (s == null) return '—'
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  return `${m}m ${Math.round(s - m * 60)}s`
}

/**
 * 任务队列的聚合视图。
 *
 * /jobs 那张列表是逐条日志流——出事时你得自己一页页往下翻找规律。
 * 这个面板回答的是翻之前的那个问题：现在哪种状态堆着？失败都栽在什么上？
 */
export function JobStatsPanel({ refreshKey }: { refreshKey?: number }) {
  const [data, setData] = useState<AdminJobStats | null>(null)
  const [days, setDays] = useState(14)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const load = useCallback(async (d: number) => {
    try {
      setError(null)
      setData(await adminApi.statsJobs(d))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load(days)
  }, [load, days, refreshKey])

  const byStatus = Object.entries(data?.by_status ?? {}).sort((a, b) => b[1] - a[1])
  const statusTotal = byStatus.reduce((sum, [, n]) => sum + n, 0)
  const reasons = data?.failure_reasons ?? []
  const maxReason = Math.max(1, ...reasons.map((r) => r.count))
  const rt = data?.runtime_seconds

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <ListChecks className="h-4 w-4 text-cyan" strokeWidth={1.5} />
          任务队列聚合
        </h2>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none"
        >
          <option value={7}>近 7 天</option>
          <option value={14}>近 14 天</option>
          <option value={30}>近 30 天</option>
          <option value={90}>近 90 天</option>
        </select>
      </div>

      {error && <p className="mt-2 font-mono text-xs text-severity-critical">{error}</p>}

      {statusTotal > 0 && (
        <>
          {/* 一条堆叠条 + 图例。饼图在 5 个以内分类上并不比它更好读，还更占地方。 */}
          <div className="mt-4 flex h-2.5 w-full overflow-hidden rounded-full bg-bg-secondary">
            {byStatus.map(([status, n]) => (
              <div
                key={status}
                style={{
                  width: `${(n / statusTotal) * 100}%`,
                  background: STATUS_COLOR[status] ?? 'var(--color-text-muted)',
                }}
                title={`${status}: ${n}`}
              />
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-text-muted">
            {byStatus.map(([status, n]) => (
              <span key={status} className="flex items-center gap-1.5">
                <span
                  className="inline-block h-1.5 w-3 rounded-sm"
                  style={{ background: STATUS_COLOR[status] ?? 'var(--color-text-muted)' }}
                />
                {status} <span className="text-text-primary">{n}</span>
              </span>
            ))}
          </div>
        </>
      )}

      <div className="mt-4 grid grid-cols-3 gap-3">
        <Mini label="执行耗时 P50" value={fmtSeconds(rt?.p50 ?? null)} />
        <Mini label="执行耗时 P95" value={fmtSeconds(rt?.p95 ?? null)} />
        <Mini label="最长一次" value={fmtSeconds(rt?.max ?? null)} hint={rt ? `样本 ${rt.sample_size}` : ''} />
      </div>

      <div className="mt-5">
        <p className="font-mono text-[10px] uppercase tracking-wide text-text-muted">
          失败原因 Top {reasons.length}
        </p>
        {reasons.length === 0 && (
          <p className="mt-2 rounded-lg border border-border bg-bg-secondary px-3 py-4 text-center text-xs text-text-muted">
            这段时间没有失败的任务
          </p>
        )}
        <ul className="mt-2 space-y-1.5">
          {reasons.map((r) => (
            <li key={r.signature}>
              <button
                onClick={() => setExpanded(expanded === r.signature ? null : r.signature)}
                className="w-full rounded-md px-1 py-1 text-left hover:bg-bg-secondary"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-text-primary">
                    {r.signature}
                  </span>
                  <span className="shrink-0 font-mono text-[11px] text-severity-critical">
                    {r.count}
                  </span>
                </div>
                <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-bg-secondary">
                  <div
                    className="h-full rounded-full bg-severity-critical/60"
                    style={{ width: `${(r.count / maxReason) * 100}%` }}
                  />
                </div>
              </button>
              {expanded === r.signature && r.sample && (
                <pre className="mt-1 max-h-40 overflow-auto rounded-md bg-bg-secondary p-2 font-mono text-[10px] leading-relaxed text-text-muted">
                  {r.sample}
                </pre>
              )}
            </li>
          ))}
        </ul>
        {reasons.length > 0 && (
          <p className="mt-2 font-mono text-[10px] text-text-muted">
            签名已归一化（UUID / 数字替换为占位符），所以同类故障会聚成一条。点开看原始消息。
          </p>
        )}
      </div>
    </section>
  )
}

function Mini({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-border bg-bg-secondary p-3">
      <p className="font-mono text-[10px] uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-1 font-mono text-lg text-text-primary">{value}</p>
      {hint && <p className="mt-0.5 font-mono text-[10px] text-text-muted">{hint}</p>}
    </div>
  )
}
