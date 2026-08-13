import { useParams, Link } from 'react-router'
import { useState, useEffect } from 'react'
import { fetchReview, fetchEvaluation, fetchEthicsReport } from '@/lib/api'
import { ApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'
import type { Review, EvaluationScorecard, EthicsReportView } from '@/lib/mock-data'
import {
  EVALUATION_DIMENSIONS,
  SKILLS,
  ETHICS_SEVERITY_BADGE_CLASSES,
  ETHICS_SEVERITY_LABELS,
  stereotypeRiskBadgeClass,
  stereotypeRiskLabel,
  toEthicsReportView,
} from '@/lib/mock-data'
import { ArrowLeft, ChevronDown, ChevronUp, AlertOctagon, AlertCircle, FlaskConical, Shield, Loader2, Clock, User } from 'lucide-react'
import { ResponsiveContainer, Tooltip, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts'
import { PageShell, PageHeader, EmptyState, PRIMARY_BUTTON_CLASS, SECONDARY_BUTTON_CLASS } from '@/components/ui'
import { t } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import { formatDateTime, formatNumber } from '@/i18n/format'
import { tApiError } from '@/i18n/api-error'

/** 「还没生成」和「加载失败」必须分开：前者是正常状态，后者是故障。
 *  后端 GET /api/evaluations/{id} 在没有记分卡时返回 404，其余状态码都是真故障。 */
function isNotGenerated(err: unknown): boolean {
  return err instanceof ApiError && err.status === 404
}

/** created_at / completed_at 在库里都可能是 null（评审还没跑完、旧数据缺列）。
 *  以前直接 new Date(null) → 1970-01-01，页面上煞有介事地显示一个假时间。
 *  取不到就明说取不到。 */
function formatTime(iso: string | null | undefined): string {
  if (!iso) return t('page.evaluation.time.empty')
  const d = new Date(iso)
  // 解析不出来的时间戳同样明说取不到：交给 formatDateTime 会在 DEV 直接抛。
  return Number.isNaN(d.getTime()) ? t('page.evaluation.time.empty') : formatDateTime(d)
}

/** 单维度满分。后端 evaluation_service.py 每个 _eval_* 都只产出 {0,1,2,3}，
 *  passed = score >= 2，只有 scorecard.overall_score 才是 0–100
 *  （_calculate_overall_score = 总分 / (维度数 * 3) * 100）。
 *  这两个量纲混在同一页上，此前整页按 0–100 渲染：满分 3 分被写成「3/100」、
 *  进度条 3%、颜色阈值 >70 永远不成立，于是每个维度都涂成红色，
 *  而同页的总体评分显示 100 分且「评估通过」。用户看到的是自相矛盾的一页。 */
const DIMENSION_MAX_SCORE = 3

/** 维度分的配色一律跟 passed 走，不再自造分数阈值：
 *  合格线是后端定的（>=2），前端再定一套只会和「通过/未通过」徽标打架。 */
function dimensionScoreClass(result: { score: number; passed: boolean }): string {
  if (result.passed) return 'text-brand-primary'
  return result.score >= 1 ? 'text-severity-medium' : 'text-severity-critical'
}

function dimensionBarClass(result: { score: number; passed: boolean }): string {
  if (result.passed) return 'bg-brand-primary'
  return result.score >= 1 ? 'bg-severity-medium' : 'bg-severity-critical'
}

/** 维度 id 在本地词表里找不到时要说「不认识这个 id」，不能把 snake_case 原样
 *  当成正常标题直出——那看起来像是产品本来就长这样，没人会去查为什么。 */
function dimensionLabel(id: string, name?: string): string {
  return name ?? t('page.evaluation.unknown_dimension.label', { id })
}

/** 维度分的「x/3」。两处都用它，免得一处改了另一处没改。 */
function scoreText(score: number): string {
  return t('page.evaluation.score.value', {
    score: formatNumber(score),
    max: formatNumber(DIMENSION_MAX_SCORE),
  })
}

export default function EvaluationPage() {
  useDocumentTitle('page.evaluation.meta.title')
  const { id } = useParams()
  const [review, setReview] = useState<Review | null>(null)
  const [scorecard, setScorecard] = useState<EvaluationScorecard | null>(null)
  // 存收敛后的视图：违规项与风险档位在进 state 前就已经过类型守卫
  const [ethicsData, setEthicsData] = useState<EthicsReportView[]>([])
  const [loading, setLoading] = useState(true)
  /* 三个来源各自记错。
   *
   * 以前是 Promise.all([...]) + catch{ignore}：任意一个失败就整块没有数据，
   * 页面统一渲染成「评估报告尚未生成」。最常见的表现是——评估明明已经跑完，
   * 只是伦理报告接口抖了一下，用户看到的却是"没生成，请先运行评估"，
   * 于是又去重跑一次评估。现在各自降级，且失败原因如实显示。 */
  const [reviewError, setReviewError] = useState<unknown>(null)
  const [scorecardError, setScorecardError] = useState<unknown>(null)
  const [ethicsError, setEthicsError] = useState<unknown>(null)
  const [expandedDimensions, setExpandedDimensions] = useState<Set<string>>(new Set())
  /** 失败后手动重试的扳机：自增一次就重新拉一遍三份数据 */
  const [reloadNonce, setReloadNonce] = useState(0)

  useEffect(() => {
    if (!id) return
    let alive = true
    const loadData = async () => {
      const [reviewRes, scorecardRes, ethicsRes] = await Promise.allSettled([
        fetchReview(id),
        fetchEvaluation(id),
        fetchEthicsReport(id),
      ])
      if (!alive) return
      if (reviewRes.status === 'fulfilled') setReview(reviewRes.value)
      else setReviewError(reviewRes.reason)
      if (scorecardRes.status === 'fulfilled') setScorecard(scorecardRes.value)
      else setScorecardError(scorecardRes.reason)
      // 伦理报告缺失是常态（没跑过伦理检查），不该拦住整页；只在真故障时提示
      if (ethicsRes.status === 'fulfilled') setEthicsData(ethicsRes.value.map(toEthicsReportView))
      else setEthicsError(ethicsRes.reason)
      setLoading(false)
    }
    void loadData()
    return () => {
      alive = false
    }
  }, [id, reloadNonce])

  const handleRetry = () => {
    setLoading(true)
    setReviewError(null)
    setScorecardError(null)
    setEthicsError(null)
    setReloadNonce((n) => n + 1)
  }

  if (loading) {
    return (
      <PageShell size="reading" animate={false} className="py-16 text-center">
        <Loader2 className="w-8 h-8 text-cyan animate-spin mx-auto mb-4" strokeWidth={1.25} />
        <p className="text-text-secondary">{t('page.evaluation.header.loading')}</p>
      </PageShell>
    )
  }

  if (!review || !scorecard) {
    // 只有"确实还没跑过评估"才说尚未生成；其余一律如实报故障，
    // 免得用户对着一个 500 反复点"重新运行评估"。
    const blocking = !scorecard ? scorecardError : reviewError
    const notGenerated = !scorecard && isNotGenerated(scorecardError)
    return (
      <PageShell size="reading" animate={false} className="py-16">
        <div className="mx-auto max-w-2xl">
          {notGenerated ? (
            <EmptyState
              icon={FlaskConical}
              title={t('page.evaluation.not_generated.title')}
              description={t('page.evaluation.not_generated.desc')}
            />
          ) : (
            <EmptyState
              icon={AlertCircle}
              tone="error"
              title={t('page.evaluation.load_error.title')}
              // 后端 message 的语种由 tApiError 按 message_lang 判定；语种对不上时
              // 出前端译文，绝不把一句中文原文塞进英文界面的句子中间。
              description={t('page.evaluation.load_error.desc', {
                message: tApiError(blocking, 'common.ui.unknown_error'),
              })}
              action={
                <button onClick={handleRetry} className={PRIMARY_BUTTON_CLASS}>
                  <Loader2 className="w-4 h-4" strokeWidth={1.25} />
                  {t('common.action.retry')}
                </button>
              }
            />
          )}
          <div className="mt-4 text-center">
            <Link to={`/review/${id}/report`} className={SECONDARY_BUTTON_CLASS}>
              <ArrowLeft className="w-4 h-4" strokeWidth={1.25} />
              {t('page.evaluation.back.cta')}
            </Link>
          </div>
        </div>
      </PageShell>
    )
  }

  const skill = review.skill_type ? SKILLS.find((s) => s.type === review.skill_type) : null

  const radarData = scorecard.results.map((r) => {
    const dim = EVALUATION_DIMENSIONS.find((d) => d.id === r.dimension)
    return {
      dimension: dimensionLabel(r.dimension, dim?.name),
      score: r.score,
      fullMark: DIMENSION_MAX_SCORE,
    }
  })

  return (
    // 阅读型页面：正文列收窄居中（recharts 自带响应式容器，图表不需要横向滚动兜底）
    <PageShell size="reading">
      <PageHeader
        leading={
          <Link to={`/review/${id}/report`} aria-label={t('page.evaluation.header.aria')} className="p-2 rounded-lg hover:bg-bg-card transition-colors">
            <ArrowLeft className="w-5 h-5 text-text-secondary" strokeWidth={1.25} />
          </Link>
        }
        title={t('page.evaluation.header.title')}
        subtitle={review.target_title}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-1 rounded-xl border border-border bg-bg-card p-6 flex flex-col items-center justify-center">
          <h3 className="text-sm font-medium text-text-muted mb-4">{t('page.evaluation.overall.title')}</h3>
          <div className={cn(
            'w-28 h-28 rounded-full flex items-center justify-center border-4 mb-4',
            scorecard.overall_score > 70
              ? 'border-brand-primary bg-brand-primary/10'
              : scorecard.overall_score >= 50
                ? 'border-severity-medium bg-severity-medium/10'
                : 'border-severity-critical bg-severity-critical/10'
          )}>
            <span className={cn(
              'text-3xl font-bold font-mono tabular-nums',
              scorecard.overall_score > 70
                ? 'text-brand-primary'
                : scorecard.overall_score >= 50
                  ? 'text-severity-medium'
                  : 'text-severity-critical'
            )}>
              {formatNumber(scorecard.overall_score)}
            </span>
          </div>
          <span className={cn(
            'inline-flex items-center gap-1 px-4 py-1.5 rounded-full text-sm font-medium',
            scorecard.passed
              ? 'bg-brand-primary/10 text-brand-primary'
              : 'bg-severity-critical/10 text-severity-critical'
          )}>
            {scorecard.passed
              ? t('page.evaluation.state.overall_pass')
              : t('page.evaluation.state.overall_fail')}
          </span>
          <p className="text-xs text-text-muted mt-2">
            {t('page.evaluation.overall.desc', {
              passed: formatNumber(scorecard.results.filter((r) => r.passed).length),
              count: scorecard.results.length,
            })}
          </p>
          {/* 明说总体评分是 0–100：同一页下面的维度分是 0–3，不标满分的话
              两个量纲长得一样，用户会把「2」当成极低分 */}
          <p className="text-xs text-text-muted mt-0.5">{t('page.evaluation.overall.hint')}</p>
        </div>

        <div className="lg:col-span-2 rounded-xl border border-border bg-bg-card p-6">
          <h3 className="text-sm font-medium text-text-muted mb-4">{t('page.evaluation.radar.title')}</h3>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              {/* 深色底上 #e5e5ea 网格会亮得刺眼；刻度/网格/雷达线统一用深色适配色 */}
              <PolarGrid stroke="#38383a" />
              <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11, fill: '#8e8e93' }} />
              {/* 轴上限 = 单维度满分 3，不是 0–100：按 100 画会把满分压成一个贴着
                  圆心的点，整张雷达图恒定塌陷成一团 */}
              <PolarRadiusAxis domain={[0, DIMENSION_MAX_SCORE]} tickCount={DIMENSION_MAX_SCORE + 1} tick={{ fontSize: 9, fill: '#636366' }} />
              <Radar
                name={t('page.evaluation.radar.label')}
                dataKey="score"
                stroke="#0a84ff"
                fill="#0a84ff"
                fillOpacity={0.2}
                strokeWidth={2}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#1c1c1e', border: '1px solid #38383a', borderRadius: '8px', fontSize: '12px' }}
                itemStyle={{ color: '#ffffff' }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {scorecard.critical_failures.length > 0 && (
        <div className="rounded-xl border-2 border-severity-critical/30 bg-severity-critical/5 p-4 md:p-5 mb-6">
          <div className="flex items-center gap-2 mb-3">
            <AlertOctagon className="w-5 h-5 text-severity-critical" strokeWidth={1.25} />
            <h3 className="text-base font-semibold text-severity-critical">{t('page.evaluation.critical.title')}</h3>
          </div>
          <ul className="space-y-2">
            {scorecard.critical_failures.map((cf, i) => (
              <li key={i} className="text-sm text-text-secondary flex items-start gap-2">
                <span className="text-severity-critical font-bold shrink-0">{i + 1}.</span>
                {cf}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mb-6">
        <h3 className="text-lg font-semibold text-text-primary mb-4">{t('page.evaluation.dimensions.title')}</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {scorecard.results.map((result) => {
            const dim = EVALUATION_DIMENSIONS.find((d) => d.id === result.dimension)
            const expanded = expandedDimensions.has(result.dimension)
            return (
              <div key={result.dimension} className="rounded-xl border border-border bg-bg-card overflow-hidden">
                <button
                  onClick={() => {
                    setExpandedDimensions((prev) => {
                      const next = new Set(prev)
                      if (next.has(result.dimension)) next.delete(result.dimension)
                      else next.add(result.dimension)
                      return next
                    })
                  }}
                  className="w-full flex items-center gap-3 px-4 py-4 text-left hover:bg-bg-card-hover transition-colors"
                >
                  <div className={cn(
                    'w-10 h-10 rounded-lg flex items-center justify-center text-xs font-bold font-mono',
                    result.passed ? 'bg-brand-primary/10 text-brand-primary' : 'bg-severity-critical/10 text-severity-critical'
                  )}>
                    {scoreText(result.score)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-text-primary">{dimensionLabel(result.dimension, dim?.name)}</span>
                      <span className={cn(
                        'text-xs px-1.5 py-0.5 rounded',
                        result.passed ? 'bg-brand-primary/10 text-brand-primary' : 'bg-severity-critical/10 text-severity-critical'
                      )}>
                        {result.passed ? t('page.evaluation.state.pass') : t('page.evaluation.state.fail')}
                      </span>
                    </div>
                    <p className="text-xs text-text-muted mt-0.5 line-clamp-1">{dim?.description}</p>
                  </div>
                  {expanded ? (
                    <ChevronUp className="w-4 h-4 text-text-muted shrink-0" strokeWidth={1.25} />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-text-muted shrink-0" strokeWidth={1.25} />
                  )}
                </button>
                {expanded && (
                  <div className="px-4 pb-4 border-t border-border pt-3">
                    <p className="text-xs text-text-muted mb-2">{dim?.description ?? t('page.evaluation.dimension.hint')}</p>
                    <p className="text-sm text-text-secondary leading-relaxed">{result.details}</p>
                    <div className="mt-3">
                      <div className="flex items-center justify-between text-xs text-text-muted mb-1">
                        <span>{t('page.evaluation.score.label')}</span>
                        <span className={cn('font-mono font-bold', dimensionScoreClass(result))}>
                          {scoreText(result.score)}
                        </span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-bg-secondary overflow-hidden">
                        <div
                          className={cn('h-full rounded-full transition-all', dimensionBarClass(result))}
                          style={{ width: `${(result.score / DIMENSION_MAX_SCORE) * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* 伦理报告拉失败不该悄悄消失成"这次没有伦理问题"——空数据当正常值渲染
          正是最容易骗人的一种。404（本来就没跑伦理检查）不算故障，不提示。 */}
      {ethicsError !== null && !isNotGenerated(ethicsError) && (
        <div className="mb-6 flex items-start gap-2.5 rounded-xl border border-warm-orange/40 bg-warm-orange/5 p-3">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-warm-orange" strokeWidth={1.5} />
          <p className="text-xs text-text-secondary break-all">
            {/* 别写死"8 维"：维度条数来自 scorecard.results，后端 rubric 改了这句就成假话 */}
            {t('page.evaluation.ethics_error.desc', {
              message: tApiError(ethicsError, 'common.ui.unknown_error'),
              count: scorecard.results.length,
            })}
          </p>
        </div>
      )}

      {ethicsData.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-4">
          {/* lucide 调色板里没有 purple 语义 token；用品牌蓝保持一致，伦理摘要本就是辅助区 */}
          <Shield className="w-5 h-5 text-brand-primary" strokeWidth={1.25} />
            <h3 className="text-lg font-semibold text-text-primary">{t('page.evaluation.ethics.title')}</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {ethicsData.map((er) => (
              <div key={er.persona_id} className="rounded-xl border border-border bg-bg-card p-4">
                <div className="flex items-center gap-2 mb-3">
                  <User className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                  <span className="text-sm font-medium text-text-primary">{er.persona_id}</span>
                  <span className={cn(
                    'ml-auto text-xs px-2 py-0.5 rounded font-medium',
                    er.passed ? 'bg-brand-primary/10 text-brand-primary' : 'bg-severity-critical/10 text-severity-critical'
                  )}>
                    {er.passed ? t('page.evaluation.state.pass') : t('page.evaluation.state.fail')}
                  </span>
                </div>
                <div className="space-y-2">
                  <div>
                    <div className="flex items-center justify-between text-xs text-text-muted mb-1">
                      <span>{t('page.evaluation.ethics_score.label')}</span>
                      <span className={cn(
                        'font-mono font-bold',
                        er.score > 70 ? 'text-brand-primary' : er.score >= 50 ? 'text-severity-medium' : 'text-severity-critical'
                      )}>
                        {formatNumber(er.score)}
                      </span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-bg-secondary overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full',
                          er.score > 70 ? 'bg-brand-primary' : er.score >= 50 ? 'bg-severity-medium' : 'bg-severity-critical'
                        )}
                        style={{ width: `${er.score}%` }}
                      />
                    </div>
                  </div>
                  {/* 刻板印象风险是三档枚举，不是百分比：这里只给档位徽标，
                      不再做百分比和进度条——把枚举画成进度条是在编造精度。 */}
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-muted">{t('page.evaluation.stereotype.label')}</span>
                    <span className={cn(
                      'px-2 py-0.5 rounded font-medium',
                      stereotypeRiskBadgeClass(er.stereotype_risk)
                    )}>
                      {stereotypeRiskLabel(er.stereotype_risk)}
                    </span>
                  </div>
                  {er.violations.length > 0 && (
                    <div className="pt-1">
                      <div className="text-xs text-text-muted mb-1.5">
                        {t('page.evaluation.violations.label', { count: er.violations.length })}
                      </div>
                      <ul className="space-y-1.5">
                        {er.violations.map((v, i) => (
                          <li key={`${v.rule ?? 'legacy'}-${i}`} className="rounded-lg bg-bg-secondary/60 px-2 py-1.5">
                            <div className="flex items-center gap-1.5 mb-0.5">
                              <span className={cn(
                                'px-1.5 py-0.5 rounded text-[10px] font-medium',
                                ETHICS_SEVERITY_BADGE_CLASSES[v.severity]
                              )}>
                                {ETHICS_SEVERITY_LABELS[v.severity]}
                              </span>
                              {v.rule && (
                                <code className="text-[10px] font-mono text-text-primary break-all">{v.rule}</code>
                              )}
                            </div>
                            <p className="text-xs text-text-secondary leading-relaxed">{v.detail}</p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
        <div className="flex items-center gap-2 mb-3">
          <Clock className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
          <h3 className="text-sm font-medium text-text-muted">{t('page.evaluation.timeline.title')}</h3>
        </div>
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-text-secondary">{t('page.evaluation.created.label')}</span>
            <span className="text-text-muted font-mono text-xs">{formatTime(review.created_at)}</span>
          </div>
          {review.completed_at && (
            <div className="flex items-center gap-2">
              <span className="text-text-secondary">{t('page.evaluation.completed.label')}</span>
              <span className="text-text-muted font-mono text-xs">{formatTime(review.completed_at)}</span>
            </div>
          )}
          {skill && (
            <div className="flex items-center gap-2">
              <span className="text-text-secondary">{t('page.evaluation.skill.label')}</span>
              {/* SKILLS[].icon 是图片路径不是 emoji，直接当文本渲染会显示出路径 */}
              <span className={cn('flex items-center gap-1.5 text-xs', skill.color)}>
                <img src={skill.icon} alt="" className="h-4 w-4 object-contain" loading="lazy" />
                {skill.name}
              </span>
            </div>
          )}
        </div>
      </div>
    </PageShell>
  )
}
