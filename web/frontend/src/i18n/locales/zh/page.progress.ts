/**
 * 评审进度页（/review/:id）。owner: agent-9。
 *
 * 三条连接状态提示（poll_failure / ws_unavailable / ws_reconnect）与 AskPage
 * 的三条**语义重复但措辞不同**，按契约 D10 默认不合并——两页的语气差异是刻意的：
 * 对话页是即时交互，用户在等一句回话，措辞要短、要立刻说清"还能不能说话"；
 * 进度页是长时等待，用户会盯着一个不动的进度条看几分钟，措辞必须先说
 * "评审没停、在后台继续跑"，再说通道怎么了——否则不动的进度条会被读成"卡死"。
 * 合并成一套会抹掉这个差异，而抹掉之后没人能从代码里看出它曾经存在过。
 *
 * 与 error.ws.* 也不是一回事：那五条是**语气中立、任何页面都能原样用**的通道
 * 状态词，这里的四条是"这一页此刻该对用户交代什么"。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '评审进度',

  /** target_title 与 task_type 都为空时的兜底标题。真标题是数据，不在这里。 */
  'header.title': '评审',
  'header.subtitle': '评审进度',
  /** 技能徽章的前缀。技能名本身属于后端目录（catalog.skill.*），不在这里。 */
  'skill.label': '技能',
  'selected_personas.badge': '指定角色 · {{count}} 位',
  'project.badge': '项目 · {{key}}',
  'report.cta': '查看报告',

  // ---- 首屏加载失败 ----
  // 「加载失败」和「真的没有这条评审」是两条分支，措辞必须分开：
  // 断网 / 500 / 403 全说成"未找到评审记录"，用户会以为数据没了。
  'load_error.title': '没能加载这条评审',
  'load_error.desc': '这不代表评审被删除了，评审仍在后台继续运行',
  'not_found.empty': '未找到评审记录',
  'back.cta': '返回评审历史',

  // ---- 四张统计卡 ----
  'overall.label': '总进度',
  'status.label': '状态',
  'persona_count.label': '角色数',
  'cost.label': '已消耗',

  // ---- 连接 / 停滞交代 ----
  'poll_failure.error':
    '无法从服务器同步进度（已连续失败 {{count}} 次），正在自动重试。评审在后台继续运行，不会因此中断。',
  'ws_unavailable.hint': '实时连接不可用，已切换为每 {{count}} 秒轮询获取进度。进度仍会更新，只是稍慢。',
  'ws_reconnect.hint': '实时连接中断，正在重连；期间已切换为轮询获取进度。',
  'stall.hint':
    '已有 {{count}} 秒没有新进展 —— 仍在处理中（某个人格的长文本推理可能耗时较久）。页面每 {{interval}} 秒会主动同步一次状态。',

  // ---- 终态横幅 ----
  // failed.desc 只在后端一个字都没给时才用。后端给了就原样显示它——
  // 本期 WS 推的是 str(exc)（中文原文），英文界面上会混中文，这是已知的、
  // 记在契约 D14 P1 里的欠债，不许在这里加一层"看起来处理了"的兜底把它盖住。
  'failed.title': '评审失败',
  'failed.desc': '执行失败，请稍后重试',
  'failed.cta': '重新发起评审',
  'done.title': '评审已完成，报告已生成',
  'done.cta': '查看完整报告',

  // ---- v2 链路：只有事件流、没有 persona_outputs 时的进行中卡片 ----
  'running_card.title': '评审进行中',
  'running_card.pending': '等待评审团就位…',

  // ---- 角色进度 ----
  'personas.title': '角色进度',
  'personas.empty': '本次评审没有可展示的角色明细',
  'personas.pending': '评审团正在开庭，人格完成后逐一亮灯…',
  'persona_cost.label': '费用 {{amount}}',
  'persona_failed.error': '执行失败',
  'persona_done.badge': '已完成',
  'persona_remaining.pending': '还有 {{count}} 位人格评审中…',

  // ---- 交叉质询 / 聚合分析两块 ----
  // stage.* 是本页自己的 PhaseStatus（'waiting' | 'running' | 'completed'），
  // 不是后端枚举——后端从不推这三个词，它们是前端按事件推导出来的阶段名。
  // 所以它留在 page.progress 而不是 enum.*。
  'cross_exam.title': '交叉质询',
  'aggregation.title': '聚合分析',
  'stage.waiting': '等待中',
  'stage.running': '进行中',
  'stage.completed': '已完成',
} satisfies Messages
