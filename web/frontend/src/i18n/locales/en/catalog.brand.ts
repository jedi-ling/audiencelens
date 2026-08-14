// owner: agent-11（见 zh/catalog.brand.ts 的文件头）。
//
// 官方英文名，不是直译。openai / deepseek 两条两侧字面相同——品牌名本来就只有一种写法，
// 这不是"忘了翻"（i18n:check 的"照抄中文"断言只在值含中文时才触发，这两条不含）。
import type { Messages } from '@/i18n/types'

export default {
  openai: 'OpenAI',
  deepseek: 'DeepSeek',
  // 月之暗面对外的英文公司名是 Moonshot AI，产品名是 Kimi。
  kimi: 'Kimi (Moonshot AI)',
  qwen: 'Qwen',
  glm: 'Zhipu GLM',
  // Ollama 是产品名，只有"本地模型"这半句可译。
  ollama: 'Ollama (local models)',
} satisfies Messages
