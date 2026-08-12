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

/** 与隐私政策同一个联系邮箱。必须是真地址——example.com 是 RFC 2606 保留域名。 */
const CONTACT_EMAIL = 'REMOVED'

const sections = [
  {
    icon: ScrollText,
    title: '服务内容',
    color: 'text-brand-primary',
    borderColor: 'border-brand-primary/30',
    bgColor: 'bg-brand-primary/5',
    iconBg: 'bg-brand-primary/10',
    items: [
      {
        label: 'AudienceLens 提供什么',
        details: [
          '用多个 AI 人格从不同视角评审你提交的材料，产出一份结构化报告',
          '把报告里的建议转成可证伪的假设，供你做真人验证后回填结果',
          '你可以自带模型密钥（BYOK），也可以使用平台密钥（受额度限制）',
        ],
      },
      {
        label: '它不是什么',
        details: [
          // 这三条不是免责套话，是这个产品的事实边界，报告页每次都会展示同样的说明
          '不是真人用户测试。参与评审的是 AI 人格，不是任何真实用户群体的抽样',
          '不是市场调研报告。立场分布反映的是模型输出，不具备统计代表性',
          '不构成商业、法律、财务或投资建议。据此做出的任何决策由你自行负责',
        ],
      },
    ],
  },
  {
    icon: AlertTriangle,
    title: '服务可用性',
    color: 'text-warm-orange',
    borderColor: 'border-warm-orange/30',
    bgColor: 'bg-warm-orange/5',
    iconBg: 'bg-warm-orange/10',
    items: [
      {
        label: '我们不承诺可用性指标',
        details: [
          // 说清楚而不是含糊其辞：单人运营 + 单机部署，给 SLA 就是空头支票
          '本服务按「现状」提供，不承诺任何可用率（SLA）、响应时间或不中断运行',
          '这不是免责话术，是事实：目前由个人独立运营，单机部署，无冗余副本',
          '维护、升级或故障都可能导致服务临时不可用，我们会尽力但不保证提前通知',
          '上游模型服务商（Anthropic / OpenAI 等）的中断会直接影响本服务，这部分不在我们控制范围内',
        ],
      },
      {
        label: '数据可靠性',
        details: [
          '数据库每日自动备份，并定期做恢复演练验证备份可用',
          '尽管如此，仍建议你对重要材料自行留存副本——任何单点系统都可能丢数据',
          '设置页提供「导出我的全部数据」，随时可以把内容带走',
        ],
      },
    ],
  },
  {
    icon: UserCog,
    title: '账号与使用规范',
    color: 'text-cyan',
    borderColor: 'border-cyan/30',
    bgColor: 'bg-cyan/5',
    iconBg: 'bg-cyan/10',
    items: [
      {
        label: '你的责任',
        details: [
          '妥善保管账号密码与 API 密钥；因密码泄露导致的损失由你自行承担',
          '你对提交的材料拥有合法权利，且提交行为不侵犯任何第三方的权利',
          '不得提交违法内容，或利用本服务生成、传播违法或侵权内容',
        ],
      },
      {
        label: '禁止的行为',
        details: [
          '绕过或试图绕过额度限制、登录校验、付费墙',
          '自动化批量刷取免费额度（含注册多账号、滥用兑换码）',
          '对服务进行压力测试、漏洞扫描或其它未经授权的安全测试',
          '转售、二次分发本服务的输出并声称其为真人用户研究',
        ],
      },
      {
        label: '违规处理',
        details: [
          // 这个能力确实存在（admin PUT /users/{id} 的 is_active），所以敢写
          '违反上述规范的账号，我们可以在不事先通知的情况下限制额度或停用',
          '停用后你仍可通过下方邮箱申诉；数据不会因停用被立即删除',
        ],
      },
    ],
  },
  {
    icon: CreditCard,
    title: '费用与退款',
    color: 'text-brand-primary',
    borderColor: 'border-brand-primary/30',
    bgColor: 'bg-brand-primary/5',
    iconBg: 'bg-brand-primary/10',
    items: [
      {
        label: '当前的付费方式',
        details: [
          // 与定价页保持同一口径：在线支付确实还没接，不能在条款里假装有
          '目前没有接入在线支付。付费开通通过兑换码或联系我们人工处理',
          '免费额度、套餐限额都是运行时配置，我们可能调整——调整前会尽量提前说明',
          '使用自带密钥（BYOK）时，模型调用费用由你的服务商直接向你计费，与我们无关',
        ],
      },
      {
        label: '退款',
        details: [
          '因为没有自助支付流程，退款同样是人工处理：写信到下方邮箱说明情况',
          '已消耗的评审次数原则上不退；服务方原因导致评审失败的次数会退还到你的余额',
        ],
      },
    ],
  },
  {
    icon: ShieldQuestion,
    title: '知识产权',
    color: 'text-cyan',
    borderColor: 'border-cyan/30',
    bgColor: 'bg-cyan/5',
    iconBg: 'bg-cyan/10',
    items: [
      {
        label: '你的内容归你',
        details: [
          '你提交的材料、以及为你生成的报告，所有权和使用权都归你',
          '我们不会用你的内容训练模型、做案例展示或转给第三方（详见隐私政策）',
          '你可以自由使用、修改、商用生成的报告，无需署名',
        ],
      },
      {
        label: '本服务的知识产权',
        details: [
          '本项目代码开源，遵循仓库中声明的开源许可证',
          '人格设定、评审方法与提示词模板同样在仓库内公开，可查证、可自建',
        ],
      },
    ],
  },
  {
    icon: Gavel,
    title: '责任限制与条款变更',
    color: 'text-warm-orange',
    borderColor: 'border-warm-orange/30',
    bgColor: 'bg-warm-orange/5',
    iconBg: 'bg-warm-orange/10',
    items: [
      {
        label: '责任限制',
        details: [
          '在法律允许的最大范围内，我们不对使用本服务产生的间接损失负责——'
            + '包括但不限于商业机会损失、数据丢失、因采纳评审建议导致的决策损失',
          '如你已付费，我们的赔偿责任总额不超过你在此前 12 个月内实际支付的金额',
        ],
      },
      {
        label: '条款变更',
        details: [
          '我们可能修订本条款。重大变更会在站内公告，并更新本页底部的生效日期',
          '变更生效后继续使用即视为接受；不接受的话，可以导出数据并删除账号',
        ],
      },
      {
        label: '这份条款的性质',
        details: [
          // 不写这一句，等于暗示它经过法律审阅
          '这是一份通用条款，尚未经执业律师审阅。它反映的是本服务当前的真实运作方式，'
            + '而不是一份完备的法律文件',
          '如你所在司法辖区的强制性规定与本条款冲突，以强制性规定为准',
        ],
      },
    ],
  },
]

export default function TermsPage() {
  return (
    // 与隐私政策同一套长文排版：max-w-3xl 收阅读宽度，段前距大于段后距
    <div className="max-w-3xl mx-auto px-4 py-8 animate-fade-in">
      <div className="mb-10">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-secondary transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" strokeWidth={1.25} />
          返回首页
        </Link>
        <h1 className="text-3xl font-display font-semibold text-text-primary mb-3">服务条款</h1>
        <p className="text-text-secondary">
          使用 AudienceLens 即表示你同意以下条款。我们尽量把话说明白，
          不用听不懂的措辞掩盖真实的边界。
        </p>
        <p className="mt-3 text-sm text-text-muted">最后更新：2026 年 8 月</p>
      </div>

      <div className="space-y-8">
        {sections.map((section) => {
          const SectionIcon = section.icon
          return (
            <section
              key={section.title}
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
                  {section.title}
                </h2>
              </div>

              <div className="space-y-5">
                {section.items.map((item) => (
                  <div key={item.label}>
                    <h3 className="text-sm font-medium text-text-primary mb-2">{item.label}</h3>
                    <ul className="space-y-2">
                      {item.details.map((detail, di) => (
                        <li key={di} className="flex items-start gap-2.5 text-sm text-text-secondary">
                          <span className="mt-1.5 w-1 h-1 rounded-full bg-text-muted shrink-0" />
                          <span className="leading-6">{detail}</span>
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
          <h2 className="text-lg font-display font-semibold text-text-primary">终止服务</h2>
        </div>
        <p className="text-sm leading-6 text-text-secondary">
          你可以随时在设置页删除账号与全部数据，无需申请、无需等待审核。
          我们也可能因不可抗力或运营原因终止服务——若发生这种情况，
          我们会提前公告并保留足够时间让你导出数据。
        </p>
      </section>

      <section className="mt-8 text-center">
        <div className="inline-flex items-center gap-2 mb-3 text-text-muted">
          <Mail className="w-4 h-4" strokeWidth={1.25} />
          <span className="text-sm">对条款有疑问，或需要申诉、退款</span>
        </div>
        <div>
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="inline-flex max-w-full items-center gap-2 px-4 py-2 rounded-lg bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-colors text-sm font-medium break-all"
          >
            <Mail className="w-4 h-4 shrink-0" strokeWidth={1.25} />
            {CONTACT_EMAIL}
          </a>
        </div>
        <p className="mt-6 text-sm text-text-muted">
          另请阅读{' '}
          <Link to="/privacy" className="text-cyan hover:underline">
            隐私政策
          </Link>
          ，了解我们如何处理你的数据。
        </p>
      </section>
    </div>
  )
}
