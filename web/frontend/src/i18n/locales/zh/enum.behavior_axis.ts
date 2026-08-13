/**
 * 人格行为画像的雷达图轴名。owner: agent-10。
 *
 * 叶子 = 后端 behavior_profile 的键原样（patience / genre_literacy / …）。
 *
 * 这张表**是**契约 D8 点名的那个反例的修复处：
 * PersonaRadarChart 原来写 `AXIS_LABEL_MAP[d.axis] ?? d.axis`，查不到就把后端的
 * 英文键（"novelty_seeking"）直接画在雷达图上假装那就是轴名——中文界面上出现一圈
 * 英文下划线标识符，看起来像"这个维度就叫这个名字"，没有任何人会发现是缺译。
 * 现在查不到就渲染 ⟦missing:<locale>:enum.behavior_axis.<键>⟧，
 * 一条 grep 就能扫出来（见 PersonaRadarChart.tsx 的 axisLabel）。
 *
 * 后端加了新轴而这里没跟上时，表现就是那个轴显示 ⟦missing:…⟧ —— 这是要的效果，
 * **不要**为了"图好看"给它补 `?? axis`。
 */
import type { Messages } from '@/i18n/types'

export default {
  patience: '耐心',
  genre_literacy: '品类理解力',
  novelty_seeking: '新鲜感追求',
  risk_tolerance: '风险承受度',
  social_influence: '社交影响度',
  completion_drive: '完成驱动',
  price_sensitivity: '价格敏感度',
  criticism_style: '批评风格',
  emotional_engagement: '情感投入度',
  agency_preference: '自主偏好',
  tolerance_for_ambiguity: '模糊容忍度',
  platform_loyalty: '平台忠诚度',
} satisfies Messages
