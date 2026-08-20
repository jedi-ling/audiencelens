// owner: batch-0。见 zh/error.api.ts 的文件头——这 10 条粒度很粗，是止血。
import type { Messages } from '@/i18n/types'

export default {
  bad_request: 'Something in the request was not valid',
  unauthorized: 'Please sign in first',
  session_expired: 'Your session has expired — please sign in again.',
  forbidden: 'You do not have access to this',
  not_found: 'Not found',
  rate_limited: 'Too many requests — try again in a moment',
  quota_exceeded: 'You are out of quota',
  llm_key_missing: 'No model API key configured yet',
  upstream_error: 'The model service is unavailable right now',
  internal_error: 'The server hit an error',
  admin_disabled: 'An administrator has turned this off',
} satisfies Messages
