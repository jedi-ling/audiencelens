/**
 * 判断复利页（LedgerPage.tsx）。owner: agent 6。
 *
 * 改这里的文案前先读三条，它们是这一页的产品前提，不是措辞偏好：
 *
 * 1. **样本不足必须说出来。** low_confidence 那条提示的措辞
 *    （"不具统计意义"）是刻意难听的——把它优化成"数据积累中"会让用户拿
 *    3 个样本当命中率用，那正是这一页存在的意义的反面。
 * 2. **Brier / 校准误差这类术语每条都配了 hint。** hint 不是装饰，
 *    没有那句人话，这块指标只是看起来专业。删 hint = 删掉可读性。
 * 3. **「—」不是缺译，是"这个数没有"。** 指标为 null 时显示它，
 *    绝不显示 0——Brier 越低越好，把"没数据"画成 0 等于把空账本
 *    显示成满分预测。所以 stat.empty 在 zh/en 两侧字面相同。
 *
 * 后端自由文本（HitRate.note / ValidationMetrics.note / ConfidenceCalibration.note、
 * Judgment.claim / .severity、LeaderboardEntry.persona_id）不在本表内：
 * 它们由后端产出，前端无从翻译。见交付报告。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '预测复盘',

  'header.title': '预测复盘',
  'header.desc':
    '每次评审的预测都盖了时间戳留档。真人测试回来后回填结果——判断准不准，从此有据可查。',

  // ---- 整页加载失败横幅 ----
  // 未登录被拒在多租户形态下是常态路径而不是异常，所以 hint 要说清"为什么"，
  // cta 要给得出下一步动作。
  'error.title': '预测复盘数据加载失败',
  'error.hint':
    '这一页放的是「属于你自己的」预测台账，未登录时后端无法区分谁是谁，所以拒绝返回。',
  'error.pending': '重试中…',
  'error.cta': '登录 / 注册',

  // ---- 产品价值验证 ----
  'value.title': '产品价值验证',
  'feedback_coverage.label': '反馈覆盖',
  'useful_rate.label': '认为有用',
  'decision_change.label': '改变决策',
  'adoption.label': '建议采纳',
  'hours_saved.label': '累计节省',
  // h = 小时符号，中英同形，只有数字部分跟 locale 走。
  'hours_saved.value': '{{hours}}h',
  'avg_model_cost.label': '平均模型成本',
  'cost_per_useful.label': '每份有效报告成本',
  'cost_per_adopted.label': '每条采纳成本',
  'avg_willingness.label': '平均付费意愿',

  'by_task_type.title': '按任务类型寻找最强切入点',
  'task_useful.value': '有用 {{value}}',
  'task_adopted.value': '采纳 {{value}}',
  'top_fixes.title': '真正被采纳的建议',
  'top_fixes.value': '×{{times}}',

  // ---- 命中率总览 ----
  'total_judgments.label': '累计预测',
  'pending_verification.label': '待验证',
  'verified.label': '已验证',
  'hit_rate.label': '命中率',

  // ---- 人格命中率排行 ----
  'leaderboard.title': '谁的判断最值得听',
  // 样本量。n= 是统计学通用写法，中英同形。
  'sample.value': 'n={{size}}',

  // ---- 置信度校准 ----
  'calibration.title': '置信度校准',
  'calibration.desc':
    '评审说自己有多大把握，和真实结果对得上吗。上面的命中率回答「说中了几次」，这里回答「说有把握的时候准不准」。',
  'calibration.hint':
    '置信度来源是合成面板的启发式权重，尚未经真实结果重新校准——这张表正是用来做那件事的。',
  'mean_confidence.label': '平均声称把握',
  'observed_hit.label': '真实命中得分',
  // 映射规则，中英同形：它是一行公式，不是句子。
  'observed_hit.hint': 'hit=1 / partial=0.5 / miss=0',
  'brier.label': 'Brier 分数',
  'brier.hint': '越低越好，0=完美',
  'ece.label': '校准误差',
  'ece.hint': '说的把握与实际的平均差距',
  'bins.title': '分区间对照',
  'bins.value': '{{lower}}–{{upper}}%',
  'bin_claimed.value': '说 {{value}}',
  'bin_observed.value': '实 {{value}}',
  // 高估与低估各一条：只标高估会让人以为低估无害，而系统性低估同样意味着没校准。
  'over_estimate.value': '高估 {{value}}',
  'under_estimate.value': '低估 {{value}}',
  'low_confidence.hint': '样本量 {{count}} 偏小，以下数字仅供参考，不具统计意义。',
  // 这两条是同一句话的互斥分支（有没有被排除的行），不是拼接：
  // 中文的句号落在括号之后，拆成"已回填 N 条" + "（…）" + "。" 三段会让
  // 英文侧无法调整语序。
  'verified_rows.value': '已回填 {{count}} 条。',
  'excluded_rows.value':
    '已回填 {{verified}} 条（其中 {{count}} 条因缺少置信度或结果无法映射而未计入）。',

  // ---- 预测清单 ----
  'list.title': '历史预测',
  'list.label': '只看待验证',
  /** 回填的真实后果（project_memory_service 红线 1），写在动作旁边而不是文档里。 */
  'list.hint': '回填为「没发生」的判断，不再进入同项目下一次评审的上下文。',
  // 加载失败时这里曾照样打出"还没有预测记录"——把一次失败说成了"你没有数据"。
  // 所以 list.error 与 list_empty.* 是两条不同的话，不许合并。
  'list.error': '没能加载到预测记录，原因见上方。',
  'list_empty.title': '还没有预测记录',
  'list_empty.desc': '跑一次评审，系统会自动把结论留档。',
  'item.meta': '{{author}} · {{severity}} · {{time}}',
  'panel.label': '评审团合议',

  /*
   * 回填结果的四个取值（后端 Verdict 枚举）。
   *
   * ⚠ 归属说明：按契约 §11 第 3 条，枚举标签应当进 enum.verdict.*，而 enum.*
   * 整个域归 batch-0。截至本次交付，locales/{zh,en}/ 下**没有任何 enum.* 文件**，
   * 而页面 agent 不得创建别人命名空间的文件。所以这四条先落在 page.ledger 的
   * state 变体块里（它是 i18n-gen.mjs 认的变体块，块内叶子不受角色闭集约束）。
   * enum.verdict.* 一旦交付，这四条应整体迁走、调用点改成 enum key——
   * 迁移面就是本文件这四行加 LedgerPage.tsx 的 VERDICT_LABEL_KEYS 一张表。
   */
  'state.hit': '说中了',
  'state.partial': '部分成立',
  'state.miss': '没发生',
  'state.unknown': '暂无法判定',

  'verify_error.title': '回填失败，这条预测仍是「待验证」',
  'verify_error.cta': '登录 / 注册后再回填',

  // 指标为 null 时的显示值。见文件头第 3 条：它表示"没有这个数"，不是缺译。
  'stat.empty': '—',
} satisfies Messages
