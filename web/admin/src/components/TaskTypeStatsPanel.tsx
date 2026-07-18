import { useCallback, useEffect, useState } from 'react'
import { BarChart3 } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminPersonaPackStat, AdminTaskTypeStat } from '@/lib/types'

/** 任务类型分布——水平条形图（完成/失败/其它 三色分段），无第三方图表库。 */
export function TaskTypeStatsPanel() {
  const [taskTypes, setTaskTypes] = useState<AdminTaskTypeStat[]>([])
  const [packs, setPacks] = useState<AdminPersonaPackStat[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [tt, pp] = await Promise.all([adminApi.statsTaskTypes(), adminApi.statsPersonaPacks()])
      setTaskTypes(tt.task_types)
      setPacks(pp.persona_packs)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const maxTotal = Math.max(1, ...taskTypes.map((t) => t.total))
  const maxPack = Math.max(1, ...packs.map((p) => p.total))

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
        <BarChart3 className="h-4 w-4 text-cyan" strokeWidth={1.5} />
        任务类型 / 人格包分布
      </h2>
      {error && <p className="mt-2 font-mono text-xs text-severity-critical">{error}</p>}

      <div className="mt-4 space-y-2">
        {taskTypes.length === 0 && <p className="py-4 text-center text-xs text-text-muted">暂无评审数据</p>}
        {taskTypes.map((t) => {
          const other = t.total - t.completed - t.failed
          const width = (t.total / maxTotal) * 100
          return (
            <div key={t.task_type}>
              <div className="mb-0.5 flex items-baseline justify-between font-mono text-[10px]">
                <span className="text-text-secondary">{t.task_type}</span>
                <span className="text-text-muted">
                  {t.total} 次 · ${t.cost_usd.toFixed(2)}
                </span>
              </div>
              <div className="flex h-2.5 overflow-hidden rounded-sm bg-bg-secondary" style={{ width: `${width}%`, minWidth: '2rem' }}>
                {t.completed > 0 && (
                  <div className="bg-neon-green/70" style={{ flex: t.completed }} title={`完成 ${t.completed}`} />
                )}
                {t.failed > 0 && (
                  <div className="bg-severity-critical/70" style={{ flex: t.failed }} title={`失败 ${t.failed}`} />
                )}
                {other > 0 && (
                  <div className="bg-text-muted/40" style={{ flex: other }} title={`其它 ${other}`} />
                )}
              </div>
            </div>
          )
        })}
      </div>

      {taskTypes.length > 0 && (
        <div className="mt-2 flex gap-4 font-mono text-[10px] text-text-muted">
          <span className="flex items-center gap-1.5"><span className="inline-block h-1.5 w-3 rounded-sm bg-neon-green/70" />完成</span>
          <span className="flex items-center gap-1.5"><span className="inline-block h-1.5 w-3 rounded-sm bg-severity-critical/70" />失败</span>
          <span className="flex items-center gap-1.5"><span className="inline-block h-1.5 w-3 rounded-sm bg-text-muted/40" />进行中/其它</span>
        </div>
      )}

      {packs.length > 0 && (
        <>
          <h3 className="mt-5 font-mono text-xs text-text-secondary">人格包使用量</h3>
          <div className="mt-2 space-y-1.5">
            {packs.map((p) => (
              <div key={p.persona_pack} className="flex items-center gap-2 font-mono text-[10px]">
                <span className="w-36 shrink-0 truncate text-text-secondary">{p.persona_pack}</span>
                <div className="h-2 rounded-sm bg-cyan/60" style={{ width: `${(p.total / maxPack) * 60}%`, minWidth: '0.5rem' }} />
                <span className="text-text-muted">{p.total}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  )
}
