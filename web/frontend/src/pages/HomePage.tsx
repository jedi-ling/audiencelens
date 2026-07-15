import { useEffect } from 'react'
import { Link } from 'react-router'
import { useReviewStore } from '@/store/review-store'
import {
  Zap,
  BarChart3,
  ArrowRight,
  Clock,
  CheckCircle2,
  Loader2,
  ChevronDown,
  Users,
  Package,
  Layers,
  Swords,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  Fingerprint,
  Eye,
  Gauge,
  MessageSquareText,
  TerminalSquare,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Review } from '@/lib/mock-data'
import ParticleConstellation from '@/components/ParticleConstellation'
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

/** 板块眉标：等宽字体的代码注释风格，全站赛博视觉锚点 */
function SectionTag({ children, color = 'cyan' }: { children: string; color?: 'cyan' | 'green' | 'orange' }) {
  const colorClass = {
    cyan: 'text-cyan',
    green: 'text-neon-green',
    orange: 'text-warm-orange',
  }[color]
  return (
    <div className={cn('font-mono text-[11px] md:text-xs tracking-[0.3em] uppercase mb-3', colorClass)}>
      {'// '}{children}
    </div>
  )
}

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

// 核心差异化——三条经过竞品调研核实的差异点，
// 取代泛泛的"零门槛/可视化/可分享"话术，讲清楚"为什么不是又一个 AI 对话框"。
const features = [
  {
    icon: Swords,
    title: '交叉质询 + 改票',
    description:
      '人格之间互相质疑论据、暴露盲点，三轮辩论后投票可能翻转。不是简单的问答，而是真正的群体审议——每个结论都扛过了反驳。',
    stat: '三轮交叉质询 · 改票留痕',
    color: 'neon-green',
  },
  {
    icon: BarChart3,
    title: '结构化裁决',
    description:
      '共识区、分歧区、修复建议表三个维度输出，附带完整质询记录。比访谈更有结构，比问卷更有深度，可直接进你的迭代待办。',
    stat: '共识 / 分歧 / 修复 三维输出',
    color: 'cyan',
  },
  {
    icon: ExternalLink,
    title: '开源免费 · BYOK',
    description:
      'MIT 协议，随意修改、商用、扩展，模型可换本地。用你自己的 API Key 运行，服务端不经手你的数据，也不替你花一分钱。',
    stat: 'MIT · 数据不离开你的机器',
    color: 'warm-orange',
  },
]

// 终端错误码风格的三个痛点
const PROBLEMS = [
  {
    code: 'ERR://01',
    name: 'SINGLE_VIEWPOINT',
    title: '一个 AI 的一面之词',
    body: '问一次得一个答案，它不会反驳自己。你听不到不同人格之间的分歧，也就看不到盲点在哪。',
  },
  {
    code: 'ERR://02',
    name: 'FALSE_CONSENSUS',
    title: '大家都说"挺好的"',
    body: '没有对抗机制，合成反馈会滑向廉价的共识。好听，但对你的决策毫无价值。',
  },
  {
    code: 'ERR://03',
    name: 'NO_PROVENANCE',
    title: '结论没有证据链',
    body: '"感觉不错"——凭什么？哪个人格因为什么改了主意？没有记录，就无法复盘，也无法信任。',
  },
]

const STEPS = [
  { cmd: 'select --skill', title: '选择技能', body: '游戏评审 / 产品评审 / 红队对抗 / 人格生成器' },
  { cmd: 'load ./artifact', title: '投入素材', body: '概念文档、商店页面、功能描述或直接粘贴文本' },
  { cmd: 'run --panel', title: '评审团开庭', body: '人格独立评审 → 交叉质询 → 改票投票' },
  { cmd: 'export verdict', title: '获取裁决', body: 'JSON 数据 + Markdown 摘要 + 可视化报告' },
]

// 价格区间已对照对方官网核实：
// SyntheticUsers 官网为 $2–60/次区间；Yabble 为年约 $8,900–80,000，非月费。
const COMPARE_ROWS: Array<[string, string, string, string, string]> = [
  ['方法论', '评审式', '访谈式', '真人访谈', '对话式'],
  ['质询深度', '三轮交叉质询', '单轮对话', '依赖主持人', '单轮对话'],
  ['改票机制', '支持 ✓', '不支持', '不支持', '不支持'],
  ['开源', 'MIT ✓', '闭源', '闭源', '闭源'],
  ['价格', '免费', '$2–60 / 次', '按项目报价', '$8,900–80,000 / 年'],
]

const ETHICS = [
  {
    tag: 'ETHIC_01',
    icon: Fingerprint,
    title: '行为优先于人口统计',
    body: '人格由 12 维行为特征定义，而非性别、年龄、地域——从源头切断刻板印象的因果链。',
  },
  {
    tag: 'ETHIC_02',
    icon: Eye,
    title: '两层刻板印象检测',
    body: '正则初筛 + LLM 复审双层机制，自动识别并标记"身份→行为"的因果推断违规。',
  },
  {
    tag: 'ETHIC_03',
    icon: ShieldCheck,
    title: '证据三级标注',
    body: '直接引用 / 合理推断 / 信息缺口三级分层，推断占比强制封顶，杜绝凭空捏造。',
  },
  {
    tag: 'ETHIC_04',
    icon: Gauge,
    title: '8 维质量 Harness',
    body: '通过 8 个维度的评估框架量化人格分化度与校准诚实度，结论以假设而非预测呈现。',
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
      {/* ---------- Hero ---------- */}
      <section className="relative min-h-[calc(100vh-4rem)] md:min-h-[calc(100vh-4rem)] flex items-center justify-center overflow-hidden">
        <ParticleConstellation className="absolute inset-0" />

        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-bg-primary pointer-events-none" />

        <div className="relative z-10 text-center px-4 max-w-5xl mx-auto">
          <h1
            className="font-display text-4xl sm:text-5xl md:text-9xl font-bold text-gradient-green mb-4 md:mb-6 tracking-tight animate-hero-text"
            style={{ animationDelay: '0.1s', textShadow: '0 0 20px rgba(0,255,136,0.2)' }}
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
            一整支合成人格评审团独立评审你的游戏或产品，互相交叉质询、当场改票，
            最后收敛出一份带证据的结构化裁决——定位于真人测试之前的预筛，而非替代真人研究。
          </p>

          <div style={{ animationDelay: '0.7s' }} className="animate-hero-text flex flex-wrap items-center justify-center gap-3">
            <Link
              to="/ask"
              className="inline-flex items-center gap-3 px-8 py-3 md:px-10 md:py-4 rounded-xl bg-neon-green text-bg-primary font-bold text-base md:text-lg hover:scale-105 transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,136,0.3)]"
            >
              <MessageSquareText className="w-5 h-5" strokeWidth={1.25} />
              对话评审
            </Link>
            <Link
              to="/review/new"
              className="inline-flex items-center gap-2 px-6 py-3 md:px-8 md:py-4 rounded-xl border border-border text-text-primary font-medium text-sm md:text-base hover:border-neon-green/40 hover:text-neon-green transition-colors"
            >
              <Zap className="w-4 h-4" strokeWidth={1.25} />
              手动配置
            </Link>
          </div>
        </div>

        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-float">
          <ChevronDown className="w-8 h-8 text-text-muted" strokeWidth={1.25} />
        </div>
      </section>

      {/* ---------- 问题：终端错误码 ---------- */}
      <section className="relative py-16 md:py-24 border-b border-border">
        <div className="absolute inset-0 grid-lines pointer-events-none [mask-image:radial-gradient(ellipse_70%_60%_at_50%_40%,#000_30%,transparent_80%)]" />
        <div className="relative max-w-5xl mx-auto px-4">
          <div className="text-center mb-10 md:mb-14">
            <SectionTag color="orange">FEEDBACK_AUDIT — 3 ERRORS FOUND</SectionTag>
            <h2 className="font-display text-2xl md:text-4xl font-bold text-text-primary mb-3">
              问题不在没人给反馈，而在反馈从没被质询过
            </h2>
            <p className="text-text-secondary text-sm md:text-base max-w-xl mx-auto">
              找 ChatGPT 问一句，得到的是一个声音的附和。真实用户测试很贵、很慢。中间这段，一直是空的。
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {PROBLEMS.map((p) => (
              <div
                key={p.code}
                className="group relative rounded-lg border border-border bg-bg-card/80 backdrop-blur-sm overflow-hidden hover:border-warm-orange/40 transition-colors"
              >
                <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border bg-bg-secondary/80 font-mono text-[11px]">
                  <span className="w-2 h-2 rounded-full bg-warm-orange animate-pulse-glow" />
                  <span className="text-warm-orange">{p.code}</span>
                  <span className="text-text-muted tracking-wider">{p.name}</span>
                </div>
                <div className="p-4 md:p-5">
                  <h3 className="font-display text-base md:text-lg font-bold text-text-primary mb-2">{p.title}</h3>
                  <p className="text-sm text-text-secondary leading-relaxed">{p.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 实时统计 ---------- */}
      <section className="relative border-b border-border">
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

      {/* ---------- 核心差异化 ---------- */}
      <section className="py-16 md:py-28">
        <div className="max-w-6xl mx-auto px-4">
          <div className="text-center mb-12 md:mb-16">
            <SectionTag color="green">CORE_DIFFERENTIATORS</SectionTag>
            <h2 className="font-display text-3xl md:text-5xl font-bold text-gradient-green mb-4">
              不是又一个 AI 对话框
            </h2>
            <p className="text-text-secondary max-w-xl mx-auto text-sm md:text-base">
              三轮质询、改票机制、结构化裁决——这是真正会互相较真的合成评审团
            </p>
          </div>

          <div className="space-y-16 md:space-y-32">
            {features.map((feature, index) => {
              const isReversed = index % 2 === 1
              const Icon = feature.icon
              const colorMap: Record<string, { text: string; bg: string; border: string; glow: string }> = {
                'neon-green': {
                  text: 'text-neon-green',
                  bg: 'bg-neon-green/10',
                  border: 'border-neon-green/20',
                  glow: 'group-hover:shadow-[0_0_30px_rgba(0,255,136,0.15)]',
                },
                'cyan': {
                  text: 'text-cyan',
                  bg: 'bg-cyan/10',
                  border: 'border-cyan/20',
                  glow: 'group-hover:shadow-[0_0_30px_rgba(0,212,255,0.15)]',
                },
                'warm-orange': {
                  text: 'text-warm-orange',
                  bg: 'bg-warm-orange/10',
                  border: 'border-warm-orange/20',
                  glow: 'group-hover:shadow-[0_0_30px_rgba(255,107,53,0.15)]',
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
                      <div className={cn('w-24 h-24 md:w-40 md:h-40 rounded-xl border', c.border, 'flex items-center justify-center relative overflow-hidden', c.glow, 'group-hover:scale-105 transition-transform duration-500 scanline-overlay')}>
                        <div className={cn('absolute inset-0 opacity-20', c.bg)} />
                        <Icon className={cn('w-10 h-10 md:w-16 md:h-16', c.text)} strokeWidth={1.25} />
                      </div>
                    </div>

                    <div className="flex-1 text-center md:text-left pt-0">
                      <div className={cn('text-sm font-mono tracking-[0.2em] mb-2', c.text)}>
                        {'['}0{index + 1}{']'}
                      </div>
                      <h3 className="font-display text-xl md:text-3xl font-bold text-text-primary mb-3">
                        {feature.title}
                      </h3>
                      <p className="text-text-secondary leading-relaxed mb-4 max-w-md text-sm md:text-base">
                        {feature.description}
                      </p>
                      <div className={cn('inline-flex items-center gap-2 text-sm font-mono', c.text)}>
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

      {/* ---------- 运作流程：命令管线 ---------- */}
      <section className="relative py-12 md:py-20 border-t border-border">
        <div className="absolute inset-0 grid-lines pointer-events-none [mask-image:radial-gradient(ellipse_60%_70%_at_50%_50%,#000_20%,transparent_75%)]" />
        <div className="relative max-w-6xl mx-auto px-4">
          <div className="text-center mb-10">
            <SectionTag>EXECUTION_PIPELINE</SectionTag>
            <h2 className="font-display text-xl md:text-3xl font-bold text-text-primary">
              四步，从素材到裁决
            </h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {STEPS.map((step, i) => (
              <div key={step.title} className="relative">
                <div className="hud-corners h-full rounded-lg border border-border bg-bg-card/80 backdrop-blur-sm p-4 md:p-5 hover:border-neon-green/30 transition-colors">
                  <div className="font-mono text-[11px] text-text-muted mb-1">
                    <span className="text-neon-green">$</span> audiencelens {step.cmd}
                  </div>
                  <div className="font-mono text-xs text-neon-green mb-3">[{String(i + 1).padStart(2, '0')}/04]</div>
                  <h3 className="font-display text-sm md:text-base font-bold text-text-primary mb-1.5">{step.title}</h3>
                  <p className="text-xs text-text-secondary leading-relaxed">{step.body}</p>
                </div>
                {i < STEPS.length - 1 && (
                  <div className="hidden lg:flex absolute top-1/2 -right-3.5 -translate-y-1/2 z-10 text-neon-green/60 font-mono text-lg select-none">
                    ▸
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 评审技能 ---------- */}
      <section className="py-12 md:py-16 border-t border-border">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex items-end justify-between mb-6">
            <div>
              <SectionTag color="green">SKILL_ARSENAL</SectionTag>
              <h2 className="font-display text-xl md:text-2xl font-bold text-text-primary">
                评审技能
              </h2>
            </div>
            <Link to="/skills" className="text-sm text-cyan hover:text-cyan-dim transition-colors flex items-center gap-1 pb-1">
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
                <div className="flex items-center gap-2 mt-3 text-xs text-text-muted font-mono">
                  <span>{skill.task_types.length} 种任务</span>
                  <span>·</span>
                  <span>{skill.persona_count} 个角色</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 竞品对比：终端窗口 ---------- */}
      <section className="py-16 md:py-24 border-t border-border">
        <div className="max-w-5xl mx-auto px-4">
          <div className="text-center mb-10">
            <SectionTag>COMPETITIVE_SCAN</SectionTag>
            <h2 className="font-display text-2xl md:text-4xl font-bold text-text-primary mb-3">
              不是所有 AI 研究工具都一样
            </h2>
            <p className="text-text-secondary text-sm md:text-base max-w-xl mx-auto">
              差异集中在一个地方：反馈有没有被质询过。价格区间已对照对方官网核实。
            </p>
          </div>

          <div className="hud-corners-cyan hud-corners rounded-xl border border-border bg-bg-card overflow-hidden scan-sweep">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-bg-secondary font-mono text-[11px] text-text-muted">
              <span className="w-2.5 h-2.5 rounded-full bg-severity-critical/80" />
              <span className="w-2.5 h-2.5 rounded-full bg-severity-medium/80" />
              <span className="w-2.5 h-2.5 rounded-full bg-neon-green/80" />
              <span className="ml-2"><span className="text-neon-green">$</span> audiencelens compare --against synthetic-users outset yabble</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[640px]">
                <thead>
                  <tr className="bg-bg-secondary/60">
                    <th className="text-left px-4 py-3 font-mono text-[11px] tracking-wider uppercase text-text-muted font-medium">维度</th>
                    <th className="text-left px-4 py-3 font-mono text-[11px] tracking-wider uppercase text-neon-green font-bold">AudienceLens</th>
                    <th className="text-left px-4 py-3 font-mono text-[11px] tracking-wider uppercase text-text-muted font-medium">SyntheticUsers</th>
                    <th className="text-left px-4 py-3 font-mono text-[11px] tracking-wider uppercase text-text-muted font-medium">Outset</th>
                    <th className="text-left px-4 py-3 font-mono text-[11px] tracking-wider uppercase text-text-muted font-medium">Yabble</th>
                  </tr>
                </thead>
                <tbody>
                  {COMPARE_ROWS.map((row, i) => (
                    <tr key={row[0]} className={cn('border-t border-border/60', i % 2 === 1 && 'bg-bg-secondary/30')}>
                      <th className="text-left px-4 py-3 font-medium text-text-secondary whitespace-nowrap">{row[0]}</th>
                      <td className="px-4 py-3 bg-neon-green/5 text-neon-green font-medium border-x border-neon-green/20 whitespace-nowrap">{row[1]}</td>
                      <td className="px-4 py-3 text-text-muted whitespace-nowrap">{row[2]}</td>
                      <td className="px-4 py-3 text-text-muted whitespace-nowrap">{row[3]}</td>
                      <td className="px-4 py-3 text-text-muted whitespace-nowrap">{row[4]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      {/* ---------- 裁决预览：运行中的终端 ---------- */}
      <section className="relative py-16 md:py-24 border-t border-border">
        <div className="absolute inset-0 grid-lines pointer-events-none [mask-image:radial-gradient(ellipse_60%_60%_at_50%_45%,#000_25%,transparent_78%)]" />
        <div className="relative max-w-5xl mx-auto px-4">
          <div className="text-center mb-10">
            <SectionTag color="green">VERDICT_PREVIEW</SectionTag>
            <h2 className="font-display text-2xl md:text-4xl font-bold text-text-primary mb-3">
              三轮质询后的结构化评价书
            </h2>
            <p className="text-text-secondary text-sm md:text-base max-w-xl mx-auto">
              共识、分歧、修复建议与完整质询记录——每一条结论都能溯源到是谁、因为什么。
            </p>
          </div>

          <div className="hud-corners rounded-xl border border-neon-green/25 bg-bg-card overflow-hidden shadow-[0_0_40px_rgba(0,255,136,0.06)]">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-bg-secondary font-mono text-[11px] text-text-muted">
              <span className="w-2.5 h-2.5 rounded-full bg-severity-critical/80" />
              <span className="w-2.5 h-2.5 rounded-full bg-severity-medium/80" />
              <span className="w-2.5 h-2.5 rounded-full bg-neon-green/80" />
              <TerminalSquare className="w-3.5 h-3.5 ml-2 text-neon-green" strokeWidth={1.5} />
              <span>evaluation-report.json — panel:20 · rounds:3 · flips:1</span>
            </div>

            <div className="px-5 pt-4 font-mono text-xs text-text-secondary">
              <span className="text-neon-green">$</span> audiencelens run steam_page_review ./artifact.json --mode full
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-5">
              <div className="rounded-lg border border-border p-4 bg-bg-primary/80">
                <div className="flex items-center gap-2 text-[11px] font-mono tracking-[0.2em] text-neon-green mb-3">
                  <span className="w-2 h-2 rounded-sm bg-current animate-pulse-glow" /> CONSENSUS · 共识区
                </div>
                <p className="text-sm text-text-primary mb-1">17 / 20 人格认为核心循环满足需求</p>
                <p className="text-xs text-text-muted">探索—战斗—成长的节奏被广泛认可，前期正反馈充足。</p>
              </div>
              <div className="rounded-lg border border-border p-4 bg-bg-primary/80">
                <div className="flex items-center gap-2 text-[11px] font-mono tracking-[0.2em] text-warm-orange mb-3">
                  <span className="w-2 h-2 rounded-sm bg-current animate-pulse-glow" /> DISAGREEMENT · 分歧区
                </div>
                <p className="text-sm text-text-primary mb-1">8 / 20 人格对定价策略持负面意见</p>
                <p className="text-xs text-text-muted">价格敏感型与核心硬核型在"128 元含金量"上尖锐对立。</p>
              </div>
              <div className="rounded-lg border border-border p-4 bg-bg-primary/80">
                <div className="flex items-center gap-2 text-[11px] font-mono tracking-[0.2em] text-severity-medium mb-3">
                  <span className="w-2 h-2 rounded-sm bg-current" /> REPAIR_TABLE · 修复建议
                </div>
                <p className="text-sm text-text-primary mb-1.5"><span className="font-mono text-severity-critical text-[10px] border border-severity-critical/40 rounded px-1 py-0.5 mr-1.5">HIGH</span>移动端适配缺失 → 优先修复</p>
                <p className="text-sm text-text-primary"><span className="font-mono text-severity-medium text-[10px] border border-severity-medium/40 rounded px-1 py-0.5 mr-1.5">MED</span>CTA 不够突出 → 增大对比度</p>
              </div>
              <div className="rounded-lg border border-cyan/25 p-4 bg-bg-primary/80">
                <div className="flex items-center gap-2 text-[11px] font-mono tracking-[0.2em] text-cyan mb-3">
                  <RefreshCw className="w-3.5 h-3.5" strokeWidth={1.5} /> CROSS_EXAM_LOG · 质询记录
                </div>
                <p className="text-xs font-mono text-text-secondary mb-1.5">
                  <span className="text-cyan">R2·P12→P05</span> 你的正面评价是否忽略了移动端体验？
                </p>
                <p className="text-xs font-mono text-warm-orange">
                  <span className="text-cyan">R3·P05→P12</span> 确实，我改投反对票 <span className="inline-block">↺ VOTE_FLIPPED</span>
                </p>
              </div>
            </div>

            <div className="px-5 pb-4 font-mono text-xs text-text-muted terminal-cursor">
              <span className="text-neon-green">✓</span> verdict sealed · 3 judgments recorded to ledger
            </div>
          </div>

          <div className="mt-6 text-center">
            <Link to="/ledger" className="inline-flex items-center gap-2 text-sm font-mono text-cyan hover:text-cyan-dim transition-colors">
              {'>'} 判断复利：查看历史预测的命中率追踪 <ArrowRight className="w-3.5 h-3.5" strokeWidth={1.25} />
            </Link>
          </div>
        </div>
      </section>

      {/* ---------- 伦理与合规 ---------- */}
      <section className="py-16 md:py-24 border-t border-border">
        <div className="max-w-5xl mx-auto px-4">
          <div className="text-center mb-10">
            <SectionTag>ETHICS_&_COMPLIANCE</SectionTag>
            <h2 className="font-display text-2xl md:text-4xl font-bold text-text-primary mb-3">
              合成评审，必须负责任
            </h2>
            <p className="text-text-secondary text-sm md:text-base max-w-xl mx-auto">
              AI 模拟观众有其边界。AudienceLens 把这些边界写进了系统，而不是免责声明里。
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {ETHICS.map((e) => {
              const Icon = e.icon
              return (
                <div key={e.tag} className="hud-corners flex gap-4 p-5 rounded-lg border border-border bg-bg-card/80 hover:border-neon-green/30 transition-colors">
                  <div className="shrink-0 w-10 h-10 rounded-lg bg-neon-green/10 border border-neon-green/20 flex items-center justify-center">
                    <Icon className="w-5 h-5 text-neon-green" strokeWidth={1.25} />
                  </div>
                  <div>
                    <div className="font-mono text-[10px] tracking-[0.25em] text-text-muted mb-1">[{e.tag}]</div>
                    <h3 className="font-display text-sm md:text-base font-bold text-text-primary mb-1">{e.title}</h3>
                    <p className="text-xs md:text-sm text-text-secondary leading-relaxed">{e.body}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* ---------- 最近评审 ---------- */}
      <section className="py-16 md:py-24 border-t border-border">
        <div className="max-w-5xl mx-auto px-4">
          <div className="flex items-end justify-between mb-6">
            <div>
              <SectionTag color="green">RECENT_RUNS</SectionTag>
              <h2 className="font-display text-xl md:text-3xl font-bold text-text-primary">
                最近评审
              </h2>
            </div>
            <Link to="/review/new" className="text-sm text-cyan hover:text-cyan-dim transition-colors flex items-center gap-1 pb-1">
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
                to="/ask"
                className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-neon-green text-bg-primary font-semibold hover:bg-neon-green-dim transition-colors"
              >
                <MessageSquareText className="w-4 h-4" strokeWidth={1.25} />
                开始对话评审
              </Link>
            </div>
          )}
        </div>
      </section>

      {/* ---------- 最终 CTA ---------- */}
      <section className="relative pt-16 pb-12 md:pt-20 md:pb-16 overflow-hidden border-t border-border">
        <div className="absolute inset-0 bg-gradient-to-b from-bg-secondary/50 via-bg-secondary to-bg-primary" />
        <div className="absolute inset-0 grid-lines animate-grid-pulse pointer-events-none [mask-image:radial-gradient(ellipse_65%_80%_at_50%_100%,#000_20%,transparent_80%)]" />
        <div className="relative max-w-4xl mx-auto px-4 text-center">
          <SectionTag color="green">PANEL_STANDBY</SectionTag>
          <h2 className="font-display text-2xl md:text-4xl font-bold text-gradient-green mb-4">
            75 位 AI 评审员已就位，等待你的素材
          </h2>
          <p className="text-text-secondary text-sm md:text-lg mb-8 max-w-xl mx-auto">
            本地即可运行，无需注册。设置 API Key 获得真实评审，或空跑验证管线。
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link
              to="/ask"
              className="inline-flex items-center gap-3 px-8 py-3 md:px-10 md:py-4 rounded-xl bg-neon-green text-bg-primary font-bold text-base md:text-lg hover:scale-105 transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,136,0.3)]"
            >
              <MessageSquareText className="w-5 h-5" strokeWidth={1.25} />
              立即开始
            </Link>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3 md:px-8 md:py-4 rounded-xl border border-border text-text-primary font-medium text-sm md:text-base hover:border-neon-green/40 hover:text-neon-green transition-colors"
            >
              <ExternalLink className="w-4 h-4" strokeWidth={1.25} />
              GitHub 仓库
            </a>
          </div>
        </div>
      </section>
    </div>
  )
}
