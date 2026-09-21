/**
 * 【生成物 · 禁止手改】
 * 由 scripts/i18n-gen.mjs 生成。改资源文件后跑 `npm run i18n:gen`。
 * 手改这里 → `npm run i18n:check` 会红（它逐字节比对生成结果）。
 */

import type { Catalog } from '../../types'
import catalog_brand from './catalog.brand'
import catalog_eval_dimension from './catalog.eval_dimension'
import catalog_material from './catalog.material'
import catalog_mode from './catalog.mode'
import catalog_persona_pack from './catalog.persona_pack'
import catalog_skill from './catalog.skill'
import catalog_task_type from './catalog.task_type'
import common_action from './common.action'
import common_calibration_gauge from './common.calibration_gauge'
import common_meta from './common.meta'
import common_persona_card from './common.persona_card'
import common_persona_radar from './common.persona_radar'
import common_report_charts from './common.report_charts'
import common_ui from './common.ui'
import common_validate from './common.validate'
import enum_behavior_axis from './enum.behavior_axis'
import enum_calibration from './enum.calibration'
import enum_cross_exam_mode from './enum.cross_exam_mode'
import enum_direction from './enum.direction'
import enum_disabled_reason from './enum.disabled_reason'
import enum_ethics_severity from './enum.ethics_severity'
import enum_evidence_quality from './enum.evidence_quality'
import enum_gate_reason from './enum.gate_reason'
import enum_mode_badge from './enum.mode_badge'
import enum_persona_status from './enum.persona_status'
import enum_primary_stance from './enum.primary_stance'
import enum_rebuttal_status from './enum.rebuttal_status'
import enum_release_risk from './enum.release_risk'
import enum_review_status from './enum.review_status'
import enum_severity from './enum.severity'
import enum_stereotype_risk from './enum.stereotype_risk'
import enum_stop_reason from './enum.stop_reason'
import enum_verdict from './enum.verdict'
import error_api from './error.api'
import error_fetch from './error.fetch'
import error_store from './error.store'
import error_ws from './error.ws'
import nav_account from './nav.account'
import nav_footer from './nav.footer'
import nav_item from './nav.item'
import nav_menu from './nav.menu'
import nav_session from './nav.session'
import nav_verify_banner from './nav.verify_banner'
import page_ask from './page.ask'
import page_create from './page.create'
import page_evaluation from './page.evaluation'
import page_forgot from './page.forgot'
import page_history from './page.history'
import page_landing from './page.landing'
import page_ledger from './page.ledger'
import page_login from './page.login'
import page_personas from './page.personas'
import page_plans from './page.plans'
import page_privacy from './page.privacy'
import page_progress from './page.progress'
import page_qq_callback from './page.qq_callback'
import page_register from './page.register'
import page_report from './page.report'
import page_reset from './page.reset'
import page_settings from './page.settings'
import page_shared from './page.shared'
import page_skills from './page.skills'
import page_task_types from './page.task_types'
import page_terms from './page.terms'
import page_tutorial from './page.tutorial'
import page_verify from './page.verify'

const TABLES: Record<string, Record<string, string>> = {
  'catalog.brand': catalog_brand,
  'catalog.eval_dimension': catalog_eval_dimension,
  'catalog.material': catalog_material,
  'catalog.mode': catalog_mode,
  'catalog.persona_pack': catalog_persona_pack,
  'catalog.skill': catalog_skill,
  'catalog.task_type': catalog_task_type,
  'common.action': common_action,
  'common.calibration_gauge': common_calibration_gauge,
  'common.meta': common_meta,
  'common.persona_card': common_persona_card,
  'common.persona_radar': common_persona_radar,
  'common.report_charts': common_report_charts,
  'common.ui': common_ui,
  'common.validate': common_validate,
  'enum.behavior_axis': enum_behavior_axis,
  'enum.calibration': enum_calibration,
  'enum.cross_exam_mode': enum_cross_exam_mode,
  'enum.direction': enum_direction,
  'enum.disabled_reason': enum_disabled_reason,
  'enum.ethics_severity': enum_ethics_severity,
  'enum.evidence_quality': enum_evidence_quality,
  'enum.gate_reason': enum_gate_reason,
  'enum.mode_badge': enum_mode_badge,
  'enum.persona_status': enum_persona_status,
  'enum.primary_stance': enum_primary_stance,
  'enum.rebuttal_status': enum_rebuttal_status,
  'enum.release_risk': enum_release_risk,
  'enum.review_status': enum_review_status,
  'enum.severity': enum_severity,
  'enum.stereotype_risk': enum_stereotype_risk,
  'enum.stop_reason': enum_stop_reason,
  'enum.verdict': enum_verdict,
  'error.api': error_api,
  'error.fetch': error_fetch,
  'error.store': error_store,
  'error.ws': error_ws,
  'nav.account': nav_account,
  'nav.footer': nav_footer,
  'nav.item': nav_item,
  'nav.menu': nav_menu,
  'nav.session': nav_session,
  'nav.verify_banner': nav_verify_banner,
  'page.ask': page_ask,
  'page.create': page_create,
  'page.evaluation': page_evaluation,
  'page.forgot': page_forgot,
  'page.history': page_history,
  'page.landing': page_landing,
  'page.ledger': page_ledger,
  'page.login': page_login,
  'page.personas': page_personas,
  'page.plans': page_plans,
  'page.privacy': page_privacy,
  'page.progress': page_progress,
  'page.qq_callback': page_qq_callback,
  'page.register': page_register,
  'page.report': page_report,
  'page.reset': page_reset,
  'page.settings': page_settings,
  'page.shared': page_shared,
  'page.skills': page_skills,
  'page.task_types': page_task_types,
  'page.terms': page_terms,
  'page.tutorial': page_tutorial,
  'page.verify': page_verify,
}

// 完整 key = 文件名 + '.' + 文件里的 key。这条拼接规则是"文件名决定 owner"
// 那套并行分工的唯一实现处，改它等于改契约 4.1。
const merged: Catalog = {}
for (const ns of Object.keys(TABLES)) {
  const table = TABLES[ns]
  for (const k of Object.keys(table)) merged[`${ns}.${k}`] = table[k]
}

export default merged
