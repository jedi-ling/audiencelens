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
  const { config, identity, usage, bootstrap, logout, sessionExpired, dismissSessionExpired } = useSessionStore()
  // 重发验证邮件的四态。做成状态而不是 toast，是因为"已发送"这个信息要一直留在
  // 提示条上——用户去邮箱翻找、回来发现按钮恢复原样，会以为根本没发出去，于是
  // 反复点，把发信配额打满。
  const [resendState, setResendState] = useState<'idle' | 'sending' | 'sent' | 'failed'>('idle')

  const resendVerifyEmail = async () => {
    if (resendState === 'sending' || resendState === 'sent') return
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
      <header className="sticky top-0 z-50 bg-bg-primary/70 backdrop-blur-xl backdrop-saturate-150 border-b border-black/5 shrink-0">
        <div className="max-w-[1600px] mx-auto px-4 h-14 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2.5 group shrink-0">
            <svg
              viewBox="0 0 24 24"
              className="w-5 h-5 shrink-0"
              aria-hidden="true"
            >
              <path
                d="M12 2l1.9 6.2L20 10l-6.1 1.8L12 18l-1.9-6.2L4 10l6.1-1.8L12 2z"
                fill="#0071e3"
              />
            </svg>
            <span className="font-display font-semibold text-[17px] tracking-tight whitespace-nowrap">
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
                    <div className="absolute right-0 top-full z-50 mt-2 w-56 rounded-2xl border border-black/5 bg-white p-1.5 shadow-[0_12px_40px_rgba(0,0,0,0.12)]">
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
            className="absolute inset-0 bg-black/20 backdrop-blur-sm"
            onClick={() => setMenuOpen(false)}
          />
          <nav className="absolute left-0 top-0 bottom-0 w-64 bg-white border-r border-black/5 shadow-2xl animate-fade-in flex flex-col pt-20 px-4">
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
              className="mt-4 flex items-center gap-3 border-t border-black/5 px-4 py-3 pt-5 rounded-xl text-sm text-text-muted hover:text-text-secondary hover:bg-bg-card-hover transition-all"
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
                ? '已发送，请查收（含垃圾箱）'
                : resendState === 'failed'
                  ? '发送失败，点此重试'
                  : '重新发送验证邮件'}
          </button>
        </div>
      )}

      <main className="flex-1">
        <Outlet />
      </main>

      {!isAskPage && (
      <footer className="relative border-t border-black/5 py-8 shrink-0 bg-bg-secondary">
        <div className="max-w-7xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex flex-col gap-1 items-center md:items-start">
            <span className="font-display font-semibold text-sm tracking-tight">
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
