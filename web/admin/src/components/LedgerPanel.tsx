import { useCallback, useEffect, useState } from 'react'
import { Gauge } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminLedgerOverview } from '@/lib/types'
import { PanelShell, PanelError, PanelEmpty, PanelLoading, SubHeading, MiniStat } from './panel'

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
    <PanelShell icon={Gauge} title="判断复利（全局）" hint="跨全体用户聚合">
      <PanelError>{error}</PanelError>

      {!data && !error && <PanelLoading />}

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

          <SubHeading>人格排行榜</SubHeading>
          <div className="mt-2 divide-y divide-border">
            {data.persona_leaderboard.length === 0 && <PanelEmpty />}
            {data.persona_leaderboard.map((entry) => (
              <div key={entry.persona_id} className="flex items-center gap-3 py-2">
                <span className="min-w-0 flex-1 truncate font-mono text-xs text-text-primary">{entry.persona_id}</span>
                <span className="font-mono text-xs text-text-muted">样本 {entry.sample_size}</span>
                <span className={`font-mono text-xs font-semibold tabular-nums ${entry.low_confidence ? 'text-warm-orange' : 'text-brand-primary'}`}>
                  {formatRate(entry.hit_rate)}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </PanelShell>
  )
}

function formatRate(rate: number | null): string {
  return rate == null ? '—' : `${Math.round(rate * 100)}%`
}
