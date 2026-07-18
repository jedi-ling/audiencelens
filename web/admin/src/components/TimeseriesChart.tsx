import { useCallback, useEffect, useState } from 'react'
import { TrendingUp } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminTimeseries } from '@/lib/types'

const WIDTH = 640
const HEIGHT = 180
const PAD = { top: 12, right: 12, bottom: 22, left: 8 }
const INNER_W = WIDTH - PAD.left - PAD.right
const INNER_H = HEIGHT - PAD.top - PAD.bottom

type ReviewKey = 'reviews_total' | 'reviews_completed' | 'reviews_failed'

const LINES: Array<{ key: ReviewKey; color: string; label: string }> = [
  { key: 'reviews_total', color: 'var(--color-cyan)', label: '总量' },
  { key: 'reviews_completed', color: 'var(--color-neon-green)', label: '完成' },
  { key: 'reviews_failed', color: 'var(--color-severity-critical)', label: '失败' },
]

/** 无第三方依赖的轻量 SVG 趋势图——评审量三线 + 成本柱状叠加，够用即可，不为此引入图表库。 */
export function TimeseriesChart() {
  const [data, setData] = useState<AdminTimeseries | null>(null)
  const [days, setDays] = useState(14)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (d: number) => {
    try {
      setData(await adminApi.timeseries(d))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load(days)
  }, [load, days])

  const series = data?.series ?? []
  const maxReviews = Math.max(1, ...series.map((s) => s.reviews_total))
  const maxCost = Math.max(0.0001, ...series.map((s) => s.cost_usd))

  const xFor = (i: number) => PAD.left + (series.length <= 1 ? INNER_W / 2 : (i / (series.length - 1)) * INNER_W)
  const yForReviews = (v: number) => PAD.top + INNER_H - (v / maxReviews) * INNER_H
  const linePath = (key: ReviewKey) =>
    series.map((s, i) => `${i === 0 ? 'M' : 'L'} ${xFor(i).toFixed(1)} ${yForReviews(s[key]).toFixed(1)}`).join(' ')

  const barW = series.length > 0 ? Math.max(2, (INNER_W / series.length) * 0.5) : 0

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <TrendingUp className="h-4 w-4 text-cyan" strokeWidth={1.5} />
          评审量 / 成本趋势
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

      {series.length > 0 && (
        <>
          <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="mt-3 h-44 w-full">
            {[0, 0.5, 1].map((f) => (
              <line
                key={f}
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={PAD.top + INNER_H * (1 - f)}
                y2={PAD.top + INNER_H * (1 - f)}
                stroke="var(--color-border)"
                strokeWidth="1"
              />
            ))}
            {series.map((s, i) => {
              const h = (s.cost_usd / maxCost) * INNER_H
              return (
                <rect
                  key={s.date}
                  x={xFor(i) - barW / 2}
                  y={PAD.top + INNER_H - h}
                  width={barW}
                  height={h}
                  fill="var(--color-warm-orange)"
                  opacity={0.25}
                />
              )
            })}
            {LINES.map(({ key, color }) => (
              <path key={key} d={linePath(key)} fill="none" stroke={color} strokeWidth="2" />
            ))}
            {series.map((s, i) => (
              <circle key={i} cx={xFor(i)} cy={yForReviews(s.reviews_total)} r="2" fill="var(--color-cyan)" />
            ))}
            <text x={PAD.left} y={HEIGHT - 6} fontSize="9" fill="var(--color-text-muted)">
              {series[0].date}
            </text>
            <text x={WIDTH - PAD.right} y={HEIGHT - 6} fontSize="9" fill="var(--color-text-muted)" textAnchor="end">
              {series[series.length - 1].date}
            </text>
          </svg>
          <div className="mt-1 flex flex-wrap gap-4 font-mono text-[10px] text-text-muted">
            {LINES.map(({ key, color, label }) => (
              <span key={key} className="flex items-center gap-1.5">
                <span className="inline-block h-1.5 w-3 rounded-sm" style={{ background: color }} />
                {label}
              </span>
            ))}
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-1.5 w-3 rounded-sm bg-warm-orange/40" />
              成本（独立坐标轴）
            </span>
          </div>
        </>
      )}
      {series.length === 0 && !error && <p className="mt-4 py-6 text-center text-xs text-text-muted">加载中…</p>}
    </section>
  )
}
