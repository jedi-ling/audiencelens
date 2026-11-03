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
import { t } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import type { PlainMessageKey } from '@/i18n/keys.gen'

/**
 * 章节表。存的是 **key 不是文案**：这个数组在模块求值时就固定了，存翻译结果
 * 的话切换语言不会重新求值，整页政策会一直停在打开页面时的那种语言。
 * 与 Layout.tsx 的 navItems 同一条规矩。
 */
const sections: {
  icon: React.ElementType
  titleKey: PlainMessageKey
  color: string
  borderColor: string
  bgColor: string
  iconBg: string
  items: { type: string; labelKey: PlainMessageKey; detailKeys: PlainMessageKey[] }[]
  providers?: { name: string; icon: React.ElementType; color: string }[]
}[] = [
  {
    icon: Database,
    titleKey: 'page.privacy.collection.title',
    color: 'text-brand-primary',
    borderColor: 'border-brand-primary/30',
    bgColor: 'bg-brand-primary/5',
    iconBg: 'bg-brand-primary/10',
    items: [
      {
        type: 'collect',
        labelKey: 'page.privacy.collection_collected.label',
        detailKeys: [
          'page.privacy.collection_collected_materials.desc',
          'page.privacy.collection_collected_config.desc',
          'page.privacy.collection_collected_report.desc',
          // 对话持续化上线后新增的一类数据。此前这一条不存在，因为那段对话
          // 只活在浏览器内存里、从不离开设备；现在它会落到服务器数据库，
          // 政策里就必须写明——否则这一页对用户就是不实的。
          'page.privacy.collection_collected_chat.desc',
          // 图片改为落盘之后新增。此前它只以 data URI 形式活在浏览器内存里，
          // 从不落到服务器磁盘；现在会，政策就得写明。
          'page.privacy.collection_collected_images.desc',
          'page.privacy.collection_collected_account.desc',
          'page.privacy.collection_collected_usage.desc',
        ],
      },
      {
        type: 'no-collect',
        labelKey: 'page.privacy.collection_not.label',
        detailKeys: [
          'page.privacy.collection_not_history.desc',
          'page.privacy.collection_not_fingerprint.desc',
          'page.privacy.collection_not_identity.desc',
        ],
      },
      {
        type: 'key',
        labelKey: 'page.privacy.collection_apikey.label',
        detailKeys: [
          'page.privacy.collection_apikey_encrypted.desc',
          'page.privacy.collection_apikey_separate.desc',
          'page.privacy.collection_apikey_masked.desc',
          'page.privacy.collection_apikey_delete.desc',
        ],
      },
    ],
  },
  {
    icon: Eye,
    titleKey: 'page.privacy.usage.title',
    color: 'text-cyan',
    borderColor: 'border-cyan/30',
    bgColor: 'bg-cyan/5',
    iconBg: 'bg-cyan/10',
    items: [
      {
        type: 'use',
        labelKey: 'page.privacy.usage_purpose.label',
        detailKeys: [
          'page.privacy.usage_purpose_single.desc',
          'page.privacy.usage_purpose_retained.desc',
          'page.privacy.usage_purpose_isolated.desc',
        ],
      },
      {
        type: 'use',
        labelKey: 'page.privacy.usage_never.label',
        detailKeys: [
          'page.privacy.usage_never_training.desc',
          'page.privacy.usage_never_showcase.desc',
          'page.privacy.usage_never_copy.desc',
        ],
      },
      {
        type: 'use',
        labelKey: 'page.privacy.usage_admin.label',
        detailKeys: [
          // 早期版本这里写的是"不在你未要求时读取你的内容"——管理后台上线评审
          // 巡检功能后，这条承诺已经不成立了：处理客诉、排查滥用、核对计费
          // 争议时，运营方（目前是本站唯一的开发者）可以在未经你主动求助的
          // 情况下打开评审内容。与其让承诺继续挂着不实的文案，不如把真实
          // 边界写清楚。
          'page.privacy.usage_admin_access.desc',
          'page.privacy.usage_admin_audit.desc',
          'page.privacy.usage_admin_unchanged.desc',
        ],
      },
    ],
  },
  {
    icon: Lock,
    titleKey: 'page.privacy.security.title',
    color: 'text-brand-primary',
    borderColor: 'border-brand-primary/30',
    bgColor: 'bg-brand-primary/5',
    iconBg: 'bg-brand-primary/10',
    items: [
      {
        type: 'security',
        labelKey: 'page.privacy.security_tech.label',
        detailKeys: [
          'page.privacy.security_tech_key.desc',
          'page.privacy.security_tech_password.desc',
          'page.privacy.security_tech_token.desc',
          'page.privacy.security_tech_cors.desc',
          'page.privacy.security_tech_upload.desc',
        ],
      },
    ],
  },
  {
    icon: ShieldCheck,
    titleKey: 'page.privacy.verify.title',
    color: 'text-brand-primary',
    borderColor: 'border-brand-primary/30',
    bgColor: 'bg-brand-primary/5',
    iconBg: 'bg-brand-primary/10',
    items: [
      {
        type: 'verify',
        labelKey: 'page.privacy.verify_checkable.label',
        detailKeys: [
          'page.privacy.verify_checkable_oss.desc',
          'page.privacy.verify_checkable_byok.desc',
          'page.privacy.verify_checkable_hosted.desc',
          'page.privacy.verify_checkable_selfhost.desc',
          'page.privacy.verify_checkable_export.desc',
        ],
      },
    ],
  },
  {
    icon: Globe,
    titleKey: 'page.privacy.third_party.title',
    color: 'text-cyan',
    borderColor: 'border-cyan/30',
    bgColor: 'bg-cyan/5',
    iconBg: 'bg-cyan/10',
    items: [
      {
        type: 'third-party',
        labelKey: 'page.privacy.third_party_llm.label',
        detailKeys: [
          'page.privacy.third_party_llm_providers.desc',
          'page.privacy.third_party_llm_only.desc',
          'page.privacy.third_party_llm_ollama.desc',
          'page.privacy.third_party_llm_scope.desc',
        ],
      },
    ],
    // 服务商名是品牌专名，不翻译（契约 6.11）。
    providers: [
      { name: 'Anthropic', icon: Bot, color: 'text-brand-primary' },
      { name: 'OpenAI', icon: Cpu, color: 'text-cyan' },
      { name: 'DeepSeek', icon: Globe, color: 'text-warm-orange' },
      { name: 'Ollama', icon: Server, color: 'text-brand-primary' },
    ],
  },
  {
    icon: Trash2,
    titleKey: 'page.privacy.retention.title',
    color: 'text-brand-primary',
    borderColor: 'border-brand-primary/30',
    bgColor: 'bg-brand-primary/5',
    iconBg: 'bg-brand-primary/10',
    items: [
      {
        type: 'retention',
        labelKey: 'page.privacy.retention_policy.label',
        detailKeys: [
          'page.privacy.retention_policy_forever.desc',
          'page.privacy.retention_policy_export.desc',
          // 这份清单是逐项对着 user_data_service.delete_user_data 的实现写的。
          // 加了新表就必须同步加进来，否则清单会慢慢变成"看起来删干净了"。
          'page.privacy.retention_policy_delete.desc',
          'page.privacy.retention_policy_exception.desc',
        ],
      },
    ],
  },
]

function ItemBadge({ type }: { type: string }) {
  // 这张表在**渲染期**求值，所以直接 t() 是安全的（模块级常量才必须存 key）。
  const config: Record<string, { icon: React.ElementType; label: string; className: string }> = {
    collect: { icon: CheckCircle2, label: t('page.privacy.collect.badge'), className: 'bg-brand-primary/10 text-brand-primary' },
    'no-collect': { icon: XCircle, label: t('page.privacy.no_collect.badge'), className: 'bg-severity-critical/10 text-severity-critical' },
    key: { icon: Lock, label: t('page.privacy.key.badge'), className: 'bg-cyan/10 text-cyan' },
    use: { icon: Eye, label: t('page.privacy.use.badge'), className: 'bg-cyan/10 text-cyan' },
    security: { icon: ShieldCheck, label: t('page.privacy.security.badge'), className: 'bg-brand-primary/10 text-brand-primary' },
    'third-party': { icon: Wifi, label: t('page.privacy.third_party.badge'), className: 'bg-cyan/10 text-cyan' },
    retention: { icon: Trash2, label: t('page.privacy.retention.badge'), className: 'bg-brand-primary/10 text-brand-primary' },
    verify: { icon: ShieldCheck, label: t('page.privacy.verify.badge'), className: 'bg-brand-primary/10 text-brand-primary' },
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
  useDocumentTitle('page.privacy.meta.title')

  return (
    // 长文排版：max-w-3xl 收阅读宽度；正文 leading-7；段前距大于段后距（space-y-8 / mb-4）；
    // 邮箱等长串加 break-all 防移动端横向溢出。
    <div className="max-w-3xl mx-auto px-4 py-8 animate-fade-in">
      <div className="mb-10">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-secondary transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" strokeWidth={1.25} />
          {t('page.privacy.header.link')}
        </Link>
        <h1 className="text-3xl md:text-4xl font-bold text-gradient-green font-display mb-3">
          {t('page.privacy.header.title')}
        </h1>
        <p className="text-text-secondary">
          {t('page.privacy.header.subtitle')}
        </p>
        <div className="flex items-center gap-2 mt-4 text-xs text-text-muted">
          <ShieldCheck className="w-4 h-4 text-brand-primary" strokeWidth={1.25} />
          <span>{t('page.privacy.header.meta')}</span>
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
              <div className="flex items-center gap-3 mb-4">
                <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', section.iconBg)}>
                  <SectionIcon className={cn('w-5 h-5', section.color)} strokeWidth={1.25} />
                </div>
                <h2 className={cn('text-xl font-semibold font-display', section.color)}>
                  {t(section.titleKey)}
                </h2>
              </div>

              <div className="space-y-5">
                {section.items.map((item, ii) => (
                  <div key={ii} className="pl-1">
                    <div className="flex items-center gap-2 mb-3">
                      <ItemBadge type={item.type} />
                      <span className="text-sm font-medium text-text-primary">{t(item.labelKey)}</span>
                    </div>
                    <ul className="space-y-2 ml-1">
                      {item.detailKeys.map((detailKey, di) => (
                        <li key={di} className="flex items-start gap-2.5 text-sm text-text-secondary">
                          <span className={cn('mt-1.5 w-1 h-1 rounded-full shrink-0', section.color === 'text-cyan' ? 'bg-cyan' : 'bg-brand-primary')} />
                          {t(detailKey)}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>

              {section.providers && (
                <div className="mt-5 pt-4 border-t border-border/50">
                  <p className="text-xs text-text-muted mb-3">{t('page.privacy.third_party_providers.label')}</p>
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
            <h2 className="text-xl font-semibold text-cyan font-display">{t('page.privacy.contact.title')}</h2>
          </div>
          <p className="text-sm text-text-secondary mb-3">
            {t('page.privacy.contact.desc')}
          </p>
          <a
            href="https://github.com/jedi-ling/audiencelens/issues"
            target="_blank"
            rel="noreferrer"
            className="inline-flex max-w-full items-center gap-2 px-4 py-2 rounded-lg bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-colors text-sm font-medium break-all"
          >
            <Mail className="w-4 h-4" strokeWidth={1.25} />
            GitHub Issues
          </a>
        </section>

        <div className="text-center py-6 border-t border-border/50">
          <p className="text-xs text-text-muted">
            {t('page.privacy.footer.desc')}
          </p>
        </div>
      </div>
    </div>
  )
}
