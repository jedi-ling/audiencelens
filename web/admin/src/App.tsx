import { useCallback, useEffect, useState } from 'react'
import { Activity, Lock, LayoutDashboard, RefreshCw, ScrollText, Server, Settings2, Ticket, Users } from 'lucide-react'
import { adminApi, getAdminToken, setAdminToken } from '@/lib/adminClient'
import { ApiError } from '@/lib/types'
import type { AdminOverview } from '@/lib/types'
import { OverviewCards } from '@/components/OverviewCards'
import { TimeseriesChart } from '@/components/TimeseriesChart'
import { LedgerPanel } from '@/components/LedgerPanel'
import { SettingsPanel } from '@/components/SettingsPanel'
import { ServerKeyPanel } from '@/components/ServerKeyPanel'
import { MailPanel } from '@/components/MailPanel'
import { PlansPanel } from '@/components/PlansPanel'
import { AuditLogPanel } from '@/components/AuditLogPanel'
import { JobsPanel } from '@/components/JobsPanel'
import { ReviewsPanel } from '@/components/ReviewsPanel'
import { UsersPanel } from '@/components/UsersPanel'
import { TaskTypeStatsPanel } from '@/components/TaskTypeStatsPanel'
import { CostInsightsPanel } from '@/components/CostInsightsPanel'
import { CdkPanel } from '@/components/CdkPanel'

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
              在后端服务的环境变量中设置 <span className="text-brand-primary">AL_ADMIN_TOKEN</span> 后重启即可启用。
              未设置时该接口整体返回 503 —— 安全默认值，绝不无密钥暴露管理接口。
            </p>
          </CenterMessage>
        )}

        {gate === 'locked' && (
          <CenterMessage>
            <div className="mb-4 flex items-center gap-2 text-text-primary">
              <Lock className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
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
                className="w-full rounded-lg border border-border bg-bg-card px-4 py-2.5 font-mono text-sm text-text-primary placeholder-text-muted outline-none focus:border-brand-primary transition-colors"
              />
              <button
                onClick={() => void tryUnlock(tokenInput)}
                className="shrink-0 rounded-lg bg-brand-primary px-4 py-2.5 text-sm font-semibold text-bg-primary hover:bg-brand-primary-dim transition-colors"
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
    <header className="sticky top-0 z-40 border-b border-border bg-bg-secondary/60 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[88rem] items-center gap-3 px-6">
        <Server className="h-5 w-5 text-brand-primary" strokeWidth={1.5} />
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

type SectionId = 'overview' | 'users' | 'billing' | 'config' | 'ops' | 'audit'

const SECTIONS: { id: SectionId; label: string; icon: React.ComponentType<{ className?: string; strokeWidth?: number }>; desc: string }[] = [
  { id: 'overview', label: '总览', icon: LayoutDashboard, desc: '核心指标、趋势与分布' },
  { id: 'users', label: '用户', icon: Users, desc: '用户管理与判断复利' },
  { id: 'billing', label: '套餐与 CDK', icon: Ticket, desc: '套餐矩阵、兑换码发放' },
  { id: 'config', label: '运行时配置', icon: Settings2, desc: '开关覆盖与平台 Key' },
  { id: 'ops', label: '任务巡检', icon: Activity, desc: '队列与评审明细' },
  { id: 'audit', label: '审计日志', icon: ScrollText, desc: '管理操作留痕' },
]

function Dashboard() {
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [section, setSection] = useState<SectionId>('overview')

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
    setRefreshKey((k) => k + 1) // 让子面板（无独立刷新入口）也重新拉一次
    setRefreshing(false)
  }

  const active = SECTIONS.find((s) => s.id === section)!

  return (
    <div className="mx-auto flex max-w-[88rem] gap-6 px-6 py-6">
      {/* 分区导航：桌面侧栏 */}
      <aside className="hidden w-52 shrink-0 lg:block">
        <nav className="sticky top-20 space-y-1">
          {SECTIONS.map((s) => {
            const Icon = s.icon
            const isActive = s.id === section
            return (
              <button
                key={s.id}
                onClick={() => setSection(s.id)}
                className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                  isActive
                    ? 'border-l-2 border-brand-primary bg-brand-primary/10 text-brand-primary'
                    : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" strokeWidth={1.5} />
                {s.label}
              </button>
            )
          })}
        </nav>
      </aside>

      <div className="min-w-0 flex-1">
        {/* 分区导航：窄屏横向页签 */}
        <div className="mb-4 flex gap-1 overflow-x-auto lg:hidden">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => setSection(s.id)}
              className={`shrink-0 rounded-full px-3 py-1.5 text-xs transition-colors ${
                s.id === section
                  ? 'bg-brand-primary/15 text-brand-primary'
                  : 'bg-bg-card text-text-secondary'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="mb-5 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold text-text-primary">{active.label}</h1>
            <p className="mt-0.5 text-xs text-text-muted">{active.desc}</p>
          </div>
          <button
            onClick={() => void refresh()}
            className="flex shrink-0 items-center gap-1.5 rounded-md border border-border px-3 py-1.5 font-mono text-xs text-text-secondary hover:border-brand-primary/40 hover:text-brand-primary transition-colors"
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

        <div key={refreshKey} className="contents">
          {section === 'overview' && (
            <>
              {overview && <OverviewCards data={overview} />}
              <div className="mt-6">
                <TimeseriesChart />
              </div>
              <div className="mt-6 grid gap-6 xl:grid-cols-2">
                <TaskTypeStatsPanel />
                <CostInsightsPanel />
              </div>
            </>
          )}

          {section === 'users' && (
            <>
              <UsersPanel />
              <div className="mt-6">
                <LedgerPanel />
              </div>
            </>
          )}

          {section === 'billing' && (
            <>
              <PlansPanel />
              <div className="mt-6">
                <CdkPanel />
              </div>
            </>
          )}

          {section === 'config' && (
            <div className="grid gap-6 xl:grid-cols-2">
              <SettingsPanel />
              <ServerKeyPanel />
              <MailPanel />
            </div>
          )}

          {section === 'ops' && (
            <div className="grid gap-6 xl:grid-cols-2">
              <JobsPanel />
              <ReviewsPanel />
            </div>
          )}

          {section === 'audit' && <AuditLogPanel />}
        </div>
      </div>
    </div>
  )
}
