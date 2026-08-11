import { useEffect, useState } from 'react'
import { KeyRound, Receipt, X } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminUserDetail } from '@/lib/types'

const STATUS_COLOR: Record<string, string> = {
  completed: 'text-brand-primary',
  failed: 'text-severity-critical',
  running: 'text-cyan',
  queued: 'text-warm-orange',
}

/**
 * 单个用户的全景抽屉。
 *
 * 用户列表只能回答"这个人跑了多少、花了多少"。出问题时要问的是更细的：
 * 他用的是自己的 key 还是平台的？次数余额跟兑换记录对不对得上？
 * 最近几次是不是都失败了？在此之前这些只能连数据库查。
 */
export function UserDetailDrawer({ userId, onClose }: { userId: string; onClose: () => void }) {
  const [data, setData] = useState<AdminUserDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    setData(null)
    setError(null)
    adminApi
      .userDetail(userId)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e instanceof Error ? e.message : '加载失败'))
    return () => {
      alive = false
    }
  }, [userId])

  // 兑换发放总量 vs 当前余额。对不上不一定是 bug（用掉了也会减），
  // 但两个数放在一起，运营至少能自己判断"是不是根本没到账"。
  const grantedTotal = (data?.cdk_redemptions ?? []).reduce((s, r) => s + r.credits, 0)

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" onClick={onClose}>
      <aside
        className="h-full w-full max-w-2xl overflow-y-auto border-l border-border bg-bg-card p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="truncate font-mono text-sm text-text-primary">
              {data?.email ?? '加载中…'}
            </h2>
            <p className="mt-0.5 font-mono text-[10px] text-text-muted">{userId}</p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded-md border border-border p-1.5 text-text-muted hover:text-text-primary"
          >
            <X className="h-4 w-4" strokeWidth={1.5} />
          </button>
        </div>

        {error && <p className="mt-4 font-mono text-xs text-severity-critical">{error}</p>}

        {data && (
          <>
            <div className="mt-4 grid grid-cols-4 gap-2">
              <Cell label="套餐" value={data.plan} />
              <Cell label="状态" value={data.is_active ? '正常' : '已停用'} bad={!data.is_active} />
              <Cell label="评审总数" value={String(data.reviews.total)} />
              <Cell label="次数余额" value={String(data.credit_balance)} />
            </div>

            <Section title="评审状态分布">
              {Object.keys(data.reviews.by_status).length === 0 ? (
                <Empty>这个用户还没有跑过任何评审</Empty>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {Object.entries(data.reviews.by_status).map(([status, n]) => (
                    <span
                      key={status}
                      className={`rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-[11px] ${
                        STATUS_COLOR[status] ?? 'text-text-muted'
                      }`}
                    >
                      {status} {n}
                    </span>
                  ))}
                </div>
              )}
            </Section>

            <Section title="用量按 key 来源拆分">
              {data.usage_by_key_source.length === 0 ? (
                <Empty>还没有任何用量记录</Empty>
              ) : (
                <table className="w-full font-mono text-[11px]">
                  <thead className="text-text-muted">
                    <tr className="border-b border-border">
                      <th className="py-1 text-left font-normal">来源</th>
                      <th className="py-1 text-right font-normal">次数</th>
                      <th className="py-1 text-right font-normal">成本</th>
                      <th className="py-1 text-right font-normal">Tokens</th>
                    </tr>
                  </thead>
                  <tbody className="text-text-primary">
                    {data.usage_by_key_source.map((u) => (
                      <tr key={u.key_source} className="border-b border-border/50">
                        <td className="py-1">{u.key_source}</td>
                        <td className="py-1 text-right">{u.count}</td>
                        <td className="py-1 text-right">${u.cost_usd.toFixed(4)}</td>
                        <td className="py-1 text-right">
                          {(u.input_tokens + u.output_tokens).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>

            <Section title="BYOK 密钥" icon={<KeyRound className="h-3.5 w-3.5" strokeWidth={1.5} />}>
              {data.api_keys.length === 0 ? (
                <Empty>没有配置自带密钥——这个用户走的是平台 key</Empty>
              ) : (
                <ul className="space-y-1.5">
                  {data.api_keys.map((k, i) => (
                    <li
                      key={i}
                      className="rounded-md border border-border bg-bg-secondary px-2.5 py-2 font-mono text-[11px]"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-text-primary">
                          {k.provider}
                          {k.model ? ` · ${k.model}` : ''}
                        </span>
                        <span className={k.is_active ? 'text-brand-primary' : 'text-text-muted'}>
                          {k.is_active ? '启用' : '停用'}
                        </span>
                      </div>
                      <p className="mt-0.5 text-text-muted">
                        {k.key_masked}
                        {k.last_used_at ? ` · 最近使用 ${k.last_used_at.slice(0, 10)}` : ' · 从未使用'}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-1.5 font-mono text-[10px] text-text-muted">
                只显示脱敏回显。密钥密文不会经过后台接口——后端刻意不返回 key_ciphertext。
              </p>
            </Section>

            <Section title="兑换记录" icon={<Receipt className="h-3.5 w-3.5" strokeWidth={1.5} />}>
              {data.cdk_redemptions.length === 0 ? (
                <Empty>没有兑换过任何码</Empty>
              ) : (
                <>
                  <ul className="space-y-1">
                    {data.cdk_redemptions.map((r, i) => (
                      <li
                        key={i}
                        className="flex items-center justify-between gap-3 rounded-md bg-bg-secondary px-2.5 py-1.5 font-mono text-[11px]"
                      >
                        <span className="text-text-primary">{r.code}</span>
                        <span className="text-text-muted">
                          +{r.credits} · {r.created_at?.slice(0, 16).replace('T', ' ') ?? '—'}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-1.5 font-mono text-[10px] text-text-muted">
                    累计发放 {grantedTotal} 次，当前余额 {data.credit_balance} 次。
                    {grantedTotal > 0 && data.credit_balance === 0 && ' 余额已用完（或从未到账——查兑换记录页核对流水）。'}
                  </p>
                </>
              )}
            </Section>

            <Section title={`最近评审（${data.reviews.recent.length}）`}>
              {data.reviews.recent.length === 0 ? (
                <Empty>没有评审记录</Empty>
              ) : (
                <ul className="space-y-1">
                  {data.reviews.recent.map((r) => (
                    <li
                      key={r.id}
                      className="rounded-md bg-bg-secondary px-2.5 py-1.5 font-mono text-[11px]"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="min-w-0 flex-1 truncate text-text-primary">
                          {r.target_title || r.task_type}
                        </span>
                        <span className={STATUS_COLOR[r.status] ?? 'text-text-muted'}>{r.status}</span>
                      </div>
                      <p className="mt-0.5 truncate text-text-muted">
                        {r.created_at?.slice(0, 16).replace('T', ' ') ?? '—'} · $
                        {(r.total_cost_usd ?? 0).toFixed(4)} · {r.tokens_total.toLocaleString()} tokens
                        {r.error_message ? ` · ${r.error_message}` : ''}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          </>
        )}
      </aside>
    </div>
  )
}

function Section({
  title,
  icon,
  children,
}: {
  title: string
  icon?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div className="mt-5">
      <p className="mb-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wide text-text-muted">
        {icon}
        {title}
      </p>
      {children}
    </div>
  )
}

function Cell({ label, value, bad }: { label: string; value: string; bad?: boolean }) {
  return (
    <div className="rounded-lg border border-border bg-bg-secondary p-2.5">
      <p className="font-mono text-[10px] text-text-muted">{label}</p>
      <p
        className={`mt-0.5 font-mono text-sm ${bad ? 'text-severity-critical' : 'text-text-primary'}`}
      >
        {value}
      </p>
    </div>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-lg border border-border bg-bg-secondary px-3 py-3 text-center text-xs text-text-muted">
      {children}
    </p>
  )
}
