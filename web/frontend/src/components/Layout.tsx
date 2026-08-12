import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router'
import { cn } from '@/lib/utils'
import { Menu, X, User, LogOut, Settings, ChevronDown } from 'lucide-react'
import { useSessionStore } from '@/store/session-store'
import { api } from '@/lib/apiClient'

const navItems = [
  { path: '/', label: '首页' },
  { path: '/ask', label: '对话评审' },
  { path: '/history', label: '评审历史' },
  { path: '/ledger', label: '判断复利' },
  { path: '/tutorial', label: '使用教程' },
  { path: '/skills', label: '技能中心' },
  { path: '/task-types', label: '任务类型' },
  { path: '/personas', label: '角色' },
  { path: '/plans', label: '定价' },
  { path: '/settings', label: '设置' },
]

/** 全页背景图映射：13 个路由循环复用 4 张高质量素材图。
 * 顺序按路由的"视觉重要度"排列——重要的页面（/ask、/review/new）放差异化图片，
 * 辅助页面循环复用。landing 走自己的视频背景，这里不管。
 * 数组里的索引决定哪张图被分配给哪个路由——按调用顺序循环取。 */
const BG_POOL = [
  '/images/bg-1.png',
  '/images/bg-2.png',
  '/images/bg-3.png',
  '/images/bg-4.png',
]

/** 哪些路由需要显示背景图——按路由顺序定义，自然循环复用 4 张图 */
const ROUTES_WITH_BG: readonly string[] = [
  '/ask',
  '/history',
  '/ledger',
  '/settings',
  '/tutorial',
  '/skills',
  '/task-types',
  '/personas',
  '/plans',
  '/login',
  '/register',
  '/review/new',
]

/** 根据路径返回对应的背景图 URL。
 * 路径不在白名单里就返回 undefined（不显示背景）。
 * 同样路径返回同一张图，避免切换路由时图突变。 */
function getBgForRoute(path: string): string | undefined {
  const idx = ROUTES_WITH_BG.indexOf(path)
  if (idx === -1) return undefined
  return BG_POOL[idx % BG_POOL.length]
}

// 这里曾有一条 { path: '/evaluations', label: '评估报告' } 的次级导航。
// 路由表里只有 /evaluations/:id，没有 /evaluations——点它会被 <Route path="*">
// 兜底静默 Navigate 回首页，用户以为自己点错了。
// 为什么是删掉而不是补一个列表页：评估是"某一次评审"的附属产物，后端只有
// GET /api/evaluations/{review_id}（按评审取），没有任何"列出我的全部评估"
// 的接口；凭空造个列表页只能拿空数组渲染成"你还没有评估"，那正是本仓最忌讳的
// "空数据装成正常结果"。真正的入口在报告页（ReportPage 的「查看评估」按钮），
// 那里才有 review id。要恢复导航项，得先有列表接口。

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const isCreatePage = location.pathname === '/review/new'
  // 对话评审是全高聊天界面，footer 会把页面顶出视口、抢滚动条
  const isAskPage = location.pathname === '/ask'
  const [menuOpen, setMenuOpen] = useState(false)
  // 账户下拉菜单——之前点邮箱按钮就直接退出登录，误触一下就被登出了
  const [accountOpen, setAccountOpen] = useState(false)
  // 按字段拆分订阅：原 useSessionStore() 整体订阅会让 store 任意状态变更
  // （如 usage 刷新、loading 切换）都触发整页重渲染。函数引用在 store 生命周期
  // 内稳定，单独订阅不会触发重渲染；identity/usage/sessionExpired 各自独立订阅，
  // 任一变化只重渲染真正依赖它的子树。
  const identity = useSessionStore((s) => s.identity)
  const usage = useSessionStore((s) => s.usage)
  const sessionExpired = useSessionStore((s) => s.sessionExpired)
  const bootstrap = useSessionStore((s) => s.bootstrap)
  const logout = useSessionStore((s) => s.logout)
  const dismissSessionExpired = useSessionStore((s) => s.dismissSessionExpired)
  // 重发验证邮件的四态。做成状态而不是 toast，是因为"已发送"这个信息要一直留在
  // 提示条上——用户去邮箱翻找、回来发现按钮恢复原样，会以为根本没发出去，于是
  // 反复点，把发信配额打满。
  const [resendState, setResendState] = useState<'idle' | 'sending' | 'sent' | 'failed'>('idle')

  // 换了账号（或登出再登入）必须重置这个状态。Layout 是根布局，路由切换与
  // 登出登入都不会卸载它，logout() 也只清 store 不碰组件内 state——实测：
  // A 点过重发后切成 B，B 的账户菜单显示 b@example.com，提示条却写着
  // "已发送，请查收"，而 B 从没收到过任何邮件。
  useEffect(() => {
    setResendState('idle')
  }, [identity?.user_id])

  const resendVerifyEmail = async () => {
    // 'sent' 不再直接拦死。原先这里 return 掉是想防止反复点把发信配额打满，
    // 但按钮同时又是 enabled 的（只在 'sending' 时禁用），于是变成一个
    // **点了毫无反应**的死控件：用户没收到邮件想再发一次，点不动、没有任何
    // 反馈，只能刷整页。防滥用交给后端限流（auth_mail 5 次/小时），
    // 前端这里只防重复提交。
    if (resendState === 'sending') return
    setResendState('sending')
    try {
      // 必须看 sent 字段，不能因为没抛异常就当成功：发信失败时接口是 200 + sent:false
      // （发信失败不该是 HTTP 错误——令牌已经签发了，请求本身没毛病）。
      const r = await api.sendVerifyEmail()
      setResendState(r.sent ? 'sent' : 'failed')
    } catch {
      setResendState('failed')
    }
  }

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  // 切换路由时回到顶部——否则从很长的落地页点进 /ask 等页会停在下方，看不到顶栏
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])

  const loggedIn = !!identity && !identity.is_anonymous
  // 评审历史/判断复利这两项要看"过往数据"。原来只在首页对未登录用户隐藏，
  // 结果首页和其它页面导航项不一致——用户从首页点进别的页面，导航突然多出
  // 两项，同样是一种困惑。改成全站统一：未登录状态下（不管在哪个页面）都
  // 不显示这两项，登录后（含匿名认领后转正）才出现，导航在任意路由间跳转
  // 都保持一致。/history 本身仍然可以用匿名 guest 身份直接访问（任务82的
  // 认领机制不受影响），只是不再出现在未登录时的导航条里。
  const visibleNavItems = loggedIn
    ? navItems
    : navItems.filter((item) => item.path !== '/history' && item.path !== '/ledger')

  const handleLogout = () => {
    setAccountOpen(false)
    setMenuOpen(false)
    logout()
    navigate('/')
  }

  // 路由切换时收起账户菜单，避免"悬浮菜单跟着新页面一起出现"的怪状态
  useEffect(() => {
    setAccountOpen(false)
  }, [location.pathname])

  // 抽屉打开时锁定 body 滚动，否则矮屏手机上手滑滚动的是被遮罩盖住的背景页面，
  // 抽屉本身内容又滚不动。Layout 几乎不会卸载，cleanup 以关闭抽屉为主要触发点。
  useEffect(() => {
    if (!menuOpen) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [menuOpen])

  // Esc 键关闭移动端菜单
  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menuOpen])

  return (
    <div className="min-h-screen flex flex-col overflow-x-clip relative bg-black" style={{ isolation: 'auto' }}>
      {/* 全页背景图：按路由切换，position:fixed 铺满视口，滚动时纹丝不动。
         只对非 landing 页生效——landing 有自己的视频+粒子背景，不要叠加。
         z-index -1 让它落在所有内容之下。 */}
      {location.pathname !== '/' && getBgForRoute(location.pathname) && (
        <img
          src={getBgForRoute(location.pathname)}
          alt=""
          aria-hidden="true"
          className="page-bg pointer-events-none"
        />
      )}
      <header className="sticky top-0 z-50 bg-black/90 backdrop-blur-xl backdrop-saturate-180 border-b border-white/[0.06] shrink-0">
        <div className="max-w-[1600px] mx-auto px-4 h-20 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-3 group shrink-0">
            <span className="logo-shine relative inline-flex h-16 w-[64px] shrink-0 items-center justify-center overflow-hidden">
              <img
                src="/images/logo-icon.png"
                className="h-16 w-auto shrink-0 object-contain"
                alt=""
              />
              <span className="logo-shine-sweep pointer-events-none absolute inset-0" aria-hidden="true" />
            </span>
            <span className="font-display font-semibold text-[17px] tracking-tight whitespace-nowrap">
              <span className="text-text-primary">Audience</span>
              <span className="text-brand-primary">Lens</span>
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-2 min-w-0">
            <nav className="flex items-center gap-0.5 shrink-0">
              {visibleNavItems.map((item) => {
                const isActive = item.path === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.path)
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={cn(
                      'relative flex items-center px-2.5 py-2 rounded-full text-[13px] whitespace-nowrap shrink-0 transition-all',
                      isActive
                        ? 'text-text-primary font-medium'
                        : 'text-text-secondary hover:text-text-primary'
                    )}
                  >
                    <span>{item.label}</span>
                    <span
                      className={cn(
                        'absolute bottom-0.5 left-1/2 -translate-x-1/2 h-[3px] rounded-full bg-brand-primary transition-all duration-300',
                        isActive ? 'w-4' : 'w-0'
                      )}
                    />
                  </Link>
                )
              })}
            </nav>

            {!isCreatePage && (
              <Link
                to="/review/new"
                className="flex items-center px-4 py-1.5 rounded-full text-[13px] font-medium whitespace-nowrap shrink-0 bg-brand-primary text-white hover:bg-brand-primary-dim transition-all"
              >
                <span>新建评审</span>
              </Link>
            )}

            {loggedIn ? (
              <div className="relative shrink-0">
                <button
                  onClick={() => setAccountOpen((v) => !v)}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm whitespace-nowrap text-text-secondary hover:text-text-primary transition-all"
                  aria-expanded={accountOpen}
                  aria-label="账户菜单"
                >
                  <User className="w-4 h-4" strokeWidth={1.5} />
                  <span className="max-w-[8rem] truncate">{identity?.email}</span>
                  <ChevronDown className={cn('w-3.5 h-3.5 transition-transform', accountOpen && 'rotate-180')} strokeWidth={1.5} />
                </button>
                {accountOpen && (
                  <>
                    {/* 点击空白处收起 */}
                    <div className="fixed inset-0 z-40" onClick={() => setAccountOpen(false)} />
                    <div className="absolute right-0 top-full z-50 mt-2 w-56 rounded-2xl border border-black/[0.06] bg-bg-card p-1.5 shadow-[0_12px_40px_rgba(0,0,0,0.12)]">
                      <p className="truncate px-3 py-2 text-xs text-text-muted">{identity?.email}</p>
                      <Link
                        to="/settings"
                        onClick={() => setAccountOpen(false)}
                        className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-text-secondary hover:bg-bg-card-hover hover:text-text-primary transition-colors"
                      >
                        <Settings className="w-4 h-4" strokeWidth={1.5} />
                        设置
                      </Link>
                      <button
                        onClick={handleLogout}
                        className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-text-secondary hover:bg-severity-critical/10 hover:text-severity-critical transition-colors"
                      >
                        <LogOut className="w-4 h-4" strokeWidth={1.5} />
                        退出登录
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <>
                {/* 未登录也有游客身份（CDK 兑换/匿名对话都在用），/settings 本身
                    已经处理了匿名态（配额、CDK 兑换、认领入口），给未登录用户
                    一个显式入口，不是只有一个孤零零的"登录"链接 */}
                <Link
                  to="/settings"
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm whitespace-nowrap shrink-0 text-text-secondary hover:text-text-primary transition-all"
                >
                  <User className="w-4 h-4" strokeWidth={1.5} />
                  <span>游客</span>
                </Link>
                <Link
                  to="/login"
                  className="flex items-center px-3 py-2 rounded-lg text-sm whitespace-nowrap shrink-0 text-text-secondary hover:text-text-primary transition-all"
                >
                  <span>登录</span>
                </Link>
              </>
            )}
          </div>

          <button
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="菜单"
            aria-expanded={menuOpen}
            aria-controls="mobile-menu"
            className="lg:hidden p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-card transition-colors"
          >
            {menuOpen ? (
              <X className="w-5 h-5" strokeWidth={1.25} />
            ) : (
              <Menu className="w-5 h-5" strokeWidth={1.25} />
            )}
          </button>
        </div>
      </header>

      {menuOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 bg-black/20 backdrop-blur-sm"
            aria-hidden="true"
            onClick={() => setMenuOpen(false)}
          />
          <nav
            id="mobile-menu"
            role="dialog"
            aria-modal="true"
            aria-label="导航菜单"
            className="absolute left-0 top-0 bottom-0 w-64 bg-bg-card border-r border-black/[0.06] shadow-2xl animate-fade-in flex flex-col pt-20 px-4"
          >
            {visibleNavItems.map((item) => {
              const isActive = item.path === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.path)
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMenuOpen(false)}
                  className={cn(
                    'flex items-center px-4 py-3 rounded-xl text-sm transition-all mb-1',
                    isActive
                      ? 'bg-brand-primary/10 text-brand-primary font-medium'
                      : 'text-text-secondary hover:text-text-primary hover:bg-bg-card-hover'
                  )}
                >
                  <span>{item.label}</span>
                </Link>
              )
            })}

            {!isCreatePage && (
              <Link
                to="/review/new"
                onClick={() => setMenuOpen(false)}
                className="flex items-center justify-center px-4 py-3 mt-4 rounded-full text-sm font-medium bg-brand-primary text-white hover:bg-brand-primary-dim transition-all"
              >
                <span>新建评审</span>
              </Link>
            )}

            {loggedIn ? (
              <div className="mt-2 border-t border-black/5 pt-2">
                <p className="flex items-center gap-2 px-4 py-2 text-xs text-text-muted">
                  <User className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
                  <span className="truncate">{identity?.email}</span>
                </p>
                <button
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 px-4 py-3 rounded-xl text-sm text-text-secondary hover:bg-severity-critical/10 hover:text-severity-critical transition-all"
                >
                  <LogOut className="w-4 h-4" strokeWidth={1.5} />
                  退出登录
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                onClick={() => setMenuOpen(false)}
                className="flex items-center px-4 py-3 mt-2 rounded-xl text-sm text-text-secondary hover:text-text-primary hover:bg-bg-card-hover transition-all"
              >
                <span>登录</span>
              </Link>
            )}

            <Link
              to="/privacy"
              onClick={() => setMenuOpen(false)}
              className="mt-4 flex shrink-0 items-center gap-3 border-t border-black/5 px-4 py-3 pt-5 rounded-xl text-sm text-text-muted hover:text-text-secondary hover:bg-bg-card-hover transition-all"
            >
              <span>隐私政策</span>
            </Link>
            <Link
              to="/terms"
              onClick={() => setMenuOpen(false)}
              className="flex shrink-0 items-center gap-3 px-4 py-3 rounded-xl text-sm text-text-muted hover:text-text-secondary hover:bg-bg-card-hover transition-all"
            >
              <span>服务条款</span>
            </Link>
          </nav>
        </div>
      )}

      {sessionExpired && (
        // 过期 token 之前会静默退回匿名——用户只会莫名其妙发现自己"没登录了"，
        // 不知道发生了什么。这里显式说明，且不挡内容（可关闭）。
        <div className="flex items-center justify-center gap-3 border-b border-warm-orange/30 bg-warm-orange/10 px-4 py-2 text-sm text-warm-orange">
          <span>登录已过期，请重新登录</span>
          <Link to="/login" className="font-medium underline underline-offset-2 hover:text-text-primary" onClick={dismissSessionExpired}>
            去登录
          </Link>
          <button onClick={dismissSessionExpired} className="ml-1 text-warm-orange/70 hover:text-warm-orange" aria-label="关闭提示">
            <X className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
        </div>
      )}

      {loggedIn && usage?.reviews_limit_capped_unverified && (
        // 未验证邮箱 → 每日次数被压到很低。不挡人使用（软拦），但必须让用户
        // 知道额度为什么这么少、以及怎么解锁——否则他看到的"限 1 次"会被当成
        // 产品本来就这么小气，而真正的动作（去邮箱点一下）是免费且立刻生效的。
        // 故意不给关闭按钮：关掉之后用户下次撞上限额仍然不知道原因。
        <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border-b border-cyan/30 bg-cyan/10 px-4 py-2 text-sm text-cyan">
          <span>
            邮箱尚未验证，每天只能评审 {usage.reviews_limit} 次。验证后解锁完整额度。
          </span>
          <button
            onClick={() => void resendVerifyEmail()}
            disabled={resendState === 'sending'}
            className="font-medium underline underline-offset-2 hover:text-text-primary disabled:opacity-60 disabled:no-underline"
          >
            {resendState === 'sending'
              ? '发送中…'
              : resendState === 'sent'
                ? '已发送，请查收（含垃圾箱）·点此再发一次'
                : resendState === 'failed'
                  ? '发送失败，点此重试'
                  : '重新发送验证邮件'}
          </button>
        </div>
      )}

      <main className="flex-1 relative z-[1]">
        <Outlet />
      </main>

      {!isAskPage && (
      <footer className="relative z-[2] bg-black border-t border-white/[0.06] py-10 shrink-0">
        <div className="max-w-7xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex flex-col gap-1 items-center md:items-start">
            <div className="flex items-center gap-2">
              <img
                src="/images/logo-icon.png"
                className="h-8 w-auto shrink-0 object-contain"
                alt=""
              />
              <span className="font-display font-semibold text-sm tracking-tight">
                <span className="text-text-primary">Audience</span>
                <span className="text-brand-primary">Lens</span>
              </span>
            </div>
            <span className="text-xs text-text-muted">
              多代理合成用户评审系统
            </span>
          </div>

          <nav className="hidden md:flex items-center gap-6">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className="text-xs text-text-muted hover:text-text-secondary transition-colors"
              >
                {item.label}
              </Link>
            ))}
            <Link
              to="/privacy"
              className="text-xs text-text-muted hover:text-text-secondary transition-colors"
            >
              隐私政策
            </Link>
            <Link
              to="/terms"
              className="text-xs text-text-muted hover:text-text-secondary transition-colors"
            >
              服务条款
            </Link>
          </nav>

          <div className="flex flex-col items-center md:items-end gap-0.5">
            <span className="text-xs text-text-muted font-display">
              v1.0.0
            </span>
            <span className="text-[10px] text-text-muted">
              © 2026 AudienceLens
            </span>
          </div>
        </div>
      </footer>
      )}
    </div>
  )
}
