/**
 * 材料字段的 label / placeholder。owner: agent-catalog-frontend。
 *
 * 契约 D5 的表里这一行的 zh 与 en 事实源**都是前端**：后端只认材料的
 * key（MaterialExtractor.TASK_FIELDS 按中文字面量匹配），根本没有 label
 * 这个概念。所以这份不是"后端拉不到时的离线兜底"，它就是唯一事实源，
 * 缺一条就等于那个输入框在英文界面上没有名字。
 *
 * ── key 的形状：为什么不是契约 §3.4 例 10 的那一种 ──
 * 例 10 写的是 `catalog.material.concept_review.一句话pitch` → `{label, placeholder}`，
 * 即四段 key 配一个对象值。它跑不起来，两处硬冲突：
 *   1. scripts/i18n-gen.mjs 的 loadLocale 要求资源文件是**扁平的字符串表**
 *      （值不是 string 直接 fail），对象值进不去；
 *   2. 拆成 `….一句话pitch.label` 是五段，而 gen 只允许 3 或 4 段。
 * 所以这里把"任务类型 + 材料 key"压进第 3 段（用 `__` 连接），第 4 段留给
 * 契约 §3.2 的角色闭集：
 *
 *     catalog.material.<task_type>__<wire_key>.label
 *     catalog.material.<task_type>__<wire_key>.placeholder
 *
 * 用 `__` 而不是 `.` 是因为 `.` 会被 gen 数成第五段。
 *
 * ── 中文 wire key 原样出现在 key 里，这是刻意的 ──
 * `一句话pitch` / `截图` / `游戏名称` 是 wire contract：CreateReviewPage 把它当
 * `materials[].type` 发给后端，后端按同样的中文字面量匹配。**永不翻译**。
 * 把它放进 key 段而不是值里，等于让"改了 wire key"表现为一条 t() 查不到 →
 * DEV 抛错 / PROD ⟦missing:…⟧，而不是"编译通过、界面正常、引擎提取不到材料"。
 * 这是契约 5.5 想要的那把锁在扁平字符串表下唯一还能保留的形态
 * （对象映射类型 MaterialOverlay 的 tsc 版本因为上面两条约束用不成）。
 * 契约 §3.3 禁止的是"把**中文原文**当 key"（source-as-key，即拿要显示的文案当键），
 * 这里放进 key 的是协议标识符，不是文案——两者在本仓恰恰必须能区分开。
 *
 * ── 源常量一个字不改（D6）──
 * 值是 src/lib/mock-data.ts 里 TASK_MATERIALS 的 label / placeholder 的**逐字副本**，
 * 由脚本抄出来的，不是手打的。中文界面现在走这张表而不是直接读源常量，
 * 是为了让 zh / en 只有一条代码路径（见 i18n/catalog.ts 的 getMaterialFields）——
 * 两条路径必然出现"中文好好的、英文是空的"这类只在一种语言下发生的 bug。
 * 代价是这份副本会与源常量漂移，防线见 getMaterialFields 里的 DEV 断言。
 *
 * ⚠ 已知卡口冲突（交付报告里已单列）：i18n-gen.mjs 的"[wire key]"断言检查的是
 * **值**是否落在 wire 字符串集合里，而本表有 16 条 zh label 恰好与自己的 wire key
 * 逐字相同（"游戏名称" 的 label 就叫 "游戏名称"）——那是源数据的巧合，不是有人
 * 把 wire key 抄进了文案表。这条断言需要 batch-0 放行，否则 i18n:check 会红。
 */
import type { Messages } from '@/i18n/types'

export default {
  // ---- concept_review ----
  'concept_review__一句话pitch.label': '一句话介绍',
  'concept_review__一句话pitch.placeholder': '用一句话描述你的游戏核心概念...',
  'concept_review__核心循环说明.label': '核心玩法循环',
  'concept_review__核心循环说明.placeholder': '描述游戏的核心循环：探索→战斗→...',
  'concept_review__竞品对比.label': '竞品参考',
  'concept_review__竞品对比.placeholder': '列出参考竞品，如：Dead Cells（战斗节奏）、Hollow Knight（探索深度）',
  'concept_review__目标受众.label': '目标受众',
  'concept_review__目标受众.placeholder': '描述目标玩家画像...',
  'concept_review__定价与平台.label': '定价与平台',
  'concept_review__定价与平台.placeholder': '如：抢先体验 $14.99，PC Steam首发',
  'concept_review__截图.label': '截图/视觉描述',
  'concept_review__截图.placeholder': '描述游戏视觉风格，或上传截图...',
  'concept_review__系统说明.label': '核心系统说明',
  'concept_review__系统说明.placeholder': '描述3-5个核心系统...',

  // ---- demo_first_play ----
  'demo_first_play__游戏名称.label': '游戏名称',
  'demo_first_play__游戏名称.placeholder': '输入游戏名称',
  'demo_first_play__核心循环说明.label': '核心玩法',
  'demo_first_play__核心循环说明.placeholder': '描述试玩版包含的核心玩法...',
  'demo_first_play__截图.label': '截图/视觉描述',
  'demo_first_play__截图.placeholder': '描述游戏画面风格...',
  'demo_first_play__实机视频.label': '实机视频描述',
  'demo_first_play__实机视频.placeholder': '描述视频内容或粘贴视频链接...',
  'demo_first_play__竞品对比.label': '竞品参考',
  'demo_first_play__竞品对比.placeholder': '列出参考竞品...',
  'demo_first_play__评价摘要.label': '已有评价',
  'demo_first_play__评价摘要.placeholder': '粘贴已有的玩家评价（如有）...',

  // ---- steam_page_review ----
  'steam_page_review__游戏名称.label': '游戏名称',
  'steam_page_review__游戏名称.placeholder': '输入游戏名称',
  'steam_page_review__截图.label': '胶囊图/截图描述',
  'steam_page_review__截图.placeholder': '描述Steam胶囊图和截图内容...',
  'steam_page_review__核心循环说明.label': '游戏简介',
  'steam_page_review__核心循环说明.placeholder': '粘贴Steam商店页的简短描述...',
  'steam_page_review__tags.label': '标签',
  'steam_page_review__tags.placeholder': '如：roguelite, metroidvania, pixel art',
  'steam_page_review__价格.label': '价格',
  'steam_page_review__价格.placeholder': '如：$19.99',
  'steam_page_review__评价摘要.label': '用户评价',
  'steam_page_review__评价摘要.placeholder': '粘贴已有的用户评价摘要...',
  'steam_page_review__demo.label': 'Demo信息',
  'steam_page_review__demo.placeholder': '是否有Demo，包含什么内容...',

  // ---- kickstarter_review ----
  'kickstarter_review__项目名称.label': '项目名称',
  'kickstarter_review__项目名称.placeholder': '输入众筹项目名称',
  'kickstarter_review__一句话pitch.label': '一句话介绍',
  'kickstarter_review__一句话pitch.placeholder': '项目的核心卖点...',
  'kickstarter_review__核心循环说明.label': '项目描述',
  'kickstarter_review__核心循环说明.placeholder': '描述项目的核心内容和特色...',
  'kickstarter_review__定价与平台.label': '回报档位',
  'kickstarter_review__定价与平台.placeholder': '列出各档位的价格和内容...',
  'kickstarter_review__截图.label': '视觉素材描述',
  'kickstarter_review__截图.placeholder': '描述众筹页的图片和视频内容...',
  'kickstarter_review__目标受众.label': '目标支持者',
  'kickstarter_review__目标受众.placeholder': '描述目标支持者画像...',

  // ---- discord_community_review ----
  'discord_community_review__社区名称.label': '社区名称',
  'discord_community_review__社区名称.placeholder': '如：Echoes of the Void 官方Discord',
  'discord_community_review__核心循环说明.label': '社区描述',
  'discord_community_review__核心循环说明.placeholder': '描述社区的主题和规模...',
  'discord_community_review__评价摘要.label': '近期帖子摘要',
  'discord_community_review__评价摘要.placeholder': '粘贴3-5条近期代表性帖子...',
  'discord_community_review__系统说明.label': '频道结构',
  'discord_community_review__系统说明.placeholder': '列出主要频道和规则...',
  'discord_community_review__竞品对比.label': '竞品社区对比',
  'discord_community_review__竞品对比.placeholder': '对比其他类似游戏的社区...',

  // ---- devlog_review ----
  'devlog_review__游戏名称.label': '游戏名称',
  'devlog_review__游戏名称.placeholder': '输入游戏名称',
  'devlog_review__核心循环说明.label': '开发日志内容',
  'devlog_review__核心循环说明.placeholder': '粘贴开发日志全文或摘要...',
  'devlog_review__评价摘要.label': '社区反馈',
  'devlog_review__评价摘要.placeholder': '粘贴社区对日志的反馈...',
  'devlog_review__截图.label': '配图描述',
  'devlog_review__截图.placeholder': '描述日志中的截图/GIF内容...',

  // ---- monetization_review ----
  'monetization_review__游戏名称.label': '游戏名称',
  'monetization_review__游戏名称.placeholder': '输入游戏名称',
  'monetization_review__定价与平台.label': '付费方案',
  'monetization_review__定价与平台.placeholder': '描述付费模型：买断/免费+内购/订阅...',
  'monetization_review__核心循环说明.label': '核心玩法',
  'monetization_review__核心循环说明.placeholder': '描述游戏核心循环...',
  'monetization_review__竞品对比.label': '竞品定价',
  'monetization_review__竞品对比.placeholder': '列出竞品的定价策略...',
  'monetization_review__评价摘要.label': '玩家反馈',
  'monetization_review__评价摘要.placeholder': '粘贴玩家对定价的反馈...',

  // ---- update_announcement_review ----
  'update_announcement_review__游戏名称.label': '游戏名称',
  'update_announcement_review__游戏名称.placeholder': '输入游戏名称',
  'update_announcement_review__核心循环说明.label': '更新内容',
  'update_announcement_review__核心循环说明.placeholder': '粘贴更新公告全文...',
  'update_announcement_review__评价摘要.label': '玩家反馈',
  'update_announcement_review__评价摘要.placeholder': '粘贴玩家对更新的反馈...',
  'update_announcement_review__截图.label': '更新截图描述',
  'update_announcement_review__截图.placeholder': '描述更新中的新内容截图...',

  // ---- localization_review ----
  'localization_review__游戏名称.label': '游戏名称',
  'localization_review__游戏名称.placeholder': '输入游戏名称',
  'localization_review__核心循环说明.label': '原文内容',
  'localization_review__核心循环说明.placeholder': '粘贴需要评审的原文文本...',
  'localization_review__系统说明.label': '翻译内容',
  'localization_review__系统说明.placeholder': '粘贴翻译后的文本...',
  'localization_review__竞品对比.label': '文化参考',
  'localization_review__竞品对比.placeholder': '描述目标文化的特殊考量...',

  // ---- looking_for_party_post ----
  'looking_for_party_post__游戏名称.label': '游戏名称',
  'looking_for_party_post__游戏名称.placeholder': '输入游戏名称',
  'looking_for_party_post__核心循环说明.label': '帖子内容',
  'looking_for_party_post__核心循环说明.placeholder': '粘贴组队帖全文...',
  'looking_for_party_post__目标受众.label': '目标玩家',
  'looking_for_party_post__目标受众.placeholder': '描述你想吸引什么样的玩家...',

  // ---- product_feedback_review ----
  'product_feedback_review__产品名称.label': '产品名称',
  'product_feedback_review__产品名称.placeholder': '输入产品或功能名称',
  'product_feedback_review__核心循环说明.label': '产品做什么',
  'product_feedback_review__核心循环说明.placeholder': '描述产品解决什么问题、用户怎么用...',
  'product_feedback_review__评价摘要.label': '已有用户反馈',
  'product_feedback_review__评价摘要.placeholder': '粘贴 3-5 条真实用户反馈、工单或评论...',
  'product_feedback_review__目标受众.label': '目标用户',
  'product_feedback_review__目标受众.placeholder': '描述目标用户画像与使用场景...',
  'product_feedback_review__竞品对比.label': '竞品参考',
  'product_feedback_review__竞品对比.placeholder': '列出用户可能拿来对比的竞品...',
  'product_feedback_review__截图.label': '界面截图描述',
  'product_feedback_review__截图.placeholder': '描述关键界面，或上传截图...',

  // ---- pricing_page_review ----
  'pricing_page_review__产品名称.label': '产品名称',
  'pricing_page_review__产品名称.placeholder': '输入产品名称',
  'pricing_page_review__定价与平台.label': '定价方案',
  'pricing_page_review__定价与平台.placeholder': '逐档列出：档位名称 / 价格 / 包含什么 / 限制是什么...',
  'pricing_page_review__核心循环说明.label': '定价页文案',
  'pricing_page_review__核心循环说明.placeholder': '粘贴定价页上的标题、卖点与说明文字...',
  'pricing_page_review__目标受众.label': '目标付费人群',
  'pricing_page_review__目标受众.placeholder': '你希望谁来买、他们的预算区间...',
  'pricing_page_review__竞品对比.label': '竞品定价',
  'pricing_page_review__竞品对比.placeholder': '列出竞品的档位与价格...',
  'pricing_page_review__截图.label': '页面截图描述',
  'pricing_page_review__截图.placeholder': '描述定价页的版式与视觉...',

  // ---- onboarding_review ----
  'onboarding_review__产品名称.label': '产品名称',
  'onboarding_review__产品名称.placeholder': '输入产品名称',
  'onboarding_review__核心循环说明.label': '引导流程步骤',
  'onboarding_review__核心循环说明.placeholder': '按顺序列出新用户从注册到第一次拿到价值的每一步...',
  'onboarding_review__目标受众.label': '新用户是谁',
  'onboarding_review__目标受众.placeholder': '描述新用户的背景、动机与已有认知...',
  'onboarding_review__系统说明.label': '首次价值时刻',
  'onboarding_review__系统说明.placeholder': '用户在哪一步第一次觉得「这东西有用」...',
  'onboarding_review__评价摘要.label': '流失反馈',
  'onboarding_review__评价摘要.placeholder': '粘贴新用户流失时的反馈或漏斗观察...',
  'onboarding_review__截图.label': '引导界面描述',
  'onboarding_review__截图.placeholder': '描述引导页面/提示的内容与顺序...',

  // ---- pitch_review ----
  'pitch_review__项目名称.label': '项目名称',
  'pitch_review__项目名称.placeholder': '输入项目或公司名称',
  'pitch_review__一句话pitch.label': '一句话介绍',
  'pitch_review__一句话pitch.placeholder': '一句话说清你做什么、给谁、解决什么问题...',
  'pitch_review__核心循环说明.label': 'BP / 路演材料正文',
  'pitch_review__核心循环说明.placeholder': '粘贴 BP、路演稿或申报表的正文...',
  'pitch_review__目标受众.label': '目标市场与客户',
  'pitch_review__目标受众.placeholder': '描述目标市场规模判断依据与典型客户...',
  'pitch_review__系统说明.label': '团队与进展',
  'pitch_review__系统说明.placeholder': '团队背景、当前进展、已有数据或验证...',
  'pitch_review__定价与平台.label': '商业模式与融资需求',
  'pitch_review__定价与平台.placeholder': '怎么收钱、单位经济、本轮融多少用在哪...',
  'pitch_review__竞品对比.label': '竞争格局',
  'pitch_review__竞品对比.placeholder': '列出竞争对手与你的差异...',
} satisfies Messages
