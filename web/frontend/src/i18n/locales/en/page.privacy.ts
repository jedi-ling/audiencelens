/**
 * Privacy Policy. owner: agent-5 (same owner as page.terms.ts).
 *
 * ⚠ 这份英文译文**尚未经法务复核**（契约 4.3 对本 agent 的备注）。
 *
 * 翻译纪律：中文原件的措辞是刻意保守的，好几条是被代码变更倒逼着改窄的
 * （对话消息落库、图片落盘、管理端可见范围）。英文不许翻宽——
 * 尤其 usage_admin_* 那三条，它说的是"运营方可以在你没求助时打开你的评审"，
 * 不许软化成 "we may occasionally need to access"。
 *
 * verify_checkable_hosted / third_party_llm_ollama / third_party_llm_scope
 * 这三条是全页最容易被翻错的：中文明确否认了"数据不出你的设备"，
 * 英文如果写成常见的隐私宣传口吻，就正好把这一页最诚实的部分翻反。
 *
 * 撇号一律用 U+2019（’），不用 ASCII '，省得在单引号字符串里转义。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Privacy Policy',

  'header.link': 'Back to home',
  'header.title': 'Privacy Policy',
  'header.subtitle': 'Your privacy matters to us. This policy explains how AudienceLens collects, uses and protects your data.',
  'header.meta': 'Last updated: May 2026',

  'collect.badge': 'Collected',
  'no_collect.badge': 'Not collected',
  'key.badge': 'Keys',
  'use.badge': 'Use',
  'security.badge': 'Security',
  'third_party.badge': 'Third party',
  'retention.badge': 'Retention',
  'verify.badge': 'Verifiable',

  'collection.title': 'What we collect',
  'collection_collected.label': 'Data we collect',
  'collection_collected_materials.desc': 'The review material you upload (text, screenshots and so on). It is kept with the review record until you delete it',
  'collection_collected_config.desc': 'The task type, persona configuration and review mode you chose',
  'collection_collected_report.desc': 'The review report, each persona’s opinion, and your follow-up questions and their replies',
  'collection_collected_chat.desc': 'Messages exchanged on the chat page, including the clarifying turns before a review starts. They are held on the server, so they survive a refresh or a change of device',
  'collection_collected_images.desc': 'Images you upload in chat, stored as files on the server’s disk (the database holds a reference only, not the image itself)',
  'collection_collected_account.desc': 'Your registration email and password hash (registered users only; passwords are salted and hashed with PBKDF2-HMAC-SHA256, which we cannot reverse)',
  'collection_collected_usage.desc': 'Usage records: tokens, cost and time for each review',
  'collection_not.label': 'Data we do not collect',
  'collection_not_history.desc': 'No browsing history, no cross-site tracking',
  'collection_not_fingerprint.desc': 'No device fingerprinting, no third-party advertising or analytics SDKs',
  'collection_not_identity.desc': 'Apart from your registration email we ask for no identifying information — no phone number, no real-name verification',
  'collection_apikey.label': 'How your API key is handled',
  'collection_apikey_encrypted.desc': 'Your LLM API key is encrypted before it is stored in the database (Fernet / AES-128-CBC with HMAC authentication)',
  'collection_apikey_separate.desc': 'The encryption key is configured separately from the login token key, so rotating the login key does not invalidate your stored key',
  'collection_apikey_masked.desc': 'The page only ever shows a mask (for example sk-ant-…4f2a); data exports carry the mask too, never the plaintext',
  'collection_apikey_delete.desc': 'You can delete it from the settings page at any time',

  'usage.title': 'How your data is used',
  'usage_purpose.label': 'What the data is used for',
  'usage_purpose_single.desc': 'Your material is used for that one review: sent to the model provider you picked, to produce the report you asked for',
  'usage_purpose_retained.desc': 'Material and reports are kept with the review record so you can look back and keep asking follow-ups — until you delete them yourself',
  'usage_purpose_isolated.desc': 'Review results are reachable only by you (scoped by account; when you are not signed in, by anonymous identity)',
  'usage_never.label': 'What we do not do',
  'usage_never_training.desc': 'We do not train any model on your content — we do not train models at all, and we do not sell or share your data with anyone',
  'usage_never_showcase.desc': 'We do not use your project as a case study, marketing material or public sample',
  'usage_never_copy.desc': 'Troubleshooting does not copy your material anywhere else, and does not hand it to any third party',
  // ⚠ 这三条是本页最需要保住原意的地方：中文说的是"运营方可以在你没求助的
  // 情况下打开评审内容"，这是一条**承认**，不是一条承诺。翻软了就是不实。
  'usage_admin.label': 'What the admin side can see (stated plainly)',
  'usage_admin_access.desc': 'To handle complaints, investigate abuse or settle billing disputes, the operator can open review content without you having asked for help first',
  'usage_admin_audit.desc': 'Such access is written to the admin audit log (when it happened, and which review was opened), but you are not notified about it today',
  'usage_admin_unchanged.desc': 'This does not change the point above: content is never used to train models, shown as a case study, or handed to a third party',

  'security.title': 'Security measures',
  'security_tech.label': 'Technical safeguards',
  'security_tech_key.desc': 'API keys are stored encrypted with Fernet (AES-128-CBC plus HMAC-SHA256 authentication)',
  'security_tech_password.desc': 'Login passwords are salted and hashed with PBKDF2-HMAC-SHA256 (200,000 rounds), and cannot be reversed',
  'security_tech_token.desc': 'Email verification and password reset tokens are stored as hash digests only — single-use, and they expire',
  'security_tech_cors.desc': 'A strict CORS allowlist, security response headers, and WebSocket origin checks',
  'security_tech_upload.desc': 'Upload type and size limits, chunked streaming reads, aborted the moment a limit is passed',

  'verify.title': 'You do not have to take our word for it',
  'verify_checkable.label': 'Checkable, not just believable',
  'verify_checkable_oss.desc': 'The code is open source: every promise on this page can be checked against the source',
  'verify_checkable_byok.desc': 'Bring your own key (BYOK): model calls run on your own allowance, and the bill and usage sit in your provider’s console',
  'verify_checkable_hosted.desc': 'When you use this site (the hosted form): your material is uploaded to our server and stored there first, and the server then calls the model on your behalf — there is no way to do that without the server, so we do not claim otherwise',
  'verify_checkable_selfhost.desc': 'The only way to keep your data on your own machine is to self-host, or run the CLI / Python / MCP locally. Then the material stays on your machine from start to finish and we never get near it',
  'verify_checkable_export.desc': 'Take it away or wipe it whenever you like: two buttons on the settings page, no email to send, no manual approval to wait for',

  'third_party.title': 'Third-party services',
  'third_party_llm.label': 'LLM providers',
  'third_party_llm_providers.desc': 'Reviews run on the Anthropic / OpenAI / DeepSeek / Ollama APIs',
  'third_party_llm_only.desc': 'Apart from the LLM provider you choose yourself, we pass your material to no third party',
  'third_party_llm_ollama.desc': 'The Ollama option points at localhost on whichever machine is running this system: when you self-host, that is your machine; when you use this site, it is our server — not your computer',
  'third_party_llm_scope.desc': 'So “your data never leaves your device” holds only in the self-hosted / CLI / Python / MCP forms. It does not hold in the hosted one',
  'third_party_providers.label': 'Supported LLM providers',

  'retention.title': 'Data retention',
  'retention_policy.label': 'Retention policy',
  'retention_policy_forever.desc': 'Review records stay in the server database until you delete them — we set no automatic expiry',
  'retention_policy_export.desc': 'The settings page has “Export all my data”: one JSON file with all of your content in it',
  'retention_policy_delete.desc': 'The settings page has “Delete my account and data”: reviews, material, reports, follow-ups, conversation records, uploaded images (the bytes on disk go too), ethics-check records (including the excerpts they quote), your API key and the account itself are physically deleted straight away',
  'retention_policy_exception.desc': 'One exception, stated plainly: usage and redemption ledger rows are kept, but the user_id on them is rewritten to a tombstone identifier that points back to nobody — the rows are needed for financial reconciliation, and after that they cannot be linked to you',

  'contact.title': 'Contact',
  'contact.desc': 'If you have questions or suggestions about this policy, reach us here:',
  'footer.desc': 'AudienceLens is committed to protecting your data privacy and security',
} satisfies Messages
