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
import { ArrowRight, Check, CheckCircle2, Info, KeyRound, Loader2, Mail, Ticket, XCircle } from 'lucide-react'
import { api, claimPendingReviews, setToken } from '@/lib/apiClient'
import { cn } from '@/lib/utils'
import { useSessionStore } from '@/store/session-store'
import type { Plan, UsageSummary } from '@/lib/types'

/** 人工开通的联系方式。必须是真地址——example.com 是 RFC 2606 保留域名，
 *  写在这里等于告诉用户"想付钱请发邮件到黑洞"。 */
const CONTACT_EMAIL = 'REMOVED'
const REPO_ISSUES_URL = 'https://github.com/jedilpf/audiencelens/issues'

/** 后台可以把价格改成小数，所以不能无脑 toFixed(0)，也不该给整数补 ".00" */
function money(n: number): string {
  return Number.isInteger(n) ? `$${n}` : `$${n.toFixed(2)}`
}

function upgradeMailto(plan: Plan): string {
  const subject = `AudienceLens 升级到 ${plan.name} 档`
  // 正文不带用户邮箱等个人信息——收件人从发件地址就能看到，没必要塞进 URL
  const body = `我想升级到 ${plan.name}（${money(plan.price_usd_month)}/月，每天 ${plan.reviews_per_day} 次评审）。\n\n请告诉我怎么付款。`
  return `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
}

export default function PlansPage() {
  const { config, identity, bootstrap } = useSessionStore()

  const [plans, setPlans] = useState<Plan[] | null>(null)
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [plansError, setPlansError] = useState<string | null>(null)

  const [cdkCode, setCdkCode] = useState('')
  const [cdkBusy, setCdkBusy] = useState(false)
  const [cdkError, setCdkError] = useState<string | null>(null)
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
      setPlansError(plansRes.reason instanceof Error ? plansRes.reason.message : '套餐信息加载失败')
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
      setCdkError(e instanceof Error ? e.message : '兑换失败')
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

  return (
    <div className="max-w-5xl mx-auto px-4 py-10 animate-fade-in">
      <header className="mb-8">
        <h1 className="font-display text-3xl md:text-4xl font-bold text-gradient-green mb-2">套餐与额度</h1>
        <p className="text-text-secondary max-w-2xl">
          额度只约束「走平台垫付 Key」的评审。填自己的 API Key（BYOK）跑评审不消耗任何额度，也不受下面这些限制。
        </p>
      </header>

      {/* ---------- 当前状态：这个部署到底按什么规则算额度 ---------- */}
      <section className="mb-8 space-y-3">
        {!quotaEnabled && (
          <Banner tone="info">
            当前部署<strong className="font-semibold">未开启配额限制</strong>：下面各档的每日限额目前不生效，评审不受次数约束。
            运营随时可能在后台打开它——所以档位信息仍然按真实定义展示。
          </Banner>
        )}
        {quotaEnabled && creditsMode && (
          <Banner tone="info">
            当前部署按 <strong className="font-semibold">CDK 次数制</strong>计费：套餐的「每日次数」不生效，
            你的额度就是下面的兑换码余额，每跑一次评审扣 1 次，用完可再兑。
          </Banner>
        )}
        {byokOnly && (
          <Banner tone="info">
            当前部署为 <strong className="font-semibold">BYOK 模式</strong>：评审一律走你自己填的 Key，
            平台不垫付、也就不扣额度。套餐在这种部署下没有实际约束力。
          </Banner>
        )}
        {authEnabled && isAnonymous && (
          <Banner tone="warn">
            你还没登录。未登录时的用量记在<strong className="font-semibold">全站共享的匿名身份</strong>上，
            额度可能已经被别人用掉。
            <Link to="/register" className="ml-1 underline underline-offset-2 hover:text-gold-cream">
              注册一个账号
            </Link>
            ，额度才真正属于你。
          </Banner>
        )}
      </section>

      {/* ---------- 我的额度 ---------- */}
      <section className="mb-10">
        <h2 className="mb-3 font-display text-lg font-semibold text-text-primary">我的额度（近 24 小时）</h2>
        {loading ? (
          <div className="rounded-xl border border-border bg-bg-card p-4 text-sm text-text-muted">正在读取用量…</div>
        ) : usage ? (
          <div className="rounded-xl border border-border bg-bg-card p-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div>
                <div className="text-xs text-text-muted mb-1">当前档位</div>
                <div className="font-display font-bold text-brand-primary">
                  {plans?.find((p) => p.id === currentPlanId)?.name ?? currentPlanId}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-muted mb-1">已用评审</div>
                <div className="font-display font-bold text-text-primary">
                  {usage.reviews_used}
                  {usage.reviews_limit != null && (
                    <span className="font-normal text-text-muted"> / {usage.reviews_limit}</span>
                  )}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-muted mb-1">{creditsMode ? '剩余次数' : '兑换码加量'}</div>
                <div className="font-display font-bold text-warm-orange">
                  {usage.bonus_credits ?? 0}
                  <span className="text-xs font-normal text-text-muted"> 次</span>
                </div>
              </div>
              <div>
                <div className="text-xs text-text-muted mb-1">平台垫付成本</div>
                <div className="font-display font-bold text-text-secondary">
                  ${usage.cost_usd_on_server_key.toFixed(4)}
                  {usage.cost_usd_limit != null && (
                    <span className="font-normal text-text-muted"> / ${usage.cost_usd_limit}</span>
                  )}
                </div>
              </div>
            </div>

            {usage.reviews_limit != null && usage.reviews_limit > 0 && (
              <div className="mt-4">
                <div className="h-2 overflow-hidden rounded-full bg-bg-secondary">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all duration-700',
                      usage.reviews_used >= usage.reviews_limit ? 'bg-severity-critical' : 'bg-cyan',
                    )}
                    style={{
                      width: `${Math.min(100, Math.round((usage.reviews_used / usage.reviews_limit) * 100))}%`,
                    }}
                  />
                </div>
                <p className="mt-1.5 text-xs text-text-muted">
                  配额窗口：{usage.window}（滚动 24 小时，不是自然日）
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-xl border border-border bg-bg-card p-4 text-sm text-text-muted">
            用量读取失败——不影响下面的套餐信息。
          </div>
        )}
      </section>

      {/* ---------- 三档套餐（价格与限额来自后端，后台改价这里立刻跟着变） ---------- */}
      <section className="mb-10">
        <h2 className="mb-3 font-display text-lg font-semibold text-text-primary">套餐</h2>

        {plansError ? (
          <div className="rounded-xl border border-severity-critical/30 bg-severity-critical/10 p-4">
            <p className="text-sm text-severity-critical">{plansError}</p>
            <button
              onClick={() => void load()}
              className="mt-3 rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:text-text-primary"
            >
              重试
            </button>
          </div>
        ) : loading ? (
          <div className="rounded-xl border border-border bg-bg-card p-6 text-sm text-text-muted">正在读取套餐…</div>
        ) : (
          <div className="grid gap-4 md:grid-cols-3">
            {(plans ?? []).map((plan) => {
              const isCurrent = plan.id === currentPlanId
              const isFree = plan.price_usd_month <= 0
              return (
                <div
                  key={plan.id}
                  className={cn(
                    'flex flex-col rounded-xl border p-5 transition-colors',
                    isCurrent
                      ? 'border-brand-primary/50 bg-brand-primary/[0.06]'
                      : 'border-border bg-bg-card hover:bg-bg-card-hover',
                  )}
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <h3 className="font-display text-lg font-bold text-text-primary">{plan.name}</h3>
                    {isCurrent && (
                      <span className="rounded-full border border-brand-primary/30 bg-brand-primary/10 px-2 py-0.5 text-[11px] text-brand-primary">
                        当前档位
                      </span>
                    )}
                  </div>

                  <div className="mb-4">
                    <span className="font-display text-3xl font-bold text-text-primary">
                      {money(plan.price_usd_month)}
                    </span>
                    <span className="text-sm text-text-muted"> / 月</span>
                  </div>

                  <ul className="mb-5 space-y-2 text-sm text-text-secondary">
                    <li className="flex items-start gap-2">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-primary" strokeWidth={1.5} />
                      <span>
                        每天 <strong className="text-text-primary">{plan.reviews_per_day}</strong> 次评审
                        {!quotaEnabled && <span className="text-text-muted">（当前部署未启用限额）</span>}
                        {quotaEnabled && creditsMode && <span className="text-text-muted">（次数制部署下不生效）</span>}
                      </span>
                    </li>
                    <li className="flex items-start gap-2">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-primary" strokeWidth={1.5} />
                      <span>
                        平台垫付成本上限 <strong className="text-text-primary">${plan.cost_usd_per_day}</strong> / 天
                      </span>
                    </li>
                    <li className="flex items-start gap-2">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-primary" strokeWidth={1.5} />
                      <span>自带 Key（BYOK）不限次，不计额度</span>
                    </li>
                  </ul>

                  <div className="mt-auto">
                    {isCurrent ? (
                      <div className="rounded-lg border border-border px-4 py-2.5 text-center text-sm text-text-muted">
                        你正在用这一档
                      </div>
                    ) : isFree ? (
                      <div className="rounded-lg border border-border px-4 py-2.5 text-center text-sm text-text-muted">
                        免费档 · 无需付费
                      </div>
                    ) : (
                      <a
                        href={upgradeMailto(plan)}
                        className="flex items-center justify-center gap-2 rounded-lg border border-brand-primary/30 bg-brand-primary/10 px-4 py-2.5 text-sm font-medium text-brand-primary transition-all hover:bg-brand-primary/20 hover:border-brand-primary/50"
                      >
                        <Mail className="h-4 w-4" strokeWidth={1.5} />
                        联系升级
                      </a>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <p className="mt-3 flex items-start gap-2 text-xs text-text-muted">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
          <span>
            三档之间目前<strong className="text-text-secondary">只差额度</strong>：功能完全相同，没有专属人格、没有多席位、
            没有团队协作空间。写在这里是为了让你按真实差异做决定——等这些能力真做出来了，这句话才会改。
          </span>
        </p>
      </section>

      {/* ---------- 为什么没有"立即支付" ---------- */}
      <section className="mb-10 rounded-xl border border-warm-orange/30 bg-warm-orange/[0.07] p-5">
        <h2 className="mb-2 font-display text-base font-semibold text-warm-orange">为什么这里没有「立即支付」按钮</h2>
        <p className="text-sm text-text-secondary">
          在线支付还没接：没有 Stripe、没有支付宝、没有微信支付。与其放一个点下去跳空的按钮，不如直接说清楚
          今天真能走通的两条路——下面这两个都是接好的，不是占位。付款方式接上之后，这一段会换成真正的结账入口。
        </p>
      </section>

      {/* ---------- 真路径 1：兑换 CDK（本页直接兑，与设置页同一个接口） ---------- */}
      <section className="mb-8">
        <div className="rounded-xl border border-border bg-bg-card p-5">
          <h2 className="mb-1 flex items-center gap-2 font-display text-base font-semibold text-text-primary">
            <Ticket className="h-4 w-4 text-warm-orange" strokeWidth={1.5} />
            兑换码（CDK）
          </h2>
          <p className="mb-3 text-xs text-text-muted">
            {creditsMode
              ? '兑换后获得评审次数：每次评审消耗 1 次，用完可再兑。'
              : '兑换后获得加量次数：套餐日限用完后自动垫上，走平台垫付 Key 时生效。'}
            {authEnabled && ' 无需注册——匿名兑换会自动创建游客身份，次数存在这个浏览器里，清缓存前别弄丢。'}
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
              placeholder="AL-XXXX-XXXX-XXXX"
              aria-label="兑换码"
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
              兑换
            </button>
          </div>

          {cdkSuccess && (
            <p className="mt-2 flex flex-wrap items-center gap-1.5 text-sm text-brand-primary animate-fade-in">
              <CheckCircle2 className="h-4 w-4" strokeWidth={1.5} />
              兑换成功 +{cdkSuccess.granted} 次，当前余额 {cdkSuccess.balance} 次
              {cdkSuccess.guest && <span className="text-xs text-text-muted">（已为你创建游客身份并自动登录）</span>}
            </p>
          )}
          {cdkError && (
            <p className="mt-2 flex items-start gap-1.5 text-sm text-severity-critical">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.5} />
              <span>{cdkError}</span>
            </p>
          )}

          <p className="mt-3 text-xs text-text-muted">
            没有码？发邮件说明用途，我给你发一个。
            <a
              href={`mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent('AudienceLens 兑换码申请')}`}
              className="ml-1 text-brand-primary underline underline-offset-2 hover:text-gold-cream"
            >
              {CONTACT_EMAIL}
            </a>
          </p>
        </div>
      </section>

      {/* ---------- 真路径 2：人工开通 / 3：BYOK ---------- */}
      <section className="mb-10 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-border bg-bg-card p-5">
          <h2 className="mb-1 flex items-center gap-2 font-display text-base font-semibold text-text-primary">
            <Mail className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
            人工开通 Pro / Team
          </h2>
          <p className="mb-3 text-sm text-text-secondary">
            AudienceLens 由一个人做。写封邮件说明你要哪一档、账号邮箱是什么，我手动把你的账号改档
            （改完下一次请求就生效），或者直接给你发等额兑换码。
          </p>
          <div className="flex flex-wrap gap-3 text-sm">
            <a
              href={`mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent('AudienceLens 升级咨询')}`}
              className="flex items-center gap-1.5 text-brand-primary underline underline-offset-2 hover:text-gold-cream"
            >
              {CONTACT_EMAIL}
            </a>
            <a
              href={REPO_ISSUES_URL}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 text-text-muted underline underline-offset-2 hover:text-text-secondary"
            >
              GitHub Issues
            </a>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-bg-card p-5">
          <h2 className="mb-1 flex items-center gap-2 font-display text-base font-semibold text-text-primary">
            <KeyRound className="h-4 w-4 text-cyan" strokeWidth={1.5} />
            不想付月费？自带 Key
          </h2>
          <p className="mb-3 text-sm text-text-secondary">
            填自己的 API Key（Anthropic 原生，或任意 OpenAI 兼容服务），评审走你自己的额度：
            不消耗平台次数、不受日限约束，token 花费直接结算在你的服务商账单上。
          </p>
          <Link
            to="/settings"
            className="inline-flex items-center gap-1.5 text-sm text-cyan underline underline-offset-2 hover:text-cyan-dim"
          >
            去设置页填 Key
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
