/**
 * 档位开销对比 —— 让用户在**选档位的那一刻**看见"贵多少、贵在哪"。
 *
 * ── 这里的数字是怎么来的（不是估的，是数出来的）──
 *
 * 一次评审的模型调用由两部分构成，都能从引擎的档位配置直接推出来：
 *   1. 人格调用 = 该档的人格数上限（REVIEW_MODE_BOUNDARIES.max_personas，
 *      事实源是 src/runner/cli.py 的 REVIEW_MODE_CONFIG，有一致性测试钉着）
 *   2. 交叉质询调用（src/runner/cross_exam.py）：
 *        · quick    —— 该档不跑质询，0 次
 *        · standard —— MODE_MODERATED：仲裁式，**总共 1 次**
 *        · full     —— MODE_MULTI_AGENT：每个争议点的每一方各 1 次，
 *                      次数随本次材料的分歧多少变化，**事前无法确定**
 *   3. 校准检查不发任何 API 调用（calibration.py 里 compute_role_consistency_rate /
 *      compute_coverage_score / compute_hallucination_rate 全是本地计算）——
 *      所以 full 档的"含校准"不额外增加 token，这一条必须说清楚，
 *      否则用户会以为勾了校准就更贵。
 *
 * ── 为什么标"调用次数"而不是"多少钱 / 多少 token" ──
 *
 * 单次调用消耗多少 token 取决于材料长度、人格卡长度、模型返回长度，事前不可知。
 * 库里现有的真实用量样本是 quick 4 条 / standard 4 条 / full **1 条**——
 * 拿 n=1 去算"完整档平均花费 $X"就是在编数据。调用次数是结构性确定的，
 * 能诚实地表达相对开销，所以只说这个，并明确标注"实际 token 随材料长度变化"。
 *
 * ── 配色为什么是同一个蓝的三档深浅，不是三个颜色 ──
 *
 * 三个档位是**有序量级**（quick < standard < full），不是并列的三个类别。
 * 按数据可视化规范，有序量用单色相渐变（sequential/ordinal），彩虹色会暗示
 * "它们之间没有顺序"。这三步经 dataviz 验证器 --ordinal 实测通过：
 * 明度单调、相邻 ΔL ≥ 0.06、最浅一端对底色 3.15:1、色相跨度 3°。
 */
import { REVIEW_MODE_BOUNDARIES } from '@/lib/mock-data'
import { t } from '@/i18n/runtime'
import type { PlainMessageKey } from '@/i18n/keys.gen'

/** 各档交叉质询的调用次数。事实源：src/runner/cli.py 的
 *  CROSS_EXAM_MODE_BY_REVIEW_MODE + src/runner/cross_exam.py 的分支。
 *  null = 随分歧数变化，事前不可确定（full 档的多智能体反驳）。 */
const CROSS_EXAM_CALLS: Record<string, number | null> = {
  quick: 0,
  standard: 1,
  full: null,
}

/** 有序量级用单色相三档深浅（见文件头说明）。深→浅 = 便宜→贵。 */
const TIER_COLOR: Record<string, string> = {
  quick: '#256abf',
  standard: '#3987e5',
  full: '#86b6ef',
}

const MODE_LABEL_KEY: Record<string, PlainMessageKey> = {
  quick: 'enum.mode_badge.quick',
  standard: 'enum.mode_badge.standard',
  full: 'enum.mode_badge.full',
}

interface Row {
  id: string
  personas: number
  crossExamCalls: number | null
  /** 已知的最少调用次数。full 档是下界（还要加上不确定的质询调用）。 */
  minCalls: number
  variable: boolean
}

function buildRows(): Row[] {
  return REVIEW_MODE_BOUNDARIES.map((m) => {
    const ce = CROSS_EXAM_CALLS[m.id] ?? null
    return {
      id: m.id,
      personas: m.max_personas,
      crossExamCalls: ce,
      minCalls: m.max_personas + (ce ?? 0),
      variable: ce === null,
    }
  })
}

export default function ModeCostCompare({ selectedMode }: { selectedMode?: string }) {
  const rows = buildRows()
  // 条长按"已知最少调用次数"归一化。full 档的条另加一段斜纹表示"还会更多"，
  // 不用一个编出来的数字把它画满——不确定就画成不确定。
  //
  // 分母留出余量：直接拿 max 当分母时，最长的那条（正好是带斜纹的 full 档）
  // 会占满 100%，斜纹尾巴被挤成零宽度——"还会更多"这层信息就画丢了。
  // 留 40% 余量让尾巴有地方画。余量只影响观感比例，不影响右侧那个真实数字。
  const max = Math.max(...rows.map((r) => r.minCalls))
  const denom = rows.some((r) => r.variable) ? max * 1.4 : max

  return (
    <div className="mt-4 rounded-xl border border-border bg-bg-secondary/40 p-4">
      <div className="mb-1 flex items-baseline gap-2">
        <h4 className="text-sm font-medium text-text-primary">{t('page.create.mode_cost.title')}</h4>
        <span className="font-mono text-[10px] text-text-muted">{t('page.create.mode_cost.unit')}</span>
      </div>
      <p className="mb-3 text-xs leading-relaxed text-text-muted">
        {t('page.create.mode_cost.desc')}
      </p>

      <div className="space-y-2.5">
        {rows.map((r) => {
          const pct = Math.round((r.minCalls / denom) * 100)
          const isActive = selectedMode === r.id
          return (
            <div key={r.id} className="flex items-center gap-3">
              <span
                className={cnLabel(isActive)}
                // 档位名用文字 token 色，不用序列色——颜色属于色块，文字属于文字
              >
                {t(MODE_LABEL_KEY[r.id])}
              </span>
              <div className="relative h-3 flex-1 overflow-hidden rounded-[3px] bg-bg-card">
                <div
                  className="h-full rounded-[3px]"
                  style={{ width: `${pct}%`, background: TIER_COLOR[r.id] }}
                />
                {r.variable && (
                  // full 档：45° 斜纹尾巴 = "还会更多，但多少取决于分歧数量"。
                  // 用纹理而不是把条画长，是因为画长就等于给了一个假的具体数字。
                  <div
                    className="absolute inset-y-0 h-full opacity-70"
                    style={{
                      left: `${pct}%`,
                      right: 0,
                      backgroundImage: `repeating-linear-gradient(45deg, ${TIER_COLOR[r.id]} 0 3px, transparent 3px 6px)`,
                    }}
                  />
                )}
              </div>
              <span className="w-28 shrink-0 text-right font-mono text-[11px] text-text-secondary tabular-nums">
                {r.variable
                  ? t('page.create.count.mode_calls_variable', { count: r.minCalls })
                  : t('page.create.count.mode_calls', { count: r.minCalls })}
              </span>
            </div>
          )
        })}
      </div>

      <p className="mt-3 border-t border-border pt-2 text-[11px] leading-4 text-text-muted">
        {t('page.create.mode_cost.hint')}
      </p>
    </div>
  )
}

function cnLabel(active: boolean): string {
  return [
    'w-16 shrink-0 text-xs',
    active ? 'font-semibold text-text-primary' : 'text-text-secondary',
  ].join(' ')
}
