import { useCallback, useEffect, useState } from 'react'
import { FileClock } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminReviewDetail, AdminReviewRow } from '@/lib/types'
import { StatusDot } from './StatusDot'
import { DetailDrawer, DetailField, DetailJson } from './DetailDrawer'
import { Pager } from './Pager'

const PAGE_SIZE = 20

export function ReviewsPanel() {
  const [reviews, setReviews] = useState<AdminReviewRow[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState('')
  const [userId, setUserId] = useState('')
  const [selected, setSelected] = useState<AdminReviewDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const result = await adminApi.listReviews({
        status: status || undefined,
        userId: userId || undefined,
        limit: PAGE_SIZE,
        offset,
      })
      setReviews(result.reviews)
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
      setSelected(await adminApi.reviewDetail(id))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载详情失败')
    }
  }

  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const removeSelected = async () => {
    if (!selected) return
    setDeleting(true)
    try {
      await adminApi.deleteReview(selected.id)
      setSelected(null)
      setConfirmingDelete(false)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <FileClock className="h-4 w-4 text-cyan" strokeWidth={1.5} />
          评审
        </h2>
        <input
          value={userId}
          onChange={(e) => { setOffset(0); setUserId(e.target.value) }}
          placeholder="按 user_id 过滤"
          className="ml-auto w-32 rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary placeholder-text-muted outline-none focus:border-neon-green"
        />
        <select
          value={status}
          onChange={(e) => { setOffset(0); setStatus(e.target.value) }}
          className="rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none"
        >
          <option value="">全部状态</option>
          <option value="pending">pending</option>
          <option value="running">running</option>
          <option value="completed">completed</option>
          <option value="failed">failed</option>
        </select>
      </div>

      {error && <p className="mt-2 font-mono text-xs text-severity-critical">{error}</p>}

      <ul className="mt-3 max-h-80 space-y-2 overflow-y-auto">
        {reviews.length === 0 && <li className="py-4 text-center text-xs text-text-muted">无记录</li>}
        {reviews.map((r) => (
          <li
            key={r.id}
            onClick={() => void openDetail(r.id)}
            className="cursor-pointer rounded-md border border-border bg-bg-primary/60 px-3 py-2 font-mono text-xs hover:border-neon-green/30 transition-colors"
          >
            <div className="flex items-center gap-2">
              <StatusDot status={r.status} />
              <span className="truncate text-text-primary">{r.target_title || r.task_type}</span>
              <span className="ml-auto shrink-0 text-text-muted">${r.total_cost_usd.toFixed(3)}</span>
            </div>
            <div className="mt-1 flex items-center gap-2 text-text-muted">
              <span>{r.user_id}</span>
              <span>·</span>
              <span>{r.task_type}</span>
              {r.tokens_total > 0 && (
                <>
                  <span>·</span>
                  <span title={`输入 ${r.input_tokens.toLocaleString('en-US')} · 输出 ${r.output_tokens.toLocaleString('en-US')}`}>
                    {r.tokens_total.toLocaleString('en-US')} tok
                  </span>
                </>
              )}
            </div>
            {r.error_message && <div className="mt-1 truncate text-severity-critical">{r.error_message}</div>}
          </li>
        ))}
      </ul>

      <Pager total={total} offset={offset} pageSize={PAGE_SIZE} onChange={setOffset} />

      {selected && (
        <DetailDrawer title={`评审 ${selected.id}`} onClose={() => { setSelected(null); setConfirmingDelete(false) }}>
          <div className="mb-4 flex justify-end">
            {confirmingDelete ? (
              <span className="flex items-center gap-2 font-mono text-xs">
                <span className="text-severity-critical">确认删除？评审与判断留档一并删除，用量账不删。</span>
                <button
                  onClick={() => void removeSelected()}
                  disabled={deleting}
                  className="rounded-md bg-severity-critical px-2.5 py-1 font-semibold text-bg-primary disabled:opacity-50"
                >
                  {deleting ? '删除中…' : '确认删除'}
                </button>
                <button
                  onClick={() => setConfirmingDelete(false)}
                  className="rounded-md border border-border px-2.5 py-1 text-text-secondary"
                >
                  取消
                </button>
              </span>
            ) : (
              <button
                onClick={() => setConfirmingDelete(true)}
                className="rounded-md bg-severity-critical/10 px-2.5 py-1 font-mono text-xs text-severity-critical hover:bg-severity-critical/20 transition-colors"
              >
                删除评审
              </button>
            )}
          </div>
          <DetailField label="标题" value={selected.target_title ?? '—'} />
          <DetailField label="状态" value={selected.status} />
          <DetailField label="任务类型" value={selected.task_type} />
          <DetailField label="模式" value={selected.mode} />
          <DetailField label="人格包" value={selected.persona_pack ?? '—'} />
          <DetailField label="用户" value={selected.user_id ?? '—'} />
          <DetailField label="成本" value={`$${selected.total_cost_usd.toFixed(4)}`} />
          <DetailField
            label="Token 用量"
            value={
              selected.tokens_total > 0
                ? `${selected.tokens_total.toLocaleString('en-US')}（输入 ${selected.input_tokens.toLocaleString('en-US')} · 输出 ${selected.output_tokens.toLocaleString('en-US')}）`
                : '—'
            }
          />
          <DetailField label="创建时间" value={selected.created_at ? new Date(selected.created_at).toLocaleString() : '—'} />
          <DetailField label="完成时间" value={selected.completed_at ? new Date(selected.completed_at).toLocaleString() : '—'} />
          {selected.error_message && <DetailField label="错误信息" value={<span className="text-severity-critical">{selected.error_message}</span>} />}
          <DetailJson label="Report JSON" value={selected.report_json} />
          <DetailJson label="Calibration" value={selected.calibration} />
        </DetailDrawer>
      )}
    </section>
  )
}
