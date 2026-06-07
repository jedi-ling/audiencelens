import { Link } from 'react-router'
import {
  ShieldCheck,
  Database,
  Eye,
  Lock,
  Server,
  Trash2,
  Mail,
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Wifi,
  Globe,
  Cpu,
  Bot,
} from 'lucide-react'

const sections = [
  {
    icon: Database,
    title: '数据收集说明',
    color: 'text-neon-green',
    borderColor: 'border-neon-green/30',
    bgColor: 'bg-neon-green/5',
    iconBg: 'bg-neon-green/10',
    items: [
      {
        type: 'collect',
        label: '我们收集的数据',
        details: [
          '上传的评审文件（文档、设计稿等）',
          '选择的任务类型和角色配置',
          '评审结果与报告数据',
        ],
      },
      {
        type: 'no-collect',
        label: '我们不收集的数据',
        details: [
          '不收集个人身份信息',
          '不收集浏览历史',
          '不收集设备信息',
        ],
      },
      {
        type: 'key',
        label: 'API Key 处理',
        details: [
          '用户的 LLM API Key 仅存储在服务端内存中',
          '不写入数据库，不记录日志',
          '服务重启后自动清除',
        ],
      },
    ],
  },
  {
    icon: Eye,
    title: '数据使用说明',
    color: 'text-cyan',
    borderColor: 'border-cyan/30',
    bgColor: 'bg-cyan/5',
    iconBg: 'bg-cyan/10',
    items: [
      {
        type: 'use',
        label: '数据用途',
        details: [
          '上传的文件仅用于 AI 提取评审材料',
          '处理完成后不保留原文',
          '评审结果仅用户本人可访问',
        ],
      },
    ],
  },
  {
    icon: Lock,
    title: '数据安全措施',
    color: 'text-neon-green',
    borderColor: 'border-neon-green/30',
    bgColor: 'bg-neon-green/5',
    iconBg: 'bg-neon-green/10',
    items: [
      {
        type: 'security',
        label: '技术保障',
        details: [
          'API Key 内存存储 + base64 编码',
          'CORS 严格白名单',
          '安全响应头',
          '文件上传类型和大小限制',
          'WebSocket Origin 验证',
        ],
      },
    ],
  },
  {
    icon: Globe,
    title: '第三方服务',
    color: 'text-cyan',
    borderColor: 'border-cyan/30',
    bgColor: 'bg-cyan/5',
    iconBg: 'bg-cyan/10',
    items: [
      {
        type: 'third-party',
        label: 'LLM 服务商',
        details: [
          '使用 Anthropic / OpenAI / DeepSeek / Ollama API 进行 AI 评审',
          '用户数据仅发送到用户自行选择的 LLM 服务商',
          '本地模式（Ollama）数据不离开用户设备',
        ],
      },
    ],
    providers: [
      { name: 'Anthropic', icon: Bot, color: 'text-neon-green' },
      { name: 'OpenAI', icon: Cpu, color: 'text-cyan' },
      { name: 'DeepSeek', icon: Globe, color: 'text-warm-orange' },
      { name: 'Ollama', icon: Server, color: 'text-neon-green' },
    ],
  },
  {
    icon: Trash2,
    title: '数据保留',
    color: 'text-neon-green',
    borderColor: 'border-neon-green/30',
    bgColor: 'bg-neon-green/5',
    iconBg: 'bg-neon-green/10',
    items: [
      {
        type: 'retention',
        label: '保留策略',
        details: [
          '评审记录保存在本地 SQLite 数据库',
          '用户可随时删除评审记录',
          'API Key 在服务重启后自动清除',
        ],
      },
    ],
  },
]

function ItemBadge({ type }: { type: string }) {
  const config: Record<string, { icon: React.ElementType; label: string; className: string }> = {
    collect: { icon: CheckCircle2, label: '收集', className: 'bg-neon-green/10 text-neon-green' },
    'no-collect': { icon: XCircle, label: '不收集', className: 'bg-severity-critical/10 text-severity-critical' },
    key: { icon: Lock, label: '密钥', className: 'bg-cyan/10 text-cyan' },
    use: { icon: Eye, label: '用途', className: 'bg-cyan/10 text-cyan' },
    security: { icon: ShieldCheck, label: '安全', className: 'bg-neon-green/10 text-neon-green' },
    'third-party': { icon: Wifi, label: '第三方', className: 'bg-cyan/10 text-cyan' },
    retention: { icon: Trash2, label: '保留', className: 'bg-neon-green/10 text-neon-green' },
  }
  const c = config[type] || config.use
  const Icon = c.icon
  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium', c.className)}>
      <Icon className="w-3 h-3" strokeWidth={1.25} />
      {c.label}
    </span>
  )
}

import { cn } from '@/lib/utils'

export default function PrivacyPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8 animate-fade-in">
      <div className="mb-10">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-secondary transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" strokeWidth={1.25} />
          返回首页
        </Link>
        <h1 className="text-3xl md:text-4xl font-bold text-gradient-green font-display mb-3">
          隐私政策
        </h1>
        <p className="text-text-secondary">
          我们重视您的数据隐私。本政策说明 AudienceLens 如何收集、使用和保护您的数据。
        </p>
        <div className="flex items-center gap-2 mt-4 text-xs text-text-muted">
          <ShieldCheck className="w-4 h-4 text-neon-green" strokeWidth={1.25} />
          <span>最后更新：2026 年 5 月</span>
        </div>
      </div>

      <div className="space-y-6">
        {sections.map((section, si) => {
          const SectionIcon = section.icon
          return (
            <section
              key={si}
              className={cn(
                'rounded-xl border p-6 transition-all',
                section.borderColor,
                section.bgColor
              )}
            >
              <div className="flex items-center gap-3 mb-5">
                <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', section.iconBg)}>
                  <SectionIcon className={cn('w-5 h-5', section.color)} strokeWidth={1.25} />
                </div>
                <h2 className={cn('text-xl font-semibold font-display', section.color)}>
                  {section.title}
                </h2>
              </div>

              <div className="space-y-5">
                {section.items.map((item, ii) => (
                  <div key={ii} className="pl-1">
                    <div className="flex items-center gap-2 mb-3">
                      <ItemBadge type={item.type} />
                      <span className="text-sm font-medium text-text-primary">{item.label}</span>
                    </div>
                    <ul className="space-y-2 ml-1">
                      {item.details.map((d, di) => (
                        <li key={di} className="flex items-start gap-2.5 text-sm text-text-secondary">
                          <span className={cn('mt-1.5 w-1 h-1 rounded-full shrink-0', section.color === 'text-cyan' ? 'bg-cyan' : 'bg-neon-green')} />
                          {d}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>

              {section.providers && (
                <div className="mt-5 pt-4 border-t border-border/50">
                  <p className="text-xs text-text-muted mb-3">支持的 LLM 服务商</p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {section.providers.map((p, pi) => {
                      const PIcon = p.icon
                      return (
                        <div
                          key={pi}
                          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-bg-card border border-border/50"
                        >
                          <PIcon className={cn('w-4 h-4', p.color)} strokeWidth={1.25} />
                          <span className="text-xs font-medium text-text-primary">{p.name}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </section>
          )
        })}

        <section className="rounded-xl border border-border bg-bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-cyan/10 flex items-center justify-center">
              <Mail className="w-5 h-5 text-cyan" strokeWidth={1.25} />
            </div>
            <h2 className="text-xl font-semibold text-cyan font-display">联系方式</h2>
          </div>
          <p className="text-sm text-text-secondary mb-3">
            如果您对本隐私政策有任何疑问或建议，请通过以下方式联系我们：
          </p>
          <a
            href="mailto:audience-lens@example.com"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-colors text-sm font-medium"
          >
            <Mail className="w-4 h-4" strokeWidth={1.25} />
            audience-lens@example.com
          </a>
        </section>

        <div className="text-center py-6 border-t border-border/50">
          <p className="text-xs text-text-muted">
            AudienceLens 致力于保护您的数据隐私与安全
          </p>
        </div>
      </div>
    </div>
  )
}
