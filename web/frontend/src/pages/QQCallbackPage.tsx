/**
 * QQ 登录回调落地页（前端侧，路由 /auth/qq）。
 *
 * 链路全貌：
 *   1. 用户点「QQ 登录」 → 整页跳到 /api/auth/qq/authorize
 *   2. 后端 302 到腾讯授权页
 *   3. 腾讯回调 **后端** /api/auth/qq/callback（这是 QQ 互联后台登记的那个地址）
 *   4. 后端换 token→openid→找到/创建账号，再 302 到这里，带一个**一次性交接码**
 *   5. 本页把交接码 POST 给后端换成真正的会话 JWT
 *
 * 为什么要第 5 步、不让后端直接把 JWT 拼进 URL：JWT 有效期 7 天，拼进 URL 就会
 * 留在浏览器历史、Referer 和中间层日志里。交接码 30 秒过期、用一次即废。
 *
 * 这一页没有可交互内容，只有三种状态：兑换中 / 失败（给重试入口）/ 成功（自动跳走）。
 */
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router'
import { Loader2, AlertTriangle } from 'lucide-react'
import { api, setToken, claimPendingReviews } from '@/lib/apiClient'
import { useSessionStore } from '@/store/session-store'
import { tApiError } from '@/i18n/api-error'
import { t } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'

export default function QQCallbackPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const bootstrap = useSessionStore((s) => s.bootstrap)
  // "地址栏里压根没有 code" 这一种在首帧就能判定，所以用惰性初值直接算出来，
  // 不在 effect 里 setState：那样会先渲染一帧"正在登录"再跳成错误页，
  // 也正是 React 19 set-state-in-effect 规则点名的写法。
  // 兑换失败那一种只能等网络回来，仍然走 setError。
  const [error, setError] = useState<string | null>(() =>
    params.get('code') ? null : t('page.qq_callback.missing.error')
  )
  useDocumentTitle('page.qq_callback.meta.title')

  // React 18 严格模式下 effect 会跑两次；交接码是**一次性**的，
  // 第二次兑换必然失败并把成功的那次覆盖成错误页。用 ref 挡住重入。
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true

    const code = params.get('code')
    // 没有 code 的情况首帧已经在上面的初值里判定过了，这里只需要不发请求
    if (!code) return

    void (async () => {
      try {
        const result = await api.qqExchange(code)
        setToken(result.token)
        // 与注册/登录/CDK 兑换同一套收尾：把登录前匿名跑的评审认领过来，
        // 否则用户登录完回头找刚才那份报告会发现"评审不存在"。
        await claimPendingReviews().catch(() => {})
        await bootstrap()
        navigate('/ask', { replace: true })
      } catch (e) {
        setError(tApiError(e, 'page.qq_callback.failed.error'))
      }
    })()
  }, [params, navigate, bootstrap])

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center px-4 text-center">
      {error ? (
        <>
          <AlertTriangle className="h-8 w-8 text-severity-critical" strokeWidth={1.5} />
          <p className="mt-3 text-sm font-medium text-text-primary">
            {t('page.qq_callback.failed.title')}
          </p>
          <p className="mt-1.5 text-xs leading-relaxed text-text-secondary">{error}</p>
          <Link
            to="/login"
            className="mt-5 rounded-lg border border-border px-4 py-2 text-sm text-text-primary transition-colors hover:border-brand-primary/40"
          >
            {t('page.qq_callback.retry.cta')}
          </Link>
        </>
      ) : (
        <>
          <Loader2 className="h-6 w-6 animate-spin text-brand-primary" strokeWidth={1.5} />
          <p className="mt-3 text-sm text-text-secondary">{t('page.qq_callback.pending.label')}</p>
        </>
      )}
    </div>
  )
}
