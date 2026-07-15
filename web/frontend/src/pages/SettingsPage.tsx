import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router'
import { cn } from '@/lib/utils'
import { fetchLLMFormats, fetchLLMPresets, saveLLMSettings, testLLMConnection } from '@/lib/api'
import type { LLMFormat, LLMPreset } from '@/lib/api'
import { api } from '@/lib/apiClient'
import type { KeyStatus, UsageSummary } from '@/lib/types'
import { Eye, EyeOff, Loader2, CheckCircle2, XCircle, Save, Wifi, WifiOff, Zap, Bot, Cpu, Globe, Server, ShieldCheck, ArrowRight, KeyRound, Trash2, BarChart3 } from 'lucide-react'

type ApiFormat = 'anthropic' | 'openai_compatible'
type TestStatus = 'idle' | 'testing' | 'success' | 'error'

const FORMAT_CONFIG: Record<ApiFormat, {
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
      glow: 'shadow-sm',
    },
    desc: '/v1/messages',
  },
  openai_compatible: {
    label: 'OpenAI 兼容',
    icon: Cpu,
    color: {
      border: 'border-cyan/50',
      bg: 'bg-cyan/10',
      text: 'text-cyan',
      glow: 'shadow-sm',
    },
    desc: '/v1/chat/completions',
  },
}

const PRESET_ICONS: Record<string, React.ElementType> = {
  anthropic_claude: Bot,
  openai_gpt: Cpu,
  deepseek: Globe,
  ollama: Server,
}

export default function SettingsPage() {
  const [formats, setFormats] = useState<Record<string, LLMFormat>>({})
  const [presets, setPresets] = useState<LLMPreset[]>([])
  const [loading, setLoading] = useState(true)

  const [apiFormat, setApiFormat] = useState<ApiFormat>('openai_compatible')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [showApiKey, setShowApiKey] = useState(false)
  const [apiBase, setApiBase] = useState('')

  const [testStatus, setTestStatus] = useState<TestStatus>('idle')
  const [testError, setTestError] = useState('')
  const [testModel, setTestModel] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // ---------------- BYOK（v2 平台链路）----------------
  const [keyStatus, setKeyStatus] = useState<KeyStatus | null>(null)
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [byokKey, setByokKey] = useState('')
  const [showByokKey, setShowByokKey] = useState(false)
  const [byokSaving, setByokSaving] = useState(false)
  const [byokDeleting, setByokDeleting] = useState<string | null>(null)
  const [byokError, setByokError] = useState<string | null>(null)
  const [byokSaved, setByokSaved] = useState(false)

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

  const handleByokSave = async () => {
    if (!byokKey.trim()) return
    setByokSaving(true)
    setByokError(null)
    setByokSaved(false)
    try {
      await api.saveKey(byokKey.trim())
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

  useEffect(() => {
    Promise.all([fetchLLMFormats(), fetchLLMPresets()])
      .then(([fmtData, presetData]) => {
        setFormats(fmtData)
        setPresets(presetData)
        const withEnv = presetData.find((p) => p.has_env_key)
        if (withEnv) {
          setApiFormat(withEnv.api_format as ApiFormat)
          setModel(withEnv.model)
          setApiBase(withEnv.api_base)
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (formats[apiFormat] && !apiBase) {
      setApiBase(formats[apiFormat].default_base)
    }
  }, [apiFormat, formats])

  const applyPreset = (preset: LLMPreset) => {
    setApiFormat(preset.api_format as ApiFormat)
    setModel(preset.model)
    setApiBase(preset.api_base)
    setTestStatus('idle')
    setTestError('')
  }

  const handleTest = async () => {
    if (!model.trim()) return
    setTestStatus('testing')
    setTestError('')
    try {
      const result = await testLLMConnection({
        api_format: apiFormat,
        api_key: apiKey || undefined,
        model: model.trim(),
        api_base: apiBase || undefined,
      })
      if (result.connected) {
        setTestStatus('success')
        setTestModel(result.model || model)
      } else {
        setTestStatus('error')
        setTestError(result.error || '连接失败')
      }
    } catch (e) {
      setTestStatus('error')
      setTestError(e instanceof Error ? e.message : '连接失败')
    }
  }

  const handleSave = async () => {
    if (!model.trim()) return
    setSaving(true)
    setSaveSuccess(false)
    try {
      await saveLLMSettings({
        api_format: apiFormat,
        api_key: apiKey,
        model: model.trim(),
        api_base: apiBase || undefined,
      })
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch {
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 text-neon-green animate-spin" strokeWidth={1.25} />
      </div>
    )
  }

  const currentFormatConfig = FORMAT_CONFIG[apiFormat]
  const FormatIcon = currentFormatConfig.icon

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="font-display text-3xl md:text-4xl font-bold text-gradient-green mb-2">
          LLM 设置
        </h1>
        <p className="text-text-secondary">
          配置评审系统使用的大语言模型，支持 Anthropic 原生和 OpenAI 兼容两种 API 范式
        </p>
      </div>

      <div className="space-y-8">
        <section>
          <h2 className="text-lg font-display font-semibold text-text-primary mb-3">
            API 范式
          </h2>
          <p className="text-xs text-text-muted mb-4">
            选择 API 调用格式：Anthropic 原生格式使用 /v1/messages 端点，OpenAI 兼容格式使用 /v1/chat/completions 端点
          </p>
          <div className="grid grid-cols-2 gap-3">
            {(Object.keys(FORMAT_CONFIG) as ApiFormat[]).map((fmt) => {
              const cfg = FORMAT_CONFIG[fmt]
              const Icon = cfg.icon
              const isSelected = apiFormat === fmt
              return (
                <button
                  key={fmt}
                  onClick={() => {
                    setApiFormat(fmt)
                    setApiBase(formats[fmt]?.default_base || '')
                    setTestStatus('idle')
                    setTestError('')
                  }}
                  className={cn(
                    'flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all cursor-pointer relative overflow-hidden',
                    'bg-bg-card hover:bg-bg-card-hover',
                    isSelected
                      ? cn(cfg.color.border, cfg.color.glow)
                      : 'border-border hover:border-border-hover'
                  )}
                >
                  {isSelected && (
                    <div className={cn('absolute inset-0 opacity-10', cfg.color.bg)} />
                  )}
                  <Icon
                    className={cn(
                      'w-7 h-7 relative z-10 transition-colors',
                      isSelected ? cfg.color.text : 'text-text-muted'
                    )}
                    strokeWidth={1.25}
                  />
                  <span
                    className={cn(
                      'text-sm font-medium relative z-10 transition-colors',
                      isSelected ? 'text-text-primary' : 'text-text-secondary'
                    )}
                  >
                    {cfg.label}
                  </span>
                  <span
                    className={cn(
                      'text-[10px] font-mono relative z-10 transition-colors',
                      isSelected ? 'text-text-secondary' : 'text-text-muted'
                    )}
                  >
                    {cfg.desc}
                  </span>
                  {isSelected && (
                    <div className={cn('absolute bottom-0 left-0 right-0 h-0.5', cfg.color.bg)} />
                  )}
                </button>
              )
            })}
          </div>
        </section>

        <section>
          <h2 className="text-lg font-display font-semibold text-text-primary mb-3">
            快捷预设
          </h2>
          <p className="text-xs text-text-muted mb-4">
            点击预设自动填充 API 范式、模型名和 API Base，也可手动自定义
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {presets.map((preset) => {
              const Icon = PRESET_ICONS[preset.id] || Cpu
              const isMatch = apiFormat === preset.api_format && model === preset.model
              return (
                <button
                  key={preset.id}
                  onClick={() => applyPreset(preset)}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2.5 rounded-lg border transition-all cursor-pointer text-left',
                    'bg-bg-card hover:bg-bg-card-hover',
                    isMatch
                      ? 'border-neon-green/50 bg-neon-green/5'
                      : 'border-border hover:border-border-hover'
                  )}
                >
                  <Icon
                    className={cn(
                      'w-4 h-4 shrink-0',
                      isMatch ? 'text-neon-green' : 'text-text-muted'
                    )}
                    strokeWidth={1.25}
                  />
                  <div className="min-w-0 flex-1">
                    <div className={cn(
                      'text-xs font-medium truncate',
                      isMatch ? 'text-text-primary' : 'text-text-secondary'
                    )}>
                      {preset.name}
                    </div>
                    <div className="text-[10px] text-text-muted font-mono truncate">
                      {preset.model}
                    </div>
                  </div>
                  {preset.has_env_key && (
                    <span className="text-[9px] px-1 py-0.5 rounded bg-neon-green/10 text-neon-green shrink-0">
                      环境变量
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </section>

        <section>
          <h2 className="text-lg font-display font-semibold text-text-primary mb-3">
            模型名称
          </h2>
          <div className="flex items-center gap-2">
            <div className={cn(
              'flex items-center gap-1.5 px-3 py-3 rounded-l-lg border border-r-0 text-xs font-mono',
              apiFormat === 'anthropic'
                ? 'border-neon-green/30 bg-neon-green/5 text-neon-green'
                : 'border-cyan/30 bg-cyan/5 text-cyan'
            )}>
              <FormatIcon className="w-3.5 h-3.5" strokeWidth={1.25} />
              {apiFormat === 'anthropic' ? 'anthropic/' : 'openai/'}
            </div>
            <input
              type="text"
              value={model}
              onChange={(e) => {
                setModel(e.target.value)
                setTestStatus('idle')
              }}
              placeholder={apiFormat === 'anthropic' ? 'claude-sonnet-4-20250514' : 'gpt-4o'}
              className="flex-1 px-4 py-3 rounded-r-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-neon-green transition-colors font-mono text-sm"
            />
          </div>
          <p className="mt-1.5 text-xs text-text-muted">
            {apiFormat === 'anthropic'
              ? '输入 Anthropic 模型名称，如 claude-sonnet-4-20250514、claude-haiku-4-20250514'
              : '输入模型名称，如 gpt-4o、deepseek-chat、llama3 等，LiteLLM 会自动路由'}
          </p>
        </section>

        <section>
          <h2 className="text-lg font-display font-semibold text-text-primary mb-3">
            API Base URL
          </h2>
          <input
            type="text"
            value={apiBase}
            onChange={(e) => {
              setApiBase(e.target.value)
              setTestStatus('idle')
            }}
            placeholder={formats[apiFormat]?.default_base || 'https://api.example.com/v1'}
            className="w-full px-4 py-3 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-neon-green transition-colors font-mono text-sm"
          />
          <p className="mt-1.5 text-xs text-text-muted">
            {apiFormat === 'anthropic'
              ? 'Anthropic API 端点地址，默认 https://api.anthropic.com'
              : 'OpenAI 兼容 API 端点地址，可指向任何兼容服务（Azure、代理网关、本地 Ollama 等）'}
          </p>
        </section>

        <section>
          <h2 className="text-lg font-display font-semibold text-text-primary mb-3">
            API Key
          </h2>
          <div className="relative">
            <input
              type={showApiKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value)
                setTestStatus('idle')
              }}
              placeholder="输入 API Key（Ollama 等本地服务可留空）"
              className="w-full px-4 py-3 pr-24 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-neon-green transition-colors font-mono text-sm"
            />
            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
              <button
                onClick={() => setShowApiKey(!showApiKey)}
                className="p-1.5 rounded-md hover:bg-bg-card-hover text-text-muted hover:text-text-secondary transition-colors"
              >
                {showApiKey ? (
                  <EyeOff className="w-4 h-4" strokeWidth={1.25} />
                ) : (
                  <Eye className="w-4 h-4" strokeWidth={1.25} />
                )}
              </button>
              <button
                onClick={handleTest}
                disabled={testStatus === 'testing' || !model.trim()}
                className={cn(
                  'flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all',
                  testStatus === 'testing' || !model.trim()
                    ? 'bg-bg-secondary text-text-muted cursor-not-allowed'
                    : 'bg-neon-green/10 text-neon-green hover:bg-neon-green/20'
                )}
              >
                {testStatus === 'testing' ? (
                  <Loader2 className="w-3 h-3 animate-spin" strokeWidth={1.25} />
                ) : (
                  <Wifi className="w-3 h-3" strokeWidth={1.25} />
                )}
                测试
              </button>
            </div>
          </div>
          <p className="mt-1.5 text-xs text-text-muted flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 shrink-0" strokeWidth={1.25} />
            API Key 仅存储在服务器内存中，页面刷新后需重新输入，不会持久化
          </p>
          {testStatus === 'success' && (
            <div className="mt-2 flex items-center gap-2 text-sm text-neon-green">
              <CheckCircle2 className="w-4 h-4" strokeWidth={1.25} />
              <span>连接成功</span>
              {testModel && (
                <span className="text-text-muted font-mono text-xs">({testModel})</span>
              )}
            </div>
          )}
          {testStatus === 'error' && (
            <div className="mt-2 flex items-start gap-2 text-sm text-severity-critical">
              <XCircle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.25} />
              <span className="break-all">{testError}</span>
            </div>
          )}
        </section>

        <section className="pt-4 border-t border-border">
          <div className="flex items-center gap-4">
            <button
              onClick={handleSave}
              disabled={saving || !model.trim()}
              className={cn(
                'flex items-center gap-2 px-8 py-3 rounded-lg font-bold transition-all',
                saving || !model.trim()
                  ? 'bg-bg-card text-text-muted cursor-not-allowed'
                  : 'bg-neon-green text-bg-primary hover:bg-neon-green-dim glow-green'
              )}
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.25} />
              ) : (
                <Save className="w-4 h-4" strokeWidth={1.25} />
              )}
              保存配置
            </button>

            {saveSuccess && (
              <span className="flex items-center gap-1.5 text-sm text-neon-green animate-fade-in">
                <CheckCircle2 className="w-4 h-4" strokeWidth={1.25} />
                已保存
              </span>
            )}
          </div>
        </section>

        <section className="rounded-xl border border-border bg-bg-card p-4">
          <h3 className="text-sm font-display font-semibold text-text-primary mb-2 flex items-center gap-2">
            <Zap className="w-4 h-4 text-cyan" strokeWidth={1.25} />
            LiteLLM 路由说明
          </h3>
          <div className="space-y-1.5 text-xs text-text-muted">
            <p>
              系统使用 LiteLLM 统一调用层，根据 API 范式自动添加路由前缀：
            </p>
            <div className="flex items-center gap-2 font-mono">
              <span className={cn('px-1.5 py-0.5 rounded text-[10px]', FORMAT_CONFIG[apiFormat].color.bg, FORMAT_CONFIG[apiFormat].color.text)}>
                {apiFormat === 'anthropic' ? 'anth' : 'openai'}
              </span>
              <ArrowRight className="w-3 h-3" strokeWidth={1.25} />
              <span>{apiFormat === 'anthropic' ? 'anthropic/' : 'openai/'}{model || '<model>'}</span>
            </div>
            <p>
              {apiFormat === 'anthropic'
                ? 'Anthropic 格式使用 x-api-key 头认证，调用 /v1/messages 端点'
                : 'OpenAI 兼容格式使用 Bearer Token 认证，调用 /v1/chat/completions 端点，兼容所有 OpenAI API 兼容服务'}
            </p>
          </div>
        </section>

        {/* ---------------- API Key (BYOK) —— v2 平台链路 ---------------- */}
        <section className="pt-8 border-t border-border">
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
                    <div className="text-sm text-text-primary font-medium">{k.provider}</div>
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

          {/* 新增 / 更新 Key */}
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <input
                type={showByokKey ? 'text' : 'password'}
                value={byokKey}
                onChange={(e) => setByokKey(e.target.value)}
                placeholder="sk-ant-…（输入 Anthropic API Key）"
                className="w-full px-4 py-3 pr-12 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-neon-green transition-colors font-mono text-sm"
              />
              <button
                onClick={() => setShowByokKey(!showByokKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md hover:bg-bg-card-hover text-text-muted hover:text-text-secondary transition-colors"
              >
                {showByokKey ? (
                  <EyeOff className="w-4 h-4" strokeWidth={1.25} />
                ) : (
                  <Eye className="w-4 h-4" strokeWidth={1.25} />
                )}
              </button>
            </div>
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
              {byokSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.25} />
              ) : (
                <Save className="w-4 h-4" strokeWidth={1.25} />
              )}
              保存 Key
            </button>
          </div>
          {byokSaved && (
            <p className="mt-2 flex items-center gap-1.5 text-sm text-neon-green animate-fade-in">
              <CheckCircle2 className="w-4 h-4" strokeWidth={1.25} />
              Key 已保存
            </p>
          )}

          {/* 24h 用量：quota 关闭时只报数字，不画配额条 */}
          {usage && (
            <div className="mt-6 rounded-xl border border-border bg-bg-card p-4">
              <h3 className="text-sm font-display font-semibold text-text-primary mb-3 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-cyan" strokeWidth={1.25} />
                近 24 小时用量
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
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
                  <div className="text-xs text-text-muted mb-1">总费用</div>
                  <div className="font-mono font-bold text-text-primary">
                    ${usage.cost_usd_total.toFixed(4)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-text-muted mb-1">其中服务器 Key</div>
                  <div className="font-mono font-bold text-text-secondary">
                    ${usage.cost_usd_on_server_key.toFixed(4)}
                  </div>
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
                  <p className="mt-1.5 text-xs text-text-muted">
                    配额窗口：{usage.window}
                  </p>
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      <div className="mt-8 pt-6 border-t border-border text-center">
        <Link
          to="/privacy"
          className="text-xs text-text-muted hover:text-text-secondary transition-colors"
        >
          隐私政策
        </Link>
      </div>
    </div>
  )
}
