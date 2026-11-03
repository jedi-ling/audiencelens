/**
 * 定价 / 套餐页 —— 用户想给钱时的落点。
 *
 * 在这之前配额提示写着"可升级套餐"，但全站没有任何一条 /plans 路由，
 * api.plans() 零调用点：撞到限额的人找不到地方付钱。这一页补的就是这个洞。
 *
 * 三条纪律写在最前面，免得后面有人往里塞"看起来能用"的东西：
 *
 *   1. 价格与限额一律从 GET /api/plans 拉。后台面板能改价
 *      （plan_service.set_plan_override / quota_free_*），前端写死当场就和真实
 *      计费口径对不上。
 *
 *   2. 在线支付**没有接**——仓库里没有 Stripe / 支付宝 / 微信支付的任何集成。
 *      所以本页不画"立即支付"按钮。今天真能走通的付费路径只有两条：
 *        · 兑换 CDK（POST /api/cdk/redeem，本页直接兑，无需注册）
 *        · 联系人工开通（管理员 PUT /api/admin/users/{id} 改 plan，立即生效）
 *
 *   3. 三档之间**只差额度**。plan_service 里 free/pro/team 的差异只有
 *      price_usd_month / reviews_per_day / cost_usd_per_day 三个字段，
 *      后端没有任何按 plan 分支的功能开关。所以这里不许出现"Team 支持多人协作"
 *      "Pro 解锁高级人格"之类的卖点——那是凭空发明的承诺。
 */

import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { ArrowRight, Check, CheckCircle2, Crown, Info, KeyRound, Loader2, Mail, Sparkles, Ticket, XCircle, Zap } from 'lucide-react'
import { api, claimPendingReviews, setToken } from '@/lib/apiClient'
import { cn } from '@/lib/utils'
import { useSessionStore } from '@/store/session-store'
import type { Plan, UsageSummary } from '@/lib/types'
import { t, Trans } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import { formatNumber, formatPercent, formatUsd } from '@/i18n/format'
import { tApiError } from '@/i18n/api-error'

/** 人工开通 / 申请兑换码的唯一联系渠道：仓库的 GitHub Issues。
 *  界面上不放任何邮箱地址——个人邮箱写进前端就是公开给爬虫。 */
const REPO_ISSUES_URL = 'https://github.com/jedi-ling/audiencelens/issues'

/** 后台可以把价格改成小数，所以不能无脑 toFixed(0)，也不该给整数补 ".00" */
function money(n: number): string {
  // 走 @/i18n/format 而不是自己拼 `$${n}`：千分位与小数点要跟界面语言走
  // （契约 6.5）。货币符号恒 '$'，不做汇率换算——我们没有汇率事实源。
  return Number.isInteger(n) ? formatUsd(n, 0) : formatUsd(n, 2)
}

/**
 * 升级申请：打开一个预填标题的 GitHub issue。
 *
 * ⚠ 标题 / 正文 **恒为中文，不进 key 表**（契约 12.2）：收件人是作者本人，
 * 不是终端用户——跟着 ui_lang 翻的话，界面切成英文的中文用户会发出一封英文申请。
 * 正文刻意不带账号邮箱等个人信息：issue 是公开的。
 */
function upgradeIssueUrl(plan: Plan, showPlatformQuota: boolean): string {
  const title = `AudienceLens 升级到 ${plan.name} 档`
  const quota = showPlatformQuota ? `，每天 ${plan.reviews_per_day} 次评审` : ''
  const body = `我想升级到 ${plan.name}（${money(plan.price_usd_month)}/月${quota}）。\n\n（请不要在这里贴邮箱、密码等个人信息。）`
  return `${REPO_ISSUES_URL}/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`
}

export default function PlansPage() {
  useDocumentTitle('page.plans.meta.title')
  const { config, identity, bootstrap } = useSessionStore()

  const [plans, setPlans] = useState<Plan[] | null>(null)
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [loading, setLoading] = useState(true)
  // 存的是**错误对象**不是已翻好的字符串。存字符串的话文案在 catch 的那一刻
  // 就固定了，用户之后切语言错误横幅还留在旧语言里——和"模块级常量存 key
  // 不存文案"是同一个坑，只是换到了组件 state 上。包一层对象是为了让
  // `null = 没出错` 与 `{ e: undefined } = 出错了但拿到的是 undefined` 可分。
  const [plansError, setPlansError] = useState<{ e: unknown } | null>(null)

  const [cdkCode, setCdkCode] = useState('')
  const [cdkBusy, setCdkBusy] = useState(false)
  const [cdkError, setCdkError] = useState<{ e: unknown } | null>(null)
  const [cdkSuccess, setCdkSuccess] = useState<{ granted: number; balance: number; guest: boolean } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setPlansError(null)
    // 套餐是获客内容、用量是个人数据：一个挂了不该把另一个一起拖没。
    // 未登录时 /api/usage 也是通的（optional_identity），返回匿名桶的用量。
    const [plansRes, usageRes] = await Promise.allSettled([api.plans(), api.usage()])
    if (plansRes.status === 'fulfilled') {
      setPlans(plansRes.value.plans)
    } else {
      setPlansError({ e: plansRes.reason })
    }
    setUsage(usageRes.status === 'fulfilled' ? usageRes.value : null)
    setLoading(false)
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleRedeem = async () => {
    if (!cdkCode.trim() || cdkBusy) return
    setCdkBusy(true)
    setCdkError(null)
    setCdkSuccess(null)
    try {
      const result = await api.redeemCdk(cdkCode.trim())
      if (result.token) {
        // 匿名兑换时后端会签发游客身份 token。不存下来，这次充的次数就跟着
        // 请求一起丢了（下一次请求又变回全站共享的 anonymous 桶）。
        setToken(result.token)
        // 身份从共享的 "anonymous" 变成独立游客 id，之前匿名跑的评审在所有读取
        // 路由上立刻 404（后端按 user_id 精确比对归属）。不认领的话，用户兑换完
        // 回头找刚才那份报告会发现"评审不存在"——与登录/注册路径同一处理。
        // 认领失败不该反噬兑换本身，所以吞掉异常但只吞这一处。
        await claimPendingReviews().catch(() => {})
        await bootstrap() // 顶栏和全站 identity 要跟上新身份
      }
      setCdkSuccess({
        granted: result.credits_granted,
        balance: result.balance,
        guest: !!result.guest,
      })
      setCdkCode('')
      const fresh = await api.usage().catch(() => null)
      if (fresh) setUsage(fresh)
    } catch (e) {
      setCdkError({ e })
    } finally {
      setCdkBusy(false)
    }
  }

  const currentPlanId = identity?.plan ?? 'free'
  const isAnonymous = !identity || identity.is_anonymous
  const authEnabled = config?.auth_enabled !== false
  // 限额到底生不生效，以 /api/usage 的实时值为准（后台面板能实时关配额）；
  // 拿不到用量时退而用 /api/health 的 config，两者都没有就别乱下结论。
  const quotaEnabled = usage ? usage.quota_enabled : (config?.quota_enabled ?? true)
  const creditsMode = usage?.quota_mode === 'credits'
  const byokOnly = config?.key_mode === 'byok'
  // 部署方没配平台 Key：套餐里"每天 N 次评审 / 平台承担费用"这两条承诺兑现不了——
  // 那 N 次是按平台 Key 计的，而平台 Key 根本不存在。此时隐藏这两条，置顶说明只支持 BYOK。
  // 为什么是隐藏而不是"按成本上限 ÷ 单次成本"换算出一个数：代码里只有单次评审的
  // token 估算（AL_QUOTA_TOKENS_PER_REVIEW_ESTIMATE），没有 token 单价，
  // 换算出来的数字没有事实源，等于再编一个承诺。拿不到 config 时不下结论。
  const noPlatformKey = config ? !config.server_key_present : false
  const showPlatformQuota = !noPlatformKey

  return (
    <div className="max-w-5xl mx-auto px-4 py-10 animate-fade-in">
      <header className="mb-10">
        <div className="flex items-center gap-3 mb-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-primary/10 border border-brand-primary/20">
            <Crown className="h-5 w-5 text-brand-primary" strokeWidth={1.5} />
          </div>
          <h1 className="font-display text-3xl md:text-4xl font-bold text-text-primary">{t('page.plans.header.title')}</h1>
        </div>
        <p className="text-text-secondary max-w-2xl text-[15px] leading-relaxed">
          {t('page.plans.header.desc')}
        </p>
      </header>

      {/* ---------- 当前状态：这个部署到底按什么规则算额度 ---------- */}
      <section className="mb-8 space-y-2">
        {/* 三条横幅是互斥分支，各一条整句 key：<mode> 槽就是原来那个 <strong>。
            不拆成「当前部署 + {模式名} + 后半句」——那等于把语序锁死成中文的，
            英文里强调词的位置和中文不在一处。 */}
        {noPlatformKey && (
          <Banner tone="info">
            <Trans k="page.plans.banner_no_platform_key" slots={{ mode: (s) => <strong className="font-semibold">{s}</strong> }} />
          </Banner>
        )}
        {byokOnly ? (
          <Banner tone="info">
            <Trans k="page.plans.banner_byok" slots={{ mode: (s) => <strong className="font-semibold">{s}</strong> }} />
          </Banner>
        ) : !quotaEnabled ? (
          <Banner tone="info">
            <Trans k="page.plans.banner_no_quota" slots={{ mode: (s) => <strong className="font-semibold">{s}</strong> }} />
          </Banner>
        ) : creditsMode ? (
          <Banner tone="info">
            <Trans k="page.plans.banner_credits" slots={{ mode: (s) => <strong className="font-semibold">{s}</strong> }} />
          </Banner>
        ) : null}
        {authEnabled && isAnonymous && (
          <p className="text-xs text-text-muted">
            <Trans
              k="page.plans.anon.hint"
              slots={{
                register: (s) => (
                  <Link to="/register" className="underline underline-offset-2 hover:text-text-primary">
                    {s}
                  </Link>
                ),
              }}
            />
          </p>
        )}
      </section>

      {/* ---------- 我的额度 ---------- */}
      <section className="mb-10">
        <h2 className="mb-4 font-display text-lg font-semibold text-text-primary">{t('page.plans.quota.title')}</h2>
        {loading ? (
          <div className="rounded-xl border border-border bg-bg-card p-4 text-sm text-text-muted">{t('page.plans.quota.pending')}</div>
        ) : usage ? (
          <div className="rounded-2xl border border-border bg-bg-card p-5">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="rounded-xl bg-bg-primary/50 border border-border/80 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-brand-primary/10">
                    <Sparkles className="h-3.5 w-3.5 text-brand-primary" strokeWidth={2} />
                  </div>
                  <div className="text-xs text-text-muted">{t('page.plans.tier.label')}</div>
                </div>
                <div className="font-display text-xl font-bold text-brand-primary">
                  {/* 套餐名来自后端目录，不是本页文案。拉不到套餐表时退回 plan id
                      （free / pro / team）——它是真实的档位标识，不是编出来的名字。 */}
                  {plans?.find((p) => p.id === currentPlanId)?.name ?? currentPlanId}
                </div>
              </div>
              <div className="rounded-xl bg-bg-primary/50 border border-border/80 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-cyan/10">
                    <Zap className="h-3.5 w-3.5 text-cyan" strokeWidth={2} />
                  </div>
                  <div className="text-xs text-text-muted">{t('page.plans.used.label')}</div>
                </div>
                <div className="font-display text-xl font-bold text-text-primary">
                  {formatNumber(usage.reviews_used)}
                  {usage.reviews_limit != null && (
                    <span className="font-normal text-text-muted text-sm ml-1">/ {formatNumber(usage.reviews_limit)}</span>
                  )}
                </div>
              </div>
              <div className="rounded-xl bg-bg-primary/50 border border-border/80 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-warm-orange/10">
                    <Ticket className="h-3.5 w-3.5 text-warm-orange" strokeWidth={2} />
                  </div>
                  <div className="text-xs text-text-muted">
                    {creditsMode ? t('page.plans.credits.label') : t('page.plans.bonus.label')}
                  </div>
                </div>
                <div className="font-display text-xl font-bold text-warm-orange">
                  {/* 数字与单位是一句话：英文的 credit / credits 要按数量选词，
                      拆成「数字 + 固定单位」两段就选不了了。<unit> 槽保留原来那个小字号 span。 */}
                  <Trans
                    k="page.plans.credits.value"
                    vars={{ count: usage.bonus_credits ?? 0 }}
                    slots={{ unit: (s) => <span className="text-xs font-normal text-text-muted ml-1">{s}</span> }}
                  />
                </div>
              </div>
            </div>

            {usage.reviews_limit != null && usage.reviews_limit > 0 && (
              <div className="mt-5">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-text-muted">{t('page.plans.progress.label')}</span>
                  <span className="text-xs font-medium text-text-secondary">
                    {/* formatPercent 收的是**比值**不是 87 这种已乘过 100 的数，
                        百分号也由它按 locale 出（契约 6.5） */}
                    {formatPercent(Math.min(1, usage.reviews_used / usage.reviews_limit))}
                  </span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-bg-primary">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all duration-700',
                      usage.reviews_used >= usage.reviews_limit ? 'bg-severity-critical' : 'bg-gradient-to-r from-brand-primary to-cyan',
                    )}
                    style={{
                      width: `${Math.min(100, Math.round((usage.reviews_used / usage.reviews_limit) * 100))}%`,
                    }}
                  />
                </div>
                <p className="mt-2 text-xs text-text-muted">
                  {/* window 是后端给的窗口字面量（现在恒为 "24h"），不是文案，原样透出 */}
                  {t('page.plans.progress.hint', { window: usage.window })}
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-xl border border-border bg-bg-card p-4 text-sm text-text-muted">
            {t('page.plans.quota.error')}
          </div>
        )}
      </section>

      {/* ---------- 三档套餐（价格与限额来自后端，后台改价这里立刻跟着变） ---------- */}
      <section className="mb-10">
        <h2 className="mb-5 font-display text-lg font-semibold text-text-primary">{t('page.plans.list.title')}</h2>

        {plansError ? (
          <div className="rounded-xl border border-severity-critical/30 bg-severity-critical/10 p-4">
            {/* 在渲染处翻，不在 catch 里翻：切语言时这条横幅要跟着变。
                tApiError 保证后端中文不会混排进英文界面（契约 D2）。 */}
            <p className="text-sm text-severity-critical">{tApiError(plansError.e, 'page.plans.list.error')}</p>
            <button
              onClick={() => void load()}
              className="mt-3 rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:text-text-primary"
            >
              {t('common.action.retry')}
            </button>
          </div>
        ) : loading ? (
          <div className="rounded-xl border border-border bg-bg-card p-6 text-sm text-text-muted">{t('page.plans.list.pending')}</div>
        ) : (
          <div className="grid gap-5 md:grid-cols-3 md:items-stretch">
            {(plans ?? []).map((plan) => {
              const isCurrent = plan.id === currentPlanId
              const isFree = plan.price_usd_month <= 0
              const tierIndex = plan.id === 'free' ? 0 : plan.id === 'pro' ? 1 : 2
              const tierColor =
                tierIndex === 0
                  ? 'from-slate-400/40 to-slate-300/20'
                  : tierIndex === 1
                    ? 'from-brand-primary/40 to-brand-primary/15'
                    : 'from-amber-400/50 to-amber-300/20'
              const tierAccent =
                tierIndex === 0 ? 'bg-slate-400' : tierIndex === 1 ? 'bg-brand-primary' : 'bg-amber-400'
              const tierIcon = tierIndex === 0 ? <Sparkles className="h-4 w-4" /> : tierIndex === 1 ? <Zap className="h-4 w-4" /> : <Crown className="h-4 w-4" />

              return (
                <div
                  key={plan.id}
                  className={cn(
                    // h-full 撑满 grid 行：三张卡同高，底部操作区靠 mt-auto 对齐到同一基线
                    'group relative flex h-full flex-col overflow-hidden rounded-2xl border transition-all duration-300',
                    isCurrent
                      // 当前档的视觉权重来自描边 + 底色，不靠错位浮动 badge 破坏整行基线
                      ? 'border-brand-primary/50 bg-brand-primary/[0.06] shadow-[0_8px_32px_rgba(0,113,227,0.12)]'
                      : 'border-border bg-bg-card shadow-[0_2px_12px_rgba(0,0,0,0.04)] hover:shadow-[0_8px_32px_rgba(0,0,0,0.08)] hover:-translate-y-1',
                  )}
                >
                  {/* 顶部渐变 accent 条 */}
                  <div className={cn('h-1.5 w-full bg-gradient-to-r', tierColor)} />

                  {/* 当前档位标记：放在卡内文档流里（右上角），不用 absolute 浮出卡片，
                      三张卡的内容起点保持同一基线 */}
                  {isCurrent && (
                    <div className="flex justify-end px-6 pt-4">
                      <span className="inline-flex items-center gap-1 rounded-full bg-brand-primary px-2.5 py-1 text-[10px] font-bold text-white shadow-sm">
                        <CheckCircle2 className="h-3 w-3" strokeWidth={2} />
                        {t('page.plans.card.badge')}
                      </span>
                    </div>
                  )}

                  <div className={cn('flex flex-1 flex-col p-6', isCurrent && 'pt-3')}>
                    {/* 档位名 + 图标 */}
                    <div className="mb-4 flex items-center gap-2.5">
                      <div className={cn('flex h-9 w-9 items-center justify-center rounded-xl text-white shadow-sm', tierAccent)}>
                        {tierIcon}
                      </div>
                      <div>
                        <h3 className="font-display text-base font-bold text-text-primary">{plan.name}</h3>
                        <p className="text-[11px] text-text-muted">
                          {tierIndex === 0
                            ? t('page.plans.tagline_free')
                            : tierIndex === 1
                              ? t('page.plans.tagline_pro')
                              : t('page.plans.tagline_team')}
                        </p>
                      </div>
                    </div>

                    {/* 价格：大字号 + 强对比；tabular-nums 让三档数字纵向对齐 */}
                    <div className="mb-5 flex items-baseline gap-1">
                      <span className="font-display text-4xl font-extrabold tracking-tight text-text-primary tabular-nums">
                        {money(plan.price_usd_month)}
                      </span>
                      <span className="text-sm text-text-muted">{t('page.plans.price.unit')}</span>
                    </div>

                    {/* 特性列表 */}
                    <ul className="mb-6 space-y-2.5 text-sm text-text-secondary">
                      {showPlatformQuota && (
                        <>
                          <li className="flex items-start gap-2.5">
                            <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-primary/10">
                              <Check className="h-3 w-3 text-brand-primary" strokeWidth={2.5} />
                            </div>
                            <span>
                              {/* 数字插在句子中间，中英语序不同（"每天 N 次评审" / "N reviews per day"）。
                                  整句一条 key，<n> 槽保留原来那个 tabular-nums 的 <strong>。 */}
                              <Trans
                                k="page.plans.feature_reviews"
                                vars={{ count: plan.reviews_per_day }}
                                slots={{ n: (s) => <strong className="text-text-primary tabular-nums">{s}</strong> }}
                              />
                            </span>
                          </li>
                          <li className="flex items-start gap-2.5">
                            <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-primary/10">
                              <Check className="h-3 w-3 text-brand-primary" strokeWidth={2.5} />
                            </div>
                            <span>{t('page.plans.feature_cost')}</span>
                          </li>
                        </>
                      )}
                      <li className="flex items-start gap-2.5">
                        <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-primary/10">
                          <Check className="h-3 w-3 text-brand-primary" strokeWidth={2.5} />
                        </div>
                        <span>{t('page.plans.feature_byok')}</span>
                      </li>
                    </ul>

                    {/* 底部操作区 */}
                    <div className="mt-auto">
                      {isCurrent ? (
                        <div className="flex items-center justify-center gap-2 rounded-xl border-2 border-brand-primary/30 bg-brand-primary/10 px-4 py-3 text-sm font-semibold text-brand-primary">
                          <CheckCircle2 className="h-4 w-4" strokeWidth={2} />
                          {t('page.plans.card.label')}
                        </div>
                      ) : isFree ? (
                        <div className="flex items-center justify-center gap-2 rounded-xl border border-border bg-bg-primary/50 px-4 py-3 text-sm font-medium text-text-muted">
                          <Sparkles className="h-4 w-4" strokeWidth={1.5} />
                          {t('page.plans.card.hint')}
                        </div>
                      ) : (
                        <a
                          href={upgradeIssueUrl(plan, showPlatformQuota)}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center justify-center gap-2 rounded-xl bg-brand-primary px-4 py-3 text-sm font-bold text-white shadow-sm transition-all hover:bg-brand-primary/90 hover:shadow-[0_4px_16px_rgba(0,113,227,0.3)] active:scale-[0.98]"
                        >
                          <Mail className="h-4 w-4" strokeWidth={1.5} />
                          {t('page.plans.card.cta')}
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* ---------- 兑换 CDK ---------- */}
      <section className="mb-8">
        <div className="rounded-xl border border-border bg-bg-card p-5">
          <h2 className="mb-1 flex items-center gap-2 font-display text-base font-semibold text-text-primary">
            <Ticket className="h-4 w-4 text-warm-orange" strokeWidth={1.5} />
            {t('page.plans.cdk.title')}
          </h2>
          <p className="mb-3 text-xs text-text-muted">
            {creditsMode
              ? t('page.plans.cdk_desc_credits')
              : t('page.plans.cdk_desc_plan')}
            {/* 句间空格留在 JSX 里，不写进译文——译文里的首尾空格看不见，改的人会顺手吃掉 */}
            {authEnabled && ` ${t('page.plans.cdk.hint')}`}
          </p>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input
              type="text"
              value={cdkCode}
              onChange={(e) => {
                setCdkCode(e.target.value.toUpperCase())
                setCdkError(null)
                setCdkSuccess(null)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void handleRedeem()
              }}
              placeholder={t('page.plans.cdk.placeholder')}
              aria-label={t('page.plans.cdk.aria')}
              className="min-w-0 flex-1 rounded-lg border border-border bg-bg-secondary px-4 py-2.5 font-mono text-sm tracking-wider text-text-primary placeholder-text-muted transition-colors focus:border-warm-orange focus:outline-none"
            />
            <button
              onClick={() => void handleRedeem()}
              disabled={cdkBusy || !cdkCode.trim()}
              className={cn(
                'flex shrink-0 items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-bold transition-all',
                cdkBusy || !cdkCode.trim()
                  ? 'cursor-not-allowed bg-bg-secondary text-text-muted'
                  : 'bg-warm-orange/15 text-warm-orange hover:bg-warm-orange/25',
              )}
            >
              {cdkBusy ? (
                <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
              ) : (
                <Ticket className="h-4 w-4" strokeWidth={1.5} />
              )}
              {t('page.plans.cdk.cta')}
            </button>
          </div>

          {cdkSuccess && (
            <p className="mt-2 flex flex-wrap items-center gap-1.5 text-sm text-brand-primary animate-fade-in">
              <CheckCircle2 className="h-4 w-4" strokeWidth={1.5} />
              {/* 一句里两个数：复数只能挂一个（ICU 同限制），挂本次到账的 count，
                  balance 当普通插值。 */}
              {t('page.plans.cdk.success', { count: cdkSuccess.granted, balance: cdkSuccess.balance })}
              {cdkSuccess.guest && <span className="text-xs text-text-muted">{t('page.plans.guest.hint')}</span>}
            </p>
          )}
          {cdkError && (
            <p className="mt-2 flex items-start gap-1.5 text-sm text-severity-critical">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.5} />
              <span>{tApiError(cdkError.e, 'page.plans.cdk.error')}</span>
            </p>
          )}

          <p className="mt-3 text-xs text-text-muted">
            {/* issue 标题恒为中文——收件人是作者本人（契约 12.2）。 */}
            <Trans
              k="page.plans.request.hint"
              slots={{
                mail: (s) => (
                  <a
                    href={`${REPO_ISSUES_URL}/new?title=${encodeURIComponent('AudienceLens 兑换码申请')}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-brand-primary underline underline-offset-2 hover:text-text-primary"
                  >
                    {s}
                  </a>
                ),
              }}
            />
          </p>
        </div>
      </section>

      {/* ---------- 其他方式 ---------- */}
      <section className="mb-10 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-border bg-bg-card p-5">
          <h2 className="mb-1 flex items-center gap-2 font-display text-base font-semibold text-text-primary">
            <Mail className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
            {t('page.plans.manual.title')}
          </h2>
          <p className="mb-3 text-sm text-text-secondary">
            {t('page.plans.manual.desc')}
          </p>
          <div className="flex flex-wrap gap-3 text-sm">
            <a
              href={REPO_ISSUES_URL}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 text-brand-primary underline underline-offset-2 hover:text-text-primary"
            >
              GitHub Issues
            </a>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-bg-card p-5">
          <h2 className="mb-1 flex items-center gap-2 font-display text-base font-semibold text-text-primary">
            <KeyRound className="h-4 w-4 text-cyan" strokeWidth={1.5} />
            {t('page.plans.byok.title')}
          </h2>
          <p className="mb-3 text-sm text-text-secondary">
            {t('page.plans.byok.desc')}
          </p>
          <Link
            to="/settings"
            className="inline-flex items-center gap-1.5 text-sm text-cyan underline underline-offset-2 hover:text-cyan-dim"
          >
            {t('page.plans.byok.cta')}
            <ArrowRight className="h-3.5 w-3.5" strokeWidth={1.5} />
          </Link>
        </div>
      </section>
    </div>
  )
}

function Banner({ tone, children }: { tone: 'info' | 'warn'; children: ReactNode }) {
  return (
    <div
      className={cn(
        'flex items-start gap-2 rounded-lg border px-4 py-3 text-sm',
        tone === 'warn'
          ? 'border-warm-orange/30 bg-warm-orange/10 text-warm-orange'
          : 'border-border bg-bg-card text-text-secondary',
      )}
    >
      <Info className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.5} />
      <span>{children}</span>
    </div>
  )
}
