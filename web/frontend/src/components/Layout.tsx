import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router'
import { cn } from '@/lib/utils'
import { Menu, X, User, LogOut, Settings, ChevronDown } from 'lucide-react'
import { useSessionStore } from '@/store/session-store'

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

const secondaryNavItems = [
  { path: '/evaluations', label: '评估报告' },
]

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const isCreatePage = location.pathname === '/review/new'
  // 对话评审是全高聊天界面，footer 会把页面顶出视口、抢滚动条
  const isAskPage = location.pathname === '/ask'
  const [menuOpen, setMenuOpen] = useState(false)
  // 账户下拉菜单——之前点邮箱按钮就直接退出登录，误触一下就被登出了
  const [accountOpen, setAccountOpen] = useState(false)
  const { config, identity, bootstrap, logout, sessionExpired, dismissSessionExpired } = useSessionStore()

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  // 切换路由时回到顶部——否则从很长的落地页点进 /ask 等页会停在下方，看不到顶栏
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])

  const loggedIn = !!identity && !identity.is_anonymous

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

  return (
    <div className="min-h-screen bg-bg-primary flex flex-col overflow-x-clip">
      <header className="sticky top-0 z-50 bg-bg-primary/60 backdrop-blur-xl border-b border-transparent shrink-0">
        <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-brand-primary/40 to-transparent" />
        <div className="max-w-[1600px] mx-auto px-4 h-16 flex items-center justify-between gap-4">
          {/* 品牌标志与营销落地页统一：金色星芒 + Audience（白）/ Lens（金） */}
          {/* 星芒与紧邻的 "Lens" 字样必须同色，否则品牌组合是两种金。
              实测 #B77E3B 在 bg-primary #0c0a08 上对比度 5.70:1（图形元素要求 3:1），
              余量充足，不需要提亮；#F9D67D 按 index.css 的定义只用于强调文字，不用于标志。 */}
          <Link to="/" className="flex items-center gap-2.5 group shrink-0">
            <svg
              viewBox="0 0 24 24"
              className="w-5 h-5 shrink-0 drop-shadow-[0_0_10px_rgba(183,126,59,0.5)]"
              aria-hidden="true"
            >
              <path
                d="M12 2l1.9 6.2L20 10l-6.1 1.8L12 18l-1.9-6.2L4 10l6.1-1.8L12 2z"
                fill="#B77E3B"
              />
            </svg>
            <span className="font-display font-bold text-lg whitespace-nowrap">
              <span className="text-text-primary">Audience</span>
              <span className="text-brand-primary">Lens</span>
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-2 min-w-0">
            <nav className="flex items-center gap-0.5 shrink-0">
              {navItems.map((item) => {
                const isActive = item.path === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.path)
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={cn(
                      'relative flex items-center px-2 py-2 rounded-lg text-sm whitespace-nowrap shrink-0 transition-all',
                      isActive
                        ? 'text-brand-primary'
                        : 'text-text-secondary hover:text-text-primary'
                    )}
                  >
                    <span>{item.label}</span>
                    <span
                      className={cn(
                        'absolute bottom-0 left-0 h-0.5 rounded-full bg-brand-primary transition-all duration-300',
                        isActive ? 'w-full' : 'w-0 group-hover:w-full'
                      )}
                    />
                  </Link>
                )
              })}
            </nav>

            <div className="hidden md:flex items-center gap-0.5 shrink-0 ml-1 pl-2 border-l border-border">
              {secondaryNavItems.map((item) => {
                const isActive = location.pathname.startsWith(item.path)
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={cn(
                      'relative flex items-center px-2 py-2 rounded-lg text-sm whitespace-nowrap shrink-0 transition-all',
                      isActive
                        ? 'text-cyan'
                        : 'text-text-secondary hover:text-text-primary'
                    )}
                  >
                    <span>{item.label}</span>
                  </Link>
                )
              })}
            </div>

            {!isCreatePage && (
              <Link
                to="/review/new"
                className="flex items-center px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap shrink-0 bg-brand-primary/10 text-brand-primary border border-brand-primary/30 hover:bg-brand-primary/20 hover:border-brand-primary/50 transition-all"
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
                    <div className="absolute right-0 top-full z-50 mt-1 w-56 rounded-xl border border-border bg-bg-card p-1.5 shadow-[0_8px_32px_rgba(0,0,0,0.5)]">
                      <p className="truncate px-3 py-2 text-xs text-text-muted">{identity?.email}</p>
                      <Link
                        to="/settings"
                        onClick={() => setAccountOpen(false)}
                        className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-text-secondary hover:bg-bg-card-hover hover:text-text-primary transition-colors"
                      >
                        <Settings className="w-4 h-4" strokeWidth={1.5} />
                        设置
                      </Link>
                      <button
                        onClick={handleLogout}
                        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-text-secondary hover:bg-severity-critical/10 hover:text-severity-critical transition-colors"
                      >
                        <LogOut className="w-4 h-4" strokeWidth={1.5} />
                        退出登录
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <Link
                to="/login"
                className="flex items-center px-3 py-2 rounded-lg text-sm whitespace-nowrap shrink-0 text-text-secondary hover:text-text-primary transition-all"
              >
                <span>登录</span>
              </Link>
            )}
          </div>

          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-card transition-colors"
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
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMenuOpen(false)}
          />
          <nav className="absolute left-0 top-0 bottom-0 w-64 bg-bg-primary border-r border-border shadow-2xl animate-fade-in flex flex-col pt-20 px-4">
            {navItems.map((item) => {
              const isActive = item.path === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.path)
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMenuOpen(false)}
                  className={cn(
                    'flex items-center px-4 py-3 rounded-lg text-sm transition-all mb-1',
                    isActive
                      ? 'bg-brand-primary/10 text-brand-primary border-l-2 border-brand-primary'
                      : 'text-text-secondary hover:text-text-primary hover:bg-bg-card'
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
                className="flex items-center px-4 py-3 mt-4 rounded-lg text-sm font-medium bg-brand-primary/10 text-brand-primary border border-brand-primary/30 hover:bg-brand-primary/20 transition-all"
              >
                <span>新建评审</span>
              </Link>
            )}

            {loggedIn ? (
              <div className="mt-2 border-t border-border pt-2">
                <p className="flex items-center gap-2 px-4 py-2 text-xs text-text-muted">
                  <User className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
                  <span className="truncate">{identity?.email}</span>
                </p>
                <button
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 px-4 py-3 rounded-lg text-sm text-text-secondary hover:bg-severity-critical/10 hover:text-severity-critical transition-all"
                >
                  <LogOut className="w-4 h-4" strokeWidth={1.5} />
                  退出登录
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                onClick={() => setMenuOpen(false)}
                className="flex items-center px-4 py-3 mt-2 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-bg-card transition-all"
              >
                <span>登录</span>
              </Link>
            )}

            <div className="mt-4 pt-3 border-t border-border">
              {secondaryNavItems.map((item) => {
                const isActive = location.pathname.startsWith(item.path)
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    onClick={() => setMenuOpen(false)}
                    className={cn(
                      'flex items-center px-4 py-3 rounded-lg text-sm transition-all mb-1',
                      isActive
                        ? 'bg-cyan/10 text-cyan border-l-2 border-cyan'
                        : 'text-text-secondary hover:text-text-primary hover:bg-bg-card'
                    )}
                  >
                    <span>{item.label}</span>
                  </Link>
                )
              })}
            </div>

            <Link
              to="/privacy"
              onClick={() => setMenuOpen(false)}
              className="flex items-center gap-3 px-4 py-3 mt-2 rounded-lg text-sm text-text-muted hover:text-text-secondary hover:bg-bg-card transition-all"
            >
              <span>隐私政策</span>
            </Link>
          </nav>
        </div>
      )}

      {sessionExpired && (
        // 过期 token 之前会静默退回匿名——用户只会莫名其妙发现自己"没登录了"，
        // 不知道发生了什么。这里显式说明，且不挡内容（可关闭）。
        <div className="flex items-center justify-center gap-3 border-b border-warm-orange/30 bg-warm-orange/10 px-4 py-2 text-sm text-warm-orange">
          <span>登录已过期，请重新登录</span>
          <Link to="/login" className="font-medium underline underline-offset-2 hover:text-gold-cream" onClick={dismissSessionExpired}>
            去登录
          </Link>
          <button onClick={dismissSessionExpired} className="ml-1 text-warm-orange/70 hover:text-warm-orange" aria-label="关闭提示">
            <X className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
        </div>
      )}

      <main className="flex-1">
        <Outlet />
      </main>

      {!isAskPage && (
      <footer className="relative border-t border-transparent py-8 shrink-0">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
        <div className="max-w-7xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex flex-col gap-1 items-center md:items-start">
            <span className="font-display font-bold text-sm">
              <span className="text-text-primary">Audience</span>
              <span className="text-brand-primary">Lens</span>
            </span>
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
