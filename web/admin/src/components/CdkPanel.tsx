import { useCallback, useEffect, useState } from 'react'
import { Ticket, Loader2, Copy, Check, Ban } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { CdkCode, CdkGenerateResult, CdkStatus } from '@/lib/types'

const STATUS_LABEL: Record<CdkStatus, string> = {
  active: '可用',
  disabled: '已停用',
  exhausted: '已用完',
  expired: '已过期',
}

const STATUS_COLOR: Record<CdkStatus, string> = {
  active: 'text-neon-green bg-neon-green/10',
  disabled: 'text-severity-critical bg-severity-critical/10',
  exhausted: 'text-text-muted bg-bg-secondary',
  expired: 'text-warm-orange bg-warm-orange/10',
}

export function CdkPanel() {
  const [codes, setCodes] = useState<CdkCode[]>([])
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 生成表单
  const [genCount, setGenCount] = useState(10)
  const [genCredits, setGenCredits] = useState(5)
  const [genMaxUses, setGenMaxUses] = useState(1)
  const [genExpireDays, setGenExpireDays] = useState<number | ''>('')
  const [genNote, setGenNote] = useState('')
  const [generating, setGenerating] = useState(false)
  const [lastBatch, setLastBatch] = useState<CdkGenerateResult | null>(null)
  const [copied, setCopied] = useState(false)
  const [disabling, setDisabling] = useState<string | null>(null)

  const load = useCallback(async (status: string) => {
    setLoading(true)
    setError(null)
    try {
      const res = await adminApi.listCdk({ status: status || undefined, limit: 50 })
      setCodes(res.codes)
      setTotal(res.total)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(statusFilter)
  }, [load, statusFilter])

  const generate = async () => {
    setGenerating(true)
    setError(null)
    setLastBatch(null)
    try {
      const res = await adminApi.generateCdk({
        count: genCount,
        credits: genCredits,
        max_uses: genMaxUses,
        expires_in_days: genExpireDays === '' ? undefined : genExpireDays,
        note: genNote.trim() || undefined,
      })
      setLastBatch(res)
      await load(statusFilter)
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成失败')
    } finally {
      setGenerating(false)
    }
  }

  const copyBatch = async () => {
    if (!lastBatch) return
    await navigator.clipboard.writeText(lastBatch.codes.join('\n'))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const disable = async (id: string) => {
    setDisabling(id)
    try {
      await adminApi.disableCdk(id)
      await load(statusFilter)
    } catch (e) {
      setError(e instanceof Error ? e.message : '停用失败')
    } finally {
      setDisabling(null)
    }
  }

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
        <Ticket className="h-4 w-4 text-warm-orange" strokeWidth={1.5} />
        CDK 兑换码
        <span className="font-mono text-[10px] font-normal text-text-muted">
          免登录兑换评审次数（走平台垫付 Key 时生效）
        </span>
      </h2>
      <p className="mt-1 text-xs text-text-muted">
        批量生成 → 分发 → 用户在设置页兑换。匿名兑换会自动签发游客身份，次数落到访客各自头上，
        不会进共享匿名桶被陌生人分掉。兑换接口有 10 次/分钟的防枚举限流。
      </p>

      {error && <p className="mt-3 font-mono text-xs text-severity-critical">{error}</p>}

      {/* 生成表单 */}
      <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-5">
        <label className="text-xs text-text-muted">
          生成数量
          <input
            type="number"
            min={1}
            max={500}
            value={genCount}
            onChange={(e) => setGenCount(Math.max(1, Number(e.target.value) || 1))}
            className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-2 py-1.5 font-mono text-sm text-text-primary outline-none focus:border-warm-orange transition-colors"
          />
        </label>
        <label className="text-xs text-text-muted">
          每码次数
          <input
            type="number"
            min={1}
            max={10000}
            value={genCredits}
            onChange={(e) => setGenCredits(Math.max(1, Number(e.target.value) || 1))}
            className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-2 py-1.5 font-mono text-sm text-text-primary outline-none focus:border-warm-orange transition-colors"
          />
        </label>
        <label className="text-xs text-text-muted">
          可兑换人数
          <input
            type="number"
            min={1}
            value={genMaxUses}
            onChange={(e) => setGenMaxUses(Math.max(1, Number(e.target.value) || 1))}
            className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-2 py-1.5 font-mono text-sm text-text-primary outline-none focus:border-warm-orange transition-colors"
          />
        </label>
        <label className="text-xs text-text-muted">
          有效期（天）
          <input
            type="number"
            min={1}
            placeholder="留空=永久"
            value={genExpireDays}
            onChange={(e) => setGenExpireDays(e.target.value === '' ? '' : Math.max(1, Number(e.target.value) || 1))}
            className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-2 py-1.5 font-mono text-sm text-text-primary placeholder-text-muted outline-none focus:border-warm-orange transition-colors"
          />
        </label>
        <label className="text-xs text-text-muted">
          备注
          <input
            type="text"
            placeholder="如：首发活动"
            value={genNote}
            onChange={(e) => setGenNote(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-2 py-1.5 text-sm text-text-primary placeholder-text-muted outline-none focus:border-warm-orange transition-colors"
          />
        </label>
      </div>
      <button
        onClick={() => void generate()}
        disabled={generating}
        className="mt-3 flex items-center gap-2 rounded-lg bg-warm-orange/15 px-4 py-2 text-sm font-semibold text-warm-orange hover:bg-warm-orange/25 transition-colors disabled:opacity-50"
      >
        {generating ? (
          <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
        ) : (
          <Ticket className="h-4 w-4" strokeWidth={1.5} />
        )}
        批量生成
      </button>

      {/* 刚生成的批次：一键复制分发 */}
      {lastBatch && (
        <div className="mt-3 rounded-lg border border-neon-green/30 bg-bg-primary p-3">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-neon-green">
              本批 {lastBatch.count} 个 · 每码 {lastBatch.credits} 次 · 可兑 {lastBatch.max_uses} 人
            </span>
            <button
              onClick={() => void copyBatch()}
              className="flex items-center gap-1 rounded-md bg-bg-secondary px-2.5 py-1 font-mono text-xs text-text-secondary hover:text-text-primary transition-colors"
            >
              {copied ? (
                <Check className="h-3 w-3 text-neon-green" strokeWidth={1.5} />
              ) : (
                <Copy className="h-3 w-3" strokeWidth={1.5} />
              )}
              {copied ? '已复制' : '复制全部'}
            </button>
          </div>
          <div className="mt-2 max-h-32 overflow-y-auto font-mono text-xs text-text-primary leading-relaxed">
            {lastBatch.codes.map((c) => (
              <div key={c}>{c}</div>
            ))}
          </div>
        </div>
      )}

      {/* 已有码列表 */}
      <div className="mt-4 flex items-center gap-2">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-border bg-bg-secondary px-2 py-1.5 font-mono text-xs text-text-secondary outline-none"
        >
          <option value="">全部状态</option>
          <option value="active">可用</option>
          <option value="disabled">已停用</option>
          <option value="exhausted">已用完</option>
          <option value="expired">已过期</option>
        </select>
        <span className="font-mono text-[10px] text-text-muted">共 {total} 个</span>
        {loading && <Loader2 className="h-3 w-3 animate-spin text-text-muted" strokeWidth={1.5} />}
      </div>

      {codes.length > 0 ? (
        <ul className="mt-2 divide-y divide-border">
          {codes.map((c) => (
            <li key={c.id} className="flex items-center gap-3 py-2">
              <span className="font-mono text-sm text-text-primary">{c.code}</span>
              <span className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${STATUS_COLOR[c.status]}`}>
                {STATUS_LABEL[c.status]}
              </span>
              <span className="font-mono text-xs text-text-muted">
                {c.credits} 次 · 已兑 {c.used_count}/{c.max_uses}
              </span>
              {c.note && <span className="text-xs text-text-muted truncate max-w-[10rem]">{c.note}</span>}
              <span className="ml-auto font-mono text-[10px] text-text-muted">
                {c.expires_at ? `到期 ${new Date(c.expires_at).toLocaleDateString()}` : '永久'}
              </span>
              {c.status === 'active' && (
                <button
                  onClick={() => void disable(c.id)}
                  disabled={disabling === c.id}
                  className="flex shrink-0 items-center gap-1 rounded-md bg-severity-critical/10 px-2 py-1 font-mono text-[10px] text-severity-critical hover:bg-severity-critical/20 transition-colors disabled:opacity-50"
                >
                  {disabling === c.id ? (
                    <Loader2 className="h-3 w-3 animate-spin" strokeWidth={1.5} />
                  ) : (
                    <Ban className="h-3 w-3" strokeWidth={1.5} />
                  )}
                  停用
                </button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        !loading && <p className="mt-2 font-mono text-xs text-text-muted">暂无兑换码。</p>
      )}
    </section>
  )
}
