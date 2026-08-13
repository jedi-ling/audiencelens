/**
 * 服务商预设的展示名（lib/types.ts 的 OPENAI_COMPATIBLE_PRESETS）。
 *
 * ⚠ 分工提示：契约 6.11 指名这批文案"放 catalog.brand.ts"，4.3 把 catalog.* 划给
 * batch-0，但 batch-0 没有建这个文件，而 lib/types.ts 归 agent-11。由 agent-11 建，
 * 集成时请确认没有第二份同名文件。
 *
 * **这不是翻译，是查官方英文名**（契约 6.11 / 12.2）：
 * 通义千问 → Qwen、智谱 GLM → Zhipu GLM 都是厂商自己对外用的英文名，
 * 直译成 "Tongyi Qianwen" 之类会让英文用户在厂商官网上搜不到这家公司。
 * 'Ollama 本地模型' 里只有"本地模型"是可译的，Ollama 是产品名。
 *
 * 叶子 = preset.id，与 lib/types.ts 里的 id 一一对应。
 */
import type { Messages } from '@/i18n/types'

export default {
  openai: 'OpenAI',
  deepseek: 'DeepSeek',
  kimi: 'Kimi (月之暗面)',
  qwen: '通义千问',
  glm: '智谱 GLM',
  ollama: 'Ollama 本地模型',
} satisfies Messages
