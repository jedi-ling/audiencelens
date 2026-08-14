// owner: batch-0。页面 agent 只读。见 zh/common.validate.ts 的文件头。
import type { Messages } from '@/i18n/types'

export default {
  required: 'This field is required',
  email_format: 'Enter a valid email address',
  // min 是位数，不是数量——英文里没有复数陷阱（"at least 1 characters" 才有），
  // 所以这里用 character(s) 的显式写法而不是挂 count 复数：
  // 这条 key 的变量名是 min 不是 count，i18n:check 也不会要求 _one/_other。
  password_min: 'Password must be at least {{min}} characters',
  password_mismatch: 'The two passwords do not match',
  too_long: 'Maximum {{max}} characters',
  number_range: 'Enter a number between {{min}} and {{max}}',
  file_too_large: 'File is larger than {{max}}',
} satisfies Messages
