import { useCallback, useEffect, useState } from 'react'
import { Lock, Wifi, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import { OPENAI_COMPATIBLE_PRESETS } from '@/lib/types'
import type { AdminServerKeyStatus, TestConnectionResult } from '@/lib/types'

type Provider = 'anthropic' | 'openai_compatible'
type TestStatus = 'idle' | 'testing' | 'success' | 'error'

export function ServerKeyPanel() {
  const [status, setStatus] = useState<AdminServerKeyStatus | null>(null)
  const [provider, setProvider] = useState<Provider>('anthropic')
  const [model, setModel] = useState('')
  const [apiBase, setApiBase] = useState('')
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [testStatus, setTestStatus] = useState<TestStatus>('idle')
  const [testResult, setTestResult] = useState<TestConnectionResult | null>(null)

  const load = useCallback(async (p: Provider) => {
    try {
      setStatus(await adminApi.serverKeyStatus(p))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load(provider)
  }, [load, provider])

  const resetTest = () => {
    setTestStatus('idle')
    setTestResult(null)
  }

  const switchProvider = (p: Provider) => {
    setProvider(p)
    setModel('')
    setApiBase('')
    resetTest()
  }

  const applyPreset = (preset: (typeof OPENAI_COMPATIBLE_PRESETS)[number]) => {
    setModel(preset.model)
    setApiBase(preset.api_base)
    resetTest()
  }

  const save = async () => {
    if (!input.trim()) return
    if (provider === 'openai_compatible' && !model.trim()) {
      setError('OpenAI 兼容格式需要填写模型名称')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await adminApi.setServerKey(input.trim(), provider, {
        model: model.trim() || undefined,
        apiBase: apiBase.trim() || undefined,
      })
      setInput('')
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      await load(provider)
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
      await adminApi.deleteServerKey(provider)
      resetTest()
      await load(provider)
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败')
    } finally {
      setBusy(false)
    }
  }

  const test = async () => {
    setTestStatus('testing')
    setTestResult(null)
    try {
      const result = await adminApi.testServerKey(provider)
      setTestResult(result)
      setTestStatus(result.connected ? 'success' : 'error')
    } catch (e) {
      setTestResult({ connected: false, error: e instanceof Error ? e.message : '连接失败' })
      setTestStatus('error')
    }
  }

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
        <Lock className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
        平台级 API Key
        <span className="font-mono text-[10px] font-normal text-text-muted">managed/hybrid 模式垫付用</span>
      </h2>
      <p className="mt-1 text-xs text-text-muted">
        托管模式下服务端垫付的 key。支持 Anthropic 原生或任意 OpenAI 兼容服务（DeepSeek / Kimi / 通义千问 / 智谱 GLM /
        Ollama 等）。测试按钮走的是评审真正会用的链路（runner.llm_client），不是摆设。
      </p>

      <div className="mt-4 flex gap-2 font-mono text-xs">
        {(['anthropic', 'openai_compatible'] as Provider[]).map((p) => (
          <button
            key={p}
            onClick={() => switchProvider(p)}
            className={`rounded-md px-3 py-1.5 transition-colors ${
              provider === p
                ? 'bg-brand-primary/15 text-brand-primary border border-brand-primary/40'
                : 'bg-bg-secondary text-text-muted border border-border hover:text-text-secondary'
            }`}
          >
            {p === 'anthropic' ? 'Anthropic 原生' : 'OpenAI 兼容 / 国产模型'}
          </button>
        ))}
      </div>

      {error && <p className="mt-3 font-mono text-xs text-severity-critical">{error}</p>}

      {status?.configured ? (
        <div className="mt-4 flex items-center gap-3 rounded-lg border border-brand-primary/30 bg-bg-primary px-4 py-3">
          <span className="font-mono text-sm text-brand-primary">{status.key?.masked}</span>
          {status.key?.model && <span className="font-mono text-xs text-text-secondary">{status.key.model}</span>}
          <span className="ml-auto font-mono text-[10px] text-text-muted">
            {status.key?.last_used_at ? `最近使用 ${new Date(status.key.last_used_at).toLocaleString()}` : '尚未使用'}
          </span>
          <button
            onClick={() => void test()}
            disabled={testStatus === 'testing'}
            className="flex shrink-0 items-center gap-1 rounded-md bg-cyan/10 px-2.5 py-1 font-mono text-xs text-cyan hover:bg-cyan/20 transition-colors disabled:opacity-50"
          >
            {testStatus === 'testing' ? (
              <Loader2 className="h-3 w-3 animate-spin" strokeWidth={1.5} />
            ) : (
              <Wifi className="h-3 w-3" strokeWidth={1.5} />
            )}
            测试
          </button>
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

      {testStatus === 'success' && testResult && (
        <div className="mt-2 flex items-center gap-2 font-mono text-xs text-brand-primary">
          <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={1.5} />
          <span>连接成功</span>
          {testResult.model && <span className="text-text-muted">({testResult.model})</span>}
          {testResult.sample && <span className="text-text-muted truncate max-w-[20rem]">回复：{testResult.sample}</span>}
        </div>
      )}
      {testStatus === 'error' && (
        <div className="mt-2 flex items-start gap-2 font-mono text-xs text-severity-critical">
          <XCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" strokeWidth={1.5} />
          <span className="break-all">{testResult?.error || '连接失败'}</span>
        </div>
      )}

      {provider === 'openai_compatible' && (
        <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-3">
          {OPENAI_COMPATIBLE_PRESETS.map((preset) => (
            <button
              key={preset.id}
              onClick={() => applyPreset(preset)}
              className={`rounded-lg border px-3 py-2 text-left font-mono text-[11px] transition-colors ${
                model === preset.model && apiBase === preset.api_base
                  ? 'border-cyan/50 bg-cyan/5 text-text-primary'
                  : 'border-border bg-bg-secondary text-text-muted hover:text-text-secondary'
              }`}
            >
              <div className="truncate">{preset.name}</div>
              <div className="truncate text-text-muted">{preset.model}</div>
            </button>
          ))}
        </div>
      )}

      {/* 模型 ID + API Base：两个服务商都能填。anthropic 留空则按人格分级自动选型，
          但也支持指定具体模型、或填第三方中转/代理地址——不是只有 OpenAI 兼容才有这种场景。 */}
      <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
        <input
          type="text"
          value={model}
          onChange={(e) => {
            setModel(e.target.value)
            resetTest()
          }}
          placeholder={
            provider === 'anthropic'
              ? '模型 ID，留空自动按人格分级选型'
              : '模型名称，如 deepseek-v4-pro'
          }
          className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 font-mono text-sm text-text-primary placeholder-text-muted outline-none focus:border-cyan transition-colors"
        />
        <input
          type="text"
          value={apiBase}
          onChange={(e) => {
            setApiBase(e.target.value)
            resetTest()
          }}
          placeholder={
            provider === 'anthropic'
              ? 'API Base，留空用官方地址，或填第三方中转'
              : 'API Base，如 https://api.deepseek.com'
          }
          className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 font-mono text-sm text-text-primary placeholder-text-muted outline-none focus:border-cyan transition-colors"
        />
      </div>

      <div className="mt-3 flex gap-2">
        <input
          type="password"
          value={input}
          onChange={(e) => {
            setInput(e.target.value)
            resetTest()
          }}
          placeholder={provider === 'anthropic' ? 'sk-ant-…（轮换或首次设置）' : '对应服务商的 API Key（Ollama 本地可留空）'}
          className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 font-mono text-sm text-text-primary placeholder-text-muted outline-none focus:border-brand-primary transition-colors"
        />
        <button
          onClick={() => void save()}
          disabled={busy || !input.trim()}
          className="shrink-0 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-bg-primary hover:bg-brand-primary-dim transition-colors disabled:opacity-50"
        >
          保存
        </button>
      </div>
      {saved && <p className="mt-2 font-mono text-xs text-brand-primary">已保存</p>}
    </section>
  )
}
