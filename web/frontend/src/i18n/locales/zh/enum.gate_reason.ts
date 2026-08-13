/**
 * 三层校验的门控失败类型。owner: agent-1（ReportPage）。
 *
 * 叶子 = 引擎回传的英文枚举值原样（src/runner/cli.py 的 RETRY_SCHEMA /
 * RETRY_ROLE_DRIFT / RETRY_HALLUCINATION），契约 §3.4 例 8。
 *
 * 这三句是**给用户读的解释**，不是给开发者读的错误码：括号里那半句必须说清
 * "这条为什么不算数"，否则用户只会看到一个自己没见过的英文词。
 * 认不出的枚举值不在这里兜底，ReportPage 显式渲染
 * page.report.gate.label（"未知失败类型（原值）"），不猜、也不吞。
 */
import type { Messages } from '@/i18n/types'

export default {
  schema_failure: '输出结构不合格（关键字段缺失或格式不对）',
  role_drift: '角色漂移（没有按这个人格的设定作答）',
  hallucination: '证据核对不通过（引用的原文在材料里找不到）',
} satisfies Messages
