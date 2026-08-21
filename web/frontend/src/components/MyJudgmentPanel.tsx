/**
 * 「我的判断」—— 用户在报告出来后记录自己的看法。
 *
 * 为什么需要它：判断留档层此前**只记评审团的预测**，回填之后也只能回答
 * "评审团准不准"。而用户真正关心的是自己的判断在不在变准——一个只给工具
 * 打分的系统，用户没有长期用它的理由。
 *
 * 与 ARTi「创建我的判断」的对应与差异：
 *   · 对应 —— 都是"AI 给了判断之后，让用户留下自己的那一份"，都进同一套留档。
 *   · 差异 —— 他们的字段是股票的（周期/方向/目标价），我们的是产品评审的
 *     （同意与否 + 把握 + 理由）。更关键的是 ground truth：他们用股价验证，
 *     掺"赶上普涨"的运气噪音；我们用真人测试结果验证，是干净的对照。
 *     所以"你 vs 评审团"这个对比在我们这里才真的可信。
 *
 * 三条边界：
 * 1. **匿名不显示。** 判断按 user_id 隔离，匿名桶是所有访客共用的，
 *    记了也无法归属到"你"，那这个功能就没有意义。
 * 2. **一次评审记一条。** 提交后收起换成回执，不做成可反复提交的表单——
 *    留档的价值在于"当时你是怎么想的"，允许改写就等于允许事后修改历史。
 * 3. **不预填、不诱导。** 理由是可多选的 chip，但默认一个都不选；
 *    把握度默认空缺而不是给个 0.7——替用户填的数字会污染校准曲线。
 */
import { useState } from 'react'
import { CheckCircle2, PenLine, Loader2 } from 'lucide-react'
import { api, getToken } from '@/lib/apiClient'
import { tApiError } from '@/i18n/api-error'
import { t } from '@/i18n/runtime'
import { cn } from '@/lib/utils'

type Stance = 'agree' | 'disagree' | 'partial'

/** 立场三选一。key 写成字面量常量而不是模板拼接：拼接出来的是 string，
 *  t() 的键存在性校验就失效了（后端/语料改名时编译期发现不了）。 */
const STANCE_KEYS = [
  { v: 'agree' as const, k: 'page.report.state.stance_agree' as const },
  { v: 'partial' as const, k: 'page.report.state.stance_partial' as const },
  { v: 'disagree' as const, k: 'page.report.state.stance_disagree' as const },
]

/** 理由 chip 的 key。用闭集而不是自由文本框：自由文本无法聚合分析，
 *  而这批理由的价值恰恰在于"你不同意评审团的时候，通常是因为什么"。 */
const RATIONALE_KEYS = [
  'page.report.reason.rationale_own_data',
  'page.report.reason.rationale_priority',
  'page.report.reason.rationale_persona_fit',
  'page.report.reason.rationale_evidence_weak',
  'page.report.reason.rationale_cost',
] as const

export default function MyJudgmentPanel({
  reviewId,
  panelRecommendation,
}: {
  reviewId: string
  /** 评审团的主流建议，作为「同意」时落库的 claim —— 用户点"同意"时
   *  留档的必须是**具体内容**而不是"agree"这个词，否则日后回填时
   *  没人知道当初同意的是什么。 */
  panelRecommendation?: string
}) {
  const [open, setOpen] = useState(false)
  const [stance, setStance] = useState<Stance>('agree')
  const [claim, setClaim] = useState('')
  const [confidence, setConfidence] = useState<number | null>(null)
  const [rationale, setRationale] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 边界 1：匿名不显示
  if (!getToken()) return null

  const submit = async (quickAgree: boolean) => {
    const finalStance: Stance = quickAgree ? 'agree' : stance
    const finalClaim = quickAgree
      ? panelRecommendation?.trim() || t('page.report.my_judgment.empty')
      : claim.trim()
    if (!finalClaim) {
      setError(t('page.report.my_judgment.error'))
      return
    }
    setSaving(true)
    setError(null)
    try {
      await api.createMyJudgment(reviewId, {
        claim: finalClaim,
        stance: finalStance,
        confidence: confidence ?? undefined,
        rationale: [...rationale].map((k) => t(k as (typeof RATIONALE_KEYS)[number])),
      })
      setSaved(true)
      setOpen(false)
    } catch (e) {
      setError(tApiError(e, 'page.report.my_judgment.error'))
    } finally {
      setSaving(false)
    }
  }

  // 边界 2：提交后收起换回执，不允许反复改写
  if (saved) {
    return (
      <div className="mb-6 flex items-center gap-2 rounded-xl border border-cyan/30 bg-cyan/5 px-4 py-3 text-sm text-cyan">
        <CheckCircle2 className="h-4 w-4 shrink-0" strokeWidth={1.75} />
        {t('page.report.my_judgment.success')}
      </div>
    )
  }

  return (
    <div className="mb-6 rounded-xl border border-border bg-bg-card p-4 md:p-5">
      <div className="mb-1 flex items-center gap-2">
        <PenLine className="h-4 w-4 text-cyan" strokeWidth={1.25} />
        <h3 className="text-sm font-semibold text-text-primary">{t('page.report.my_judgment.title')}</h3>
      </div>
      <p className="mb-3 text-xs leading-relaxed text-text-muted">
        {t('page.report.my_judgment.desc')}
      </p>

      {!open ? (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => void submit(true)}
            disabled={saving}
            className="inline-flex items-center gap-1.5 rounded-md border border-cyan/40 bg-cyan/10 px-3 py-1.5 text-xs font-medium text-cyan transition-colors hover:bg-cyan/15 disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} /> : <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={1.5} />}
            {t('page.report.my_judgment.confirm')}
          </button>
          <button
            onClick={() => setOpen(true)}
            className="rounded-md border border-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:text-text-primary"
          >
            {t('page.report.my_judgment.cta')}
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {/* 立场 */}
          <div className="flex flex-wrap gap-1.5">
            {STANCE_KEYS.map(({ v, k }) => (
              <button
                key={v}
                onClick={() => setStance(v)}
                className={cn(
                  'rounded-md border px-2.5 py-1 text-xs transition-colors',
                  stance === v
                    ? 'border-cyan/50 bg-cyan/10 text-cyan'
                    : 'border-border text-text-muted hover:text-text-secondary'
                )}
              >
                {t(k)}
              </button>
            ))}
          </div>

          {/* 判断正文 */}
          <textarea
            value={claim}
            onChange={(e) => setClaim(e.target.value)}
            rows={2}
            placeholder={t('page.report.my_judgment.placeholder')}
            className="w-full resize-none rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none focus:border-cyan/40"
          />

          {/* 把握度。边界 3：默认空缺而不是预填一个数——替用户填会污染校准曲线 */}
          <div className="flex items-center gap-2 text-xs">
            <span className="shrink-0 text-text-muted">{t('page.report.my_confidence.label')}</span>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={confidence === null ? 50 : Math.round(confidence * 100)}
              onChange={(e) => setConfidence(Number(e.target.value) / 100)}
              className="flex-1 accent-cyan"
            />
            <span className="w-16 shrink-0 text-right font-mono text-text-secondary">
              {confidence === null ? t('page.report.my_confidence.empty') : `${Math.round(confidence * 100)}%`}
            </span>
          </div>

          {/* 理由（可多选，默认不选） */}
          <div className="flex flex-wrap gap-1.5">
            {RATIONALE_KEYS.map((k) => (
              <button
                key={k}
                onClick={() =>
                  setRationale((prev) => {
                    const next = new Set(prev)
                    if (next.has(k)) next.delete(k)
                    else next.add(k)
                    return next
                  })
                }
                className={cn(
                  'rounded-md border px-2 py-1 text-xs transition-colors',
                  rationale.has(k)
                    ? 'border-cyan/40 bg-cyan/10 text-cyan'
                    : 'border-border text-text-muted hover:text-text-secondary'
                )}
              >
                {t(k)}
              </button>
            ))}
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => void submit(false)}
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-md bg-cyan px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} />}
              {t('page.report.my_judgment_save.cta')}
            </button>
            <button
              onClick={() => setOpen(false)}
              className="rounded-md border border-border px-3 py-1.5 text-xs text-text-muted transition-colors hover:text-text-secondary"
            >
              {t('common.action.cancel')}
            </button>
          </div>
        </div>
      )}

      {error && <p className="mt-2 text-xs text-severity-critical">{error}</p>}
    </div>
  )
}
