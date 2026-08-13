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
import { t, Trans, missingMarker } from '@/i18n/runtime'
import { getLocale } from '@/i18n/locale'
import { useDocumentTitle } from '@/i18n/head'
import { formatDateTime, formatNumber } from '@/i18n/format'
import { tApiError } from '@/i18n/api-error'
import type { PlainMessageKey } from '@/i18n/keys.gen'
import {
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
import { PageShell, PageHeader, EmptyState, PRIMARY_BUTTON_CLASS, SECONDARY_BUTTON_CLASS } from '@/components/ui'

/** 这两张表存的是 **key 不是文案**：模块级常量存翻译结果的话，切换语言不会
 *  重新求值，徽章会一直停在打开页面时的那种语言（同 Layout.tsx 的 navItems）。 */
const statusConfig: Record<string, { labelKey: PlainMessageKey; color: string; bg: string }> = {
  pending: { labelKey: 'enum.review_status.pending', color: 'text-text-muted', bg: 'bg-bg-secondary' },
  running: { labelKey: 'enum.review_status.running', color: 'text-cyan', bg: 'bg-cyan/10' },
  completed: { labelKey: 'enum.review_status.completed', color: 'text-brand-primary', bg: 'bg-brand-primary/10' },
  failed: { labelKey: 'enum.review_status.failed', color: 'text-severity-critical', bg: 'bg-severity-critical/10' },
  cancelled: { labelKey: 'enum.review_status.cancelled', color: 'text-text-muted', bg: 'bg-bg-secondary' },
}

const modeBadgeConfig: Record<ReviewMode, { labelKey: PlainMessageKey; color: string; bg: string; Icon: typeof Zap }> = {
  quick: { labelKey: 'enum.mode_badge.quick', color: 'text-cyan', bg: 'bg-cyan/10', Icon: Zap },
  standard: { labelKey: 'enum.mode_badge.standard', color: 'text-brand-primary', bg: 'bg-brand-primary/10', Icon: ListChecks },
  full: { labelKey: 'enum.mode_badge.full', color: 'text-warm-orange', bg: 'bg-warm-orange/10', Icon: Microscope },
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

export default function ReviewHistoryPage() {
  const navigate = useNavigate()
  // 订阅 ui_lang（useDocumentTitle 内部就是 useLocale）：t() 是普通函数、不带
  // 响应性，切语言时必须有人触发重渲染。页面订阅一次，子组件跟着重渲染。
  useDocumentTitle('page.history.meta.title')
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
      // tApiError：原来是 `e instanceof Error ? e.message : '加载失败'`，
      // 会把 `TypeError: x is not a function` 原样甩给用户；而后端 message
      // 是中文，在英文界面上并排一句中文用户会以为界面坏了（契约 D2）。
      setError(tApiError(e, 'page.history.load.error'))
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
      setError(tApiError(e, 'page.history.load_more.error'))
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
      setError(tApiError(e, 'page.history.delete.error'))
    } finally {
      setDeletingId(null)
    }
  }

  const loaded = reviews?.length ?? 0
  /** 顶部计数：总数拿得到就说"共 N 条"，拿不到就只说已显示多少——不猜 */
  /* 抽 key 时补充：第四个分支（total === null && loaded === 0）是**空串**，
     那不是一句"什么都不说"的文案，是这一整块不渲染，所以它不进 key 表
     （契约 3.4 例 5）。条件渲染保留在这里。 */
  const countLabel =
    total === null
      ? loaded > 0
        ? t('page.history.count.loaded_only', { count: loaded })
        : ''
      : hasMore || loaded < total
        ? t('page.history.count.total_and_loaded', { count: total, loaded })
        : t('page.history.count.total', { count: total })

  return (
    <PageShell size="reading">
      <PageHeader
        title={t('page.history.header.title')}
        subtitle={t('page.history.header.desc')}
        actions={
          countLabel
            ? <span className="text-xs text-text-muted tabular-nums">{countLabel}</span>
            : undefined
        }
      />

      {error && (
        <div className="mb-4 flex items-center gap-2 text-sm text-severity-critical">
          <AlertCircle className="w-4 h-4 shrink-0" strokeWidth={1.25} />
          {error}
        </div>
      )}

      {reviews === null ? (
        <div className="py-16 text-center">
          <Loader2 className="w-8 h-8 text-cyan animate-spin mx-auto mb-3" strokeWidth={1.25} />
          <p className="text-text-secondary text-sm">{t('common.ui.loading')}</p>
        </div>
      ) : reviews.length === 0 ? (
        /* 空列表要分清两种情况：真的没有记录，和"没加载出来"。
           以前加载失败时这里会照样显示"还没有评审记录"——用户会以为数据没了。 */
        error ? (
          <EmptyState
            icon={AlertCircle}
            tone="error"
            title={t('page.history.load_error.title')}
            description={t('page.history.load_error.desc')}
            action={
              <button onClick={() => void loadFirstPage()} className={SECONDARY_BUTTON_CLASS}>
                {t('common.action.retry')}
              </button>
            }
          />
        ) : (
          <EmptyState
            icon={Inbox}
            title={t('page.history.list_empty.title')}
            action={
              <Link to="/ask" className={PRIMARY_BUTTON_CLASS}>
                {t('page.history.list_empty.cta')}
              </Link>
            }
          />
        )
      ) : (
        (() => {
          const { projects, ungrouped } = groupByProject(reviews)
          const renderRow = (r: ReviewListItem) => {
            // 认不出来的状态/模式：**样式**回落到 pending / standard 那一档（总得画点
            // 什么，而且中性配色不会让用户误读成某个确定的档位），但**文案不回落**。
            // 回落会让后端新增的枚举值在界面上伪装成"等待中"，缺译因此隐身（契约 D8）。
            const scHit: (typeof statusConfig)[string] | undefined = statusConfig[r.status]
            const sc = scHit ?? statusConfig.pending
            const statusLabel = scHit
              ? t(scHit.labelKey)
              : missingMarker(`enum.review_status.${r.status}`, getLocale())

            const modeTable = modeBadgeConfig as Record<string, (typeof modeBadgeConfig)[ReviewMode] | undefined>
            const mbHit = modeTable[r.mode]
            const mb = mbHit ?? modeBadgeConfig.standard
            const modeLabel = mbHit
              ? t(mbHit.labelKey)
              : missingMarker(`enum.mode_badge.${r.mode}`, getLocale())

            const target = r.status === 'completed' ? `/review/${r.id}/report` : `/review/${r.id}`
            const label = r.target_title || taskTypeName(r.task_type)

            // 二次确认直接长在这一行里。整行不再可点（避免"想点取消结果打开了评审"）。
            if (confirmingId === r.id) {
              return (
                <div
                  key={r.id}
                  role="alertdialog"
                  aria-label={t('page.history.confirm_dialog.aria', { title: label })}
                  className="rounded-xl border-2 border-severity-critical/40 bg-severity-critical/5 p-4"
                >
                  <p className="mb-2 text-sm leading-relaxed text-text-secondary">
                    {/* 标题和后果说明排版不同（主色 / 小字弱色），但必须是**一条** key：
                        拆成两条之后英文语序就改不动了（契约 D13 / 3.4 例 6）。 */}
                    <Trans
                      k="page.history.confirm_dialog.desc"
                      vars={{ title: label }}
                      slots={{
                        name: (s) => <span className="text-text-primary">{s}</span>,
                        note: (s) => <span className="text-xs text-text-muted">{s}</span>,
                      }}
                    />
                  </p>
                  <div className="flex gap-2">
                    <button
                      autoFocus
                      onClick={(e) => void handleDelete(e, r.id)}
                      disabled={deletingId === r.id}
                      className="flex items-center gap-1.5 rounded-lg bg-severity-critical/85 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-severity-critical disabled:opacity-60"
                    >
                      {deletingId === r.id && <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />}
                      {t('common.action.delete')}
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setConfirmingId(null)
                      }}
                      className="rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-bg-card-hover hover:text-text-primary"
                    >
                      {t('common.action.cancel')}
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
                  {statusLabel}
                </span>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-text-primary truncate">{label}</span>
                    <span
                      className={cn('shrink-0 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium', mb.bg, mb.color)}
                    >
                      <mb.Icon className="w-2.5 h-2.5" strokeWidth={1.5} />
                      {modeLabel}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-text-muted">
                    <span>{taskTypeName(r.task_type)}</span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" strokeWidth={1.25} />
                      {/* 原来是 toLocaleString('zh-CN', …)：硬编码的 locale 会让英文
                          界面显示中文日期。全站格式化统一走 @/i18n/format（契约 6.5）。 */}
                      {formatDateTime(r.created_at)}
                    </span>
                    {r.total_cost_usd > 0 && (
                      <span className="flex items-center gap-1">
                        <DollarSign className="w-3 h-3" strokeWidth={1.25} />
                        {/* 货币符号已经是左边那个图标了，所以这里只格式化数字、
                            不用 formatUsd——用了会变成两个 $。金额恒为美元，不换算。 */}
                        {formatNumber(r.total_cost_usd, 3)}
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
                  aria-label={t('page.history.item.aria', { title: label })}
                  title={t('page.history.item.tooltip')}
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
                    <span className="text-xs text-text-muted">
                      {t('page.history.group.meta', { count: group.items.length })}
                    </span>
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
                        {t('common.ui.loading')}
                      </>
                    ) : (
                      <>
                        <ChevronDown className="w-4 h-4" strokeWidth={1.25} />
                        {total === null
                          ? t('page.history.load_more.cta')
                          : `${t('page.history.load_more.cta')} ${t('page.history.load_more.remaining', { count: Math.max(0, total - loaded) })}`}
                      </>
                    )}
                  </button>
                ) : (
                  loaded > REVIEWS_PAGE_SIZE && (
                    <p className="inline-flex items-center gap-1.5 text-xs text-text-muted">
                      <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.25} />
                      {t('page.history.load_more.success', { count: loaded })}
                    </p>
                  )
                )}
              </div>
            </div>
          )
        })()
      )}
    </PageShell>
  )
}
