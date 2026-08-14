/**
 * lib/api.ts（v1 链路）拉取失败时的兜底文案。owner: agent-11（error.* 的补充）。
 *
 * 它替换的是 `toApiError(res, '加载评审列表失败')` 里那串写死的中文。
 * **只在后端什么原因都没给时**才会被用到：后端写清楚的原因（"PDF 文件已加密…"
 * "无法解析文件编码…"）仍然原样透出，那是 lib/api.ts 顶部那段注释立的规矩，
 * 这一层不许把它盖掉——把"可自助修复的失败"降级成"神秘失败"正是当初要修的问题。
 *
 * 与 error.api.*（batch-0）的分工别搞混：
 *   · error.api.*   —— 后端给了 code、但 message 语种对不上界面时的粗译文
 *   · error.fetch.* —— 后端**连原因都没给**（网关 HTML 错误页 / 空 body）时的兜底
 */
import type { Messages } from '@/i18n/types'

export default {
  review_list: '加载评审列表失败',
  review: '加载评审失败',
  report: '加载报告失败',
  personas: '加载人格列表失败',
  persona_packs: '加载人格包失败',
  examples: '加载示例失败',
  extract_materials: '解析文件失败',
  delete_review: '删除评审失败',
  task_types: '加载任务类型失败',
  review_modes: '加载评审模式失败',
  review_result: '加载评审结果失败',
  skills: '加载技能列表失败',
  run_evaluation: '运行质量评估失败',
  evaluation: '加载质量评估失败',
  ethics: '加载伦理检查失败',

  /** 兜底文案后面缀上状态码。带上它是为了让"神秘失败"至少有一个可搜索的线索。 */
  http_status: '{{message}}（HTTP {{status}}）',

  /**
   * FastAPI 422 会回一个校验错误数组，多条拼成一句时的分隔符。
   * 中文用全角分号，英文侧用半角分号 + 空格——全角标点在英文句子里是排版错误。
   */
  separator: '；',
} satisfies Messages
