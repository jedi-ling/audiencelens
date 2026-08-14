/**
 * owner: agent-catalog-frontend。key 形状与"为什么中文 wire key 出现在 key 里"
 * 见 zh/catalog.material.ts 的文件头。
 *
 * 译法口径（三条，写下来是为了下一个人加任务类型时不用重新拍）：
 *   1. label 是**表单字段名**：句首大写、其余小写、不加冒号、尽量两三个词。
 *      "Core gameplay loop" 而不是 "Core Gameplay Loop"，也不是 "The core loop of your game"。
 *   2. placeholder 是**指令**，保留中文侧的省略号收尾（它在界面上表示"还有得写"），
 *      也保留中文侧的举例（Dead Cells / $19.99 / roguelite 这些是真实例子，不是占位符）。
 *   3. 中文里的「」在英文侧换成 “”（U+201C/U+201D），不留中文书名号——契约 §6.9。
 *
 * 有一条不是直译，单独说明：product_feedback_review 的 "竞品参考" 直译成
 * "Comparable products" 会和 pricing_page_review 的 "Competitor pricing" 读起来像同一件事，
 * 而这一栏问的其实是"用户会拿谁跟你比"，所以写成
 * "Alternatives users compare you to"——中文侧不动，那是 D6 保护的源行。
 */
import type { Messages } from '@/i18n/types'

export default {
  // ---- concept_review ----
  'concept_review__一句话pitch.label': 'One-line pitch',
  'concept_review__一句话pitch.placeholder': "Describe your game's core concept in one sentence...",
  'concept_review__核心循环说明.label': 'Core gameplay loop',
  'concept_review__核心循环说明.placeholder': 'Describe the core loop: explore → fight → ...',
  'concept_review__竞品对比.label': 'Comparable titles',
  'concept_review__竞品对比.placeholder': 'List what you benchmark against, e.g. Dead Cells (combat pacing), Hollow Knight (exploration depth)',
  'concept_review__目标受众.label': 'Target audience',
  'concept_review__目标受众.placeholder': 'Describe the players you are aiming at...',
  'concept_review__定价与平台.label': 'Pricing and platforms',
  'concept_review__定价与平台.placeholder': 'e.g. Early Access $14.99, PC launch on Steam',
  'concept_review__截图.label': 'Screenshots / visual style',
  'concept_review__截图.placeholder': 'Describe the visual style, or upload screenshots...',
  'concept_review__系统说明.label': 'Core systems',
  'concept_review__系统说明.placeholder': 'Describe 3–5 core systems...',

  // ---- demo_first_play ----
  'demo_first_play__游戏名称.label': 'Game title',
  'demo_first_play__游戏名称.placeholder': 'Enter the game title',
  'demo_first_play__核心循环说明.label': 'Core gameplay',
  'demo_first_play__核心循环说明.placeholder': 'Describe the gameplay the demo covers...',
  'demo_first_play__截图.label': 'Screenshots / visual style',
  'demo_first_play__截图.placeholder': 'Describe how the game looks...',
  'demo_first_play__实机视频.label': 'Gameplay video',
  'demo_first_play__实机视频.placeholder': 'Describe the video, or paste a link...',
  'demo_first_play__竞品对比.label': 'Comparable titles',
  'demo_first_play__竞品对比.placeholder': 'List what you benchmark against...',
  'demo_first_play__评价摘要.label': 'Existing feedback',
  'demo_first_play__评价摘要.placeholder': 'Paste any player feedback you already have...',

  // ---- steam_page_review ----
  'steam_page_review__游戏名称.label': 'Game title',
  'steam_page_review__游戏名称.placeholder': 'Enter the game title',
  'steam_page_review__截图.label': 'Capsule art / screenshots',
  'steam_page_review__截图.placeholder': 'Describe the Steam capsule art and the screenshots...',
  'steam_page_review__核心循环说明.label': 'Short description',
  'steam_page_review__核心循环说明.placeholder': 'Paste the short description from your Steam page...',
  'steam_page_review__tags.label': 'Tags',
  'steam_page_review__tags.placeholder': 'e.g. roguelite, metroidvania, pixel art',
  'steam_page_review__价格.label': 'Price',
  'steam_page_review__价格.placeholder': 'e.g. $19.99',
  'steam_page_review__评价摘要.label': 'User reviews',
  'steam_page_review__评价摘要.placeholder': 'Paste a summary of the reviews you already have...',
  'steam_page_review__demo.label': 'Demo',
  'steam_page_review__demo.placeholder': 'Is there a demo, and what does it include...',

  // ---- kickstarter_review ----
  'kickstarter_review__项目名称.label': 'Project name',
  'kickstarter_review__项目名称.placeholder': 'Enter the crowdfunding project name',
  'kickstarter_review__一句话pitch.label': 'One-line pitch',
  'kickstarter_review__一句话pitch.placeholder': 'The core selling point of the project...',
  'kickstarter_review__核心循环说明.label': 'Project description',
  'kickstarter_review__核心循环说明.placeholder': 'Describe what the project is and what makes it stand out...',
  'kickstarter_review__定价与平台.label': 'Reward tiers',
  'kickstarter_review__定价与平台.placeholder': 'List the price and contents of each tier...',
  'kickstarter_review__截图.label': 'Visual assets',
  'kickstarter_review__截图.placeholder': 'Describe the images and video on the campaign page...',
  'kickstarter_review__目标受众.label': 'Target backers',
  'kickstarter_review__目标受众.placeholder': 'Describe the backers you are aiming at...',

  // ---- discord_community_review ----
  'discord_community_review__社区名称.label': 'Community name',
  'discord_community_review__社区名称.placeholder': 'e.g. Echoes of the Void official Discord',
  'discord_community_review__核心循环说明.label': 'Community description',
  'discord_community_review__核心循环说明.placeholder': 'Describe what the community is about and how big it is...',
  'discord_community_review__评价摘要.label': 'Recent posts',
  'discord_community_review__评价摘要.placeholder': 'Paste 3–5 recent posts that are representative...',
  'discord_community_review__系统说明.label': 'Channel structure',
  'discord_community_review__系统说明.placeholder': 'List the main channels and the rules...',
  'discord_community_review__竞品对比.label': 'Comparable communities',
  'discord_community_review__竞品对比.placeholder': 'Compare it with the communities of similar games...',

  // ---- devlog_review ----
  'devlog_review__游戏名称.label': 'Game title',
  'devlog_review__游戏名称.placeholder': 'Enter the game title',
  'devlog_review__核心循环说明.label': 'Devlog content',
  'devlog_review__核心循环说明.placeholder': 'Paste the full devlog, or a summary...',
  'devlog_review__评价摘要.label': 'Community feedback',
  'devlog_review__评价摘要.placeholder': 'Paste how the community responded to the devlog...',
  'devlog_review__截图.label': 'Images',
  'devlog_review__截图.placeholder': 'Describe the screenshots / GIFs used in the devlog...',

  // ---- monetization_review ----
  'monetization_review__游戏名称.label': 'Game title',
  'monetization_review__游戏名称.placeholder': 'Enter the game title',
  'monetization_review__定价与平台.label': 'Monetization model',
  'monetization_review__定价与平台.placeholder': 'Describe the model: premium / free-to-play with IAP / subscription...',
  'monetization_review__核心循环说明.label': 'Core gameplay',
  'monetization_review__核心循环说明.placeholder': 'Describe the core loop of the game...',
  'monetization_review__竞品对比.label': 'Competitor pricing',
  'monetization_review__竞品对比.placeholder': 'List how comparable titles are priced...',
  'monetization_review__评价摘要.label': 'Player feedback',
  'monetization_review__评价摘要.placeholder': 'Paste what players have said about the pricing...',

  // ---- update_announcement_review ----
  'update_announcement_review__游戏名称.label': 'Game title',
  'update_announcement_review__游戏名称.placeholder': 'Enter the game title',
  'update_announcement_review__核心循环说明.label': 'Update notes',
  'update_announcement_review__核心循环说明.placeholder': 'Paste the full update announcement...',
  'update_announcement_review__评价摘要.label': 'Player feedback',
  'update_announcement_review__评价摘要.placeholder': 'Paste what players have said about the update...',
  'update_announcement_review__截图.label': 'Update screenshots',
  'update_announcement_review__截图.placeholder': 'Describe the screenshots of what is new...',

  // ---- localization_review ----
  'localization_review__游戏名称.label': 'Game title',
  'localization_review__游戏名称.placeholder': 'Enter the game title',
  'localization_review__核心循环说明.label': 'Source text',
  'localization_review__核心循环说明.placeholder': 'Paste the source text you want reviewed...',
  'localization_review__系统说明.label': 'Translated text',
  'localization_review__系统说明.placeholder': 'Paste the translated text...',
  'localization_review__竞品对比.label': 'Cultural notes',
  'localization_review__竞品对比.placeholder': 'Describe anything specific to the target culture...',

  // ---- looking_for_party_post ----
  'looking_for_party_post__游戏名称.label': 'Game title',
  'looking_for_party_post__游戏名称.placeholder': 'Enter the game title',
  'looking_for_party_post__核心循环说明.label': 'Post content',
  'looking_for_party_post__核心循环说明.placeholder': 'Paste the full looking-for-group post...',
  'looking_for_party_post__目标受众.label': 'Players you want',
  'looking_for_party_post__目标受众.placeholder': 'Describe the kind of players you want to attract...',

  // ---- product_feedback_review ----
  'product_feedback_review__产品名称.label': 'Product name',
  'product_feedback_review__产品名称.placeholder': 'Enter the product or feature name',
  'product_feedback_review__核心循环说明.label': 'What the product does',
  'product_feedback_review__核心循环说明.placeholder': 'Describe the problem it solves and how people use it...',
  'product_feedback_review__评价摘要.label': 'Existing user feedback',
  'product_feedback_review__评价摘要.placeholder': 'Paste 3–5 pieces of real user feedback, support tickets or comments...',
  'product_feedback_review__目标受众.label': 'Target users',
  'product_feedback_review__目标受众.placeholder': 'Describe who they are and when they use it...',
  'product_feedback_review__竞品对比.label': 'Alternatives users compare you to',
  'product_feedback_review__竞品对比.placeholder': 'List the products users are likely to weigh you against...',
  'product_feedback_review__截图.label': 'Interface screenshots',
  'product_feedback_review__截图.placeholder': 'Describe the key screens, or upload screenshots...',

  // ---- pricing_page_review ----
  'pricing_page_review__产品名称.label': 'Product name',
  'pricing_page_review__产品名称.placeholder': 'Enter the product name',
  'pricing_page_review__定价与平台.label': 'Pricing tiers',
  'pricing_page_review__定价与平台.placeholder': 'Tier by tier: name / price / what is included / what is capped...',
  'pricing_page_review__核心循环说明.label': 'Pricing page copy',
  'pricing_page_review__核心循环说明.placeholder': 'Paste the headings, selling points and explanatory copy from the page...',
  'pricing_page_review__目标受众.label': 'Who you want to pay',
  'pricing_page_review__目标受众.placeholder': 'Who you expect to buy, and what budget they have...',
  'pricing_page_review__竞品对比.label': 'Competitor pricing',
  'pricing_page_review__竞品对比.placeholder': 'List the tiers and prices of your competitors...',
  'pricing_page_review__截图.label': 'Page screenshots',
  'pricing_page_review__截图.placeholder': 'Describe the layout and the visuals of the pricing page...',

  // ---- onboarding_review ----
  'onboarding_review__产品名称.label': 'Product name',
  'onboarding_review__产品名称.placeholder': 'Enter the product name',
  'onboarding_review__核心循环说明.label': 'Onboarding steps',
  'onboarding_review__核心循环说明.placeholder': 'List every step in order, from sign-up to the first time a new user gets value...',
  'onboarding_review__目标受众.label': 'Who the new users are',
  'onboarding_review__目标受众.placeholder': 'Describe their background, their motivation and what they already know...',
  'onboarding_review__系统说明.label': 'First value moment',
  'onboarding_review__系统说明.placeholder': 'The step where a user first thinks “this is useful”...',
  'onboarding_review__评价摘要.label': 'Drop-off feedback',
  'onboarding_review__评价摘要.placeholder': 'Paste feedback from users who dropped off, or what the funnel shows...',
  'onboarding_review__截图.label': 'Onboarding screens',
  'onboarding_review__截图.placeholder': 'Describe the screens and prompts, and the order they appear in...',

  // ---- pitch_review ----
  'pitch_review__项目名称.label': 'Project name',
  'pitch_review__项目名称.placeholder': 'Enter the project or company name',
  'pitch_review__一句话pitch.label': 'One-line pitch',
  'pitch_review__一句话pitch.placeholder': 'One sentence: what you do, who for, and which problem it solves...',
  'pitch_review__核心循环说明.label': 'Deck / pitch document',
  'pitch_review__核心循环说明.placeholder': 'Paste the body of your business plan, pitch script or application form...',
  'pitch_review__目标受众.label': 'Market and customers',
  'pitch_review__目标受众.placeholder': 'How you sized the market, and who a typical customer is...',
  'pitch_review__系统说明.label': 'Team and traction',
  'pitch_review__系统说明.placeholder': 'Team background, where you are now, any data or validation...',
  'pitch_review__定价与平台.label': 'Business model and raise',
  'pitch_review__定价与平台.placeholder': 'How you charge, unit economics, how much you are raising and what for...',
  'pitch_review__竞品对比.label': 'Competitive landscape',
  'pitch_review__竞品对比.placeholder': 'List your competitors and how you differ from them...',
} satisfies Messages
