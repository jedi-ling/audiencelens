/**
 * ApiErrorCode → 界面文案。owner: batch-0。
 *
 * ⚠ 这 10 条**粒度很粗**，是止血用的：后端 174 个 raise 点共用这 10 个 code，
 * 光 bad_request 一个码就覆盖 75 段不同的中文。所以这里每条都只能写到
 * "这一类请求出了什么事"，写不到具体原因。
 *
 * 正常情况下 zh 界面走的是后端 message（更具体），这 10 条只在
 * 「后端明确标注 message_lang 不是中文」时才会被用到。别把它们当成主路径去打磨，
 * 真正该做的是后端补细粒度 code + 消息目录（契约 D2 / 第 13 节欠债 1）。
 */
import type { Messages } from '@/i18n/types'

export default {
  bad_request: '请求参数有误',
  unauthorized: '请先登录',
  session_expired: '登录已过期，请重新登录。',
  forbidden: '没有权限访问这项内容',
  not_found: '找不到这项内容',
  rate_limited: '操作太频繁，请稍后再试',
  quota_exceeded: '配额已用完',
  llm_key_missing: '还没有配置模型密钥',
  upstream_error: '模型服务暂时不可用',
  internal_error: '服务出错了',
  admin_disabled: '该功能已被管理员关闭',
} satisfies Messages
