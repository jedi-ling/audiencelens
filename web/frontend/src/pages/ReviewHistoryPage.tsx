/**
 * 评审历史列表——之前产品里完全没有这个页面，用户发起评审后除了当次的进度页
 * 链接，没有任何地方能回看"我都评审过什么"。数据走 fetchReviews()（/api/reviews），
 * 后端已按登录身份过滤（见 app/api/__init__.py 的 _check_review_owner），
 * 匿名单机形态下所有匿名请求共享同一个历史列表，这是既有设计，不是本页的 bug。
 */
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { cn } from '@/lib/utils'
import { fetchReviews, deleteReview } from '@/lib/api'
import { TASK_TYPES } from '@/lib/mock-data'
import type { Review, ReviewListItem, ReviewMode } from '@/lib/mock-data'
import {
  History,
  Loader2,
  FileText,
  Trash2,
  DollarSign,
  Clock,
  Zap,
  ListChecks,
  Microscope,
  AlertCircle,
  Inbox,
  FolderOpen,
} from 'lucide-react'

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: '等待中', color: 'text-text-muted', bg: 'bg-bg-secondary' },
  running: { label: '运行中', color: 'text-cyan', bg: 'bg-cyan/10' },
  completed: { label: '已完成', color: 'text-neon-green', bg: 'bg-neon-green/10' },
  failed: { label: '失败', color: 'text-severity-critical', bg: 'bg-severity-critical/10' },
  cancelled: { label: '已取消', color: 'text-text-muted', bg: 'bg-bg-secondary' },
}

const modeBadgeConfig: Record<ReviewMode, { label: string; color: string; bg: string; Icon: typeof Zap }> = {
  quick: { label: '快速', color: 'text-cyan', bg: 'bg-cyan/10', Icon: Zap },
  standard: { label: '标准', color: 'text-neon-green', bg: 'bg-neon-green/10', Icon: ListChecks },
  full: { label: '完整', color: 'text-warm-orange', bg: 'bg-warm-orange/10', Icon: Microscope },
}

function taskTypeName(taskType: string): string {
  return TASK_TYPES.find((t) => t.id === taskType)?.name ?? taskType
}

/** 同 project_key 的评审聚合成"长期评审项目"分组（与 /ask 侧栏同一逻辑）；
 * 列表已按 created_at 倒序，分组内/分组间顺序天然保留。 */
function groupByProject(reviews: ReviewListItem[]): { projects: { key: string; items: ReviewListItem[] }[]; ungrouped: ReviewListItem[] } {
  const order: string[] = []
  const map = new Map<string, ReviewListItem[]>()
  const ungrouped: ReviewListItem[] = []
  for (const r of reviews) {
    if (r.project_key) {
      if (!map.has(r.project_key)) {
        map.set(r.project_key, [])
        order.push(r.project_key)
      }
      map.get(r.project_key)!.push(r)
    } else {
      ungrouped.push(r)
    }
  }
  return { projects: order.map((key) => ({ key, items: map.get(key)! })), ungrouped }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}

export default function ReviewHistoryPage() {
  const navigate = useNavigate()
  const [reviews, setReviews] = useState<ReviewListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await fetchReviews()
      setReviews(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.preventDefault()
    e.stopPropagation()
    if (!window.confirm('确定删除这条评审记录吗？此操作无法撤销。')) return
    setDeletingId(id)
    try {
      await deleteReview(id)
      setReviews((prev) => (prev ? prev.filter((r) => r.id !== id) : prev))
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 animate-fade-in">
      <div className="flex items-center gap-3 mb-6">
        <History className="w-6 h-6 text-neon-green" strokeWidth={1.25} />
        <div>
          <h1 className="text-xl font-semibold text-text-primary">评审历史</h1>
          <p className="text-sm text-text-secondary mt-0.5">你发起过的所有评审，点进去看报告或继续跟进</p>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 text-sm text-severity-critical">
          <AlertCircle className="w-4 h-4 shrink-0" strokeWidth={1.25} />
          {error}
        </div>
      )}

      {reviews === null ? (
        <div className="py-16 text-center">
          <Loader2 className="w-8 h-8 text-cyan animate-spin mx-auto mb-3" strokeWidth={1.25} />
          <p className="text-text-secondary text-sm">加载中...</p>
        </div>
      ) : reviews.length === 0 ? (
        <div className="py-16 text-center rounded-xl border border-border bg-bg-card">
          <Inbox className="w-10 h-10 text-text-muted mx-auto mb-3" strokeWidth={1.25} />
          <p className="text-text-secondary text-sm mb-4">还没有评审记录</p>
          <Link
            to="/ask"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-neon-green text-bg-primary text-sm font-bold hover:bg-neon-green-dim transition-colors"
          >
            发起第一次评审 →
          </Link>
        </div>
      ) : (
        (() => {
          const { projects, ungrouped } = groupByProject(reviews)
          const renderRow = (r: ReviewListItem) => {
            const sc = statusConfig[r.status] ?? statusConfig.pending
            const mb = modeBadgeConfig[r.mode] ?? modeBadgeConfig.standard
            const target = r.status === 'completed' ? `/review/${r.id}/report` : `/review/${r.id}`
            return (
              <div
                key={r.id}
                onClick={() => navigate(target)}
                className="group flex items-center gap-4 p-4 rounded-xl border border-border bg-bg-card hover:border-neon-green/30 hover:bg-bg-card-hover transition-all cursor-pointer"
              >
                <span className={cn('shrink-0 px-2 py-1 rounded text-xs font-medium', sc.bg, sc.color)}>
                  {sc.label}
                </span>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-text-primary truncate">
                      {r.target_title || taskTypeName(r.task_type)}
                    </span>
                    <span
                      className={cn('shrink-0 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium', mb.bg, mb.color)}
                    >
                      <mb.Icon className="w-2.5 h-2.5" strokeWidth={1.5} />
                      {mb.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-text-muted">
                    <span>{taskTypeName(r.task_type)}</span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" strokeWidth={1.25} />
                      {formatTime(r.created_at)}
                    </span>
                    {r.total_cost_usd > 0 && (
                      <span className="flex items-center gap-1">
                        <DollarSign className="w-3 h-3" strokeWidth={1.25} />
                        {r.total_cost_usd.toFixed(3)}
                      </span>
                    )}
                  </div>
                </div>

                {r.status === 'completed' && (
                  <FileText className="w-4 h-4 text-neon-green shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" strokeWidth={1.25} />
                )}

                <button
                  onClick={(e) => handleDelete(e, r.id)}
                  disabled={deletingId === r.id}
                  className="shrink-0 p-1.5 rounded-md text-text-muted hover:text-severity-critical hover:bg-severity-critical/10 transition-colors disabled:opacity-50"
                  title="删除"
                >
                  {deletingId === r.id ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.25} />
                  ) : (
                    <Trash2 className="w-3.5 h-3.5" strokeWidth={1.25} />
                  )}
                </button>
              </div>
            )
          }
          return (
            <div className="space-y-5">
              {projects.map((group) => (
                <div key={group.key}>
                  <div className="mb-2 flex items-center gap-2 text-sm font-medium text-warm-orange">
                    <FolderOpen className="w-4 h-4 shrink-0" strokeWidth={1.5} />
                    <span className="min-w-0 truncate">{group.key}</span>
                    <span className="text-xs text-text-muted">长期评审项目 · {group.items.length} 次评审</span>
                  </div>
                  <div className="space-y-2.5 border-l-2 border-warm-orange/20 pl-3">
                    {group.items.map(renderRow)}
                  </div>
                </div>
              ))}
              {ungrouped.length > 0 && (
                <div className="space-y-2.5">{ungrouped.map(renderRow)}</div>
              )}
            </div>
          )
        })()
      )}
    </div>
  )
}
