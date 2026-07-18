import { useCallback, useEffect, useState } from 'react'
import { Users } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminUser } from '@/lib/types'
import { Pager } from './Pager'

const PAGE_SIZE = 20
const PLAN_OPTIONS = ['free', 'pro', 'team']

/** 用户管理：套餐调整立即影响配额校验，停用立即让该用户的 token 失效（登录也被拒）。 */
export function UsersPanel() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [q, setQ] = useState('')
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

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

  const update = async (id: string, body: { plan?: string; is_active?: boolean }) => {
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
          <Users className="h-4 w-4 text-neon-green" strokeWidth={1.5} />
          用户管理
          <span className="font-mono text-[10px] font-normal text-text-muted">改套餐/停用立即生效</span>
        </h2>
        <input
          value={q}
          onChange={(e) => { setOffset(0); setQ(e.target.value) }}
          placeholder="按邮箱搜索"
          className="ml-auto w-44 rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary placeholder-text-muted outline-none focus:border-neon-green"
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
              <th className="py-2 pr-3 font-normal">注册时间</th>
              <th className="py-2 font-normal">状态</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {users.length === 0 && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-text-muted">暂无注册用户</td>
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
                    className="rounded-md border border-border bg-bg-secondary px-1.5 py-0.5 text-xs text-text-primary outline-none focus:border-neon-green"
                  >
                    {PLAN_OPTIONS.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </td>
                <td className="py-2 pr-3 tabular-nums text-text-secondary">{u.reviews_total}</td>
                <td className="py-2 pr-3 tabular-nums text-text-secondary">${u.cost_usd_total.toFixed(4)}</td>
                <td className="py-2 pr-3 text-text-muted">
                  {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                </td>
                <td className="py-2">
                  <button
                    onClick={() => void update(u.id, { is_active: !u.is_active })}
                    disabled={pending === u.id}
                    className={`rounded-md px-2 py-0.5 text-[10px] transition-colors disabled:opacity-50 ${
                      u.is_active
                        ? 'bg-neon-green/10 text-neon-green hover:bg-severity-critical/10 hover:text-severity-critical'
                        : 'bg-severity-critical/10 text-severity-critical hover:bg-neon-green/10 hover:text-neon-green'
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
