import { useCallback, useEffect, useState } from 'react'
import { Tags } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminPlan, PlanEditableField } from '@/lib/types'

const FIELD_LABELS: Record<PlanEditableField, string> = {
  price_usd_month: '月价 (USD)',
  reviews_per_day: '每日评审上限',
  cost_usd_per_day: '每日成本上限 (USD)',
}

export function PlansPanel() {
  const [plans, setPlans] = useState<AdminPlan[]>([])
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setPlans((await adminApi.plans()).plans)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const apply = async (planId: string, field: PlanEditableField, value: number) => {
    const token = `${planId}.${field}`
    setPending(token)
    setError(null)
    try {
      await adminApi.setPlanField(planId, field, value)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setPending(null)
    }
  }

  const reset = async (planId: string, field: PlanEditableField) => {
    const token = `${planId}.${field}`
    setPending(token)
    setError(null)
    try {
      await adminApi.resetPlanField(planId, field)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '重置失败')
    } finally {
      setPending(null)
    }
  }

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
        <Tags className="h-4 w-4 text-neon-green" strokeWidth={1.5} />
        套餐
        <span className="font-mono text-[10px] font-normal text-text-muted">可编辑，改动无需重启</span>
      </h2>
      {error && <p className="mt-2 font-mono text-xs text-severity-critical">{error}</p>}

      <div className="mt-4 space-y-4">
        {plans.map((plan) => (
          <div key={plan.id} className="rounded-lg border border-border bg-bg-primary/60 p-3">
            <div className="mb-2 flex items-center gap-2">
              <span className="font-mono text-sm font-semibold text-text-primary">{plan.name}</span>
              <span className="font-mono text-[10px] text-text-muted">{plan.id}</span>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {plan.editable_fields.map((field) => {
                const token = `${plan.id}.${field}`
                const overridden = plan.overridden_fields.includes(field)
                return (
                  <div key={field} className="flex items-center gap-1.5">
                    <div className="min-w-0 flex-1">
                      <div className="text-[10px] text-text-muted">{FIELD_LABELS[field]}</div>
                      <input
                        key={`${token}-${plan[field]}`}
                        type="number"
                        defaultValue={plan[field]}
                        disabled={pending === token}
                        onBlur={(e) => {
                          const v = parseFloat(e.target.value)
                          if (!Number.isNaN(v) && v !== plan[field]) void apply(plan.id, field, v)
                        }}
                        className="w-full rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none focus:border-neon-green"
                      />
                    </div>
                    {overridden && (
                      <button
                        onClick={() => void reset(plan.id, field)}
                        disabled={pending === token}
                        title={`env 默认 ${plan.env_default[field]}`}
                        className="shrink-0 self-end rounded-md border border-border px-1.5 py-1 font-mono text-[10px] text-warm-orange hover:border-warm-orange/40 transition-colors disabled:opacity-50"
                      >
                        重置
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
