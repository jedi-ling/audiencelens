import { useCallback, useEffect, useState } from 'react'
import { FileClock } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminAuditLogEntry } from '@/lib/types'

const ACTION_LABELS: Record<string, string> = {
  'setting.update': '修改配置',
  'setting.reset': '重置配置',
  'server_key.set': '设置平台 Key',
  'server_key.delete': '删除平台 Key',
  'plan.override': '覆盖套餐字段',
  'plan.reset': '重置套餐字段',
  // 以下动作名逐一核对自 web/backend/app/api/admin.py 里 audit_log_service.record 的调用点
  'user.update': '修改用户',
  'cdk.generate': '生成兑换码',
  'cdk.disable': '停用兑换码',
  'review.delete': '删除评审',
  'mail.test': '测试邮件发送',
}

/** 谁在何时改了哪个配置/套餐/平台 Key——目前只有单一共享令牌，不区分具体管理员身份。 */
export function AuditLogPanel() {
  const [entries, setEntries] = useState<AdminAuditLogEntry[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setEntries((await adminApi.auditLog(50)).entries)
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
        <FileClock className="h-4 w-4 text-cyan" strokeWidth={1.5} />
        操作审计
      </h2>
      {error && <p className="mt-2 font-mono text-xs text-severity-critical">{error}</p>}
      <ul className="mt-3 max-h-80 space-y-2 overflow-y-auto">
        {entries.length === 0 && <li className="py-4 text-center text-xs text-text-muted">暂无记录</li>}
        {entries.map((e) => (
          <li key={e.id} className="rounded-md border border-border bg-bg-primary/60 px-3 py-2 font-mono text-xs">
            <div className="flex items-center gap-2">
              <span className="text-text-primary">{ACTION_LABELS[e.action] ?? e.action}</span>
              {e.target && <span className="text-text-muted">{e.target}</span>}
              <span className="ml-auto shrink-0 text-[10px] text-text-muted">
                {e.created_at ? new Date(e.created_at).toLocaleString() : '—'}
              </span>
            </div>
            {e.detail != null && (
              <div className="mt-1 truncate text-text-secondary">{JSON.stringify(e.detail)}</div>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
