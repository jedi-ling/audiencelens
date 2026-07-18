import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router'
import { cn } from '@/lib/utils'
import { api, setToken } from '@/lib/apiClient'
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
} from 'lucide-react'

type Provider = 'anthropic' | 'openai_compatible'
type TestStatus = 'idle' | 'testing' | 'success' | 'error'

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
      border: 'border-neon-green/50',
      bg: 'bg-neon-green/10',
      text: 'text-neon-green',
      glow: 'shadow-[0_0_15px_rgba(212,169,78,0.15)]',
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
      glow: 'shadow-[0_0_15px_rgba(78,205,196,0.15)]',
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
      if (result.token) setToken(result.token)
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

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="font-display text-3xl md:text-4xl font-bold text-gradient-green mb-2">
          LLM 设置
        </h1>
        <p className="text-text-secondary">
          配置评审系统实际调用的大语言模型：支持 Anthropic 原生，以及任意 OpenAI 兼容服务（DeepSeek / Kimi /
          通义千问 / 智谱 GLM / Ollama 本地模型等）。测试按钮走的是评审真正会用的链路，不是摆设。
        </p>
      </div>

      <div className="space-y-8">
        <section className="pt-2">
          <h2 className="text-lg font-display font-semibold text-text-primary mb-3 flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-neon-green" strokeWidth={1.25} />
            API Key（BYOK）
          </h2>
          <p className="text-xs text-text-muted mb-4">
            自带 Key 用于 Web 评审链路：Key 加密存储在服务端，评审时按你的 Key 计费。
            {keyStatus?.server_key_available && '（服务器也配置了共享 Key，可作为回落）'}
          </p>

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
                  className="flex items-center gap-3 px-4 py-3 rounded-lg bg-bg-card border border-neon-green/30"
                >
                  <CheckCircle2 className="w-4 h-4 text-neon-green shrink-0" strokeWidth={1.25} />
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
                    'bg-bg-card hover:bg-bg-card-hover',
                    isSelected ? cn(cfg.color.border, cfg.color.glow) : 'border-border hover:border-border-hover'
                  )}
                >
                  {isSelected && <div className={cn('absolute inset-0 opacity-10', cfg.color.bg)} />}
                  <Icon
                    className={cn('w-6 h-6 relative z-10 transition-colors', isSelected ? cfg.color.text : 'text-text-muted')}
                    strokeWidth={1.25}
                  />
                  <span className={cn('text-sm font-medium relative z-10 transition-colors', isSelected ? 'text-text-primary' : 'text-text-secondary')}>
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
                      'bg-bg-card hover:bg-bg-card-hover',
                      isMatch ? 'border-cyan/50 bg-cyan/5' : 'border-border hover:border-border-hover'
                    )}
                  >
                    <Icon className={cn('w-4 h-4 shrink-0', isMatch ? 'text-cyan' : 'text-text-muted')} strokeWidth={1.25} />
                    <div className="min-w-0 flex-1">
                      <div className={cn('text-xs font-medium truncate', isMatch ? 'text-text-primary' : 'text-text-secondary')}>
                        {preset.name}
                      </div>
                      <div className="text-[10px] text-text-muted font-mono truncate">{preset.model}</div>
                    </div>
                  </button>
                )
              })}
            </div>
          )}

          {/* 模型名 + API Base（仅 OpenAI 兼容需要；Anthropic 可留空走人格分级选型） */}
          {byokProvider === 'openai_compatible' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
              <div>
                <label className="block text-xs text-text-muted mb-1.5">模型名称</label>
                <input
                  type="text"
                  value={byokModel}
                  onChange={(e) => {
                    setByokModel(e.target.value)
                    resetTest()
                  }}
                  placeholder="deepseek-chat"
                  className="w-full px-3 py-2.5 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-cyan transition-colors font-mono text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-text-muted mb-1.5">API Base URL</label>
                <input
                  type="text"
                  value={byokApiBase}
                  onChange={(e) => {
                    setByokApiBase(e.target.value)
                    resetTest()
                  }}
                  placeholder="https://api.deepseek.com"
                  className="w-full px-3 py-2.5 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-cyan transition-colors font-mono text-sm"
                />
              </div>
            </div>
          )}

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
                placeholder={byokProvider === 'anthropic' ? 'sk-ant-…（输入 Anthropic API Key）' : '输入对应服务商的 API Key（Ollama 本地可留空）'}
                className="w-full px-4 py-3 pr-12 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-neon-green transition-colors font-mono text-sm"
              />
              <button
                onClick={() => setShowByokKey(!showByokKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md hover:bg-bg-card-hover text-text-muted hover:text-text-secondary transition-colors"
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
                  ? 'bg-bg-secondary text-text-muted cursor-not-allowed'
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
                  ? 'bg-bg-card text-text-muted cursor-not-allowed'
                  : 'bg-neon-green text-bg-primary hover:bg-neon-green-dim'
              )}
            >
              {byokSaving ? <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.25} /> : <Save className="w-4 h-4" strokeWidth={1.25} />}
              保存 Key
            </button>
          </div>

          {testStatus === 'success' && testResult && (
            <div className="mt-2 flex items-center gap-2 text-sm text-neon-green">
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
            <p className="mt-2 flex items-center gap-1.5 text-sm text-neon-green animate-fade-in">
              <CheckCircle2 className="w-4 h-4" strokeWidth={1.25} />
              Key 已保存
            </p>
          )}
          <p className="mt-2 text-xs text-text-muted flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 shrink-0" strokeWidth={1.25} />
            API Key 加密存储在服务端，本页面不会明文回显
          </p>

          <div className="mt-4 flex items-start gap-2 text-xs text-text-muted rounded-lg border border-border bg-bg-card p-3">
            <ImagePlus className="w-3.5 h-3.5 shrink-0 mt-0.5 text-warm-orange" strokeWidth={1.25} />
            <span>
              多模态：对话页支持上传截图 / demo 图 / BP 页面，视觉能力模型（Claude、GPT-4o、Qwen-VL、GLM-4V 等）会真正"看到"图片；
              非视觉模型会静默降级为纯文字，不会中断评审。
            </span>
          </div>

          {/* CDK 兑换码：无需登录，兑换后自动获得游客身份 */}
          <div className="mt-6 rounded-xl border border-border bg-bg-card p-4">
            <h3 className="text-sm font-display font-semibold text-text-primary mb-1 flex items-center gap-2">
              <Ticket className="w-4 h-4 text-warm-orange" strokeWidth={1.25} />
              CDK 兑换码
            </h3>
            <p className="text-xs text-text-muted mb-3">
              {usage?.quota_mode === 'credits'
                ? '兑换后获得评审次数：每次评审消耗 1 次，用完可再兑（走平台垫付 Key 时生效）。'
                : '兑换后获得评审加量次数，套餐日限用完后自动垫付（走平台垫付 Key 时生效）。'}
              无需注册——匿名兑换会自动创建游客身份，次数存在这个浏览器里，清除缓存前请勿弄丢。
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
                className="flex-1 px-4 py-2.5 rounded-lg bg-bg-secondary border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-warm-orange transition-colors font-mono text-sm tracking-wider"
              />
              <button
                onClick={() => void handleRedeemCdk()}
                disabled={cdkBusy || !cdkCode.trim()}
                className={cn(
                  'flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-bold transition-all shrink-0',
                  cdkBusy || !cdkCode.trim()
                    ? 'bg-bg-secondary text-text-muted cursor-not-allowed'
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
              <p className="mt-2 flex items-center gap-1.5 text-sm text-neon-green animate-fade-in">
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
            <div className="mt-6 rounded-xl border border-border bg-bg-card p-4">
              <h3 className="text-sm font-display font-semibold text-text-primary mb-3 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-cyan" strokeWidth={1.25} />
                近 24 小时用量
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div>
                  <div className="text-xs text-text-muted mb-1">评审次数</div>
                  <div className="font-display font-bold text-text-primary">
                    {usage.reviews_used}
                    {usage.quota_enabled && usage.reviews_limit != null && (
                      <span className="text-text-muted font-normal"> / {usage.reviews_limit}</span>
                    )}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-text-muted mb-1">
                    {usage.quota_mode === 'credits' ? '剩余次数' : '加量余额'}
                  </div>
                  <div className="font-display font-bold text-neon-green">
                    {usage.bonus_credits ?? 0}
                    <span className="text-text-muted font-normal text-xs"> 次</span>
                  </div>
                </div>
                <div>
                  <div className="text-xs text-text-muted mb-1">总费用</div>
                  <div className="font-display font-bold text-warm-orange">${usage.cost_usd_total.toFixed(4)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted mb-1">其中服务器 Key</div>
                  <div className="font-display font-bold text-text-secondary">${usage.cost_usd_on_server_key.toFixed(4)}</div>
                </div>
              </div>
              {usage.quota_enabled && usage.reviews_limit != null && usage.reviews_limit > 0 && (
                <div className="mt-3">
                  <div className="h-2 bg-bg-secondary rounded-full overflow-hidden">
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
            </div>
          )}
        </section>
      </div>

      <div className="mt-8 pt-6 border-t border-border text-center">
        <Link to="/privacy" className="text-xs text-text-muted hover:text-text-secondary transition-colors">
          隐私政策
        </Link>
      </div>
    </div>
  )
}
