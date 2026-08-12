import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router'
import { cn } from '@/lib/utils'
import { api, claimPendingReviews, setToken } from '@/lib/apiClient'
import { useSessionStore } from '@/store/session-store'
import type { KeyStatus, UsageSummary, TestConnectionResult } from '@/lib/types'
import { OPENAI_COMPATIBLE_PRESETS } from '@/lib/types'
import {
  Eye,
  EyeOff,
  Loader2,
  CheckCircle2,
  XCircle,
  Save,
  Wifi,
  Bot,
  Cpu,
  Globe,
  Server,
  ShieldCheck,
  KeyRound,
  Trash2,
  BarChart3,
  ImagePlus,
  Ticket,
  Download,
  AlertTriangle,
  User,
} from 'lucide-react'

type Provider = 'anthropic' | 'openai_compatible'
type TestStatus = 'idle' | 'testing' | 'success' | 'error'
type SectionKey = 'account' | 'model' | 'usage' | 'data'

// 参考 MiniMax 控制台那种「左侧分组导航 + 右侧单类目内容」的信息架构——
// 之前是三个大 section 从上到下堆一整屏，用户想改密码得先划过整块 BYOK
// 表单。分组按"这是关于什么"分：账户身份 / 怎么接模型 / 花了多少钱 / 数据主权，
// 而不是按"这段代码是什么时候加的"从上到下堆。
const NAV_GROUPS: Array<{
  label: string
  items: Array<{ key: SectionKey; label: string; icon: React.ElementType }>
}> = [
  {
    label: '账户',
    items: [{ key: 'account', label: '个人信息', icon: User }],
  },
  {
    label: '模型配置',
    items: [{ key: 'model', label: 'API Key（BYOK）', icon: KeyRound }],
  },
  {
    label: '用量与兑换',
    items: [{ key: 'usage', label: '兑换码 · 用量统计', icon: BarChart3 }],
  },
  {
    label: '数据与隐私',
    items: [{ key: 'data', label: '导出与删除', icon: ShieldCheck }],
  },
]

const PROVIDER_CONFIG: Record<Provider, {
  label: string
  icon: React.ElementType
  color: { border: string; bg: string; text: string; glow: string }
  desc: string
}> = {
  anthropic: {
    label: 'Anthropic 原生',
    icon: Bot,
    color: {
      border: 'border-brand-primary/50',
      bg: 'bg-brand-primary/10',
      text: 'text-brand-primary',
      glow: 'shadow-[0_2px_12px_rgba(0,113,227,0.12)]',
    },
    desc: 'Claude 官方 API',
  },
  openai_compatible: {
    label: 'OpenAI 兼容 / 国产模型',
    icon: Cpu,
    color: {
      border: 'border-cyan/50',
      bg: 'bg-cyan/10',
      text: 'text-cyan',
      glow: 'shadow-[0_2px_12px_rgba(50,173,230,0.12)]',
    },
    desc: 'DeepSeek / Kimi / 通义千问 / 智谱 GLM / Ollama 等',
  },
}

const PRESET_ICONS: Record<string, React.ElementType> = {
  openai: Cpu,
  deepseek: Globe,
  kimi: Globe,
  qwen: Globe,
  glm: Globe,
  ollama: Server,
}

export default function SettingsPage() {
  const [activeSection, setActiveSection] = useState<SectionKey>('model')
  const [keyStatus, setKeyStatus] = useState<KeyStatus | null>(null)
  const [usage, setUsage] = useState<UsageSummary | null>(null)

  const [byokProvider, setByokProvider] = useState<Provider>('anthropic')
  const [byokModel, setByokModel] = useState('')
  const [byokApiBase, setByokApiBase] = useState('')
  const [byokKey, setByokKey] = useState('')
  const [showByokKey, setShowByokKey] = useState(false)
  const [byokSaving, setByokSaving] = useState(false)
  const [byokDeleting, setByokDeleting] = useState<string | null>(null)
  const [byokError, setByokError] = useState<string | null>(null)
  const [byokSaved, setByokSaved] = useState(false)

  const [testStatus, setTestStatus] = useState<TestStatus>('idle')
  const [testResult, setTestResult] = useState<TestConnectionResult | null>(null)

  // ---------------- CDK 兑换码 ----------------
  const [cdkCode, setCdkCode] = useState('')
  const [cdkBusy, setCdkBusy] = useState(false)
  const [cdkError, setCdkError] = useState<string | null>(null)
  const [cdkSuccess, setCdkSuccess] = useState<{ granted: number; balance: number; guest: boolean } | null>(null)

  // ---------------- 数据自主权：导出 / 删号 ----------------
  const { identity, logout } = useSessionStore()
  const [exporting, setExporting] = useState(false)
  const [dataError, setDataError] = useState<string | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [deletePassword, setDeletePassword] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [deleteDone, setDeleteDone] = useState<Record<string, number> | null>(null)


  // ---------------- 账户：改昵称 / 改密码 ----------------
  // 这两件事以前在界面上**根本没有入口**，后端也没有对应接口：昵称在注册那一刻
  // 定死，密码只能"退出登录 → 忘记密码 → 收邮件 → 点链接"。而邮件链路没配通的
  // 部署里，后一条等于密码不可更改。
  const [nameDraft, setNameDraft] = useState('')
  const [nameBusy, setNameBusy] = useState(false)
  const [nameMsg, setNameMsg] = useState<string | null>(null)
  const [nameError, setNameError] = useState<string | null>(null)

  const [pwCurrent, setPwCurrent] = useState('')
  const [pwNext, setPwNext] = useState('')
  const [pwConfirm, setPwConfirm] = useState('')
  const [pwBusy, setPwBusy] = useState(false)
  const [pwMsg, setPwMsg] = useState<string | null>(null)
  const [pwError, setPwError] = useState<string | null>(null)

  useEffect(() => {
    // 进页面时把当前昵称填进输入框当初值；identity 是异步拿的，所以放 effect 里。
    if (identity?.display_name) setNameDraft(identity.display_name)
  }, [identity?.display_name])

  const handleSaveName = async () => {
    const name = nameDraft.trim()
    if (!name) { setNameError('昵称不能为空'); return }
    setNameBusy(true); setNameError(null); setNameMsg(null)
    try {
      await api.updateProfile(name)
      // 重新拉一次身份：顶栏、账户菜单都读 store 里的 identity，不刷新的话
      // 页面上的名字会和刚保存的值不一致，看起来像没保存成功。
      await useSessionStore.getState().bootstrap()
      setNameMsg('昵称已更新')
    } catch (e) {
      setNameError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setNameBusy(false)
    }
  }

  const handleChangePassword = async () => {
    // 两次新密码不一致要在本地就拦下——让用户把一个打错的密码提交上去、
    // 成功了才发现自己不知道新密码是什么，是最糟的失败方式。
    if (pwNext !== pwConfirm) { setPwError('两次输入的新密码不一致'); return }
    if (pwNext.length < 8) { setPwError('新密码至少 8 位'); return }
    setPwBusy(true); setPwError(null); setPwMsg(null)
    try {
      const r = await api.changePassword(pwCurrent, pwNext)
      // 关键一步：后端撤销了该用户全部旧会话，手上这把 token 已经作废。
      // 不换成返回的新令牌的话，改完密码下一个请求就 401，用户会以为自己被登出了。
      setToken(r.token)
      setPwCurrent(''); setPwNext(''); setPwConfirm('')
      setPwMsg('密码已修改。其他设备上的登录已失效，本设备无需重新登录。')
    } catch (e) {
      setPwError(e instanceof Error ? e.message : '修改失败')
    } finally {
      setPwBusy(false)
    }
  }

  /** 导出：直接在浏览器里生成文件下载，不经过服务端存一份中间产物——
   *  少一个副本就少一处泄露面，也免得又攒出一堆没人清理的死文件。 */
  const handleExport = async () => {
    setExporting(true)
    setDataError(null)
    try {
      const data = await api.exportMyData()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audiencelens-my-data-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setDataError(e instanceof Error ? e.message : '导出失败')
    } finally {
      setExporting(false)
    }
  }

  const handleDeleteAccount = async () => {
    setDeleting(true)
    setDataError(null)
    try {
      const res = await api.deleteMyAccount(deleteConfirm, deletePassword || undefined)
      setDeleteDone(res.detail)
      setDeleteOpen(false)
      // 账号已经没了，本地登录态留着只会让后续请求一直 401
      if (!identity?.is_anonymous) logout()
      await refreshByok()
    } catch (e) {
      setDataError(e instanceof Error ? e.message : '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  const refreshByok = useCallback(async () => {
    // key 状态和用量各自失败互不影响；平台服务没起时整块降级为提示
    const [keysRes, usageRes] = await Promise.allSettled([api.getKeys(), api.usage()])
    if (keysRes.status === 'fulfilled') setKeyStatus(keysRes.value)
    if (usageRes.status === 'fulfilled') setUsage(usageRes.value)
    if (keysRes.status === 'rejected' && usageRes.status === 'rejected') {
      setByokError('平台服务不可用，BYOK Key 管理暂时无法使用')
    }
  }, [])

  useEffect(() => {
    void refreshByok()
  }, [refreshByok])

  const applyPreset = (preset: (typeof OPENAI_COMPATIBLE_PRESETS)[number]) => {
    setByokProvider('openai_compatible')
    setByokModel(preset.model)
    setByokApiBase(preset.api_base)
    setTestStatus('idle')
    setTestResult(null)
  }

  const resetTest = () => {
    setTestStatus('idle')
    setTestResult(null)
  }

  const handleByokTest = async () => {
    if (byokProvider === 'openai_compatible' && !byokModel.trim()) return
    setTestStatus('testing')
    setTestResult(null)
    try {
      const result = await api.testKey({
        apiKey: byokKey.trim() || undefined,
        provider: byokProvider,
        model: byokModel.trim() || undefined,
        apiBase: byokApiBase.trim() || undefined,
      })
      setTestResult(result)
      setTestStatus(result.connected ? 'success' : 'error')
    } catch (e) {
      setTestResult({ connected: false, error: e instanceof Error ? e.message : '连接失败' })
      setTestStatus('error')
    }
  }

  const handleByokSave = async () => {
    if (!byokKey.trim()) return
    if (byokProvider === 'openai_compatible' && !byokModel.trim()) {
      setByokError('OpenAI 兼容格式需要填写模型名称')
      return
    }
    setByokSaving(true)
    setByokError(null)
    setByokSaved(false)
    try {
      await api.saveKey(byokKey.trim(), byokProvider, {
        model: byokModel.trim() || undefined,
        apiBase: byokApiBase.trim() || undefined,
      })
      setByokKey('')
      setByokSaved(true)
      setTimeout(() => setByokSaved(false), 3000)
      await refreshByok()
    } catch (e) {
      setByokError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setByokSaving(false)
    }
  }

  const handleRedeemCdk = async () => {
    if (!cdkCode.trim() || cdkBusy) return
    setCdkBusy(true)
    setCdkError(null)
    setCdkSuccess(null)
    try {
      const result = await api.redeemCdk(cdkCode.trim())
      // 匿名兑换会拿到游客身份 token——必须存下来，次数才跟着这个浏览器走
      if (result.token) {
        setToken(result.token)
        // 换身份 = 之前匿名跑的评审全部 404。后端归属校验是 user_id 精确比对，
        // 这个浏览器刚从 "anonymous" 变成独立游客 id，不认领的话用户上一秒还能
        // 打开的报告下一秒就"不存在"了。与登录/注册路径（session-store）同一处理。
        // 认领失败不该反噬兑换本身：兑换已经成功，这里只是补救。
        await claimPendingReviews().catch(() => {})
      }
      setCdkSuccess({
        granted: result.credits_granted,
        balance: result.balance,
        guest: !!result.guest,
      })
      setCdkCode('')
      await refreshByok() // 刷新用量卡片里的余额
    } catch (e) {
      setCdkError(e instanceof Error ? e.message : '兑换失败')
    } finally {
      setCdkBusy(false)
    }
  }

  const handleByokDelete = async (provider: string) => {
    setByokDeleting(provider)
    setByokError(null)
    try {
      await api.deleteKey(provider)
      await refreshByok()
    } catch (e) {
      setByokError(e instanceof Error ? e.message : '删除失败')
    } finally {
      setByokDeleting(null)
    }
  }

  const SECTION_HEADERS: Record<SectionKey, { title: string; desc: string }> = {
    account: {
      title: '个人信息',
      desc: identity?.is_anonymous
        ? '当前是游客身份，登录后可以改昵称、改密码、管理长期账号。'
        : '管理你的账号信息与安全设置。',
    },
    model: {
      title: 'API Key（BYOK）',
      desc: '选择评审使用的大模型。支持 Anthropic 官方 API，以及 DeepSeek、Kimi、通义千问、智谱 GLM、Ollama 等任意 OpenAI 兼容服务。点「测试」可验证连接是否可用。',
    },
    usage: {
      title: '兑换码 · 用量统计',
      desc: '用 CDK 兑换码换取评审次数，查看近 24 小时用量与累计 token 消耗。',
    },
    data: {
      title: '数据与隐私',
      desc: '你上传的材料、评审报告、对话记录随时可以导出或永久删除。',
    },
  }

  return (
    // 表单/阅读型页面：与其他设置类页面同一档容器
    <div className="max-w-4xl mx-auto px-4 py-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="font-display text-2xl font-bold text-text-primary">
          设置
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          账户、模型接入、用量与数据，都在这里管理。
        </p>
      </div>

      <div className="flex flex-col md:flex-row gap-8 items-start">
        {/* 左侧分组导航——按"这是关于什么"分组（账户身份 / 怎么接模型 /
            花了多少钱 / 数据主权），不是按代码加入的先后顺序堆叠。 */}
        <aside className="w-full md:w-56 shrink-0 md:sticky md:top-24">
          <nav className="space-y-5">
            {NAV_GROUPS.map((group) => (
              <div key={group.label}>
                <div className="px-3 mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                  {group.label}
                </div>
                <div className="space-y-0.5">
                  {group.items.map((item) => {
                    const Icon = item.icon
                    const isActive = activeSection === item.key
                    return (
                      <button
                        key={item.key}
                        onClick={() => setActiveSection(item.key)}
                        className={cn(
                          'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-left transition-colors',
                          isActive
                            ? 'bg-brand-primary/10 text-brand-primary font-medium'
                            : 'text-text-secondary hover:text-text-primary hover:bg-white/5'
                        )}
                      >
                        <Icon className="w-4 h-4 shrink-0" strokeWidth={1.5} />
                        <span className="truncate">{item.label}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </nav>
        </aside>

        {/* 右侧内容：一次只显示当前选中的一个类目，而不是把三大块全部
            堆在一条竖向滚动里——之前改密码得先滚过整块 BYOK 表单。 */}
        <div className="flex-1 min-w-0 w-full">
      <div className="mb-6">
        <h2 className="font-display text-xl font-semibold text-text-primary mb-1">
          {SECTION_HEADERS[activeSection].title}
        </h2>
        <p className="text-sm text-text-secondary">
          {SECTION_HEADERS[activeSection].desc}
        </p>
      </div>

      <div className="space-y-6">
        {/* ---------------- 账户：个人信息 ---------------- */}
        {activeSection === 'account' && (
          identity?.is_anonymous ? (
            <section className="rounded-xl border border-border bg-bg-card p-5 md:p-6">
              <div className="flex items-center gap-3 mb-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-primary/10 border border-brand-primary/20">
                  <User className="h-5 w-5 text-brand-primary" strokeWidth={1.5} />
                </div>
                <div>
                  <h3 className="text-base font-display font-semibold text-text-primary">
                    当前是游客身份
                  </h3>
                  <p className="text-xs text-text-muted">
                    没有邮箱和密码可以改——登录或注册一个账号后，这里会显示昵称、密码修改入口。
                  </p>
                </div>
              </div>
              <Link
                to="/login"
                className="mt-4 inline-flex items-center gap-1.5 rounded-md bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-dim"
              >
                去登录 / 注册
              </Link>
            </section>
          ) : (
            <section className="rounded-xl border border-border bg-bg-card p-5 md:p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-primary/10 border border-brand-primary/20">
                  <User className="h-5 w-5 text-brand-primary" strokeWidth={1.5} />
                </div>
                <div>
                  <h3 className="text-base font-display font-semibold text-text-primary">
                    账户信息
                  </h3>
                  <p className="text-xs text-text-muted">
                    当前登录：{identity?.email}
                  </p>
                </div>
              </div>
              {/* 昵称 */}
              <div className="mt-4 rounded-lg border border-border bg-black/30 p-4">
                <label className="block text-xs font-medium text-text-secondary">昵称</label>
                <div className="mt-2 flex flex-wrap gap-2">
                  <input
                    value={nameDraft}
                    onChange={(e) => { setNameDraft(e.target.value); setNameMsg(null); setNameError(null) }}
                    maxLength={50}
                    className="min-w-0 flex-1 rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary/50"
                    placeholder="怎么称呼你"
                  />
                  <button
                    onClick={() => void handleSaveName()}
                    disabled={nameBusy || !nameDraft.trim() || nameDraft.trim() === (identity?.display_name ?? '')}
                    className="flex items-center gap-1.5 rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary transition-colors hover:border-brand-primary/40 disabled:opacity-50"
                  >
                    {nameBusy ? <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} /> : <Save className="h-4 w-4" strokeWidth={1.5} />}
                    保存
                  </button>
                </div>
                {nameMsg && <p className="mt-2 text-xs text-brand-primary">{nameMsg}</p>}
                {nameError && <p className="mt-2 text-xs text-severity-critical">{nameError}</p>}
                <p className="mt-2 text-xs text-text-muted">
                  邮箱暂不支持自助修改。如需更换，请联系我们。
                </p>
              </div>

              {/* 密码 */}
              <div className="mt-3 rounded-lg border border-border bg-black/30 p-4">
                <label className="block text-xs font-medium text-text-secondary">修改密码</label>
                <div className="mt-2 grid gap-2 sm:grid-cols-3">
                  <input
                    type="password" value={pwCurrent} autoComplete="current-password"
                    onChange={(e) => { setPwCurrent(e.target.value); setPwMsg(null); setPwError(null) }}
                    placeholder="当前密码"
                    className="rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary/50"
                  />
                  <input
                    type="password" value={pwNext} autoComplete="new-password"
                    onChange={(e) => { setPwNext(e.target.value); setPwMsg(null); setPwError(null) }}
                    placeholder="新密码（至少 8 位）"
                    className="rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary/50"
                  />
                  <input
                    type="password" value={pwConfirm} autoComplete="new-password"
                    onChange={(e) => { setPwConfirm(e.target.value); setPwMsg(null); setPwError(null) }}
                    placeholder="再输一次新密码"
                    className="rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary/50"
                  />
                </div>
                <button
                  onClick={() => void handleChangePassword()}
                  disabled={pwBusy || !pwCurrent || !pwNext || !pwConfirm}
                  className="mt-3 flex items-center gap-1.5 rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary transition-colors hover:border-brand-primary/40 disabled:opacity-50"
                >
                  {pwBusy ? <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} /> : <KeyRound className="h-4 w-4" strokeWidth={1.5} />}
                  修改密码
                </button>
                {pwMsg && <p className="mt-2 text-xs text-brand-primary">{pwMsg}</p>}
                {pwError && <p className="mt-2 text-xs text-severity-critical">{pwError}</p>}
                <p className="mt-2 text-xs text-text-muted">
                  修改后其他设备会自动退出登录，本设备保持登录。如忘记当前密码，请退出后通过「忘记密码」重置。
                </p>
              </div>
            </section>
          )
        )}

        {/* ---------------- 模型配置：API Key（BYOK） ---------------- */}
        {activeSection === 'model' && (
        <section className="rounded-xl border border-border bg-bg-card p-5 md:p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-primary/10 border border-brand-primary/20">
              <KeyRound className="w-5 h-5 text-brand-primary" strokeWidth={1.5} />
            </div>
            <div>
              <h2 className="text-lg font-display font-semibold text-text-primary">
                API Key（BYOK）
              </h2>
              <p className="text-xs text-text-muted">
                自带 Key 评审：Key 加密存储在服务端，评审费用从你的模型账户扣除。
                {keyStatus?.server_key_available && '（平台也提供共享 Key 作为兜底）'}
              </p>
            </div>
          </div>

          {byokError && (
            <div className="mb-4 flex items-start gap-2 text-sm text-severity-critical">
              <XCircle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.25} />
              <span className="break-all">{byokError}</span>
            </div>
          )}

          {/* 已保存的 Key：掩码展示 + 删除 */}
          {keyStatus && keyStatus.keys.length > 0 && (
            <div className="space-y-2 mb-4">
              {keyStatus.keys.map((k) => (
                <div
                  key={k.provider}
                  className="flex items-center gap-3 px-4 py-3 rounded-xl bg-black/30 border border-brand-primary/20 shadow-sm"
                >
                  <CheckCircle2 className="w-4 h-4 text-brand-primary shrink-0" strokeWidth={1.25} />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-text-primary font-medium">
                      {k.provider}
                      {k.model && <span className="text-text-muted font-mono font-normal"> · {k.model}</span>}
                    </div>
                    <div className="text-xs text-text-muted font-mono truncate">
                      {k.masked}
                      {k.last_used_at && ` · 最近使用 ${new Date(k.last_used_at).toLocaleString()}`}
                    </div>
                  </div>
                  <button
                    onClick={() => handleByokDelete(k.provider)}
                    disabled={byokDeleting === k.provider}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium bg-severity-critical/10 text-severity-critical hover:bg-severity-critical/20 transition-all disabled:opacity-50"
                  >
                    {byokDeleting === k.provider ? (
                      <Loader2 className="w-3 h-3 animate-spin" strokeWidth={1.25} />
                    ) : (
                      <Trash2 className="w-3 h-3" strokeWidth={1.25} />
                    )}
                    删除
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* 服务商选择 */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            {(Object.keys(PROVIDER_CONFIG) as Provider[]).map((p) => {
              const cfg = PROVIDER_CONFIG[p]
              const Icon = cfg.icon
              const isSelected = byokProvider === p
              return (
                <button
                  key={p}
                  onClick={() => {
                    setByokProvider(p)
                    resetTest()
                  }}
                  className={cn(
                    'flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all cursor-pointer relative overflow-hidden',
                    'bg-black/30 hover:bg-white/5',
                    isSelected
                      ? cn(cfg.color.border, cfg.color.glow, 'shadow-sm')
                      : 'border-border hover:border-border-hover'
                  )}
                >
                  {isSelected && <div className={cn('absolute inset-0 opacity-[0.07]', cfg.color.bg)} />}
                  <div className={cn(
                    'flex h-10 w-10 items-center justify-center rounded-lg transition-colors relative z-10',
                    isSelected ? cfg.color.bg : 'bg-black/30'
                  )}>
                    <Icon
                      className={cn('w-5 h-5 transition-colors', isSelected ? cfg.color.text : 'text-text-muted')}
                      strokeWidth={1.5}
                    />
                  </div>
                  <span className={cn('text-sm font-semibold relative z-10 transition-colors', isSelected ? 'text-text-primary' : 'text-text-secondary')}>
                    {cfg.label}
                  </span>
                  <span className={cn('text-[10px] font-mono relative z-10 text-center transition-colors', isSelected ? 'text-text-secondary' : 'text-text-muted')}>
                    {cfg.desc}
                  </span>
                </button>
              )
            })}
          </div>

          {/* OpenAI 兼容：快捷预设 */}
          {byokProvider === 'openai_compatible' && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-4">
              {OPENAI_COMPATIBLE_PRESETS.map((preset) => {
                const Icon = PRESET_ICONS[preset.id] || Cpu
                const isMatch = byokModel === preset.model && byokApiBase === preset.api_base
                return (
                  <button
                    key={preset.id}
                    onClick={() => applyPreset(preset)}
                    className={cn(
                      'flex items-center gap-2 px-3 py-2.5 rounded-lg border transition-all cursor-pointer text-left',
                      'bg-black/30 hover:bg-white/5',
                      isMatch ? 'border-cyan/50 bg-cyan/[0.06] shadow-sm' : 'border-border hover:border-border-hover'
                    )}
                  >
                    <div className={cn(
                      'flex h-7 w-7 shrink-0 items-center justify-center rounded-md',
                      isMatch ? 'bg-cyan/10' : 'bg-black/30'
                    )}>
                      <Icon className={cn('w-3.5 h-3.5', isMatch ? 'text-cyan' : 'text-text-muted')} strokeWidth={1.5} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className={cn('text-xs font-semibold truncate', isMatch ? 'text-text-primary' : 'text-text-secondary')}>
                        {preset.name}
                      </div>
                      <div className="text-[10px] text-text-muted font-mono truncate">{preset.model}</div>
                    </div>
                  </button>
                )
              })}
            </div>
          )}

          {/* 模型名 + API Base：两个服务商都能填。
              openai_compatible 必填模型名（没有统一默认值）；
              anthropic 都留空则走人格分级自动选型（haiku/sonnet/opus），
              但也支持指定具体模型 ID，或填第三方中转/代理的 base_url（不是只有 OpenAI 兼容才有这种场景）。 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
            <div>
              <label className="block text-xs text-text-muted mb-1.5">
                模型 ID {byokProvider === 'anthropic' && <span className="text-text-muted/70">（留空自动按人格分级选型）</span>}
              </label>
              <input
                type="text"
                value={byokModel}
                onChange={(e) => {
                  setByokModel(e.target.value)
                  resetTest()
                }}
                placeholder={byokProvider === 'anthropic' ? 'claude-sonnet-4-5-20250929（留空自动选）' : 'deepseek-v4-pro'}
                className="w-full px-3 py-2.5 rounded-lg bg-black/30 border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-cyan transition-colors font-mono text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1.5">
                API Base URL {byokProvider === 'anthropic' && <span className="text-text-muted/70">（留空用官方地址）</span>}
              </label>
              <input
                type="text"
                value={byokApiBase}
                onChange={(e) => {
                  setByokApiBase(e.target.value)
                  resetTest()
                }}
                placeholder={byokProvider === 'anthropic' ? 'https://api.anthropic.com（或第三方中转地址）' : 'https://api.deepseek.com'}
                className="w-full px-3 py-2.5 rounded-lg bg-black/30 border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-cyan transition-colors font-mono text-sm"
              />
            </div>
          </div>

          {/* Key 输入 + 测试/保存 */}
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <input
                type={showByokKey ? 'text' : 'password'}
                value={byokKey}
                onChange={(e) => {
                  setByokKey(e.target.value)
                  resetTest()
                }}
                aria-label="API Key"
                placeholder={byokProvider === 'anthropic' ? 'sk-ant-…（输入 Anthropic API Key）' : '输入对应服务商的 API Key（Ollama 本地可留空）'}
                className="w-full px-4 py-3 pr-12 rounded-lg bg-black/30 border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-brand-primary transition-colors font-mono text-sm"
              />
              <button
                onClick={() => setShowByokKey(!showByokKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md hover:bg-white/5 text-text-muted hover:text-text-secondary transition-colors"
              >
                {showByokKey ? <EyeOff className="w-4 h-4" strokeWidth={1.25} /> : <Eye className="w-4 h-4" strokeWidth={1.25} />}
              </button>
            </div>
            <button
              onClick={handleByokTest}
              disabled={testStatus === 'testing' || (byokProvider === 'openai_compatible' && !byokModel.trim())}
              className={cn(
                'flex items-center gap-1.5 px-4 py-3 rounded-lg text-sm font-medium transition-all shrink-0',
                testStatus === 'testing' || (byokProvider === 'openai_compatible' && !byokModel.trim())
                  ? 'bg-black/30 text-text-muted cursor-not-allowed'
                  : 'bg-cyan/10 text-cyan hover:bg-cyan/20'
              )}
            >
              {testStatus === 'testing' ? (
                <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.25} />
              ) : (
                <Wifi className="w-4 h-4" strokeWidth={1.25} />
              )}
              测试
            </button>
            <button
              onClick={handleByokSave}
              disabled={byokSaving || !byokKey.trim()}
              className={cn(
                'flex items-center gap-2 px-5 py-3 rounded-lg text-sm font-bold transition-all shrink-0',
                byokSaving || !byokKey.trim()
                  ? 'bg-black/30 text-text-muted cursor-not-allowed'
                  : 'bg-brand-primary text-white hover:bg-brand-primary-dim'
              )}
            >
              {byokSaving ? <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.25} /> : <Save className="w-4 h-4" strokeWidth={1.25} />}
              保存 Key
            </button>
          </div>

          {testStatus === 'success' && testResult && (
            <div className="mt-2 flex items-center gap-2 text-sm text-brand-primary">
              <CheckCircle2 className="w-4 h-4" strokeWidth={1.25} />
              <span>连接成功</span>
              {testResult.model && <span className="text-text-muted font-mono text-xs">({testResult.model})</span>}
              {testResult.sample && (
                <span className="text-text-muted text-xs truncate max-w-[16rem]">回复：{testResult.sample}</span>
              )}
            </div>
          )}
          {testStatus === 'error' && (
            <div className="mt-2 flex items-start gap-2 text-sm text-severity-critical">
              <XCircle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.25} />
              <span className="break-all">{testResult?.error || '连接失败'}</span>
            </div>
          )}
          {byokSaved && (
            <p className="mt-2 flex items-center gap-1.5 text-sm text-brand-primary animate-fade-in">
              <CheckCircle2 className="w-4 h-4" strokeWidth={1.25} />
              Key 已保存
            </p>
          )}
          <p className="mt-2 text-xs text-text-muted flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 shrink-0" strokeWidth={1.25} />
            API Key 加密存储，本页面不会明文回显
          </p>

          <div className="mt-4 flex items-start gap-2 text-xs text-text-muted rounded-lg border border-border bg-black/30 p-3">
            <ImagePlus className="w-3.5 h-3.5 shrink-0 mt-0.5 text-warm-orange" strokeWidth={1.25} />
            <span>
              多模态支持：评审时可上传截图、设计稿、BP 页面。支持视觉的模型（Claude、GPT-4o、Qwen-VL、GLM-4V 等）会直接看图；不支持视觉的模型仅按文字评审，流程不会中断。
            </span>
          </div>
        </section>
        )}

        {/* ---------------- 用量与兑换 ---------------- */}
        {activeSection === 'usage' && (
        <div className="space-y-6">
          {/* CDK 兑换码：无需登录，兑换后自动获得游客身份 */}
          <div className="rounded-xl border border-border bg-black/30 p-5">
            <div className="flex items-center gap-2 mb-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-warm-orange/10 border border-warm-orange/20">
                <Ticket className="w-3.5 h-3.5 text-warm-orange" strokeWidth={1.5} />
              </div>
              <h3 className="text-sm font-display font-semibold text-text-primary">
                CDK 兑换码
              </h3>
            </div>
            <p className="text-xs text-text-muted mb-3">
              {usage?.quota_mode === 'credits'
                ? '兑换后获得评审次数：每次评审消耗 1 次，使用平台共享 Key 时生效。'
                : '兑换后获得加量次数，套餐日限用完后自动垫付，使用平台共享 Key 时生效。'}
              匿名兑换自动创建游客身份，次数存在当前浏览器，请在清除缓存前使用完。
            </p>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={cdkCode}
                onChange={(e) => {
                  setCdkCode(e.target.value.toUpperCase())
                  setCdkError(null)
                  setCdkSuccess(null)
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void handleRedeemCdk()
                }}
                placeholder="AL-XXXX-XXXX-XXXX"
                className="flex-1 px-4 py-2.5 rounded-lg bg-black/30 border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-warm-orange transition-colors font-mono text-sm tracking-wider"
              />
              <button
                onClick={() => void handleRedeemCdk()}
                disabled={cdkBusy || !cdkCode.trim()}
                className={cn(
                  'flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-bold transition-all shrink-0',
                  cdkBusy || !cdkCode.trim()
                    ? 'bg-black/30 text-text-muted cursor-not-allowed'
                    : 'bg-warm-orange/15 text-warm-orange hover:bg-warm-orange/25'
                )}
              >
                {cdkBusy ? (
                  <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.25} />
                ) : (
                  <Ticket className="w-4 h-4" strokeWidth={1.25} />
                )}
                兑换
              </button>
            </div>
            {cdkSuccess && (
              <p className="mt-2 flex items-center gap-1.5 text-sm text-brand-primary animate-fade-in">
                <CheckCircle2 className="w-4 h-4" strokeWidth={1.25} />
                兑换成功 +{cdkSuccess.granted} 次，当前余额 {cdkSuccess.balance} 次
                {cdkSuccess.guest && (
                  <span className="text-xs text-text-muted">（已为你创建游客身份并自动登录）</span>
                )}
              </p>
            )}
            {cdkError && (
              <p className="mt-2 flex items-start gap-1.5 text-sm text-severity-critical">
                <XCircle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.25} />
                <span>{cdkError}</span>
              </p>
            )}
          </div>

          {/* 24h 用量：quota 关闭时只报数字，不画配额条 */}
          {usage && (
            <div className="mt-6 rounded-xl border border-border bg-black/30 p-5">
              <div className="flex items-center gap-2 mb-4">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-cyan/10 border border-cyan/20">
                  <BarChart3 className="w-3.5 h-3.5 text-cyan" strokeWidth={1.5} />
                </div>
                <h3 className="text-sm font-display font-semibold text-text-primary">
                  近 24 小时用量
                </h3>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-lg bg-black/30 border border-border p-3">
                  <div className="text-xs text-text-muted mb-1">评审次数</div>
                  <div className="font-display text-2xl font-bold text-text-primary">
                    {usage.reviews_used_all}
                  </div>
                  {usage.quota_enabled && usage.reviews_limit != null && (
                    <div className="mt-1 text-[10px] text-text-muted">
                      平台垫付 {usage.reviews_used} / {usage.reviews_limit}
                    </div>
                  )}
                </div>
                <div className="rounded-lg bg-black/30 border border-border p-3">
                  <div className="text-xs text-text-muted mb-1">
                    {usage.quota_mode === 'credits' ? '剩余次数' : '加量余额'}
                  </div>
                  <div className="font-display text-2xl font-bold text-brand-primary">
                    {usage.bonus_credits ?? 0}
                    <span className="text-text-muted font-normal text-sm"> 次</span>
                  </div>
                </div>
                <div className="rounded-lg bg-black/30 border border-border p-3">
                  <div className="text-xs text-text-muted mb-1">总费用</div>
                  <div className="font-display text-2xl font-bold text-warm-orange">${usage.cost_usd_total.toFixed(2)}</div>
                </div>
                <div className="rounded-lg bg-black/30 border border-border p-3">
                  <div className="text-xs text-text-muted mb-1">其中服务器 Key</div>
                  <div className="font-display text-2xl font-bold text-text-secondary">${usage.cost_usd_on_server_key.toFixed(2)}</div>
                </div>
              </div>
              {usage.quota_enabled && usage.reviews_limit != null && usage.reviews_limit > 0 && (
                <div className="mt-3">
                  <div className="h-2 bg-black/30 rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all duration-700',
                        usage.reviews_used >= usage.reviews_limit ? 'bg-severity-critical' : 'bg-cyan'
                      )}
                      style={{
                        width: `${Math.min(100, Math.round((usage.reviews_used / usage.reviews_limit) * 100))}%`,
                      }}
                    />
                  </div>
                  <p className="mt-1.5 text-xs text-text-muted">配额窗口：{usage.window}</p>
                </div>
              )}

              {/* 终身 token 额度。故意放在配额块最后、且不受 quota_enabled 影响：
                  上面那些是 24h 滚动窗口，这一条不重置——两者性质不同，混在一起
                  会让人以为"明天就恢复了"。没设上限时只显示已用量，不显示进度条。 */}
              {/* 条件里的 tokens_limit != null 不能省：原先只判 tokens_used > 0，
                  于是"额度已设、但还没用过"时整块不显示——而新用户在第一次评审前
                  恰恰最需要知道自己有多少额度，那时 tokens_used 必然是 0。 */}
              {(usage.tokens_used_all > 0 || usage.tokens_limit != null) && (
                <div className="mt-4 border-t border-border pt-3">
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs text-text-secondary">累计 token 用量（不按天重置）</span>
                    <span className="font-mono text-sm text-text-primary">
                      {/* 主数字是"你一共花了多少"（含 BYOK）。此前这里放的是
                          tokens_used（只算平台垫付），BYOK 用户永远看到 0，
                          整块还因为 >0 的条件被隐藏——等于这个功能对他不存在。 */}
                      {usage.tokens_used_all.toLocaleString()}
                      <span className="ml-1 text-xs text-text-muted">tokens</span>
                    </span>
                  </div>
                  {usage.tokens_limit != null && usage.tokens_limit > 0 && (
                    <>
                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-black/30">
                        <div
                          className={cn(
                            'h-full rounded-full transition-all',
                            usage.tokens_used >= usage.tokens_limit ? 'bg-severity-critical' : 'bg-cyan'
                          )}
                          style={{ width: `${Math.min(100, Math.round((usage.tokens_used / usage.tokens_limit) * 100))}%` }}  /* 进度条按平台垫付口径——它约束的就是这部分 */
                        />
                      </div>
                      <p className="mt-1.5 text-xs text-text-muted">
                        体验额度只约束平台垫付的部分：已用 {usage.tokens_used.toLocaleString()} /{' '}
                        {usage.tokens_limit?.toLocaleString()}。用自己的 API Key（BYOK）跑的不计入。
                      </p>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
        )}

        {/* ---------------- 数据自主权 ----------------
         * "你的东西归你"不能只写在隐私政策里——给两个用户能亲手按的按钮，
         * 承诺才变成可验证的事实。 */}
        {activeSection === 'data' && (
        <section className="rounded-xl border border-border bg-bg-card p-5 md:p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-primary/10 border border-brand-primary/20">
              <ShieldCheck className="h-5 w-5 text-brand-primary" strokeWidth={1.5} />
            </div>
            <div>
              <h2 className="text-lg font-display font-semibold text-text-primary">
                我的数据
              </h2>
              <p className="text-xs text-text-muted">
                你上传的材料、评审报告、对话记录随时可以导出或永久删除。
              </p>
            </div>
          </div>

          {dataError && (
            <p className="mt-3 rounded-md border border-severity-critical/30 bg-severity-critical/10 px-3 py-2 font-mono text-xs text-severity-critical">
              {dataError}
            </p>
          )}

          {deleteDone && (
            <div className="mt-3 rounded-md border border-brand-primary/30 bg-brand-primary/10 px-3 py-2 text-xs text-brand-primary">
              已删除：{deleteDone.reviews_deleted} 条评审、{deleteDone.api_keys_deleted} 个密钥。
              计费流水已切断与你的关联（保留无主统计，见隐私政策）。
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              onClick={() => void handleExport()}
              disabled={exporting}
              className="flex items-center gap-1.5 rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary transition-colors hover:border-brand-primary/40 disabled:opacity-50"
            >
              {exporting ? (
                <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
              ) : (
                <Download className="h-4 w-4" strokeWidth={1.5} />
              )}
              导出我的全部数据
            </button>

            <button
              onClick={() => { setDeleteOpen(true); setDeleteDone(null) }}
              className="flex items-center gap-1.5 rounded-md border border-severity-critical/30 bg-severity-critical/5 px-3 py-2 text-sm text-severity-critical transition-colors hover:bg-severity-critical/10"
            >
              <Trash2 className="h-4 w-4" strokeWidth={1.5} />
              删除我的账号与数据
            </button>
          </div>

          {deleteOpen && (
            <div className="mt-4 rounded-lg border border-severity-critical/30 bg-severity-critical/5 p-4">
              <p className="flex items-start gap-2 text-sm text-text-primary">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-severity-critical" strokeWidth={2} />
                <span>
                  这会<strong>立即物理删除</strong>你的全部评审、上传材料、报告、追问记录和已保存的
                  API 密钥，<strong>不可撤销</strong>。
                  <br />
                  计费与兑换流水会保留但切断与你的关联（财务对账所需，此后无法回指到你本人）。
                  <br />
                  建议先「导出我的全部数据」留个备份。
                </span>
              </p>

              <div className="mt-3 space-y-2">
                <div>
                  <label className="text-xs text-text-muted">
                    输入「删除我的账号」以确认
                  </label>
                  <input
                    value={deleteConfirm}
                    onChange={(e) => setDeleteConfirm(e.target.value)}
                    placeholder="删除我的账号"
                    className="mt-1 w-full rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none focus:border-severity-critical/50"
                  />
                </div>
                {!identity?.is_anonymous && (
                  <div>
                    <label className="text-xs text-text-muted">账号密码</label>
                    <input
                      type="password"
                      value={deletePassword}
                      onChange={(e) => setDeletePassword(e.target.value)}
                      className="mt-1 w-full rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary outline-none focus:border-severity-critical/50"
                    />
                  </div>
                )}
              </div>

              <div className="mt-3 flex gap-2">
                <button
                  onClick={() => void handleDeleteAccount()}
                  disabled={deleting || deleteConfirm !== '删除我的账号'}
                  className="rounded-md bg-severity-critical px-3 py-2 text-sm font-semibold text-white disabled:opacity-40"
                >
                  {deleting ? '删除中…' : '确认永久删除'}
                </button>
                <button
                  onClick={() => { setDeleteOpen(false); setDeleteConfirm(''); setDeletePassword('') }}
                  className="rounded-md border border-border px-3 py-2 text-sm text-text-secondary"
                >
                  取消
                </button>
              </div>
            </div>
          )}
        </section>
        )}
      </div>
        </div>
      </div>

      <div className="mt-8 pt-6 border-t border-border text-center">
        <Link to="/privacy" className="text-xs text-text-muted hover:text-text-secondary transition-colors">
          隐私政策
        </Link>
      </div>
    </div>
  )
}
