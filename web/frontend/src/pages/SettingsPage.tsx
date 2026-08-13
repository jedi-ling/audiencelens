import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router'
import { cn } from '@/lib/utils'
import { api, claimPendingReviews, setToken } from '@/lib/apiClient'
import { useSessionStore } from '@/store/session-store'
import type { KeyStatus, UsageSummary, TestConnectionResult } from '@/lib/types'
import { OPENAI_COMPATIBLE_PRESETS } from '@/lib/types'
import { t, Trans } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import { formatDateTime, formatNumber, formatUsd } from '@/i18n/format'
import { tApiError } from '@/i18n/api-error'
import type { PlainMessageKey } from '@/i18n/keys.gen'
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
  LogOut,
  User,
} from 'lucide-react'

type Provider = 'anthropic' | 'openai_compatible'
type TestStatus = 'idle' | 'testing' | 'success' | 'error'
type SectionKey = 'account' | 'model' | 'usage' | 'data'

// 参考 MiniMax 控制台那种「左侧分组导航 + 右侧单类目内容」的信息架构——
// 之前是三个大 section 从上到下堆一整屏，用户想改密码得先划过整块 BYOK
// 表单。分组按"这是关于什么"分：账户身份 / 怎么接模型 / 花了多少钱 / 数据主权，
// 而不是按"这段代码是什么时候加的"从上到下堆。
// 存的是 **key 不是文案**：这个数组在模块求值时就固定了，存翻译结果的话
// 切换语言不会重新求值，左侧导航会一直停在打开页面时的那种语言。
const NAV_GROUPS: Array<{
  labelKey: PlainMessageKey
  items: Array<{ key: SectionKey; labelKey: PlainMessageKey; icon: React.ElementType }>
}> = [
  {
    labelKey: 'page.settings.group_account.label',
    items: [{ key: 'account', labelKey: 'page.settings.section_account.tab', icon: User }],
  },
  {
    labelKey: 'page.settings.group_model.label',
    items: [{ key: 'model', labelKey: 'page.settings.section_model.tab', icon: KeyRound }],
  },
  {
    labelKey: 'page.settings.group_usage.label',
    items: [{ key: 'usage', labelKey: 'page.settings.section_usage.tab', icon: BarChart3 }],
  },
  {
    labelKey: 'page.settings.group_data.label',
    items: [{ key: 'data', labelKey: 'page.settings.section_data.tab', icon: ShieldCheck }],
  },
]

// 同样存 key 不存文案（理由见 NAV_GROUPS 上面那两行）。color 留在这里——样式不是文案。
const PROVIDER_CONFIG: Record<Provider, {
  labelKey: PlainMessageKey
  icon: React.ElementType
  color: { border: string; bg: string; text: string; glow: string }
  descKey: PlainMessageKey
}> = {
  anthropic: {
    labelKey: 'page.settings.provider_anthropic.label',
    icon: Bot,
    color: {
      border: 'border-brand-primary/50',
      bg: 'bg-brand-primary/10',
      text: 'text-brand-primary',
      glow: 'shadow-[0_2px_12px_rgba(0,113,227,0.12)]',
    },
    descKey: 'page.settings.provider_anthropic.desc',
  },
  openai_compatible: {
    labelKey: 'page.settings.provider_openai.label',
    icon: Cpu,
    color: {
      border: 'border-cyan/50',
      bg: 'bg-cyan/10',
      text: 'text-cyan',
      glow: 'shadow-[0_2px_12px_rgba(50,173,230,0.12)]',
    },
    descKey: 'page.settings.provider_openai.desc',
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
  // 顺带订阅 ui_lang：t() 是普通函数、不带响应性，切语言时要有人触发重渲染。
  useDocumentTitle('page.settings.meta.title')
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
  // 成功提示存布尔不存文案：它只有一种内容，存翻译结果的话用户在提示还挂着的时候
  // 切语言，那句话不会跟着变。错误提示只能存字符串（里面可能是后端原文），
  // 那一条的语言滞后是已知限制，记在交付报告里。
  const [nameSaved, setNameSaved] = useState(false)
  const [nameError, setNameError] = useState<string | null>(null)

  const [pwCurrent, setPwCurrent] = useState('')
  const [pwNext, setPwNext] = useState('')
  const [pwConfirm, setPwConfirm] = useState('')
  const [pwBusy, setPwBusy] = useState(false)
  const [pwSaved, setPwSaved] = useState(false)
  const [pwError, setPwError] = useState<string | null>(null)
  // 登出所有设备：两段式确认（第一次点变成"确认？"，再点才真执行）。
  // 不用 window.confirm——它在移动端体验差，且被浏览器"阻止此页面弹窗"拦掉时
  // 会静默什么都不发生，用户以为点了没反应。
  const [revokeBusy, setRevokeBusy] = useState(false)
  const [revokeConfirm, setRevokeConfirm] = useState(false)
  const [revokeError, setRevokeError] = useState<string | null>(null)

  useEffect(() => {
    // 进页面时把当前昵称填进输入框当初值；identity 是异步拿的，所以放 effect 里。
    if (identity?.display_name) setNameDraft(identity.display_name)
  }, [identity?.display_name])

  const handleSaveName = async () => {
    const name = nameDraft.trim()
    if (!name) { setNameError(t('common.validate.required')); return }
    setNameBusy(true); setNameError(null); setNameSaved(false)
    try {
      await api.updateProfile(name)
      // 重新拉一次身份：顶栏、账户菜单都读 store 里的 identity，不刷新的话
      // 页面上的名字会和刚保存的值不一致，看起来像没保存成功。
      await useSessionStore.getState().bootstrap()
      setNameSaved(true)
    } catch (e) {
      setNameError(tApiError(e, 'page.settings.name.error'))
    } finally {
      setNameBusy(false)
    }
  }

  const handleChangePassword = async () => {
    // 两次新密码不一致要在本地就拦下——让用户把一个打错的密码提交上去、
    // 成功了才发现自己不知道新密码是什么，是最糟的失败方式。
    if (pwNext !== pwConfirm) { setPwError(t('common.validate.password_mismatch')); return }
    if (pwNext.length < 8) { setPwError(t('common.validate.password_min', { min: 8 })); return }
    setPwBusy(true); setPwError(null); setPwSaved(false)
    try {
      const r = await api.changePassword(pwCurrent, pwNext)
      // 关键一步：后端撤销了该用户全部旧会话，手上这把 token 已经作废。
      // 不换成返回的新令牌的话，改完密码下一个请求就 401，用户会以为自己被登出了。
      setToken(r.token)
      setPwCurrent(''); setPwNext(''); setPwConfirm('')
      setPwSaved(true)
    } catch (e) {
      setPwError(tApiError(e, 'page.settings.password.error'))
    } finally {
      setPwBusy(false)
    }
  }

  /** 登出所有设备。
   *
   *  与 handleChangePassword 的关键差别：那边后端会回一把新令牌让本设备续上，
   *  这边**不会**——本设备也被登出。所以成功后必须 setToken(null) 并跳登录页，
   *  否则页面会带着一把已作废的令牌继续跑，下一个请求 401，用户看到的是
   *  一堆莫名其妙的报错而不是"已登出"。
   */
  const handleRevokeAllSessions = async () => {
    if (!revokeConfirm) { setRevokeConfirm(true); setRevokeError(null); return }
    setRevokeBusy(true); setRevokeError(null)
    try {
      await api.revokeAllSessions()
      setToken(null)
      // 用整页跳转而不是 router navigate：本地还残留着 session-store 里的
      // identity/keys 等状态，软跳转会让登录页上半截还显示着上一个账号的信息。
      window.location.href = '/login'
    } catch (e) {
      setRevokeError(tApiError(e, 'common.ui.unknown_error'))
      setRevokeConfirm(false)
    } finally {
      setRevokeBusy(false)
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
      setDataError(tApiError(e, 'page.settings.export.error'))
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
      setDataError(tApiError(e, 'page.settings.delete_account.error'))
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
      setByokError(t('page.settings.byok.error'))
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
      setTestResult({ connected: false, error: tApiError(e, 'page.settings.test.error') })
      setTestStatus('error')
    }
  }

  const handleByokSave = async () => {
    if (!byokKey.trim()) return
    if (byokProvider === 'openai_compatible' && !byokModel.trim()) {
      setByokError(t('page.settings.model_id.error'))
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
      setByokError(tApiError(e, 'page.settings.save_key.error'))
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
      setCdkError(tApiError(e, 'page.settings.cdk.error'))
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
      setByokError(tApiError(e, 'page.settings.key_item.error'))
    } finally {
      setByokDeleting(null)
    }
  }

  // 这张表在组件体内求值，切语言时随重渲染重新 t()，所以这里可以直接放文案。
  // （模块级常量 NAV_GROUPS / PROVIDER_CONFIG 就不行——那两处必须存 key。）
  const SECTION_HEADERS: Record<SectionKey, { title: string; desc: string }> = {
    account: {
      title: t('page.settings.section_account.title'),
      desc: identity?.is_anonymous
        ? t('page.settings.section_account_guest.desc')
        : t('page.settings.section_account.desc'),
    },
    model: {
      title: t('page.settings.section_model.title'),
      desc: t('page.settings.section_model.desc'),
    },
    usage: {
      title: t('page.settings.section_usage.title'),
      desc: t('page.settings.section_usage.desc'),
    },
    data: {
      title: t('page.settings.section_data.title'),
      desc: t('page.settings.section_data.desc'),
    },
  }

  return (
    // 表单/阅读型页面：与其他设置类页面同一档容器
    <div className="max-w-4xl mx-auto px-4 py-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="font-display text-2xl font-bold text-text-primary">
          {t('page.settings.header.title')}
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          {t('page.settings.header.desc')}
        </p>
      </div>

      <div className="flex flex-col md:flex-row gap-8 items-start">
        {/* 左侧分组导航——按"这是关于什么"分组（账户身份 / 怎么接模型 /
            花了多少钱 / 数据主权），不是按代码加入的先后顺序堆叠。 */}
        <aside className="w-full md:w-56 shrink-0 md:sticky md:top-24">
          <nav className="space-y-5">
            {NAV_GROUPS.map((group) => (
              <div key={group.labelKey}>
                <div className="px-3 mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                  {t(group.labelKey)}
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
                        <span className="truncate">{t(item.labelKey)}</span>
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
                    {t('page.settings.guest_card.title')}
                  </h3>
                  <p className="text-xs text-text-muted">
                    {t('page.settings.guest_card.desc')}
                  </p>
                </div>
              </div>
              <Link
                to="/login"
                className="mt-4 inline-flex items-center gap-1.5 rounded-md bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-dim"
              >
                {t('page.settings.guest_card.cta')}
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
                    {t('page.settings.account_card.title')}
                  </h3>
                  <p className="text-xs text-text-muted">
                    {/* email 在类型上是 string | null。原来直接渲染，null 会渲染成空字符串，
                        句子变成"当前登录："后面什么都没有。这里用显式的"未记录"而不是空串，
                        让"没有邮箱"和"邮箱没加载出来"在界面上长得不一样。 */}
                    {t('page.settings.account_card.desc', {
                      email: identity?.email ?? t('common.ui.not_recorded'),
                    })}
                  </p>
                </div>
              </div>
              {/* 昵称 */}
              <div className="mt-4 rounded-lg border border-border bg-black/30 p-4">
                <label className="block text-xs font-medium text-text-secondary">{t('page.settings.name.label')}</label>
                <div className="mt-2 flex flex-wrap gap-2">
                  <input
                    value={nameDraft}
                    onChange={(e) => { setNameDraft(e.target.value); setNameSaved(false); setNameError(null) }}
                    maxLength={50}
                    className="min-w-0 flex-1 rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary/50"
                    placeholder={t('page.settings.name.placeholder')}
                  />
                  <button
                    onClick={() => void handleSaveName()}
                    disabled={nameBusy || !nameDraft.trim() || nameDraft.trim() === (identity?.display_name ?? '')}
                    className="flex items-center gap-1.5 rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary transition-colors hover:border-brand-primary/40 disabled:opacity-50"
                  >
                    {nameBusy ? <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} /> : <Save className="h-4 w-4" strokeWidth={1.5} />}
                    {t('common.action.save')}
                  </button>
                </div>
                {nameSaved && <p className="mt-2 text-xs text-brand-primary">{t('page.settings.name.success')}</p>}
                {nameError && <p className="mt-2 text-xs text-severity-critical">{nameError}</p>}
                <p className="mt-2 text-xs text-text-muted">
                  {t('page.settings.name.hint')}
                </p>
              </div>

              {/* 密码 */}
              <div className="mt-3 rounded-lg border border-border bg-black/30 p-4">
                <label className="block text-xs font-medium text-text-secondary">{t('page.settings.password.label')}</label>
                <div className="mt-2 grid gap-2 sm:grid-cols-3">
                  <input
                    type="password" value={pwCurrent} autoComplete="current-password"
                    onChange={(e) => { setPwCurrent(e.target.value); setPwSaved(false); setPwError(null) }}
                    placeholder={t('page.settings.password_current.placeholder')}
                    className="rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary/50"
                  />
                  <input
                    type="password" value={pwNext} autoComplete="new-password"
                    onChange={(e) => { setPwNext(e.target.value); setPwSaved(false); setPwError(null) }}
                    placeholder={t('page.settings.password_new.placeholder')}
                    className="rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary/50"
                  />
                  <input
                    type="password" value={pwConfirm} autoComplete="new-password"
                    onChange={(e) => { setPwConfirm(e.target.value); setPwSaved(false); setPwError(null) }}
                    placeholder={t('page.settings.password_confirm.placeholder')}
                    className="rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary/50"
                  />
                </div>
                <button
                  onClick={() => void handleChangePassword()}
                  disabled={pwBusy || !pwCurrent || !pwNext || !pwConfirm}
                  className="mt-3 flex items-center gap-1.5 rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary transition-colors hover:border-brand-primary/40 disabled:opacity-50"
                >
                  {pwBusy ? <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} /> : <KeyRound className="h-4 w-4" strokeWidth={1.5} />}
                  {t('page.settings.password.cta')}
                </button>
                {pwSaved && <p className="mt-2 text-xs text-brand-primary">{t('page.settings.password.success')}</p>}
                {pwError && <p className="mt-2 text-xs text-severity-critical">{pwError}</p>}
                <p className="mt-2 text-xs text-text-muted">
                  {t('page.settings.password.hint')}
                </p>
              </div>

              {/* 登出所有设备。
                  与改密码分开是有意的：怀疑账号被盗时第一反应是"把别人踢下线"，
                  而改密码要求先想出并记住一个新密码——多一道摩擦，慌乱时最容易被拖延。
                  撤销会话是止血，改密码是治本，不该绑成一件事。 */}
              <div className="mt-3 rounded-lg border border-border bg-black/30 p-4">
                <label className="block text-xs font-medium text-text-secondary">{t('page.settings.revoke.label')}</label>
                <p className="mt-1.5 text-xs leading-relaxed text-text-muted">
                  <Trans
                    k="page.settings.revoke.desc"
                    slots={{
                      strong: (s) => <strong className="text-text-secondary">{s}</strong>,
                    }}
                  />
                </p>
                <button
                  onClick={() => void handleRevokeAllSessions()}
                  disabled={revokeBusy}
                  className="mt-3 flex items-center gap-1.5 rounded-md border border-severity-critical/40 bg-black/30 px-3 py-2 text-sm text-severity-critical transition-colors hover:bg-severity-critical/10 disabled:opacity-50"
                >
                  {revokeBusy
                    ? <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
                    : <LogOut className="h-4 w-4" strokeWidth={1.5} />}
                  {revokeConfirm ? t('page.settings.revoke.confirm') : t('page.settings.revoke.cta')}
                </button>
                {revokeConfirm && !revokeBusy && (
                  <p className="mt-2 text-xs text-warm-orange">
                    {t('page.settings.revoke.hint')}
                  </p>
                )}
                {revokeError && <p className="mt-2 text-xs text-severity-critical">{revokeError}</p>}
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
                {t('page.settings.byok.title')}
              </h2>
              <p className="text-xs text-text-muted">
                {t('page.settings.byok.desc')}
                {/* JSX 会把跨行的空白整段吃掉，两句会直接粘在一起。中文粘着还看得下去，
                    英文 "…account.(optional — …)" 就是错的，所以显式补一个空格。 */}
                {keyStatus?.server_key_available && ` ${t('page.settings.byok.hint')}`}
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
                      {k.last_used_at && ` ${t('page.settings.key_item.meta', { time: formatDateTime(k.last_used_at) })}`}
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
                    {t('common.action.delete')}
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
                    {t(cfg.labelKey)}
                  </span>
                  <span className={cn('text-[10px] font-mono relative z-10 text-center transition-colors', isSelected ? 'text-text-secondary' : 'text-text-muted')}>
                    {t(cfg.descKey)}
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
                        {t(preset.nameKey)}
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
                {t('page.settings.model_id.label')} {byokProvider === 'anthropic' && <span className="text-text-muted/70">{t('page.settings.model_id.hint')}</span>}
              </label>
              <input
                type="text"
                value={byokModel}
                onChange={(e) => {
                  setByokModel(e.target.value)
                  resetTest()
                }}
                placeholder={byokProvider === 'anthropic' ? t('page.settings.model_id.placeholder') : t('page.settings.model_id_compat.placeholder')}
                className="w-full px-3 py-2.5 rounded-lg bg-black/30 border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-cyan transition-colors font-mono text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1.5">
                {t('page.settings.api_base.label')} {byokProvider === 'anthropic' && <span className="text-text-muted/70">{t('page.settings.api_base.hint')}</span>}
              </label>
              <input
                type="text"
                value={byokApiBase}
                onChange={(e) => {
                  setByokApiBase(e.target.value)
                  resetTest()
                }}
                placeholder={byokProvider === 'anthropic' ? t('page.settings.api_base.placeholder') : t('page.settings.api_base_compat.placeholder')}
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
                aria-label={t('page.settings.key_input.aria')}
                placeholder={byokProvider === 'anthropic' ? t('page.settings.key_input.placeholder') : t('page.settings.key_input_compat.placeholder')}
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
              {t('page.settings.test.cta')}
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
              {t('page.settings.save_key.cta')}
            </button>
          </div>

          {testStatus === 'success' && testResult && (
            <div className="mt-2 flex items-center gap-2 text-sm text-brand-primary">
              <CheckCircle2 className="w-4 h-4" strokeWidth={1.25} />
              <span>{t('page.settings.test.success')}</span>
              {testResult.model && <span className="text-text-muted font-mono text-xs">({testResult.model})</span>}
              {testResult.sample && (
                <span className="text-text-muted text-xs truncate max-w-[16rem]">{t('page.settings.test.meta', { sample: testResult.sample })}</span>
              )}
            </div>
          )}
          {testStatus === 'error' && (
            <div className="mt-2 flex items-start gap-2 text-sm text-severity-critical">
              <XCircle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.25} />
              {/* testResult.error 是后端自由文本（语种由后端决定），拿不到时才用本地文案。
                  这不是缺译兜底，是"后端没说原因"时的诚实占位。 */}
              <span className="break-all">{testResult?.error || t('page.settings.test.error')}</span>
            </div>
          )}
          {byokSaved && (
            <p className="mt-2 flex items-center gap-1.5 text-sm text-brand-primary animate-fade-in">
              <CheckCircle2 className="w-4 h-4" strokeWidth={1.25} />
              {t('page.settings.save_key.success')}
            </p>
          )}
          {/* 把 Key 交给别人的服务器，用户会有疑虑——这是合理的。
              与其含糊地写一句"加密存储"，不如逐条回答他心里真正在问的：
              谁能看到、你们拿去干嘛、我不想给行不行。
              最后那条（不填也能用 / 可自建）比任何安全承诺都更能消除怀疑，
              因为它把选择权交回给用户，而不是要求他信任我们。 */}
          <div className="mt-3 rounded-lg border border-border bg-black/30 p-3">
            <p className="flex items-center gap-1.5 text-xs font-medium text-text-secondary">
              <ShieldCheck className="w-3.5 h-3.5 shrink-0 text-brand-primary" strokeWidth={1.5} />
              {t('page.settings.key_privacy.title')}
            </p>
            <ul className="mt-2 space-y-1.5 text-xs leading-relaxed text-text-muted">
              {/* 每条都是"小标题：正文"。JSX 会把跨行空白整段吃掉，中文靠「：」
                  自带停顿看不出来，英文会变成 "Who can see it:No one."，所以逐条补空格。 */}
              <li>
                <span className="text-text-secondary">{t('page.settings.privacy_who.label')}</span>{' '}
                <Trans
                  k="page.settings.privacy_who.desc"
                  slots={{ code: (s) => <code className="font-mono">{s}</code> }}
                />
              </li>
              <li>
                <span className="text-text-secondary">{t('page.settings.privacy_use.label')}</span>{' '}
                {t('page.settings.privacy_use.desc')}
              </li>
              <li>
                <span className="text-text-secondary">{t('page.settings.privacy_device.label')}</span>{' '}
                {t('page.settings.privacy_device.desc')}
              </li>
              <li>
                <span className="text-text-secondary">{t('page.settings.privacy_optout.label')}</span>{' '}
                {keyStatus?.server_key_available
                  ? t('page.settings.privacy_optout.desc')
                  : t('page.settings.privacy_selfhost.desc')}
                {' '}{t('page.settings.privacy_optout.hint')}
              </li>
            </ul>
            <p className="mt-2 border-t border-border pt-2 text-[11px] text-text-muted">
              <Trans
                k="page.settings.privacy_source.desc"
                slots={{
                  privacy: (s) => <Link to="/privacy" className="text-cyan hover:underline">{s}</Link>,
                }}
              />
            </p>
          </div>

          <div className="mt-4 flex items-start gap-2 text-xs text-text-muted rounded-lg border border-border bg-black/30 p-3">
            <ImagePlus className="w-3.5 h-3.5 shrink-0 mt-0.5 text-warm-orange" strokeWidth={1.25} />
            <span>
              {t('page.settings.multimodal.desc')}
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
                {t('page.settings.cdk.title')}
              </h3>
            </div>
            <p className="text-xs text-text-muted mb-3">
              {usage?.quota_mode === 'credits'
                ? t('page.settings.cdk.desc')
                : t('page.settings.cdk_plan.desc')}
              {' '}{t('page.settings.cdk.hint')}
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
                placeholder={t('page.settings.cdk.placeholder')}
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
                {t('page.settings.cdk.cta')}
              </button>
            </div>
            {cdkSuccess && (
              <p className="mt-2 flex items-center gap-1.5 text-sm text-brand-primary animate-fade-in">
                <CheckCircle2 className="w-4 h-4" strokeWidth={1.25} />
                {t('page.settings.cdk.success', {
                  count: cdkSuccess.granted,
                  balance: formatNumber(cdkSuccess.balance),
                })}
                {cdkSuccess.guest && (
                  <span className="text-xs text-text-muted">{t('page.settings.cdk_guest.hint')}</span>
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
                  {t('page.settings.usage.title')}
                </h3>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-lg bg-black/30 border border-border p-3">
                  <div className="text-xs text-text-muted mb-1">{t('page.settings.usage_reviews.label')}</div>
                  <div className="font-display text-2xl font-bold text-text-primary">
                    {formatNumber(usage.reviews_used_all)}
                  </div>
                  {usage.quota_enabled && usage.reviews_limit != null && (
                    <div className="mt-1 text-[10px] text-text-muted">
                      {t('page.settings.usage_reviews.hint', {
                        used: formatNumber(usage.reviews_used),
                        limit: formatNumber(usage.reviews_limit),
                      })}
                    </div>
                  )}
                </div>
                <div className="rounded-lg bg-black/30 border border-border p-3">
                  <div className="text-xs text-text-muted mb-1">
                    {usage.quota_mode === 'credits'
                      ? t('page.settings.usage_credits.label')
                      : t('page.settings.usage_bonus.label')}
                  </div>
                  <div className="font-display text-2xl font-bold text-brand-primary">
                    {formatNumber(usage.bonus_credits ?? 0)}
                    <span className="text-text-muted font-normal text-sm"> {t('page.settings.usage_credits.unit')}</span>
                  </div>
                </div>
                <div className="rounded-lg bg-black/30 border border-border p-3">
                  <div className="text-xs text-text-muted mb-1">{t('page.settings.usage_cost.label')}</div>
                  <div className="font-display text-2xl font-bold text-warm-orange">{formatUsd(usage.cost_usd_total)}</div>
                </div>
                <div className="rounded-lg bg-black/30 border border-border p-3">
                  <div className="text-xs text-text-muted mb-1">{t('page.settings.usage_server_cost.label')}</div>
                  <div className="font-display text-2xl font-bold text-text-secondary">{formatUsd(usage.cost_usd_on_server_key)}</div>
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
                  <p className="mt-1.5 text-xs text-text-muted">{t('page.settings.usage.hint', { window: usage.window })}</p>
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
                    <span className="text-xs text-text-secondary">{t('page.settings.usage_tokens.label')}</span>
                    <span className="font-mono text-sm text-text-primary">
                      {/* 主数字是"你一共花了多少"（含 BYOK）。此前这里放的是
                          tokens_used（只算平台垫付），BYOK 用户永远看到 0，
                          整块还因为 >0 的条件被隐藏——等于这个功能对他不存在。 */}
                      {formatNumber(usage.tokens_used_all)}
                      <span className="ml-1 text-xs text-text-muted">{t('page.settings.usage_tokens.unit')}</span>
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
                        {t('page.settings.usage_tokens.hint', {
                          used: formatNumber(usage.tokens_used),
                          limit: formatNumber(usage.tokens_limit),
                        })}
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
                {t('page.settings.data.title')}
              </h2>
              <p className="text-xs text-text-muted">
                {t('page.settings.data.desc')}
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
              {t('page.settings.delete_done.desc', {
                reviews: formatNumber(deleteDone.reviews_deleted),
                keys: formatNumber(deleteDone.api_keys_deleted),
              })}
              {' '}{t('page.settings.delete_done.hint')}
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
              {t('page.settings.export.cta')}
            </button>

            <button
              onClick={() => { setDeleteOpen(true); setDeleteDone(null) }}
              className="flex items-center gap-1.5 rounded-md border border-severity-critical/30 bg-severity-critical/5 px-3 py-2 text-sm text-severity-critical transition-colors hover:bg-severity-critical/10"
            >
              <Trash2 className="h-4 w-4" strokeWidth={1.5} />
              {t('page.settings.delete_account.cta')}
            </button>
          </div>

          {deleteOpen && (
            <div className="mt-4 rounded-lg border border-severity-critical/30 bg-severity-critical/5 p-4">
              <p className="flex items-start gap-2 text-sm text-text-primary">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-severity-critical" strokeWidth={2} />
                <span>
                  <Trans
                    k="page.settings.delete_confirm.desc"
                    slots={{ strong: (s) => <strong>{s}</strong> }}
                  />
                </span>
              </p>

              <div className="mt-3 space-y-2">
                <div>
                  {/* 用户要敲进去的那句中文是**凭据不是文案**：后端 platform.py 的
                      DELETE_CONFIRM_PHRASE 做的是中文字面量相等比较。所以这里既不
                      自己写死一份，也不翻译它——一律取 common.action.delete_account_phrase
                      （zh/en 两侧值相同，i18n:check 对它单列豁免）。英文侧的提示语
                      里写清了"照着敲这句中文"，否则英文用户永远删不掉账号。见契约 6.8。 */}
                  <label className="text-xs text-text-muted">
                    {t('page.settings.delete_confirm.label', {
                      phrase: t('common.action.delete_account_phrase'),
                    })}
                  </label>
                  <input
                    value={deleteConfirm}
                    onChange={(e) => setDeleteConfirm(e.target.value)}
                    placeholder={t('common.action.delete_account_phrase')}
                    className="mt-1 w-full rounded-md border border-border bg-black/30 px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none focus:border-severity-critical/50"
                  />
                </div>
                {!identity?.is_anonymous && (
                  <div>
                    <label className="text-xs text-text-muted">{t('page.settings.delete_password.label')}</label>
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
                  disabled={deleting || deleteConfirm !== t('common.action.delete_account_phrase')}
                  className="rounded-md bg-severity-critical px-3 py-2 text-sm font-semibold text-white disabled:opacity-40"
                >
                  {deleting ? t('common.ui.deleting') : t('page.settings.delete_confirm.cta')}
                </button>
                <button
                  onClick={() => { setDeleteOpen(false); setDeleteConfirm(''); setDeletePassword('') }}
                  className="rounded-md border border-border px-3 py-2 text-sm text-text-secondary"
                >
                  {t('common.action.cancel')}
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
          {t('page.settings.footer.link')}
        </Link>
      </div>
    </div>
  )
}
