/**
 * 隐私政策。owner: agent-5（与 page.terms.ts 同一个 owner）。
 *
 * ⚠ 与服务条款同一条写作纪律：**只写这套代码今天真做得到的事**。
 * 这一页里好几条是被代码变更倒逼着改过的（对话消息落库、图片落盘、
 * 管理端可见范围），PrivacyPage.tsx 的注释逐条记录了改动理由。
 * 措辞是刻意保守的：写宽了就是对用户不实。
 *
 * 特别注意 usage_admin_* 这三条：早期版本写的是"不在你未要求时读取你的内容"，
 * 后台评审巡检上线后那句承诺已经不成立，于是改成如实说明边界。
 * 英文侧同理——不许翻回成一句听起来更好听的承诺。
 *
 * key 的组织方式与 page.terms.ts 一致：
 *   <section>.title / <section>_<group>.label / <section>_<group>_<点>.desc
 * 另有 <badge_type>.badge：ItemBadge 上那颗小标签，块名取自数据里的 type 值，
 * 这样"哪个 type 用哪条文案"在 key 上就能看出来。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '隐私政策',

  'header.link': '返回首页',
  'header.title': '隐私政策',
  'header.subtitle': '我们重视您的数据隐私。本政策说明 AudienceLens 如何收集、使用和保护您的数据。',
  'header.meta': '最后更新：2026 年 5 月',

  // ---- ItemBadge 的小标签。块名 = 数据里的 type 值 ----
  'collect.badge': '收集',
  'no_collect.badge': '不收集',
  'key.badge': '密钥',
  'use.badge': '用途',
  'security.badge': '安全',
  'third_party.badge': '第三方',
  'retention.badge': '保留',
  'verify.badge': '可验证',

  // ---- 数据收集说明 ----
  'collection.title': '数据收集说明',
  'collection_collected.label': '我们收集的数据',
  'collection_collected_materials.desc': '你上传的评审材料（文本、截图等），随评审记录长期保存，直到你删除',
  'collection_collected_config.desc': '选择的任务类型、角色配置、评审模式',
  'collection_collected_report.desc': '评审报告、各角色意见、你的追问与回复',
  // 对话持续化上线后新增的一类数据（详见 PrivacyPage.tsx 的注释）
  'collection_collected_chat.desc': '对话页里的往返消息（包括发起评审之前的澄清），存在服务器上，刷新与换设备后可继续',
  // 图片改为落盘之后新增
  'collection_collected_images.desc': '你在对话里上传的图片，以文件形式存在服务器磁盘上（数据库里只存引用，不存图片本身）',
  'collection_collected_account.desc': '注册邮箱与密码哈希（仅注册用户；密码用 PBKDF2-HMAC-SHA256 加盐哈希，我们无法还原）',
  'collection_collected_usage.desc': '用量记录：每次评审的 token 数、花费、时间',
  'collection_not.label': '我们不收集的数据',
  'collection_not_history.desc': '不收集浏览历史、不做跨站追踪',
  'collection_not_fingerprint.desc': '不收集设备指纹、不接入第三方广告或分析 SDK',
  'collection_not_identity.desc': '除注册邮箱外，不主动索取任何身份信息（不要手机号、不要实名）',
  'collection_apikey.label': 'API Key 处理',
  'collection_apikey_encrypted.desc': '你的 LLM API Key 加密后存进数据库（Fernet / AES-128-CBC + HMAC 认证加密）',
  'collection_apikey_separate.desc': '加密密钥与登录令牌密钥分离配置，轮换登录密钥不会导致密钥失效',
  'collection_apikey_masked.desc': '页面上只回显掩码（如 sk-ant-…4f2a）；数据导出也只给掩码，不含明文',
  'collection_apikey_delete.desc': '你可以随时在设置页删除它',

  // ---- 数据使用说明 ----
  'usage.title': '数据使用说明',
  'usage_purpose.label': '数据用途',
  'usage_purpose_single.desc': '你的材料只用于这一次评审：发给你选定的模型服务商，生成给你看的报告',
  'usage_purpose_retained.desc': '材料与报告会随评审记录保存，方便你回看历史、继续追问——直到你自己删除',
  'usage_purpose_isolated.desc': '评审结果仅你本人可访问（按账号隔离；未登录时按匿名身份隔离）',
  'usage_never.label': '我们不会做的事',
  'usage_never_training.desc': '不用你的内容训练任何模型——我们不训练模型，也不向任何人出售或共享你的数据',
  'usage_never_showcase.desc': '不拿你的项目内容做案例展示、宣传素材或公开样本',
  'usage_never_copy.desc': '运维排障不会把你的材料复制到别处，也不会转手给任何第三方',
  'usage_admin.label': '管理端可见范围（我们如实说明）',
  'usage_admin_access.desc': '为处理客诉、排查滥用、核对计费争议，运营方可以查看评审内容，不需要你先主动求助',
  'usage_admin_audit.desc': '这类访问会记入后台审计日志（时间、被查看的评审），但目前不会主动通知你',
  'usage_admin_unchanged.desc': '这不改变上面那条：内容不会被用来训练模型、做案例展示，或转手给任何第三方',

  // ---- 数据安全措施 ----
  'security.title': '数据安全措施',
  'security_tech.label': '技术保障',
  'security_tech_key.desc': 'API Key 用 Fernet 对称加密后落库（AES-128-CBC + HMAC-SHA256 认证加密）',
  'security_tech_password.desc': '登录密码用 PBKDF2-HMAC-SHA256（20 万轮）加盐哈希，不可还原',
  'security_tech_token.desc': '邮箱验证与密码重置令牌只存哈希摘要，一次性、可过期',
  'security_tech_cors.desc': 'CORS 严格白名单 + 安全响应头 + WebSocket Origin 验证',
  'security_tech_upload.desc': '上传类型/大小限制，分块流式读取，超限即中止',

  // ---- 你不必只听我们的承诺 ----
  'verify.title': '你不必只听我们的承诺',
  'verify_checkable.label': '可验证，而不是只能相信',
  'verify_checkable_oss.desc': '代码开源：这一页写的每条承诺，都能在源码里查证是否属实',
  'verify_checkable_byok.desc': '自带密钥（BYOK）：模型调用用你自己的额度，账单和用量都在你自己的服务商后台',
  'verify_checkable_hosted.desc': '用本站（托管形态）时：材料会先上传到本站服务器并落库，再由服务器代你调用模型——不经过服务器是做不到的，所以我们不这么说',
  'verify_checkable_selfhost.desc': '要做到"数据不出你的机器"，只有自建或本地跑 CLI / Python / MCP 这一条路：那时材料从头到尾在你的机器上，我们连接触的机会都没有',
  'verify_checkable_export.desc': '随时带走或删干净：设置页两个按钮，不用发邮件申请、不用等人工审核',

  // ---- 第三方服务 ----
  'third_party.title': '第三方服务',
  'third_party_llm.label': 'LLM 服务商',
  'third_party_llm_providers.desc': '使用 Anthropic / OpenAI / DeepSeek / Ollama API 进行 AI 评审',
  'third_party_llm_only.desc': '除你自行选择的 LLM 服务商外，我们不把你的材料转给任何第三方',
  'third_party_llm_ollama.desc': 'Ollama 档指向的是「运行本系统的那台机器」的 localhost：你自建时它就是你的机器，用本站时它是本站服务器——不是你的电脑',
  'third_party_llm_scope.desc': '所以"数据不离开用户设备"只在自建 / CLI / Python / MCP 形态下成立，托管形态下不成立',
  'third_party_providers.label': '支持的 LLM 服务商',

  // ---- 数据保留 ----
  'retention.title': '数据保留',
  'retention_policy.label': '保留策略',
  'retention_policy_forever.desc': '评审记录保存在服务器数据库，直到你主动删除——我们不设自动过期',
  'retention_policy_export.desc': '设置页可「导出我的全部数据」，一份 JSON 带走全部内容',
  // 这份清单是逐项对着 user_data_service.delete_user_data 的实现写的。
  // 后端加了新表就必须同步改这条，否则清单会慢慢变成"看起来删干净了"。
  'retention_policy_delete.desc': '设置页可「删除我的账号与数据」：评审、材料、报告、追问、对话记录、上传的图片（磁盘上的字节一并删除）、伦理体检记录（含内容摘录）、API Key、账号本身立即物理删除',
  'retention_policy_exception.desc': '例外（我们如实说明）：用量与兑换流水会保留，但 user_id 会被改写成不可回指的墓碑标识——财务对账所需，此后无法关联到你本人',

  // ---- 联系方式与页脚 ----
  'contact.title': '联系方式',
  'contact.desc': '如果您对本隐私政策有任何疑问或建议，请通过以下方式联系我们：',
  'footer.desc': 'AudienceLens 致力于保护您的数据隐私与安全',
} satisfies Messages
