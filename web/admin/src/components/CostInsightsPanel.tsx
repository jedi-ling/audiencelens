import { useCallback, useEffect, useState } from 'react'
import { Wallet } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminCostStats } from '@/lib/types'
import { PanelShell, PanelError, PanelEmpty, PanelLoading, SubHeading } from './panel'

const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  byok: { label: 'BYOK（用户自付）', color: 'bg-cyan/70' },
  server: { label: '平台垫付', color: 'bg-warm-orange/70' },
}

/** 成本构成：谁在花钱、花的是谁的钱——运营最关心的两个问题。 */
export function CostInsightsPanel() {
  const [data, setData] = useState<AdminCostStats | null>(null)
  const [days, setDays] = useState(30)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (d: number) => {
    try {
      setData(await adminApi.statsCosts(d))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load(days)
  }, [load, days])

  const sources = Object.entries(data?.cost_by_source ?? {})
  const totalCost = sources.reduce((a, [, v]) => a + v, 0)
  const topUsers = data?.top_users ?? []
  const maxUserCost = Math.max(0.0001, ...topUsers.map((u) => u.cost_usd))

  return (
    <PanelShell
      icon={Wallet}
      iconTone="text-warm-orange"
      title="成本构成"
      actions={
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none"
        >
          <option value={7}>近 7 天</option>
          <option value={30}>近 30 天</option>
          <option value={90}>近 90 天</option>
        </select>
      }
    >
      <PanelError>{error}</PanelError>

      {!data && !error && <PanelLoading />}

      {data && (
        <>
          <div className="mt-4">
            <div className="mb-1 flex items-baseline justify-between font-mono text-xs">
              <span className="text-text-muted">总成本</span>
              <span className="font-bold tabular-nums text-text-primary">${totalCost.toFixed(4)}</span>
            </div>
            {totalCost > 0 ? (
              <>
                <div className="flex h-3 overflow-hidden rounded-sm bg-bg-secondary">
                  {sources.map(([source, cost]) => (
                    <div
                      key={source}
                      className={SOURCE_LABELS[source]?.color ?? 'bg-text-muted/40'}
                      style={{ flex: cost }}
                      title={`${SOURCE_LABELS[source]?.label ?? source}: $${cost.toFixed(4)}`}
                    />
                  ))}
                </div>
                <div className="mt-1.5 flex flex-wrap gap-3 font-mono text-[10px] text-text-muted">
                  {sources.map(([source, cost]) => (
                    <span key={source} className="flex items-center gap-1.5">
                      <span className={`inline-block h-1.5 w-3 rounded-sm ${SOURCE_LABELS[source]?.color ?? 'bg-text-muted/40'}`} />
                      {SOURCE_LABELS[source]?.label ?? source} ${cost.toFixed(4)}
                      {totalCost > 0 && `（${Math.round((cost / totalCost) * 100)}%）`}
                    </span>
                  ))}
                </div>
              </>
            ) : (
              <p className="py-3 text-center font-mono text-[10px] text-text-muted">窗口期内暂无用量</p>
            )}
          </div>

          <h3 className="mt-5 font-mono text-xs text-text-secondary">消耗 Top 用户</h3>
          <div className="mt-2 space-y-1.5">
            {topUsers.length === 0 && <p className="py-3 text-center text-xs text-text-muted">暂无记录</p>}
            {topUsers.map((u) => (
              <div key={u.user_id} className="flex items-center gap-2 font-mono text-[10px]">
                <span className="w-40 shrink-0 truncate text-text-secondary" title={u.email ?? u.user_id}>
                  {u.email ?? u.user_id}
                </span>
                <div className="h-2 rounded-sm bg-warm-orange/60" style={{ width: `${(u.cost_usd / maxUserCost) * 50}%`, minWidth: '0.25rem' }} />
                <span className="tabular-nums text-text-muted">${u.cost_usd.toFixed(4)} · {u.records} 笔</span>
              </div>
            ))}
          </div>
        </>
      )}
    </PanelShell>
  )
}
