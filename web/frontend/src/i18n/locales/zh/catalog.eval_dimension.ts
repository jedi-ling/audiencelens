/**
 * 自评维度（EVALUATION_DIMENSIONS）的名称与说明。owner: agent-catalog-frontend。
 *
 * 契约 D5 的表里这一行的 zh 与 en 事实源**都是前端**：这 8 条是前端为后端
 * RUBRIC_SCORES 的 8 个 id 配的中文标签，后端只回 id 与分数，没有 name/description。
 * 所以这份是唯一事实源，不是离线兜底。
 *
 * 叶子 = 后端维度 id 原样（persona_differentiation / input_grounding / …），
 * 不做大小写转换、不改写。后端加了新维度而这里没跟上时，页面显示
 * ⟦missing:<locale>:catalog.eval_dimension.<新 id>.label⟧ —— 这正是要的效果：
 * mock-data.ts:985 的注释记过一次相反的事故（id 对不上导致 find() 恒 undefined，
 * 维度标题退化成英文 snake_case 直出、说明整行空白，看起来像排版问题而不是缺数据）。
 *
 * 值是 src/lib/mock-data.ts 里 EVALUATION_DIMENSIONS 的 name / description 的逐字副本
 * （源常量一个字不改，契约 D6）。name 在这里用角色段 label —— 契约 §3.2 的角色闭集里
 * 没有 name，而这两条在界面上就是维度卡片的标题与说明。
 */
import type { Messages } from '@/i18n/types'

export default {
  'persona_differentiation.label': '人格差异度',
  'persona_differentiation.desc': '各人格是否有由行为规则支撑的稳定视角差异，而不只是措辞不同',

  'input_grounding.label': '材料贴合度',
  'input_grounding.desc': '结论是否持续引用你提交的材料细节，而不是给一段通用建议',

  'actionability.label': '可行动性',
  'actionability.desc': 'P0/P1/P2 行动项是否具体且分了优先级，而不是泛泛而谈',

  'segment_conflict.label': '人群分歧',
  'segment_conflict.desc': '不同人群之间是否出现了能影响产品决策的真实分歧',

  'risk_detection.label': '风险识别',
  'risk_detection.desc': '是否指出了明确的阻断点、反对理由和分人群的风险',

  'ethical_persona_use.label': '人格伦理',
  'ethical_persona_use.desc': '是否避免刻板印象，把人口统计/MBTI 一类字段只当作弱修饰',

  'report_structure.label': '报告结构',
  'report_structure.desc': '报告是否包含全部必需章节且每节都有实质内容',

  'calibration_honesty.label': '结论诚实度',
  'calibration_honesty.desc': '是否把发现表述为待验证的假设并给出真实验证方式，而非预测成功',
} satisfies Messages
