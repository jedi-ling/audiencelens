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
import { Link } from 'react-router'
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

const VERDICT_LABELS: Record<Verdict, string> = {
  hit: '说中了',
  partial: '部分成立',
  miss: '没发生',
  unknown: '暂无法判定',
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
  const [judgments, setJudgments] = useState<Judgment[]>([])
  const [stats, setStats] = useState<HitRate | null>(null)
  const [board, setBoard] = useState<LeaderboardEntry[]>([])
  const [valueMetrics, setValueMetrics] = useState<ValidationMetrics | null>(null)
  const [calibration, setCalibration] = useState<ConfidenceCalibration | null>(null)
  const [onlyUnverified, setOnlyUnverified] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  // 回填是本页唯一的写操作，失败必须逐条看得见：以前 verify() 全程没有 try/catch，
  // 请求被拒之后按钮跟没点过一样，用户会以为"填了"。
  const [verifyingId, setVerifyingId] = useState<string | null>(null)
  const [verifyError, setVerifyError] = useState<{ id: string; error: Error } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [j, s, b, v, c] = await Promise.all([
        api.listJudgments({ onlyUnverified }),
        api.hitRate(),
        api.leaderboard(),
        api.validationMetrics(),
        api.calibration(),
      ])
      setJudgments(j.judgments)
      setStats(s)
      setBoard(b.personas)
      setValueMetrics(v)
      setCalibration(c)
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
      <PageHeader
        title="判断复利"
        subtitle="每次评审的预测都盖了时间戳留档。真人测试回来后回填结果——判断准不准，从此有据可查。"
      />

      {error && (
        <div className="mb-6 rounded-lg border border-severity-critical/40 bg-severity-critical/10 p-4 text-sm text-text-primary">
          <p className="font-medium">判断复利数据加载失败</p>
          <p className="mt-1 whitespace-pre-wrap break-words text-text-secondary">{error.message}</p>
          {needsLogin(error) && (
            <p className="mt-1 text-text-secondary">
              这一页放的是「属于你自己的」预测台账，未登录时后端无法区分谁是谁，所以拒绝返回。
            </p>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              onClick={() => void load()}
              disabled={loading}
              className="rounded-md border border-border bg-bg-card px-3 py-1.5 text-xs text-text-secondary hover:border-brand-primary/30 hover:text-brand-primary disabled:opacity-50"
            >
              {loading ? '重试中…' : '重试'}
            </button>
            {needsLogin(error) && (
              <Link
                to="/login"
                className="rounded-md bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-primary-dim"
              >
                登录 / 注册
              </Link>
            )}
          </div>
        </div>
      )}

      {valueMetrics && (
        <SectionCard className="mb-6 border-brand-primary/30">
          <h2 className="mb-4 font-display text-sm font-semibold text-text-primary">产品价值验证</h2>
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-5">
            <Stat label="反馈覆盖" value={percent(valueMetrics.feedback_coverage)} />
            <Stat label="认为有用" value={percent(valueMetrics.useful_rate)} />
            <Stat label="改变决策" value={percent(valueMetrics.decision_change_rate)} />
            <Stat label="建议采纳" value={percent(valueMetrics.adoption_rate)} />
            <Stat label="累计节省" value={`${valueMetrics.hours_saved}h`} />
          </div>
          <div className="mt-5 grid grid-cols-2 gap-4 border-t border-border pt-4 sm:grid-cols-4">
            <Stat label="平均模型成本" value={money(valueMetrics.average_model_cost_usd)} />
            <Stat label="每份有效报告成本" value={money(valueMetrics.cost_per_useful_review_usd)} />
            <Stat label="每条采纳成本" value={money(valueMetrics.cost_per_adopted_fix_usd)} />
            <Stat label="平均付费意愿" value={money(valueMetrics.average_willingness_to_pay_usd)} />
          </div>
          {valueMetrics.by_task_type.length > 0 && (
            <div className="mt-5 border-t border-border pt-4">
              <h3 className="mb-2 text-xs font-semibold text-text-secondary">按任务类型寻找最强切入点</h3>
              <div className="space-y-2">
                {valueMetrics.by_task_type.map((row) => (
                  <div key={row.task_type} className="grid grid-cols-[1fr_auto_auto] gap-4 text-xs">
                    <span className="font-mono text-text-secondary">{row.task_type} {row.low_confidence && '⚠️'}</span>
                    <span className="text-text-primary">有用 {percent(row.useful_rate)}</span>
                    <span className="text-text-primary">采纳 {percent(row.adoption_rate)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {valueMetrics.top_adopted_fixes.length > 0 && (
            <div className="mt-5 border-t border-border pt-4">
              <h3 className="mb-2 text-xs font-semibold text-text-secondary">真正被采纳的建议</h3>
              <ol className="space-y-2">
                {valueMetrics.top_adopted_fixes.map((fix) => (
                  <li key={fix.title} className="flex justify-between gap-4 text-xs text-text-primary">
                    <span>{fix.title}</span><span className="font-mono text-brand-primary">×{fix.adoption_count}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
          {valueMetrics.note && <p className="mt-4 text-xs text-warm-orange">⚠️ {valueMetrics.note}</p>}
        </SectionCard>
      )}

      {/* 命中率总览 */}
      {stats && (
        <SectionCard className="mb-6">
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
            <Stat label="累计预测" value={stats.total_judgments} />
            <Stat label="待验证" value={stats.pending_verification} />
            <Stat label="已验证" value={stats.sample_size} />
            <Stat
              label="命中率"
              value={stats.hit_rate === null ? '—' : `${(stats.hit_rate * 100).toFixed(0)}%`}
            />
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
          <h2 className="mb-4 font-display text-sm font-semibold text-text-primary">谁的判断最值得听</h2>
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
                  {p.hit_rate === null ? '—' : `${(p.hit_rate * 100).toFixed(0)}%`}
                </span>
                <span className="w-20 text-right font-mono text-xs text-text-muted">
                  n={p.sample_size}
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
        <div className="flex items-center gap-3 border-b border-border px-6 py-4">
          <h2 className="font-display text-sm font-semibold text-text-primary">历史预测</h2>
          <label className="ml-auto flex items-center gap-2 text-xs text-text-secondary">
            <input
              type="checkbox"
              checked={onlyUnverified}
              onChange={(e) => setOnlyUnverified(e.target.checked)}
              className="accent-brand-primary"
            />
            只看待验证
          </label>
        </div>

        {loading ? (
          <p className="p-6 text-sm text-text-secondary">加载中…</p>
        ) : error ? (
          // 加载失败时这里曾照样打出"还没有预测记录"——把一次失败说成了"你没有数据"，
          // 正是本仓库要根除的那种伪装。原因和重试按钮在上方横幅里。
          <p className="p-6 text-sm text-text-secondary">没能加载到预测记录，原因见上方。</p>
        ) : judgments.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="还没有预测记录"
            description="跑一次评审，系统会自动把结论留档。"
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
                      {j.persona_id ? `${j.persona_id} · ` : '评审团合议 · '}
                      {j.severity ?? '—'} ·{' '}
                      {j.predicted_at ? new Date(j.predicted_at).toLocaleString() : '—'}
                    </p>
                  </div>

                  {j.outcome ? (
                    <span
                      className={`shrink-0 rounded-md border px-2.5 py-1 text-xs font-medium ${
                        VERDICT_STYLES[j.outcome.verdict]
                      }`}
                    >
                      {VERDICT_LABELS[j.outcome.verdict]}
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
                          {verifyingId === j.id ? '提交中…' : VERDICT_LABELS[v]}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* 回填失败：这条记录的状态没有变，必须当场说清楚，
                    否则用户会以为已经填过了（按钮回弹得跟成功一模一样）。 */}
                {verifyError?.id === j.id && (
                  <div className="mt-3 rounded-md border border-severity-critical/40 bg-severity-critical/10 px-3 py-2 text-xs text-text-primary">
                    <p className="font-medium">回填失败，这条预测仍是「待验证」</p>
                    <p className="mt-1 whitespace-pre-wrap break-words text-text-secondary">
                      {verifyError.error.message}
                    </p>
                    {needsLogin(verifyError.error) && (
                      <Link
                        to="/login"
                        className="mt-2 inline-block rounded-md bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-primary-dim"
                      >
                        登录 / 注册后再回填
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

function percent(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(0)}%`
}

function money(value: number | null): string {
  return value === null ? '—' : `$${value.toFixed(2)}`
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
        置信度校准
      </h2>
      <p className="mb-4 text-xs leading-relaxed text-text-muted">
        评审说自己有多大把握，和真实结果对得上吗。
        上面的命中率回答「说中了几次」，这里回答「说有把握的时候准不准」。
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <CalibStat
          label="平均声称把握"
          value={data.mean_predicted_confidence === null ? '—' : percent(data.mean_predicted_confidence)}
        />
        <CalibStat
          label="真实命中得分"
          value={data.observed_hit_score === null ? '—' : percent(data.observed_hit_score)}
          hint="hit=1 / partial=0.5 / miss=0"
        />
        <CalibStat
          label="Brier 分数"
          value={data.brier_score === null ? '—' : data.brier_score.toFixed(3)}
          hint="越低越好，0=完美"
        />
        <CalibStat
          label="校准误差"
          value={
            data.expected_calibration_error === null
              ? '—'
              : data.expected_calibration_error.toFixed(3)
          }
          hint="说的把握与实际的平均差距"
        />
      </div>

      {bins.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs font-semibold text-text-secondary">分区间对照</p>
          <div className="space-y-1.5">
            {bins.map((b) => {
              const over = (b.mean_confidence ?? 0) > (b.observed_hit_score ?? 0)
              return (
                <div key={`${b.lower}-${b.upper}`} className="flex items-center gap-3 text-xs">
                  <span className="w-20 shrink-0 font-mono text-text-muted">
                    {(b.lower * 100).toFixed(0)}–{(b.upper * 100).toFixed(0)}%
                  </span>
                  <span className="w-24 shrink-0 font-mono tabular-nums text-text-secondary">
                    说 {percent(b.mean_confidence)}
                  </span>
                  <span className="w-24 shrink-0 font-mono tabular-nums text-text-primary">
                    实 {percent(b.observed_hit_score)}
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
                    {b.gap === null ? '' : over ? `高估 ${percent(b.gap)}` : `低估 ${percent(b.gap)}`}
                  </span>
                  <span className="ml-auto font-mono text-text-muted">n={b.sample_size}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <p className="mt-4 border-t border-border pt-3 text-[11px] leading-relaxed text-text-muted">
        {data.low_confidence && (
          <span className="text-warm-orange">
            ⚠️ {data.note ?? `样本量 ${data.sample_size} 偏小，以下数字仅供参考，不具统计意义。`}{' '}
          </span>
        )}
        已回填 {data.verified_rows} 条
        {data.excluded_rows > 0 && `（其中 ${data.excluded_rows} 条因缺少置信度或结果无法映射而未计入）`}。
        置信度来源是合成面板的启发式权重，尚未经真实结果重新校准——这张表正是用来做那件事的。
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
