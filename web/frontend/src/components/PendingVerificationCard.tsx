/**
 * 待验证追踪卡——判断飞轮在首页的落点。
 *
 * 动机：回填（verify_judgment）此前的唯一入口藏在 /ledger 页面里，用户得自己
 * 想起来去点。而回填在本产品里是**有真实后果**的动作：被回填为 miss 的判断
 * 不再进入同项目下一次评审的提示词（project_memory_service 的红线 1）。
 * 一个有后果的动作配一个没人找得到的入口，等于没有。
 *
 * 形态抄 ARTi 登录后首页的「持续追踪中」卡：把"判断"当成有生命周期的活对象
 * 摆在发起评审的主路径上——`「官网定价页」· 3 条预测未回填 · 已留档 5 天`。
 *
 * 三条边界：
 * 1. **匿名不显示。** 判断按 user_id 隔离，匿名桶是所有访客共用的，没有
 *    "你的待办"可言；而且这张卡是激励不是门槛，未登录不该被它骚扰。
 * 2. **加载失败静默消失。** 它是主路径旁的提示，不是核心内容——为一张
 *    可有可无的卡弹错误横幅，打扰远大于价值。控制台留 error 供排查。
 * 3. **空列表不渲染任何占位。** "你没有待验证的判断"对新用户是纯噪音
 *    （同 ReportPage 的 no_open_judgments 不渲染，一个道理）。
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { ClipboardCheck, ChevronRight } from 'lucide-react'
import { api, getToken } from '@/lib/apiClient'
import type { Judgment } from '@/lib/types'
import { t } from '@/i18n/runtime'

interface TrackGroup {
  /** project_key 优先，缺了退回评审标题——两个都没有的老数据归到"未命名"组 */
  label: string
  count: number
  oldestDays: number
}

function groupJudgments(rows: Judgment[]): TrackGroup[] {
  const now = Date.now()
  const groups = new Map<string, { count: number; oldest: number }>()
  for (const j of rows) {
    const label = j.project_key || j.review_title || t('page.ask.tracking_unnamed.label')
    const g = groups.get(label) ?? { count: 0, oldest: 0 }
    g.count += 1
    if (j.predicted_at) {
      const days = Math.floor((now - new Date(j.predicted_at).getTime()) / 86_400_000)
      if (days > g.oldest) g.oldest = days
    }
    groups.set(label, g)
  }
  return [...groups.entries()]
    .map(([label, g]) => ({ label, count: g.count, oldestDays: g.oldest }))
    // 欠得最久的排最前——它就是最该被处理的那一组
    .sort((a, b) => b.oldestDays - a.oldestDays)
}

/** 确认卡上的回填提醒：用户即将对某个项目发起新评审时，如果这个项目还有
 *  未回填的历史预测，提一句。这句话有真实机制背书——项目记忆按回填结果过滤，
 *  先回填能让"已被推翻的判断"不再进入本次评审的上下文。
 *  自己取数：确认卡的 props 链很深（AskPage → ChatBubble → 确认卡），
 *  为一行提示穿三层 props 不值得。匿名 / 无欠账 / 加载失败都静默不渲染。 */
export function PendingVerifyNudge({ projectKey }: { projectKey: string }) {
  const [count, setCount] = useState(0)

  useEffect(() => {
    if (!getToken() || !projectKey) return
    let cancelled = false
    api
      .listJudgments({ onlyUnverified: true })
      .then((r) => {
        if (cancelled) return
        setCount(r.judgments.filter((j) => j.project_key === projectKey).length)
      })
      .catch(() => {
        // 提醒缺席不影响任何流程，不打扰
      })
    return () => {
      cancelled = true
    }
  }, [projectKey])

  if (count === 0) return null
  return (
    <p className="mt-2 flex flex-wrap items-center gap-x-1.5 text-xs text-text-muted">
      <ClipboardCheck className="h-3.5 w-3.5 shrink-0 text-cyan" strokeWidth={1.5} />
      {t('page.ask.verify_nudge.hint', { total: count })}
      <Link to="/ledger?pending=1" className="text-cyan hover:underline">
        {t('page.ask.verify_nudge.cta')}
      </Link>
    </p>
  )
}

export default function PendingVerificationCard() {
  const [groups, setGroups] = useState<TrackGroup[] | null>(null)
  const [truncated, setTruncated] = useState(false)

  useEffect(() => {
    // 匿名不请求：接口对匿名会 403（require_isolated_identity），
    // 何必发一个注定失败的请求再靠 catch 收拾。
    if (!getToken()) return
    let cancelled = false
    api
      .listJudgments({ onlyUnverified: true })
      .then((r) => {
        if (cancelled) return
        setGroups(groupJudgments(r.judgments))
        // 列表按 limit 截断过：此时总数是下界不是准数，标题显示 "N+"。
        setTruncated(r.truncated === true)
      })
      .catch((e) => {
        // 边界 2：静默。这张卡缺席不影响任何核心流程。
        console.error('[PendingVerificationCard] 待验证列表加载失败：', e)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (!groups || groups.length === 0) return null

  const shown = groups.slice(0, 3)
  const total = groups.reduce((n, g) => n + g.count, 0)

  return (
    <div className="mx-auto mt-6 w-full max-w-sm text-left">
      <div className="rounded-xl border border-border bg-bg-card">
        <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
          <ClipboardCheck className="h-4 w-4 shrink-0 text-cyan" strokeWidth={1.5} />
          <span className="text-xs font-medium text-text-primary">
            {truncated
              ? t('page.ask.tracking_more.title', { total })
              : t('page.ask.tracking.title', { count: total })}
          </span>
        </div>
        <div>
          {shown.map((g) => (
            <Link
              key={g.label}
              // pending=1：落地即筛到"只看待验证"，与卡片上写的条数口径一致。
              // 不带的话点进去是全部记录（含已回填），和这张卡的承诺对不上。
              to="/ledger?pending=1"
              className="flex items-center gap-2 px-4 py-2.5 transition-colors hover:bg-bg-card-hover"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-text-primary">{g.label}</p>
                <p className="text-[11px] text-text-muted">
                  {t('page.ask.tracking.meta', { count: g.count, days: g.oldestDays })}
                </p>
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-text-muted" strokeWidth={1.5} />
            </Link>
          ))}
        </div>
        {/* 回填的真实后果——这句是真的（project_memory_service 按回填结果过滤），
            不是营销话术。这也是这张卡和"待办清单"的本质区别。 */}
        <p className="border-t border-border px-4 py-2 text-[11px] leading-4 text-text-muted">
          {t('page.ask.tracking.hint')}
        </p>
      </div>
    </div>
  )
}
