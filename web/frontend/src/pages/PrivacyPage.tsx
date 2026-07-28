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
    color: 'text-brand-primary',
    borderColor: 'border-brand-primary/30',
    bgColor: 'bg-brand-primary/5',
    iconBg: 'bg-brand-primary/10',
    items: [
      {
        type: 'collect',
        label: '我们收集的数据',
        details: [
          '你上传的评审材料（文本、截图等），随评审记录长期保存，直到你删除',
          '选择的任务类型、角色配置、评审模式',
          '评审报告、各角色意见、你的追问与回复',
          '注册邮箱与密码哈希（仅注册用户；密码用 PBKDF2-HMAC-SHA256 加盐哈希，我们无法还原）',
          '用量记录：每次评审的 token 数、花费、时间',
        ],
      },
      {
        type: 'no-collect',
        label: '我们不收集的数据',
        details: [
          '不收集浏览历史、不做跨站追踪',
          '不收集设备指纹、不接入第三方广告或分析 SDK',
          '除注册邮箱外，不主动索取任何身份信息（不要手机号、不要实名）',
        ],
      },
      {
        type: 'key',
        label: 'API Key 处理',
        details: [
          '你的 LLM API Key 加密后存进数据库（Fernet / AES-128-CBC + HMAC 认证加密）',
          '加密密钥与登录令牌密钥分离配置，轮换登录密钥不会导致密钥失效',
          '页面上只回显掩码（如 sk-ant-…4f2a）；数据导出也只给掩码，不含明文',
          '你可以随时在设置页删除它',
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
          '你的材料只用于这一次评审：发给你选定的模型服务商，生成给你看的报告',
          '材料与报告会随评审记录保存，方便你回看历史、继续追问——直到你自己删除',
          '评审结果仅你本人可访问（按账号隔离；未登录时按匿名身份隔离）',
        ],
      },
      {
        type: 'use',
        label: '我们不会做的事',
        details: [
          '不用你的内容训练任何模型——我们不训练模型，也不向任何人出售或共享你的数据',
          '不拿你的项目内容做案例展示、宣传素材或公开样本',
          '不在你未要求时读取你的内容；运维排障也不会把你的材料复制到别处',
        ],
      },
    ],
  },
  {
    icon: Lock,
    title: '数据安全措施',
    color: 'text-brand-primary',
    borderColor: 'border-brand-primary/30',
    bgColor: 'bg-brand-primary/5',
    iconBg: 'bg-brand-primary/10',
    items: [
      {
        type: 'security',
        label: '技术保障',
        details: [
          'API Key 用 Fernet 对称加密后落库（AES-128-CBC + HMAC-SHA256 认证加密）',
          '登录密码用 PBKDF2-HMAC-SHA256（20 万轮）加盐哈希，不可还原',
          '邮箱验证与密码重置令牌只存哈希摘要，一次性、可过期',
          'CORS 严格白名单 + 安全响应头 + WebSocket Origin 验证',
          '上传类型/大小限制，分块流式读取，超限即中止',
        ],
      },
    ],
  },
  {
    icon: ShieldCheck,
    title: '你不必只听我们的承诺',
    color: 'text-brand-primary',
    borderColor: 'border-brand-primary/30',
    bgColor: 'bg-brand-primary/5',
    iconBg: 'bg-brand-primary/10',
    items: [
      {
        type: 'verify',
        label: '可验证，而不是只能相信',
        details: [
          '代码开源：这一页写的每条承诺，都能在源码里查证是否属实',
          '自带密钥（BYOK）：你的材料直接发给你自己选的模型服务商，用你自己的额度',
          '本地模式：接 Ollama 跑本地模型，数据根本不出你的机器',
          '可自建：整套系统能部署在你自己的服务器上，我们连接触的机会都没有',
          '随时带走或删干净：设置页两个按钮，不用发邮件申请、不用等人工审核',
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
      { name: 'Anthropic', icon: Bot, color: 'text-brand-primary' },
      { name: 'OpenAI', icon: Cpu, color: 'text-cyan' },
      { name: 'DeepSeek', icon: Globe, color: 'text-warm-orange' },
      { name: 'Ollama', icon: Server, color: 'text-brand-primary' },
    ],
  },
  {
    icon: Trash2,
    title: '数据保留',
    color: 'text-brand-primary',
    borderColor: 'border-brand-primary/30',
    bgColor: 'bg-brand-primary/5',
    iconBg: 'bg-brand-primary/10',
    items: [
      {
        type: 'retention',
        label: '保留策略',
        details: [
          '评审记录保存在服务器数据库，直到你主动删除——我们不设自动过期',
          '设置页可「导出我的全部数据」，一份 JSON 带走全部内容',
          '设置页可「删除我的账号与数据」：评审、材料、报告、追问、伦理体检记录（含内容摘录）、'
            + 'API Key、账号本身立即物理删除',
          '例外（我们如实说明）：用量与兑换流水会保留，但 user_id 会被改写成不可回指的墓碑标识——'
            + '财务对账所需，此后无法关联到你本人',
        ],
      },
    ],
  },
]

function ItemBadge({ type }: { type: string }) {
  const config: Record<string, { icon: React.ElementType; label: string; className: string }> = {
    collect: { icon: CheckCircle2, label: '收集', className: 'bg-brand-primary/10 text-brand-primary' },
    'no-collect': { icon: XCircle, label: '不收集', className: 'bg-severity-critical/10 text-severity-critical' },
    key: { icon: Lock, label: '密钥', className: 'bg-cyan/10 text-cyan' },
    use: { icon: Eye, label: '用途', className: 'bg-cyan/10 text-cyan' },
    security: { icon: ShieldCheck, label: '安全', className: 'bg-brand-primary/10 text-brand-primary' },
    'third-party': { icon: Wifi, label: '第三方', className: 'bg-cyan/10 text-cyan' },
    retention: { icon: Trash2, label: '保留', className: 'bg-brand-primary/10 text-brand-primary' },
    verify: { icon: ShieldCheck, label: '可验证', className: 'bg-brand-primary/10 text-brand-primary' },
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
          <ShieldCheck className="w-4 h-4 text-brand-primary" strokeWidth={1.25} />
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
                          <span className={cn('mt-1.5 w-1 h-1 rounded-full shrink-0', section.color === 'text-cyan' ? 'bg-cyan' : 'bg-brand-primary')} />
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
