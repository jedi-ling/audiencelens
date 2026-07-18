import { X } from 'lucide-react'

/** 通用详情抽屉——任务/评审的"下钻"复用这一个壳子，内容各自传 children。 */
export function DetailDrawer({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60" onClick={onClose}>
      <div
        className="h-full w-full max-w-lg overflow-y-auto border-l border-border bg-bg-secondary p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-mono text-sm font-semibold text-text-primary">{title}</h3>
          <button onClick={onClose} className="rounded-md p-1 text-text-muted hover:text-text-primary transition-colors">
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
