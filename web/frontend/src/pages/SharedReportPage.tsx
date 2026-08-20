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
import { toCrossExamView } from '@/lib/mock-data'
import { SyntheticBanner, LimitationsSection, EvidenceProfileSection, ModeBoundaryNote, CrossExamSection, type RealReport } from './ReportPage'
import SeverityBadge from '@/components/SeverityBadge'
import type { Severity } from '@/lib/mock-data'
import { Loader2, Link2Off, Users, ListChecks, Scale, ArrowRight, AlertCircle } from 'lucide-react'
import { EmptyState, PRIMARY_BUTTON_CLASS, SECONDARY_BUTTON_CLASS } from '@/components/ui'
import { t, Trans } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import { tApiError } from '@/i18n/api-error'
import { formatDateTime } from '@/i18n/format'

/** 引擎的 severity 串收敛成 SeverityBadge 认识的档位；认不出来就不画徽章，
 *  不硬塞一个默认值假装知道严重程度。 */
function toSeverity(raw?: string): Severity | null {
  const v = (raw || '').toLowerCase()
  return v === 'critical' || v === 'high' || v === 'medium' || v === 'low' ? (v as Severity) : null
}

export default function SharedReportPage() {
  const { token } = useParams()
  // 顺带订阅了 ui_lang（内部 useLocale）：切语言时整页重渲染，t() 才会重新求值。
  useDocumentTitle('page.shared.meta.title')
  const [data, setData] = useState<SharedReport | null>(null)
  const [loading, setLoading] = useState(true)
  // 404 与"网络挂了"要分开说：前者是作者撤销了（正常结果），后者是故障。
  // 混成一句"加载失败"会让访客以为是自己网络的问题，一直重试。
  const [revoked, setRevoked] = useState(false)
  // 存的是**异常对象**不是已翻好的字符串：存字符串的话，它在 catch 那一刻就
  // 定死了语种，用户之后切语言这条错误提示会一直停在旧语言上。
  // 译文在渲染处由 tApiError 现出（它还负责把语种对不上的后端原文降级成 detail）。
  const [error, setError] = useState<unknown>(null)

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
        else setError(e)
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
          title={t('page.shared.revoked.title')}
          description={t('page.shared.revoked.desc')}
          action={
            <Link to="/" className={PRIMARY_BUTTON_CLASS}>
              {t('page.shared.revoked.cta')}
            </Link>
          }
        />
      </div>
    )
  }

  if (error !== null || !data) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-20 animate-fade-in">
        {/* error === null（请求成功但 report 是空的）时 tApiError 走 fallbackKey，
            正好就是"没有拿到报告内容"这句——两条路径本来就该说同一句话。 */}
        <EmptyState
          icon={Loader2}
          tone="error"
          title={t('page.shared.load_error.title')}
          description={tApiError(error, 'page.shared.load_error.desc')}
          action={
            <button onClick={() => window.location.reload()} className={SECONDARY_BUTTON_CLASS}>
              {t('common.action.retry')}
            </button>
          }
        />
      </div>
    )
  }

  const report = (data.report ?? {}) as RealReport
  // 库里同时存在三代 cross_examination 形状，一律经 toCrossExamView 运行时收敛
  // （与 ReportPage 同一个读法，不在这里另写一套）。
  const sharedCrossExam = toCrossExamView(report.cross_examination)
  const summary = report.executive_summary
  const consensus = report.consensus
  const fixes = report.priority_fixes ?? []
  const notes = report.persona_notes ?? []

  return (
    // 阅读型页面：正文列收窄居中，与评估报告同一档容器
    <div className="mx-auto max-w-3xl px-4 py-8 animate-fade-in">
      {/* ETHICS.md 强制项之一。公开链接的访客没有任何上下文，这块尤其不能省。 */}
      <SyntheticBanner />
      {/* 档位边界 + 证据构成：分享出去的报告更需要这两块——收到链接的人没有
          任何上下文，不知道这是三档里的哪一档、结论建立在什么证据之上。
          与报告页/两份导出件同批补齐（四种形态说同样的话）。 */}
      <ModeBoundaryNote mode={data.mode} />
      <EvidenceProfileSection profile={report.evidence_profile} dimensions={report.dimension_scores} />
      {report.triage?.enabled && (
        <p className="mb-4 rounded-lg border border-border bg-bg-card px-4 py-2.5 text-xs text-text-muted">
          {t('page.report.triage.badge', {
            screened: report.triage.screened_count ?? 0,
            advanced: (report.triage.advanced ?? []).length,
          })}
          {' — '}
          {t('page.report.triage.desc')}
        </p>
      )}
      {(report.abstentions?.length ?? 0) > 0 && (
        <p className="mb-4 rounded-lg border border-dashed border-border px-4 py-2.5 text-xs text-text-muted">
          {t('page.report.abstain.label')}
          {t('page.report.sep_colon')}
          {report.abstentions!.map((ab) => ab.persona_id).join(t('page.report.sep_enum'))}
          {' — '}
          {t('page.report.abstain.desc')}
        </p>
      )}

      <header className="mb-8">
        <h1 className="font-display text-2xl font-bold text-text-primary">
          {data.target_title || report.meta?.target || t('page.shared.header.title')}
        </h1>
        {/* 分隔点写成 JSX 文本而不是拼进字符串：拼进去就得在译文里带一个前导 " · "，
            那种带首尾空格的译文在资源文件里肉眼看不出来，改一次少一个空格没人发现。 */}
        <p className="mt-1 text-sm text-text-secondary">
          {data.task_type}
          {data.completed_at && <> · {formatDateTime(data.completed_at)}</>}
          {typeof consensus?.persona_count === 'number' && (
            <> · {t('page.shared.header.meta', { count: consensus.persona_count })}</>
          )}
        </p>
        <p className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-border bg-bg-secondary/50 px-2.5 py-1 text-xs text-text-muted">
          {t('page.shared.share_note.badge')}
        </p>
      </header>

      {summary && (
        <section className="mb-6 rounded-xl border border-border bg-bg-card p-5">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Scale className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
            {t('page.shared.summary.title')}
          </h2>
          {summary.primary_recommendation && (
            <p className="text-sm leading-relaxed text-text-primary">{summary.primary_recommendation}</p>
          )}
          {/* <v> 里包的是引擎产出的原值，只加粗、不翻译：报告正文的语言在评审入队
              瞬间就冻结了，界面语言换了它也不会跟着换（契约 8.6：显示原文，不机翻）。 */}
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-text-secondary">
            {summary.release_risk && (
              <span>
                <Trans
                  k="page.shared.release_risk.label"
                  vars={{ value: summary.release_risk }}
                  slots={{ v: (s) => <strong className="text-text-primary">{s}</strong> }}
                />
              </span>
            )}
            {summary.evidence_quality && (
              <span>
                <Trans
                  k="page.shared.evidence_quality.label"
                  vars={{ value: summary.evidence_quality }}
                  slots={{ v: (s) => <strong className="text-text-primary">{s}</strong> }}
                />
              </span>
            )}
          </div>
        </section>
      )}

      {fixes.length > 0 && (
        <section className="mb-6 rounded-xl border border-border bg-bg-card p-5">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
            <ListChecks className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
            {t('page.shared.fixes.title', { count: fixes.length })}
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
                        <p className="mt-1 text-xs leading-relaxed text-text-muted">
                          {t('page.shared.suggestion.label', { text: f.suggested_fix })}
                        </p>
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
              <h2 className="mb-2 text-sm font-semibold text-text-primary">{t('page.shared.agreed.title')}</h2>
              <ul className="space-y-1.5 text-xs leading-relaxed text-text-secondary">
                {consensus.agreed_points!.map((p, i) => <li key={i}>· {p}</li>)}
              </ul>
            </div>
          )}
          {(consensus.questioned_points?.length ?? 0) > 0 && (
            <div className="rounded-xl border border-border bg-bg-card p-5">
              <h2 className="mb-2 text-sm font-semibold text-text-primary">{t('page.shared.questioned.title')}</h2>
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
            {t('page.shared.notes.title', { count: notes.length })}
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

      {/* 主要分歧 + 交叉质询：分享页的自我定位是"把报告发给合伙人看"，
          而合伙人最该看到的恰恰是"评审团在哪儿吵起来了"。这两块是本产品
          最有差异化的内容，数据白名单本来就给了（report 整体），此前只是
          没渲染。CrossExamSection 从 ReportPage 复用而非复制一份。 */}
      {(report.major_disagreements?.length ?? 0) > 0 && (
        <section className="mb-6">
          <h2 className="mb-3 text-sm font-semibold text-text-primary">
            {t('page.report.disagreements.title')}
          </h2>
          <div className="flex flex-col gap-3">
            {report.major_disagreements!.map((d, i) => (
              <div key={i} className="overflow-x-auto rounded-xl border border-warm-orange/20 bg-bg-card p-4">
                <p className="mb-2 text-sm font-medium text-text-primary">{d.topic}</p>
                {(d.persona_stances?.length ?? 0) > 0 && (
                  <ul className="space-y-1.5">
                    {d.persona_stances!.map((ps, j) => (
                      <li key={j} className="flex items-start gap-2 text-xs text-text-secondary">
                        <span className="shrink-0 font-mono text-text-muted">{ps.persona_id}</span>
                        <span className="shrink-0 rounded bg-bg-secondary px-1.5 text-text-primary">{ps.stance}</span>
                        <span>{ps.evidence}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {sharedCrossExam && <CrossExamSection view={sharedCrossExam} />}

      {/* 可证伪预测：分享页尤其需要——收链接的人没有上下文，
          "该拿什么去验证" 正是这份报告对他最有用的部分。 */}
      {(report.predictions?.length ?? 0) > 0 && (
        <section className="mb-6 rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <h2 className="mb-3 text-sm font-semibold text-text-primary">
            {t('page.report.predictions.title')}
          </h2>
          <ul className="space-y-2">
            {report.predictions!.map((p, i) => (
              <li key={p.prediction_id ?? i} className="text-sm text-text-secondary">
                <span className="text-text-primary">{p.claim || p.intervention}</span>
                {p.success_criterion && (
                  <span className="block text-xs text-text-muted">
                    {t('page.report.prediction_criterion.label')}
                    {t('page.report.sep_colon')}
                    {p.success_criterion}
                    {p.verification_window ? ` · ${p.verification_window}` : ''}
                  </span>
                )}
              </li>
            ))}
          </ul>
          <p className="mt-3 border-t border-border pt-2 text-xs text-text-muted">
            {t('page.report.falsify.desc')}
          </p>
        </section>
      )}

      {(report.information_gaps?.length ?? 0) > 0 && (
        <section className="mb-6 rounded-xl border border-border bg-bg-card p-5">
          <h2 className="mb-2 text-sm font-semibold text-text-primary">{t('page.shared.gaps.title')}</h2>
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
        <p className="text-sm text-text-secondary">{t('page.shared.footer.desc')}</p>
        <Link
          to="/"
          className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-brand-primary transition-colors hover:text-brand-primary-dim"
        >
          {t('page.shared.footer.cta')}
          <ArrowRight className="h-3.5 w-3.5" strokeWidth={1.5} />
        </Link>
      </div>
    </div>
  )
}
