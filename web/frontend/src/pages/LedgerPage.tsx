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
import { api } from '@/lib/apiClient'
import type { HitRate, Judgment, LeaderboardEntry, Verdict } from '@/lib/types'

const VERDICT_LABELS: Record<Verdict, string> = {
  hit: '说中了',
  partial: '部分成立',
  miss: '没发生',
  unknown: '暂无法判定',
}

// 复用 App 自有的语义色 token（而非独立的 Tailwind 调色板），
// 确保在暗色背景上有足够对比度，与全站视觉语言一致。
const VERDICT_STYLES: Record<Verdict, string> = {
  hit: 'bg-neon-green/10 text-neon-green border-neon-green/30',
  partial: 'bg-warm-orange/10 text-warm-orange border-warm-orange/30',
  miss: 'bg-severity-critical/10 text-severity-critical border-severity-critical/30',
  unknown: 'bg-bg-secondary text-text-muted border-border',
}

export default function LedgerPage() {
  const [judgments, setJudgments] = useState<Judgment[]>([])
  const [stats, setStats] = useState<HitRate | null>(null)
  const [board, setBoard] = useState<LeaderboardEntry[]>([])
  const [onlyUnverified, setOnlyUnverified] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [j, s, b] = await Promise.all([
        api.listJudgments({ onlyUnverified }),
        api.hitRate(),
        api.leaderboard(),
      ])
      setJudgments(j.judgments)
      setStats(s)
      setBoard(b.personas)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [onlyUnverified])

  useEffect(() => {
    void load()
  }, [load])

  const verify = async (id: string, verdict: Verdict) => {
    await api.verifyJudgment(id, verdict)
    await load()
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <header className="mb-8">
        <h1 className="font-display text-3xl font-bold tracking-tight text-text-primary">判断复利</h1>
        <p className="mt-2 text-text-secondary">
          每次评审的预测都盖了时间戳留档。真人测试回来后回填结果——
          判断准不准，从此有据可查。
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-severity-critical/40 bg-severity-critical/10 p-4 text-sm text-text-primary">
          {error}
        </div>
      )}

      {/* 命中率总览 */}
      {stats && (
        <section className="mb-8 rounded-xl border border-border bg-bg-card p-6">
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
        </section>
      )}

      {/* 人格命中率排行 */}
      {board.length > 0 && (
        <section className="mb-8 rounded-xl border border-border bg-bg-card p-6">
          <h2 className="mb-4 font-display text-sm font-semibold text-text-primary">谁的判断最值得听</h2>
          <div className="space-y-2">
            {board.map((p) => (
              <div key={p.persona_id} className="flex items-center gap-3 text-sm">
                <span className="w-40 truncate font-mono text-xs text-text-secondary">{p.persona_id}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-bg-secondary">
                  <div
                    className="h-full rounded-full bg-neon-green"
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
        </section>
      )}

      {/* 预测清单 + 回填 */}
      <section className="rounded-xl border border-border bg-bg-card">
        <div className="flex items-center gap-3 border-b border-border px-6 py-4">
          <h2 className="font-display text-sm font-semibold text-text-primary">历史预测</h2>
          <label className="ml-auto flex items-center gap-2 text-xs text-text-secondary">
            <input
              type="checkbox"
              checked={onlyUnverified}
              onChange={(e) => setOnlyUnverified(e.target.checked)}
              className="accent-neon-green"
            />
            只看待验证
          </label>
        </div>

        {loading ? (
          <p className="p-6 text-sm text-text-secondary">加载中…</p>
        ) : judgments.length === 0 ? (
          <p className="p-6 text-sm text-text-secondary">
            还没有预测记录。跑一次评审，系统会自动把结论留档。
          </p>
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
                          className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-opacity hover:opacity-80 ${VERDICT_STYLES[v]}`}
                          onClick={() => void verify(j.id, v)}
                        >
                          {VERDICT_LABELS[v]}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
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
