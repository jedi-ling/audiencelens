import { useCallback, useEffect, useState } from 'react'
import { ListChecks } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminJob, AdminJobDetail } from '@/lib/types'
import { StatusDot } from './StatusDot'
import { DetailDrawer, DetailField, DetailJson } from './DetailDrawer'
import { Pager } from './Pager'

const PAGE_SIZE = 20

export function JobsPanel() {
  const [jobs, setJobs] = useState<AdminJob[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState('')
  const [userId, setUserId] = useState('')
  const [selected, setSelected] = useState<AdminJobDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const result = await adminApi.listJobs({
        status: status || undefined,
        userId: userId || undefined,
        limit: PAGE_SIZE,
        offset,
      })
      setJobs(result.jobs)
      setTotal(result.total)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [status, userId, offset])

  useEffect(() => {
    void load()
  }, [load])

  const openDetail = async (id: string) => {
    try {
      setSelected(await adminApi.jobDetail(id))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载详情失败')
    }
  }

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <ListChecks className="h-4 w-4 text-cyan" strokeWidth={1.5} />
          任务
        </h2>
        <input
          value={userId}
          onChange={(e) => { setOffset(0); setUserId(e.target.value) }}
          placeholder="按 user_id 过滤"
          className="ml-auto w-32 rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary placeholder-text-muted outline-none focus:border-brand-primary"
        />
        <select
          value={status}
          onChange={(e) => { setOffset(0); setStatus(e.target.value) }}
          className="rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none"
        >
          <option value="">全部状态</option>
          <option value="queued">queued</option>
          <option value="running">running</option>
          <option value="done">done</option>
          <option value="failed">failed</option>
        </select>
      </div>

      {error && <p className="mt-2 font-mono text-xs text-severity-critical">{error}</p>}

      <ul className="mt-3 max-h-80 space-y-2 overflow-y-auto">
        {jobs.length === 0 && <li className="py-4 text-center text-xs text-text-muted">无记录</li>}
        {jobs.map((j) => (
          <li
            key={j.id}
            role="button"
            tabIndex={0}
            onClick={() => void openDetail(j.id)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                void openDetail(j.id)
              }
            }}
            className="cursor-pointer rounded-md border border-border bg-bg-primary/60 px-3 py-2 font-mono text-xs hover:border-brand-primary/30 transition-colors"
          >
            <div className="flex items-center gap-2">
              <StatusDot status={j.status} />
              <span className="text-text-primary">{j.kind}</span>
              <span className="ml-auto text-text-muted">{j.progress}%</span>
            </div>
            <div className="mt-1 truncate text-text-muted">{j.ref_id ?? '—'}</div>
            {j.error_message && <div className="mt-1 truncate text-severity-critical">{j.error_message}</div>}
          </li>
        ))}
      </ul>

      <Pager total={total} offset={offset} pageSize={PAGE_SIZE} onChange={setOffset} />

      {selected && (
        <DetailDrawer title={`任务 ${selected.id}`} onClose={() => setSelected(null)}>
          <DetailField label="状态" value={selected.status} />
          <DetailField label="进度" value={`${selected.progress}%`} />
          <DetailField label="用户" value={selected.user_id ?? '—'} />
          <DetailField label="关联 ID" value={selected.ref_id ?? '—'} />
          <DetailField label="创建时间" value={selected.created_at ? new Date(selected.created_at).toLocaleString() : '—'} />
          <DetailField label="开始时间" value={selected.started_at ? new Date(selected.started_at).toLocaleString() : '—'} />
          <DetailField label="结束时间" value={selected.finished_at ? new Date(selected.finished_at).toLocaleString() : '—'} />
          {selected.error_message && <DetailField label="错误信息" value={<span className="text-severity-critical">{selected.error_message}</span>} />}
          <DetailJson label="Payload" value={selected.payload} />
        </DetailDrawer>
      )}
    </section>
  )
}
