/**
 * 公开只读报告页（/s/:token）。owner: agent-9。
 *
 * ⚠ **这一页的读者不一定是作者。** 分享链接是被人直接甩过来的，访客可能
 * 第一次听说这个产品、没有账号、也没有原始材料。所以这里的措辞一律用
 * 第三人称说"作者"，不写"你的报告"——写成"你的报告"，第一次点进来的人
 * 会以为自己被误导进了别人的账号。
 *
 * 同理，任何需要身份的动作（重跑、追问、认领）在这一页都不存在，
 * 所以这里也没有对应的 key。见文件头注释与契约 8.6。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '共享报告',

  // ---- 链接被撤销（404）。与"加载失败"分开说：前者是正常结果，后者是故障。 ----
  'revoked.title': '链接已失效',
  'revoked.desc': '这条分享链接不存在，或者已经被作者撤销了。如果你需要查看，请向分享给你的人重新索取。',
  'revoked.cta': '了解千见 AudienceLens',

  // ---- 真的出故障了 ----
  // load_error.desc 同时兼两个用途：拿不到具体错误时的说明，
  // 以及 tApiError 的 fallbackKey（非 ApiError 的异常走它）。
  'load_error.title': '加载失败',
  'load_error.desc': '没有拿到报告内容',

  /** report.meta.target 与 target_title 都为空时的兜底标题。 */
  'header.title': '评审报告',
  'header.meta': '{{count}} 位人格参与',
  'share_note.badge': '这是作者主动分享的只读报告',

  'summary.title': '总体结论',
  // <v> 里包的是引擎产出的原值（中文），只负责加粗，不做任何翻译。
  'release_risk.label': '发布风险：<v>{{value}}</v>',
  'evidence_quality.label': '证据质量：<v>{{value}}</v>',

  'fixes.title': '优先修复（{{count}}）',
  'suggestion.label': '建议：{{text}}',

  'agreed.title': '多数认同',
  'questioned.title': '存在质疑',
  'notes.title': '各角色视角（{{count}}）',
  'gaps.title': '信息缺口',

  // 访客大概率是第一次听说这个产品——给一条自然的了解入口，不做拦截层。
  'footer.desc': '这份报告由千见 AudienceLens 的多角色评审团生成。',
  'footer.cta': '给自己的东西也跑一轮',
} satisfies Messages
