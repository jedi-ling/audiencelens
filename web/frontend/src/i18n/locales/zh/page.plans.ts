/**
 * 定价 / 套餐页。owner: agent-8（PlansPage.tsx）。
 *
 * 页面本身的三条纪律写在 PlansPage.tsx 的文件头（价格从后端拉、没有在线支付、
 * 三档只差额度），这里只补 i18n 侧的三条：
 *
 * 1. **mailto 的 subject / body 不在这张表里。** 那三处的收件人是站方（solo dev）
 *    本人，不是终端用户——按界面语言翻，中文用户就会发出一封英文询价邮件，
 *    而收件人还是同一个中国人。它们恒为中文，见契约 12.2。
 *
 * 2. 配额/降级那几句原来是 f-string 式拼接（"每天 " + n + " 次评审"），
 *    数字与套餐名插在句子中间。英译语序不同，拆着拼必然译出「中文骨架 + 英文变量」，
 *    所以全部重构成带命名占位符的整句模板，语序交给译文自己决定。
 *
 * 3. 三条部署模式横幅是**互斥分支**，各一条 key。不做「当前部署{{x}}」这种
 *    把半句话当变量的写法——那等于把语序锁死成中文的。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '套餐与额度',

  'header.title': '套餐与额度',
  'header.desc':
    '使用自带 API Key（BYOK）跑评审不消耗平台额度。套餐额度仅适用于使用平台提供的 Key。',

  // ---- 部署模式横幅：三选一，互斥。<mode> 槽是原来的 <strong> ----
  banner_byok: '当前部署为 <mode>BYOK 模式</mode>：评审使用你自己填的 Key，套餐额度不生效。',
  // 部署方没有配置平台 Key 时（/api/health 的 server_key_present=false）置顶显示；
  // 此时下方套餐卡片里"每天 N 次评审 / 平台承担费用"两条会被隐藏，见 PlansPage。
  banner_no_platform_key: '<mode>平台 Key 当前未开放</mode>，目前仅支持自带 API Key（BYOK）。',
  banner_no_quota: '当前部署<mode>未开启配额限制</mode>，评审暂不受次数约束。',
  banner_credits: '当前部署按 <mode>CDK 次数制</mode>计费：每次评审消耗 1 次，用完可再兑。',

  'anon.hint':
    '未登录时用量保存在浏览器本地（共享匿名身份）。<register>注册账号</register>后，额度与账号绑定。',

  // ---- 我的额度 ----
  'quota.title': '我的额度（近 24 小时）',
  // 有具体语义的加载态才进 page.*，用角色段 pending（契约 6.7）
  'quota.pending': '正在读取用量…',
  'quota.error': '用量暂时无法读取',
  'tier.label': '当前档位',
  'used.label': '已用评审',
  // 同一个数字在两种配额模式下叫法不同：credits 模式它就是全部额度，
  // plan 模式它是日限用完后的加量。两条 key 而不是一条带条件的。
  'credits.label': '剩余次数',
  'bonus.label': '兑换码加量',
  // 数字与单位同属一句：英文的 credit/credits 要按数量选词，
  // 拆成「数字 + 固定单位」两段就没法选了。<unit> 槽保留原来那个小字号 span。
  'credits.value': '{{count}}<unit>次</unit>',
  'progress.label': '配额使用进度',
  'progress.hint': '配额周期：{{window}}',

  // ---- 套餐卡片 ----
  'list.title': '套餐',
  'list.pending': '正在读取套餐…',
  'list.error': '套餐信息加载失败',
  // 三档的一句话定位。档位名（plan.name）来自后端，不在这里。
  tagline_free: '入门体验',
  tagline_pro: '个人深度使用',
  tagline_team: '团队高频评审',
  'price.unit': '/ 月',
  // <n> 槽是原来那个 tabular-nums 的 <strong>，数字用 count 驱动英文复数
  feature_reviews: '每天 <n>{{count}}</n> 次评审',
  feature_cost: '平台承担模型调用费用',
  feature_byok: '自带 Key 不限次，不受额度约束',
  'card.badge': '当前使用',
  'card.label': '正在使用',
  'card.hint': '免费档 · 无需付费',
  'card.cta': '申请升级',

  // ---- 兑换 CDK ----
  'cdk.title': '兑换码（CDK）',
  cdk_desc_credits: '兑换后获得评审次数，每次评审消耗 1 次。',
  cdk_desc_plan: '兑换后获得加量次数，套餐日限用完后自动垫上。',
  'cdk.hint': '无需注册，匿名兑换后次数保存在当前浏览器。',
  // 兑换码的书写格式示例，不是文案：两侧字面相同是对的。
  'cdk.placeholder': 'AL-XXXX-XXXX-XXXX',
  'cdk.aria': '兑换码',
  'cdk.cta': '兑换',
  // 一句里两个数：复数挂 count（本次到账），balance 当普通插值（ICU 同限制）
  'cdk.success': '兑换成功 +{{count}} 次，当前余额 {{balance}} 次',
  'cdk.error': '兑换失败',
  'guest.hint': '（已为你创建游客身份并自动登录）',
  // 联系渠道是仓库的 GitHub Issues（PlansPage 的 REPO_ISSUES_URL），界面上不放邮箱。
  'request.hint': '需要兑换码？在 <mail>GitHub Issues</mail> 提交申请（不要贴邮箱等个人信息）。',

  // ---- 其他方式 ----
  'manual.title': '人工开通 Pro / Team',
  'manual.desc': '如需开通 Pro 或 Team 档，在 GitHub Issues 留言说明目标档位即可（issue 是公开的，不要贴邮箱等个人信息）。',
  'byok.title': '自带 API Key',
  'byok.desc':
    '填入自己的 API Key（Anthropic 原生，或任意 OpenAI 兼容服务），评审消耗你自己的 API 额度，不受平台次数和日限约束，token 费用由服务商直接结算。',
  'byok.cta': '去设置页填 Key',
} satisfies Messages
