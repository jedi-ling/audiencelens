/**
 * 语料加载失败时的错误屏。
 *
 * ⚠ **此处刻意不走 i18n。** 走了就是白屏套白屏：i18n 都没起来，
 * 用来解释"i18n 没起来"的那句话自然也取不到。所以硬编码**双语**字面量——
 * 这时候我们连用户想看哪种语言都不知道，两句都摆出来是唯一诚实的做法。
 *
 * 同样规矩适用于 App.tsx 的 ChunkErrorBoundary 与 PageLoading，
 * 那两处的注释已经为这条立过先例（"发版后旧 chunk 404 会直接白屏，必须有边界兜底"）。
 *
 * 样式全部内联：index.css 已经 import 了，但如果失败原因正是网络问题，
 * 内联样式至少保证这块东西是可读的，不是一堆左对齐的黑字。
 */
export default function I18nBootFailure() {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.75rem',
        padding: '2rem',
        textAlign: 'center',
        fontFamily: 'system-ui, sans-serif',
        color: '#9aa0a6',
        background: '#0b0b0c',
      }}
    >
      <p style={{ fontSize: '14px' }}>界面文案加载失败，可能是刚发布了新版本。</p>
      <p style={{ fontSize: '14px' }}>Could not load interface text — a new version may have just shipped.</p>
      <button
        onClick={() => window.location.reload()}
        style={{
          marginTop: '0.5rem',
          padding: '0.5rem 1rem',
          borderRadius: '0.5rem',
          border: '1px solid rgba(255,255,255,0.2)',
          background: 'transparent',
          color: 'inherit',
          fontSize: '14px',
          cursor: 'pointer',
        }}
      >
        刷新 / Reload
      </button>
    </div>
  )
}
