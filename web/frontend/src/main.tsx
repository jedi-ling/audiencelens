import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { initI18n } from '@/i18n/locale'
import I18nBootFailure from '@/components/I18nBootFailure'

/**
 * 语料先到位再渲染。
 *
 * 这样 t() 得以保持**同步函数**——全站不需要 Suspense、不需要 async t、
 * 页面也不需要处理"文案还没到"的中间态。代价是首屏多一次 modulepreload，
 * 而 Vite build 会自动把 per-locale 分包注入 <link rel=modulepreload>，
 * 实际上抵消掉这一次往返。
 *
 * 两份语料合计约 2000 条，静态全量打包会让中文用户白背一份英文，所以是动态 import。
 */
initI18n().then(
  () => {
    createRoot(document.getElementById('root')!).render(
      <StrictMode>
        <App />
      </StrictMode>,
    )
  },
  (err: unknown) => {
    console.error('[i18n] 语料加载失败，应用未启动', err)
    createRoot(document.getElementById('root')!).render(<I18nBootFailure />)
  },
)
