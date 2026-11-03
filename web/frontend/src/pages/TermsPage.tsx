/**
 * 服务条款。
 *
 * 写作纪律与隐私政策一致：**只写这套代码今天真做得到的事**，不写行业模板里
 * 那些听起来很正式但本产品根本没有的条款（SLA 可用性承诺、7×24 支持、
 * 企业级数据隔离…）。本仓库历史上因为"文案写了引擎没有"翻过车，条款比落地页
 * 更不能这么写——落地页夸大是营销问题，条款夸大是可以被追责的承诺。
 *
 * 因此这一页里的每条限制都能在代码里指出对应事实源：
 *   · 不保证可用性        —— 单机部署，进程内队列，无冗余（job_service.InProcessBackend）
 *   · 输出仅供参考        —— 合成人格不是真人，报告页 LimitationsSection 一直这么写
 *   · 免费额度可变        —— plan_service 的限额是后台可改的运行时配置
 *   · 无自助退款流程      —— 没有接任何支付，退款只能人工处理
 *   · 账号可被停用        —— admin PUT /users/{id} is_active，确实存在这个能力
 *
 * ⚠️ 这是一份**通用模板性质**的条款，不是律师审阅过的法律文件。正式商业化
 * （尤其开始收费）前应当请专业人士过一遍，特别是责任限制与管辖条款。
 * 这句话也写进了页面里给用户看——不写等于暗示它有法律效力背书。
 */

import { Link } from 'react-router'
import {
  ArrowLeft,
  ScrollText,
  AlertTriangle,
  Ban,
  CreditCard,
  Gavel,
  Mail,
  ShieldQuestion,
  UserCog,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { t, Trans } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import type { PlainMessageKey } from '@/i18n/keys.gen'
import { ICP_TEXT } from '@/lib/site'

/** 与隐私政策同一个联系渠道：仓库的 GitHub Issues（界面上不放任何邮箱地址）。 */
const CONTACT_URL = 'https://github.com/jedi-ling/audiencelens/issues'

/**
 * 章节表。存的是 **key 不是文案**：这个数组在模块求值时就固定了，存翻译结果
 * 的话切换语言不会重新求值，整页条款会一直停在打开页面时的那种语言。
 * 与 Layout.tsx 的 navItems 同一条规矩。
 */
const sections: {
  icon: React.ElementType
  titleKey: PlainMessageKey
  color: string
  borderColor: string
  bgColor: string
  iconBg: string
  items: { labelKey: PlainMessageKey; detailKeys: PlainMessageKey[] }[]
}[] = [
  {
    icon: ScrollText,
    titleKey: 'page.terms.service.title',
    color: 'text-brand-primary',
    borderColor: 'border-brand-primary/30',
    bgColor: 'bg-brand-primary/5',
    iconBg: 'bg-brand-primary/10',
    items: [
      {
        labelKey: 'page.terms.service_provides.label',
        detailKeys: [
          'page.terms.service_provides_review.desc',
          'page.terms.service_provides_hypothesis.desc',
          'page.terms.service_provides_byok.desc',
        ],
      },
      {
        labelKey: 'page.terms.service_not.label',
        detailKeys: [
          // 这三条不是免责套话，是这个产品的事实边界，报告页每次都会展示同样的说明
          'page.terms.service_not_usertest.desc',
          'page.terms.service_not_research.desc',
          'page.terms.service_not_advice.desc',
        ],
      },
    ],
  },
  {
    icon: AlertTriangle,
    titleKey: 'page.terms.availability.title',
    color: 'text-warm-orange',
    borderColor: 'border-warm-orange/30',
    bgColor: 'bg-warm-orange/5',
    iconBg: 'bg-warm-orange/10',
    items: [
      {
        labelKey: 'page.terms.availability_sla.label',
        detailKeys: [
          // 说清楚而不是含糊其辞：单人运营 + 单机部署，给 SLA 就是空头支票
          'page.terms.availability_sla_asis.desc',
          'page.terms.availability_sla_solo.desc',
          'page.terms.availability_sla_maintenance.desc',
          'page.terms.availability_sla_upstream.desc',
        ],
      },
      {
        labelKey: 'page.terms.availability_data.label',
        detailKeys: [
          'page.terms.availability_data_backup.desc',
          'page.terms.availability_data_copy.desc',
          'page.terms.availability_data_export.desc',
        ],
      },
    ],
  },
  {
    icon: UserCog,
    titleKey: 'page.terms.account.title',
    color: 'text-cyan',
    borderColor: 'border-cyan/30',
    bgColor: 'bg-cyan/5',
    iconBg: 'bg-cyan/10',
    items: [
      {
        labelKey: 'page.terms.account_duty.label',
        detailKeys: [
          'page.terms.account_duty_password.desc',
          'page.terms.account_duty_rights.desc',
          'page.terms.account_duty_lawful.desc',
        ],
      },
      {
        labelKey: 'page.terms.account_forbidden.label',
        detailKeys: [
          'page.terms.account_forbidden_bypass.desc',
          'page.terms.account_forbidden_farming.desc',
          'page.terms.account_forbidden_probing.desc',
          'page.terms.account_forbidden_resale.desc',
        ],
      },
      {
        labelKey: 'page.terms.account_enforcement.label',
        detailKeys: [
          // 这个能力确实存在（admin PUT /users/{id} 的 is_active），所以敢写
          'page.terms.account_enforcement_suspend.desc',
          'page.terms.account_enforcement_appeal.desc',
        ],
      },
    ],
  },
  {
    icon: CreditCard,
    titleKey: 'page.terms.billing.title',
    color: 'text-brand-primary',
    borderColor: 'border-brand-primary/30',
    bgColor: 'bg-brand-primary/5',
    iconBg: 'bg-brand-primary/10',
    items: [
      {
        labelKey: 'page.terms.billing_payment.label',
        detailKeys: [
          // 与定价页保持同一口径：在线支付确实还没接，不能在条款里假装有
          'page.terms.billing_payment_manual.desc',
          'page.terms.billing_payment_quota.desc',
          'page.terms.billing_payment_byok.desc',
        ],
      },
      {
        labelKey: 'page.terms.billing_refund.label',
        detailKeys: [
          'page.terms.billing_refund_manual.desc',
          'page.terms.billing_refund_used.desc',
        ],
      },
    ],
  },
  {
    icon: ShieldQuestion,
    titleKey: 'page.terms.ip.title',
    color: 'text-cyan',
    borderColor: 'border-cyan/30',
    bgColor: 'bg-cyan/5',
    iconBg: 'bg-cyan/10',
    items: [
      {
        labelKey: 'page.terms.ip_yours.label',
        detailKeys: [
          'page.terms.ip_yours_own.desc',
          'page.terms.ip_yours_no_training.desc',
          'page.terms.ip_yours_free_use.desc',
        ],
      },
      {
        labelKey: 'page.terms.ip_ours.label',
        detailKeys: [
          'page.terms.ip_ours_oss.desc',
          'page.terms.ip_ours_personas.desc',
        ],
      },
    ],
  },
  {
    icon: Gavel,
    titleKey: 'page.terms.liability.title',
    color: 'text-warm-orange',
    borderColor: 'border-warm-orange/30',
    bgColor: 'bg-warm-orange/5',
    iconBg: 'bg-warm-orange/10',
    items: [
      {
        labelKey: 'page.terms.liability_cap.label',
        detailKeys: [
          'page.terms.liability_cap_indirect.desc',
          'page.terms.liability_cap_amount.desc',
        ],
      },
      {
        labelKey: 'page.terms.liability_change.label',
        detailKeys: [
          'page.terms.liability_change_notice.desc',
          'page.terms.liability_change_accept.desc',
        ],
      },
      {
        labelKey: 'page.terms.liability_nature.label',
        detailKeys: [
          // 不写这一句，等于暗示它经过法律审阅
          'page.terms.liability_nature_unreviewed.desc',
          'page.terms.liability_nature_mandatory.desc',
        ],
      },
    ],
  },
]

export default function TermsPage() {
  useDocumentTitle('page.terms.meta.title')

  return (
    // 与隐私政策同一套长文排版：max-w-3xl 收阅读宽度，段前距大于段后距
    <div className="max-w-3xl mx-auto px-4 py-8 animate-fade-in">
      <div className="mb-10">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-secondary transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" strokeWidth={1.25} />
          {t('page.terms.header.link')}
        </Link>
        <h1 className="text-3xl font-display font-semibold text-text-primary mb-3">{t('page.terms.header.title')}</h1>
        <p className="text-text-secondary">
          {t('page.terms.header.subtitle')}
        </p>
        <p className="mt-3 text-sm text-text-muted">{t('page.terms.header.meta')}</p>
      </div>

      <div className="space-y-8">
        {sections.map((section) => {
          const SectionIcon = section.icon
          return (
            <section
              key={section.titleKey}
              className={cn(
                'rounded-2xl border p-6',
                section.borderColor,
                section.bgColor,
              )}
            >
              <div className="flex items-center gap-3 mb-4">
                <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', section.iconBg)}>
                  <SectionIcon className={cn('w-5 h-5', section.color)} strokeWidth={1.25} />
                </div>
                <h2 className="text-lg font-display font-semibold text-text-primary">
                  {t(section.titleKey)}
                </h2>
              </div>

              <div className="space-y-5">
                {section.items.map((item) => (
                  <div key={item.labelKey}>
                    <h3 className="text-sm font-medium text-text-primary mb-2">{t(item.labelKey)}</h3>
                    <ul className="space-y-2">
                      {item.detailKeys.map((detailKey) => (
                        <li key={detailKey} className="flex items-start gap-2.5 text-sm text-text-secondary">
                          <span className="mt-1.5 w-1 h-1 rounded-full bg-text-muted shrink-0" />
                          <span className="leading-6">{t(detailKey)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </section>
          )
        })}
      </div>

      <section className="mt-8 rounded-2xl border border-border bg-bg-card p-6">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-lg bg-bg-secondary flex items-center justify-center">
            <Ban className="w-5 h-5 text-text-muted" strokeWidth={1.25} />
          </div>
          <h2 className="text-lg font-display font-semibold text-text-primary">{t('page.terms.termination.title')}</h2>
        </div>
        <p className="text-sm leading-6 text-text-secondary">
          {t('page.terms.termination.desc')}
        </p>
      </section>

      <section className="mt-8 text-center">
        <div className="inline-flex items-center gap-2 mb-3 text-text-muted">
          <Mail className="w-4 h-4" strokeWidth={1.25} />
          <span className="text-sm">{t('page.terms.contact.hint')}</span>
        </div>
        <div>
          <a
            href={CONTACT_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex max-w-full items-center gap-2 px-4 py-2 rounded-lg bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-colors text-sm font-medium break-all"
          >
            <Mail className="w-4 h-4 shrink-0" strokeWidth={1.25} />
            GitHub Issues
          </a>
        </div>
        {/* 链接文字不拆成单独的 key：拆了之后英文语序改不动，只能硬凑成
            "另请阅读 + 隐私政策 + ，了解…" 的中式语序（契约 3.4 例 6）。 */}
        <p className="mt-6 text-sm text-text-muted">
          <Trans
            k="page.terms.related.desc"
            slots={{
              privacy: (s) => (
                <Link to="/privacy" className="text-cyan hover:underline">
                  {s}
                </Link>
              ),
            }}
          />
        </p>

        {/* 备案主体信息。条款是一份协议，用户有权知道对方是谁——
            只在页脚放一个备案号，等于告诉用户"有备案"但不告诉他跟谁签的约。
            备案号来自构建期 VITE_ICP_TEXT（lib/site.ts），不设置时整行不渲染。
            它**刻意不进 key 表**：工信部要求逐字符原样公示，翻译或改写都是违规。 */}
        {ICP_TEXT && (
          <p className="mt-4 text-xs text-text-muted">
            {t('page.terms.filing.label')}
            <a
              href="https://beian.miit.gov.cn/"
              target="_blank"
              rel="noopener noreferrer"
              className="mx-1 hover:text-text-secondary transition-colors"
            >
              {ICP_TEXT}
            </a>
          </p>
        )}
      </section>
    </div>
  )
}
