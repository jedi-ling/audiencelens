import { useCallback, useEffect, useState } from 'react'
import { ListChecks } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminJob, AdminJobDetail } from '@/lib/types'
import { StatusDot } from './StatusDot'
import { DetailDrawer, DetailField, DetailJson } from './DetailDrawer'
import { Pager } from './Pager'
import { PanelShell, PanelError, PanelLoading, EmptyRow } from './panel'

const PAGE_SIZE = 20

/** 终态：这些行没有可执行的运维操作，后端对它们一律 400。 */
const TERMINAL = ['done', 'failed', 'cancelled']

export function JobsPanel() {
  const [jobs, setJobs] = useState<AdminJob[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState('')
  const [userId, setUserId] = useState('')
  const [selected, setSelected] = useState<AdminJobDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)

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
      setLoaded(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [status, userId, offset])

  useEffect(() => {
    void load()
  }, [load])

  const act = async (id: string, op: 'cancel' | 'force-fail') => {
    setBusyId(id)
    setError(null)
    try {
      if (op === 'cancel') await adminApi.cancelJob(id)
      else await adminApi.forceFailJob(id)
      await load()
    } catch (e) {
      // 后端对 running 的取消返回 400 并说明理由，那条消息本身就是给运营看的，直接透出
      setError(e instanceof Error ? e.message : '操作失败')
    } finally {
      setBusyId(null)
    }
  }

  const openDetail = async (id: string) => {
    try {
      setSelected(await adminApi.jobDetail(id))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载详情失败')
    }
  }

  return (
    <PanelShell
      icon={ListChecks}
      iconTone="text-cyan"
      title="任务"
      actions={
        <>
          <input
            value={userId}
            onChange={(e) => { setOffset(0); setUserId(e.target.value) }}
            placeholder="按 user_id 过滤"
            className="w-32 rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary placeholder-text-muted outline-none focus:border-brand-primary"
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
            {/* 后端 Job.status 注释明确有 cancelled（job_service 取消链路会写入），筛选项要跟全 */}
            <option value="cancelled">cancelled</option>
          </select>
        </>
      }
    >
      <PanelError>{error}</PanelError>

      {!loaded && !error && <PanelLoading />}

      <ul className="mt-3 max-h-80 space-y-2 overflow-y-auto">
        {loaded && jobs.length === 0 && <EmptyRow />}
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

            {/* 运维操作只在非终态的行上出现。stopPropagation 是必需的——
                外层 li 整块是"打开详情"的点击区，不拦住的话点按钮会同时弹出抽屉。 */}
            {!TERMINAL.includes(j.status) && (
              <div className="mt-2 flex gap-2" onClick={(e) => e.stopPropagation()}>
                {j.status === 'queued' && (
                  <button
                    onClick={() => void act(j.id, 'cancel')}
                    disabled={busyId === j.id}
                    className="rounded border border-border px-2 py-0.5 text-[10px] text-text-muted transition-colors hover:border-brand-primary/40 hover:text-brand-primary disabled:opacity-40"
                  >
                    取消
                  </button>
                )}
                <button
                  onClick={() => void act(j.id, 'force-fail')}
                  disabled={busyId === j.id}
                  title="不会真的停下后台线程，但会把这行推到终态，让统计和用户前端解锁"
                  className="rounded border border-severity-critical/40 px-2 py-0.5 text-[10px] text-severity-critical transition-colors hover:bg-severity-critical/10 disabled:opacity-40"
                >
                  {busyId === j.id ? '处理中…' : '标记为失败'}
                </button>
              </div>
            )}
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
    </PanelShell>
  )
}
