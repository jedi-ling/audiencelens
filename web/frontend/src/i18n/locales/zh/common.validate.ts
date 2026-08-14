/**
 * 客户端表单校验文案。owner: batch-0，**页面 agent 只读不写**。
 *
 * 这是 D10「默认不合并」的唯一例外，理由（契约 D11）：
 * 这批文案在 5 个认证页 + 设置页 + 创建评审页里逐字重复，它们不是"语气差异"，
 * 是同一条规则的同一句话。各抽各的会产生 7 份译文，改一次校验规则要改 7 个地方，
 * 而且必然有一处忘改——那处的表现是"同一个校验在不同页面说法不一样"，
 * 用户会以为是两种不同的错误。
 *
 * 需要新的校验类型（比如手机号格式）：写进你的交付报告，由 batch-0 加，不要自己加。
 */
import type { Messages } from '@/i18n/types'

export default {
  required: '此项必填',
  email_format: '请输入有效的邮箱地址',
  password_min: '密码至少 {{min}} 位',
  password_mismatch: '两次输入的密码不一致',
  too_long: '最多 {{max}} 个字符',
  number_range: '请输入 {{min}} 到 {{max}} 之间的数字',
  // {{max}} 由调用方用 formatBytes() 先格式化好再传进来——
  // 这里不做单位换算，否则字节数的换算逻辑会分裂成 i18n 和 format 两处。
  file_too_large: '文件超过 {{max}}',
} satisfies Messages
