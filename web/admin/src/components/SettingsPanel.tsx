import { useCallback, useEffect, useState } from 'react'
import { Sliders } from 'lucide-react'
import { adminApi } from '@/lib/adminClient'
import type { AdminSettingRow } from '@/lib/types'
import { PanelShell, PanelError, PanelEmpty, PanelLoading } from './panel'

export function SettingsPanel() {
  const [rows, setRows] = useState<AdminSettingRow[]>([])
  const [loaded, setLoaded] = useState(false)
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setRows((await adminApi.listSettings()).settings)
      setLoaded(true)
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
    <PanelShell icon={Sliders} title="运行时配置" hint="改动无需重启">
      <PanelError>{error}</PanelError>
      {!loaded && !error && <PanelLoading />}
      <div className="mt-4 divide-y divide-border">
        {loaded && rows.length === 0 && <PanelEmpty />}
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
                className="shrink-0 rounded-md border border-border px-2 py-1 font-mono text-[10px] text-text-muted hover:border-brand-primary/40 hover:text-brand-primary transition-colors disabled:opacity-50"
              >
                重置
              </button>
            )}
          </div>
        ))}
      </div>
    </PanelShell>
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
        aria-label={row.label}
        className="h-4 w-4 shrink-0 accent-brand-primary"
      />
    )
  }
  if (row.choices) {
    return (
      <select
        value={String(row.effective_value)}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="shrink-0 rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none focus:border-brand-primary"
      >
        {row.choices.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>
    )
  }
  return (
    <input
      key={`${row.key}-${row.effective_value}`}
      type="number"
      defaultValue={String(row.effective_value)}
      disabled={disabled}
      onBlur={(e) => {
        const v = row.type === 'int' ? parseInt(e.target.value, 10) : parseFloat(e.target.value)
        if (!Number.isNaN(v)) onChange(v)
      }}
      className="w-24 shrink-0 rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-xs text-text-primary outline-none focus:border-brand-primary"
    />
  )
}
