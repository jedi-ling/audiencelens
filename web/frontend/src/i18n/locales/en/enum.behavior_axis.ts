/**
 * owner: agent-10。见 zh/enum.behavior_axis.ts。
 *
 * 译文按"雷达图轴标签"来写，不是词典义：字号只有 8–10px、绕着圆周排，
 * 长词会被 recharts 直接截断。所以一律两词以内、句首大写、其余小写
 * （"Novelty seeking" 而不是 "Novelty Seeking" —— 图表轴不是标题）。
 */
import type { Messages } from '@/i18n/types'

export default {
  patience: 'Patience',
  genre_literacy: 'Genre literacy',
  novelty_seeking: 'Novelty seeking',
  risk_tolerance: 'Risk tolerance',
  social_influence: 'Social influence',
  completion_drive: 'Completion drive',
  price_sensitivity: 'Price sensitivity',
  criticism_style: 'Criticism style',
  emotional_engagement: 'Emotional engagement',
  agency_preference: 'Wants agency',
  tolerance_for_ambiguity: 'Tolerates ambiguity',
  platform_loyalty: 'Platform loyalty',
} satisfies Messages
