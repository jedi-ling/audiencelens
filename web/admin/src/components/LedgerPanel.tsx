import { useCallback, useEffect, useState } from 'react'
import { Gauge } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminLedgerOverview } from '@/lib/types'

/** 判断复利闭环的全局视角——护城河指标，此前只在单用户产品前端可见，这是它第一次出现在后台。 */
export function LedgerPanel() {
  const [data, setData] = useState<AdminLedgerOverview | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setData(await adminApi.ledger())
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
        <Gauge className="h-4 w-4 text-neon-green" strokeWidth={1.5} />
        判断复利（全局）
        <span className="font-mono text-[10px] font-normal text-text-muted">跨全体用户聚合</span>
      </h2>

      {error && <p className="mt-2 font-mono text-xs text-severity-critical">{error}</p>}

      {data && (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MiniStat label="命中率" value={formatRate(data.hit_rate.hit_rate)} warn={data.hit_rate.low_confidence} />
            <MiniStat label="样本量" value={String(data.hit_rate.sample_size)} />
            <MiniStat label="已验证" value={String(data.hit_rate.verified)} />
            <MiniStat label="待验证" value={String(data.hit_rate.pending_verification)} />
          </div>
          {data.hit_rate.note && (
            <p className="mt-2 font-mono text-[10px] text-warm-orange">{data.hit_rate.note}</p>
          )}

          <h3 className="mt-5 font-mono text-xs text-text-secondary">人格排行榜</h3>
          <div className="mt-2 divide-y divide-border">
            {data.persona_leaderboard.length === 0 && (
              <p className="py-4 text-center text-xs text-text-muted">暂无已验证的判断</p>
            )}
            {data.persona_leaderboard.map((entry) => (
              <div key={entry.persona_id} className="flex items-center gap-3 py-2">
                <span className="min-w-0 flex-1 truncate font-mono text-xs text-text-primary">{entry.persona_id}</span>
                <span className="font-mono text-xs text-text-muted">样本 {entry.sample_size}</span>
                <span className={`font-mono text-xs font-semibold ${entry.low_confidence ? 'text-warm-orange' : 'text-neon-green'}`}>
                  {formatRate(entry.hit_rate)}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  )
}

function formatRate(rate: number | null): string {
  return rate == null ? '—' : `${Math.round(rate * 100)}%`
}

function MiniStat({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="rounded-lg border border-border bg-bg-primary/60 p-3">
      <div className={`font-mono text-lg font-bold tabular-nums ${warn ? 'text-warm-orange' : 'text-text-primary'}`}>{value}</div>
      <div className="mt-0.5 text-[10px] text-text-muted">{label}</div>
    </div>
  )
}
