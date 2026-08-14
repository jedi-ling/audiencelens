// owner: agent-1（见 zh/enum.gate_reason.ts 的文件头）
import type { Messages } from '@/i18n/types'

export default {
  schema_failure: 'Malformed output (required fields missing or in the wrong shape)',
  role_drift: 'Role drift (the answer ignored this persona’s profile)',
  hallucination: 'Evidence check failed (the quoted line is not in your materials)',
} satisfies Messages
