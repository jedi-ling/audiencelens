/**
 * 未验证邮箱提示条。owner: batch-0。
 *
 * 重发按钮是**四态各一条 key，不是插值**（契约 3.4 例 2）。
 * 原来是一段嵌套三元，抽 key 时把三元保留在 tsx 里，key 表这边平铺四条——
 * 三元里的分支条件是行为逻辑，不是文案，不该被 i18n 层吃掉。
 *
 * 做成状态而不是 toast 的原因写在 Layout.tsx 的注释里，翻译时别把
 * "已发送"改成一个会自己消失的语气。
 */
import type { Messages } from '@/i18n/types'

export default {
  hint: '邮箱尚未验证，每天只能评审 {{count}} 次。验证后解锁完整额度。',
  /**
   * reviews_limit 是 number | null。null 时用这条。
   *
   * 原来这里直接渲染 {usage.reviews_limit}，null 会渲染成空字符串，
   * 句子变成"每天只能评审  次。"——外化时被 t() 的类型逼出来的既有坑。
   * 不许写成 `?? 0`：那会向用户断言"你今天一次都不能评审"，而这不是事实。
   */
  hint_unknown: '邮箱尚未验证，每日评审次数被压低了。验证后解锁完整额度。',
  cta: '重新发送验证邮件',
  sending: '发送中…',
  success: '已发送，请查收（含垃圾箱）·点此再发一次',
  error: '发送失败，点此重试',
} satisfies Messages
