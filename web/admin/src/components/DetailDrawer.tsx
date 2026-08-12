import { useEffect } from 'react'
import { X } from 'lucide-react'

/** 通用详情抽屉——任务/评审的"下钻"复用这一个壳子，内容各自传 children。 */
export function DetailDrawer({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        /* 窄屏近乎全宽（留 1rem 露出遮罩提示可点外面关闭），sm 起限到 max-w-lg */
        className="h-full w-[calc(100vw-1rem)] max-w-lg overflow-y-auto border-l border-border bg-bg-secondary p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between gap-3">
          <h3 className="truncate font-mono text-sm font-semibold text-text-primary">{title}</h3>
          {/* aria-label：图标按钮没有文字，读屏与测试选择器都靠它 */}
          <button
            onClick={onClose}
            aria-label="关闭"
            className="shrink-0 rounded-md border border-border p-1.5 text-text-muted hover:border-border-hover hover:text-text-primary transition-colors"
          >
            <X className="h-4 w-4" strokeWidth={1.5} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function DetailField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="mb-3">
      <div className="font-mono text-[10px] uppercase tracking-wide text-text-muted">{label}</div>
      <div className="mt-0.5 text-sm text-text-primary break-words">{value}</div>
    </div>
  )
}

export function DetailJson({ label, value }: { label: string; value: unknown }) {
  if (value == null) return <DetailField label={label} value={<span className="text-text-muted">—</span>} />
  return (
    <div className="mb-3">
      <div className="font-mono text-[10px] uppercase tracking-wide text-text-muted">{label}</div>
      <pre className="mt-1 max-h-72 overflow-auto rounded-md border border-border bg-bg-primary p-3 font-mono text-[11px] text-text-secondary">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}
