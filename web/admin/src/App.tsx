import { useCallback, useEffect, useState } from 'react'
import { Lock, RefreshCw, Server, Sliders, ListChecks, FileClock } from 'lucide-react'
import { adminApi, getAdminToken, setAdminToken } from '@/lib/adminClient'
import { ApiError } from '@/lib/types'
import type { AdminJob, AdminOverview, AdminReviewRow, AdminServerKeyStatus, AdminSettingRow } from '@/lib/types'

type GateState = 'checking' | 'disabled' | 'locked' | 'unlocked'

export default function App() {
  const [gate, setGate] = useState<GateState>('checking')
  const [tokenInput, setTokenInput] = useState('')
  const [gateError, setGateError] = useState<string | null>(null)

  const tryUnlock = useCallback(async (token: string) => {
    setGateError(null)
    setAdminToken(token || null)
    try {
      await adminApi.overview()
      setGate('unlocked')
    } catch (e) {
      if (e instanceof ApiError && e.code === 'admin_disabled') {
        setGate('disabled')
      } else if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
        setGate('locked')
        setGateError('令牌无效')
      } else {
        setGate('locked')
        setGateError(e instanceof Error ? e.message : '连接失败')
      }
    }
  }, [])

  useEffect(() => {
    void tryUnlock(getAdminToken() ?? '')
  }, [tryUnlock])

  return (
    <div className="min-h-screen bg-bg-primary">
      <AppHeader
        showLock={gate === 'unlocked'}
        onLock={() => { setAdminToken(null); setGate('locked'); setTokenInput('') }}
      />
      <main>
        {gate === 'checking' && <CenterMessage>检查中…</CenterMessage>}

        {gate === 'disabled' && (
          <CenterMessage>
            <p className="text-text-primary">管理后台未启用</p>
            <p className="mt-2 max-w-md font-mono text-xs text-text-muted">
              在后端服务的环境变量中设置 <span className="text-neon-green">AL_ADMIN_TOKEN</span> 后重启即可启用。
              未设置时该接口整体返回 503 —— 安全默认值，绝不无密钥暴露管理接口。
            </p>
          </CenterMessage>
        )}

        {gate === 'locked' && (
          <CenterMessage>
            <div className="mb-4 flex items-center gap-2 text-text-primary">
              <Lock className="h-4 w-4 text-neon-green" strokeWidth={1.5} />
              输入管理员令牌
            </div>
            <div className="flex w-full max-w-sm gap-2">
              <input
                type="password"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && void tryUnlock(tokenInput)}
                placeholder="AL_ADMIN_TOKEN"
                autoFocus
                className="w-full rounded-lg border border-border bg-bg-card px-4 py-2.5 font-mono text-sm text-text-primary placeholder-text-muted outline-none focus:border-neon-green transition-colors"
              />
              <button
                onClick={() => void tryUnlock(tokenInput)}
                className="shrink-0 rounded-lg bg-neon-green px-4 py-2.5 text-sm font-semibold text-bg-primary hover:bg-neon-green-dim transition-colors"
              >
                解锁
              </button>
            </div>
            {gateError && <p className="mt-3 font-mono text-xs text-severity-critical">{gateError}</p>}
          </CenterMessage>
        )}

        {gate === 'unlocked' && <Dashboard />}
      </main>
    </div>
  )
}

function AppHeader({ showLock, onLock }: { showLock: boolean; onLock: () => void }) {
  return (
    <header className="border-b border-border bg-bg-secondary/60 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-6">
        <Server className="h-5 w-5 text-neon-green" strokeWidth={1.5} />
        <span className="font-mono text-sm font-semibold text-text-primary">AudienceLens</span>
        <span className="font-mono text-xs text-text-muted">/ 管理后台</span>
        {showLock && (
          <button
            onClick={onLock}
            className="ml-auto rounded-md border border-border px-3 py-1.5 font-mono text-xs text-text-muted hover:border-severity-critical/40 hover:text-severity-critical transition-colors"
          >
            锁定
          </button>
        )}
      </div>
    </header>
  )
}

function CenterMessage({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] flex-col items-center justify-center px-6 text-center">
      {children}
    </div>
  )
}

// ============================== 仪表盘 ==============================

function Dashboard() {
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    try {
      setOverview(await adminApi.overview())
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const refresh = async () => {
    setRefreshing(true)
    await load()
    setRefreshing(false)
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <p className="text-sm text-text-secondary">跨用户的系统视角——运行时配置、平台 Key、任务与评审巡检。</p>
        <button
          onClick={() => void refresh()}
          className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 font-mono text-xs text-text-secondary hover:border-neon-green/40 hover:text-neon-green transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} strokeWidth={1.5} />
          刷新
        </button>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-severity-critical/40 bg-severity-critical/10 p-4 text-sm text-text-primary">
          {error}
        </div>
      )}

      {overview && <OverviewCards data={overview} />}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <SettingsPanel />
        <ServerKeyPanel />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <JobsPanel />
        <ReviewsPanel />
      </div>
    </div>
  )
}

function OverviewCards({ data }: { data: AdminOverview }) {
  const usageBySource = Object.entries(data.usage_24h.cost_usd_by_source)
  return (
    <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Stat label="评审总数" value={data.reviews.total} sub={statusBreakdown(data.reviews.by_status)} />
      <Stat
        label="24h 用量成本"
        value={`$${data.usage_24h.cost_usd_total.toFixed(4)}`}
        sub={usageBySource.map(([k, v]) => `${k}: $${v.toFixed(4)}`).join(' · ') || '—'}
      />
      <Stat
        label="判断留档"
        value={data.judgments.total}
        sub={`已验证 ${data.judgments.verified} (${percent(data.judgments.verified, data.judgments.total)})`}
      />
      <Stat
        label="任务队列"
        value={Object.values(data.jobs_by_status).reduce((a, b) => a + b, 0)}
        sub={statusBreakdown(data.jobs_by_status)}
      />
    </section>
  )
}

function statusBreakdown(rec: Record<string, number>): string {
  const entries = Object.entries(rec)
  return entries.length ? entries.map(([k, v]) => `${k}:${v}`).join(' · ') : '—'
}

function percent(n: number, total: number): string {
  return total ? `${Math.round((n / total) * 100)}%` : '—'
}

function Stat({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="rounded-xl border border-border bg-bg-card p-4">
      <div className="font-mono text-2xl font-bold tabular-nums text-text-primary">{value}</div>
      <div className="mt-1 text-xs text-text-muted">{label}</div>
      {sub && <div className="mt-2 font-mono text-[10px] text-text-secondary">{sub}</div>}
    </div>
  )
}

// ============================== 运行时配置 ==============================

function SettingsPanel() {
  const [rows, setRows] = useState<AdminSettingRow[]>([])
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setRows((await adminApi.listSettings()).settings)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const apply = async (key: string, value: unknown) => {
    setPending(key)
    setError(null)
    try {
      await adminApi.setSetting(key, value)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setPending(null)
    }
  }

  const reset = async (key: string) => {
    setPending(key)
    setError(null)
    try {
      await adminApi.resetSetting(key)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '重置失败')
    } finally {
      setPending(null)
    }
  }

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
        <Sliders className="h-4 w-4 text-neon-green" strokeWidth={1.5} />
        运行时配置
        <span className="font-mono text-[10px] font-normal text-text-muted">改动无需重启</span>
      </h2>
      {error && <p className="mt-2 font-mono text-xs text-severity-critical">{error}</p>}
      <div className="mt-4 divide-y divide-border">
        {rows.map((row) => (
          <div key={row.key} className="flex items-center gap-3 py-3">
            <div className="min-w-0 flex-1">
              <div className="text-sm text-text-primary">{row.label}</div>
              <div className="font-mono text-[10px] text-text-muted">
                {row.key} · env 默认 {String(row.env_default)}
                {row.overridden && <span className="ml-1.5 text-warm-orange">已覆盖</span>}
              </div>
            </div>
            <SettingControl row={row} disabled={pending === row.key} onChange={(v) => void apply(row.key, v)} />
            {row.overridden && (
              <button
                onClick={() => void reset(row.key)}
                disabled={pending === row.key}
                className="shrink-0 rounded-md border border-border px-2 py-1 font-mono text-[10px] text-text-muted hover:border-neon-green/40 hover:text-neon-green transition-colors disabled:opacity-50"
              >
                重置
              </button>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

function SettingControl({ row, disabled, onChange }: { row: AdminSettingRow; disabled: boolean; onChange: (value: unknown) => void }) {
  if (row.type === 'bool') {
    return (
      <input
        type="checkbox"
        checked={Boolean(row.effective_value)}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 shrink-0 accent-neon-green"
      />
    )
  }
  if (row.choices) {
    return (
      <select
        value={String(row.effective_value)}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="shrink-0 rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none focus:border-neon-green"
      >
        {row.choices.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>
    )
  }
  return (
    <input
      type="number"
      defaultValue={String(row.effective_value)}
      disabled={disabled}
      onBlur={(e) => {
        const v = row.type === 'int' ? parseInt(e.target.value, 10) : parseFloat(e.target.value)
        if (!Number.isNaN(v)) onChange(v)
      }}
      className="w-24 shrink-0 rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none focus:border-neon-green"
    />
  )
}

// ============================== 平台级 API Key ==============================

function ServerKeyPanel() {
  const [status, setStatus] = useState<AdminServerKeyStatus | null>(null)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const load = useCallback(async () => {
    try {
      setStatus(await adminApi.serverKeyStatus())
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const save = async () => {
    if (!input.trim()) return
    setBusy(true)
    setError(null)
    try {
      await adminApi.setServerKey(input.trim())
      setInput('')
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    setBusy(true)
    setError(null)
    try {
      await adminApi.deleteServerKey()
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
        <Lock className="h-4 w-4 text-neon-green" strokeWidth={1.5} />
        平台级 API Key
        <span className="font-mono text-[10px] font-normal text-text-muted">managed/hybrid 模式垫付用</span>
      </h2>
      <p className="mt-1 text-xs text-text-muted">
        托管模式下服务端垫付的 key。此处设置优先于环境变量 ANTHROPIC_API_KEY，改动即时生效。
      </p>

      {error && <p className="mt-3 font-mono text-xs text-severity-critical">{error}</p>}

      {status?.configured ? (
        <div className="mt-4 flex items-center gap-3 rounded-lg border border-neon-green/30 bg-bg-primary px-4 py-3">
          <span className="font-mono text-sm text-neon-green">{status.key?.masked}</span>
          <span className="ml-auto font-mono text-[10px] text-text-muted">
            {status.key?.last_used_at ? `最近使用 ${new Date(status.key.last_used_at).toLocaleString()}` : '尚未使用'}
          </span>
          <button
            onClick={() => void remove()}
            disabled={busy}
            className="shrink-0 rounded-md bg-severity-critical/10 px-2.5 py-1 font-mono text-xs text-severity-critical hover:bg-severity-critical/20 transition-colors disabled:opacity-50"
          >
            删除
          </button>
        </div>
      ) : (
        <p className="mt-4 font-mono text-xs text-text-muted">尚未配置。</p>
      )}

      <div className="mt-4 flex gap-2">
        <input
          type="password"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="sk-ant-…（轮换或首次设置）"
          className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 font-mono text-sm text-text-primary placeholder-text-muted outline-none focus:border-neon-green transition-colors"
        />
        <button
          onClick={() => void save()}
          disabled={busy || !input.trim()}
          className="shrink-0 rounded-lg bg-neon-green px-4 py-2 text-sm font-semibold text-bg-primary hover:bg-neon-green-dim transition-colors disabled:opacity-50"
        >
          保存
        </button>
      </div>
      {saved && <p className="mt-2 font-mono text-xs text-neon-green">已保存</p>}
    </section>
  )
}

// ============================== 任务 / 评审巡检 ==============================

function JobsPanel() {
  const [jobs, setJobs] = useState<AdminJob[]>([])
  const [filter, setFilter] = useState('')

  const load = useCallback(async () => {
    setJobs((await adminApi.listJobs(filter || undefined)).jobs)
  }, [filter])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <ListChecks className="h-4 w-4 text-cyan" strokeWidth={1.5} />
          最近任务
        </h2>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none"
        >
          <option value="">全部状态</option>
          <option value="queued">queued</option>
          <option value="running">running</option>
          <option value="done">done</option>
          <option value="failed">failed</option>
        </select>
      </div>
      <ul className="mt-3 max-h-80 space-y-2 overflow-y-auto">
        {jobs.length === 0 && <li className="py-4 text-center text-xs text-text-muted">无记录</li>}
        {jobs.map((j) => (
          <li key={j.id} className="rounded-md border border-border bg-bg-primary/60 px-3 py-2 font-mono text-xs">
            <div className="flex items-center gap-2">
              <StatusDot status={j.status} />
              <span className="text-text-primary">{j.kind}</span>
              <span className="ml-auto text-text-muted">{j.progress}%</span>
            </div>
            <div className="mt-1 truncate text-text-muted">{j.ref_id ?? '—'}</div>
            {j.error_message && <div className="mt-1 truncate text-severity-critical">{j.error_message}</div>}
          </li>
        ))}
      </ul>
    </section>
  )
}

function ReviewsPanel() {
  const [reviews, setReviews] = useState<AdminReviewRow[]>([])
  const [filter, setFilter] = useState('')

  const load = useCallback(async () => {
    setReviews((await adminApi.listReviews(filter || undefined)).reviews)
  }, [filter])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <FileClock className="h-4 w-4 text-cyan" strokeWidth={1.5} />
          最近评审
        </h2>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none"
        >
          <option value="">全部状态</option>
          <option value="pending">pending</option>
          <option value="running">running</option>
          <option value="completed">completed</option>
          <option value="failed">failed</option>
        </select>
      </div>
      <ul className="mt-3 max-h-80 space-y-2 overflow-y-auto">
        {reviews.length === 0 && <li className="py-4 text-center text-xs text-text-muted">无记录</li>}
        {reviews.map((r) => (
          <li key={r.id} className="rounded-md border border-border bg-bg-primary/60 px-3 py-2 font-mono text-xs">
            <div className="flex items-center gap-2">
              <StatusDot status={r.status} />
              <span className="truncate text-text-primary">{r.target_title || r.task_type}</span>
              <span className="ml-auto shrink-0 text-text-muted">${r.total_cost_usd.toFixed(3)}</span>
            </div>
            <div className="mt-1 flex items-center gap-2 text-text-muted">
              <span>{r.user_id}</span>
              <span>·</span>
              <span>{r.task_type}</span>
            </div>
            {r.error_message && <div className="mt-1 truncate text-severity-critical">{r.error_message}</div>}
          </li>
        ))}
      </ul>
    </section>
  )
}

function StatusDot({ status }: { status: string }) {
  const color =
    status === 'completed' || status === 'done'
      ? 'bg-neon-green'
      : status === 'failed'
        ? 'bg-severity-critical'
        : status === 'running'
          ? 'bg-cyan'
          : 'bg-text-muted'
  return <span className={`h-2 w-2 shrink-0 rounded-full ${color}`} />
}
