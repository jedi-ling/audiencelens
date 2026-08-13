/**
 * 服务条款。owner: agent-5（与 page.privacy.ts 同一个 owner）。
 *
 * ⚠ 这一页是**法律文本**，不是普通 UI 文案。TermsPage.tsx 的文件头写死了它的
 * 写作纪律：只写这套代码今天真做得到的事，每条限制都能在代码里指出事实源
 * （无 SLA / 单机部署 / 无自助退款 / 账号可停用）。
 * 改这里的措辞前先去读那段文件头——落地页夸大是营销问题，条款夸大是可以被
 * 追责的承诺。宁可直白，也不要用行业套话把限制说得更软。
 *
 * key 的组织方式：块 = 页面上的结构块。
 *   <section>.title            章节标题
 *   <section>_<group>.label    章节里一组条款的小标题
 *   <section>_<group>_<点>.desc  这组里的一条
 * 逐条一个块名（而不是序号）是刻意的：条款会增删，序号会全部错位，
 * 而块名带语义的话，删掉一条只会让一个 key 消失，不影响其余。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '服务条款',

  'header.link': '返回首页',
  'header.title': '服务条款',
  'header.subtitle': '使用 AudienceLens 即表示你同意以下条款。我们尽量把话说明白，不用听不懂的措辞掩盖真实的边界。',
  'header.meta': '最后更新：2026 年 8 月',

  // ---- 服务内容 ----
  'service.title': '服务内容',
  'service_provides.label': 'AudienceLens 提供什么',
  'service_provides_review.desc': '用多个 AI 人格从不同视角评审你提交的材料，产出一份结构化报告',
  'service_provides_hypothesis.desc': '把报告里的建议转成可证伪的假设，供你做真人验证后回填结果',
  'service_provides_byok.desc': '你可以自带模型密钥（BYOK），也可以使用平台密钥（受额度限制）',
  // 这三条不是免责套话，是这个产品的事实边界，报告页每次都会展示同样的说明
  'service_not.label': '它不是什么',
  'service_not_usertest.desc': '不是真人用户测试。参与评审的是 AI 人格，不是任何真实用户群体的抽样',
  'service_not_research.desc': '不是市场调研报告。立场分布反映的是模型输出，不具备统计代表性',
  'service_not_advice.desc': '不构成商业、法律、财务或投资建议。据此做出的任何决策由你自行负责',

  // ---- 服务可用性 ----
  'availability.title': '服务可用性',
  'availability_sla.label': '我们不承诺可用性指标',
  'availability_sla_asis.desc': '本服务按「现状」提供，不承诺任何可用率（SLA）、响应时间或不中断运行',
  'availability_sla_solo.desc': '这不是免责话术，是事实：目前由个人独立运营，单机部署，无冗余副本',
  'availability_sla_maintenance.desc': '维护、升级或故障都可能导致服务临时不可用，我们会尽力但不保证提前通知',
  'availability_sla_upstream.desc': '上游模型服务商（Anthropic / OpenAI 等）的中断会直接影响本服务，这部分不在我们控制范围内',
  'availability_data.label': '数据可靠性',
  'availability_data_backup.desc': '数据库每日自动备份，并定期做恢复演练验证备份可用',
  'availability_data_copy.desc': '尽管如此，仍建议你对重要材料自行留存副本——任何单点系统都可能丢数据',
  'availability_data_export.desc': '设置页提供「导出我的全部数据」，随时可以把内容带走',

  // ---- 账号与使用规范 ----
  'account.title': '账号与使用规范',
  'account_duty.label': '你的责任',
  'account_duty_password.desc': '妥善保管账号密码与 API 密钥；因密码泄露导致的损失由你自行承担',
  'account_duty_rights.desc': '你对提交的材料拥有合法权利，且提交行为不侵犯任何第三方的权利',
  'account_duty_lawful.desc': '不得提交违法内容，或利用本服务生成、传播违法或侵权内容',
  'account_forbidden.label': '禁止的行为',
  'account_forbidden_bypass.desc': '绕过或试图绕过额度限制、登录校验、付费墙',
  'account_forbidden_farming.desc': '自动化批量刷取免费额度（含注册多账号、滥用兑换码）',
  'account_forbidden_probing.desc': '对服务进行压力测试、漏洞扫描或其它未经授权的安全测试',
  'account_forbidden_resale.desc': '转售、二次分发本服务的输出并声称其为真人用户研究',
  // 这个能力确实存在（admin PUT /users/{id} 的 is_active），所以敢写
  'account_enforcement.label': '违规处理',
  'account_enforcement_suspend.desc': '违反上述规范的账号，我们可以在不事先通知的情况下限制额度或停用',
  'account_enforcement_appeal.desc': '停用后你仍可通过下方邮箱申诉；数据不会因停用被立即删除',

  // ---- 费用与退款 ----
  'billing.title': '费用与退款',
  // 与定价页保持同一口径：在线支付确实还没接，不能在条款里假装有
  'billing_payment.label': '当前的付费方式',
  'billing_payment_manual.desc': '目前没有接入在线支付。付费开通通过兑换码或联系我们人工处理',
  'billing_payment_quota.desc': '免费额度、套餐限额都是运行时配置，我们可能调整——调整前会尽量提前说明',
  'billing_payment_byok.desc': '使用自带密钥（BYOK）时，模型调用费用由你的服务商直接向你计费，与我们无关',
  'billing_refund.label': '退款',
  'billing_refund_manual.desc': '因为没有自助支付流程，退款同样是人工处理：写信到下方邮箱说明情况',
  'billing_refund_used.desc': '已消耗的评审次数原则上不退；服务方原因导致评审失败的次数会退还到你的余额',

  // ---- 知识产权 ----
  'ip.title': '知识产权',
  'ip_yours.label': '你的内容归你',
  'ip_yours_own.desc': '你提交的材料、以及为你生成的报告，所有权和使用权都归你',
  'ip_yours_no_training.desc': '我们不会用你的内容训练模型、做案例展示或转给第三方（详见隐私政策）',
  'ip_yours_free_use.desc': '你可以自由使用、修改、商用生成的报告，无需署名',
  'ip_ours.label': '本服务的知识产权',
  'ip_ours_oss.desc': '本项目代码开源，遵循仓库中声明的开源许可证',
  'ip_ours_personas.desc': '人格设定、评审方法与提示词模板同样在仓库内公开，可查证、可自建',

  // ---- 责任限制与条款变更 ----
  'liability.title': '责任限制与条款变更',
  'liability_cap.label': '责任限制',
  'liability_cap_indirect.desc': '在法律允许的最大范围内，我们不对使用本服务产生的间接损失负责——包括但不限于商业机会损失、数据丢失、因采纳评审建议导致的决策损失',
  'liability_cap_amount.desc': '如你已付费，我们的赔偿责任总额不超过你在此前 12 个月内实际支付的金额',
  'liability_change.label': '条款变更',
  'liability_change_notice.desc': '我们可能修订本条款。重大变更会在站内公告，并更新本页底部的生效日期',
  'liability_change_accept.desc': '变更生效后继续使用即视为接受；不接受的话，可以导出数据并删除账号',
  // 不写这一句，等于暗示它经过法律审阅
  'liability_nature.label': '这份条款的性质',
  'liability_nature_unreviewed.desc': '这是一份通用条款，尚未经执业律师审阅。它反映的是本服务当前的真实运作方式，而不是一份完备的法律文件',
  'liability_nature_mandatory.desc': '如你所在司法辖区的强制性规定与本条款冲突，以强制性规定为准',

  // ---- 终止服务 ----
  'termination.title': '终止服务',
  'termination.desc': '你可以随时在设置页删除账号与全部数据，无需申请、无需等待审核。我们也可能因不可抗力或运营原因终止服务——若发生这种情况，我们会提前公告并保留足够时间让你导出数据。',

  // ---- 联系与关联文档 ----
  'contact.hint': '对条款有疑问，或需要申诉、退款',
  'related.desc': '另请阅读 <privacy>隐私政策</privacy>，了解我们如何处理你的数据。',
  // 备案主体信息。条款是一份协议，用户有权知道对方是谁。
  // 备案号本身（苏ICP备…）**不进 key 表**：工信部要求逐字符原样公示，
  // 翻译或改写都是违规，所以它留在 TermsPage.tsx 里当字面量。
  'filing.label': '本服务备案主体：',
} satisfies Messages
