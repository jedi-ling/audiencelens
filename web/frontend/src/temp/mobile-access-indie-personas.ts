import type { Persona } from '@/lib/mock-data'

const BEHAVIOR_AXES = [
  '攻击性', '探索性', '社交性', '创造性',
  '竞争性', '合作性', '风险偏好', '耐心',
  '完美主义', '沉浸感', '策略性', '表现欲',
]

function generateBehaviorProfile(): Record<string, number> {
  const profile: Record<string, number> = {}
  for (const axis of BEHAVIOR_AXES) {
    profile[axis] = Math.round((Math.random() * 0.8 + 0.1) * 100) / 100
  }
  return profile
}

export const MOBILE_F2P_PERSONAS: Persona[] = [
  {
    id: 'p39',
    name: '白嫖达人',
    archetype: 'f2p-purist',
    pack: 'mobile-f2p',
    identity_summary: '手机里30+款游戏，充值记录为零，以零氪通关为最高荣耀——但这不代表我不懂好游戏值多少钱，只代表我要求免费体验本身就必须足够完整',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若核心循环在免费阶段已完整呈现且付费墙不打断心流，则认可其F2P设计诚意',
      '若免费获取途径（签到/任务/活动）的肝度超过日活30分钟底线，则判定为"逼氪陷阱"',
    ],
    triggers: [
      '首小时即弹出首充弹窗三次以上',
      '不付费无法体验完整核心玩法',
    ],
  },
  {
    id: 'p40',
    name: '微氪月卡党',
    archetype: 'monthly-card',
    pack: 'mobile-f2p',
    identity_summary: '月卡30块是我的"信仰充值"——我愿意为喜欢的游戏每个月花一顿快餐钱，但我要求这笔钱花得有尊严、有感知、有长期回报',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若月卡提供的日均收益换算后显著高于单次付费，且签到链条设计合理不中断，则愿意持续订阅',
      '若月卡之外还存在战力断层式付费点，则视为"月卡只是诱饵"，不再信任该付费体系',
    ],
    triggers: [
      '月卡收益在版本更新后被变相稀释',
      '连续签到被一次断签清零且无补救机制',
    ],
  },
  {
    id: 'p41',
    name: '氪金大佬',
    archetype: 'whale-spender',
    pack: 'mobile-f2p',
    identity_summary: '单月氪金五位数起步，服务器战力榜前十常客——但别以为我不挑，正因为我花得最多，所以我对"值不值"的判断比谁都苛刻',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若VIP特权带来的体验差异是"更好玩"而非仅仅是"更强"，且炫耀系统（称号/皮肤/排行榜展示）有辨识度，则认可其氪金设计',
      '若付费内容在两周内就被免费玩家追上或版本更替贬值超过30%，则判定为"收割型运营"',
    ],
    triggers: [
      '限时礼包频率超过每周3次',
      '顶级付费内容缺乏独占审美或社交辨识度',
    ],
  },
  {
    id: 'p42',
    name: '广告忍耐者',
    archetype: 'ad-tolerant',
    pack: 'mobile-f2p',
    identity_summary: '我可以接受看30秒广告拿一个宝箱，这是我用时间换资源的方式——前提是广告不打断我的沉浸时刻，奖励不让我觉得被侮辱',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若广告入口清晰可选而非强制弹出，且单次广告奖励与实际游戏进度成正比，则接受广告变现模式',
      '若广告后回到游戏出现加载中断、进度丢失或画面卡死，则无论奖励多好都直接卸载',
    ],
    triggers: [
      '战斗中或剧情高潮时弹出不可跳过的广告',
      '连续看5次广告的奖励总和不如一次微氪的1/10',
    ],
  },
  {
    id: 'p43',
    name: '弃坑回归者',
    archetype: 'returning-player',
    pack: 'mobile-f2p',
    identity_summary: '三个月前删了游戏，今天看到版本大更新又下载回来——我需要一个不让我后悔回归的理由，别让我觉得"这三个月白等了"',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若回归奖励能有效弥补弃坑期间的资源缺口（至少覆盖核心养成线的50%），且有明确的版本追赶指引，则愿意重新投入',
      '若回归后面对的仍是老问题未修复，仅靠新皮肤/新角色拉动，则永久弃坑',
    ],
    triggers: [
      '回归礼包领取后仍需手动补30天以上日常',
      '新版本内容与弃坑时体验无本质区别',
    ],
  },
]

export const ACCESSIBILITY_PERSONAS: Persona[] = [
  {
    id: 'p44',
    name: '色弱视觉辅助',
    archetype: 'color-blind',
    pack: 'accessibility',
    identity_summary: '红绿色弱，不代表我分不清敌人和队友——但如果你只用红绿两色来标记阵营，那你就是在逼我用猜的。给我符号、给我形状、给我除了颜色之外的任何区分方式',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若所有关键信息（阵营/血量/稀有度/状态）均有非颜色编码的替代方案（图标/文字/形状），则认可其为色觉友好设计',
      '若存在任何仅靠颜色传达且无法自定义的核心信息，则判定为可访问性不及格',
    ],
    triggers: [
      '红绿配色用于对立信息且无图案区分',
      '色盲模式只是加了一层滤镜而非重新设计信息层级',
    ],
  },
  {
    id: 'p45',
    name: '认知负担敏感',
    archetype: 'cognitive-load',
    pack: 'accessibility',
    identity_summary: 'ADHD让我对同时涌来的信息极度敏感——如果你的UI像飞机驾驶舱一样塞满图标、弹窗、跑马灯，我撑不过五分钟',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若当前目标始终清晰可见（任务追踪/导航指引不消失）、信息密度有分段节奏、且支持一键关闭非核心UI元素，则视为认知友好设计',
      '若同一屏幕同时存在超过3个独立引导目标，则判定为认知过载',
    ],
    triggers: [
      '主界面同时出现超过5个红点/气泡提示',
      '教学引导与实时战斗信息同时弹出且不可分别关闭',
    ],
  },
  {
    id: 'p46',
    name: '运动辅助需求',
    archetype: 'motor-accessible',
    pack: 'accessibility',
    identity_summary: '手部灵活性受限，不是不能玩游戏——只是我不能同时按住三个键再滑动屏幕。给我自动瞄准、给我可调节的操作节奏、给我按键映射的自由',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若提供完整的按键映射自定义（含连发/长按替代方案）且关键操作可设为切换而非长按，则视为运动友好设计',
      '若存在不可跳过的QTE或需要同时多指操作的硬性门槛，则判定为不友好',
    ],
    triggers: [
      '核心操作需要三指及以上同时触控',
      '限时操作没有可调节的时间宽容度设置',
    ],
  },
  {
    id: 'p47',
    name: '听觉辅助需求',
    archetype: 'hearing-accessible',
    pack: 'accessibility',
    identity_summary: '我听不到脚步声、听不到技能音效、听不到NPC的语音警告——但这不代表我不想"听到"这些信息。给我字幕、给我视觉提示、给我震动反馈，用眼睛和触觉来替代耳朵',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若所有关键音频信息（敌人方位/技能预警/剧情对话）均有完整字幕+方向指示器+可选的震动反馈，则视为听觉友好设计',
      '若存在任何仅靠声音线索传达且无视觉替代的玩法机制，则判定为不可用',
    ],
    triggers: [
      '过场动画无字幕或字幕不可调节大小',
      '环境音效提示（如背后敌人脚步声）无任何视觉方向指示',
    ],
  },
  {
    id: 'p48',
    name: '屏幕阅读依赖者',
    archetype: 'screen-reader',
    pack: 'accessibility',
    identity_summary: '我用屏幕阅读器"看"你的游戏——菜单的Tab顺序对不对、按钮有没有语义标签、NPC能不能被识别到，这些决定了我能不能玩下去',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若所有UI元素的Tab导航顺序符合逻辑（从上到下/从左到右）、按钮/图标均有语义化标签、且关键场景切换时有明确播报，则视为屏幕阅读友好',
      '若菜单层级超过3层且无返回快捷键，或核心交互依赖纯视觉判断（如拖拽/无标签图片按钮），则直接不可用',
    ],
    triggers: [
      '菜单焦点在层级间跳转时顺序混乱',
      '核心功能按钮为纯图标且无aria-label或等效文本描述',
    ],
  },
]

export const INDIE_CREATIVE_PERSONAS: Persona[] = [
  {
    id: 'p49',
    name: '独立鉴赏家',
    archetype: 'indie-connoisseur',
    pack: 'indie-creative',
    identity_summary: '每年Steam愿望单里超过100款独立游戏，从像素RPG到实验性叙事到哲学模拟器——我不在乎你的画面精度，我在乎你有没有"只有你能讲的故事"和"只有你能做的机制"',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若游戏在15秒内展示出明确的作者表达意图（独特的视觉语言/叙事腔调/机制哲学），则立即加入愿望单',
      '若玩法/美术/叙事三者中有至少两项是现有作品的直接组合而无任何原创转化，则判定为"换皮独立"',
    ],
    triggers: [
      '商店页首屏看不出与同类作品的任何差异点',
      '开发日志中反复提及的"灵感来源"远多于"我们自己的创新"',
    ],
  },
  {
    id: 'p50',
    name: '创意追求者',
    archetype: 'creativity-seeker',
    pack: 'indie-creative',
    identity_summary: '我玩游戏不是为了打发时间——我在找那些"从没见过的东西"。一个奇怪的机制、一种反直觉的交互、一个让我愣住三秒的设计，比100小时的"精致内容"更让我兴奋',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若游戏的核心机制在已知类型框架内做了至少一次"出格"的尝试（颠覆预期/打破类型边界/嫁接不可能的组合），则愿意为其不完美买单',
      '若整款游戏的所有设计决策都可以用"因为XX游戏也这么做"来解释，则完全失去兴趣',
    ],
    triggers: [
      '玩法介绍全部可以用现有类型标签穷举',
      '开发者在采访/日志中回避"冒了哪些险"的问题',
    ],
  },
  {
    id: 'p51',
    name: '文化消费主义者',
    archetype: 'culture-consumer',
    pack: 'indie-creative',
    identity_summary: '我把独立游戏当文化消费品，和看电影、读小说、逛展览一样——我需要你的游戏说出某个群体的真实处境、某个被忽视的议题、某个非主流视角下的世界',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若游戏的叙事/世界观/角色设计具有明确的文化立场或社会关怀，且作者背景能为此提供真实性的背书，则给予高度关注',
      '若涉及敏感议题但处理方式停留在"借壳"或"消费符号"层面，则判定为文化挪用而非文化表达',
    ],
    triggers: [
      '多元文化元素仅作为皮肤/换皮存在',
      '开发者无法清晰表述作品的文化立场或创作动机',
    ],
  },
  {
    id: 'p52',
    name: '学生开发者',
    archetype: 'student-dev',
    pack: 'indie-creative',
    identity_summary: '我白天在大学学游戏设计，晚上自己做demo——我评审不仅是为玩，更是为了学：你的关卡怎么拆的、你的系统怎么耦合的、你用的什么技术栈，我全都要记笔记',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若游戏的开发日志/技术博客/GDC演讲公开了核心设计推导过程和实现方案，则视为高价值学习对象',
      '若设计文档或商店页包含可逆向推导的数值框架和系统拆解信息，则额外加分',
    ],
    triggers: [
      '开发过程完全不透明，无任何技术或设计分享',
      '游戏系统的复杂度低于课设水平',
    ],
  },
  {
    id: 'p53',
    name: 'GameJam评委视角',
    archetype: 'gamejam-judge',
    pack: 'indie-creative',
    identity_summary: '我评过十几场GameJam，48小时内从零到可玩的极限——所以我知道"完成比完美重要"，但我也知道核心亮点必须在首30秒内击中评委',
    behavior_profile: generateBehaviorProfile(),
    decisionRules: [
      '若作品有一个清晰的核心亮点（一个机制/一种情感/一个瞬间），且围绕它做的所有取舍都是为突出这个亮点服务，则给予高分评价',
      '若作品功能堆砌但无突出长板，或因追求"完整"导致所有模块都是半成品水平，则判定为Jam方向错误',
    ],
    triggers: [
      '首30秒体验内无法识别唯一核心卖点',
      '作品复杂性远超Jam时间约束下的合理范围',
    ],
  },
]