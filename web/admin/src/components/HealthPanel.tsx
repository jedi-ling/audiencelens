import { useCallback, useEffect, useState } from 'react'
import { Activity, AlertTriangle } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import { ApiError, type AdminHealth } from '@/lib/types'
import { PanelShell, PanelError, PanelLoading, MiniStat } from './panel'

const WIDTH = 640
const HEIGHT = 150
const PAD = { top: 12, right: 12, bottom: 22, left: 8 }
const INNER_W = WIDTH - PAD.left - PAD.right
const INNER_H = HEIGHT - PAD.top - PAD.bottom

function fmtDuration(seconds: number | null): string {
  if (seconds == null) return '—'
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  return `${m}m ${Math.round(seconds - m * 60)}s`
}

function fmtRate(rate: number | null): string {
  return rate == null ? '—' : `${(rate * 100).toFixed(1)}%`
}

/**
 * 系统健康度：成功率趋势 + 评审耗时分位数 + 卡死任务。
 *
 * 与 TimeseriesChart 的分工：那张图回答"跑了多少、花了多少钱"（业务量），
 * 这张回答"跑得好不好"（健康度）。放在一起会变成一张谁都看不懂的六线图。
 */
export function HealthPanel({ onJobsChanged }: { onJobsChanged?: () => void }) {
  const [data, setData] = useState<AdminHealth | null>(null)
  const [days, setDays] = useState(14)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const load = useCallback(async (d: number) => {
    try {
      setError(null)
      setData(await adminApi.statsHealth(d))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load(days)
  }, [load, days])

  async function forceFail(jobId: string) {
    setBusyId(jobId)
    try {
      await adminApi.forceFailJob(jobId)
      await load(days)
      onJobsChanged?.()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '操作失败')
    } finally {
      setBusyId(null)
    }
  }

  const series = data?.series ?? []
  // 只连有数据的点。把 success_rate=null 的空白天当成 0 会画出一条
  // 直插谷底的假崩溃线——那天不是全崩了，是压根没跑。
  const points = series
    .map((s, i) => ({ ...s, i }))
    .filter((s) => s.success_rate != null) as Array<{ date: string; success_rate: number; i: number }>

  const xFor = (i: number) =>
    PAD.left + (series.length <= 1 ? INNER_W / 2 : (i / (series.length - 1)) * INNER_W)
  const yFor = (rate: number) => PAD.top + INNER_H - rate * INNER_H

  const dur = data?.duration_seconds
  const stuck = data?.stuck

  return (
    <PanelShell
      icon={Activity}
      title="系统健康度"
      actions={
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
      }
    >
      <PanelError>{error}</PanelError>

      {/* 卡死告警：有就顶在最上面。这是整个面板里唯一需要立刻动手的东西。 */}
      {stuck && stuck.count > 0 && (
        <div className="mt-3 rounded-lg border border-severity-critical/40 bg-severity-critical/5 p-3">
          <p className="flex items-center gap-2 text-xs font-semibold text-severity-critical">
            <AlertTriangle className="h-3.5 w-3.5" strokeWidth={1.5} />
            {stuck.count} 个任务卡住超过 {stuck.threshold_minutes} 分钟
          </p>
          <p className="mt-1 text-[11px] leading-relaxed text-text-muted">
            状态停在 queued/running 且没有终态回写。进程内队列在重启后不会自动收尾这些行，
            它们会一直污染成功率统计，关联评审也让用户前端一直转圈。
          </p>
          <ul className="mt-2 space-y-1">
            {stuck.jobs.slice(0, 8).map((j) => (
              <li
                key={j.id}
                className="flex items-center justify-between gap-3 rounded-md bg-bg-secondary px-2 py-1.5"
              >
                <span className="min-w-0 flex-1 truncate font-mono text-[10px] text-text-muted">
                  <span className="text-text-primary">{j.kind}</span> · {j.id.slice(0, 8)} ·{' '}
                  {j.status} · 已 {j.stuck_minutes} 分钟
                </span>
                <button
                  onClick={() => void forceFail(j.id)}
                  disabled={busyId === j.id}
                  className="shrink-0 rounded border border-severity-critical/50 px-2 py-0.5 font-mono text-[10px] text-severity-critical hover:bg-severity-critical/10 disabled:opacity-40"
                >
                  {busyId === j.id ? '处理中…' : '标记为失败'}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 三个健康数字。分位数为 null 时显示 —— 而不是 0：样本为空和"跑得飞快"是两回事。 */}
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <MiniStat
          label="整体成功率"
          value={fmtRate(data?.totals.success_rate ?? null)}
          hint={data ? `完成 ${data.totals.completed} · 失败 ${data.totals.failed}` : undefined}
          tone={
            data?.totals.success_rate == null
              ? 'muted'
              : data.totals.success_rate >= 0.95
                ? 'good'
                : data.totals.success_rate >= 0.8
                  ? 'warn'
                  : 'bad'
          }
        />
        <MiniStat
          label="评审耗时 P50"
          value={fmtDuration(dur?.p50 ?? null)}
          hint={dur ? `样本 ${dur.sample_size}` : undefined}
        />
        <MiniStat
          label="评审耗时 P95"
          value={fmtDuration(dur?.p95 ?? null)}
          hint={dur?.max != null ? `最长 ${fmtDuration(dur.max)}` : undefined}
        />
      </div>

      {series.length > 0 && (
        <>
          <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="mt-4 h-36 w-full">
            {[0, 0.5, 0.8, 0.95, 1].map((f) => (
              <g key={f}>
                <line
                  x1={PAD.left}
                  x2={WIDTH - PAD.right}
                  y1={yFor(f)}
                  y2={yFor(f)}
                  stroke="var(--color-border)"
                  strokeWidth="1"
                  strokeDasharray={f === 0.95 ? '3 3' : undefined}
                />
                <text x={WIDTH - PAD.right} y={yFor(f) - 2} fontSize="8" fill="var(--color-text-muted)" textAnchor="end">
                  {(f * 100).toFixed(0)}%
                </text>
              </g>
            ))}

            {/* 失败数用柱子叠在底部：成功率掉下去的那天，柱子会同时长起来，
                一眼能分清"成功率低"是因为失败多，还是因为当天样本只有 1 次。 */}
            {series.map((s, i) => {
              const total = s.completed + s.failed
              if (total === 0) return null
              const maxBar = Math.max(1, ...series.map((p) => p.completed + p.failed))
              const h = (s.failed / maxBar) * INNER_H * 0.5
              const w = Math.max(2, (INNER_W / series.length) * 0.5)
              return (
                <rect
                  key={s.date}
                  x={xFor(i) - w / 2}
                  y={PAD.top + INNER_H - h}
                  width={w}
                  height={h}
                  fill="var(--color-severity-critical)"
                  opacity={0.3}
                />
              )
            })}

            {points.length > 1 && (
              <path
                d={points
                  .map((p, k) => `${k === 0 ? 'M' : 'L'} ${xFor(p.i).toFixed(1)} ${yFor(p.success_rate).toFixed(1)}`)
                  .join(' ')}
                fill="none"
                stroke="var(--color-brand-primary)"
                strokeWidth="2"
              />
            )}
            {points.map((p) => (
              <circle
                key={p.date}
                cx={xFor(p.i)}
                cy={yFor(p.success_rate)}
                r="2.5"
                fill={p.success_rate >= 0.95 ? 'var(--color-brand-primary)' : 'var(--color-severity-critical)'}
              >
                <title>{`${p.date} · 成功率 ${(p.success_rate * 100).toFixed(1)}%`}</title>
              </circle>
            ))}

            <text x={PAD.left} y={HEIGHT - 6} fontSize="9" fill="var(--color-text-muted)">
              {series[0].date}
            </text>
            <text x={WIDTH - PAD.right} y={HEIGHT - 6} fontSize="9" fill="var(--color-text-muted)" textAnchor="end">
              {series[series.length - 1].date}
            </text>
          </svg>
          <div className="mt-1 flex flex-wrap gap-4 font-mono text-[10px] text-text-muted">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-1.5 w-3 rounded-sm bg-brand-primary" />
              成功率
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-1.5 w-3 rounded-sm bg-severity-critical/40" />
              失败数
            </span>
            <span>没有已结束评审的日期不画点（空白天 ≠ 0%）</span>
          </div>
        </>
      )}
      {series.length === 0 && !error && <PanelLoading />}
    </PanelShell>
  )
}
