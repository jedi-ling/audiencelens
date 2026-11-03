/**
 * Pricing / plans page. owner: agent-8 (same owner as zh/page.plans.ts).
 *
 * 译注（保留中文以便与 zh 侧对读）：
 * 1. mailto 的 subject / body 不在这张表里，恒为中文——收件人是站方本人（契约 12.2）。
 * 2. 带 count 的 key 在 en 侧必须同时有 _one 和 _other；调用方只写逻辑 key。
 * 3. 这里的英文是给英文用户看的产品文案，按英文表达习惯写，不是中文的字面对应：
 *    "我的额度（近 24 小时）" → "Your quota (last 24 hours)"，
 *    "平台承担模型调用费用" → "Model usage is on us"。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Plans & quota',

  'header.title': 'Plans & quota',
  'header.desc':
    'Reviews you run with your own API key (BYOK) never touch your plan quota. Plan quota applies only when you use the platform’s key.',

  banner_byok:
    'This deployment runs in <mode>BYOK mode</mode>: reviews use the key you supply, so plan quotas don’t apply.',
  banner_no_quota:
    'This deployment has <mode>quota limits switched off</mode> — reviews aren’t capped right now.',
  banner_credits:
    'This deployment bills in <mode>CDK credits</mode>: each review costs one credit, and you can redeem more once you run out.',

  'anon.hint':
    'While you’re signed out, usage lives in this browser under a shared anonymous identity. <register>Create an account</register> to tie your quota to you.',

  'quota.title': 'Your quota (last 24 hours)',
  'quota.pending': 'Loading usage…',
  'quota.error': 'Usage is unavailable right now',
  'tier.label': 'Current plan',
  'used.label': 'Reviews used',
  'credits.label': 'Credits left',
  'bonus.label': 'Redeemed top-up',
  // 单位跟着数量走，所以两条变体都要有；<unit> 槽的内容与 zh 侧的 span 同一个。
  'credits.value_one': '{{count}}<unit>credit</unit>',
  'credits.value_other': '{{count}}<unit>credits</unit>',
  'progress.label': 'Quota used',
  'progress.hint': 'Quota window: {{window}}',

  'list.title': 'Plans',
  'list.pending': 'Loading plans…',
  'list.error': 'Could not load plan information',
  tagline_free: 'Try it out',
  tagline_pro: 'Serious solo use',
  tagline_team: 'High-volume team reviews',
  'price.unit': '/ mo',
  feature_reviews_one: '<n>{{count}}</n> review per day',
  feature_reviews_other: '<n>{{count}}</n> reviews per day',
  feature_cost: 'Model usage is on us',
  feature_byok: 'Bring your own key — unlimited, quota never applies',
  'card.badge': 'Current',
  'card.label': 'In use',
  'card.hint': 'Free · nothing to pay',
  'card.cta': 'Request an upgrade',

  'cdk.title': 'Redemption code (CDK)',
  cdk_desc_credits: 'Redeeming adds review credits; each review costs one credit.',
  cdk_desc_plan:
    'Redeeming adds top-up reviews, which kick in automatically once your plan’s daily limit runs out.',
  'cdk.hint': 'No account needed — credits redeemed anonymously stay in this browser.',
  'cdk.placeholder': 'AL-XXXX-XXXX-XXXX',
  'cdk.aria': 'Redemption code',
  'cdk.cta': 'Redeem',
  'cdk.success_one': 'Redeemed — {{count}} credit added, balance now {{balance}}',
  'cdk.success_other': 'Redeemed — {{count}} credits added, balance now {{balance}}',
  'cdk.error': 'Could not redeem that code',
  'guest.hint': '(a guest identity was created and signed in for you)',
  'request.hint': 'Need a code? Request one on <mail>GitHub Issues</mail> (please don\'t post your email or other personal details).',

  'manual.title': 'Manual Pro / Team activation',
  'manual.desc':
    'To move to Pro or Team, open a GitHub issue saying which plan you want (issues are public, so leave out your email and other personal details).',
  'byok.title': 'Bring your own API key',
  'byok.desc':
    'Add your own API key (native Anthropic, or any OpenAI-compatible service). Reviews then draw on your API quota instead of ours — no per-day cap, no platform limits — and your provider bills you for tokens directly.',
  'byok.cta': 'Add a key in Settings',
} satisfies Messages
