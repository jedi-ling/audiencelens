/**
 * 判断复利闭环 —— 产品的护城河页面。
 *
 * 一次性评审工具跑完就断了；这一页把每条预测留档，
 * 等真人测试回来回填结果，于是能回答"我们的判断历史上准不准"。
 *
 * 诚实原则（写进 UI，不只是写在文档里）：
 * 样本量不足时必须显示"不具统计意义"，绝不用 3 个样本吹准确率。
 */

import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ApiError, api } from '@/lib/apiClient'
import type {
  ConfidenceCalibration,
  HitRate,
  Judgment,
  LeaderboardEntry,
  ValidationMetrics,
  Verdict,
} from '@/lib/types'
import { PageShell, PageHeader, SectionCard, EmptyState } from '@/components/ui'
import { Inbox } from 'lucide-react'
import { t } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import { formatDateTime, formatNumber, formatPercent, formatUsd } from '@/i18n/format'
import { tApiErrorParts } from '@/i18n/api-error'
import type { PlainMessageKey } from '@/i18n/keys.gen'

/**
 * 回填结果 → 文案 key。
 *
 * 存的是 **key 不是文案**：这张表在模块求值时就固定了，存翻译结果的话切换语言
 * 不会重新求值，徽标会一直停在打开页面时的那种语言。
 */
const VERDICT_LABEL_KEYS: Record<Verdict, PlainMessageKey> = {
  hit: 'page.ledger.state.hit',
  partial: 'page.ledger.state.partial',
  miss: 'page.ledger.state.miss',
  unknown: 'page.ledger.state.unknown',
}

// 复用 App 自有的语义色 token（而非独立的 Tailwind 调色板），
// 确保在暗色背景上有足够对比度，与全站视觉语言一致。
const VERDICT_STYLES: Record<Verdict, string> = {
  hit: 'bg-brand-primary/10 text-brand-primary border-brand-primary/30',
  partial: 'bg-warm-orange/10 text-warm-orange border-warm-orange/30',
  miss: 'bg-severity-critical/10 text-severity-critical border-severity-critical/30',
  unknown: 'bg-bg-secondary text-text-muted border-border',
}

export default function LedgerPage() {
  useDocumentTitle('page.ledger.meta.title')
  const [judgments, setJudgments] = useState<Judgment[]>([])
  const [stats, setStats] = useState<HitRate | null>(null)
  const [board, setBoard] = useState<LeaderboardEntry[]>([])
  const [valueMetrics, setValueMetrics] = useState<ValidationMetrics | null>(null)
  const [calibration, setCalibration] = useState<ConfidenceCalibration | null>(null)
  // 你 vs 评审团。scoreboard 在任一方没有已定论样本时会给 comparable=false，
  // 那种情况下只列数字不下结论——不拿 0/0 拼一个"你领先"。
  const [scoreboard, setScoreboard] = useState<Awaited<ReturnType<typeof api.ledgerScoreboard>> | null>(null)
  // ?pending=1 进来时直接筛到"只看待验证"。
  // 首页那张待验证追踪卡写着「3 条未回填」，点进来却是全部记录混在一起、
  // 要用户自己发现那个勾选框——承诺和落点对不上。带上这个参数就对上了。
  const [searchParams] = useSearchParams()
  const [onlyUnverified, setOnlyUnverified] = useState(
    searchParams.get('pending') === '1'
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  // 回填是本页唯一的写操作，失败必须逐条看得见：以前 verify() 全程没有 try/catch，
  // 请求被拒之后按钮跟没点过一样，用户会以为"填了"。
  const [verifyingId, setVerifyingId] = useState<string | null>(null)
  const [verifyError, setVerifyError] = useState<{ id: string; error: Error } | null>(null)

  // 后端 message 的语种由 tApiErrorParts 按 message_lang 判定：语种对得上就直接用
  // （它比 10 个粗 code 具体得多），对不上就出前端译文、把后端原文降级成 detail。
  // detail 挂 title 属性而不是并排渲染——英文界面上并排一句中文，用户会以为界面坏了。
  const errorText = error ? tApiErrorParts(error, 'common.ui.unknown_error') : null
  const verifyErrorText = verifyError
    ? tApiErrorParts(verifyError.error, 'common.ui.unknown_error')
    : null

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [j, s, b, v, c, sb] = await Promise.all([
        api.listJudgments({ onlyUnverified }),
        api.hitRate(),
        api.leaderboard(),
        api.validationMetrics(),
        api.calibration(),
        api.ledgerScoreboard(),
      ])
      setJudgments(j.judgments)
      setStats(s)
      setBoard(b.personas)
      setValueMetrics(v)
      setCalibration(c)
      setScoreboard(sb)
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)))
    } finally {
      setLoading(false)
    }
  }, [onlyUnverified])

  useEffect(() => {
    void load()
  }, [load])

  const verify = async (id: string, verdict: Verdict) => {
    setVerifyError(null)
    setVerifyingId(id)
    try {
      await api.verifyJudgment(id, verdict)
      await load()
    } catch (e) {
      // 挂在这条预测上而不是页面顶部：清单可能很长，顶部一条提示看不出是哪条没填上
      setVerifyError({ id, error: e instanceof Error ? e : new Error(String(e)) })
    } finally {
      setVerifyingId(null)
    }
  }

  return (
    <PageShell size="reading">
      <PageHeader title={t('page.ledger.header.title')} subtitle={t('page.ledger.header.desc')} />

      {error && errorText && (
        <div className="mb-6 rounded-lg border border-severity-critical/40 bg-severity-critical/10 p-4 text-sm text-text-primary">
          <p className="font-medium">{t('page.ledger.error.title')}</p>
          <p
            className="mt-1 whitespace-pre-wrap break-words text-text-secondary"
            title={errorText.detail}
          >
            {errorText.text}
          </p>
          {needsLogin(error) && (
            <p className="mt-1 text-text-secondary">{t('page.ledger.error.hint')}</p>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              onClick={() => void load()}
              disabled={loading}
              className="rounded-md border border-border bg-bg-card px-3 py-1.5 text-xs text-text-secondary hover:border-brand-primary/30 hover:text-brand-primary disabled:opacity-50"
            >
              {loading ? t('page.ledger.error.pending') : t('common.action.retry')}
            </button>
            {needsLogin(error) && (
              <Link
                to="/login"
                className="rounded-md bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-primary-dim"
              >
                {t('page.ledger.error.cta')}
              </Link>
            )}
          </div>
        </div>
      )}

      {valueMetrics && (
        <SectionCard className="mb-6 border-brand-primary/30">
          <h2 className="mb-4 font-display text-sm font-semibold text-text-primary">
            {t('page.ledger.value.title')}
          </h2>
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-5">
            <Stat
              label={t('page.ledger.feedback_coverage.label')}
              value={percent(valueMetrics.feedback_coverage)}
            />
            <Stat
              label={t('page.ledger.useful_rate.label')}
              value={percent(valueMetrics.useful_rate)}
            />
            <Stat
              label={t('page.ledger.decision_change.label')}
              value={percent(valueMetrics.decision_change_rate)}
            />
            <Stat
              label={t('page.ledger.adoption.label')}
              value={percent(valueMetrics.adoption_rate)}
            />
            <Stat
              label={t('page.ledger.hours_saved.label')}
              value={t('page.ledger.hours_saved.value', {
                hours: formatNumber(valueMetrics.hours_saved),
              })}
            />
          </div>
          <div className="mt-5 grid grid-cols-2 gap-4 border-t border-border pt-4 sm:grid-cols-4">
            <Stat
              label={t('page.ledger.avg_model_cost.label')}
              value={money(valueMetrics.average_model_cost_usd)}
            />
            <Stat
              label={t('page.ledger.cost_per_useful.label')}
              value={money(valueMetrics.cost_per_useful_review_usd)}
            />
            <Stat
              label={t('page.ledger.cost_per_adopted.label')}
              value={money(valueMetrics.cost_per_adopted_fix_usd)}
            />
            <Stat
              label={t('page.ledger.avg_willingness.label')}
              value={money(valueMetrics.average_willingness_to_pay_usd)}
            />
          </div>
          {valueMetrics.by_task_type.length > 0 && (
            <div className="mt-5 border-t border-border pt-4">
              <h3 className="mb-2 text-xs font-semibold text-text-secondary">
                {t('page.ledger.by_task_type.title')}
              </h3>
              <div className="space-y-2">
                {valueMetrics.by_task_type.map((row) => (
                  <div key={row.task_type} className="grid grid-cols-[1fr_auto_auto] gap-4 text-xs">
                    <span className="font-mono text-text-secondary">{row.task_type} {row.low_confidence && '⚠️'}</span>
                    <span className="text-text-primary">
                      {t('page.ledger.task_useful.value', { value: percent(row.useful_rate) })}
                    </span>
                    <span className="text-text-primary">
                      {t('page.ledger.task_adopted.value', { value: percent(row.adoption_rate) })}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {valueMetrics.top_adopted_fixes.length > 0 && (
            <div className="mt-5 border-t border-border pt-4">
              <h3 className="mb-2 text-xs font-semibold text-text-secondary">
                {t('page.ledger.top_fixes.title')}
              </h3>
              <ol className="space-y-2">
                {valueMetrics.top_adopted_fixes.map((fix) => (
                  <li key={fix.title} className="flex justify-between gap-4 text-xs text-text-primary">
                    <span>{fix.title}</span>
                    <span className="font-mono text-brand-primary">
                      {t('page.ledger.top_fixes.value', {
                        times: formatNumber(fix.adoption_count),
                      })}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          )}
          {/* note 是后端产出的自由文本，前端翻不了；它带 ⚠️ 前缀出现在这里就是原样转述 */}
          {valueMetrics.note && <p className="mt-4 text-xs text-warm-orange">⚠️ {valueMetrics.note}</p>}
        </SectionCard>
      )}

      {/* 你 vs 评审团。
          这一块是判断留档从"给工具打分"变成"给你自己打分"的落点：
          回填一次同时算两边，而我们的 ground truth 是真人测试结果，
          不掺股价那种运气噪音，所以这个对比是可信的。
          comparable=false（任一方没有已定论样本）时只列数字不下结论。 */}
      {scoreboard && (scoreboard.panel.sample_size > 0 || scoreboard.user.sample_size > 0) && (
        <SectionCard className="mb-6">
          <h2 className="mb-1 font-display text-sm font-semibold text-text-primary">
            {t('page.ledger.scoreboard.title')}
          </h2>
          <p className="mb-4 text-xs leading-relaxed text-text-muted">
            {t('page.ledger.scoreboard.desc')}
          </p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {([
              { key: 'panel', side: scoreboard.panel, label: t('page.ledger.state.side_panel'), tone: 'text-brand-primary' },
              { key: 'user', side: scoreboard.user, label: t('page.ledger.state.side_user'), tone: 'text-cyan' },
            ] as const).map(({ key, side, label, tone }) => (
              <div key={key} className="rounded-xl border border-border bg-bg-secondary p-4">
                <p className={`text-xs font-medium ${tone}`}>{label}</p>
                <p className="mt-1 font-display text-2xl font-semibold text-text-primary">
                  {side.sample_size > 0 ? percent(side.hit_rate) : '—'}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  {t('page.ledger.side.meta', {
                    hit: side.hit,
                    partial: side.partial,
                    miss: side.miss,
                    total: side.sample_size,
                  })}
                </p>
                {/* 样本不足必须写在数字旁边而不是页脚——诚实原则写进 UI */}
                {side.sample_size > 0 && side.low_confidence && (
                  <p className="mt-1.5 text-[11px] leading-4 text-warm-orange">
                    {t('page.ledger.side.hint')}
                  </p>
                )}
              </div>
            ))}
          </div>
          {!scoreboard.comparable && scoreboard.note && (
            <p className="mt-3 border-t border-border pt-3 text-xs text-text-muted">
              {scoreboard.note}
            </p>
          )}
        </SectionCard>
      )}

      {/* 命中率总览 */}
      {stats && (
        <SectionCard className="mb-6">
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
            <Stat
              label={t('page.ledger.total_judgments.label')}
              value={formatNumber(stats.total_judgments)}
            />
            <Stat
              label={t('page.ledger.pending_verification.label')}
              value={formatNumber(stats.pending_verification)}
            />
            <Stat label={t('page.ledger.verified.label')} value={formatNumber(stats.sample_size)} />
            <Stat label={t('page.ledger.hit_rate.label')} value={percent(stats.hit_rate)} />
          </div>
          {/* 诚实标注：样本不足绝不吹准确率 */}
          {stats.note && (
            <p className="mt-4 rounded-md border border-warm-orange/30 bg-warm-orange/10 px-3 py-2 text-xs font-medium text-warm-orange">
              ⚠️ {stats.note}
            </p>
          )}
        </SectionCard>
      )}

      {/* 人格命中率排行 */}
      {board.length > 0 && (
        <SectionCard className="mb-6">
          <h2 className="mb-4 font-display text-sm font-semibold text-text-primary">
            {t('page.ledger.leaderboard.title')}
          </h2>
          <div className="space-y-2">
            {board.map((p) => (
              <div key={p.persona_id} className="flex items-center gap-3 text-sm">
                <span className="w-40 truncate font-mono text-xs text-text-secondary">{p.persona_id}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-bg-secondary">
                  <div
                    className="h-full rounded-full bg-brand-primary"
                    style={{ width: `${(p.hit_rate ?? 0) * 100}%` }}
                  />
                </div>
                <span className="w-12 text-right font-mono tabular-nums text-text-primary">
                  {percent(p.hit_rate)}
                </span>
                <span className="w-20 text-right font-mono text-xs text-text-muted">
                  {t('page.ledger.sample.value', { size: formatNumber(p.sample_size) })}
                  {p.low_confidence && ' ⚠️'}
                </span>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* 置信度校准。
          与上面「谁的判断最值得听」的分工：那张榜回答"说中了几次"，
          这一块回答"说自己有把握的时候准不准"——一个恒说 90% 却只对一半的面板，
          命中率榜上看不出问题，校准能。 */}
      <CalibrationSection data={calibration} />

      {/* 预测清单 + 回填 */}
      <SectionCard className="p-0">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-6 py-4">
          <h2 className="font-display text-sm font-semibold text-text-primary">
            {t('page.ledger.list.title')}
          </h2>
          {/* 回填的真实后果就写在动作旁边：被判 miss 的判断不再进同项目下次评审
              的上下文（project_memory_service 红线 1）。用户知道这个按钮有后果，
              才有理由点它——这句是机制描述，不是鼓励语。 */}
          <span className="basis-full text-xs text-text-muted md:basis-auto">
            {t('page.ledger.list.hint')}
          </span>
          <label className="ml-auto flex items-center gap-2 text-xs text-text-secondary">
            <input
              type="checkbox"
              checked={onlyUnverified}
              onChange={(e) => setOnlyUnverified(e.target.checked)}
              className="accent-brand-primary"
            />
            {t('page.ledger.list.label')}
          </label>
        </div>

        {loading ? (
          <p className="p-6 text-sm text-text-secondary">{t('common.ui.loading')}</p>
        ) : error ? (
          // 加载失败时这里曾照样打出"还没有预测记录"——把一次失败说成了"你没有数据"，
          // 正是本仓库要根除的那种伪装。原因和重试按钮在上方横幅里。
          <p className="p-6 text-sm text-text-secondary">{t('page.ledger.list.error')}</p>
        ) : judgments.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title={t('page.ledger.list_empty.title')}
            description={t('page.ledger.list_empty.desc')}
            className="border-0 rounded-none"
          />
        ) : (
          <ul className="divide-y divide-border">
            {judgments.map((j) => (
              <li key={j.id} className="px-6 py-4">
                <div className="flex items-start gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-text-primary">{j.claim}</p>
                    <p className="mt-1 font-mono text-xs text-text-muted">
                      {/* 三段拼在一条 key 里而不是在 JSX 里串起来：分隔符与顺序属于文案，
                          英文侧要能整句重排。severity 是后端自由文本，原样透出。 */}
                      {t('page.ledger.item.meta', {
                        author: j.persona_id ?? t('page.ledger.panel.label'),
                        severity: j.severity ?? t('page.ledger.stat.empty'),
                        time: j.predicted_at
                          ? formatDateTime(j.predicted_at)
                          : t('page.ledger.stat.empty'),
                      })}
                    </p>
                  </div>

                  {j.outcome ? (
                    <span
                      className={`shrink-0 rounded-md border px-2.5 py-1 text-xs font-medium ${
                        VERDICT_STYLES[j.outcome.verdict]
                      }`}
                    >
                      {t(VERDICT_LABEL_KEYS[j.outcome.verdict])}
                    </span>
                  ) : (
                    <div className="flex shrink-0 gap-1.5">
                      {(['hit', 'partial', 'miss'] as Verdict[]).map((v) => (
                        <button
                          key={v}
                          disabled={verifyingId !== null}
                          className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-opacity hover:opacity-80 disabled:opacity-40 ${VERDICT_STYLES[v]}`}
                          onClick={() => void verify(j.id, v)}
                        >
                          {verifyingId === j.id
                            ? t('common.ui.submitting')
                            : t(VERDICT_LABEL_KEYS[v])}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* 回填失败：这条记录的状态没有变，必须当场说清楚，
                    否则用户会以为已经填过了（按钮回弹得跟成功一模一样）。 */}
                {verifyError?.id === j.id && verifyErrorText && (
                  <div className="mt-3 rounded-md border border-severity-critical/40 bg-severity-critical/10 px-3 py-2 text-xs text-text-primary">
                    <p className="font-medium">{t('page.ledger.verify_error.title')}</p>
                    <p
                      className="mt-1 whitespace-pre-wrap break-words text-text-secondary"
                      title={verifyErrorText.detail}
                    >
                      {verifyErrorText.text}
                    </p>
                    {needsLogin(verifyError.error) && (
                      <Link
                        to="/login"
                        className="mt-2 inline-block rounded-md bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-primary-dim"
                      >
                        {t('page.ledger.verify_error.cta')}
                      </Link>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </PageShell>
  )
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div>
      <div className="font-display text-2xl font-bold tabular-nums text-text-primary">{value}</div>
      <div className="mt-1 text-xs text-text-muted">{label}</div>
    </div>
  )
}

/**
 * 这个错误该不该把用户引到登录页。
 *
 * /ledger/* 现在对未登录访客一律 401（后端 deps.require_isolated_identity：
 * 未登录访客共用同一个匿名身份，无法区分谁的台账是谁的）。也就是说"被拒"在
 * 多租户形态下是常态路径而不是异常，提示必须给得出下一步动作。
 */
function needsLogin(error: Error): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403)
}

/** null = 这个指标没有值，显示「—」而不是 0。数字部分走 @/i18n/format，跟界面语言同源。 */
function percent(value: number | null): string {
  return value === null ? t('page.ledger.stat.empty') : formatPercent(value)
}

function money(value: number | null): string {
  return value === null ? t('page.ledger.stat.empty') : formatUsd(value)
}

/**
 * 置信度校准区块。
 *
 * 展示纪律（和本页其它指标一致）：
 *   · 样本不足时挂 low_confidence，如实说"不具统计意义"，不拿几个样本谈校准
 *   · 所有指标为 null 时显示「—」而不是 0——Brier 越低越好，把"没数据"画成 0
 *     等于把空账本显示成满分预测
 *   · Brier / ECE 这类术语必须自带一句人话解释，否则它只是看起来专业
 */
function CalibrationSection({ data }: { data: ConfidenceCalibration | null }) {
  // 一条都没回填过就不显示——空区块只会让页面显得更长，不会让人更懂
  if (!data || data.sample_size === 0) return null

  const bins = data.bins.filter((b) => b.sample_size > 0)

  return (
    <SectionCard className="mb-6">
      <h2 className="mb-1 font-display text-sm font-semibold text-text-primary">
        {t('page.ledger.calibration.title')}
      </h2>
      <p className="mb-4 text-xs leading-relaxed text-text-muted">
        {t('page.ledger.calibration.desc')}
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <CalibStat
          label={t('page.ledger.mean_confidence.label')}
          value={percent(data.mean_predicted_confidence)}
        />
        <CalibStat
          label={t('page.ledger.observed_hit.label')}
          value={percent(data.observed_hit_score)}
          hint={t('page.ledger.observed_hit.hint')}
        />
        <CalibStat
          label={t('page.ledger.brier.label')}
          value={
            data.brier_score === null
              ? t('page.ledger.stat.empty')
              : formatNumber(data.brier_score, 3)
          }
          hint={t('page.ledger.brier.hint')}
        />
        <CalibStat
          label={t('page.ledger.ece.label')}
          value={
            data.expected_calibration_error === null
              ? t('page.ledger.stat.empty')
              : formatNumber(data.expected_calibration_error, 3)
          }
          hint={t('page.ledger.ece.hint')}
        />
      </div>

      {bins.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs font-semibold text-text-secondary">
            {t('page.ledger.bins.title')}
          </p>
          <div className="space-y-1.5">
            {bins.map((b) => {
              const over = (b.mean_confidence ?? 0) > (b.observed_hit_score ?? 0)
              return (
                <div key={`${b.lower}-${b.upper}`} className="flex items-center gap-3 text-xs">
                  <span className="w-20 shrink-0 font-mono text-text-muted">
                    {t('page.ledger.bins.value', {
                      lower: formatNumber(b.lower * 100, 0),
                      upper: formatNumber(b.upper * 100, 0),
                    })}
                  </span>
                  <span className="w-24 shrink-0 font-mono tabular-nums text-text-secondary">
                    {t('page.ledger.bin_claimed.value', { value: percent(b.mean_confidence) })}
                  </span>
                  <span className="w-24 shrink-0 font-mono tabular-nums text-text-primary">
                    {t('page.ledger.bin_observed.value', { value: percent(b.observed_hit_score) })}
                  </span>
                  {/* 高估/低估都要标出来：只标高估会让人以为低估无害，
                      而系统性低估同样意味着这套权重没校准 */}
                  <span
                    className={
                      (b.gap ?? 0) >= 0.2
                        ? over
                          ? 'text-severity-critical'
                          : 'text-warm-orange'
                        : 'text-text-muted'
                    }
                  >
                    {b.gap === null
                      ? ''
                      : over
                        ? t('page.ledger.over_estimate.value', { value: percent(b.gap) })
                        : t('page.ledger.under_estimate.value', { value: percent(b.gap) })}
                  </span>
                  <span className="ml-auto font-mono text-text-muted">
                    {t('page.ledger.sample.value', { size: formatNumber(b.sample_size) })}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <p className="mt-4 border-t border-border pt-3 text-[11px] leading-relaxed text-text-muted">
        {data.low_confidence && (
          <span className="text-warm-orange">
            {/* data.note 是后端文案，取不到时前端自己说一遍——这不是缺译兜底，
                是"后端没给这句话"时本来就该有的说明。 */}
            ⚠️ {data.note ?? t('page.ledger.low_confidence.hint', { count: data.sample_size })}{' '}
          </span>
        )}
        {data.excluded_rows > 0
          ? t('page.ledger.excluded_rows.value', {
              verified: formatNumber(data.verified_rows),
              count: data.excluded_rows,
            })
          : t('page.ledger.verified_rows.value', { count: data.verified_rows })}{' '}
        {t('page.ledger.calibration.hint')}
      </p>
    </SectionCard>
  )
}

function CalibStat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-border bg-bg-secondary p-3">
      <p className="text-xs text-text-muted">{label}</p>
      <p className="mt-1 font-display text-lg tabular-nums text-text-primary">{value}</p>
      {hint && <p className="mt-0.5 text-[10px] leading-tight text-text-muted">{hint}</p>}
    </div>
  )
}
