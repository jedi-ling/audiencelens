/**
 * Terms of Service. owner: agent-5 (same owner as page.privacy.ts).
 *
 * ⚠ 这份英文译文**尚未经法务复核**（契约 4.3 对本 agent 的备注）。
 * VITE_AL_LOCALES=zh,en 只是开发自测用；正式对英文用户上线前必须有人过一遍。
 *
 * 翻译纪律：**保住中文原件那种刻意保守的分寸**。
 * 中文侧每条限制都对应一个代码事实源（无 SLA / 单机部署 / 无自助退款 /
 * 账号可停用），措辞是故意直白的。英文不许用行业套话把限制说软——
 * "best-effort availability"、"enterprise-grade" 这类词一个都不要出现，
 * 它们会把"我们做不到"翻译成"我们大概能做到"，而条款夸大是可以被追责的。
 *
 * 撇号一律用 U+2019（’），不用 ASCII '，省得在单引号字符串里转义。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Terms of Service',

  'header.link': 'Back to home',
  'header.title': 'Terms of Service',
  'header.subtitle': 'By using AudienceLens you agree to the terms below. We have tried to write them plainly, rather than using language you cannot follow to hide where the real limits are.',
  'header.meta': 'Last updated: August 2026',

  'service.title': 'What the service is',
  'service_provides.label': 'What AudienceLens does',
  'service_provides_review.desc': 'Reviews the material you submit through several AI personas, each from a different angle, and produces one structured report',
  'service_provides_hypothesis.desc': 'Turns the report’s suggestions into falsifiable hypotheses, so you can test them with real people and fill the results back in',
  'service_provides_byok.desc': 'Lets you bring your own model key (BYOK), or use the platform key within its quota',
  'service_not.label': 'What it is not',
  'service_not_usertest.desc': 'It is not real user testing. The reviewers are AI personas, not a sample of any real user population',
  'service_not_research.desc': 'It is not market research. The spread of stances reflects model output and is not statistically representative',
  'service_not_advice.desc': 'It is not business, legal, financial or investment advice. Any decision you make on the basis of it is yours',

  'availability.title': 'Service availability',
  'availability_sla.label': 'We do not promise availability targets',
  // "as is" 用引号是照中文的「现状」处理。不要软化成 "we aim to provide"——
  // 中文这句的全部意义就是明确地不承诺。
  'availability_sla_asis.desc': 'The service is provided “as is”. We promise no uptime target (SLA), no response time, and no uninterrupted operation',
  'availability_sla_solo.desc': 'That is not disclaimer boilerplate, it is the actual situation: one person runs this, on a single machine, with no redundant instance',
  'availability_sla_maintenance.desc': 'Maintenance, upgrades or faults can make the service temporarily unavailable. We will try to give notice but cannot guarantee it',
  'availability_sla_upstream.desc': 'An outage at an upstream model provider (Anthropic, OpenAI and others) hits this service directly, and that part is outside our control',
  'availability_data.label': 'Data durability',
  'availability_data_backup.desc': 'The database is backed up automatically every day, and restores are rehearsed periodically to confirm the backups actually work',
  'availability_data_copy.desc': 'Even so, keep your own copy of anything that matters — any single-point system can lose data',
  'availability_data_export.desc': 'The settings page has “Export all my data”, so you can take your content with you at any time',

  'account.title': 'Accounts and acceptable use',
  'account_duty.label': 'Your responsibilities',
  'account_duty_password.desc': 'Keep your account password and API keys safe. Losses caused by a leaked password are yours to bear',
  'account_duty_rights.desc': 'You hold the rights to the material you submit, and submitting it infringes nobody else’s rights',
  'account_duty_lawful.desc': 'Do not submit unlawful material, or use the service to produce or spread unlawful or infringing content',
  'account_forbidden.label': 'What is not allowed',
  'account_forbidden_bypass.desc': 'Bypassing, or trying to bypass, quota limits, login checks or the paywall',
  'account_forbidden_farming.desc': 'Farming free quota in bulk, including registering multiple accounts and abusing redemption codes',
  'account_forbidden_probing.desc': 'Load testing, vulnerability scanning or any other unauthorised security testing of the service',
  'account_forbidden_resale.desc': 'Reselling or redistributing this service’s output while presenting it as research on real users',
  'account_enforcement.label': 'If these rules are broken',
  'account_enforcement_suspend.desc': 'We may cut the quota of an account that breaks the rules above, or disable it, without prior notice',
  'account_enforcement_appeal.desc': 'You can still appeal by writing to the address below. Disabling an account does not immediately delete its data',

  'billing.title': 'Fees and refunds',
  'billing_payment.label': 'How paying works today',
  'billing_payment_manual.desc': 'There is no online payment yet. Paid access is arranged with a redemption code, or by contacting us and having it handled by hand',
  'billing_payment_quota.desc': 'The free allowance and plan limits are runtime settings, and we may adjust them — we will try to say so before we do',
  'billing_payment_byok.desc': 'When you bring your own key (BYOK), your provider bills you for model calls directly and we are not part of it',
  'billing_refund.label': 'Refunds',
  'billing_refund_manual.desc': 'Since there is no self-service payment flow, refunds are handled by hand too: write to the address below and explain the situation',
  'billing_refund_used.desc': 'Reviews you have already spent are not normally refunded. Reviews that failed for reasons on our side are credited back to your balance',

  'ip.title': 'Intellectual property',
  'ip_yours.label': 'Your content stays yours',
  'ip_yours_own.desc': 'The material you submit, and the reports generated for you, are yours to own and to use',
  'ip_yours_no_training.desc': 'We will not train models on your content, use it as a showcase, or pass it to a third party (see the Privacy Policy)',
  'ip_yours_free_use.desc': 'You may use, modify and commercialise the reports freely, with no attribution required',
  'ip_ours.label': 'The service’s own intellectual property',
  'ip_ours_oss.desc': 'This project’s code is open source, under the licence declared in the repository',
  'ip_ours_personas.desc': 'The persona definitions, the review method and the prompt templates are public in that same repository — you can check them, and you can run them yourself',

  'liability.title': 'Limits of liability, and changes to these terms',
  'liability_cap.label': 'Limits of liability',
  'liability_cap_indirect.desc': 'To the fullest extent the law allows, we are not liable for indirect losses arising from use of this service — including but not limited to lost business opportunities, lost data, and losses from decisions made by acting on a review',
  'liability_cap_amount.desc': 'If you have paid, our total liability will not exceed what you actually paid over the preceding 12 months',
  'liability_change.label': 'Changes to these terms',
  'liability_change_notice.desc': 'We may revise these terms. Significant changes will be announced on the site, and the effective date at the bottom of this page will be updated',
  'liability_change_accept.desc': 'Continuing to use the service after a change takes effect counts as accepting it. If you do not accept it, you can export your data and delete your account',
  'liability_nature.label': 'What this document is',
  'liability_nature_unreviewed.desc': 'These are general-purpose terms that no practising lawyer has reviewed. They describe how this service actually works today; they are not a complete legal document',
  'liability_nature_mandatory.desc': 'Where mandatory rules in your jurisdiction conflict with these terms, those rules prevail',

  'termination.title': 'Ending the service',
  'termination.desc': 'You can delete your account and all of its data from the settings page at any time — nothing to apply for, no review to wait on. We may also have to stop running the service, whether for reasons beyond our control or operational ones. If that happens, we will announce it in advance and leave you enough time to export your data.',

  'contact.hint': 'Questions about these terms, or an appeal or refund to raise',
  'related.desc': 'Also read the <privacy>Privacy Policy</privacy> to see how we handle your data.',
  'filing.label': 'ICP filing holder for this service:',
} satisfies Messages
