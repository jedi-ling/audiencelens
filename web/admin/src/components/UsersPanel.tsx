import { useCallback, useEffect, useState } from 'react'
import { Users } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminUser } from '@/lib/types'
import { Pager } from './Pager'

const PAGE_SIZE = 20
/* 兜底列表：套餐真实清单以 /api/admin/plans 为准（挂载后拉取覆盖），
   这份静态值只在请求失败时保证下拉不至于空。 */
const PLAN_OPTIONS_FALLBACK = ['free', 'pro', 'team']

/** 用户管理：套餐调整立即影响配额校验，停用立即让该用户的 token 失效（登录也被拒）。 */
export function UsersPanel() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [q, setQ] = useState('')
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [planOptions, setPlanOptions] = useState<string[]>(PLAN_OPTIONS_FALLBACK)

  // 套餐清单从 /api/admin/plans 拉，和 PlansPanel 同一事实源；失败就保持兜底列表
  useEffect(() => {
    void (async () => {
      try {
        const ids = (await adminApi.plans()).plans.map((p) => p.id)
        if (ids.length > 0) setPlanOptions(ids)
      } catch {
        /* 拉取失败静默保持兜底，不打断用户列表本身的使用 */
      }
    })()
  }, [])

  const load = useCallback(async () => {
    try {
      const result = await adminApi.listUsers({ q: q || undefined, limit: PAGE_SIZE, offset })
      setUsers(result.users)
      setTotal(result.total)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [q, offset])

  useEffect(() => {
    void load()
  }, [load])

  const update = async (
    id: string,
    body: { plan?: string; is_active?: boolean; token_quota_total?: number },
  ) => {
    setPending(id)
    setError(null)
    try {
      await adminApi.updateUser(id, body)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '更新失败')
    } finally {
      setPending(null)
    }
  }

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <Users className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
          用户管理
          <span className="font-mono text-[10px] font-normal text-text-muted">改套餐/停用立即生效</span>
        </h2>
        <input
          value={q}
          onChange={(e) => { setOffset(0); setQ(e.target.value) }}
          placeholder="按邮箱搜索"
          className="ml-auto w-44 rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary placeholder-text-muted outline-none focus:border-brand-primary"
        />
      </div>

      {error && <p className="mt-2 font-mono text-xs text-severity-critical">{error}</p>}

      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left font-mono text-xs">
          <thead>
            <tr className="text-[10px] uppercase tracking-wide text-text-muted">
              <th className="py-2 pr-3 font-normal">邮箱</th>
              <th className="py-2 pr-3 font-normal">套餐</th>
              <th className="py-2 pr-3 font-normal">评审数</th>
              <th className="py-2 pr-3 font-normal">累计成本</th>
              <th className="py-2 pr-3 font-normal">累计 Token</th>
              <th className="py-2 pr-3 font-normal" title="留空=跟随全局 AL_QUOTA_TOKENS_TOTAL">体验额度</th>
              <th className="py-2 pr-3 font-normal">注册时间</th>
              <th className="py-2 font-normal">状态</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {users.length === 0 && (
              <tr>
                <td colSpan={8} className="py-6 text-center text-text-muted">暂无注册用户</td>
              </tr>
            )}
            {users.map((u) => (
              <tr key={u.id} className={u.is_active ? '' : 'opacity-50'}>
                <td className="max-w-[200px] truncate py-2 pr-3 text-text-primary" title={u.email}>
                  {u.email}
                </td>
                <td className="py-2 pr-3">
                  <select
                    value={u.plan}
                    disabled={pending === u.id}
                    onChange={(e) => void update(u.id, { plan: e.target.value })}
                    className="rounded-md border border-border bg-bg-secondary px-1.5 py-0.5 text-xs text-text-primary outline-none focus:border-brand-primary"
                  >
                    {/* 用户当前套餐若不在清单里（历史遗留值），补一项以免 select 显示错乱 */}
                    {(planOptions.includes(u.plan) ? planOptions : [...planOptions, u.plan]).map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </td>
                <td className="py-2 pr-3 tabular-nums text-text-secondary">{u.reviews_total}</td>
                <td className="py-2 pr-3 tabular-nums text-text-secondary">${u.cost_usd_total.toFixed(4)}</td>
                <td
                  className="py-2 pr-3 tabular-nums text-text-secondary"
                  title={`输入 ${u.input_tokens_total.toLocaleString('en-US')} · 输出 ${u.output_tokens_total.toLocaleString('en-US')}`}
                >
                  {u.tokens_total.toLocaleString('en-US')}
                </td>
                <td className="py-2 pr-3">
                  {/* 三态输入：留空 = 跟随全局（后端收 -1 清除覆盖），填数字 = 该用户专属上限。
                      不用下拉/开关是因为运营真正要做的动作就是"给这个人多少"，
                      一个数字框最直接；占位符里写明留空的含义，避免"清空=0"的误解。 */}
                  <input
                    defaultValue={u.token_quota_total ?? ''}
                    placeholder="跟随全局"
                    disabled={pending === u.id}
                    onBlur={(e) => {
                      const raw = e.target.value.trim()
                      const next = raw === '' ? -1 : Number(raw)
                      if (raw !== '' && (!Number.isFinite(next) || next < 0)) {
                        e.target.value = String(u.token_quota_total ?? '')
                        return
                      }
                      // 没变就别发请求——onBlur 每次失焦都会触发，
                      // 不判断的话点一下表格就写一条审计日志。
                      const current = u.token_quota_total ?? -1
                      if (next === current) return
                      void update(u.id, { token_quota_total: next })
                    }}
                    className="w-28 rounded border border-border bg-bg-secondary px-1.5 py-0.5 text-right font-mono text-xs tabular-nums text-text-primary placeholder-text-muted outline-none focus:border-brand-primary disabled:opacity-50"
                  />
                </td>
                <td className="py-2 pr-3 text-text-muted">
                  {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                </td>
                <td className="py-2">
                  <button
                    onClick={() => void update(u.id, { is_active: !u.is_active })}
                    disabled={pending === u.id}
                    className={`rounded-md px-2 py-0.5 text-[10px] transition-colors disabled:opacity-50 ${
                      u.is_active
                        ? 'bg-brand-primary/10 text-brand-primary hover:bg-severity-critical/10 hover:text-severity-critical'
                        : 'bg-severity-critical/10 text-severity-critical hover:bg-brand-primary/10 hover:text-brand-primary'
                    }`}
                    title={u.is_active ? '点击停用' : '点击启用'}
                  >
                    {u.is_active ? '正常' : '已停用'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Pager total={total} offset={offset} pageSize={PAGE_SIZE} onChange={setOffset} />
    </section>
  )
}
