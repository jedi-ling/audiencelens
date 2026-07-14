import { useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router'
import { cn } from '@/lib/utils'
import { Eye, Plus, Users, Home, BookOpen, Settings, Menu, X, Layers, Sparkles, FlaskConical, MessageSquare, TrendingUp } from 'lucide-react'

const navItems = [
  { path: '/', label: '首页', icon: Home },
  { path: '/ask', label: '对话评审', icon: MessageSquare },
  { path: '/ledger', label: '判断复利', icon: TrendingUp },
  { path: '/tutorial', label: '使用教程', icon: BookOpen },
  { path: '/skills', label: '技能中心', icon: Sparkles },
  { path: '/task-types', label: '任务类型', icon: Layers },
  { path: '/personas', label: '角色', icon: Users },
  { path: '/settings', label: '设置', icon: Settings },
]

const secondaryNavItems = [
  { path: '/evaluations', label: '评估报告', icon: FlaskConical },
]

export default function Layout() {
  const location = useLocation()
  const isCreatePage = location.pathname === '/review/new'
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="min-h-screen bg-bg-primary flex flex-col overflow-x-hidden">
      <header className="sticky top-0 z-50 bg-bg-primary/60 backdrop-blur-xl border-b border-transparent shrink-0">
        <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-neon-green/40 to-transparent" />
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="relative">
              <Eye className="w-6 h-6 text-neon-green group-hover:text-glow-green transition-colors" strokeWidth={1.25} />
              <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-neon-green shadow-[0_0_6px_rgba(0,255,136,0.8)] animate-pulse" />
            </div>
            <span className="font-display font-bold text-lg text-neon-green text-glow-green">
              AudienceLens
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-3">
            <nav className="flex items-center gap-1">
              {navItems.map((item) => {
                const Icon = item.icon
                const isActive = item.path === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.path)
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={cn(
                      'relative flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm transition-all',
                      isActive
                        ? 'text-neon-green'
                        : 'text-text-secondary hover:text-text-primary'
                    )}
                  >
                    <Icon className="w-4 h-4" strokeWidth={1.25} />
                    <span>{item.label}</span>
                    <span
                      className={cn(
                        'absolute bottom-0 left-0 h-0.5 rounded-full bg-neon-green transition-all duration-300',
                        isActive ? 'w-full' : 'w-0 group-hover:w-full'
                      )}
                    />
                  </Link>
                )
              })}
            </nav>

            <div className="hidden md:flex items-center gap-1 ml-2 pl-2 border-l border-border">
              {secondaryNavItems.map((item) => {
                const Icon = item.icon
                const isActive = location.pathname.startsWith(item.path)
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={cn(
                      'relative flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm transition-all',
                      isActive
                        ? 'text-cyan'
                        : 'text-text-secondary hover:text-text-primary'
                    )}
                  >
                    <Icon className="w-4 h-4" strokeWidth={1.25} />
                    <span>{item.label}</span>
                  </Link>
                )
              })}
            </div>

            {!isCreatePage && (
              <Link
                to="/review/new"
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-neon-green/10 text-neon-green border border-neon-green/30 hover:bg-neon-green/20 hover:border-neon-green/50 transition-all"
              >
                <Plus className="w-4 h-4" strokeWidth={1.25} />
                <span>新建评审</span>
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
              const Icon = item.icon
              const isActive = item.path === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.path)
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMenuOpen(false)}
                  className={cn(
                    'flex items-center gap-3 px-4 py-3 rounded-lg text-sm transition-all mb-1',
                    isActive
                      ? 'bg-neon-green/10 text-neon-green border-l-2 border-neon-green'
                      : 'text-text-secondary hover:text-text-primary hover:bg-bg-card'
                  )}
                >
                  <Icon className="w-5 h-5" strokeWidth={1.25} />
                  <span>{item.label}</span>
                </Link>
              )
            })}

            {!isCreatePage && (
              <Link
                to="/review/new"
                onClick={() => setMenuOpen(false)}
                className="flex items-center gap-3 px-4 py-3 mt-4 rounded-lg text-sm font-medium bg-neon-green/10 text-neon-green border border-neon-green/30 hover:bg-neon-green/20 transition-all"
              >
                <Plus className="w-5 h-5" strokeWidth={1.25} />
                <span>新建评审</span>
              </Link>
            )}

            <div className="mt-4 pt-3 border-t border-border">
              {secondaryNavItems.map((item) => {
                const Icon = item.icon
                const isActive = location.pathname.startsWith(item.path)
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    onClick={() => setMenuOpen(false)}
                    className={cn(
                      'flex items-center gap-3 px-4 py-3 rounded-lg text-sm transition-all mb-1',
                      isActive
                        ? 'bg-cyan/10 text-cyan border-l-2 border-cyan'
                        : 'text-text-secondary hover:text-text-primary hover:bg-bg-card'
                    )}
                  >
                    <Icon className="w-5 h-5" strokeWidth={1.25} />
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

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="relative border-t border-transparent py-8 shrink-0">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
        <div className="max-w-7xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex flex-col gap-1 items-center md:items-start">
            <span className="font-display font-bold text-sm text-neon-green">
              AudienceLens
            </span>
            <span className="text-xs text-text-muted">
              多代理合成玩家评审系统
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
    </div>
  )
}
