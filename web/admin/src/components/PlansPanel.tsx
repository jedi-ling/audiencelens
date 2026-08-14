import { useCallback, useEffect, useState } from 'react'
import { Tags } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminPlan, PlanEditableField } from '@/lib/types'
import { PanelShell, PanelError, PanelEmpty, PanelLoading } from './panel'

const FIELD_LABELS: Record<PlanEditableField, string> = {
  price_usd_month: '月价 (USD)',
  reviews_per_day: '每日评审上限',
  cost_usd_per_day: '每日成本上限 (USD)',
}

/* 三个字段全量列表：free 档的每日限额不在 editable_fields 里（由「设置」页的
   quota_free_* 管理），后端约定用 editable_fields 缺项来推断，缺的渲染成只读并指路设置页。 */
const ALL_FIELDS = Object.keys(FIELD_LABELS) as PlanEditableField[]

export function PlansPanel() {
  const [plans, setPlans] = useState<AdminPlan[]>([])
  const [loaded, setLoaded] = useState(false)
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setPlans((await adminApi.plans()).plans)
      setLoaded(true)
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
    <PanelShell icon={Tags} title="套餐" hint="可编辑，改动无需重启">
      <PanelError>{error}</PanelError>

      {!loaded && !error && <PanelLoading />}

      <div className="mt-4 space-y-4">
        {loaded && plans.length === 0 && <PanelEmpty />}
        {plans.map((plan) => (
          <div key={plan.id} className="rounded-lg border border-border bg-bg-primary/60 p-3">
            <div className="mb-2 flex items-center gap-2">
              <span className="font-mono text-sm font-semibold text-text-primary">{plan.name}</span>
              <span className="font-mono text-[10px] text-text-muted">{plan.id}</span>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {ALL_FIELDS.map((field) => {
                const token = `${plan.id}.${field}`
                const overridden = plan.overridden_fields.includes(field)
                if (!plan.editable_fields.includes(field)) {
                  // 只读展示生效值：后端返回的就是含 quota_free_* 覆盖的真实值，
                  // 给输入框会让人以为在这里能改，实际改了会被 API 拒绝。
                  return (
                    <div key={field} className="min-w-0">
                      <div className="text-[10px] text-text-muted">{FIELD_LABELS[field]}</div>
                      <div
                        title="此项由「设置」页的免费额度开关管理，此处只读"
                        className="w-full rounded-md border border-dashed border-border bg-bg-primary/40 px-2 py-1 font-mono text-xs text-text-secondary"
                      >
                        {plan[field]}
                        <span className="ml-1.5 text-[10px] text-text-muted">在「设置」页调整</span>
                      </div>
                    </div>
                  )
                }
                return (
                  <div key={field} className="flex items-center gap-1.5">
                    <div className="min-w-0 flex-1">
                      <div className="text-[10px] text-text-muted">{FIELD_LABELS[field]}</div>
                      <input
                        key={`${token}-${plan[field]}`}
                        type="number"
                        defaultValue={plan[field]}
                        disabled={pending === token}
                        aria-label={FIELD_LABELS[field]}
                        onBlur={(e) => {
                          const v = parseFloat(e.target.value)
                          if (!Number.isNaN(v) && v !== plan[field]) void apply(plan.id, field, v)
                        }}
                        className="w-full rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none focus:border-brand-primary"
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
    </PanelShell>
  )
}
