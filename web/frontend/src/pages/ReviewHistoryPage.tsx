/**
 * 评审历史列表——之前产品里完全没有这个页面，用户发起评审后除了当次的进度页
 * 链接，没有任何地方能回看"我都评审过什么"。数据走 fetchReviewsPage()
 * （/api/reviews），后端已按登录身份过滤（见 app/api/__init__.py 的
 * _check_review_owner），匿名单机形态下所有匿名请求共享同一个历史列表，
 * 这是既有设计，不是本页的 bug。
 *
 * 分页：后端一直是 offset/limit 分页、默认一页 20 条，而这个页面过去
 * 一个参数都不传、也没有翻页 UI——用户跑到第 21 次评审之后，旧评审在界面上
 * 就等于凭空消失，且没有任何提示。现在页面顶部常驻"共 N 条 / 已显示 M 条"，
 * 底部是"加载更多"，加载到底会明确说"已加载全部"——用户任何时候都能看出
 * 数据是没加载完、还是真的只有这么多。
 */
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { cn } from '@/lib/utils'
import { fetchReviewsPage, deleteReview, REVIEWS_PAGE_SIZE } from '@/lib/api'
import { TASK_TYPES } from '@/lib/mock-data'
import type { ReviewListItem, ReviewMode } from '@/lib/mock-data'
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
  ChevronDown,
  CheckCircle2,
} from 'lucide-react'

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: '等待中', color: 'text-text-muted', bg: 'bg-bg-secondary' },
  running: { label: '运行中', color: 'text-cyan', bg: 'bg-cyan/10' },
  completed: { label: '已完成', color: 'text-brand-primary', bg: 'bg-brand-primary/10' },
  failed: { label: '失败', color: 'text-severity-critical', bg: 'bg-severity-critical/10' },
  cancelled: { label: '已取消', color: 'text-text-muted', bg: 'bg-bg-secondary' },
}

const modeBadgeConfig: Record<ReviewMode, { label: string; color: string; bg: string; Icon: typeof Zap }> = {
  quick: { label: '快速', color: 'text-cyan', bg: 'bg-cyan/10', Icon: Zap },
  standard: { label: '标准', color: 'text-brand-primary', bg: 'bg-brand-primary/10', Icon: ListChecks },
  full: { label: '完整', color: 'text-warm-orange', bg: 'bg-warm-orange/10', Icon: Microscope },
}

function taskTypeName(taskType: string): string {
  return TASK_TYPES.find((t) => t.id === taskType)?.name ?? taskType
}

/** 同 project_key 的评审聚合成"长期评审项目"分组（与 /ask 侧栏同一逻辑）；
 * 列表已按 created_at 倒序，分组内/分组间顺序天然保留。
 * 分页是在这之前把已加载的条目累加好再分组的，所以跨页的同一项目会正确合并。 */
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
  /** 后端 X-Total-Count；读不到（跨域没 expose 等）就是 null，此时不显示"共 N 条" */
  const [total, setTotal] = useState<number | null>(null)
  const [hasMore, setHasMore] = useState(false)
  /**
   * 下一页要用的 offset。**不能**直接用 reviews.length：删掉一条已加载的评审后，
   * 服务端列表整体左移一位，继续按 reviews.length 取下一页会正好跳过一条，
   * 那条评审就变成了翻不到的"幽灵"。所以删除成功时这里跟着减一。
   */
  const [nextOffset, setNextOffset] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  /** 正在等二次确认的那条。页面内确认，不用 window.confirm——理由见 askDelete */
  const [confirmingId, setConfirmingId] = useState<string | null>(null)

  const loadFirstPage = useCallback(async () => {
    try {
      const page = await fetchReviewsPage(0, REVIEWS_PAGE_SIZE)
      setReviews(page.items)
      setTotal(page.total)
      setHasMore(page.hasMore)
      setNextOffset(page.items.length)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
      setReviews((prev) => prev ?? [])
    }
  }, [])

  useEffect(() => {
    void loadFirstPage()
  }, [loadFirstPage])

  const loadMore = async () => {
    if (loadingMore) return
    setLoadingMore(true)
    try {
      const page = await fetchReviewsPage(nextOffset, REVIEWS_PAGE_SIZE)
      setReviews((prev) => {
        const base = prev ?? []
        // 去重兜底：删除导致的偏移已在 nextOffset 里修正，这里只是防御性保险，
        // 万一重复也不该炸出 React 重复 key
        const seen = new Set(base.map((r) => r.id))
        return [...base, ...page.items.filter((r) => !seen.has(r.id))]
      })
      setTotal(page.total)
      setHasMore(page.hasMore)
      setNextOffset((prev) => prev + page.items.length)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载更多失败')
    } finally {
      setLoadingMore(false)
    }
  }

  /** 点垃圾桶：只进入"待确认"状态，不真删。
   *
   * 二次确认曾经用 window.confirm，实测不可靠：Chrome 在同一页面连弹几次后会给出
   * "阻止此页面创建更多对话框"的勾选框，用户勾上之后 confirm() 直接静默返回 false，
   * 于是点删除永远没反应、也没有任何报错——表现就是"删不掉"。某些内嵌 WebView
   * 也会整体屏蔽这类对话框。AskPage 已经因此改成页面内确认，这里统一成同一种写法。
   */
  const askDelete = (e: React.MouseEvent, id: string) => {
    e.preventDefault()
    e.stopPropagation()
    setError(null)
    setConfirmingId((prev) => (prev === id ? null : id))
  }

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.preventDefault()
    e.stopPropagation()
    setConfirmingId(null)
    setDeletingId(id)
    try {
      await deleteReview(id)
      setReviews((prev) => (prev ? prev.filter((r) => r.id !== id) : prev))
      setTotal((prev) => (prev === null ? null : Math.max(0, prev - 1)))
      setNextOffset((prev) => Math.max(0, prev - 1)) // 见 nextOffset 的说明
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败')
    } finally {
      setDeletingId(null)
    }
  }

  const loaded = reviews?.length ?? 0
  /** 顶部计数：总数拿得到就说"共 N 条"，拿不到就只说已显示多少——不猜 */
  const countLabel =
    total === null
      ? loaded > 0
        ? `已显示 ${loaded} 条`
        : ''
      : hasMore || loaded < total
        ? `共 ${total} 条 · 已显示 ${loaded} 条`
        : `共 ${total} 条`

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 animate-fade-in">
      <div className="flex items-center gap-3 mb-6">
        <History className="w-6 h-6 text-brand-primary" strokeWidth={1.25} />
        <div>
          <h1 className="text-xl font-semibold text-text-primary">评审历史</h1>
          <p className="text-sm text-text-secondary mt-0.5">你发起过的所有评审，点进去看报告或继续跟进</p>
        </div>
        {countLabel && (
          <span className="ml-auto shrink-0 text-xs text-text-muted tabular-nums">{countLabel}</span>
        )}
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
        /* 空列表要分清两种情况：真的没有记录，和"没加载出来"。
           以前加载失败时这里会照样显示"还没有评审记录"——用户会以为数据没了。 */
        error ? (
          <div className="py-16 text-center rounded-xl border border-border bg-bg-card">
            <AlertCircle className="w-10 h-10 text-severity-critical mx-auto mb-3" strokeWidth={1.25} />
            <p className="text-text-secondary text-sm mb-1">没能加载评审历史</p>
            <p className="text-text-muted text-xs mb-4">这不代表记录被删除了，请重试或稍后再来</p>
            <button
              onClick={() => void loadFirstPage()}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm text-text-secondary hover:border-brand-primary/30 hover:text-text-primary transition-colors"
            >
              重试
            </button>
          </div>
        ) : (
          <div className="py-16 text-center rounded-xl border border-border bg-bg-card">
            <Inbox className="w-10 h-10 text-text-muted mx-auto mb-3" strokeWidth={1.25} />
            <p className="text-text-secondary text-sm mb-4">还没有评审记录</p>
            <Link
              to="/ask"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-primary text-white text-sm font-bold hover:bg-brand-primary-dim transition-colors"
            >
              发起第一次评审 →
            </Link>
          </div>
        )
      ) : (
        (() => {
          const { projects, ungrouped } = groupByProject(reviews)
          const renderRow = (r: ReviewListItem) => {
            const sc = statusConfig[r.status] ?? statusConfig.pending
            const mb = modeBadgeConfig[r.mode] ?? modeBadgeConfig.standard
            const target = r.status === 'completed' ? `/review/${r.id}/report` : `/review/${r.id}`
            const label = r.target_title || taskTypeName(r.task_type)

            // 二次确认直接长在这一行里。整行不再可点（避免"想点取消结果打开了评审"）。
            if (confirmingId === r.id) {
              return (
                <div
                  key={r.id}
                  role="alertdialog"
                  aria-label={`确认删除「${label}」`}
                  className="rounded-xl border-2 border-severity-critical/40 bg-severity-critical/5 p-4"
                >
                  <p className="mb-2 text-sm leading-relaxed text-text-secondary">
                    删除「<span className="text-text-primary">{label}</span>」？
                    <br />
                    <span className="text-xs text-text-muted">
                      报告、各角色意见、全部追问记录一起没，无法撤销。
                    </span>
                  </p>
                  <div className="flex gap-2">
                    <button
                      autoFocus
                      onClick={(e) => void handleDelete(e, r.id)}
                      disabled={deletingId === r.id}
                      className="flex items-center gap-1.5 rounded-lg bg-severity-critical/85 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-severity-critical disabled:opacity-60"
                    >
                      {deletingId === r.id && <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />}
                      删除
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setConfirmingId(null)
                      }}
                      className="rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-bg-card-hover hover:text-text-primary"
                    >
                      取消
                    </button>
                  </div>
                </div>
              )
            }

            return (
              <div
                key={r.id}
                onClick={() => navigate(target)}
                className="group flex items-center gap-4 p-4 rounded-xl border border-border bg-bg-card hover:border-brand-primary/30 hover:bg-bg-card-hover transition-all cursor-pointer"
              >
                <span className={cn('shrink-0 px-2 py-1 rounded text-xs font-medium', sc.bg, sc.color)}>
                  {sc.label}
                </span>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-text-primary truncate">{label}</span>
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
                  <FileText className="w-4 h-4 text-brand-primary shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" strokeWidth={1.25} />
                )}

                <button
                  onClick={(e) => askDelete(e, r.id)}
                  disabled={deletingId === r.id}
                  className="shrink-0 p-1.5 rounded-md text-text-muted hover:text-severity-critical hover:bg-severity-critical/10 transition-colors disabled:opacity-50"
                  aria-label={`删除「${label}」`}
                  title="删除这条评审（会二次确认）"
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

              {/* 翻页出口：有更多就给按钮，没有了就明说"已加载全部"，
                  不让用户对着一个截断的列表猜数据是不是丢了 */}
              <div className="pt-2 text-center">
                {hasMore ? (
                  <button
                    onClick={() => void loadMore()}
                    disabled={loadingMore}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-bg-card text-sm text-text-secondary hover:border-brand-primary/30 hover:text-text-primary transition-colors disabled:opacity-50"
                  >
                    {loadingMore ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.25} />
                        加载中...
                      </>
                    ) : (
                      <>
                        <ChevronDown className="w-4 h-4" strokeWidth={1.25} />
                        加载更多
                        {total !== null && ` · 还有 ${Math.max(0, total - loaded)} 条`}
                      </>
                    )}
                  </button>
                ) : (
                  loaded > REVIEWS_PAGE_SIZE && (
                    <p className="inline-flex items-center gap-1.5 text-xs text-text-muted">
                      <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.25} />
                      已加载全部 {loaded} 条评审
                    </p>
                  )
                )}
              </div>
            </div>
          )
        })()
      )}
    </div>
  )
}
