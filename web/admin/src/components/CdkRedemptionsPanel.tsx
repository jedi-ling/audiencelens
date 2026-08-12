import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Receipt } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminCdkRedemptionList } from '@/lib/types'
import { Pager } from './Pager'
import { PanelShell, PanelError, PanelEmpty, PanelLoading } from './panel'

const PAGE = 20

/**
 * CDK 兑换记录。
 *
 * 在这个面板之前，CdkRedemption 表只被 cdk_service（去重）和 user_data_service
 * （用户自己导出数据）读过——后台一条都看不到。运营只能看见每个码的 used_count，
 * 于是"我兑了码但次数没到账"这类客诉完全无法调查：你不知道是谁兑的、什么时候兑的、
 * 更不知道 credit_ledger 里有没有真的进账。
 *
 * 「入账」那一列就是为这个客诉而存在的：它是 credit_ledger 里对应的求和，
 * 跟「发放」对不上就说明码消耗掉了但次数没落到用户头上。
 */
export function CdkRedemptionsPanel() {
  const [data, setData] = useState<AdminCdkRedemptionList | null>(null)
  const [code, setCode] = useState('')
  const [userId, setUserId] = useState('')
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setError(null)
      setData(
        await adminApi.cdkRedemptions({
          code: code.trim() || undefined,
          userId: userId.trim() || undefined,
          limit: PAGE,
          offset,
        }),
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [code, userId, offset])

  useEffect(() => {
    void load()
  }, [load])

  const rows = data?.redemptions ?? []
  const mismatched = rows.filter((r) => r.credited_in_ledger !== r.credits)

  return (
    <PanelShell
      icon={Receipt}
      iconTone="text-warm-orange"
      title="兑换记录"
      hint={data ? `共 ${data.total} 条` : undefined}
      actions={
        <>
          <input
            value={code}
            onChange={(e) => {
              setCode(e.target.value)
              setOffset(0)
            }}
            placeholder="按兑换码筛选"
            className="w-36 rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none placeholder:text-text-muted"
          />
          <input
            value={userId}
            onChange={(e) => {
              setUserId(e.target.value)
              setOffset(0)
            }}
            placeholder="按 user_id 筛选"
            className="w-40 rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none placeholder:text-text-muted"
          />
        </>
      }
    >
      <PanelError>{error}</PanelError>

      {mismatched.length > 0 && (
        <p className="mt-3 flex items-center gap-2 rounded-lg border border-severity-critical/40 bg-severity-critical/5 px-3 py-2 font-mono text-[11px] text-severity-critical">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
          本页有 {mismatched.length} 条「发放」与「入账」对不上——码消耗掉了但次数可能没到用户账上。
        </p>
      )}

      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[720px] font-mono text-[11px]">
          <thead className="text-text-muted">
            <tr className="border-b border-border">
              <th className="py-1.5 text-left font-normal">兑换码</th>
              <th className="py-1.5 text-left font-normal">用户</th>
              <th className="py-1.5 text-right font-normal">发放</th>
              <th className="py-1.5 text-right font-normal">入账</th>
              <th className="py-1.5 text-left font-normal">备注</th>
              <th className="py-1.5 text-right font-normal">时间</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const ok = r.credited_in_ledger === r.credits
              return (
                <tr key={r.id} className="border-b border-border/50">
                  <td className="py-1.5 text-text-primary">{r.code}</td>
                  <td className="py-1.5 text-text-muted">
                    {r.user_email ?? (
                      <span title={r.user_id}>
                        {r.user_id.slice(0, 12)}… <span className="text-warm-orange">(访客)</span>
                      </span>
                    )}
                  </td>
                  <td className="py-1.5 text-right text-text-primary">{r.credits}</td>
                  <td
                    className={`py-1.5 text-right ${ok ? 'text-brand-primary' : 'text-severity-critical'}`}
                    title={ok ? '与发放量一致' : 'credit_ledger 里对不上——次数可能没到账'}
                  >
                    {r.credited_in_ledger ?? '无记录'}
                  </td>
                  <td className="max-w-[160px] truncate py-1.5 text-text-muted">{r.note ?? '—'}</td>
                  <td className="py-1.5 text-right text-text-muted">
                    {r.created_at?.slice(0, 16).replace('T', ' ') ?? '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {!data && !error && <PanelLoading />}

      {rows.length === 0 && data && <PanelEmpty />}

      {data && <Pager offset={offset} pageSize={PAGE} total={data.total} onChange={setOffset} />}
    </PanelShell>
  )
}
