/**
 * 设置页：账户 / API Key（BYOK）/ 用量与兑换 / 数据与隐私。owner: agent-3。
 *
 * 动手前先看这四条：
 *
 * 1. **删号要用户敲的那句中文不在本文件里。** 它是凭据不是文案，走
 *    `common.action.delete_account_phrase`（后端 platform.py 做的是中文字面量
 *    相等比较）。本文件只有提示语 `delete_confirm.label`，用 {{phrase}} 把那句
 *    凭据插进来；英文侧必须写清"照着敲下面这句中文"，否则英文用户永远删不掉
 *    账号，而且报错还是中文。见契约 6.8。
 *
 * 2. **BYOK 那几条隐私说明的措辞是刻意保守的**：只陈述做了什么（加密落库、
 *    只显示脱敏形式、不转第三方），不做"绝对安全"这类承诺，最后一条把选择权
 *    交回用户（可以不填 / 可自建）。翻译时**不许加强语气**，加了就是在替产品
 *    许一个源码里查不到的诺。
 *
 * 3. 左侧导航项与右侧标题**各一条 key**，不合并：data 这一组两处措辞本来就
 *    不同（导航写"导出与删除"、标题写"数据与隐私"），合并会逼其中一处改文案。
 *
 * 4. 通用动作词不在这里重写：保存 / 删除 / 取消 → `common.action.*`，
 *    删除中… → `common.ui.deleting`，表单校验 → `common.validate.*`（契约 D11）。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '设置',

  'header.title': '设置',
  'header.desc': '账户、模型接入、用量与数据，都在这里管理。',

  /* ---------------- 左侧分组导航 ---------------- */
  // 总览曾是独立的 /dashboard 页面，与本页用量板块职责重叠、令人困惑，
  // 已合并成这里的第一个分区——总览只做"概览 + 跳转"，具体数字/管理操作
  // 仍归各自分区，不在总览里重复展示（避免两处各存一份、改一处忘一处）。
  'group_overview.label': '总览',
  'group_account.label': '账户',
  'group_model.label': '模型配置',
  'group_usage.label': '用量与兑换',
  'group_data.label': '数据与隐私',

  'section_overview.tab': '战绩与入口',
  'section_account.tab': '个人信息',
  'section_model.tab': 'API Key（BYOK）',
  'section_usage.tab': '兑换码 · 用量统计',
  'section_data.tab': '导出与删除',

  /* ---------------- 右侧类目抬头 ---------------- */
  'section_overview.title': '战绩与入口',
  'section_overview.desc': '你的判断留档战绩、最近评审和常用入口，用量明细见「用量与兑换」。',
  'section_account.title': '个人信息',
  'section_account.desc': '管理你的账号信息与安全设置。',
  /** 游客态的抬头说明。与登录态是两个互斥分支，不是同一句话的变体。 */
  'section_account_guest.desc': '当前是游客身份，登录后可以改昵称、改密码、管理长期账号。',
  'section_model.title': 'API Key（BYOK）',
  'section_model.desc':
    '选择评审使用的大模型。支持 Anthropic 官方 API，以及 DeepSeek、Kimi、通义千问、智谱 GLM、Ollama 等任意 OpenAI 兼容服务。点「测试」可验证连接是否可用。',
  'section_usage.title': '兑换码 · 用量统计',
  'section_usage.desc': '用 CDK 兑换码换取评审次数，查看近 24 小时用量与累计 token 消耗。',
  'section_data.title': '数据与隐私',
  'section_data.desc': '你上传的材料、评审报告、对话记录随时可以导出或永久删除。',

  /* ---------------- 账户：游客态 ---------------- */
  'guest_card.title': '当前是游客身份',
  'guest_card.desc': '没有邮箱和密码可以改——登录或注册一个账号后，这里会显示昵称、密码修改入口。',
  'guest_card.cta': '去登录 / 注册',

  /* ---------------- 账户：登录态 ---------------- */
  'account_card.title': '账户信息',
  'account_card.desc': '当前登录：{{email}}',

  'name.label': '昵称',
  'name.placeholder': '怎么称呼你',
  'name.success': '昵称已更新',
  'name.error': '保存失败',
  'name.hint': '邮箱暂不支持自助修改。如需更换，请联系我们。',

  'password.label': '修改密码',
  'password_current.placeholder': '当前密码',
  'password_new.placeholder': '新密码（至少 8 位）',
  'password_confirm.placeholder': '再输一次新密码',
  'password.cta': '修改密码',
  'password.success': '密码已修改。其他设备上的登录已失效，本设备无需重新登录。',
  'password.error': '修改失败',
  'password.hint': '修改后其他设备会自动退出登录，本设备保持登录。如忘记当前密码，请退出后通过「忘记密码」重置。',

  'revoke.label': '登出所有设备',
  /** <strong> 是本设备也会被登出这件事——它是用户最容易忽略、代价最大的一条。 */
  'revoke.desc':
    '怀疑账号在别处被登录时用这个：立即作废本账号已签发的全部登录凭证。<strong>本设备也会退出</strong>，需要重新登录。你的 API Key 和评审记录不受影响。',
  'revoke.cta': '登出所有设备',
  'revoke.confirm': '确认登出所有设备？',
  'revoke.hint': '再点一次确认。确认后所有设备（含本机）都需要重新登录。',

  /* ---------------- BYOK ---------------- */
  'byok.title': 'API Key（BYOK）',
  'byok.desc': '自带 Key 评审：评审费用从你自己的模型账户扣除。',
  'byok.hint': '（不填也能用——平台提供共享 Key）',
  'byok.error': '平台服务不可用，BYOK Key 管理暂时无法使用',

  'key_item.meta': '· 最近使用 {{time}}',
  'key_item.error': '删除失败',

  'provider_anthropic.label': 'Anthropic 原生',
  'provider_anthropic.desc': 'Claude 官方 API',
  'provider_openai.label': 'OpenAI 兼容 / 国产模型',
  'provider_openai.desc': 'DeepSeek / Kimi / 通义千问 / 智谱 GLM / Ollama 等',

  'model_id.label': '模型 ID',
  'model_id.hint': '（留空自动按人格分级选型）',
  'model_id.placeholder': 'claude-sonnet-5（留空自动选）',
  'model_id_compat.placeholder': 'deepseek-v4-pro',
  'model_id.error': 'OpenAI 兼容格式需要填写模型名称',

  'api_base.label': 'API Base URL',
  'api_base.hint': '（留空用官方地址）',
  'api_base.placeholder': 'https://api.anthropic.com（或第三方中转地址）',
  'api_base_compat.placeholder': 'https://api.deepseek.com',

  'key_input.aria': 'API Key',
  'key_input.placeholder': 'sk-ant-…（输入 Anthropic API Key）',
  'key_input_compat.placeholder': '输入对应服务商的 API Key（Ollama 本地可留空）',

  'test.cta': '测试',
  'test.success': '连接成功',
  'test.error': '连接失败',
  'test.meta': '回复：{{sample}}',

  'save_key.cta': '保存 Key',
  'save_key.success': 'Key 已保存',
  'save_key.error': '保存失败',

  /* ---------------- BYOK 隐私说明（措辞刻意保守，见文件头第 2 条） ---------------- */
  'key_privacy.title': '你的 Key 会被怎么对待',
  'privacy_who.label': '谁能看到：',
  'privacy_who.desc':
    '没有人。加密后落库（Fernet / AES-128 + HMAC），本页面、数据导出、管理后台一律只显示脱敏形式（如 <code>sk-ant-…4f2a</code>）。',
  'privacy_use.label': '用来干嘛：',
  'privacy_use.desc': '只用于你自己发起的评审。不训练模型、不做案例展示、不转给任何第三方。',
  'privacy_device.label': '换设备：',
  'privacy_device.desc': 'Key 绑在账号上而不是浏览器上，换设备登录后自动可用，无需重填。',
  'privacy_optout.label': '不想给：',
  /** 平台有共享 Key 时的说法。 */
  'privacy_optout.desc': '可以不填，直接用平台提供的共享 Key。',
  /** 平台没有共享 Key 时的说法——两者互斥，各一条 key。 */
  'privacy_selfhost.desc': '本项目代码开源，可自行部署——自建时 Key 从头到尾在你自己的机器上。',
  'privacy_optout.hint': '也可以随时在本页删除它。',
  'privacy_source.desc': '以上每一条都能在源码里查证（本项目开源）。详见 <privacy>隐私政策</privacy>。',

  'multimodal.desc':
    '多模态支持：评审时可上传截图、设计稿、BP 页面。支持视觉的模型（Claude、GPT-4o、Qwen-VL、GLM-4V 等）会直接看图；不支持视觉的模型仅按文字评审，流程不会中断。',

  /* ---------------- CDK 兑换 ---------------- */
  'cdk.title': 'CDK 兑换码',
  /** quota_mode === 'credits' 时的说法。 */
  'cdk.desc': '兑换后获得评审次数：每次评审消耗 1 次，使用平台共享 Key 时生效。',
  /** quota_mode === 'plan' 时的说法。 */
  'cdk_plan.desc': '兑换后获得加量次数，套餐日限用完后自动垫付，使用平台共享 Key 时生效。',
  'cdk.hint': '匿名兑换自动创建游客身份，次数存在当前浏览器，请在清除缓存前使用完。',
  'cdk.placeholder': 'AL-XXXX-XXXX-XXXX',
  'cdk.cta': '兑换',
  /** 一句话里两个数字，复数只能挂一个（ICU 同限制）。这里挂本次到账的 count。 */
  'cdk.success': '兑换成功 +{{count}} 次，当前余额 {{balance}} 次',
  'cdk_guest.hint': '（已为你创建游客身份并自动登录）',
  'cdk.error': '兑换失败',

  /* ---------------- 用量 ---------------- */
  'usage.title': '近 24 小时用量',
  'usage.hint': '配额窗口：{{window}}',
  'usage_reviews.label': '评审次数',
  'usage_reviews.hint': '平台垫付 {{used}} / {{limit}}',
  'usage_credits.label': '剩余次数',
  'usage_bonus.label': '加量余额',
  'usage_credits.unit': '次',
  'usage_cost.label': '总费用',
  'usage_server_cost.label': '其中服务器 Key',
  'usage_tokens.label': '累计 token 用量（不按天重置）',
  'usage_tokens.unit': 'tokens',
  'usage_tokens.hint':
    '体验额度只约束平台垫付的部分：已用 {{used}} / {{limit}}。用自己的 API Key（BYOK）跑的不计入。',

  /* ---------------- 数据自主权 ---------------- */
  'data.title': '我的数据',
  'data.desc': '你上传的材料、评审报告、对话记录随时可以导出或永久删除。',
  'export.cta': '导出我的全部数据',
  'export.error': '导出失败',
  'delete_account.cta': '删除我的账号与数据',
  'delete_account.error': '删除失败',
  'delete_done.desc': '已删除：{{reviews}} 条评审、{{keys}} 个密钥。',
  'delete_done.hint': '计费流水已切断与你的关联（保留无主统计，见隐私政策）。',
  'delete_confirm.desc':
    '这会<strong>立即物理删除</strong>你的全部评审、上传材料、报告、追问记录和已保存的 API 密钥，<strong>不可撤销</strong>。<br/>计费与兑换流水会保留但切断与你的关联（财务对账所需，此后无法回指到你本人）。<br/>建议先「导出我的全部数据」留个备份。',
  /** {{phrase}} 恒等于 common.action.delete_account_phrase，见文件头第 1 条。 */
  'delete_confirm.label': '输入「{{phrase}}」以确认',
  'delete_confirm.cta': '确认永久删除',
  'delete_password.label': '账号密码',

  'footer.link': '隐私政策',

  /* ---------------- 总览分区（见 group_overview 上方注释） ---------------- */
  'overview_plan.value': '当前套餐：{{plan}}',
  'overview_usage.cta': '查看用量明细',

  'overview_scoreboard.title': '你 vs 评审团',
  'overview_scoreboard.cta': '查看完整对比 →',
  'overview_side_panel.label': '评审团',
  'overview_side_user.label': '你',
  'overview_sample.value_other': '{{count}} 个已验证样本',
  'overview_pending_one': '还有 {{count}} 条判断待回填',
  'overview_pending_other': '还有 {{count}} 条判断待回填',

  'overview_recent.title': '最近评审',
  'overview_recent.cta': '查看全部 →',
  'overview_recent_empty.title': '还没有评审记录',
  'overview_recent_empty.desc': '发起第一次评审后，最近的几条会出现在这里',

  'overview_links.title': '常用入口',
} satisfies Messages
