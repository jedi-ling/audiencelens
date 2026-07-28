export function Pager({ total, offset, pageSize, onChange }: { total: number; offset: number; pageSize: number; onChange: (offset: number) => void }) {
  if (total <= pageSize) return null
  const page = Math.floor(offset / pageSize) + 1
  const pageCount = Math.ceil(total / pageSize)
  return (
    <div className="mt-3 flex items-center justify-between font-mono text-[10px] text-text-muted">
      <button
        onClick={() => onChange(Math.max(0, offset - pageSize))}
        disabled={offset === 0}
        className="rounded-md border border-border px-2 py-1 hover:border-brand-primary/40 hover:text-brand-primary transition-colors disabled:opacity-30"
      >
        上一页
      </button>
      <span>第 {page} / {pageCount} 页 · 共 {total} 条</span>
      <button
        onClick={() => onChange(offset + pageSize)}
        disabled={offset + pageSize >= total}
        className="rounded-md border border-border px-2 py-1 hover:border-brand-primary/40 hover:text-brand-primary transition-colors disabled:opacity-30"
      >
        下一页
      </button>
    </div>
  )
}
