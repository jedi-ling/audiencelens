import { useEffect } from 'react'
import { Link } from 'react-router'
import { useReviewStore } from '@/store/review-store'
import { Zap, BarChart3, Share2, ArrowRight, Clock, CheckCircle2, Loader2, ChevronDown, Users, Package, Layers } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Review } from '@/lib/mock-data'
import { SKILLS } from '@/lib/mock-data'

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-4 h-4 text-text-muted" strokeWidth={1.25} />,
  running: <Loader2 className="w-4 h-4 text-cyan animate-spin" strokeWidth={1.25} />,
  completed: <CheckCircle2 className="w-4 h-4 text-neon-green" strokeWidth={1.25} />,
  failed: <CheckCircle2 className="w-4 h-4 text-severity-critical" strokeWidth={1.25} />,
}

const statusLabels: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

import { TASK_TYPES } from '@/lib/mock-data'

const taskTypeNames: Record<string, string> = Object.fromEntries(
  TASK_TYPES.map((t) => [t.id, t.name])
)

function ReviewRow({ review }: { review: Review }) {
  return (
    <Link
      to={review.status === 'completed' ? `/review/${review.id}/report` : `/review/${review.id}`}
      className="flex items-center gap-3 md:gap-4 px-4 py-3 rounded-lg bg-bg-card hover:bg-bg-card-hover border border-border hover:border-neon-green/30 transition-all group relative overflow-hidden"
    >
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none">
        <div className="absolute inset-0 bg-gradient-to-r from-neon-green/5 via-transparent to-transparent" />
      </div>
      <div className="shrink-0 relative z-10">{statusIcons[review.status]}</div>
      <div className="flex-1 min-w-0 relative z-10">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary truncate">{review.target_title}</span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-bg-secondary text-text-secondary hidden sm:inline">
            {taskTypeNames[review.task_type] ?? review.task_type}
          </span>
        </div>
        <span className="text-xs text-text-muted">{statusLabels[review.status]}</span>
      </div>
      <div className="shrink-0 text-xs text-text-muted font-mono relative z-10 hidden sm:block">
        {new Date(review.created_at).toLocaleDateString('zh-CN')}
      </div>
      <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-neon-green transition-colors relative z-10" strokeWidth={1.25} />
    </Link>
  )
}

const stats = [
  { value: '4', label: '评审技能', icon: Zap },
  { value: '43', label: '角色', icon: Users },
  { value: '7', label: '角色包', icon: Package },
  { value: '14', label: '任务类型', icon: Layers },
]

const features = [
  {
    icon: Zap,
    title: '零门槛启动',
    description: '无需招募真实玩家，选择 Persona Pack 即可启动评审。几分钟内获得多维度反馈。',
    stat: '5 分钟内完成首轮评审',
    color: 'neon-green',
  },
  {
    icon: BarChart3,
    title: '可视化洞察',
    description: '雷达图、仪表盘、立场分布图，评审结果一目了然。支持 Persona 对比与校准指标追踪。',
    stat: '12 维度数据可视化',
    color: 'cyan',
  },
  {
    icon: Share2,
    title: '可分享报告',
    description: '导出 JSON 或 Markdown 格式报告，轻松分享给团队。每个结论都有证据链支撑。',
    stat: '100% 可追溯证据链',
    color: 'warm-orange',
  },
]

export default function HomePage() {
  const reviews = useReviewStore((s) => s.reviews)
  const initReviews = useReviewStore((s) => s.initReviews)

  useEffect(() => {
    initReviews()
  }, [initReviews])

  return (
    <div>
      <section className="relative min-h-[calc(100vh-4rem)] md:min-h-[calc(100vh-4rem)] flex items-center justify-center overflow-hidden">
        {/* 仪器风背景：冷色渐层 + 发丝级蓝图网格，取代赛博粒子场 */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute inset-0 bg-gradient-to-b from-bg-secondary/60 via-bg-primary to-bg-primary" />
          <div
            className="absolute inset-0 opacity-[0.4]"
            style={{
              backgroundImage:
                'linear-gradient(var(--color-border) 1px, transparent 1px), linear-gradient(90deg, var(--color-border) 1px, transparent 1px)',
              backgroundSize: '48px 48px',
              maskImage: 'radial-gradient(ellipse 65% 55% at 50% 42%, black, transparent 78%)',
              WebkitMaskImage: 'radial-gradient(ellipse 65% 55% at 50% 42%, black, transparent 78%)',
            }}
          />
        </div>

        <div className="relative z-10 text-center px-4 max-w-5xl mx-auto">
          <h1
            className="font-display text-4xl sm:text-5xl md:text-9xl font-bold text-gradient-green mb-4 md:mb-6 tracking-tight animate-hero-text"
            style={{ animationDelay: '0.1s' }}
          >
            AudienceLens
          </h1>

          <p
            className="text-lg sm:text-xl md:text-3xl text-cyan tracking-[0.1em] md:tracking-[0.15em] mb-3 md:mb-4 animate-hero-text"
            style={{ animationDelay: '0.3s' }}
          >
            多代理合成玩家评审系统
          </p>

          <p
            className="text-sm md:text-lg text-text-secondary max-w-2xl mx-auto mb-8 md:mb-12 animate-hero-text"
            style={{ animationDelay: '0.5s' }}
          >
            基于多个人格代理的合成评审框架，模拟真实玩家视角，生成可量化、可追溯、可行动的评审报告
          </p>

          <div style={{ animationDelay: '0.7s' }} className="animate-hero-text">
            <Link
              to="/review/new"
              className="inline-flex items-center gap-3 px-8 py-3 md:px-10 md:py-4 rounded-xl bg-neon-green text-primary-foreground font-bold text-base md:text-lg shadow-sm hover:scale-105 hover:shadow-md transition-all duration-300"
            >
              <Zap className="w-5 h-5" strokeWidth={1.25} />
              开始评审
            </Link>
          </div>
        </div>

        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-float">
          <ChevronDown className="w-8 h-8 text-text-muted" strokeWidth={1.25} />
        </div>
      </section>

      <section className="relative border-y border-border">
        <div className="absolute inset-0 bg-gradient-to-r from-bg-primary via-bg-secondary to-bg-primary" />
        <div className="relative max-w-6xl mx-auto px-4 py-8 md:py-10">
          <div className="grid grid-cols-2 md:grid-cols-4">
            {stats.map((stat, index) => (
              <div key={stat.label} className={cn('text-center px-4 md:px-12 py-3 md:py-4', index < stats.length - 1 && 'md:border-r md:border-border')}>
                <div className="font-display text-3xl md:text-5xl font-bold text-gradient-green mb-1">
                  {stat.value}
                </div>
                <div className="text-xs md:text-sm text-text-secondary tracking-wider font-display">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-12 md:py-16 border-b border-border">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-display text-xl md:text-2xl font-bold text-text-primary">
              评审技能
            </h2>
            <Link to="/skills" className="text-sm text-cyan hover:text-cyan-dim transition-colors flex items-center gap-1">
              查看全部 <ArrowRight className="w-3 h-3" strokeWidth={1.25} />
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
            {SKILLS.map((skill) => (
              <Link
                key={skill.type}
                to={`/review/new?skill=${skill.type}`}
                className={cn(
                  'group flex flex-col p-4 md:p-5 rounded-xl border-2 transition-all duration-300',
                  'bg-bg-card hover:bg-bg-card-hover',
                  skill.border,
                  'hover:scale-[1.02]'
                )}
              >
                <span className="text-2xl mb-2">{skill.icon}</span>
                <h3 className={cn('text-sm md:text-base font-bold font-display mb-1', skill.color)}>
                  {skill.name}
                </h3>
                <p className="text-xs text-text-secondary line-clamp-2 leading-relaxed">
                  {skill.description_zh}
                </p>
                <div className="flex items-center gap-2 mt-3 text-xs text-text-muted">
                  <span>{skill.task_types.length} 种任务</span>
                  <span>·</span>
                  <span>{skill.persona_count} 个角色</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16 md:py-28">
        <div className="max-w-6xl mx-auto px-4">
          <h2 className="font-display text-3xl md:text-5xl font-bold text-center text-gradient-green mb-4">
            为什么选择 AudienceLens
          </h2>
          <p className="text-text-secondary text-center max-w-xl mx-auto mb-12 md:mb-16 text-sm md:text-base">
            从评审到洞察，每一步都经过精心设计
          </p>

          <div className="space-y-16 md:space-y-32">
            {features.map((feature, index) => {
              const isReversed = index % 2 === 1
              const Icon = feature.icon
              const colorMap: Record<string, { text: string; bg: string; border: string; glow: string }> = {
                'neon-green': {
                  text: 'text-neon-green',
                  bg: 'bg-neon-green/10',
                  border: 'border-neon-green/20',
                  glow: 'group-hover:shadow-md',
                },
                'cyan': {
                  text: 'text-cyan',
                  bg: 'bg-cyan/10',
                  border: 'border-cyan/20',
                  glow: 'group-hover:shadow-md',
                },
                'warm-orange': {
                  text: 'text-warm-orange',
                  bg: 'bg-warm-orange/10',
                  border: 'border-warm-orange/20',
                  glow: 'group-hover:shadow-md',
                },
              }
              const c = colorMap[feature.color]

              return (
                <div
                  key={feature.title}
                  className="max-w-3xl mx-auto"
                >
                  <div
                    className={cn(
                      'flex flex-col md:flex-row items-center gap-6 md:gap-12 group',
                      isReversed && 'md:flex-row-reverse'
                    )}
                  >
                    <div className="flex-1 flex justify-center w-full">
                      <div className={cn('w-24 h-24 md:w-40 md:h-40 rounded-xl border', c.border, 'flex items-center justify-center relative overflow-hidden', c.glow, 'group-hover:scale-105 transition-transform duration-500')}>
                        <div className={cn('absolute inset-0 opacity-20', c.bg)} />
                        <Icon className={cn('w-10 h-10 md:w-16 md:h-16', c.text)} strokeWidth={1.25} />
                      </div>
                    </div>

                    <div className="flex-1 text-center md:text-left pt-0">
                      <div className={cn('text-sm font-display tracking-wider mb-2', c.text)}>
                        0{index + 1}
                      </div>
                      <h3 className="font-display text-xl md:text-3xl font-bold text-text-primary mb-3">
                        {feature.title}
                      </h3>
                      <p className="text-text-secondary leading-relaxed mb-4 max-w-md text-sm md:text-base">
                        {feature.description}
                      </p>
                      <div className={cn('inline-flex items-center gap-2 text-sm font-medium', c.text)}>
                        <span className="w-4 h-px bg-current" />
                        {feature.stat}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      <section className="py-16 md:py-24 border-t border-border">
        <div className="max-w-5xl mx-auto px-4">
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-display text-xl md:text-3xl font-bold text-text-primary">
              最近评审
            </h2>
            <Link to="/review/new" className="text-sm text-cyan hover:text-cyan-dim transition-colors flex items-center gap-1">
              查看全部 <ArrowRight className="w-3 h-3" strokeWidth={1.25} />
            </Link>
          </div>

          {reviews.length > 0 ? (
            <div className="flex flex-col gap-2">
              {reviews.map((review) => (
                <ReviewRow key={review.id} review={review} />
              ))}
            </div>
          ) : (
            <div className="text-center py-16 border border-dashed border-border rounded-xl">
              <Zap className="w-10 h-10 text-text-muted mx-auto mb-4" strokeWidth={1.25} />
              <p className="text-text-secondary mb-2">还没有评审记录</p>
              <p className="text-text-muted text-sm mb-6">创建你的第一个评审，获取多维度玩家视角</p>
              <Link
                to="/review/new"
                className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-neon-green text-primary-foreground font-semibold hover:bg-neon-green-dim transition-colors"
              >
                <Zap className="w-4 h-4" strokeWidth={1.25} />
                开始评审
              </Link>
            </div>
          )}
        </div>
      </section>

      <section className="pt-16 pb-12 md:pt-20 md:pb-16 relative overflow-hidden border-t border-border">
        <div className="absolute inset-0 bg-gradient-to-b from-bg-secondary/50 via-bg-secondary to-bg-primary" />
        <div className="relative max-w-4xl mx-auto px-4 text-center">
          <h2 className="font-display text-2xl md:text-4xl font-bold text-gradient-green mb-4">
            准备好获得真实玩家视角了吗？
          </h2>
          <p className="text-text-secondary text-sm md:text-lg mb-8 max-w-xl mx-auto">
            用合成玩家代理替代昂贵的真实用户测试，快速迭代你的游戏设计
          </p>
          <Link
            to="/review/new"
            className="inline-flex items-center gap-3 px-8 py-3 md:px-10 md:py-4 rounded-xl bg-neon-green text-primary-foreground font-bold text-base md:text-lg shadow-sm hover:scale-105 hover:shadow-md transition-all duration-300"
          >
            <Zap className="w-5 h-5" strokeWidth={1.25} />
            立即开始
          </Link>
        </div>
      </section>
    </div>
  )
}
