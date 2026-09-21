/**
 * owner: agent-3。分工与四条硬规定见 zh/page.settings.ts 的文件头。
 *
 * 英文侧两处需要特别注意：
 *
 * 1. `delete_confirm.label` 里的 {{phrase}} 是**后端的字面量比较凭据**，
 *    恒为中文「删除我的账号」（common.action.delete_account_phrase）。
 *    所以英文提示必须显式说"照着敲这句中文"——不说的话英文用户会去输
 *    "Delete my account"，后端比对不上，账号永远删不掉，而且报错还是中文。
 *
 * 2. BYOK 隐私段的措辞在中文侧是刻意保守的（只陈述做了什么，不做安全承诺）。
 *    英文这边同样不写 "fully secure" / "guaranteed" 这类词——那会变成一个
 *    源码里查不到的承诺。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Settings',

  'header.title': 'Settings',
  'header.desc': 'Your account, model access, usage and data — all managed here.',

  'group_overview.label': 'Overview',
  'group_account.label': 'Account',
  'group_model.label': 'Models',
  'group_usage.label': 'Usage & credits',
  'group_data.label': 'Data & privacy',

  'section_overview.tab': 'Track record & shortcuts',
  'section_account.tab': 'Profile',
  'section_model.tab': 'API key (BYOK)',
  'section_usage.tab': 'Credits · usage',
  'section_data.tab': 'Export & delete',

  'section_overview.title': 'Track record & shortcuts',
  'section_overview.desc': 'Your judgment-ledger track record, recent reviews, and shortcuts — usage details live under "Usage & credits".',
  'section_account.title': 'Profile',
  'section_account.desc': 'Manage your account details and security settings.',
  'section_account_guest.desc':
    'You are browsing as a guest. Sign in to set a display name, change your password and keep a long-term account.',
  'section_model.title': 'API key (BYOK)',
  'section_model.desc':
    'Pick the model your reviews run on. Works with the official Anthropic API and with any OpenAI-compatible service — DeepSeek, Kimi, Qwen, Zhipu GLM, Ollama and others. Hit “Test” to check the connection before you save.',
  'section_usage.title': 'Credits · usage',
  'section_usage.desc':
    'Redeem a CDK code for review credits, and see your last 24 hours of usage plus total token spend.',
  'section_data.title': 'Data & privacy',
  'section_data.desc':
    'Everything you upload — materials, reports, follow-up threads — can be exported or permanently deleted whenever you want.',

  'guest_card.title': 'You are browsing as a guest',
  'guest_card.desc':
    'There is no email or password to change yet. Sign in or create an account and this section will let you edit your display name and password.',
  'guest_card.cta': 'Sign in or sign up',

  'account_card.title': 'Account',
  'account_card.desc': 'Signed in as {{email}}',

  'name.label': 'Display name',
  'name.placeholder': 'What should we call you?',
  'name.success': 'Display name updated',
  'name.error': 'Could not save that',
  'name.hint': 'Changing your email is not self-service yet — get in touch if you need to.',

  'password.label': 'Change password',
  'password_current.placeholder': 'Current password',
  'password_new.placeholder': 'New password (8 characters or more)',
  'password_confirm.placeholder': 'Repeat the new password',
  'password.cta': 'Change password',
  'password.success':
    'Password changed. Every other device has been signed out; this one stays signed in.',
  'password.error': 'Could not change your password',
  'password.hint':
    'Changing your password signs out every other device and keeps this one signed in. If you do not remember your current password, sign out and use “Forgot password” instead.',

  'revoke.label': 'Sign out everywhere',
  'revoke.desc':
    'Use this if you think someone else is signed in to your account: it immediately invalidates every login token ever issued for it. <strong>This device is signed out too</strong> and will have to sign in again. Your API keys and review history are untouched.',
  'revoke.cta': 'Sign out everywhere',
  'revoke.confirm': 'Sign out of every device?',
  'revoke.hint':
    'Click once more to confirm. Every device, this one included, will need to sign in again.',

  'byok.title': 'API key (BYOK)',
  'byok.desc': 'Bring your own key: review costs are billed to your own model account.',
  'byok.hint': '(optional — the platform also offers a shared key)',
  'byok.error': 'The platform service is unreachable, so key management is unavailable right now',

  'key_item.meta': '· last used {{time}}',
  'key_item.error': 'Could not delete that key',

  'provider_anthropic.label': 'Anthropic (native)',
  'provider_anthropic.desc': 'The official Claude API',
  'provider_openai.label': 'OpenAI-compatible providers',
  // 品牌专名用官方英文名，不直译（契约 6.11）：通义千问 → Qwen、智谱 GLM → Zhipu GLM。
  'provider_openai.desc': 'DeepSeek / Kimi / Qwen / Zhipu GLM / Ollama and more',

  'model_id.label': 'Model ID',
  'model_id.hint': '(leave blank to pick a model per persona tier)',
  'model_id.placeholder': 'claude-sonnet-5 (blank = pick automatically)',
  'model_id_compat.placeholder': 'deepseek-v4-pro',
  'model_id.error': 'OpenAI-compatible providers need a model name',

  'api_base.label': 'API Base URL',
  'api_base.hint': '(leave blank for the official endpoint)',
  'api_base.placeholder': 'https://api.anthropic.com (or a proxy endpoint)',
  'api_base_compat.placeholder': 'https://api.deepseek.com',

  'key_input.aria': 'API key',
  'key_input.placeholder': 'sk-ant-… (your Anthropic API key)',
  'key_input_compat.placeholder': 'Your provider’s API key (leave blank for a local Ollama)',

  'test.cta': 'Test',
  'test.success': 'Connected',
  'test.error': 'Could not connect',
  'test.meta': 'Reply: {{sample}}',

  'save_key.cta': 'Save key',
  'save_key.success': 'Key saved',
  'save_key.error': 'Could not save the key',

  'key_privacy.title': 'What happens to your key',
  'privacy_who.label': 'Who can see it:',
  'privacy_who.desc':
    'No one. It is encrypted at rest (Fernet / AES-128 + HMAC), and this page, your data export and the admin console all show only a masked form such as <code>sk-ant-…4f2a</code>.',
  'privacy_use.label': 'What it is used for:',
  'privacy_use.desc':
    'Only the reviews you start yourself. Not for training models, not for case studies, and never passed to a third party.',
  'privacy_device.label': 'On another device:',
  'privacy_device.desc':
    'The key belongs to your account, not to this browser, so it works as soon as you sign in elsewhere. You never re-enter it.',
  'privacy_optout.label': 'If you would rather not:',
  'privacy_optout.desc': 'Leave it empty and use the shared key the platform provides.',
  'privacy_selfhost.desc':
    'This project is open source and you can host it yourself — on your own deployment the key stays on your machine from end to end.',
  'privacy_optout.hint': 'You can also delete it from this page at any time.',
  'privacy_source.desc':
    'Every point above can be checked against the source code — this project is open. See the <privacy>Privacy Policy</privacy> for more.',

  'multimodal.desc':
    'Multimodal input: you can attach screenshots, mockups and pitch-deck pages to a review. Models that support vision (Claude, GPT-4o, Qwen-VL, GLM-4V and similar) look at the images directly; models without vision review the text only, and the run carries on either way.',

  'cdk.title': 'CDK redemption code',
  'cdk.desc':
    'Redeeming adds review credits. Each review spends one credit, and credits only apply when you run on the platform’s shared key.',
  'cdk_plan.desc':
    'Redeeming adds top-up credits. They cover you automatically once your plan’s daily limit runs out, and only apply when you run on the platform’s shared key.',
  'cdk.hint':
    'Redeeming without an account creates a guest identity. Those credits live in this browser, so use them before you clear your browsing data.',
  'cdk.placeholder': 'AL-XXXX-XXXX-XXXX',
  'cdk.cta': 'Redeem',
  // 两个数字只能有一个挂复数（ICU 同限制），挂本次到账的 count；balance 当普通插值。
  // 单位是 credit 不是 review：本文件自己的 usage_credits.label 写的是 "Credits left"，
  // 上面 cdk_desc 也写着 "Each review spends one credit"。同一屏里换成 "reviews added"
  // 会让用户以为兑换加的是另一种东西。
  'cdk.success_one': 'Redeemed — {{count}} credit added. Balance: {{balance}}.',
  'cdk.success_other': 'Redeemed — {{count}} credits added. Balance: {{balance}}.',
  'cdk_guest.hint': '(a guest identity was created for you and you are now signed in)',
  'cdk.error': 'Could not redeem that code',

  'usage.title': 'Usage, last 24 hours',
  'usage.hint': 'Quota window: {{window}}',
  'usage_reviews.label': 'Reviews run',
  'usage_reviews.hint': 'Covered by the platform: {{used}} / {{limit}}',
  'usage_credits.label': 'Credits left',
  'usage_bonus.label': 'Top-up credits',
  'usage_credits.unit': 'reviews',
  'usage_cost.label': 'Total cost',
  'usage_server_cost.label': 'Of that, on the shared key',
  'usage_tokens.label': 'Tokens used in total (never resets)',
  'usage_tokens.unit': 'tokens',
  'usage_tokens.hint':
    'The trial allowance only caps what the platform covers: {{used}} / {{limit}} used. Anything you run on your own API key (BYOK) is not counted.',

  'data.title': 'Your data',
  'data.desc':
    'Everything you upload — materials, reports, follow-up threads — can be exported or permanently deleted whenever you want.',
  'export.cta': 'Export all my data',
  'export.error': 'Export failed',
  'delete_account.cta': 'Delete my account and data',
  'delete_account.error': 'Deletion failed',
  'delete_done.desc': 'Deleted. Reviews removed: {{reviews}}. API keys removed: {{keys}}.',
  'delete_done.hint':
    'Billing records were unlinked from you; the anonymous totals are kept, as described in the Privacy Policy.',
  'delete_confirm.desc':
    'This <strong>immediately and physically erases</strong> every review, uploaded file, report, follow-up thread and stored API key you have, and it <strong>cannot be undone</strong>.<br/>Billing and redemption records are kept but unlinked from you — accounting needs them, and afterwards they can no longer point back to you.<br/>Run “Export all my data” first if you want a copy.',
  // {{phrase}} 恒为中文「删除我的账号」——它是后端的比较凭据，不是文案。
  // 所以这句必须写清"照着敲这句中文"，见文件头第 1 条。
  'delete_confirm.label': 'Type the Chinese phrase “{{phrase}}” exactly as shown to confirm',
  'delete_confirm.cta': 'Delete permanently',
  'delete_password.label': 'Account password',

  'footer.link': 'Privacy Policy',

  /* ---------------- Overview section ---------------- */
  'overview_plan.value': 'Current plan: {{plan}}',
  'overview_usage.cta': 'View usage details',

  'overview_scoreboard.title': 'You vs. the panel',
  'overview_scoreboard.cta': 'See full comparison →',
  'overview_side_panel.label': 'Panel',
  'overview_side_user.label': 'You',
  'overview_sample.value_one': '{{count}} verified sample',
  'overview_sample.value_other': '{{count}} verified samples',
  'overview_pending_one': '{{count}} judgment awaiting verification',
  'overview_pending_other': '{{count}} judgments awaiting verification',

  'overview_recent.title': 'Recent reviews',
  'overview_recent.cta': 'View all →',
  'overview_recent_empty.title': 'No reviews yet',
  'overview_recent_empty.desc': 'Once you run your first review, recent ones will show up here',

  'overview_links.title': 'Shortcuts',
} satisfies Messages
