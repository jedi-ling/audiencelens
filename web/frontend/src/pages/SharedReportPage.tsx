/**
 * 公开只读报告页 —— /s/:token
 *
 * 唯一一个不需要登录就能看到别人评审内容的页面。作者在自己的报告页显式点了
 * 「生成分享链接」才会有这么一份，随时可撤销（撤销后这里就是 404）。
 *
 * 三条硬性要求，改这个文件的人别破坏：
 *
 * 1) **白名单式渲染。** 只画后端 /api/v2/shared/{token} 真的给了的字段
 *    （见 share_service.to_public_dict）。诱惑是"干脆复用整个 ReportPage"——
 *    那页还挂着追问、评估、伦理报告、认领、反馈这些需要身份的东西，一个个
 *    去关比一开始就只画该画的更容易漏。
 *
 * 2) **Synthetic Banner 与 Limitations 两块必须在。** ETHICS.md 的强制项
 *    （"每份 AudienceLens 报告必须"）。在这一页尤其不能省：私有报告至少是
 *    作者自己跑的、知道这是 AI；公开链接的访客可能是被人直接甩过来的，
 *    他没有任何上下文知道这不是真人调研。
 *
 * 3) **不要在这里加任何写操作。** 评论、点赞、收藏都不属于这一页——那是
 *    另一个产品决策（公开广场），不是"把报告发给合伙人看"。
 */

import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router'
import { api, ApiError } from '@/lib/apiClient'
import type { SharedReport } from '@/lib/types'
import { SyntheticBanner, LimitationsSection, type RealReport } from './ReportPage'
import SeverityBadge from '@/components/SeverityBadge'
import type { Severity } from '@/lib/mock-data'
import { Loader2, Link2Off, Users, ListChecks, Scale, ArrowRight, AlertCircle } from 'lucide-react'
import { EmptyState, PRIMARY_BUTTON_CLASS, SECONDARY_BUTTON_CLASS } from '@/components/ui'

/** 引擎的 severity 串收敛成 SeverityBadge 认识的档位；认不出来就不画徽章，
 *  不硬塞一个默认值假装知道严重程度。 */
function toSeverity(raw?: string): Severity | null {
  const v = (raw || '').toLowerCase()
  return v === 'critical' || v === 'high' || v === 'medium' || v === 'low' ? (v as Severity) : null
}

export default function SharedReportPage() {
  const { token } = useParams()
  const [data, setData] = useState<SharedReport | null>(null)
  const [loading, setLoading] = useState(true)
  // 404 与"网络挂了"要分开说：前者是作者撤销了（正常结果），后者是故障。
  // 混成一句"加载失败"会让访客以为是自己网络的问题，一直重试。
  const [revoked, setRevoked] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    let alive = true
    setLoading(true)
    setRevoked(false)
    setError(null)
    api
      .getSharedReport(token)
      .then((d) => {
        if (alive) setData(d)
      })
      .catch((e) => {
        if (!alive) return
        if (e instanceof ApiError && e.status === 404) setRevoked(true)
        else setError(e instanceof Error ? e.message : '加载失败')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [token])

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" strokeWidth={1.5} />
      </div>
    )
  }

  if (revoked) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-20 animate-fade-in">
        <EmptyState
          icon={Link2Off}
          title="链接已失效"
          description="这条分享链接不存在，或者已经被作者撤销了。如果你需要查看，请向分享给你的人重新索取。"
          action={
            <Link to="/" className={PRIMARY_BUTTON_CLASS}>
              了解 AudienceLens
            </Link>
          }
        />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-20 animate-fade-in">
        <EmptyState
          icon={Loader2}
          tone="error"
          title="加载失败"
          description={error ?? '没有拿到报告内容'}
          action={
            <button onClick={() => window.location.reload()} className={SECONDARY_BUTTON_CLASS}>
              重试
            </button>
          }
        />
      </div>
    )
  }

  const report = (data.report ?? {}) as RealReport
  const summary = report.executive_summary
  const consensus = report.consensus
  const fixes = report.priority_fixes ?? []
  const notes = report.persona_notes ?? []

  return (
    // 阅读型页面：正文列收窄居中，与评估报告同一档容器
    <div className="mx-auto max-w-3xl px-4 py-8 animate-fade-in">
      {/* ETHICS.md 强制项之一。公开链接的访客没有任何上下文，这块尤其不能省。 */}
      <SyntheticBanner />

      <header className="mb-8">
        <h1 className="font-display text-2xl font-bold text-text-primary">
          {data.target_title || report.meta?.target || '评审报告'}
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          {data.task_type}
          {data.completed_at && ` · ${new Date(data.completed_at).toLocaleString()}`}
          {typeof consensus?.persona_count === 'number' && ` · ${consensus.persona_count} 位人格参与`}
        </p>
        <p className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-border bg-bg-secondary/50 px-2.5 py-1 text-xs text-text-muted">
          这是作者主动分享的只读报告
        </p>
      </header>

      {summary && (
        <section className="mb-6 rounded-xl border border-border bg-bg-card p-5">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Scale className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
            总体结论
          </h2>
          {summary.primary_recommendation && (
            <p className="text-sm leading-relaxed text-text-primary">{summary.primary_recommendation}</p>
          )}
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-text-secondary">
            {summary.release_risk && <span>发布风险：<strong className="text-text-primary">{summary.release_risk}</strong></span>}
            {summary.evidence_quality && <span>证据质量：<strong className="text-text-primary">{summary.evidence_quality}</strong></span>}
          </div>
        </section>
      )}

      {fixes.length > 0 && (
        <section className="mb-6 rounded-xl border border-border bg-bg-card p-5">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
            <ListChecks className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
            优先修复（{fixes.length}）
          </h2>
          <ol className="space-y-3">
            {fixes.map((f, i) => {
              const sev = toSeverity(f.severity)
              return (
                <li key={i} className="rounded-lg border border-border bg-bg-secondary/40 p-3">
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 font-mono text-xs text-text-muted">{f.priority ?? i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-text-primary">{f.issue}</span>
                        {sev && <SeverityBadge severity={sev} />}
                      </div>
                      {f.why_it_matters && (
                        <p className="mt-1 text-xs leading-relaxed text-text-secondary">{f.why_it_matters}</p>
                      )}
                      {f.suggested_fix && (
                        <p className="mt-1 text-xs leading-relaxed text-text-muted">建议：{f.suggested_fix}</p>
                      )}
                    </div>
                  </div>
                </li>
              )
            })}
          </ol>
        </section>
      )}

      {consensus && ((consensus.agreed_points?.length ?? 0) > 0 || (consensus.questioned_points?.length ?? 0) > 0) && (
        <section className="mb-6 grid gap-4 sm:grid-cols-2">
          {(consensus.agreed_points?.length ?? 0) > 0 && (
            <div className="rounded-xl border border-border bg-bg-card p-5">
              <h2 className="mb-2 text-sm font-semibold text-text-primary">多数认同</h2>
              <ul className="space-y-1.5 text-xs leading-relaxed text-text-secondary">
                {consensus.agreed_points!.map((p, i) => <li key={i}>· {p}</li>)}
              </ul>
            </div>
          )}
          {(consensus.questioned_points?.length ?? 0) > 0 && (
            <div className="rounded-xl border border-border bg-bg-card p-5">
              <h2 className="mb-2 text-sm font-semibold text-text-primary">存在质疑</h2>
              <ul className="space-y-1.5 text-xs leading-relaxed text-text-secondary">
                {consensus.questioned_points!.map((p, i) => <li key={i}>· {p}</li>)}
              </ul>
            </div>
          )}
        </section>
      )}

      {notes.length > 0 && (
        <section className="mb-6 rounded-xl border border-border bg-bg-card p-5">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Users className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
            各角色视角（{notes.length}）
          </h2>
          <div className="space-y-3">
            {notes.map((n) => (
              <div key={n.persona_id} className="rounded-lg border border-border bg-bg-secondary/40 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-text-primary">{n.persona_name || n.persona_id}</span>
                  {(n.stance || n.primary_stance) && (
                    <span className="rounded bg-bg-card px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
                      {n.stance || n.primary_stance}
                    </span>
                  )}
                </div>
                {(n.top_issues?.length ?? 0) > 0 && (
                  <ul className="mt-1.5 space-y-1 text-xs leading-relaxed text-text-secondary">
                    {n.top_issues!.map((t, i) => <li key={i}>· {t}</li>)}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {(report.information_gaps?.length ?? 0) > 0 && (
        <section className="mb-6 rounded-xl border border-border bg-bg-card p-5">
          <h2 className="mb-2 text-sm font-semibold text-text-primary">信息缺口</h2>
          <ul className="space-y-1.5 text-xs leading-relaxed text-text-secondary">
            {report.information_gaps!.map((g, i) => <li key={i}>· {g}</li>)}
          </ul>
        </section>
      )}

      {/* ETHICS.md 强制项之二 */}
      <LimitationsSection caveats={report.meta?.caveats} />

      {/* 访客大概率是第一次听说这个产品——给一条自然的了解入口。
          刻意不做成弹窗或拦截层：他是来看报告的，不是来看广告的。 */}
      <div className="mt-10 border-t border-border pt-6 text-center">
        <p className="text-sm text-text-secondary">这份报告由 AudienceLens 的多角色评审团生成。</p>
        <Link
          to="/"
          className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-brand-primary transition-colors hover:text-brand-primary-dim"
        >
          给自己的东西也跑一轮
          <ArrowRight className="h-3.5 w-3.5" strokeWidth={1.5} />
        </Link>
      </div>
    </div>
  )
}
