/**
 * 【生成物 · 禁止手改】
 * 由 scripts/i18n-gen.mjs 生成。改资源文件后跑 `npm run i18n:gen`。
 * 手改这里 → `npm run i18n:check` 会红（它逐字节比对生成结果）。
 */

/** 全部可用的**逻辑 key**（不含复数后缀——后缀由运行时选，调用方永远不写）。 */
export type MessageKey =
  | 'catalog.brand.deepseek'
  | 'catalog.brand.glm'
  | 'catalog.brand.kimi'
  | 'catalog.brand.ollama'
  | 'catalog.brand.openai'
  | 'catalog.brand.qwen'
  | 'catalog.eval_dimension.actionability.desc'
  | 'catalog.eval_dimension.actionability.label'
  | 'catalog.eval_dimension.calibration_honesty.desc'
  | 'catalog.eval_dimension.calibration_honesty.label'
  | 'catalog.eval_dimension.ethical_persona_use.desc'
  | 'catalog.eval_dimension.ethical_persona_use.label'
  | 'catalog.eval_dimension.input_grounding.desc'
  | 'catalog.eval_dimension.input_grounding.label'
  | 'catalog.eval_dimension.persona_differentiation.desc'
  | 'catalog.eval_dimension.persona_differentiation.label'
  | 'catalog.eval_dimension.report_structure.desc'
  | 'catalog.eval_dimension.report_structure.label'
  | 'catalog.eval_dimension.risk_detection.desc'
  | 'catalog.eval_dimension.risk_detection.label'
  | 'catalog.eval_dimension.segment_conflict.desc'
  | 'catalog.eval_dimension.segment_conflict.label'
  | 'catalog.material.concept_review__一句话pitch.label'
  | 'catalog.material.concept_review__一句话pitch.placeholder'
  | 'catalog.material.concept_review__定价与平台.label'
  | 'catalog.material.concept_review__定价与平台.placeholder'
  | 'catalog.material.concept_review__截图.label'
  | 'catalog.material.concept_review__截图.placeholder'
  | 'catalog.material.concept_review__核心循环说明.label'
  | 'catalog.material.concept_review__核心循环说明.placeholder'
  | 'catalog.material.concept_review__目标受众.label'
  | 'catalog.material.concept_review__目标受众.placeholder'
  | 'catalog.material.concept_review__竞品对比.label'
  | 'catalog.material.concept_review__竞品对比.placeholder'
  | 'catalog.material.concept_review__系统说明.label'
  | 'catalog.material.concept_review__系统说明.placeholder'
  | 'catalog.material.demo_first_play__实机视频.label'
  | 'catalog.material.demo_first_play__实机视频.placeholder'
  | 'catalog.material.demo_first_play__截图.label'
  | 'catalog.material.demo_first_play__截图.placeholder'
  | 'catalog.material.demo_first_play__核心循环说明.label'
  | 'catalog.material.demo_first_play__核心循环说明.placeholder'
  | 'catalog.material.demo_first_play__游戏名称.label'
  | 'catalog.material.demo_first_play__游戏名称.placeholder'
  | 'catalog.material.demo_first_play__竞品对比.label'
  | 'catalog.material.demo_first_play__竞品对比.placeholder'
  | 'catalog.material.demo_first_play__评价摘要.label'
  | 'catalog.material.demo_first_play__评价摘要.placeholder'
  | 'catalog.material.devlog_review__截图.label'
  | 'catalog.material.devlog_review__截图.placeholder'
  | 'catalog.material.devlog_review__核心循环说明.label'
  | 'catalog.material.devlog_review__核心循环说明.placeholder'
  | 'catalog.material.devlog_review__游戏名称.label'
  | 'catalog.material.devlog_review__游戏名称.placeholder'
  | 'catalog.material.devlog_review__评价摘要.label'
  | 'catalog.material.devlog_review__评价摘要.placeholder'
  | 'catalog.material.discord_community_review__核心循环说明.label'
  | 'catalog.material.discord_community_review__核心循环说明.placeholder'
  | 'catalog.material.discord_community_review__社区名称.label'
  | 'catalog.material.discord_community_review__社区名称.placeholder'
  | 'catalog.material.discord_community_review__竞品对比.label'
  | 'catalog.material.discord_community_review__竞品对比.placeholder'
  | 'catalog.material.discord_community_review__系统说明.label'
  | 'catalog.material.discord_community_review__系统说明.placeholder'
  | 'catalog.material.discord_community_review__评价摘要.label'
  | 'catalog.material.discord_community_review__评价摘要.placeholder'
  | 'catalog.material.kickstarter_review__一句话pitch.label'
  | 'catalog.material.kickstarter_review__一句话pitch.placeholder'
  | 'catalog.material.kickstarter_review__定价与平台.label'
  | 'catalog.material.kickstarter_review__定价与平台.placeholder'
  | 'catalog.material.kickstarter_review__截图.label'
  | 'catalog.material.kickstarter_review__截图.placeholder'
  | 'catalog.material.kickstarter_review__核心循环说明.label'
  | 'catalog.material.kickstarter_review__核心循环说明.placeholder'
  | 'catalog.material.kickstarter_review__目标受众.label'
  | 'catalog.material.kickstarter_review__目标受众.placeholder'
  | 'catalog.material.kickstarter_review__项目名称.label'
  | 'catalog.material.kickstarter_review__项目名称.placeholder'
  | 'catalog.material.localization_review__核心循环说明.label'
  | 'catalog.material.localization_review__核心循环说明.placeholder'
  | 'catalog.material.localization_review__游戏名称.label'
  | 'catalog.material.localization_review__游戏名称.placeholder'
  | 'catalog.material.localization_review__竞品对比.label'
  | 'catalog.material.localization_review__竞品对比.placeholder'
  | 'catalog.material.localization_review__系统说明.label'
  | 'catalog.material.localization_review__系统说明.placeholder'
  | 'catalog.material.looking_for_party_post__核心循环说明.label'
  | 'catalog.material.looking_for_party_post__核心循环说明.placeholder'
  | 'catalog.material.looking_for_party_post__游戏名称.label'
  | 'catalog.material.looking_for_party_post__游戏名称.placeholder'
  | 'catalog.material.looking_for_party_post__目标受众.label'
  | 'catalog.material.looking_for_party_post__目标受众.placeholder'
  | 'catalog.material.monetization_review__定价与平台.label'
  | 'catalog.material.monetization_review__定价与平台.placeholder'
  | 'catalog.material.monetization_review__核心循环说明.label'
  | 'catalog.material.monetization_review__核心循环说明.placeholder'
  | 'catalog.material.monetization_review__游戏名称.label'
  | 'catalog.material.monetization_review__游戏名称.placeholder'
  | 'catalog.material.monetization_review__竞品对比.label'
  | 'catalog.material.monetization_review__竞品对比.placeholder'
  | 'catalog.material.monetization_review__评价摘要.label'
  | 'catalog.material.monetization_review__评价摘要.placeholder'
  | 'catalog.material.onboarding_review__产品名称.label'
  | 'catalog.material.onboarding_review__产品名称.placeholder'
  | 'catalog.material.onboarding_review__截图.label'
  | 'catalog.material.onboarding_review__截图.placeholder'
  | 'catalog.material.onboarding_review__核心循环说明.label'
  | 'catalog.material.onboarding_review__核心循环说明.placeholder'
  | 'catalog.material.onboarding_review__目标受众.label'
  | 'catalog.material.onboarding_review__目标受众.placeholder'
  | 'catalog.material.onboarding_review__系统说明.label'
  | 'catalog.material.onboarding_review__系统说明.placeholder'
  | 'catalog.material.onboarding_review__评价摘要.label'
  | 'catalog.material.onboarding_review__评价摘要.placeholder'
  | 'catalog.material.pitch_review__一句话pitch.label'
  | 'catalog.material.pitch_review__一句话pitch.placeholder'
  | 'catalog.material.pitch_review__定价与平台.label'
  | 'catalog.material.pitch_review__定价与平台.placeholder'
  | 'catalog.material.pitch_review__核心循环说明.label'
  | 'catalog.material.pitch_review__核心循环说明.placeholder'
  | 'catalog.material.pitch_review__目标受众.label'
  | 'catalog.material.pitch_review__目标受众.placeholder'
  | 'catalog.material.pitch_review__竞品对比.label'
  | 'catalog.material.pitch_review__竞品对比.placeholder'
  | 'catalog.material.pitch_review__系统说明.label'
  | 'catalog.material.pitch_review__系统说明.placeholder'
  | 'catalog.material.pitch_review__项目名称.label'
  | 'catalog.material.pitch_review__项目名称.placeholder'
  | 'catalog.material.pricing_page_review__产品名称.label'
  | 'catalog.material.pricing_page_review__产品名称.placeholder'
  | 'catalog.material.pricing_page_review__定价与平台.label'
  | 'catalog.material.pricing_page_review__定价与平台.placeholder'
  | 'catalog.material.pricing_page_review__截图.label'
  | 'catalog.material.pricing_page_review__截图.placeholder'
  | 'catalog.material.pricing_page_review__核心循环说明.label'
  | 'catalog.material.pricing_page_review__核心循环说明.placeholder'
  | 'catalog.material.pricing_page_review__目标受众.label'
  | 'catalog.material.pricing_page_review__目标受众.placeholder'
  | 'catalog.material.pricing_page_review__竞品对比.label'
  | 'catalog.material.pricing_page_review__竞品对比.placeholder'
  | 'catalog.material.product_feedback_review__产品名称.label'
  | 'catalog.material.product_feedback_review__产品名称.placeholder'
  | 'catalog.material.product_feedback_review__截图.label'
  | 'catalog.material.product_feedback_review__截图.placeholder'
  | 'catalog.material.product_feedback_review__核心循环说明.label'
  | 'catalog.material.product_feedback_review__核心循环说明.placeholder'
  | 'catalog.material.product_feedback_review__目标受众.label'
  | 'catalog.material.product_feedback_review__目标受众.placeholder'
  | 'catalog.material.product_feedback_review__竞品对比.label'
  | 'catalog.material.product_feedback_review__竞品对比.placeholder'
  | 'catalog.material.product_feedback_review__评价摘要.label'
  | 'catalog.material.product_feedback_review__评价摘要.placeholder'
  | 'catalog.material.steam_page_review__demo.label'
  | 'catalog.material.steam_page_review__demo.placeholder'
  | 'catalog.material.steam_page_review__tags.label'
  | 'catalog.material.steam_page_review__tags.placeholder'
  | 'catalog.material.steam_page_review__价格.label'
  | 'catalog.material.steam_page_review__价格.placeholder'
  | 'catalog.material.steam_page_review__截图.label'
  | 'catalog.material.steam_page_review__截图.placeholder'
  | 'catalog.material.steam_page_review__核心循环说明.label'
  | 'catalog.material.steam_page_review__核心循环说明.placeholder'
  | 'catalog.material.steam_page_review__游戏名称.label'
  | 'catalog.material.steam_page_review__游戏名称.placeholder'
  | 'catalog.material.steam_page_review__评价摘要.label'
  | 'catalog.material.steam_page_review__评价摘要.placeholder'
  | 'catalog.material.update_announcement_review__截图.label'
  | 'catalog.material.update_announcement_review__截图.placeholder'
  | 'catalog.material.update_announcement_review__核心循环说明.label'
  | 'catalog.material.update_announcement_review__核心循环说明.placeholder'
  | 'catalog.material.update_announcement_review__游戏名称.label'
  | 'catalog.material.update_announcement_review__游戏名称.placeholder'
  | 'catalog.material.update_announcement_review__评价摘要.label'
  | 'catalog.material.update_announcement_review__评价摘要.placeholder'
  | 'catalog.mode.full.desc'
  | 'catalog.mode.quick.desc'
  | 'catalog.mode.standard.desc'
  | 'catalog.persona_pack.accessibility'
  | 'catalog.persona_pack.category_general'
  | 'catalog.persona_pack.category_platform'
  | 'catalog.persona_pack.category_player_type'
  | 'catalog.persona_pack.category_special'
  | 'catalog.persona_pack.competitive_esport'
  | 'catalog.persona_pack.educational_serious'
  | 'catalog.persona_pack.family_casual'
  | 'catalog.persona_pack.game_core'
  | 'catalog.persona_pack.general_consumer'
  | 'catalog.persona_pack.indie_creative'
  | 'catalog.persona_pack.launch_compliance'
  | 'catalog.persona_pack.mobile_f2p'
  | 'catalog.persona_pack.startup_panel'
  | 'catalog.persona_pack.vr_immersive'
  | 'catalog.skill.audience_panel.desc'
  | 'catalog.skill.audience_panel.label'
  | 'catalog.skill.persona_generate.desc'
  | 'catalog.skill.persona_generate.label'
  | 'catalog.skill.red_team_audience.desc'
  | 'catalog.skill.red_team_audience.label'
  | 'catalog.skill.synthetic_playtest.desc'
  | 'catalog.skill.synthetic_playtest.label'
  | 'catalog.task_type.concept_review.desc'
  | 'catalog.task_type.concept_review.label'
  | 'catalog.task_type.demo_first_play.desc'
  | 'catalog.task_type.demo_first_play.label'
  | 'catalog.task_type.devlog_review.desc'
  | 'catalog.task_type.devlog_review.label'
  | 'catalog.task_type.discord_community_review.desc'
  | 'catalog.task_type.discord_community_review.label'
  | 'catalog.task_type.kickstarter_review.desc'
  | 'catalog.task_type.kickstarter_review.label'
  | 'catalog.task_type.localization_review.desc'
  | 'catalog.task_type.localization_review.label'
  | 'catalog.task_type.looking_for_party_post.desc'
  | 'catalog.task_type.looking_for_party_post.label'
  | 'catalog.task_type.monetization_review.desc'
  | 'catalog.task_type.monetization_review.label'
  | 'catalog.task_type.onboarding_review.desc'
  | 'catalog.task_type.onboarding_review.label'
  | 'catalog.task_type.pitch_review.desc'
  | 'catalog.task_type.pitch_review.label'
  | 'catalog.task_type.pricing_page_review.desc'
  | 'catalog.task_type.pricing_page_review.label'
  | 'catalog.task_type.product_feedback_review.desc'
  | 'catalog.task_type.product_feedback_review.label'
  | 'catalog.task_type.steam_page_review.desc'
  | 'catalog.task_type.steam_page_review.label'
  | 'catalog.task_type.update_announcement_review.desc'
  | 'catalog.task_type.update_announcement_review.label'
  | 'common.action.back'
  | 'common.action.cancel'
  | 'common.action.clear'
  | 'common.action.close'
  | 'common.action.collapse'
  | 'common.action.confirm'
  | 'common.action.copy'
  | 'common.action.delete'
  | 'common.action.delete_account_phrase'
  | 'common.action.download'
  | 'common.action.edit'
  | 'common.action.expand'
  | 'common.action.load_more'
  | 'common.action.next'
  | 'common.action.prev'
  | 'common.action.refresh'
  | 'common.action.remove'
  | 'common.action.retry'
  | 'common.action.save'
  | 'common.action.share'
  | 'common.action.submit'
  | 'common.action.upload'
  | 'common.action.view_details'
  | 'common.calibration_gauge.missing.hint'
  | 'common.calibration_gauge.no_pass_line.hint'
  | 'common.calibration_gauge.pass_line.value'
  | 'common.calibration_gauge.readout.empty'
  | 'common.meta.description'
  | 'common.meta.title_template'
  | 'common.persona_card.confidence.value'
  | 'common.persona_radar.series_a.label'
  | 'common.persona_radar.series_b.label'
  | 'common.ui.copied'
  | 'common.ui.copy_failed'
  | 'common.ui.deleting'
  | 'common.ui.empty'
  | 'common.ui.error'
  | 'common.ui.language'
  | 'common.ui.language_aria'
  | 'common.ui.language_hint'
  | 'common.ui.loading'
  | 'common.ui.not_recorded'
  | 'common.ui.optional_mark'
  | 'common.ui.processing'
  | 'common.ui.required_mark'
  | 'common.ui.saving'
  | 'common.ui.sending'
  | 'common.ui.submitting'
  | 'common.ui.success'
  | 'common.ui.unknown_error'
  | 'common.validate.email_format'
  | 'common.validate.file_too_large'
  | 'common.validate.number_range'
  | 'common.validate.password_min'
  | 'common.validate.password_mismatch'
  | 'common.validate.required'
  | 'common.validate.too_long'
  | 'enum.behavior_axis.agency_preference'
  | 'enum.behavior_axis.completion_drive'
  | 'enum.behavior_axis.criticism_style'
  | 'enum.behavior_axis.emotional_engagement'
  | 'enum.behavior_axis.genre_literacy'
  | 'enum.behavior_axis.novelty_seeking'
  | 'enum.behavior_axis.patience'
  | 'enum.behavior_axis.platform_loyalty'
  | 'enum.behavior_axis.price_sensitivity'
  | 'enum.behavior_axis.risk_tolerance'
  | 'enum.behavior_axis.social_influence'
  | 'enum.behavior_axis.tolerance_for_ambiguity'
  | 'enum.calibration.coverage'
  | 'enum.calibration.hallucination'
  | 'enum.calibration.role_consistency'
  | 'enum.cross_exam_mode.derived_summary.desc'
  | 'enum.cross_exam_mode.derived_summary.label'
  | 'enum.cross_exam_mode.moderated_rebuttal.desc'
  | 'enum.cross_exam_mode.moderated_rebuttal.label'
  | 'enum.cross_exam_mode.multi_agent_rebuttal.desc'
  | 'enum.cross_exam_mode.multi_agent_rebuttal.label'
  | 'enum.direction.decrease'
  | 'enum.direction.increase'
  | 'enum.disabled_reason.explicit_persona_selection'
  | 'enum.ethics_severity.high'
  | 'enum.ethics_severity.low'
  | 'enum.ethics_severity.medium'
  | 'enum.evidence_quality.insufficient'
  | 'enum.evidence_quality.medium'
  | 'enum.evidence_quality.strong'
  | 'enum.evidence_quality.weak'
  | 'enum.gate_reason.hallucination'
  | 'enum.gate_reason.role_drift'
  | 'enum.gate_reason.schema_failure'
  | 'enum.mode_badge.full'
  | 'enum.mode_badge.quick'
  | 'enum.mode_badge.standard'
  | 'enum.persona_status.completed'
  | 'enum.persona_status.failed'
  | 'enum.persona_status.pending'
  | 'enum.persona_status.running'
  | 'enum.primary_stance.advocate'
  | 'enum.primary_stance.blocker'
  | 'enum.primary_stance.neutral'
  | 'enum.primary_stance.skeptic'
  | 'enum.rebuttal_status.failed'
  | 'enum.rebuttal_status.ok'
  | 'enum.rebuttal_status.partial'
  | 'enum.rebuttal_status.skipped'
  | 'enum.release_risk.critical'
  | 'enum.release_risk.high'
  | 'enum.release_risk.low'
  | 'enum.release_risk.medium'
  | 'enum.review_status.cancelled'
  | 'enum.review_status.completed'
  | 'enum.review_status.failed'
  | 'enum.review_status.pending'
  | 'enum.review_status.running'
  | 'enum.severity.critical'
  | 'enum.severity.high'
  | 'enum.severity.low'
  | 'enum.severity.medium'
  | 'enum.stereotype_risk.high'
  | 'enum.stereotype_risk.low'
  | 'enum.stereotype_risk.medium'
  | 'enum.stereotype_risk.unknown'
  | 'enum.stop_reason.cost_budget_reached'
  | 'enum.stop_reason.marginal_value_below_threshold'
  | 'enum.verdict.fail'
  | 'enum.verdict.pass'
  | 'error.api.admin_disabled'
  | 'error.api.bad_request'
  | 'error.api.forbidden'
  | 'error.api.internal_error'
  | 'error.api.llm_key_missing'
  | 'error.api.not_found'
  | 'error.api.quota_exceeded'
  | 'error.api.rate_limited'
  | 'error.api.unauthorized'
  | 'error.api.upstream_error'
  | 'error.fetch.delete_review'
  | 'error.fetch.ethics'
  | 'error.fetch.evaluation'
  | 'error.fetch.examples'
  | 'error.fetch.extract_materials'
  | 'error.fetch.http_status'
  | 'error.fetch.persona_packs'
  | 'error.fetch.personas'
  | 'error.fetch.report'
  | 'error.fetch.review'
  | 'error.fetch.review_list'
  | 'error.fetch.review_modes'
  | 'error.fetch.review_result'
  | 'error.fetch.run_evaluation'
  | 'error.fetch.separator'
  | 'error.fetch.skills'
  | 'error.fetch.task_types'
  | 'error.store.bootstrap'
  | 'error.store.examples'
  | 'error.store.personas'
  | 'error.store.review_list'
  | 'error.ws.closed'
  | 'error.ws.give_up'
  | 'error.ws.reconnecting'
  | 'error.ws.review_failed'
  | 'error.ws.unavailable'
  | 'nav.account.guest'
  | 'nav.account.login'
  | 'nav.account.logout'
  | 'nav.account.menu_aria'
  | 'nav.account.settings'
  | 'nav.footer.icp_aria'
  | 'nav.footer.privacy'
  | 'nav.footer.tagline'
  | 'nav.footer.terms'
  | 'nav.item.ask'
  | 'nav.item.create_review'
  | 'nav.item.history'
  | 'nav.item.home'
  | 'nav.item.ledger'
  | 'nav.item.personas'
  | 'nav.item.plans'
  | 'nav.item.settings'
  | 'nav.item.skills'
  | 'nav.item.task_types'
  | 'nav.item.tutorial'
  | 'nav.menu.drawer_aria'
  | 'nav.menu.toggle_aria'
  | 'nav.session.cta'
  | 'nav.session.dismiss_aria'
  | 'nav.session.expired'
  | 'nav.verify_banner.cta'
  | 'nav.verify_banner.error'
  | 'nav.verify_banner.hint'
  | 'nav.verify_banner.hint_unknown'
  | 'nav.verify_banner.sending'
  | 'nav.verify_banner.success'
  | 'page.ask.attach.hint'
  | 'page.ask.attachment_image.aria'
  | 'page.ask.attachment_limit.error'
  | 'page.ask.attachment_note_follow_up.hint'
  | 'page.ask.attachment_note_review.hint'
  | 'page.ask.attachment_preview.tooltip'
  | 'page.ask.attachment_remove.aria'
  | 'page.ask.clarify.hint'
  | 'page.ask.conclusion.title'
  | 'page.ask.confidence.label'
  | 'page.ask.confidence.value'
  | 'page.ask.confidence_high.label'
  | 'page.ask.confidence_low.label'
  | 'page.ask.confidence_medium.label'
  | 'page.ask.confirm.label'
  | 'page.ask.conversation_move.error'
  | 'page.ask.conversation_untitled.label'
  | 'page.ask.cost.value'
  | 'page.ask.count.disagreements'
  | 'page.ask.count.fixes'
  | 'page.ask.count.information_gaps'
  | 'page.ask.count.issues'
  | 'page.ask.count.persona_notes'
  | 'page.ask.count.personas'
  | 'page.ask.count.priority_fixes'
  | 'page.ask.create.error'
  | 'page.ask.disagreement.hint'
  | 'page.ask.disagreement_evidence.value'
  | 'page.ask.disagreement_stance.value'
  | 'page.ask.drop.hint'
  | 'page.ask.evidence.badge'
  | 'page.ask.example_onboarding.value'
  | 'page.ask.example_pitch.value'
  | 'page.ask.example_pricing.value'
  | 'page.ask.examples.cta'
  | 'page.ask.examples.hint'
  | 'page.ask.examples.title'
  | 'page.ask.fix.hint'
  | 'page.ask.follow_up.badge'
  | 'page.ask.follow_up.cta'
  | 'page.ask.follow_up.error'
  | 'page.ask.follow_up.label'
  | 'page.ask.follow_up.tooltip'
  | 'page.ask.follow_up_exit.aria'
  | 'page.ask.follow_up_report.cta'
  | 'page.ask.gated.cta'
  | 'page.ask.gated.hint'
  | 'page.ask.greeting.value'
  | 'page.ask.header.desc'
  | 'page.ask.header.title'
  | 'page.ask.history.error'
  | 'page.ask.history_delete.error'
  | 'page.ask.history_delete.hint'
  | 'page.ask.input.aria'
  | 'page.ask.input.placeholder'
  | 'page.ask.input_follow_up.placeholder'
  | 'page.ask.legacy.title'
  | 'page.ask.login_required.cta'
  | 'page.ask.login_required.desc'
  | 'page.ask.login_required.title'
  | 'page.ask.meta.title'
  | 'page.ask.mode.badge'
  | 'page.ask.need_key.cta'
  | 'page.ask.new_conversation.cta'
  | 'page.ask.new_project.confirm'
  | 'page.ask.new_project.cta'
  | 'page.ask.new_project.placeholder'
  | 'page.ask.no_key.cta'
  | 'page.ask.no_key.desc'
  | 'page.ask.no_key.title'
  | 'page.ask.pack.badge'
  | 'page.ask.parse.error'
  | 'page.ask.persisted_confirm.empty'
  | 'page.ask.persisted_confirm.value'
  | 'page.ask.persisted_review.value'
  | 'page.ask.persona_chat.cta'
  | 'page.ask.persona_remove.aria'
  | 'page.ask.persona_remove.tooltip'
  | 'page.ask.persona_restore.aria'
  | 'page.ask.persona_restore.tooltip'
  | 'page.ask.personas.label'
  | 'page.ask.pinned_project.aria'
  | 'page.ask.pinned_project.badge'
  | 'page.ask.pinned_project.tooltip'
  | 'page.ask.pinned_skill.aria'
  | 'page.ask.pinned_skill.badge'
  | 'page.ask.pinned_type.aria'
  | 'page.ask.pinned_type.badge'
  | 'page.ask.preview_close.aria'
  | 'page.ask.progress.hint'
  | 'page.ask.progress.pending'
  | 'page.ask.project.badge'
  | 'page.ask.project.empty'
  | 'page.ask.project_create.error'
  | 'page.ask.project_delete.aria'
  | 'page.ask.project_delete.error'
  | 'page.ask.project_delete.tooltip'
  | 'page.ask.project_delete_confirm.aria'
  | 'page.ask.project_delete_confirm.confirm'
  | 'page.ask.project_delete_confirm.cta'
  | 'page.ask.project_rename.aria'
  | 'page.ask.project_rename.error'
  | 'page.ask.project_rename.tooltip'
  | 'page.ask.project_select.aria'
  | 'page.ask.project_select.empty'
  | 'page.ask.project_select.placeholder'
  | 'page.ask.projects.loading'
  | 'page.ask.realtime_reconnecting.hint'
  | 'page.ask.realtime_unavailable.hint'
  | 'page.ask.report_card.cta'
  | 'page.ask.report_card.empty'
  | 'page.ask.report_card.loading'
  | 'page.ask.report_card.title'
  | 'page.ask.report_modal.subtitle'
  | 'page.ask.restored_review.label'
  | 'page.ask.review_delete.aria'
  | 'page.ask.review_delete.tooltip'
  | 'page.ask.review_delete_confirm.aria'
  | 'page.ask.review_delete_confirm.confirm'
  | 'page.ask.review_failed.error'
  | 'page.ask.review_failed.title'
  | 'page.ask.rule_parse.hint'
  | 'page.ask.send.aria'
  | 'page.ask.sidebar_collapse.aria'
  | 'page.ask.sidebar_collapse.tooltip'
  | 'page.ask.sidebar_empty.desc'
  | 'page.ask.sidebar_empty.title'
  | 'page.ask.sidebar_expand.aria'
  | 'page.ask.sidebar_expand.tooltip'
  | 'page.ask.skill.badge'
  | 'page.ask.skill_degraded.value'
  | 'page.ask.skill_picker.aria'
  | 'page.ask.skill_picker.tooltip'
  | 'page.ask.skill_quota.badge'
  | 'page.ask.skill_quota.empty'
  | 'page.ask.skill_quota.hint'
  | 'page.ask.stalled.hint'
  | 'page.ask.stance.empty'
  | 'page.ask.stance_row.empty'
  | 'page.ask.submit.cta'
  | 'page.ask.submit.pending'
  | 'page.ask.sync_failed.error'
  | 'page.ask.token.tooltip'
  | 'page.ask.token.unit'
  | 'page.ask.type_picker.aria'
  | 'page.ask.type_picker.placeholder'
  | 'page.ask.type_picker.tooltip'
  | 'page.ask.ungrouped.empty'
  | 'page.ask.ungrouped.title'
  | 'page.ask.upload.aria'
  | 'page.ask.upload.error'
  | 'page.ask.upload.tooltip'
  | 'page.create.category_all.tab'
  | 'page.create.confirm.desc'
  | 'page.create.confirm.title'
  | 'page.create.confirm_extra.title'
  | 'page.create.confirm_extra_evaluation.badge'
  | 'page.create.confirm_extra_red_team.badge'
  | 'page.create.confirm_field.empty'
  | 'page.create.confirm_field.label'
  | 'page.create.confirm_material.meta'
  | 'page.create.confirm_material.title'
  | 'page.create.confirm_mode.title'
  | 'page.create.confirm_persona.meta'
  | 'page.create.confirm_persona.title'
  | 'page.create.confirm_skill.title'
  | 'page.create.confirm_target.empty'
  | 'page.create.confirm_target.title'
  | 'page.create.confirm_task_type.title'
  | 'page.create.cost.desc'
  | 'page.create.cost.title'
  | 'page.create.dropped_skill.desc'
  | 'page.create.dropped_skill.title'
  | 'page.create.dropzone.cta'
  | 'page.create.dropzone.hint'
  | 'page.create.evaluation.desc'
  | 'page.create.evaluation.label'
  | 'page.create.examples.cta'
  | 'page.create.extra_fields.desc'
  | 'page.create.extra_fields_unknown.label'
  | 'page.create.extract.error'
  | 'page.create.extract.hint'
  | 'page.create.extract.pending'
  | 'page.create.extract.success'
  | 'page.create.extract_reason_unknown.error'
  | 'page.create.feature_calibration.badge'
  | 'page.create.feature_cross_exam.badge'
  | 'page.create.feature_none.badge'
  | 'page.create.fields.hint'
  | 'page.create.fields.title'
  | 'page.create.generic_field.label'
  | 'page.create.generic_field.placeholder'
  | 'page.create.input_mode_file.tab'
  | 'page.create.input_mode_text.tab'
  | 'page.create.launch.cta'
  | 'page.create.launch.error'
  | 'page.create.launch_no_material.error'
  | 'page.create.launch_pack_mismatch.error'
  | 'page.create.material.desc'
  | 'page.create.material.title'
  | 'page.create.meta.title'
  | 'page.create.mode.title'
  | 'page.create.mode_card.unit'
  | 'page.create.mode_name.value'
  | 'page.create.mode_summary.title'
  | 'page.create.mode_summary.unit'
  | 'page.create.option.desc'
  | 'page.create.option.title'
  | 'page.create.over_max.desc'
  | 'page.create.over_max.title'
  | 'page.create.pack_card.unit'
  | 'page.create.pack_conflict.desc'
  | 'page.create.pack_conflict.title'
  | 'page.create.pack_conflict.value'
  | 'page.create.pack_intro.desc'
  | 'page.create.persona.desc'
  | 'page.create.persona.title'
  | 'page.create.persona_list.meta'
  | 'page.create.persona_list.title'
  | 'page.create.red_team.desc'
  | 'page.create.red_team.label'
  | 'page.create.red_team_case_community.badge'
  | 'page.create.red_team_case_localization.badge'
  | 'page.create.red_team_case_pr.badge'
  | 'page.create.red_team_case_pricing.badge'
  | 'page.create.skill.desc'
  | 'page.create.skill.title'
  | 'page.create.skill_card.meta'
  | 'page.create.skill_error.cta'
  | 'page.create.skill_error.title'
  | 'page.create.skill_list.empty'
  | 'page.create.skill_list.error'
  | 'page.create.stage.confirm'
  | 'page.create.stage.material'
  | 'page.create.stage.option'
  | 'page.create.stage.persona'
  | 'page.create.stage.skill'
  | 'page.create.stage.task_type'
  | 'page.create.target.label'
  | 'page.create.target.placeholder'
  | 'page.create.task_type.desc'
  | 'page.create.task_type.title'
  | 'page.create.task_type_open.desc'
  | 'page.create.task_type_scoped.desc'
  | 'page.evaluation.back.cta'
  | 'page.evaluation.completed.label'
  | 'page.evaluation.created.label'
  | 'page.evaluation.critical.title'
  | 'page.evaluation.dimension.hint'
  | 'page.evaluation.dimensions.title'
  | 'page.evaluation.ethics.title'
  | 'page.evaluation.ethics_error.desc'
  | 'page.evaluation.ethics_score.label'
  | 'page.evaluation.header.aria'
  | 'page.evaluation.header.loading'
  | 'page.evaluation.header.title'
  | 'page.evaluation.load_error.desc'
  | 'page.evaluation.load_error.title'
  | 'page.evaluation.meta.title'
  | 'page.evaluation.not_generated.desc'
  | 'page.evaluation.not_generated.title'
  | 'page.evaluation.overall.desc'
  | 'page.evaluation.overall.hint'
  | 'page.evaluation.overall.title'
  | 'page.evaluation.radar.label'
  | 'page.evaluation.radar.title'
  | 'page.evaluation.score.label'
  | 'page.evaluation.score.value'
  | 'page.evaluation.skill.label'
  | 'page.evaluation.state.fail'
  | 'page.evaluation.state.overall_fail'
  | 'page.evaluation.state.overall_pass'
  | 'page.evaluation.state.pass'
  | 'page.evaluation.stereotype.label'
  | 'page.evaluation.time.empty'
  | 'page.evaluation.timeline.title'
  | 'page.evaluation.unknown_dimension.label'
  | 'page.evaluation.violations.label'
  | 'page.forgot.email.label'
  | 'page.forgot.email.placeholder'
  | 'page.forgot.header.desc'
  | 'page.forgot.header.title'
  | 'page.forgot.meta.title'
  | 'page.forgot.sent.hint'
  | 'page.forgot.sent.link'
  | 'page.forgot.sent.success'
  | 'page.forgot.signin.hint'
  | 'page.forgot.submit.cta'
  | 'page.forgot.submit.error'
  | 'page.history.confirm_dialog.aria'
  | 'page.history.confirm_dialog.desc'
  | 'page.history.count.loaded_only'
  | 'page.history.count.total'
  | 'page.history.count.total_and_loaded'
  | 'page.history.delete.error'
  | 'page.history.group.meta'
  | 'page.history.header.desc'
  | 'page.history.header.title'
  | 'page.history.item.aria'
  | 'page.history.item.tooltip'
  | 'page.history.list_empty.cta'
  | 'page.history.list_empty.title'
  | 'page.history.load.error'
  | 'page.history.load_error.desc'
  | 'page.history.load_error.title'
  | 'page.history.load_more.cta'
  | 'page.history.load_more.error'
  | 'page.history.load_more.remaining'
  | 'page.history.load_more.success'
  | 'page.history.meta.title'
  | 'page.landing.meta.title'
  | 'page.ledger.adoption.label'
  | 'page.ledger.avg_model_cost.label'
  | 'page.ledger.avg_willingness.label'
  | 'page.ledger.bin_claimed.value'
  | 'page.ledger.bin_observed.value'
  | 'page.ledger.bins.title'
  | 'page.ledger.bins.value'
  | 'page.ledger.brier.hint'
  | 'page.ledger.brier.label'
  | 'page.ledger.by_task_type.title'
  | 'page.ledger.calibration.desc'
  | 'page.ledger.calibration.hint'
  | 'page.ledger.calibration.title'
  | 'page.ledger.cost_per_adopted.label'
  | 'page.ledger.cost_per_useful.label'
  | 'page.ledger.decision_change.label'
  | 'page.ledger.ece.hint'
  | 'page.ledger.ece.label'
  | 'page.ledger.error.cta'
  | 'page.ledger.error.hint'
  | 'page.ledger.error.pending'
  | 'page.ledger.error.title'
  | 'page.ledger.excluded_rows.value'
  | 'page.ledger.feedback_coverage.label'
  | 'page.ledger.header.desc'
  | 'page.ledger.header.title'
  | 'page.ledger.hit_rate.label'
  | 'page.ledger.hours_saved.label'
  | 'page.ledger.hours_saved.value'
  | 'page.ledger.item.meta'
  | 'page.ledger.leaderboard.title'
  | 'page.ledger.list.error'
  | 'page.ledger.list.label'
  | 'page.ledger.list.title'
  | 'page.ledger.list_empty.desc'
  | 'page.ledger.list_empty.title'
  | 'page.ledger.low_confidence.hint'
  | 'page.ledger.mean_confidence.label'
  | 'page.ledger.meta.title'
  | 'page.ledger.observed_hit.hint'
  | 'page.ledger.observed_hit.label'
  | 'page.ledger.over_estimate.value'
  | 'page.ledger.panel.label'
  | 'page.ledger.pending_verification.label'
  | 'page.ledger.sample.value'
  | 'page.ledger.stat.empty'
  | 'page.ledger.state.hit'
  | 'page.ledger.state.miss'
  | 'page.ledger.state.partial'
  | 'page.ledger.state.unknown'
  | 'page.ledger.task_adopted.value'
  | 'page.ledger.task_useful.value'
  | 'page.ledger.top_fixes.title'
  | 'page.ledger.top_fixes.value'
  | 'page.ledger.total_judgments.label'
  | 'page.ledger.under_estimate.value'
  | 'page.ledger.useful_rate.label'
  | 'page.ledger.value.title'
  | 'page.ledger.verified.label'
  | 'page.ledger.verified_rows.value'
  | 'page.ledger.verify_error.cta'
  | 'page.ledger.verify_error.title'
  | 'page.login.email.label'
  | 'page.login.email.placeholder'
  | 'page.login.forgot.link'
  | 'page.login.header.desc'
  | 'page.login.header.title'
  | 'page.login.meta.title'
  | 'page.login.password.label'
  | 'page.login.password.placeholder'
  | 'page.login.signup.hint'
  | 'page.login.submit.cta'
  | 'page.login.submit.error'
  | 'page.login.submit.pending'
  | 'page.personas.compare.label'
  | 'page.personas.compare.title'
  | 'page.personas.compare_enter'
  | 'page.personas.compare_exit'
  | 'page.personas.filter.cta'
  | 'page.personas.filter.title'
  | 'page.personas.filter_all'
  | 'page.personas.header.title'
  | 'page.personas.list.pending'
  | 'page.personas.list_empty.cta'
  | 'page.personas.list_empty.desc'
  | 'page.personas.list_empty.title'
  | 'page.personas.meta.title'
  | 'page.personas.pack_unknown'
  | 'page.personas.rules.title'
  | 'page.personas.search.placeholder'
  | 'page.personas.triggers.title'
  | 'page.plans.anon.hint'
  | 'page.plans.banner_byok'
  | 'page.plans.banner_credits'
  | 'page.plans.banner_no_quota'
  | 'page.plans.bonus.label'
  | 'page.plans.byok.cta'
  | 'page.plans.byok.desc'
  | 'page.plans.byok.title'
  | 'page.plans.card.badge'
  | 'page.plans.card.cta'
  | 'page.plans.card.hint'
  | 'page.plans.card.label'
  | 'page.plans.cdk.aria'
  | 'page.plans.cdk.cta'
  | 'page.plans.cdk.error'
  | 'page.plans.cdk.hint'
  | 'page.plans.cdk.placeholder'
  | 'page.plans.cdk.success'
  | 'page.plans.cdk.title'
  | 'page.plans.cdk_desc_credits'
  | 'page.plans.cdk_desc_plan'
  | 'page.plans.credits.label'
  | 'page.plans.credits.value'
  | 'page.plans.feature_byok'
  | 'page.plans.feature_cost'
  | 'page.plans.feature_reviews'
  | 'page.plans.guest.hint'
  | 'page.plans.header.desc'
  | 'page.plans.header.title'
  | 'page.plans.list.error'
  | 'page.plans.list.pending'
  | 'page.plans.list.title'
  | 'page.plans.manual.desc'
  | 'page.plans.manual.title'
  | 'page.plans.meta.title'
  | 'page.plans.price.unit'
  | 'page.plans.progress.hint'
  | 'page.plans.progress.label'
  | 'page.plans.quota.error'
  | 'page.plans.quota.pending'
  | 'page.plans.quota.title'
  | 'page.plans.request.hint'
  | 'page.plans.tagline_free'
  | 'page.plans.tagline_pro'
  | 'page.plans.tagline_team'
  | 'page.plans.tier.label'
  | 'page.plans.used.label'
  | 'page.privacy.collect.badge'
  | 'page.privacy.collection.title'
  | 'page.privacy.collection_apikey.label'
  | 'page.privacy.collection_apikey_delete.desc'
  | 'page.privacy.collection_apikey_encrypted.desc'
  | 'page.privacy.collection_apikey_masked.desc'
  | 'page.privacy.collection_apikey_separate.desc'
  | 'page.privacy.collection_collected.label'
  | 'page.privacy.collection_collected_account.desc'
  | 'page.privacy.collection_collected_chat.desc'
  | 'page.privacy.collection_collected_config.desc'
  | 'page.privacy.collection_collected_images.desc'
  | 'page.privacy.collection_collected_materials.desc'
  | 'page.privacy.collection_collected_report.desc'
  | 'page.privacy.collection_collected_usage.desc'
  | 'page.privacy.collection_not.label'
  | 'page.privacy.collection_not_fingerprint.desc'
  | 'page.privacy.collection_not_history.desc'
  | 'page.privacy.collection_not_identity.desc'
  | 'page.privacy.contact.desc'
  | 'page.privacy.contact.title'
  | 'page.privacy.footer.desc'
  | 'page.privacy.header.link'
  | 'page.privacy.header.meta'
  | 'page.privacy.header.subtitle'
  | 'page.privacy.header.title'
  | 'page.privacy.key.badge'
  | 'page.privacy.meta.title'
  | 'page.privacy.no_collect.badge'
  | 'page.privacy.retention.badge'
  | 'page.privacy.retention.title'
  | 'page.privacy.retention_policy.label'
  | 'page.privacy.retention_policy_delete.desc'
  | 'page.privacy.retention_policy_exception.desc'
  | 'page.privacy.retention_policy_export.desc'
  | 'page.privacy.retention_policy_forever.desc'
  | 'page.privacy.security.badge'
  | 'page.privacy.security.title'
  | 'page.privacy.security_tech.label'
  | 'page.privacy.security_tech_cors.desc'
  | 'page.privacy.security_tech_key.desc'
  | 'page.privacy.security_tech_password.desc'
  | 'page.privacy.security_tech_token.desc'
  | 'page.privacy.security_tech_upload.desc'
  | 'page.privacy.third_party.badge'
  | 'page.privacy.third_party.title'
  | 'page.privacy.third_party_llm.label'
  | 'page.privacy.third_party_llm_ollama.desc'
  | 'page.privacy.third_party_llm_only.desc'
  | 'page.privacy.third_party_llm_providers.desc'
  | 'page.privacy.third_party_llm_scope.desc'
  | 'page.privacy.third_party_providers.label'
  | 'page.privacy.usage.title'
  | 'page.privacy.usage_admin.label'
  | 'page.privacy.usage_admin_access.desc'
  | 'page.privacy.usage_admin_audit.desc'
  | 'page.privacy.usage_admin_unchanged.desc'
  | 'page.privacy.usage_never.label'
  | 'page.privacy.usage_never_copy.desc'
  | 'page.privacy.usage_never_showcase.desc'
  | 'page.privacy.usage_never_training.desc'
  | 'page.privacy.usage_purpose.label'
  | 'page.privacy.usage_purpose_isolated.desc'
  | 'page.privacy.usage_purpose_retained.desc'
  | 'page.privacy.usage_purpose_single.desc'
  | 'page.privacy.use.badge'
  | 'page.privacy.verify.badge'
  | 'page.privacy.verify.title'
  | 'page.privacy.verify_checkable.label'
  | 'page.privacy.verify_checkable_byok.desc'
  | 'page.privacy.verify_checkable_export.desc'
  | 'page.privacy.verify_checkable_hosted.desc'
  | 'page.privacy.verify_checkable_oss.desc'
  | 'page.privacy.verify_checkable_selfhost.desc'
  | 'page.progress.aggregation.title'
  | 'page.progress.back.cta'
  | 'page.progress.cost.label'
  | 'page.progress.cross_exam.title'
  | 'page.progress.done.cta'
  | 'page.progress.done.title'
  | 'page.progress.failed.cta'
  | 'page.progress.failed.desc'
  | 'page.progress.failed.title'
  | 'page.progress.header.subtitle'
  | 'page.progress.header.title'
  | 'page.progress.load_error.desc'
  | 'page.progress.load_error.title'
  | 'page.progress.meta.title'
  | 'page.progress.not_found.empty'
  | 'page.progress.overall.label'
  | 'page.progress.persona_cost.label'
  | 'page.progress.persona_count.label'
  | 'page.progress.persona_done.badge'
  | 'page.progress.persona_failed.error'
  | 'page.progress.persona_remaining.pending'
  | 'page.progress.personas.empty'
  | 'page.progress.personas.pending'
  | 'page.progress.personas.title'
  | 'page.progress.poll_failure.error'
  | 'page.progress.project.badge'
  | 'page.progress.report.cta'
  | 'page.progress.running_card.pending'
  | 'page.progress.running_card.title'
  | 'page.progress.selected_personas.badge'
  | 'page.progress.skill.label'
  | 'page.progress.stage.completed'
  | 'page.progress.stage.running'
  | 'page.progress.stage.waiting'
  | 'page.progress.stall.hint'
  | 'page.progress.status.label'
  | 'page.progress.ws_reconnect.hint'
  | 'page.progress.ws_unavailable.hint'
  | 'page.register.email.label'
  | 'page.register.email.placeholder'
  | 'page.register.header.desc'
  | 'page.register.header.title'
  | 'page.register.meta.title'
  | 'page.register.name.label'
  | 'page.register.name.placeholder'
  | 'page.register.password.label'
  | 'page.register.password.placeholder'
  | 'page.register.signin.hint'
  | 'page.register.submit.cta'
  | 'page.register.submit.error'
  | 'page.register.submit.pending'
  | 'page.register.terms.consent'
  | 'page.report.adaptive.empty'
  | 'page.report.adaptive.hint'
  | 'page.report.adaptive.title'
  | 'page.report.adaptive_executed.label'
  | 'page.report.adaptive_initial.label'
  | 'page.report.adaptive_reason.label'
  | 'page.report.adaptive_saved.label'
  | 'page.report.adaptive_step.hint'
  | 'page.report.adaptive_step.label'
  | 'page.report.adaptive_step.value'
  | 'page.report.adaptive_stop.label'
  | 'page.report.argument.empty'
  | 'page.report.argument.label'
  | 'page.report.argument_con.label'
  | 'page.report.argument_pro.label'
  | 'page.report.body.loading'
  | 'page.report.budget.desc'
  | 'page.report.budget.hint'
  | 'page.report.budget.title'
  | 'page.report.budget_generic.desc'
  | 'page.report.calibration.empty'
  | 'page.report.calibration.error'
  | 'page.report.calibration.success'
  | 'page.report.calibration.title'
  | 'page.report.change.badge'
  | 'page.report.change.desc'
  | 'page.report.change.empty'
  | 'page.report.change.error'
  | 'page.report.change.label'
  | 'page.report.change_threshold.label'
  | 'page.report.compliance.badge'
  | 'page.report.compliance.title'
  | 'page.report.confidence.title'
  | 'page.report.confidence.unit'
  | 'page.report.consensus.badge'
  | 'page.report.consensus.desc'
  | 'page.report.consensus.hint'
  | 'page.report.consensus.meta'
  | 'page.report.consensus.title'
  | 'page.report.consensus_single.badge'
  | 'page.report.consensus_unknown.meta'
  | 'page.report.cross_exam.badge'
  | 'page.report.cross_exam.title'
  | 'page.report.cross_exam_absent.desc'
  | 'page.report.cross_exam_failures.empty'
  | 'page.report.cross_exam_failures.label'
  | 'page.report.cross_exam_failures.title'
  | 'page.report.cross_exam_fallback.desc'
  | 'page.report.cross_exam_legacy.desc'
  | 'page.report.cross_exam_limitation.label'
  | 'page.report.cross_exam_mode_unknown.desc'
  | 'page.report.cross_exam_mode_unknown.label'
  | 'page.report.cross_exam_mode_unknown.value'
  | 'page.report.cross_exam_skipped.desc'
  | 'page.report.degradation.desc'
  | 'page.report.degradation.label'
  | 'page.report.degradation_partial.desc'
  | 'page.report.disagreement.hint'
  | 'page.report.disagreements.title'
  | 'page.report.dispute.empty'
  | 'page.report.dispute.error'
  | 'page.report.dispute_empty.desc'
  | 'page.report.dispute_empty.hint'
  | 'page.report.ethics.title'
  | 'page.report.ethics_score.label'
  | 'page.report.ethics_stereotype.label'
  | 'page.report.ethics_violations.label'
  | 'page.report.evaluation.cta'
  | 'page.report.evaluation.error'
  | 'page.report.evaluation.meta'
  | 'page.report.evaluation.title'
  | 'page.report.evaluation_critical.title'
  | 'page.report.evaluation_dimension.empty'
  | 'page.report.evaluation_dimension.label'
  | 'page.report.evaluation_dimension.value'
  | 'page.report.evaluation_full.cta'
  | 'page.report.evaluation_overall.label'
  | 'page.report.evaluation_run.error'
  | 'page.report.failed.desc'
  | 'page.report.failed.empty'
  | 'page.report.failed.hint'
  | 'page.report.failed.label'
  | 'page.report.failed.title'
  | 'page.report.feedback.cta'
  | 'page.report.feedback.desc'
  | 'page.report.feedback.error'
  | 'page.report.feedback.success'
  | 'page.report.feedback.title'
  | 'page.report.feedback_adopted.label'
  | 'page.report.feedback_decision.label'
  | 'page.report.feedback_fix.value'
  | 'page.report.feedback_hours.label'
  | 'page.report.feedback_pay.label'
  | 'page.report.feedback_useful.cta'
  | 'page.report.feedback_useless.cta'
  | 'page.report.fix_personas.label'
  | 'page.report.fix_suggestion.label'
  | 'page.report.fix_why.label'
  | 'page.report.fixes.title'
  | 'page.report.gaps.title'
  | 'page.report.gate.empty'
  | 'page.report.gate.label'
  | 'page.report.gate.title'
  | 'page.report.gated.cta'
  | 'page.report.gated.desc'
  | 'page.report.gated.hint'
  | 'page.report.gated.subtitle'
  | 'page.report.gated_fix.title'
  | 'page.report.gated_recommendation.label'
  | 'page.report.gated_risk.label'
  | 'page.report.gated_summary.title'
  | 'page.report.header.badge'
  | 'page.report.header.subtitle'
  | 'page.report.header.title'
  | 'page.report.html.aria'
  | 'page.report.html.cta'
  | 'page.report.html.desc'
  | 'page.report.html.empty'
  | 'page.report.html.error'
  | 'page.report.html.tooltip'
  | 'page.report.limitation_demographic'
  | 'page.report.limitation_feedback_loop'
  | 'page.report.limitation_materials'
  | 'page.report.limitation_synthetic'
  | 'page.report.limitation_variance'
  | 'page.report.limitations.title'
  | 'page.report.link_detail.cta'
  | 'page.report.link_login.cta'
  | 'page.report.link_new_review.cta'
  | 'page.report.load_error.desc'
  | 'page.report.load_error.title'
  | 'page.report.md_banner.desc'
  | 'page.report.md_budget.hint'
  | 'page.report.md_cross_exam.empty'
  | 'page.report.md_cross_exam.hint'
  | 'page.report.md_cross_exam.label'
  | 'page.report.md_cross_exam_absent.desc'
  | 'page.report.md_cross_exam_legacy.desc'
  | 'page.report.md_cross_exam_skipped.desc'
  | 'page.report.md_evidence.label'
  | 'page.report.md_failures.label'
  | 'page.report.md_fix.label'
  | 'page.report.md_gate.title'
  | 'page.report.md_lang.empty'
  | 'page.report.md_lang.value'
  | 'page.report.md_lang_en.value'
  | 'page.report.md_lang_zh.value'
  | 'page.report.md_risk.empty'
  | 'page.report.md_risk.title'
  | 'page.report.md_stance.label'
  | 'page.report.md_vote.empty'
  | 'page.report.md_vote.label'
  | 'page.report.md_vote_none.label'
  | 'page.report.meta.title'
  | 'page.report.next_test.title'
  | 'page.report.next_test_audience.label'
  | 'page.report.next_test_materials.label'
  | 'page.report.next_test_tasks.label'
  | 'page.report.panel_selection.label'
  | 'page.report.panel_selection.title'
  | 'page.report.pending.cta'
  | 'page.report.pending.desc'
  | 'page.report.pending.title'
  | 'page.report.persona_evidence.label'
  | 'page.report.persona_issues.label'
  | 'page.report.personas.title'
  | 'page.report.prediction_criterion.label'
  | 'page.report.prediction_method.label'
  | 'page.report.prediction_metric.hint'
  | 'page.report.prediction_metric.label'
  | 'page.report.prediction_window.label'
  | 'page.report.predictions.badge'
  | 'page.report.predictions.desc'
  | 'page.report.predictions.hint'
  | 'page.report.predictions.title'
  | 'page.report.sep_colon'
  | 'page.report.sep_enum'
  | 'page.report.sep_semicolon'
  | 'page.report.share.aria'
  | 'page.report.share.badge'
  | 'page.report.share.cta'
  | 'page.report.share.desc'
  | 'page.report.share.error'
  | 'page.report.share.hint'
  | 'page.report.share.title'
  | 'page.report.share_copy.error'
  | 'page.report.share_create.cta'
  | 'page.report.share_hidden.label'
  | 'page.report.share_item_account.label'
  | 'page.report.share_item_calibration.label'
  | 'page.report.share_item_cost.label'
  | 'page.report.share_item_material.label'
  | 'page.report.share_item_meta.label'
  | 'page.report.share_item_report.label'
  | 'page.report.share_revoke.cta'
  | 'page.report.share_revoke.error'
  | 'page.report.share_visible.label'
  | 'page.report.stance.empty'
  | 'page.report.stance.title'
  | 'page.report.stance.value'
  | 'page.report.summary.title'
  | 'page.report.summary_consensus.hint'
  | 'page.report.summary_consensus.label'
  | 'page.report.summary_evidence.label'
  | 'page.report.summary_risk_absent.desc'
  | 'page.report.summary_risk_missing.desc'
  | 'page.report.summary_stance.label'
  | 'page.report.suppressed.desc'
  | 'page.report.suppressed_no_update.desc'
  | 'page.report.synthetic_banner.desc'
  | 'page.report.synthetic_banner.title'
  | 'page.report.threshold.error'
  | 'page.report.unknown_level.value'
  | 'page.report.usage.desc'
  | 'page.report.usage.hint'
  | 'page.report.vote.badge'
  | 'page.report.vote.empty'
  | 'page.report.vote.title'
  | 'page.report.vote_threshold.badge'
  | 'page.report.vote_unchanged.desc'
  | 'page.reset.confirm.label'
  | 'page.reset.confirm.placeholder'
  | 'page.reset.done.cta'
  | 'page.reset.done.hint'
  | 'page.reset.done.success'
  | 'page.reset.header.title'
  | 'page.reset.meta.title'
  | 'page.reset.no_token.error'
  | 'page.reset.no_token.link'
  | 'page.reset.password.label'
  | 'page.reset.password.placeholder'
  | 'page.reset.submit.cta'
  | 'page.reset.submit.error'
  | 'page.settings.account_card.desc'
  | 'page.settings.account_card.title'
  | 'page.settings.api_base.hint'
  | 'page.settings.api_base.label'
  | 'page.settings.api_base.placeholder'
  | 'page.settings.api_base_compat.placeholder'
  | 'page.settings.byok.desc'
  | 'page.settings.byok.error'
  | 'page.settings.byok.hint'
  | 'page.settings.byok.title'
  | 'page.settings.cdk.cta'
  | 'page.settings.cdk.desc'
  | 'page.settings.cdk.error'
  | 'page.settings.cdk.hint'
  | 'page.settings.cdk.placeholder'
  | 'page.settings.cdk.success'
  | 'page.settings.cdk.title'
  | 'page.settings.cdk_guest.hint'
  | 'page.settings.cdk_plan.desc'
  | 'page.settings.data.desc'
  | 'page.settings.data.title'
  | 'page.settings.delete_account.cta'
  | 'page.settings.delete_account.error'
  | 'page.settings.delete_confirm.cta'
  | 'page.settings.delete_confirm.desc'
  | 'page.settings.delete_confirm.label'
  | 'page.settings.delete_done.desc'
  | 'page.settings.delete_done.hint'
  | 'page.settings.delete_password.label'
  | 'page.settings.export.cta'
  | 'page.settings.export.error'
  | 'page.settings.footer.link'
  | 'page.settings.group_account.label'
  | 'page.settings.group_data.label'
  | 'page.settings.group_model.label'
  | 'page.settings.group_usage.label'
  | 'page.settings.guest_card.cta'
  | 'page.settings.guest_card.desc'
  | 'page.settings.guest_card.title'
  | 'page.settings.header.desc'
  | 'page.settings.header.title'
  | 'page.settings.key_input.aria'
  | 'page.settings.key_input.placeholder'
  | 'page.settings.key_input_compat.placeholder'
  | 'page.settings.key_item.error'
  | 'page.settings.key_item.meta'
  | 'page.settings.key_privacy.title'
  | 'page.settings.meta.title'
  | 'page.settings.model_id.error'
  | 'page.settings.model_id.hint'
  | 'page.settings.model_id.label'
  | 'page.settings.model_id.placeholder'
  | 'page.settings.model_id_compat.placeholder'
  | 'page.settings.multimodal.desc'
  | 'page.settings.name.error'
  | 'page.settings.name.hint'
  | 'page.settings.name.label'
  | 'page.settings.name.placeholder'
  | 'page.settings.name.success'
  | 'page.settings.password.cta'
  | 'page.settings.password.error'
  | 'page.settings.password.hint'
  | 'page.settings.password.label'
  | 'page.settings.password.success'
  | 'page.settings.password_confirm.placeholder'
  | 'page.settings.password_current.placeholder'
  | 'page.settings.password_new.placeholder'
  | 'page.settings.privacy_device.desc'
  | 'page.settings.privacy_device.label'
  | 'page.settings.privacy_optout.desc'
  | 'page.settings.privacy_optout.hint'
  | 'page.settings.privacy_optout.label'
  | 'page.settings.privacy_selfhost.desc'
  | 'page.settings.privacy_source.desc'
  | 'page.settings.privacy_use.desc'
  | 'page.settings.privacy_use.label'
  | 'page.settings.privacy_who.desc'
  | 'page.settings.privacy_who.label'
  | 'page.settings.provider_anthropic.desc'
  | 'page.settings.provider_anthropic.label'
  | 'page.settings.provider_openai.desc'
  | 'page.settings.provider_openai.label'
  | 'page.settings.revoke.confirm'
  | 'page.settings.revoke.cta'
  | 'page.settings.revoke.desc'
  | 'page.settings.revoke.hint'
  | 'page.settings.revoke.label'
  | 'page.settings.save_key.cta'
  | 'page.settings.save_key.error'
  | 'page.settings.save_key.success'
  | 'page.settings.section_account.desc'
  | 'page.settings.section_account.tab'
  | 'page.settings.section_account.title'
  | 'page.settings.section_account_guest.desc'
  | 'page.settings.section_data.desc'
  | 'page.settings.section_data.tab'
  | 'page.settings.section_data.title'
  | 'page.settings.section_model.desc'
  | 'page.settings.section_model.tab'
  | 'page.settings.section_model.title'
  | 'page.settings.section_usage.desc'
  | 'page.settings.section_usage.tab'
  | 'page.settings.section_usage.title'
  | 'page.settings.test.cta'
  | 'page.settings.test.error'
  | 'page.settings.test.meta'
  | 'page.settings.test.success'
  | 'page.settings.usage.hint'
  | 'page.settings.usage.title'
  | 'page.settings.usage_bonus.label'
  | 'page.settings.usage_cost.label'
  | 'page.settings.usage_credits.label'
  | 'page.settings.usage_credits.unit'
  | 'page.settings.usage_reviews.hint'
  | 'page.settings.usage_reviews.label'
  | 'page.settings.usage_server_cost.label'
  | 'page.settings.usage_tokens.hint'
  | 'page.settings.usage_tokens.label'
  | 'page.settings.usage_tokens.unit'
  | 'page.shared.agreed.title'
  | 'page.shared.evidence_quality.label'
  | 'page.shared.fixes.title'
  | 'page.shared.footer.cta'
  | 'page.shared.footer.desc'
  | 'page.shared.gaps.title'
  | 'page.shared.header.meta'
  | 'page.shared.header.title'
  | 'page.shared.load_error.desc'
  | 'page.shared.load_error.title'
  | 'page.shared.meta.title'
  | 'page.shared.notes.title'
  | 'page.shared.questioned.title'
  | 'page.shared.release_risk.label'
  | 'page.shared.revoked.cta'
  | 'page.shared.revoked.desc'
  | 'page.shared.revoked.title'
  | 'page.shared.share_note.badge'
  | 'page.shared.suggestion.label'
  | 'page.shared.summary.title'
  | 'page.skills.card.cta'
  | 'page.skills.card_disabled.hint'
  | 'page.skills.card_task_types.label'
  | 'page.skills.card_use_cases.label'
  | 'page.skills.header.subtitle'
  | 'page.skills.header.title'
  | 'page.skills.list.empty'
  | 'page.skills.list_error.cta'
  | 'page.skills.list_error.desc'
  | 'page.skills.list_error.title'
  | 'page.skills.meta.title'
  | 'page.task_types.card.cta'
  | 'page.task_types.card_score.label'
  | 'page.task_types.card_stance.label'
  | 'page.task_types.category_community.label'
  | 'page.task_types.category_development.label'
  | 'page.task_types.category_operations.label'
  | 'page.task_types.category_other.label'
  | 'page.task_types.category_product.label'
  | 'page.task_types.count.total'
  | 'page.task_types.detail.error'
  | 'page.task_types.detail_error.hint'
  | 'page.task_types.detail_error.title'
  | 'page.task_types.filter.tab'
  | 'page.task_types.header.error'
  | 'page.task_types.header.loading'
  | 'page.task_types.header.title'
  | 'page.task_types.list.empty'
  | 'page.task_types.list.error'
  | 'page.task_types.list_error.cta'
  | 'page.task_types.list_error.desc'
  | 'page.task_types.list_error.title'
  | 'page.task_types.meta.title'
  | 'page.task_types.modal.title'
  | 'page.task_types.modal_base.label'
  | 'page.task_types.modal_desc.label'
  | 'page.task_types.modal_id.label'
  | 'page.task_types.modal_name.label'
  | 'page.task_types.modal_score.label'
  | 'page.task_types.modal_stance.label'
  | 'page.terms.account.title'
  | 'page.terms.account_duty.label'
  | 'page.terms.account_duty_lawful.desc'
  | 'page.terms.account_duty_password.desc'
  | 'page.terms.account_duty_rights.desc'
  | 'page.terms.account_enforcement.label'
  | 'page.terms.account_enforcement_appeal.desc'
  | 'page.terms.account_enforcement_suspend.desc'
  | 'page.terms.account_forbidden.label'
  | 'page.terms.account_forbidden_bypass.desc'
  | 'page.terms.account_forbidden_farming.desc'
  | 'page.terms.account_forbidden_probing.desc'
  | 'page.terms.account_forbidden_resale.desc'
  | 'page.terms.availability.title'
  | 'page.terms.availability_data.label'
  | 'page.terms.availability_data_backup.desc'
  | 'page.terms.availability_data_copy.desc'
  | 'page.terms.availability_data_export.desc'
  | 'page.terms.availability_sla.label'
  | 'page.terms.availability_sla_asis.desc'
  | 'page.terms.availability_sla_maintenance.desc'
  | 'page.terms.availability_sla_solo.desc'
  | 'page.terms.availability_sla_upstream.desc'
  | 'page.terms.billing.title'
  | 'page.terms.billing_payment.label'
  | 'page.terms.billing_payment_byok.desc'
  | 'page.terms.billing_payment_manual.desc'
  | 'page.terms.billing_payment_quota.desc'
  | 'page.terms.billing_refund.label'
  | 'page.terms.billing_refund_manual.desc'
  | 'page.terms.billing_refund_used.desc'
  | 'page.terms.contact.hint'
  | 'page.terms.filing.label'
  | 'page.terms.header.link'
  | 'page.terms.header.meta'
  | 'page.terms.header.subtitle'
  | 'page.terms.header.title'
  | 'page.terms.ip.title'
  | 'page.terms.ip_ours.label'
  | 'page.terms.ip_ours_oss.desc'
  | 'page.terms.ip_ours_personas.desc'
  | 'page.terms.ip_yours.label'
  | 'page.terms.ip_yours_free_use.desc'
  | 'page.terms.ip_yours_no_training.desc'
  | 'page.terms.ip_yours_own.desc'
  | 'page.terms.liability.title'
  | 'page.terms.liability_cap.label'
  | 'page.terms.liability_cap_amount.desc'
  | 'page.terms.liability_cap_indirect.desc'
  | 'page.terms.liability_change.label'
  | 'page.terms.liability_change_accept.desc'
  | 'page.terms.liability_change_notice.desc'
  | 'page.terms.liability_nature.label'
  | 'page.terms.liability_nature_mandatory.desc'
  | 'page.terms.liability_nature_unreviewed.desc'
  | 'page.terms.meta.title'
  | 'page.terms.related.desc'
  | 'page.terms.service.title'
  | 'page.terms.service_not.label'
  | 'page.terms.service_not_advice.desc'
  | 'page.terms.service_not_research.desc'
  | 'page.terms.service_not_usertest.desc'
  | 'page.terms.service_provides.label'
  | 'page.terms.service_provides_byok.desc'
  | 'page.terms.service_provides_hypothesis.desc'
  | 'page.terms.service_provides_review.desc'
  | 'page.terms.termination.desc'
  | 'page.terms.termination.title'
  | 'page.tutorial.count.unknown'
  | 'page.tutorial.count.with_number'
  | 'page.tutorial.filetype_community.desc'
  | 'page.tutorial.filetype_community.title'
  | 'page.tutorial.filetype_crowdfunding.desc'
  | 'page.tutorial.filetype_crowdfunding.title'
  | 'page.tutorial.filetype_devlog.desc'
  | 'page.tutorial.filetype_devlog.title'
  | 'page.tutorial.filetype_gdd.desc'
  | 'page.tutorial.filetype_gdd.title'
  | 'page.tutorial.filetype_localization.desc'
  | 'page.tutorial.filetype_localization.title'
  | 'page.tutorial.filetype_store.desc'
  | 'page.tutorial.filetype_store.title'
  | 'page.tutorial.filetypes.desc'
  | 'page.tutorial.filetypes.title'
  | 'page.tutorial.flow.desc'
  | 'page.tutorial.flow.step'
  | 'page.tutorial.flow.title'
  | 'page.tutorial.header.subtitle'
  | 'page.tutorial.header.title'
  | 'page.tutorial.limits.hint'
  | 'page.tutorial.materials.desc'
  | 'page.tutorial.materials.title'
  | 'page.tutorial.materials_optional.label'
  | 'page.tutorial.materials_required.label'
  | 'page.tutorial.materials_task_type.label'
  | 'page.tutorial.meta.title'
  | 'page.tutorial.method.badge'
  | 'page.tutorial.method_example.desc'
  | 'page.tutorial.method_example.title'
  | 'page.tutorial.method_example_first_use.hint'
  | 'page.tutorial.method_file.desc'
  | 'page.tutorial.method_file.title'
  | 'page.tutorial.method_file_any_doc.hint'
  | 'page.tutorial.method_file_autofill.hint'
  | 'page.tutorial.method_file_editable.hint'
  | 'page.tutorial.method_file_formats.hint'
  | 'page.tutorial.method_manual.desc'
  | 'page.tutorial.method_manual.title'
  | 'page.tutorial.method_manual_fields.hint'
  | 'page.tutorial.method_manual_when.hint'
  | 'page.tutorial.result_calibration.desc'
  | 'page.tutorial.result_calibration.label'
  | 'page.tutorial.result_issues.desc'
  | 'page.tutorial.result_issues.label'
  | 'page.tutorial.result_persona.desc'
  | 'page.tutorial.result_persona.label'
  | 'page.tutorial.result_risk.desc'
  | 'page.tutorial.result_risk.label'
  | 'page.tutorial.result_stance.desc'
  | 'page.tutorial.result_stance.label'
  | 'page.tutorial.results.desc'
  | 'page.tutorial.results.title'
  | 'page.tutorial.start.cta'
  | 'page.tutorial.step_edit.desc'
  | 'page.tutorial.step_edit.label'
  | 'page.tutorial.step_panel.desc'
  | 'page.tutorial.step_panel.label'
  | 'page.tutorial.step_select_type.desc'
  | 'page.tutorial.step_select_type.label'
  | 'page.tutorial.step_upload.desc'
  | 'page.tutorial.step_upload.label'
  | 'page.tutorial.upload.desc'
  | 'page.tutorial.upload.hint'
  | 'page.tutorial.upload.title'
  | 'page.verify.confirm.error'
  | 'page.verify.fail.hint'
  | 'page.verify.fail.link'
  | 'page.verify.fail.title'
  | 'page.verify.meta.title'
  | 'page.verify.no_token.error'
  | 'page.verify.ok.cta'
  | 'page.verify.ok.title'
  | 'page.verify.pending.loading'

/** 无插值变量的 key。useDocumentTitle / tApiError 的形参用它。 */
export type PlainMessageKey =
  | 'catalog.brand.deepseek'
  | 'catalog.brand.glm'
  | 'catalog.brand.kimi'
  | 'catalog.brand.ollama'
  | 'catalog.brand.openai'
  | 'catalog.brand.qwen'
  | 'catalog.eval_dimension.actionability.desc'
  | 'catalog.eval_dimension.actionability.label'
  | 'catalog.eval_dimension.calibration_honesty.desc'
  | 'catalog.eval_dimension.calibration_honesty.label'
  | 'catalog.eval_dimension.ethical_persona_use.desc'
  | 'catalog.eval_dimension.ethical_persona_use.label'
  | 'catalog.eval_dimension.input_grounding.desc'
  | 'catalog.eval_dimension.input_grounding.label'
  | 'catalog.eval_dimension.persona_differentiation.desc'
  | 'catalog.eval_dimension.persona_differentiation.label'
  | 'catalog.eval_dimension.report_structure.desc'
  | 'catalog.eval_dimension.report_structure.label'
  | 'catalog.eval_dimension.risk_detection.desc'
  | 'catalog.eval_dimension.risk_detection.label'
  | 'catalog.eval_dimension.segment_conflict.desc'
  | 'catalog.eval_dimension.segment_conflict.label'
  | 'catalog.material.concept_review__一句话pitch.label'
  | 'catalog.material.concept_review__一句话pitch.placeholder'
  | 'catalog.material.concept_review__定价与平台.label'
  | 'catalog.material.concept_review__定价与平台.placeholder'
  | 'catalog.material.concept_review__截图.label'
  | 'catalog.material.concept_review__截图.placeholder'
  | 'catalog.material.concept_review__核心循环说明.label'
  | 'catalog.material.concept_review__核心循环说明.placeholder'
  | 'catalog.material.concept_review__目标受众.label'
  | 'catalog.material.concept_review__目标受众.placeholder'
  | 'catalog.material.concept_review__竞品对比.label'
  | 'catalog.material.concept_review__竞品对比.placeholder'
  | 'catalog.material.concept_review__系统说明.label'
  | 'catalog.material.concept_review__系统说明.placeholder'
  | 'catalog.material.demo_first_play__实机视频.label'
  | 'catalog.material.demo_first_play__实机视频.placeholder'
  | 'catalog.material.demo_first_play__截图.label'
  | 'catalog.material.demo_first_play__截图.placeholder'
  | 'catalog.material.demo_first_play__核心循环说明.label'
  | 'catalog.material.demo_first_play__核心循环说明.placeholder'
  | 'catalog.material.demo_first_play__游戏名称.label'
  | 'catalog.material.demo_first_play__游戏名称.placeholder'
  | 'catalog.material.demo_first_play__竞品对比.label'
  | 'catalog.material.demo_first_play__竞品对比.placeholder'
  | 'catalog.material.demo_first_play__评价摘要.label'
  | 'catalog.material.demo_first_play__评价摘要.placeholder'
  | 'catalog.material.devlog_review__截图.label'
  | 'catalog.material.devlog_review__截图.placeholder'
  | 'catalog.material.devlog_review__核心循环说明.label'
  | 'catalog.material.devlog_review__核心循环说明.placeholder'
  | 'catalog.material.devlog_review__游戏名称.label'
  | 'catalog.material.devlog_review__游戏名称.placeholder'
  | 'catalog.material.devlog_review__评价摘要.label'
  | 'catalog.material.devlog_review__评价摘要.placeholder'
  | 'catalog.material.discord_community_review__核心循环说明.label'
  | 'catalog.material.discord_community_review__核心循环说明.placeholder'
  | 'catalog.material.discord_community_review__社区名称.label'
  | 'catalog.material.discord_community_review__社区名称.placeholder'
  | 'catalog.material.discord_community_review__竞品对比.label'
  | 'catalog.material.discord_community_review__竞品对比.placeholder'
  | 'catalog.material.discord_community_review__系统说明.label'
  | 'catalog.material.discord_community_review__系统说明.placeholder'
  | 'catalog.material.discord_community_review__评价摘要.label'
  | 'catalog.material.discord_community_review__评价摘要.placeholder'
  | 'catalog.material.kickstarter_review__一句话pitch.label'
  | 'catalog.material.kickstarter_review__一句话pitch.placeholder'
  | 'catalog.material.kickstarter_review__定价与平台.label'
  | 'catalog.material.kickstarter_review__定价与平台.placeholder'
  | 'catalog.material.kickstarter_review__截图.label'
  | 'catalog.material.kickstarter_review__截图.placeholder'
  | 'catalog.material.kickstarter_review__核心循环说明.label'
  | 'catalog.material.kickstarter_review__核心循环说明.placeholder'
  | 'catalog.material.kickstarter_review__目标受众.label'
  | 'catalog.material.kickstarter_review__目标受众.placeholder'
  | 'catalog.material.kickstarter_review__项目名称.label'
  | 'catalog.material.kickstarter_review__项目名称.placeholder'
  | 'catalog.material.localization_review__核心循环说明.label'
  | 'catalog.material.localization_review__核心循环说明.placeholder'
  | 'catalog.material.localization_review__游戏名称.label'
  | 'catalog.material.localization_review__游戏名称.placeholder'
  | 'catalog.material.localization_review__竞品对比.label'
  | 'catalog.material.localization_review__竞品对比.placeholder'
  | 'catalog.material.localization_review__系统说明.label'
  | 'catalog.material.localization_review__系统说明.placeholder'
  | 'catalog.material.looking_for_party_post__核心循环说明.label'
  | 'catalog.material.looking_for_party_post__核心循环说明.placeholder'
  | 'catalog.material.looking_for_party_post__游戏名称.label'
  | 'catalog.material.looking_for_party_post__游戏名称.placeholder'
  | 'catalog.material.looking_for_party_post__目标受众.label'
  | 'catalog.material.looking_for_party_post__目标受众.placeholder'
  | 'catalog.material.monetization_review__定价与平台.label'
  | 'catalog.material.monetization_review__定价与平台.placeholder'
  | 'catalog.material.monetization_review__核心循环说明.label'
  | 'catalog.material.monetization_review__核心循环说明.placeholder'
  | 'catalog.material.monetization_review__游戏名称.label'
  | 'catalog.material.monetization_review__游戏名称.placeholder'
  | 'catalog.material.monetization_review__竞品对比.label'
  | 'catalog.material.monetization_review__竞品对比.placeholder'
  | 'catalog.material.monetization_review__评价摘要.label'
  | 'catalog.material.monetization_review__评价摘要.placeholder'
  | 'catalog.material.onboarding_review__产品名称.label'
  | 'catalog.material.onboarding_review__产品名称.placeholder'
  | 'catalog.material.onboarding_review__截图.label'
  | 'catalog.material.onboarding_review__截图.placeholder'
  | 'catalog.material.onboarding_review__核心循环说明.label'
  | 'catalog.material.onboarding_review__核心循环说明.placeholder'
  | 'catalog.material.onboarding_review__目标受众.label'
  | 'catalog.material.onboarding_review__目标受众.placeholder'
  | 'catalog.material.onboarding_review__系统说明.label'
  | 'catalog.material.onboarding_review__系统说明.placeholder'
  | 'catalog.material.onboarding_review__评价摘要.label'
  | 'catalog.material.onboarding_review__评价摘要.placeholder'
  | 'catalog.material.pitch_review__一句话pitch.label'
  | 'catalog.material.pitch_review__一句话pitch.placeholder'
  | 'catalog.material.pitch_review__定价与平台.label'
  | 'catalog.material.pitch_review__定价与平台.placeholder'
  | 'catalog.material.pitch_review__核心循环说明.label'
  | 'catalog.material.pitch_review__核心循环说明.placeholder'
  | 'catalog.material.pitch_review__目标受众.label'
  | 'catalog.material.pitch_review__目标受众.placeholder'
  | 'catalog.material.pitch_review__竞品对比.label'
  | 'catalog.material.pitch_review__竞品对比.placeholder'
  | 'catalog.material.pitch_review__系统说明.label'
  | 'catalog.material.pitch_review__系统说明.placeholder'
  | 'catalog.material.pitch_review__项目名称.label'
  | 'catalog.material.pitch_review__项目名称.placeholder'
  | 'catalog.material.pricing_page_review__产品名称.label'
  | 'catalog.material.pricing_page_review__产品名称.placeholder'
  | 'catalog.material.pricing_page_review__定价与平台.label'
  | 'catalog.material.pricing_page_review__定价与平台.placeholder'
  | 'catalog.material.pricing_page_review__截图.label'
  | 'catalog.material.pricing_page_review__截图.placeholder'
  | 'catalog.material.pricing_page_review__核心循环说明.label'
  | 'catalog.material.pricing_page_review__核心循环说明.placeholder'
  | 'catalog.material.pricing_page_review__目标受众.label'
  | 'catalog.material.pricing_page_review__目标受众.placeholder'
  | 'catalog.material.pricing_page_review__竞品对比.label'
  | 'catalog.material.pricing_page_review__竞品对比.placeholder'
  | 'catalog.material.product_feedback_review__产品名称.label'
  | 'catalog.material.product_feedback_review__产品名称.placeholder'
  | 'catalog.material.product_feedback_review__截图.label'
  | 'catalog.material.product_feedback_review__截图.placeholder'
  | 'catalog.material.product_feedback_review__核心循环说明.label'
  | 'catalog.material.product_feedback_review__核心循环说明.placeholder'
  | 'catalog.material.product_feedback_review__目标受众.label'
  | 'catalog.material.product_feedback_review__目标受众.placeholder'
  | 'catalog.material.product_feedback_review__竞品对比.label'
  | 'catalog.material.product_feedback_review__竞品对比.placeholder'
  | 'catalog.material.product_feedback_review__评价摘要.label'
  | 'catalog.material.product_feedback_review__评价摘要.placeholder'
  | 'catalog.material.steam_page_review__demo.label'
  | 'catalog.material.steam_page_review__demo.placeholder'
  | 'catalog.material.steam_page_review__tags.label'
  | 'catalog.material.steam_page_review__tags.placeholder'
  | 'catalog.material.steam_page_review__价格.label'
  | 'catalog.material.steam_page_review__价格.placeholder'
  | 'catalog.material.steam_page_review__截图.label'
  | 'catalog.material.steam_page_review__截图.placeholder'
  | 'catalog.material.steam_page_review__核心循环说明.label'
  | 'catalog.material.steam_page_review__核心循环说明.placeholder'
  | 'catalog.material.steam_page_review__游戏名称.label'
  | 'catalog.material.steam_page_review__游戏名称.placeholder'
  | 'catalog.material.steam_page_review__评价摘要.label'
  | 'catalog.material.steam_page_review__评价摘要.placeholder'
  | 'catalog.material.update_announcement_review__截图.label'
  | 'catalog.material.update_announcement_review__截图.placeholder'
  | 'catalog.material.update_announcement_review__核心循环说明.label'
  | 'catalog.material.update_announcement_review__核心循环说明.placeholder'
  | 'catalog.material.update_announcement_review__游戏名称.label'
  | 'catalog.material.update_announcement_review__游戏名称.placeholder'
  | 'catalog.material.update_announcement_review__评价摘要.label'
  | 'catalog.material.update_announcement_review__评价摘要.placeholder'
  | 'catalog.mode.full.desc'
  | 'catalog.mode.quick.desc'
  | 'catalog.mode.standard.desc'
  | 'catalog.persona_pack.accessibility'
  | 'catalog.persona_pack.category_general'
  | 'catalog.persona_pack.category_platform'
  | 'catalog.persona_pack.category_player_type'
  | 'catalog.persona_pack.category_special'
  | 'catalog.persona_pack.competitive_esport'
  | 'catalog.persona_pack.educational_serious'
  | 'catalog.persona_pack.family_casual'
  | 'catalog.persona_pack.game_core'
  | 'catalog.persona_pack.general_consumer'
  | 'catalog.persona_pack.indie_creative'
  | 'catalog.persona_pack.launch_compliance'
  | 'catalog.persona_pack.mobile_f2p'
  | 'catalog.persona_pack.startup_panel'
  | 'catalog.persona_pack.vr_immersive'
  | 'catalog.skill.audience_panel.desc'
  | 'catalog.skill.audience_panel.label'
  | 'catalog.skill.persona_generate.desc'
  | 'catalog.skill.persona_generate.label'
  | 'catalog.skill.red_team_audience.desc'
  | 'catalog.skill.red_team_audience.label'
  | 'catalog.skill.synthetic_playtest.desc'
  | 'catalog.skill.synthetic_playtest.label'
  | 'catalog.task_type.concept_review.desc'
  | 'catalog.task_type.concept_review.label'
  | 'catalog.task_type.demo_first_play.desc'
  | 'catalog.task_type.demo_first_play.label'
  | 'catalog.task_type.devlog_review.desc'
  | 'catalog.task_type.devlog_review.label'
  | 'catalog.task_type.discord_community_review.desc'
  | 'catalog.task_type.discord_community_review.label'
  | 'catalog.task_type.kickstarter_review.desc'
  | 'catalog.task_type.kickstarter_review.label'
  | 'catalog.task_type.localization_review.desc'
  | 'catalog.task_type.localization_review.label'
  | 'catalog.task_type.looking_for_party_post.desc'
  | 'catalog.task_type.looking_for_party_post.label'
  | 'catalog.task_type.monetization_review.desc'
  | 'catalog.task_type.monetization_review.label'
  | 'catalog.task_type.onboarding_review.desc'
  | 'catalog.task_type.onboarding_review.label'
  | 'catalog.task_type.pitch_review.desc'
  | 'catalog.task_type.pitch_review.label'
  | 'catalog.task_type.pricing_page_review.desc'
  | 'catalog.task_type.pricing_page_review.label'
  | 'catalog.task_type.product_feedback_review.desc'
  | 'catalog.task_type.product_feedback_review.label'
  | 'catalog.task_type.steam_page_review.desc'
  | 'catalog.task_type.steam_page_review.label'
  | 'catalog.task_type.update_announcement_review.desc'
  | 'catalog.task_type.update_announcement_review.label'
  | 'common.action.back'
  | 'common.action.cancel'
  | 'common.action.clear'
  | 'common.action.close'
  | 'common.action.collapse'
  | 'common.action.confirm'
  | 'common.action.copy'
  | 'common.action.delete'
  | 'common.action.delete_account_phrase'
  | 'common.action.download'
  | 'common.action.edit'
  | 'common.action.expand'
  | 'common.action.load_more'
  | 'common.action.next'
  | 'common.action.prev'
  | 'common.action.refresh'
  | 'common.action.remove'
  | 'common.action.retry'
  | 'common.action.save'
  | 'common.action.share'
  | 'common.action.submit'
  | 'common.action.upload'
  | 'common.action.view_details'
  | 'common.calibration_gauge.missing.hint'
  | 'common.calibration_gauge.no_pass_line.hint'
  | 'common.calibration_gauge.readout.empty'
  | 'common.meta.description'
  | 'common.persona_radar.series_a.label'
  | 'common.persona_radar.series_b.label'
  | 'common.ui.copied'
  | 'common.ui.copy_failed'
  | 'common.ui.deleting'
  | 'common.ui.empty'
  | 'common.ui.error'
  | 'common.ui.language'
  | 'common.ui.language_aria'
  | 'common.ui.language_hint'
  | 'common.ui.loading'
  | 'common.ui.not_recorded'
  | 'common.ui.optional_mark'
  | 'common.ui.processing'
  | 'common.ui.required_mark'
  | 'common.ui.saving'
  | 'common.ui.sending'
  | 'common.ui.submitting'
  | 'common.ui.success'
  | 'common.ui.unknown_error'
  | 'common.validate.email_format'
  | 'common.validate.password_mismatch'
  | 'common.validate.required'
  | 'enum.behavior_axis.agency_preference'
  | 'enum.behavior_axis.completion_drive'
  | 'enum.behavior_axis.criticism_style'
  | 'enum.behavior_axis.emotional_engagement'
  | 'enum.behavior_axis.genre_literacy'
  | 'enum.behavior_axis.novelty_seeking'
  | 'enum.behavior_axis.patience'
  | 'enum.behavior_axis.platform_loyalty'
  | 'enum.behavior_axis.price_sensitivity'
  | 'enum.behavior_axis.risk_tolerance'
  | 'enum.behavior_axis.social_influence'
  | 'enum.behavior_axis.tolerance_for_ambiguity'
  | 'enum.calibration.coverage'
  | 'enum.calibration.hallucination'
  | 'enum.calibration.role_consistency'
  | 'enum.cross_exam_mode.derived_summary.desc'
  | 'enum.cross_exam_mode.derived_summary.label'
  | 'enum.cross_exam_mode.moderated_rebuttal.desc'
  | 'enum.cross_exam_mode.moderated_rebuttal.label'
  | 'enum.cross_exam_mode.multi_agent_rebuttal.desc'
  | 'enum.cross_exam_mode.multi_agent_rebuttal.label'
  | 'enum.direction.decrease'
  | 'enum.direction.increase'
  | 'enum.disabled_reason.explicit_persona_selection'
  | 'enum.ethics_severity.high'
  | 'enum.ethics_severity.low'
  | 'enum.ethics_severity.medium'
  | 'enum.evidence_quality.insufficient'
  | 'enum.evidence_quality.medium'
  | 'enum.evidence_quality.strong'
  | 'enum.evidence_quality.weak'
  | 'enum.gate_reason.hallucination'
  | 'enum.gate_reason.role_drift'
  | 'enum.gate_reason.schema_failure'
  | 'enum.mode_badge.full'
  | 'enum.mode_badge.quick'
  | 'enum.mode_badge.standard'
  | 'enum.persona_status.completed'
  | 'enum.persona_status.failed'
  | 'enum.persona_status.pending'
  | 'enum.persona_status.running'
  | 'enum.primary_stance.advocate'
  | 'enum.primary_stance.blocker'
  | 'enum.primary_stance.neutral'
  | 'enum.primary_stance.skeptic'
  | 'enum.rebuttal_status.failed'
  | 'enum.rebuttal_status.ok'
  | 'enum.rebuttal_status.partial'
  | 'enum.rebuttal_status.skipped'
  | 'enum.release_risk.critical'
  | 'enum.release_risk.high'
  | 'enum.release_risk.low'
  | 'enum.release_risk.medium'
  | 'enum.review_status.cancelled'
  | 'enum.review_status.completed'
  | 'enum.review_status.failed'
  | 'enum.review_status.pending'
  | 'enum.review_status.running'
  | 'enum.severity.critical'
  | 'enum.severity.high'
  | 'enum.severity.low'
  | 'enum.severity.medium'
  | 'enum.stereotype_risk.high'
  | 'enum.stereotype_risk.low'
  | 'enum.stereotype_risk.medium'
  | 'enum.stereotype_risk.unknown'
  | 'enum.stop_reason.cost_budget_reached'
  | 'enum.stop_reason.marginal_value_below_threshold'
  | 'enum.verdict.fail'
  | 'enum.verdict.pass'
  | 'error.api.admin_disabled'
  | 'error.api.bad_request'
  | 'error.api.forbidden'
  | 'error.api.internal_error'
  | 'error.api.llm_key_missing'
  | 'error.api.not_found'
  | 'error.api.quota_exceeded'
  | 'error.api.rate_limited'
  | 'error.api.unauthorized'
  | 'error.api.upstream_error'
  | 'error.fetch.delete_review'
  | 'error.fetch.ethics'
  | 'error.fetch.evaluation'
  | 'error.fetch.examples'
  | 'error.fetch.extract_materials'
  | 'error.fetch.persona_packs'
  | 'error.fetch.personas'
  | 'error.fetch.report'
  | 'error.fetch.review'
  | 'error.fetch.review_list'
  | 'error.fetch.review_modes'
  | 'error.fetch.review_result'
  | 'error.fetch.run_evaluation'
  | 'error.fetch.separator'
  | 'error.fetch.skills'
  | 'error.fetch.task_types'
  | 'error.store.bootstrap'
  | 'error.store.examples'
  | 'error.store.personas'
  | 'error.store.review_list'
  | 'error.ws.closed'
  | 'error.ws.give_up'
  | 'error.ws.unavailable'
  | 'nav.account.guest'
  | 'nav.account.login'
  | 'nav.account.logout'
  | 'nav.account.menu_aria'
  | 'nav.account.settings'
  | 'nav.footer.icp_aria'
  | 'nav.footer.privacy'
  | 'nav.footer.tagline'
  | 'nav.footer.terms'
  | 'nav.item.ask'
  | 'nav.item.create_review'
  | 'nav.item.history'
  | 'nav.item.home'
  | 'nav.item.ledger'
  | 'nav.item.personas'
  | 'nav.item.plans'
  | 'nav.item.settings'
  | 'nav.item.skills'
  | 'nav.item.task_types'
  | 'nav.item.tutorial'
  | 'nav.menu.drawer_aria'
  | 'nav.menu.toggle_aria'
  | 'nav.session.cta'
  | 'nav.session.dismiss_aria'
  | 'nav.session.expired'
  | 'nav.verify_banner.cta'
  | 'nav.verify_banner.error'
  | 'nav.verify_banner.hint_unknown'
  | 'nav.verify_banner.sending'
  | 'nav.verify_banner.success'
  | 'page.ask.attach.hint'
  | 'page.ask.attachment_preview.tooltip'
  | 'page.ask.clarify.hint'
  | 'page.ask.conclusion.title'
  | 'page.ask.confidence.label'
  | 'page.ask.confidence_high.label'
  | 'page.ask.confidence_low.label'
  | 'page.ask.confidence_medium.label'
  | 'page.ask.confirm.label'
  | 'page.ask.conversation_move.error'
  | 'page.ask.conversation_untitled.label'
  | 'page.ask.create.error'
  | 'page.ask.drop.hint'
  | 'page.ask.example_onboarding.value'
  | 'page.ask.example_pitch.value'
  | 'page.ask.example_pricing.value'
  | 'page.ask.examples.cta'
  | 'page.ask.examples.hint'
  | 'page.ask.examples.title'
  | 'page.ask.follow_up.cta'
  | 'page.ask.follow_up.error'
  | 'page.ask.follow_up.label'
  | 'page.ask.follow_up.tooltip'
  | 'page.ask.follow_up_exit.aria'
  | 'page.ask.follow_up_report.cta'
  | 'page.ask.gated.cta'
  | 'page.ask.greeting.value'
  | 'page.ask.header.desc'
  | 'page.ask.header.title'
  | 'page.ask.history.error'
  | 'page.ask.history_delete.hint'
  | 'page.ask.input.aria'
  | 'page.ask.input.placeholder'
  | 'page.ask.legacy.title'
  | 'page.ask.login_required.cta'
  | 'page.ask.login_required.desc'
  | 'page.ask.login_required.title'
  | 'page.ask.meta.title'
  | 'page.ask.need_key.cta'
  | 'page.ask.new_conversation.cta'
  | 'page.ask.new_project.confirm'
  | 'page.ask.new_project.cta'
  | 'page.ask.new_project.placeholder'
  | 'page.ask.no_key.cta'
  | 'page.ask.no_key.desc'
  | 'page.ask.no_key.title'
  | 'page.ask.parse.error'
  | 'page.ask.persisted_confirm.empty'
  | 'page.ask.persisted_review.value'
  | 'page.ask.persona_chat.cta'
  | 'page.ask.persona_remove.tooltip'
  | 'page.ask.persona_restore.tooltip'
  | 'page.ask.personas.label'
  | 'page.ask.pinned_project.aria'
  | 'page.ask.pinned_project.tooltip'
  | 'page.ask.pinned_skill.aria'
  | 'page.ask.pinned_type.aria'
  | 'page.ask.preview_close.aria'
  | 'page.ask.progress.hint'
  | 'page.ask.progress.pending'
  | 'page.ask.project.empty'
  | 'page.ask.project_create.error'
  | 'page.ask.project_delete.error'
  | 'page.ask.project_delete.tooltip'
  | 'page.ask.project_delete_confirm.cta'
  | 'page.ask.project_rename.error'
  | 'page.ask.project_rename.tooltip'
  | 'page.ask.project_select.aria'
  | 'page.ask.project_select.empty'
  | 'page.ask.project_select.placeholder'
  | 'page.ask.projects.loading'
  | 'page.ask.realtime_reconnecting.hint'
  | 'page.ask.report_card.cta'
  | 'page.ask.report_card.empty'
  | 'page.ask.report_card.loading'
  | 'page.ask.report_card.title'
  | 'page.ask.report_modal.subtitle'
  | 'page.ask.restored_review.label'
  | 'page.ask.review_delete.tooltip'
  | 'page.ask.review_failed.error'
  | 'page.ask.review_failed.title'
  | 'page.ask.rule_parse.hint'
  | 'page.ask.send.aria'
  | 'page.ask.sidebar_collapse.aria'
  | 'page.ask.sidebar_collapse.tooltip'
  | 'page.ask.sidebar_empty.desc'
  | 'page.ask.sidebar_empty.title'
  | 'page.ask.sidebar_expand.aria'
  | 'page.ask.sidebar_expand.tooltip'
  | 'page.ask.skill_picker.aria'
  | 'page.ask.skill_picker.tooltip'
  | 'page.ask.skill_quota.empty'
  | 'page.ask.skill_quota.hint'
  | 'page.ask.stance.empty'
  | 'page.ask.stance_row.empty'
  | 'page.ask.submit.cta'
  | 'page.ask.submit.pending'
  | 'page.ask.type_picker.aria'
  | 'page.ask.type_picker.placeholder'
  | 'page.ask.type_picker.tooltip'
  | 'page.ask.ungrouped.empty'
  | 'page.ask.ungrouped.title'
  | 'page.ask.upload.aria'
  | 'page.ask.upload.tooltip'
  | 'page.create.category_all.tab'
  | 'page.create.confirm.desc'
  | 'page.create.confirm.title'
  | 'page.create.confirm_extra.title'
  | 'page.create.confirm_extra_evaluation.badge'
  | 'page.create.confirm_extra_red_team.badge'
  | 'page.create.confirm_field.empty'
  | 'page.create.confirm_material.title'
  | 'page.create.confirm_mode.title'
  | 'page.create.confirm_skill.title'
  | 'page.create.confirm_target.empty'
  | 'page.create.confirm_target.title'
  | 'page.create.confirm_task_type.title'
  | 'page.create.cost.desc'
  | 'page.create.cost.title'
  | 'page.create.dropped_skill.desc'
  | 'page.create.dropzone.cta'
  | 'page.create.dropzone.hint'
  | 'page.create.evaluation.label'
  | 'page.create.examples.cta'
  | 'page.create.extra_fields_unknown.label'
  | 'page.create.extract.hint'
  | 'page.create.extract.pending'
  | 'page.create.extract_reason_unknown.error'
  | 'page.create.feature_calibration.badge'
  | 'page.create.feature_cross_exam.badge'
  | 'page.create.feature_none.badge'
  | 'page.create.fields.title'
  | 'page.create.generic_field.label'
  | 'page.create.generic_field.placeholder'
  | 'page.create.input_mode_file.tab'
  | 'page.create.input_mode_text.tab'
  | 'page.create.launch.cta'
  | 'page.create.launch.error'
  | 'page.create.launch_no_material.error'
  | 'page.create.launch_pack_mismatch.error'
  | 'page.create.material.desc'
  | 'page.create.material.title'
  | 'page.create.meta.title'
  | 'page.create.mode.title'
  | 'page.create.mode_summary.title'
  | 'page.create.option.desc'
  | 'page.create.option.title'
  | 'page.create.pack_conflict.desc'
  | 'page.create.pack_conflict.value'
  | 'page.create.persona.desc'
  | 'page.create.persona.title'
  | 'page.create.persona_list.title'
  | 'page.create.red_team.desc'
  | 'page.create.red_team.label'
  | 'page.create.red_team_case_community.badge'
  | 'page.create.red_team_case_localization.badge'
  | 'page.create.red_team_case_pr.badge'
  | 'page.create.red_team_case_pricing.badge'
  | 'page.create.skill.desc'
  | 'page.create.skill.title'
  | 'page.create.skill_error.cta'
  | 'page.create.skill_error.title'
  | 'page.create.skill_list.empty'
  | 'page.create.skill_list.error'
  | 'page.create.stage.confirm'
  | 'page.create.stage.material'
  | 'page.create.stage.option'
  | 'page.create.stage.persona'
  | 'page.create.stage.skill'
  | 'page.create.stage.task_type'
  | 'page.create.target.label'
  | 'page.create.target.placeholder'
  | 'page.create.task_type.desc'
  | 'page.create.task_type.title'
  | 'page.evaluation.back.cta'
  | 'page.evaluation.completed.label'
  | 'page.evaluation.created.label'
  | 'page.evaluation.critical.title'
  | 'page.evaluation.dimension.hint'
  | 'page.evaluation.dimensions.title'
  | 'page.evaluation.ethics.title'
  | 'page.evaluation.ethics_score.label'
  | 'page.evaluation.header.aria'
  | 'page.evaluation.header.loading'
  | 'page.evaluation.header.title'
  | 'page.evaluation.load_error.title'
  | 'page.evaluation.meta.title'
  | 'page.evaluation.not_generated.desc'
  | 'page.evaluation.not_generated.title'
  | 'page.evaluation.overall.hint'
  | 'page.evaluation.overall.title'
  | 'page.evaluation.radar.label'
  | 'page.evaluation.radar.title'
  | 'page.evaluation.score.label'
  | 'page.evaluation.skill.label'
  | 'page.evaluation.state.fail'
  | 'page.evaluation.state.overall_fail'
  | 'page.evaluation.state.overall_pass'
  | 'page.evaluation.state.pass'
  | 'page.evaluation.stereotype.label'
  | 'page.evaluation.time.empty'
  | 'page.evaluation.timeline.title'
  | 'page.forgot.email.label'
  | 'page.forgot.email.placeholder'
  | 'page.forgot.header.desc'
  | 'page.forgot.header.title'
  | 'page.forgot.meta.title'
  | 'page.forgot.sent.hint'
  | 'page.forgot.sent.link'
  | 'page.forgot.sent.success'
  | 'page.forgot.signin.hint'
  | 'page.forgot.submit.cta'
  | 'page.forgot.submit.error'
  | 'page.history.delete.error'
  | 'page.history.header.desc'
  | 'page.history.header.title'
  | 'page.history.item.tooltip'
  | 'page.history.list_empty.cta'
  | 'page.history.list_empty.title'
  | 'page.history.load.error'
  | 'page.history.load_error.desc'
  | 'page.history.load_error.title'
  | 'page.history.load_more.cta'
  | 'page.history.load_more.error'
  | 'page.history.meta.title'
  | 'page.landing.meta.title'
  | 'page.ledger.adoption.label'
  | 'page.ledger.avg_model_cost.label'
  | 'page.ledger.avg_willingness.label'
  | 'page.ledger.bins.title'
  | 'page.ledger.brier.hint'
  | 'page.ledger.brier.label'
  | 'page.ledger.by_task_type.title'
  | 'page.ledger.calibration.desc'
  | 'page.ledger.calibration.hint'
  | 'page.ledger.calibration.title'
  | 'page.ledger.cost_per_adopted.label'
  | 'page.ledger.cost_per_useful.label'
  | 'page.ledger.decision_change.label'
  | 'page.ledger.ece.hint'
  | 'page.ledger.ece.label'
  | 'page.ledger.error.cta'
  | 'page.ledger.error.hint'
  | 'page.ledger.error.pending'
  | 'page.ledger.error.title'
  | 'page.ledger.feedback_coverage.label'
  | 'page.ledger.header.desc'
  | 'page.ledger.header.title'
  | 'page.ledger.hit_rate.label'
  | 'page.ledger.hours_saved.label'
  | 'page.ledger.leaderboard.title'
  | 'page.ledger.list.error'
  | 'page.ledger.list.label'
  | 'page.ledger.list.title'
  | 'page.ledger.list_empty.desc'
  | 'page.ledger.list_empty.title'
  | 'page.ledger.mean_confidence.label'
  | 'page.ledger.meta.title'
  | 'page.ledger.observed_hit.hint'
  | 'page.ledger.observed_hit.label'
  | 'page.ledger.panel.label'
  | 'page.ledger.pending_verification.label'
  | 'page.ledger.stat.empty'
  | 'page.ledger.state.hit'
  | 'page.ledger.state.miss'
  | 'page.ledger.state.partial'
  | 'page.ledger.state.unknown'
  | 'page.ledger.top_fixes.title'
  | 'page.ledger.total_judgments.label'
  | 'page.ledger.useful_rate.label'
  | 'page.ledger.value.title'
  | 'page.ledger.verified.label'
  | 'page.ledger.verify_error.cta'
  | 'page.ledger.verify_error.title'
  | 'page.login.email.label'
  | 'page.login.email.placeholder'
  | 'page.login.forgot.link'
  | 'page.login.header.desc'
  | 'page.login.header.title'
  | 'page.login.meta.title'
  | 'page.login.password.label'
  | 'page.login.password.placeholder'
  | 'page.login.signup.hint'
  | 'page.login.submit.cta'
  | 'page.login.submit.error'
  | 'page.login.submit.pending'
  | 'page.personas.compare.label'
  | 'page.personas.compare.title'
  | 'page.personas.compare_enter'
  | 'page.personas.compare_exit'
  | 'page.personas.filter.cta'
  | 'page.personas.filter.title'
  | 'page.personas.filter_all'
  | 'page.personas.header.title'
  | 'page.personas.list.pending'
  | 'page.personas.list_empty.cta'
  | 'page.personas.list_empty.desc'
  | 'page.personas.list_empty.title'
  | 'page.personas.meta.title'
  | 'page.personas.pack_unknown'
  | 'page.personas.rules.title'
  | 'page.personas.search.placeholder'
  | 'page.personas.triggers.title'
  | 'page.plans.anon.hint'
  | 'page.plans.banner_byok'
  | 'page.plans.banner_credits'
  | 'page.plans.banner_no_quota'
  | 'page.plans.bonus.label'
  | 'page.plans.byok.cta'
  | 'page.plans.byok.desc'
  | 'page.plans.byok.title'
  | 'page.plans.card.badge'
  | 'page.plans.card.cta'
  | 'page.plans.card.hint'
  | 'page.plans.card.label'
  | 'page.plans.cdk.aria'
  | 'page.plans.cdk.cta'
  | 'page.plans.cdk.error'
  | 'page.plans.cdk.hint'
  | 'page.plans.cdk.placeholder'
  | 'page.plans.cdk.title'
  | 'page.plans.cdk_desc_credits'
  | 'page.plans.cdk_desc_plan'
  | 'page.plans.credits.label'
  | 'page.plans.feature_byok'
  | 'page.plans.feature_cost'
  | 'page.plans.guest.hint'
  | 'page.plans.header.desc'
  | 'page.plans.header.title'
  | 'page.plans.list.error'
  | 'page.plans.list.pending'
  | 'page.plans.list.title'
  | 'page.plans.manual.desc'
  | 'page.plans.manual.title'
  | 'page.plans.meta.title'
  | 'page.plans.price.unit'
  | 'page.plans.progress.label'
  | 'page.plans.quota.error'
  | 'page.plans.quota.pending'
  | 'page.plans.quota.title'
  | 'page.plans.tagline_free'
  | 'page.plans.tagline_pro'
  | 'page.plans.tagline_team'
  | 'page.plans.tier.label'
  | 'page.plans.used.label'
  | 'page.privacy.collect.badge'
  | 'page.privacy.collection.title'
  | 'page.privacy.collection_apikey.label'
  | 'page.privacy.collection_apikey_delete.desc'
  | 'page.privacy.collection_apikey_encrypted.desc'
  | 'page.privacy.collection_apikey_masked.desc'
  | 'page.privacy.collection_apikey_separate.desc'
  | 'page.privacy.collection_collected.label'
  | 'page.privacy.collection_collected_account.desc'
  | 'page.privacy.collection_collected_chat.desc'
  | 'page.privacy.collection_collected_config.desc'
  | 'page.privacy.collection_collected_images.desc'
  | 'page.privacy.collection_collected_materials.desc'
  | 'page.privacy.collection_collected_report.desc'
  | 'page.privacy.collection_collected_usage.desc'
  | 'page.privacy.collection_not.label'
  | 'page.privacy.collection_not_fingerprint.desc'
  | 'page.privacy.collection_not_history.desc'
  | 'page.privacy.collection_not_identity.desc'
  | 'page.privacy.contact.desc'
  | 'page.privacy.contact.title'
  | 'page.privacy.footer.desc'
  | 'page.privacy.header.link'
  | 'page.privacy.header.meta'
  | 'page.privacy.header.subtitle'
  | 'page.privacy.header.title'
  | 'page.privacy.key.badge'
  | 'page.privacy.meta.title'
  | 'page.privacy.no_collect.badge'
  | 'page.privacy.retention.badge'
  | 'page.privacy.retention.title'
  | 'page.privacy.retention_policy.label'
  | 'page.privacy.retention_policy_delete.desc'
  | 'page.privacy.retention_policy_exception.desc'
  | 'page.privacy.retention_policy_export.desc'
  | 'page.privacy.retention_policy_forever.desc'
  | 'page.privacy.security.badge'
  | 'page.privacy.security.title'
  | 'page.privacy.security_tech.label'
  | 'page.privacy.security_tech_cors.desc'
  | 'page.privacy.security_tech_key.desc'
  | 'page.privacy.security_tech_password.desc'
  | 'page.privacy.security_tech_token.desc'
  | 'page.privacy.security_tech_upload.desc'
  | 'page.privacy.third_party.badge'
  | 'page.privacy.third_party.title'
  | 'page.privacy.third_party_llm.label'
  | 'page.privacy.third_party_llm_ollama.desc'
  | 'page.privacy.third_party_llm_only.desc'
  | 'page.privacy.third_party_llm_providers.desc'
  | 'page.privacy.third_party_llm_scope.desc'
  | 'page.privacy.third_party_providers.label'
  | 'page.privacy.usage.title'
  | 'page.privacy.usage_admin.label'
  | 'page.privacy.usage_admin_access.desc'
  | 'page.privacy.usage_admin_audit.desc'
  | 'page.privacy.usage_admin_unchanged.desc'
  | 'page.privacy.usage_never.label'
  | 'page.privacy.usage_never_copy.desc'
  | 'page.privacy.usage_never_showcase.desc'
  | 'page.privacy.usage_never_training.desc'
  | 'page.privacy.usage_purpose.label'
  | 'page.privacy.usage_purpose_isolated.desc'
  | 'page.privacy.usage_purpose_retained.desc'
  | 'page.privacy.usage_purpose_single.desc'
  | 'page.privacy.use.badge'
  | 'page.privacy.verify.badge'
  | 'page.privacy.verify.title'
  | 'page.privacy.verify_checkable.label'
  | 'page.privacy.verify_checkable_byok.desc'
  | 'page.privacy.verify_checkable_export.desc'
  | 'page.privacy.verify_checkable_hosted.desc'
  | 'page.privacy.verify_checkable_oss.desc'
  | 'page.privacy.verify_checkable_selfhost.desc'
  | 'page.progress.aggregation.title'
  | 'page.progress.back.cta'
  | 'page.progress.cost.label'
  | 'page.progress.cross_exam.title'
  | 'page.progress.done.cta'
  | 'page.progress.done.title'
  | 'page.progress.failed.cta'
  | 'page.progress.failed.desc'
  | 'page.progress.failed.title'
  | 'page.progress.header.subtitle'
  | 'page.progress.header.title'
  | 'page.progress.load_error.desc'
  | 'page.progress.load_error.title'
  | 'page.progress.meta.title'
  | 'page.progress.not_found.empty'
  | 'page.progress.overall.label'
  | 'page.progress.persona_count.label'
  | 'page.progress.persona_done.badge'
  | 'page.progress.persona_failed.error'
  | 'page.progress.personas.empty'
  | 'page.progress.personas.pending'
  | 'page.progress.personas.title'
  | 'page.progress.report.cta'
  | 'page.progress.running_card.pending'
  | 'page.progress.running_card.title'
  | 'page.progress.skill.label'
  | 'page.progress.stage.completed'
  | 'page.progress.stage.running'
  | 'page.progress.stage.waiting'
  | 'page.progress.status.label'
  | 'page.progress.ws_reconnect.hint'
  | 'page.register.email.label'
  | 'page.register.email.placeholder'
  | 'page.register.header.desc'
  | 'page.register.header.title'
  | 'page.register.meta.title'
  | 'page.register.name.label'
  | 'page.register.name.placeholder'
  | 'page.register.password.placeholder'
  | 'page.register.signin.hint'
  | 'page.register.submit.cta'
  | 'page.register.submit.error'
  | 'page.register.submit.pending'
  | 'page.register.terms.consent'
  | 'page.report.adaptive.empty'
  | 'page.report.adaptive.hint'
  | 'page.report.adaptive.title'
  | 'page.report.adaptive_executed.label'
  | 'page.report.adaptive_initial.label'
  | 'page.report.adaptive_saved.label'
  | 'page.report.adaptive_step.hint'
  | 'page.report.adaptive_stop.label'
  | 'page.report.argument.empty'
  | 'page.report.argument.label'
  | 'page.report.argument_con.label'
  | 'page.report.argument_pro.label'
  | 'page.report.body.loading'
  | 'page.report.budget.hint'
  | 'page.report.budget.title'
  | 'page.report.budget_generic.desc'
  | 'page.report.calibration.empty'
  | 'page.report.calibration.error'
  | 'page.report.calibration.success'
  | 'page.report.calibration.title'
  | 'page.report.change.empty'
  | 'page.report.compliance.title'
  | 'page.report.confidence.title'
  | 'page.report.consensus.badge'
  | 'page.report.consensus.title'
  | 'page.report.consensus_single.badge'
  | 'page.report.consensus_unknown.meta'
  | 'page.report.cross_exam.title'
  | 'page.report.cross_exam_absent.desc'
  | 'page.report.cross_exam_failures.empty'
  | 'page.report.cross_exam_failures.label'
  | 'page.report.cross_exam_limitation.label'
  | 'page.report.cross_exam_mode_unknown.desc'
  | 'page.report.cross_exam_mode_unknown.label'
  | 'page.report.cross_exam_skipped.desc'
  | 'page.report.disagreements.title'
  | 'page.report.dispute.empty'
  | 'page.report.dispute_empty.desc'
  | 'page.report.dispute_empty.hint'
  | 'page.report.ethics.title'
  | 'page.report.ethics_score.label'
  | 'page.report.ethics_stereotype.label'
  | 'page.report.evaluation.cta'
  | 'page.report.evaluation.error'
  | 'page.report.evaluation.title'
  | 'page.report.evaluation_critical.title'
  | 'page.report.evaluation_dimension.empty'
  | 'page.report.evaluation_dimension.label'
  | 'page.report.evaluation_full.cta'
  | 'page.report.evaluation_overall.label'
  | 'page.report.failed.desc'
  | 'page.report.failed.empty'
  | 'page.report.failed.hint'
  | 'page.report.failed.title'
  | 'page.report.feedback.cta'
  | 'page.report.feedback.desc'
  | 'page.report.feedback.error'
  | 'page.report.feedback.title'
  | 'page.report.feedback_adopted.label'
  | 'page.report.feedback_decision.label'
  | 'page.report.feedback_hours.label'
  | 'page.report.feedback_pay.label'
  | 'page.report.feedback_useful.cta'
  | 'page.report.feedback_useless.cta'
  | 'page.report.fix_personas.label'
  | 'page.report.fix_suggestion.label'
  | 'page.report.fix_why.label'
  | 'page.report.fixes.title'
  | 'page.report.gaps.title'
  | 'page.report.gate.empty'
  | 'page.report.gated.cta'
  | 'page.report.gated.desc'
  | 'page.report.gated.subtitle'
  | 'page.report.gated_fix.title'
  | 'page.report.gated_recommendation.label'
  | 'page.report.gated_risk.label'
  | 'page.report.gated_summary.title'
  | 'page.report.header.subtitle'
  | 'page.report.header.title'
  | 'page.report.html.aria'
  | 'page.report.html.cta'
  | 'page.report.html.empty'
  | 'page.report.html.tooltip'
  | 'page.report.limitation_demographic'
  | 'page.report.limitation_feedback_loop'
  | 'page.report.limitation_materials'
  | 'page.report.limitation_synthetic'
  | 'page.report.limitation_variance'
  | 'page.report.limitations.title'
  | 'page.report.link_detail.cta'
  | 'page.report.link_login.cta'
  | 'page.report.link_new_review.cta'
  | 'page.report.load_error.desc'
  | 'page.report.load_error.title'
  | 'page.report.md_banner.desc'
  | 'page.report.md_budget.hint'
  | 'page.report.md_cross_exam.empty'
  | 'page.report.md_cross_exam_absent.desc'
  | 'page.report.md_cross_exam_legacy.desc'
  | 'page.report.md_cross_exam_skipped.desc'
  | 'page.report.md_fix.label'
  | 'page.report.md_lang.empty'
  | 'page.report.md_lang_en.value'
  | 'page.report.md_lang_zh.value'
  | 'page.report.md_risk.empty'
  | 'page.report.md_vote.empty'
  | 'page.report.meta.title'
  | 'page.report.next_test.title'
  | 'page.report.next_test_audience.label'
  | 'page.report.next_test_materials.label'
  | 'page.report.next_test_tasks.label'
  | 'page.report.panel_selection.title'
  | 'page.report.pending.cta'
  | 'page.report.pending.desc'
  | 'page.report.pending.title'
  | 'page.report.persona_evidence.label'
  | 'page.report.persona_issues.label'
  | 'page.report.personas.title'
  | 'page.report.prediction_criterion.label'
  | 'page.report.prediction_method.label'
  | 'page.report.prediction_metric.label'
  | 'page.report.prediction_window.label'
  | 'page.report.predictions.desc'
  | 'page.report.predictions.title'
  | 'page.report.sep_colon'
  | 'page.report.sep_enum'
  | 'page.report.sep_semicolon'
  | 'page.report.share.aria'
  | 'page.report.share.badge'
  | 'page.report.share.cta'
  | 'page.report.share.desc'
  | 'page.report.share.error'
  | 'page.report.share.hint'
  | 'page.report.share.title'
  | 'page.report.share_copy.error'
  | 'page.report.share_create.cta'
  | 'page.report.share_hidden.label'
  | 'page.report.share_item_account.label'
  | 'page.report.share_item_calibration.label'
  | 'page.report.share_item_cost.label'
  | 'page.report.share_item_material.label'
  | 'page.report.share_item_meta.label'
  | 'page.report.share_item_report.label'
  | 'page.report.share_revoke.cta'
  | 'page.report.share_revoke.error'
  | 'page.report.share_visible.label'
  | 'page.report.stance.empty'
  | 'page.report.stance.value'
  | 'page.report.summary_consensus.label'
  | 'page.report.summary_evidence.label'
  | 'page.report.summary_risk_absent.desc'
  | 'page.report.summary_stance.label'
  | 'page.report.synthetic_banner.desc'
  | 'page.report.synthetic_banner.title'
  | 'page.report.usage.hint'
  | 'page.report.vote.empty'
  | 'page.report.vote.title'
  | 'page.report.vote_unchanged.desc'
  | 'page.reset.confirm.label'
  | 'page.reset.confirm.placeholder'
  | 'page.reset.done.cta'
  | 'page.reset.done.hint'
  | 'page.reset.done.success'
  | 'page.reset.header.title'
  | 'page.reset.meta.title'
  | 'page.reset.no_token.error'
  | 'page.reset.no_token.link'
  | 'page.reset.password.placeholder'
  | 'page.reset.submit.cta'
  | 'page.reset.submit.error'
  | 'page.settings.account_card.title'
  | 'page.settings.api_base.hint'
  | 'page.settings.api_base.label'
  | 'page.settings.api_base.placeholder'
  | 'page.settings.api_base_compat.placeholder'
  | 'page.settings.byok.desc'
  | 'page.settings.byok.error'
  | 'page.settings.byok.hint'
  | 'page.settings.byok.title'
  | 'page.settings.cdk.cta'
  | 'page.settings.cdk.desc'
  | 'page.settings.cdk.error'
  | 'page.settings.cdk.hint'
  | 'page.settings.cdk.placeholder'
  | 'page.settings.cdk.title'
  | 'page.settings.cdk_guest.hint'
  | 'page.settings.cdk_plan.desc'
  | 'page.settings.data.desc'
  | 'page.settings.data.title'
  | 'page.settings.delete_account.cta'
  | 'page.settings.delete_account.error'
  | 'page.settings.delete_confirm.cta'
  | 'page.settings.delete_confirm.desc'
  | 'page.settings.delete_done.hint'
  | 'page.settings.delete_password.label'
  | 'page.settings.export.cta'
  | 'page.settings.export.error'
  | 'page.settings.footer.link'
  | 'page.settings.group_account.label'
  | 'page.settings.group_data.label'
  | 'page.settings.group_model.label'
  | 'page.settings.group_usage.label'
  | 'page.settings.guest_card.cta'
  | 'page.settings.guest_card.desc'
  | 'page.settings.guest_card.title'
  | 'page.settings.header.desc'
  | 'page.settings.header.title'
  | 'page.settings.key_input.aria'
  | 'page.settings.key_input.placeholder'
  | 'page.settings.key_input_compat.placeholder'
  | 'page.settings.key_item.error'
  | 'page.settings.key_privacy.title'
  | 'page.settings.meta.title'
  | 'page.settings.model_id.error'
  | 'page.settings.model_id.hint'
  | 'page.settings.model_id.label'
  | 'page.settings.model_id.placeholder'
  | 'page.settings.model_id_compat.placeholder'
  | 'page.settings.multimodal.desc'
  | 'page.settings.name.error'
  | 'page.settings.name.hint'
  | 'page.settings.name.label'
  | 'page.settings.name.placeholder'
  | 'page.settings.name.success'
  | 'page.settings.password.cta'
  | 'page.settings.password.error'
  | 'page.settings.password.hint'
  | 'page.settings.password.label'
  | 'page.settings.password.success'
  | 'page.settings.password_confirm.placeholder'
  | 'page.settings.password_current.placeholder'
  | 'page.settings.password_new.placeholder'
  | 'page.settings.privacy_device.desc'
  | 'page.settings.privacy_device.label'
  | 'page.settings.privacy_optout.desc'
  | 'page.settings.privacy_optout.hint'
  | 'page.settings.privacy_optout.label'
  | 'page.settings.privacy_selfhost.desc'
  | 'page.settings.privacy_source.desc'
  | 'page.settings.privacy_use.desc'
  | 'page.settings.privacy_use.label'
  | 'page.settings.privacy_who.desc'
  | 'page.settings.privacy_who.label'
  | 'page.settings.provider_anthropic.desc'
  | 'page.settings.provider_anthropic.label'
  | 'page.settings.provider_openai.desc'
  | 'page.settings.provider_openai.label'
  | 'page.settings.revoke.confirm'
  | 'page.settings.revoke.cta'
  | 'page.settings.revoke.desc'
  | 'page.settings.revoke.hint'
  | 'page.settings.revoke.label'
  | 'page.settings.save_key.cta'
  | 'page.settings.save_key.error'
  | 'page.settings.save_key.success'
  | 'page.settings.section_account.desc'
  | 'page.settings.section_account.tab'
  | 'page.settings.section_account.title'
  | 'page.settings.section_account_guest.desc'
  | 'page.settings.section_data.desc'
  | 'page.settings.section_data.tab'
  | 'page.settings.section_data.title'
  | 'page.settings.section_model.desc'
  | 'page.settings.section_model.tab'
  | 'page.settings.section_model.title'
  | 'page.settings.section_usage.desc'
  | 'page.settings.section_usage.tab'
  | 'page.settings.section_usage.title'
  | 'page.settings.test.cta'
  | 'page.settings.test.error'
  | 'page.settings.test.success'
  | 'page.settings.usage.title'
  | 'page.settings.usage_bonus.label'
  | 'page.settings.usage_cost.label'
  | 'page.settings.usage_credits.label'
  | 'page.settings.usage_credits.unit'
  | 'page.settings.usage_reviews.label'
  | 'page.settings.usage_server_cost.label'
  | 'page.settings.usage_tokens.label'
  | 'page.settings.usage_tokens.unit'
  | 'page.shared.agreed.title'
  | 'page.shared.footer.cta'
  | 'page.shared.footer.desc'
  | 'page.shared.gaps.title'
  | 'page.shared.header.title'
  | 'page.shared.load_error.desc'
  | 'page.shared.load_error.title'
  | 'page.shared.meta.title'
  | 'page.shared.questioned.title'
  | 'page.shared.revoked.cta'
  | 'page.shared.revoked.desc'
  | 'page.shared.revoked.title'
  | 'page.shared.share_note.badge'
  | 'page.shared.summary.title'
  | 'page.skills.card.cta'
  | 'page.skills.card_disabled.hint'
  | 'page.skills.card_use_cases.label'
  | 'page.skills.header.subtitle'
  | 'page.skills.header.title'
  | 'page.skills.list.empty'
  | 'page.skills.list_error.cta'
  | 'page.skills.list_error.title'
  | 'page.skills.meta.title'
  | 'page.task_types.card.cta'
  | 'page.task_types.card_score.label'
  | 'page.task_types.card_stance.label'
  | 'page.task_types.category_community.label'
  | 'page.task_types.category_development.label'
  | 'page.task_types.category_operations.label'
  | 'page.task_types.category_other.label'
  | 'page.task_types.category_product.label'
  | 'page.task_types.detail.error'
  | 'page.task_types.detail_error.hint'
  | 'page.task_types.detail_error.title'
  | 'page.task_types.filter.tab'
  | 'page.task_types.header.error'
  | 'page.task_types.header.loading'
  | 'page.task_types.header.title'
  | 'page.task_types.list.empty'
  | 'page.task_types.list.error'
  | 'page.task_types.list_error.cta'
  | 'page.task_types.list_error.title'
  | 'page.task_types.meta.title'
  | 'page.task_types.modal.title'
  | 'page.task_types.modal_base.label'
  | 'page.task_types.modal_desc.label'
  | 'page.task_types.modal_id.label'
  | 'page.task_types.modal_name.label'
  | 'page.task_types.modal_score.label'
  | 'page.task_types.modal_stance.label'
  | 'page.terms.account.title'
  | 'page.terms.account_duty.label'
  | 'page.terms.account_duty_lawful.desc'
  | 'page.terms.account_duty_password.desc'
  | 'page.terms.account_duty_rights.desc'
  | 'page.terms.account_enforcement.label'
  | 'page.terms.account_enforcement_appeal.desc'
  | 'page.terms.account_enforcement_suspend.desc'
  | 'page.terms.account_forbidden.label'
  | 'page.terms.account_forbidden_bypass.desc'
  | 'page.terms.account_forbidden_farming.desc'
  | 'page.terms.account_forbidden_probing.desc'
  | 'page.terms.account_forbidden_resale.desc'
  | 'page.terms.availability.title'
  | 'page.terms.availability_data.label'
  | 'page.terms.availability_data_backup.desc'
  | 'page.terms.availability_data_copy.desc'
  | 'page.terms.availability_data_export.desc'
  | 'page.terms.availability_sla.label'
  | 'page.terms.availability_sla_asis.desc'
  | 'page.terms.availability_sla_maintenance.desc'
  | 'page.terms.availability_sla_solo.desc'
  | 'page.terms.availability_sla_upstream.desc'
  | 'page.terms.billing.title'
  | 'page.terms.billing_payment.label'
  | 'page.terms.billing_payment_byok.desc'
  | 'page.terms.billing_payment_manual.desc'
  | 'page.terms.billing_payment_quota.desc'
  | 'page.terms.billing_refund.label'
  | 'page.terms.billing_refund_manual.desc'
  | 'page.terms.billing_refund_used.desc'
  | 'page.terms.contact.hint'
  | 'page.terms.filing.label'
  | 'page.terms.header.link'
  | 'page.terms.header.meta'
  | 'page.terms.header.subtitle'
  | 'page.terms.header.title'
  | 'page.terms.ip.title'
  | 'page.terms.ip_ours.label'
  | 'page.terms.ip_ours_oss.desc'
  | 'page.terms.ip_ours_personas.desc'
  | 'page.terms.ip_yours.label'
  | 'page.terms.ip_yours_free_use.desc'
  | 'page.terms.ip_yours_no_training.desc'
  | 'page.terms.ip_yours_own.desc'
  | 'page.terms.liability.title'
  | 'page.terms.liability_cap.label'
  | 'page.terms.liability_cap_amount.desc'
  | 'page.terms.liability_cap_indirect.desc'
  | 'page.terms.liability_change.label'
  | 'page.terms.liability_change_accept.desc'
  | 'page.terms.liability_change_notice.desc'
  | 'page.terms.liability_nature.label'
  | 'page.terms.liability_nature_mandatory.desc'
  | 'page.terms.liability_nature_unreviewed.desc'
  | 'page.terms.meta.title'
  | 'page.terms.related.desc'
  | 'page.terms.service.title'
  | 'page.terms.service_not.label'
  | 'page.terms.service_not_advice.desc'
  | 'page.terms.service_not_research.desc'
  | 'page.terms.service_not_usertest.desc'
  | 'page.terms.service_provides.label'
  | 'page.terms.service_provides_byok.desc'
  | 'page.terms.service_provides_hypothesis.desc'
  | 'page.terms.service_provides_review.desc'
  | 'page.terms.termination.desc'
  | 'page.terms.termination.title'
  | 'page.tutorial.count.unknown'
  | 'page.tutorial.filetype_community.desc'
  | 'page.tutorial.filetype_community.title'
  | 'page.tutorial.filetype_crowdfunding.desc'
  | 'page.tutorial.filetype_crowdfunding.title'
  | 'page.tutorial.filetype_devlog.desc'
  | 'page.tutorial.filetype_devlog.title'
  | 'page.tutorial.filetype_gdd.desc'
  | 'page.tutorial.filetype_gdd.title'
  | 'page.tutorial.filetype_localization.desc'
  | 'page.tutorial.filetype_localization.title'
  | 'page.tutorial.filetype_store.desc'
  | 'page.tutorial.filetype_store.title'
  | 'page.tutorial.filetypes.desc'
  | 'page.tutorial.filetypes.title'
  | 'page.tutorial.flow.desc'
  | 'page.tutorial.flow.title'
  | 'page.tutorial.header.subtitle'
  | 'page.tutorial.header.title'
  | 'page.tutorial.materials.desc'
  | 'page.tutorial.materials.title'
  | 'page.tutorial.materials_optional.label'
  | 'page.tutorial.materials_required.label'
  | 'page.tutorial.materials_task_type.label'
  | 'page.tutorial.meta.title'
  | 'page.tutorial.method.badge'
  | 'page.tutorial.method_example.desc'
  | 'page.tutorial.method_example.title'
  | 'page.tutorial.method_example_first_use.hint'
  | 'page.tutorial.method_file.desc'
  | 'page.tutorial.method_file.title'
  | 'page.tutorial.method_file_any_doc.hint'
  | 'page.tutorial.method_file_autofill.hint'
  | 'page.tutorial.method_file_editable.hint'
  | 'page.tutorial.method_file_formats.hint'
  | 'page.tutorial.method_manual.desc'
  | 'page.tutorial.method_manual.title'
  | 'page.tutorial.method_manual_fields.hint'
  | 'page.tutorial.method_manual_when.hint'
  | 'page.tutorial.result_calibration.desc'
  | 'page.tutorial.result_calibration.label'
  | 'page.tutorial.result_issues.desc'
  | 'page.tutorial.result_issues.label'
  | 'page.tutorial.result_persona.desc'
  | 'page.tutorial.result_persona.label'
  | 'page.tutorial.result_risk.desc'
  | 'page.tutorial.result_risk.label'
  | 'page.tutorial.result_stance.desc'
  | 'page.tutorial.result_stance.label'
  | 'page.tutorial.results.desc'
  | 'page.tutorial.results.title'
  | 'page.tutorial.start.cta'
  | 'page.tutorial.step_edit.desc'
  | 'page.tutorial.step_edit.label'
  | 'page.tutorial.step_panel.desc'
  | 'page.tutorial.step_panel.label'
  | 'page.tutorial.step_select_type.desc'
  | 'page.tutorial.step_select_type.label'
  | 'page.tutorial.step_upload.desc'
  | 'page.tutorial.step_upload.label'
  | 'page.tutorial.upload.desc'
  | 'page.tutorial.upload.hint'
  | 'page.tutorial.upload.title'
  | 'page.verify.confirm.error'
  | 'page.verify.fail.hint'
  | 'page.verify.fail.link'
  | 'page.verify.fail.title'
  | 'page.verify.meta.title'
  | 'page.verify.no_token.error'
  | 'page.verify.ok.cta'
  | 'page.verify.ok.title'
  | 'page.verify.pending.loading'

/** 值里带具名 slot 的 key，只有它们能进 <Trans>。 */
export type RichMessageKey =
  | 'page.ask.project_delete_confirm.confirm'
  | 'page.ask.review_delete_confirm.confirm'
  | 'page.create.confirm_material.meta'
  | 'page.create.dropzone.cta'
  | 'page.create.pack_intro.desc'
  | 'page.forgot.signin.hint'
  | 'page.history.confirm_dialog.desc'
  | 'page.login.signup.hint'
  | 'page.plans.anon.hint'
  | 'page.plans.banner_byok'
  | 'page.plans.banner_credits'
  | 'page.plans.banner_no_quota'
  | 'page.plans.credits.value'
  | 'page.plans.feature_reviews'
  | 'page.plans.request.hint'
  | 'page.register.signin.hint'
  | 'page.register.terms.consent'
  | 'page.report.predictions.hint'
  | 'page.report.share.desc'
  | 'page.settings.delete_confirm.desc'
  | 'page.settings.privacy_source.desc'
  | 'page.settings.privacy_who.desc'
  | 'page.settings.revoke.desc'
  | 'page.shared.evidence_quality.label'
  | 'page.shared.release_risk.label'
  | 'page.terms.related.desc'

/**
 * 每条 key 需要的插值变量。漏传是编译错误。
 *
 * count 恒为 number —— 它驱动 Intl.PluralRules 选变体，传字符串会静默走非复数分支。
 * 其余变量是 string | number：这里没有能推断出"它一定是数字"的事实源，
 * 硬标成 number 会逼调用方写没有意义的转换。
 */
export interface MessageVars {
  'catalog.brand.deepseek': Record<string, never>
  'catalog.brand.glm': Record<string, never>
  'catalog.brand.kimi': Record<string, never>
  'catalog.brand.ollama': Record<string, never>
  'catalog.brand.openai': Record<string, never>
  'catalog.brand.qwen': Record<string, never>
  'catalog.eval_dimension.actionability.desc': Record<string, never>
  'catalog.eval_dimension.actionability.label': Record<string, never>
  'catalog.eval_dimension.calibration_honesty.desc': Record<string, never>
  'catalog.eval_dimension.calibration_honesty.label': Record<string, never>
  'catalog.eval_dimension.ethical_persona_use.desc': Record<string, never>
  'catalog.eval_dimension.ethical_persona_use.label': Record<string, never>
  'catalog.eval_dimension.input_grounding.desc': Record<string, never>
  'catalog.eval_dimension.input_grounding.label': Record<string, never>
  'catalog.eval_dimension.persona_differentiation.desc': Record<string, never>
  'catalog.eval_dimension.persona_differentiation.label': Record<string, never>
  'catalog.eval_dimension.report_structure.desc': Record<string, never>
  'catalog.eval_dimension.report_structure.label': Record<string, never>
  'catalog.eval_dimension.risk_detection.desc': Record<string, never>
  'catalog.eval_dimension.risk_detection.label': Record<string, never>
  'catalog.eval_dimension.segment_conflict.desc': Record<string, never>
  'catalog.eval_dimension.segment_conflict.label': Record<string, never>
  'catalog.material.concept_review__一句话pitch.label': Record<string, never>
  'catalog.material.concept_review__一句话pitch.placeholder': Record<string, never>
  'catalog.material.concept_review__定价与平台.label': Record<string, never>
  'catalog.material.concept_review__定价与平台.placeholder': Record<string, never>
  'catalog.material.concept_review__截图.label': Record<string, never>
  'catalog.material.concept_review__截图.placeholder': Record<string, never>
  'catalog.material.concept_review__核心循环说明.label': Record<string, never>
  'catalog.material.concept_review__核心循环说明.placeholder': Record<string, never>
  'catalog.material.concept_review__目标受众.label': Record<string, never>
  'catalog.material.concept_review__目标受众.placeholder': Record<string, never>
  'catalog.material.concept_review__竞品对比.label': Record<string, never>
  'catalog.material.concept_review__竞品对比.placeholder': Record<string, never>
  'catalog.material.concept_review__系统说明.label': Record<string, never>
  'catalog.material.concept_review__系统说明.placeholder': Record<string, never>
  'catalog.material.demo_first_play__实机视频.label': Record<string, never>
  'catalog.material.demo_first_play__实机视频.placeholder': Record<string, never>
  'catalog.material.demo_first_play__截图.label': Record<string, never>
  'catalog.material.demo_first_play__截图.placeholder': Record<string, never>
  'catalog.material.demo_first_play__核心循环说明.label': Record<string, never>
  'catalog.material.demo_first_play__核心循环说明.placeholder': Record<string, never>
  'catalog.material.demo_first_play__游戏名称.label': Record<string, never>
  'catalog.material.demo_first_play__游戏名称.placeholder': Record<string, never>
  'catalog.material.demo_first_play__竞品对比.label': Record<string, never>
  'catalog.material.demo_first_play__竞品对比.placeholder': Record<string, never>
  'catalog.material.demo_first_play__评价摘要.label': Record<string, never>
  'catalog.material.demo_first_play__评价摘要.placeholder': Record<string, never>
  'catalog.material.devlog_review__截图.label': Record<string, never>
  'catalog.material.devlog_review__截图.placeholder': Record<string, never>
  'catalog.material.devlog_review__核心循环说明.label': Record<string, never>
  'catalog.material.devlog_review__核心循环说明.placeholder': Record<string, never>
  'catalog.material.devlog_review__游戏名称.label': Record<string, never>
  'catalog.material.devlog_review__游戏名称.placeholder': Record<string, never>
  'catalog.material.devlog_review__评价摘要.label': Record<string, never>
  'catalog.material.devlog_review__评价摘要.placeholder': Record<string, never>
  'catalog.material.discord_community_review__核心循环说明.label': Record<string, never>
  'catalog.material.discord_community_review__核心循环说明.placeholder': Record<string, never>
  'catalog.material.discord_community_review__社区名称.label': Record<string, never>
  'catalog.material.discord_community_review__社区名称.placeholder': Record<string, never>
  'catalog.material.discord_community_review__竞品对比.label': Record<string, never>
  'catalog.material.discord_community_review__竞品对比.placeholder': Record<string, never>
  'catalog.material.discord_community_review__系统说明.label': Record<string, never>
  'catalog.material.discord_community_review__系统说明.placeholder': Record<string, never>
  'catalog.material.discord_community_review__评价摘要.label': Record<string, never>
  'catalog.material.discord_community_review__评价摘要.placeholder': Record<string, never>
  'catalog.material.kickstarter_review__一句话pitch.label': Record<string, never>
  'catalog.material.kickstarter_review__一句话pitch.placeholder': Record<string, never>
  'catalog.material.kickstarter_review__定价与平台.label': Record<string, never>
  'catalog.material.kickstarter_review__定价与平台.placeholder': Record<string, never>
  'catalog.material.kickstarter_review__截图.label': Record<string, never>
  'catalog.material.kickstarter_review__截图.placeholder': Record<string, never>
  'catalog.material.kickstarter_review__核心循环说明.label': Record<string, never>
  'catalog.material.kickstarter_review__核心循环说明.placeholder': Record<string, never>
  'catalog.material.kickstarter_review__目标受众.label': Record<string, never>
  'catalog.material.kickstarter_review__目标受众.placeholder': Record<string, never>
  'catalog.material.kickstarter_review__项目名称.label': Record<string, never>
  'catalog.material.kickstarter_review__项目名称.placeholder': Record<string, never>
  'catalog.material.localization_review__核心循环说明.label': Record<string, never>
  'catalog.material.localization_review__核心循环说明.placeholder': Record<string, never>
  'catalog.material.localization_review__游戏名称.label': Record<string, never>
  'catalog.material.localization_review__游戏名称.placeholder': Record<string, never>
  'catalog.material.localization_review__竞品对比.label': Record<string, never>
  'catalog.material.localization_review__竞品对比.placeholder': Record<string, never>
  'catalog.material.localization_review__系统说明.label': Record<string, never>
  'catalog.material.localization_review__系统说明.placeholder': Record<string, never>
  'catalog.material.looking_for_party_post__核心循环说明.label': Record<string, never>
  'catalog.material.looking_for_party_post__核心循环说明.placeholder': Record<string, never>
  'catalog.material.looking_for_party_post__游戏名称.label': Record<string, never>
  'catalog.material.looking_for_party_post__游戏名称.placeholder': Record<string, never>
  'catalog.material.looking_for_party_post__目标受众.label': Record<string, never>
  'catalog.material.looking_for_party_post__目标受众.placeholder': Record<string, never>
  'catalog.material.monetization_review__定价与平台.label': Record<string, never>
  'catalog.material.monetization_review__定价与平台.placeholder': Record<string, never>
  'catalog.material.monetization_review__核心循环说明.label': Record<string, never>
  'catalog.material.monetization_review__核心循环说明.placeholder': Record<string, never>
  'catalog.material.monetization_review__游戏名称.label': Record<string, never>
  'catalog.material.monetization_review__游戏名称.placeholder': Record<string, never>
  'catalog.material.monetization_review__竞品对比.label': Record<string, never>
  'catalog.material.monetization_review__竞品对比.placeholder': Record<string, never>
  'catalog.material.monetization_review__评价摘要.label': Record<string, never>
  'catalog.material.monetization_review__评价摘要.placeholder': Record<string, never>
  'catalog.material.onboarding_review__产品名称.label': Record<string, never>
  'catalog.material.onboarding_review__产品名称.placeholder': Record<string, never>
  'catalog.material.onboarding_review__截图.label': Record<string, never>
  'catalog.material.onboarding_review__截图.placeholder': Record<string, never>
  'catalog.material.onboarding_review__核心循环说明.label': Record<string, never>
  'catalog.material.onboarding_review__核心循环说明.placeholder': Record<string, never>
  'catalog.material.onboarding_review__目标受众.label': Record<string, never>
  'catalog.material.onboarding_review__目标受众.placeholder': Record<string, never>
  'catalog.material.onboarding_review__系统说明.label': Record<string, never>
  'catalog.material.onboarding_review__系统说明.placeholder': Record<string, never>
  'catalog.material.onboarding_review__评价摘要.label': Record<string, never>
  'catalog.material.onboarding_review__评价摘要.placeholder': Record<string, never>
  'catalog.material.pitch_review__一句话pitch.label': Record<string, never>
  'catalog.material.pitch_review__一句话pitch.placeholder': Record<string, never>
  'catalog.material.pitch_review__定价与平台.label': Record<string, never>
  'catalog.material.pitch_review__定价与平台.placeholder': Record<string, never>
  'catalog.material.pitch_review__核心循环说明.label': Record<string, never>
  'catalog.material.pitch_review__核心循环说明.placeholder': Record<string, never>
  'catalog.material.pitch_review__目标受众.label': Record<string, never>
  'catalog.material.pitch_review__目标受众.placeholder': Record<string, never>
  'catalog.material.pitch_review__竞品对比.label': Record<string, never>
  'catalog.material.pitch_review__竞品对比.placeholder': Record<string, never>
  'catalog.material.pitch_review__系统说明.label': Record<string, never>
  'catalog.material.pitch_review__系统说明.placeholder': Record<string, never>
  'catalog.material.pitch_review__项目名称.label': Record<string, never>
  'catalog.material.pitch_review__项目名称.placeholder': Record<string, never>
  'catalog.material.pricing_page_review__产品名称.label': Record<string, never>
  'catalog.material.pricing_page_review__产品名称.placeholder': Record<string, never>
  'catalog.material.pricing_page_review__定价与平台.label': Record<string, never>
  'catalog.material.pricing_page_review__定价与平台.placeholder': Record<string, never>
  'catalog.material.pricing_page_review__截图.label': Record<string, never>
  'catalog.material.pricing_page_review__截图.placeholder': Record<string, never>
  'catalog.material.pricing_page_review__核心循环说明.label': Record<string, never>
  'catalog.material.pricing_page_review__核心循环说明.placeholder': Record<string, never>
  'catalog.material.pricing_page_review__目标受众.label': Record<string, never>
  'catalog.material.pricing_page_review__目标受众.placeholder': Record<string, never>
  'catalog.material.pricing_page_review__竞品对比.label': Record<string, never>
  'catalog.material.pricing_page_review__竞品对比.placeholder': Record<string, never>
  'catalog.material.product_feedback_review__产品名称.label': Record<string, never>
  'catalog.material.product_feedback_review__产品名称.placeholder': Record<string, never>
  'catalog.material.product_feedback_review__截图.label': Record<string, never>
  'catalog.material.product_feedback_review__截图.placeholder': Record<string, never>
  'catalog.material.product_feedback_review__核心循环说明.label': Record<string, never>
  'catalog.material.product_feedback_review__核心循环说明.placeholder': Record<string, never>
  'catalog.material.product_feedback_review__目标受众.label': Record<string, never>
  'catalog.material.product_feedback_review__目标受众.placeholder': Record<string, never>
  'catalog.material.product_feedback_review__竞品对比.label': Record<string, never>
  'catalog.material.product_feedback_review__竞品对比.placeholder': Record<string, never>
  'catalog.material.product_feedback_review__评价摘要.label': Record<string, never>
  'catalog.material.product_feedback_review__评价摘要.placeholder': Record<string, never>
  'catalog.material.steam_page_review__demo.label': Record<string, never>
  'catalog.material.steam_page_review__demo.placeholder': Record<string, never>
  'catalog.material.steam_page_review__tags.label': Record<string, never>
  'catalog.material.steam_page_review__tags.placeholder': Record<string, never>
  'catalog.material.steam_page_review__价格.label': Record<string, never>
  'catalog.material.steam_page_review__价格.placeholder': Record<string, never>
  'catalog.material.steam_page_review__截图.label': Record<string, never>
  'catalog.material.steam_page_review__截图.placeholder': Record<string, never>
  'catalog.material.steam_page_review__核心循环说明.label': Record<string, never>
  'catalog.material.steam_page_review__核心循环说明.placeholder': Record<string, never>
  'catalog.material.steam_page_review__游戏名称.label': Record<string, never>
  'catalog.material.steam_page_review__游戏名称.placeholder': Record<string, never>
  'catalog.material.steam_page_review__评价摘要.label': Record<string, never>
  'catalog.material.steam_page_review__评价摘要.placeholder': Record<string, never>
  'catalog.material.update_announcement_review__截图.label': Record<string, never>
  'catalog.material.update_announcement_review__截图.placeholder': Record<string, never>
  'catalog.material.update_announcement_review__核心循环说明.label': Record<string, never>
  'catalog.material.update_announcement_review__核心循环说明.placeholder': Record<string, never>
  'catalog.material.update_announcement_review__游戏名称.label': Record<string, never>
  'catalog.material.update_announcement_review__游戏名称.placeholder': Record<string, never>
  'catalog.material.update_announcement_review__评价摘要.label': Record<string, never>
  'catalog.material.update_announcement_review__评价摘要.placeholder': Record<string, never>
  'catalog.mode.full.desc': Record<string, never>
  'catalog.mode.quick.desc': Record<string, never>
  'catalog.mode.standard.desc': Record<string, never>
  'catalog.persona_pack.accessibility': Record<string, never>
  'catalog.persona_pack.category_general': Record<string, never>
  'catalog.persona_pack.category_platform': Record<string, never>
  'catalog.persona_pack.category_player_type': Record<string, never>
  'catalog.persona_pack.category_special': Record<string, never>
  'catalog.persona_pack.competitive_esport': Record<string, never>
  'catalog.persona_pack.educational_serious': Record<string, never>
  'catalog.persona_pack.family_casual': Record<string, never>
  'catalog.persona_pack.game_core': Record<string, never>
  'catalog.persona_pack.general_consumer': Record<string, never>
  'catalog.persona_pack.indie_creative': Record<string, never>
  'catalog.persona_pack.launch_compliance': Record<string, never>
  'catalog.persona_pack.mobile_f2p': Record<string, never>
  'catalog.persona_pack.startup_panel': Record<string, never>
  'catalog.persona_pack.vr_immersive': Record<string, never>
  'catalog.skill.audience_panel.desc': Record<string, never>
  'catalog.skill.audience_panel.label': Record<string, never>
  'catalog.skill.persona_generate.desc': Record<string, never>
  'catalog.skill.persona_generate.label': Record<string, never>
  'catalog.skill.red_team_audience.desc': Record<string, never>
  'catalog.skill.red_team_audience.label': Record<string, never>
  'catalog.skill.synthetic_playtest.desc': Record<string, never>
  'catalog.skill.synthetic_playtest.label': Record<string, never>
  'catalog.task_type.concept_review.desc': Record<string, never>
  'catalog.task_type.concept_review.label': Record<string, never>
  'catalog.task_type.demo_first_play.desc': Record<string, never>
  'catalog.task_type.demo_first_play.label': Record<string, never>
  'catalog.task_type.devlog_review.desc': Record<string, never>
  'catalog.task_type.devlog_review.label': Record<string, never>
  'catalog.task_type.discord_community_review.desc': Record<string, never>
  'catalog.task_type.discord_community_review.label': Record<string, never>
  'catalog.task_type.kickstarter_review.desc': Record<string, never>
  'catalog.task_type.kickstarter_review.label': Record<string, never>
  'catalog.task_type.localization_review.desc': Record<string, never>
  'catalog.task_type.localization_review.label': Record<string, never>
  'catalog.task_type.looking_for_party_post.desc': Record<string, never>
  'catalog.task_type.looking_for_party_post.label': Record<string, never>
  'catalog.task_type.monetization_review.desc': Record<string, never>
  'catalog.task_type.monetization_review.label': Record<string, never>
  'catalog.task_type.onboarding_review.desc': Record<string, never>
  'catalog.task_type.onboarding_review.label': Record<string, never>
  'catalog.task_type.pitch_review.desc': Record<string, never>
  'catalog.task_type.pitch_review.label': Record<string, never>
  'catalog.task_type.pricing_page_review.desc': Record<string, never>
  'catalog.task_type.pricing_page_review.label': Record<string, never>
  'catalog.task_type.product_feedback_review.desc': Record<string, never>
  'catalog.task_type.product_feedback_review.label': Record<string, never>
  'catalog.task_type.steam_page_review.desc': Record<string, never>
  'catalog.task_type.steam_page_review.label': Record<string, never>
  'catalog.task_type.update_announcement_review.desc': Record<string, never>
  'catalog.task_type.update_announcement_review.label': Record<string, never>
  'common.action.back': Record<string, never>
  'common.action.cancel': Record<string, never>
  'common.action.clear': Record<string, never>
  'common.action.close': Record<string, never>
  'common.action.collapse': Record<string, never>
  'common.action.confirm': Record<string, never>
  'common.action.copy': Record<string, never>
  'common.action.delete': Record<string, never>
  'common.action.delete_account_phrase': Record<string, never>
  'common.action.download': Record<string, never>
  'common.action.edit': Record<string, never>
  'common.action.expand': Record<string, never>
  'common.action.load_more': Record<string, never>
  'common.action.next': Record<string, never>
  'common.action.prev': Record<string, never>
  'common.action.refresh': Record<string, never>
  'common.action.remove': Record<string, never>
  'common.action.retry': Record<string, never>
  'common.action.save': Record<string, never>
  'common.action.share': Record<string, never>
  'common.action.submit': Record<string, never>
  'common.action.upload': Record<string, never>
  'common.action.view_details': Record<string, never>
  'common.calibration_gauge.missing.hint': Record<string, never>
  'common.calibration_gauge.no_pass_line.hint': Record<string, never>
  'common.calibration_gauge.pass_line.value': { value: string | number }
  'common.calibration_gauge.readout.empty': Record<string, never>
  'common.meta.description': Record<string, never>
  'common.meta.title_template': { page: string | number }
  'common.persona_card.confidence.value': { value: string | number }
  'common.persona_radar.series_a.label': Record<string, never>
  'common.persona_radar.series_b.label': Record<string, never>
  'common.ui.copied': Record<string, never>
  'common.ui.copy_failed': Record<string, never>
  'common.ui.deleting': Record<string, never>
  'common.ui.empty': Record<string, never>
  'common.ui.error': Record<string, never>
  'common.ui.language': Record<string, never>
  'common.ui.language_aria': Record<string, never>
  'common.ui.language_hint': Record<string, never>
  'common.ui.loading': Record<string, never>
  'common.ui.not_recorded': Record<string, never>
  'common.ui.optional_mark': Record<string, never>
  'common.ui.processing': Record<string, never>
  'common.ui.required_mark': Record<string, never>
  'common.ui.saving': Record<string, never>
  'common.ui.sending': Record<string, never>
  'common.ui.submitting': Record<string, never>
  'common.ui.success': Record<string, never>
  'common.ui.unknown_error': Record<string, never>
  'common.validate.email_format': Record<string, never>
  'common.validate.file_too_large': { max: string | number }
  'common.validate.number_range': { max: string | number; min: string | number }
  'common.validate.password_min': { min: string | number }
  'common.validate.password_mismatch': Record<string, never>
  'common.validate.required': Record<string, never>
  'common.validate.too_long': { max: string | number }
  'enum.behavior_axis.agency_preference': Record<string, never>
  'enum.behavior_axis.completion_drive': Record<string, never>
  'enum.behavior_axis.criticism_style': Record<string, never>
  'enum.behavior_axis.emotional_engagement': Record<string, never>
  'enum.behavior_axis.genre_literacy': Record<string, never>
  'enum.behavior_axis.novelty_seeking': Record<string, never>
  'enum.behavior_axis.patience': Record<string, never>
  'enum.behavior_axis.platform_loyalty': Record<string, never>
  'enum.behavior_axis.price_sensitivity': Record<string, never>
  'enum.behavior_axis.risk_tolerance': Record<string, never>
  'enum.behavior_axis.social_influence': Record<string, never>
  'enum.behavior_axis.tolerance_for_ambiguity': Record<string, never>
  'enum.calibration.coverage': Record<string, never>
  'enum.calibration.hallucination': Record<string, never>
  'enum.calibration.role_consistency': Record<string, never>
  'enum.cross_exam_mode.derived_summary.desc': Record<string, never>
  'enum.cross_exam_mode.derived_summary.label': Record<string, never>
  'enum.cross_exam_mode.moderated_rebuttal.desc': Record<string, never>
  'enum.cross_exam_mode.moderated_rebuttal.label': Record<string, never>
  'enum.cross_exam_mode.multi_agent_rebuttal.desc': Record<string, never>
  'enum.cross_exam_mode.multi_agent_rebuttal.label': Record<string, never>
  'enum.direction.decrease': Record<string, never>
  'enum.direction.increase': Record<string, never>
  'enum.disabled_reason.explicit_persona_selection': Record<string, never>
  'enum.ethics_severity.high': Record<string, never>
  'enum.ethics_severity.low': Record<string, never>
  'enum.ethics_severity.medium': Record<string, never>
  'enum.evidence_quality.insufficient': Record<string, never>
  'enum.evidence_quality.medium': Record<string, never>
  'enum.evidence_quality.strong': Record<string, never>
  'enum.evidence_quality.weak': Record<string, never>
  'enum.gate_reason.hallucination': Record<string, never>
  'enum.gate_reason.role_drift': Record<string, never>
  'enum.gate_reason.schema_failure': Record<string, never>
  'enum.mode_badge.full': Record<string, never>
  'enum.mode_badge.quick': Record<string, never>
  'enum.mode_badge.standard': Record<string, never>
  'enum.persona_status.completed': Record<string, never>
  'enum.persona_status.failed': Record<string, never>
  'enum.persona_status.pending': Record<string, never>
  'enum.persona_status.running': Record<string, never>
  'enum.primary_stance.advocate': Record<string, never>
  'enum.primary_stance.blocker': Record<string, never>
  'enum.primary_stance.neutral': Record<string, never>
  'enum.primary_stance.skeptic': Record<string, never>
  'enum.rebuttal_status.failed': Record<string, never>
  'enum.rebuttal_status.ok': Record<string, never>
  'enum.rebuttal_status.partial': Record<string, never>
  'enum.rebuttal_status.skipped': Record<string, never>
  'enum.release_risk.critical': Record<string, never>
  'enum.release_risk.high': Record<string, never>
  'enum.release_risk.low': Record<string, never>
  'enum.release_risk.medium': Record<string, never>
  'enum.review_status.cancelled': Record<string, never>
  'enum.review_status.completed': Record<string, never>
  'enum.review_status.failed': Record<string, never>
  'enum.review_status.pending': Record<string, never>
  'enum.review_status.running': Record<string, never>
  'enum.severity.critical': Record<string, never>
  'enum.severity.high': Record<string, never>
  'enum.severity.low': Record<string, never>
  'enum.severity.medium': Record<string, never>
  'enum.stereotype_risk.high': Record<string, never>
  'enum.stereotype_risk.low': Record<string, never>
  'enum.stereotype_risk.medium': Record<string, never>
  'enum.stereotype_risk.unknown': Record<string, never>
  'enum.stop_reason.cost_budget_reached': Record<string, never>
  'enum.stop_reason.marginal_value_below_threshold': Record<string, never>
  'enum.verdict.fail': Record<string, never>
  'enum.verdict.pass': Record<string, never>
  'error.api.admin_disabled': Record<string, never>
  'error.api.bad_request': Record<string, never>
  'error.api.forbidden': Record<string, never>
  'error.api.internal_error': Record<string, never>
  'error.api.llm_key_missing': Record<string, never>
  'error.api.not_found': Record<string, never>
  'error.api.quota_exceeded': Record<string, never>
  'error.api.rate_limited': Record<string, never>
  'error.api.unauthorized': Record<string, never>
  'error.api.upstream_error': Record<string, never>
  'error.fetch.delete_review': Record<string, never>
  'error.fetch.ethics': Record<string, never>
  'error.fetch.evaluation': Record<string, never>
  'error.fetch.examples': Record<string, never>
  'error.fetch.extract_materials': Record<string, never>
  'error.fetch.http_status': { message: string | number; status: string | number }
  'error.fetch.persona_packs': Record<string, never>
  'error.fetch.personas': Record<string, never>
  'error.fetch.report': Record<string, never>
  'error.fetch.review': Record<string, never>
  'error.fetch.review_list': Record<string, never>
  'error.fetch.review_modes': Record<string, never>
  'error.fetch.review_result': Record<string, never>
  'error.fetch.run_evaluation': Record<string, never>
  'error.fetch.separator': Record<string, never>
  'error.fetch.skills': Record<string, never>
  'error.fetch.task_types': Record<string, never>
  'error.store.bootstrap': Record<string, never>
  'error.store.examples': Record<string, never>
  'error.store.personas': Record<string, never>
  'error.store.review_list': Record<string, never>
  'error.ws.closed': Record<string, never>
  'error.ws.give_up': Record<string, never>
  'error.ws.reconnecting': { count: number }
  'error.ws.review_failed': { message: string | number }
  'error.ws.unavailable': Record<string, never>
  'nav.account.guest': Record<string, never>
  'nav.account.login': Record<string, never>
  'nav.account.logout': Record<string, never>
  'nav.account.menu_aria': Record<string, never>
  'nav.account.settings': Record<string, never>
  'nav.footer.icp_aria': Record<string, never>
  'nav.footer.privacy': Record<string, never>
  'nav.footer.tagline': Record<string, never>
  'nav.footer.terms': Record<string, never>
  'nav.item.ask': Record<string, never>
  'nav.item.create_review': Record<string, never>
  'nav.item.history': Record<string, never>
  'nav.item.home': Record<string, never>
  'nav.item.ledger': Record<string, never>
  'nav.item.personas': Record<string, never>
  'nav.item.plans': Record<string, never>
  'nav.item.settings': Record<string, never>
  'nav.item.skills': Record<string, never>
  'nav.item.task_types': Record<string, never>
  'nav.item.tutorial': Record<string, never>
  'nav.menu.drawer_aria': Record<string, never>
  'nav.menu.toggle_aria': Record<string, never>
  'nav.session.cta': Record<string, never>
  'nav.session.dismiss_aria': Record<string, never>
  'nav.session.expired': Record<string, never>
  'nav.verify_banner.cta': Record<string, never>
  'nav.verify_banner.error': Record<string, never>
  'nav.verify_banner.hint': { count: number }
  'nav.verify_banner.hint_unknown': Record<string, never>
  'nav.verify_banner.sending': Record<string, never>
  'nav.verify_banner.success': Record<string, never>
  'page.ask.attach.hint': Record<string, never>
  'page.ask.attachment_image.aria': { index: string | number }
  'page.ask.attachment_limit.error': { count: number }
  'page.ask.attachment_note_follow_up.hint': { count: number }
  'page.ask.attachment_note_review.hint': { count: number }
  'page.ask.attachment_preview.tooltip': Record<string, never>
  'page.ask.attachment_remove.aria': { filename: string | number }
  'page.ask.clarify.hint': Record<string, never>
  'page.ask.conclusion.title': Record<string, never>
  'page.ask.confidence.label': Record<string, never>
  'page.ask.confidence.value': { level: string | number; percent: string | number }
  'page.ask.confidence_high.label': Record<string, never>
  'page.ask.confidence_low.label': Record<string, never>
  'page.ask.confidence_medium.label': Record<string, never>
  'page.ask.confirm.label': Record<string, never>
  'page.ask.conversation_move.error': Record<string, never>
  'page.ask.conversation_untitled.label': Record<string, never>
  'page.ask.cost.value': { amount: string | number }
  'page.ask.count.disagreements': { count: number }
  'page.ask.count.fixes': { count: number }
  'page.ask.count.information_gaps': { count: number }
  'page.ask.count.issues': { count: number }
  'page.ask.count.persona_notes': { count: number }
  'page.ask.count.personas': { count: number }
  'page.ask.count.priority_fixes': { count: number }
  'page.ask.create.error': Record<string, never>
  'page.ask.disagreement.hint': { text: string | number }
  'page.ask.disagreement_evidence.value': { evidence: string | number }
  'page.ask.disagreement_stance.value': { persona: string | number; stance: string | number }
  'page.ask.drop.hint': Record<string, never>
  'page.ask.evidence.badge': { quality: string | number }
  'page.ask.example_onboarding.value': Record<string, never>
  'page.ask.example_pitch.value': Record<string, never>
  'page.ask.example_pricing.value': Record<string, never>
  'page.ask.examples.cta': Record<string, never>
  'page.ask.examples.hint': Record<string, never>
  'page.ask.examples.title': Record<string, never>
  'page.ask.fix.hint': { text: string | number }
  'page.ask.follow_up.badge': { label: string | number }
  'page.ask.follow_up.cta': Record<string, never>
  'page.ask.follow_up.error': Record<string, never>
  'page.ask.follow_up.label': Record<string, never>
  'page.ask.follow_up.tooltip': Record<string, never>
  'page.ask.follow_up_exit.aria': Record<string, never>
  'page.ask.follow_up_report.cta': Record<string, never>
  'page.ask.gated.cta': Record<string, never>
  'page.ask.gated.hint': { count: number }
  'page.ask.greeting.value': Record<string, never>
  'page.ask.header.desc': Record<string, never>
  'page.ask.header.title': Record<string, never>
  'page.ask.history.error': Record<string, never>
  'page.ask.history_delete.error': { detail: string | number }
  'page.ask.history_delete.hint': Record<string, never>
  'page.ask.input.aria': Record<string, never>
  'page.ask.input.placeholder': Record<string, never>
  'page.ask.input_follow_up.placeholder': { label: string | number }
  'page.ask.legacy.title': Record<string, never>
  'page.ask.login_required.cta': Record<string, never>
  'page.ask.login_required.desc': Record<string, never>
  'page.ask.login_required.title': Record<string, never>
  'page.ask.meta.title': Record<string, never>
  'page.ask.mode.badge': { mode: string | number }
  'page.ask.need_key.cta': Record<string, never>
  'page.ask.new_conversation.cta': Record<string, never>
  'page.ask.new_project.confirm': Record<string, never>
  'page.ask.new_project.cta': Record<string, never>
  'page.ask.new_project.placeholder': Record<string, never>
  'page.ask.no_key.cta': Record<string, never>
  'page.ask.no_key.desc': Record<string, never>
  'page.ask.no_key.title': Record<string, never>
  'page.ask.pack.badge': { pack: string | number }
  'page.ask.parse.error': Record<string, never>
  'page.ask.persisted_confirm.empty': Record<string, never>
  'page.ask.persisted_confirm.value': { taskType: string | number }
  'page.ask.persisted_review.value': Record<string, never>
  'page.ask.persona_chat.cta': Record<string, never>
  'page.ask.persona_remove.aria': { name: string | number }
  'page.ask.persona_remove.tooltip': Record<string, never>
  'page.ask.persona_restore.aria': { name: string | number }
  'page.ask.persona_restore.tooltip': Record<string, never>
  'page.ask.personas.label': Record<string, never>
  'page.ask.pinned_project.aria': Record<string, never>
  'page.ask.pinned_project.badge': { name: string | number }
  'page.ask.pinned_project.tooltip': Record<string, never>
  'page.ask.pinned_skill.aria': Record<string, never>
  'page.ask.pinned_skill.badge': { name: string | number }
  'page.ask.pinned_type.aria': Record<string, never>
  'page.ask.pinned_type.badge': { name: string | number }
  'page.ask.preview_close.aria': Record<string, never>
  'page.ask.progress.hint': Record<string, never>
  'page.ask.progress.pending': Record<string, never>
  'page.ask.project.badge': { name: string | number }
  'page.ask.project.empty': Record<string, never>
  'page.ask.project_create.error': Record<string, never>
  'page.ask.project_delete.aria': { name: string | number }
  'page.ask.project_delete.error': Record<string, never>
  'page.ask.project_delete.tooltip': Record<string, never>
  'page.ask.project_delete_confirm.aria': { name: string | number }
  'page.ask.project_delete_confirm.confirm': { count: number; name: string | number }
  'page.ask.project_delete_confirm.cta': Record<string, never>
  'page.ask.project_rename.aria': { name: string | number }
  'page.ask.project_rename.error': Record<string, never>
  'page.ask.project_rename.tooltip': Record<string, never>
  'page.ask.project_select.aria': Record<string, never>
  'page.ask.project_select.empty': Record<string, never>
  'page.ask.project_select.placeholder': Record<string, never>
  'page.ask.projects.loading': Record<string, never>
  'page.ask.realtime_reconnecting.hint': Record<string, never>
  'page.ask.realtime_unavailable.hint': { seconds: string | number }
  'page.ask.report_card.cta': Record<string, never>
  'page.ask.report_card.empty': Record<string, never>
  'page.ask.report_card.loading': Record<string, never>
  'page.ask.report_card.title': Record<string, never>
  'page.ask.report_modal.subtitle': Record<string, never>
  'page.ask.restored_review.label': Record<string, never>
  'page.ask.review_delete.aria': { title: string | number }
  'page.ask.review_delete.tooltip': Record<string, never>
  'page.ask.review_delete_confirm.aria': { title: string | number }
  'page.ask.review_delete_confirm.confirm': { title: string | number }
  'page.ask.review_failed.error': Record<string, never>
  'page.ask.review_failed.title': Record<string, never>
  'page.ask.rule_parse.hint': Record<string, never>
  'page.ask.send.aria': Record<string, never>
  'page.ask.sidebar_collapse.aria': Record<string, never>
  'page.ask.sidebar_collapse.tooltip': Record<string, never>
  'page.ask.sidebar_empty.desc': Record<string, never>
  'page.ask.sidebar_empty.title': Record<string, never>
  'page.ask.sidebar_expand.aria': Record<string, never>
  'page.ask.sidebar_expand.tooltip': Record<string, never>
  'page.ask.skill.badge': { name: string | number }
  'page.ask.skill_degraded.value': { reason: string | number }
  'page.ask.skill_picker.aria': Record<string, never>
  'page.ask.skill_picker.tooltip': Record<string, never>
  'page.ask.skill_quota.badge': { count: number }
  'page.ask.skill_quota.empty': Record<string, never>
  'page.ask.skill_quota.hint': Record<string, never>
  'page.ask.stalled.hint': { idle: string | number; seconds: string | number }
  'page.ask.stance.empty': Record<string, never>
  'page.ask.stance_row.empty': Record<string, never>
  'page.ask.submit.cta': Record<string, never>
  'page.ask.submit.pending': Record<string, never>
  'page.ask.sync_failed.error': { count: number }
  'page.ask.token.tooltip': { input: string | number; output: string | number }
  'page.ask.token.unit': { value: string | number }
  'page.ask.type_picker.aria': Record<string, never>
  'page.ask.type_picker.placeholder': Record<string, never>
  'page.ask.type_picker.tooltip': Record<string, never>
  'page.ask.ungrouped.empty': Record<string, never>
  'page.ask.ungrouped.title': Record<string, never>
  'page.ask.upload.aria': Record<string, never>
  'page.ask.upload.error': { detail: string | number; filename: string | number }
  'page.ask.upload.tooltip': Record<string, never>
  'page.create.category_all.tab': Record<string, never>
  'page.create.confirm.desc': Record<string, never>
  'page.create.confirm.title': Record<string, never>
  'page.create.confirm_extra.title': Record<string, never>
  'page.create.confirm_extra_evaluation.badge': Record<string, never>
  'page.create.confirm_extra_red_team.badge': Record<string, never>
  'page.create.confirm_field.empty': Record<string, never>
  'page.create.confirm_field.label': { name: string | number }
  'page.create.confirm_material.meta': { count: number; total: string | number }
  'page.create.confirm_material.title': Record<string, never>
  'page.create.confirm_mode.title': Record<string, never>
  'page.create.confirm_persona.meta': { pack: string | number }
  'page.create.confirm_persona.title': { count: number }
  'page.create.confirm_skill.title': Record<string, never>
  'page.create.confirm_target.empty': Record<string, never>
  'page.create.confirm_target.title': Record<string, never>
  'page.create.confirm_task_type.title': Record<string, never>
  'page.create.cost.desc': Record<string, never>
  'page.create.cost.title': Record<string, never>
  'page.create.dropped_skill.desc': Record<string, never>
  'page.create.dropped_skill.title': { skill: string | number }
  'page.create.dropzone.cta': Record<string, never>
  'page.create.dropzone.hint': Record<string, never>
  'page.create.evaluation.desc': { count: number }
  'page.create.evaluation.label': Record<string, never>
  'page.create.examples.cta': Record<string, never>
  'page.create.extra_fields.desc': { taskType: string | number }
  'page.create.extra_fields_unknown.label': Record<string, never>
  'page.create.extract.error': { reason: string | number }
  'page.create.extract.hint': Record<string, never>
  'page.create.extract.pending': Record<string, never>
  'page.create.extract.success': { count: number }
  'page.create.extract_reason_unknown.error': Record<string, never>
  'page.create.feature_calibration.badge': Record<string, never>
  'page.create.feature_cross_exam.badge': Record<string, never>
  'page.create.feature_none.badge': Record<string, never>
  'page.create.fields.hint': { count: number }
  'page.create.fields.title': Record<string, never>
  'page.create.generic_field.label': Record<string, never>
  'page.create.generic_field.placeholder': Record<string, never>
  'page.create.input_mode_file.tab': Record<string, never>
  'page.create.input_mode_text.tab': Record<string, never>
  'page.create.launch.cta': Record<string, never>
  'page.create.launch.error': Record<string, never>
  'page.create.launch_no_material.error': Record<string, never>
  'page.create.launch_pack_mismatch.error': Record<string, never>
  'page.create.material.desc': Record<string, never>
  'page.create.material.title': Record<string, never>
  'page.create.meta.title': Record<string, never>
  'page.create.mode.title': Record<string, never>
  'page.create.mode_card.unit': { range: string | number }
  'page.create.mode_name.value': { mode: string | number }
  'page.create.mode_summary.title': Record<string, never>
  'page.create.mode_summary.unit': { range: string | number }
  'page.create.option.desc': Record<string, never>
  'page.create.option.title': Record<string, never>
  'page.create.over_max.desc': { count: number; max: string | number }
  'page.create.over_max.title': { max: string | number; mode: string | number }
  'page.create.pack_card.unit': { count: number }
  'page.create.pack_conflict.desc': Record<string, never>
  'page.create.pack_conflict.title': { count: number; packs: string | number }
  'page.create.pack_conflict.value': Record<string, never>
  'page.create.pack_intro.desc': { desc: string | number; name: string | number }
  'page.create.persona.desc': Record<string, never>
  'page.create.persona.title': Record<string, never>
  'page.create.persona_list.meta': { count: number; max: string | number }
  'page.create.persona_list.title': Record<string, never>
  'page.create.red_team.desc': Record<string, never>
  'page.create.red_team.label': Record<string, never>
  'page.create.red_team_case_community.badge': Record<string, never>
  'page.create.red_team_case_localization.badge': Record<string, never>
  'page.create.red_team_case_pr.badge': Record<string, never>
  'page.create.red_team_case_pricing.badge': Record<string, never>
  'page.create.skill.desc': Record<string, never>
  'page.create.skill.title': Record<string, never>
  'page.create.skill_card.meta': { count: number }
  'page.create.skill_error.cta': Record<string, never>
  'page.create.skill_error.title': Record<string, never>
  'page.create.skill_list.empty': Record<string, never>
  'page.create.skill_list.error': Record<string, never>
  'page.create.stage.confirm': Record<string, never>
  'page.create.stage.material': Record<string, never>
  'page.create.stage.option': Record<string, never>
  'page.create.stage.persona': Record<string, never>
  'page.create.stage.skill': Record<string, never>
  'page.create.stage.task_type': Record<string, never>
  'page.create.target.label': Record<string, never>
  'page.create.target.placeholder': Record<string, never>
  'page.create.task_type.desc': Record<string, never>
  'page.create.task_type.title': Record<string, never>
  'page.create.task_type_open.desc': { skill: string | number }
  'page.create.task_type_scoped.desc': { skill: string | number }
  'page.evaluation.back.cta': Record<string, never>
  'page.evaluation.completed.label': Record<string, never>
  'page.evaluation.created.label': Record<string, never>
  'page.evaluation.critical.title': Record<string, never>
  'page.evaluation.dimension.hint': Record<string, never>
  'page.evaluation.dimensions.title': Record<string, never>
  'page.evaluation.ethics.title': Record<string, never>
  'page.evaluation.ethics_error.desc': { count: number; message: string | number }
  'page.evaluation.ethics_score.label': Record<string, never>
  'page.evaluation.header.aria': Record<string, never>
  'page.evaluation.header.loading': Record<string, never>
  'page.evaluation.header.title': Record<string, never>
  'page.evaluation.load_error.desc': { message: string | number }
  'page.evaluation.load_error.title': Record<string, never>
  'page.evaluation.meta.title': Record<string, never>
  'page.evaluation.not_generated.desc': Record<string, never>
  'page.evaluation.not_generated.title': Record<string, never>
  'page.evaluation.overall.desc': { count: number; passed: string | number }
  'page.evaluation.overall.hint': Record<string, never>
  'page.evaluation.overall.title': Record<string, never>
  'page.evaluation.radar.label': Record<string, never>
  'page.evaluation.radar.title': Record<string, never>
  'page.evaluation.score.label': Record<string, never>
  'page.evaluation.score.value': { max: string | number; score: string | number }
  'page.evaluation.skill.label': Record<string, never>
  'page.evaluation.state.fail': Record<string, never>
  'page.evaluation.state.overall_fail': Record<string, never>
  'page.evaluation.state.overall_pass': Record<string, never>
  'page.evaluation.state.pass': Record<string, never>
  'page.evaluation.stereotype.label': Record<string, never>
  'page.evaluation.time.empty': Record<string, never>
  'page.evaluation.timeline.title': Record<string, never>
  'page.evaluation.unknown_dimension.label': { id: string | number }
  'page.evaluation.violations.label': { count: number }
  'page.forgot.email.label': Record<string, never>
  'page.forgot.email.placeholder': Record<string, never>
  'page.forgot.header.desc': Record<string, never>
  'page.forgot.header.title': Record<string, never>
  'page.forgot.meta.title': Record<string, never>
  'page.forgot.sent.hint': Record<string, never>
  'page.forgot.sent.link': Record<string, never>
  'page.forgot.sent.success': Record<string, never>
  'page.forgot.signin.hint': Record<string, never>
  'page.forgot.submit.cta': Record<string, never>
  'page.forgot.submit.error': Record<string, never>
  'page.history.confirm_dialog.aria': { title: string | number }
  'page.history.confirm_dialog.desc': { title: string | number }
  'page.history.count.loaded_only': { count: number }
  'page.history.count.total': { count: number }
  'page.history.count.total_and_loaded': { count: number; loaded: string | number }
  'page.history.delete.error': Record<string, never>
  'page.history.group.meta': { count: number }
  'page.history.header.desc': Record<string, never>
  'page.history.header.title': Record<string, never>
  'page.history.item.aria': { title: string | number }
  'page.history.item.tooltip': Record<string, never>
  'page.history.list_empty.cta': Record<string, never>
  'page.history.list_empty.title': Record<string, never>
  'page.history.load.error': Record<string, never>
  'page.history.load_error.desc': Record<string, never>
  'page.history.load_error.title': Record<string, never>
  'page.history.load_more.cta': Record<string, never>
  'page.history.load_more.error': Record<string, never>
  'page.history.load_more.remaining': { count: number }
  'page.history.load_more.success': { count: number }
  'page.history.meta.title': Record<string, never>
  'page.landing.meta.title': Record<string, never>
  'page.ledger.adoption.label': Record<string, never>
  'page.ledger.avg_model_cost.label': Record<string, never>
  'page.ledger.avg_willingness.label': Record<string, never>
  'page.ledger.bin_claimed.value': { value: string | number }
  'page.ledger.bin_observed.value': { value: string | number }
  'page.ledger.bins.title': Record<string, never>
  'page.ledger.bins.value': { lower: string | number; upper: string | number }
  'page.ledger.brier.hint': Record<string, never>
  'page.ledger.brier.label': Record<string, never>
  'page.ledger.by_task_type.title': Record<string, never>
  'page.ledger.calibration.desc': Record<string, never>
  'page.ledger.calibration.hint': Record<string, never>
  'page.ledger.calibration.title': Record<string, never>
  'page.ledger.cost_per_adopted.label': Record<string, never>
  'page.ledger.cost_per_useful.label': Record<string, never>
  'page.ledger.decision_change.label': Record<string, never>
  'page.ledger.ece.hint': Record<string, never>
  'page.ledger.ece.label': Record<string, never>
  'page.ledger.error.cta': Record<string, never>
  'page.ledger.error.hint': Record<string, never>
  'page.ledger.error.pending': Record<string, never>
  'page.ledger.error.title': Record<string, never>
  'page.ledger.excluded_rows.value': { count: number; verified: string | number }
  'page.ledger.feedback_coverage.label': Record<string, never>
  'page.ledger.header.desc': Record<string, never>
  'page.ledger.header.title': Record<string, never>
  'page.ledger.hit_rate.label': Record<string, never>
  'page.ledger.hours_saved.label': Record<string, never>
  'page.ledger.hours_saved.value': { hours: string | number }
  'page.ledger.item.meta': { author: string | number; severity: string | number; time: string | number }
  'page.ledger.leaderboard.title': Record<string, never>
  'page.ledger.list.error': Record<string, never>
  'page.ledger.list.label': Record<string, never>
  'page.ledger.list.title': Record<string, never>
  'page.ledger.list_empty.desc': Record<string, never>
  'page.ledger.list_empty.title': Record<string, never>
  'page.ledger.low_confidence.hint': { count: number }
  'page.ledger.mean_confidence.label': Record<string, never>
  'page.ledger.meta.title': Record<string, never>
  'page.ledger.observed_hit.hint': Record<string, never>
  'page.ledger.observed_hit.label': Record<string, never>
  'page.ledger.over_estimate.value': { value: string | number }
  'page.ledger.panel.label': Record<string, never>
  'page.ledger.pending_verification.label': Record<string, never>
  'page.ledger.sample.value': { size: string | number }
  'page.ledger.stat.empty': Record<string, never>
  'page.ledger.state.hit': Record<string, never>
  'page.ledger.state.miss': Record<string, never>
  'page.ledger.state.partial': Record<string, never>
  'page.ledger.state.unknown': Record<string, never>
  'page.ledger.task_adopted.value': { value: string | number }
  'page.ledger.task_useful.value': { value: string | number }
  'page.ledger.top_fixes.title': Record<string, never>
  'page.ledger.top_fixes.value': { times: string | number }
  'page.ledger.total_judgments.label': Record<string, never>
  'page.ledger.under_estimate.value': { value: string | number }
  'page.ledger.useful_rate.label': Record<string, never>
  'page.ledger.value.title': Record<string, never>
  'page.ledger.verified.label': Record<string, never>
  'page.ledger.verified_rows.value': { count: number }
  'page.ledger.verify_error.cta': Record<string, never>
  'page.ledger.verify_error.title': Record<string, never>
  'page.login.email.label': Record<string, never>
  'page.login.email.placeholder': Record<string, never>
  'page.login.forgot.link': Record<string, never>
  'page.login.header.desc': Record<string, never>
  'page.login.header.title': Record<string, never>
  'page.login.meta.title': Record<string, never>
  'page.login.password.label': Record<string, never>
  'page.login.password.placeholder': Record<string, never>
  'page.login.signup.hint': Record<string, never>
  'page.login.submit.cta': Record<string, never>
  'page.login.submit.error': Record<string, never>
  'page.login.submit.pending': Record<string, never>
  'page.personas.compare.label': Record<string, never>
  'page.personas.compare.title': Record<string, never>
  'page.personas.compare_enter': Record<string, never>
  'page.personas.compare_exit': Record<string, never>
  'page.personas.filter.cta': Record<string, never>
  'page.personas.filter.title': Record<string, never>
  'page.personas.filter_all': Record<string, never>
  'page.personas.header.title': Record<string, never>
  'page.personas.list.pending': Record<string, never>
  'page.personas.list_empty.cta': Record<string, never>
  'page.personas.list_empty.desc': Record<string, never>
  'page.personas.list_empty.title': Record<string, never>
  'page.personas.meta.title': Record<string, never>
  'page.personas.pack_unknown': Record<string, never>
  'page.personas.rules.title': Record<string, never>
  'page.personas.search.placeholder': Record<string, never>
  'page.personas.triggers.title': Record<string, never>
  'page.plans.anon.hint': Record<string, never>
  'page.plans.banner_byok': Record<string, never>
  'page.plans.banner_credits': Record<string, never>
  'page.plans.banner_no_quota': Record<string, never>
  'page.plans.bonus.label': Record<string, never>
  'page.plans.byok.cta': Record<string, never>
  'page.plans.byok.desc': Record<string, never>
  'page.plans.byok.title': Record<string, never>
  'page.plans.card.badge': Record<string, never>
  'page.plans.card.cta': Record<string, never>
  'page.plans.card.hint': Record<string, never>
  'page.plans.card.label': Record<string, never>
  'page.plans.cdk.aria': Record<string, never>
  'page.plans.cdk.cta': Record<string, never>
  'page.plans.cdk.error': Record<string, never>
  'page.plans.cdk.hint': Record<string, never>
  'page.plans.cdk.placeholder': Record<string, never>
  'page.plans.cdk.success': { balance: string | number; count: number }
  'page.plans.cdk.title': Record<string, never>
  'page.plans.cdk_desc_credits': Record<string, never>
  'page.plans.cdk_desc_plan': Record<string, never>
  'page.plans.credits.label': Record<string, never>
  'page.plans.credits.value': { count: number }
  'page.plans.feature_byok': Record<string, never>
  'page.plans.feature_cost': Record<string, never>
  'page.plans.feature_reviews': { count: number }
  'page.plans.guest.hint': Record<string, never>
  'page.plans.header.desc': Record<string, never>
  'page.plans.header.title': Record<string, never>
  'page.plans.list.error': Record<string, never>
  'page.plans.list.pending': Record<string, never>
  'page.plans.list.title': Record<string, never>
  'page.plans.manual.desc': Record<string, never>
  'page.plans.manual.title': Record<string, never>
  'page.plans.meta.title': Record<string, never>
  'page.plans.price.unit': Record<string, never>
  'page.plans.progress.hint': { window: string | number }
  'page.plans.progress.label': Record<string, never>
  'page.plans.quota.error': Record<string, never>
  'page.plans.quota.pending': Record<string, never>
  'page.plans.quota.title': Record<string, never>
  'page.plans.request.hint': { email: string | number }
  'page.plans.tagline_free': Record<string, never>
  'page.plans.tagline_pro': Record<string, never>
  'page.plans.tagline_team': Record<string, never>
  'page.plans.tier.label': Record<string, never>
  'page.plans.used.label': Record<string, never>
  'page.privacy.collect.badge': Record<string, never>
  'page.privacy.collection.title': Record<string, never>
  'page.privacy.collection_apikey.label': Record<string, never>
  'page.privacy.collection_apikey_delete.desc': Record<string, never>
  'page.privacy.collection_apikey_encrypted.desc': Record<string, never>
  'page.privacy.collection_apikey_masked.desc': Record<string, never>
  'page.privacy.collection_apikey_separate.desc': Record<string, never>
  'page.privacy.collection_collected.label': Record<string, never>
  'page.privacy.collection_collected_account.desc': Record<string, never>
  'page.privacy.collection_collected_chat.desc': Record<string, never>
  'page.privacy.collection_collected_config.desc': Record<string, never>
  'page.privacy.collection_collected_images.desc': Record<string, never>
  'page.privacy.collection_collected_materials.desc': Record<string, never>
  'page.privacy.collection_collected_report.desc': Record<string, never>
  'page.privacy.collection_collected_usage.desc': Record<string, never>
  'page.privacy.collection_not.label': Record<string, never>
  'page.privacy.collection_not_fingerprint.desc': Record<string, never>
  'page.privacy.collection_not_history.desc': Record<string, never>
  'page.privacy.collection_not_identity.desc': Record<string, never>
  'page.privacy.contact.desc': Record<string, never>
  'page.privacy.contact.title': Record<string, never>
  'page.privacy.footer.desc': Record<string, never>
  'page.privacy.header.link': Record<string, never>
  'page.privacy.header.meta': Record<string, never>
  'page.privacy.header.subtitle': Record<string, never>
  'page.privacy.header.title': Record<string, never>
  'page.privacy.key.badge': Record<string, never>
  'page.privacy.meta.title': Record<string, never>
  'page.privacy.no_collect.badge': Record<string, never>
  'page.privacy.retention.badge': Record<string, never>
  'page.privacy.retention.title': Record<string, never>
  'page.privacy.retention_policy.label': Record<string, never>
  'page.privacy.retention_policy_delete.desc': Record<string, never>
  'page.privacy.retention_policy_exception.desc': Record<string, never>
  'page.privacy.retention_policy_export.desc': Record<string, never>
  'page.privacy.retention_policy_forever.desc': Record<string, never>
  'page.privacy.security.badge': Record<string, never>
  'page.privacy.security.title': Record<string, never>
  'page.privacy.security_tech.label': Record<string, never>
  'page.privacy.security_tech_cors.desc': Record<string, never>
  'page.privacy.security_tech_key.desc': Record<string, never>
  'page.privacy.security_tech_password.desc': Record<string, never>
  'page.privacy.security_tech_token.desc': Record<string, never>
  'page.privacy.security_tech_upload.desc': Record<string, never>
  'page.privacy.third_party.badge': Record<string, never>
  'page.privacy.third_party.title': Record<string, never>
  'page.privacy.third_party_llm.label': Record<string, never>
  'page.privacy.third_party_llm_ollama.desc': Record<string, never>
  'page.privacy.third_party_llm_only.desc': Record<string, never>
  'page.privacy.third_party_llm_providers.desc': Record<string, never>
  'page.privacy.third_party_llm_scope.desc': Record<string, never>
  'page.privacy.third_party_providers.label': Record<string, never>
  'page.privacy.usage.title': Record<string, never>
  'page.privacy.usage_admin.label': Record<string, never>
  'page.privacy.usage_admin_access.desc': Record<string, never>
  'page.privacy.usage_admin_audit.desc': Record<string, never>
  'page.privacy.usage_admin_unchanged.desc': Record<string, never>
  'page.privacy.usage_never.label': Record<string, never>
  'page.privacy.usage_never_copy.desc': Record<string, never>
  'page.privacy.usage_never_showcase.desc': Record<string, never>
  'page.privacy.usage_never_training.desc': Record<string, never>
  'page.privacy.usage_purpose.label': Record<string, never>
  'page.privacy.usage_purpose_isolated.desc': Record<string, never>
  'page.privacy.usage_purpose_retained.desc': Record<string, never>
  'page.privacy.usage_purpose_single.desc': Record<string, never>
  'page.privacy.use.badge': Record<string, never>
  'page.privacy.verify.badge': Record<string, never>
  'page.privacy.verify.title': Record<string, never>
  'page.privacy.verify_checkable.label': Record<string, never>
  'page.privacy.verify_checkable_byok.desc': Record<string, never>
  'page.privacy.verify_checkable_export.desc': Record<string, never>
  'page.privacy.verify_checkable_hosted.desc': Record<string, never>
  'page.privacy.verify_checkable_oss.desc': Record<string, never>
  'page.privacy.verify_checkable_selfhost.desc': Record<string, never>
  'page.progress.aggregation.title': Record<string, never>
  'page.progress.back.cta': Record<string, never>
  'page.progress.cost.label': Record<string, never>
  'page.progress.cross_exam.title': Record<string, never>
  'page.progress.done.cta': Record<string, never>
  'page.progress.done.title': Record<string, never>
  'page.progress.failed.cta': Record<string, never>
  'page.progress.failed.desc': Record<string, never>
  'page.progress.failed.title': Record<string, never>
  'page.progress.header.subtitle': Record<string, never>
  'page.progress.header.title': Record<string, never>
  'page.progress.load_error.desc': Record<string, never>
  'page.progress.load_error.title': Record<string, never>
  'page.progress.meta.title': Record<string, never>
  'page.progress.not_found.empty': Record<string, never>
  'page.progress.overall.label': Record<string, never>
  'page.progress.persona_cost.label': { amount: string | number }
  'page.progress.persona_count.label': Record<string, never>
  'page.progress.persona_done.badge': Record<string, never>
  'page.progress.persona_failed.error': Record<string, never>
  'page.progress.persona_remaining.pending': { count: number }
  'page.progress.personas.empty': Record<string, never>
  'page.progress.personas.pending': Record<string, never>
  'page.progress.personas.title': Record<string, never>
  'page.progress.poll_failure.error': { count: number }
  'page.progress.project.badge': { key: string | number }
  'page.progress.report.cta': Record<string, never>
  'page.progress.running_card.pending': Record<string, never>
  'page.progress.running_card.title': Record<string, never>
  'page.progress.selected_personas.badge': { count: number }
  'page.progress.skill.label': Record<string, never>
  'page.progress.stage.completed': Record<string, never>
  'page.progress.stage.running': Record<string, never>
  'page.progress.stage.waiting': Record<string, never>
  'page.progress.stall.hint': { count: number; interval: string | number }
  'page.progress.status.label': Record<string, never>
  'page.progress.ws_reconnect.hint': Record<string, never>
  'page.progress.ws_unavailable.hint': { count: number }
  'page.register.email.label': Record<string, never>
  'page.register.email.placeholder': Record<string, never>
  'page.register.header.desc': Record<string, never>
  'page.register.header.title': Record<string, never>
  'page.register.meta.title': Record<string, never>
  'page.register.name.label': Record<string, never>
  'page.register.name.placeholder': Record<string, never>
  'page.register.password.label': { min: string | number }
  'page.register.password.placeholder': Record<string, never>
  'page.register.signin.hint': Record<string, never>
  'page.register.submit.cta': Record<string, never>
  'page.register.submit.error': Record<string, never>
  'page.register.submit.pending': Record<string, never>
  'page.register.terms.consent': Record<string, never>
  'page.report.adaptive.empty': Record<string, never>
  'page.report.adaptive.hint': Record<string, never>
  'page.report.adaptive.title': Record<string, never>
  'page.report.adaptive_executed.label': Record<string, never>
  'page.report.adaptive_initial.label': Record<string, never>
  'page.report.adaptive_reason.label': { raw: string | number }
  'page.report.adaptive_saved.label': Record<string, never>
  'page.report.adaptive_step.hint': Record<string, never>
  'page.report.adaptive_step.label': { count: number }
  'page.report.adaptive_step.value': { persona: string | number }
  'page.report.adaptive_stop.label': Record<string, never>
  'page.report.argument.empty': Record<string, never>
  'page.report.argument.label': Record<string, never>
  'page.report.argument_con.label': Record<string, never>
  'page.report.argument_pro.label': Record<string, never>
  'page.report.body.loading': Record<string, never>
  'page.report.budget.desc': { cap: string | number; spent: string | number }
  'page.report.budget.hint': Record<string, never>
  'page.report.budget.title': Record<string, never>
  'page.report.budget_generic.desc': Record<string, never>
  'page.report.calibration.empty': Record<string, never>
  'page.report.calibration.error': Record<string, never>
  'page.report.calibration.success': Record<string, never>
  'page.report.calibration.title': Record<string, never>
  'page.report.change.badge': { stance: string | number }
  'page.report.change.desc': { reason: string | number }
  'page.report.change.empty': Record<string, never>
  'page.report.change.error': { reason: string | number }
  'page.report.change.label': { after: string | number; before: string | number; delta: string | number }
  'page.report.change_threshold.label': { after: string | number; before: string | number; delta: string | number; threshold: string | number }
  'page.report.compliance.badge': { score: string | number; status: string | number }
  'page.report.compliance.title': Record<string, never>
  'page.report.confidence.title': Record<string, never>
  'page.report.confidence.unit': { delta: string | number }
  'page.report.consensus.badge': Record<string, never>
  'page.report.consensus.desc': { variants: string | number }
  'page.report.consensus.hint': { min: string | number; total: string | number }
  'page.report.consensus.meta': { count: number }
  'page.report.consensus.title': Record<string, never>
  'page.report.consensus_single.badge': Record<string, never>
  'page.report.consensus_unknown.meta': Record<string, never>
  'page.report.cross_exam.badge': { count: number }
  'page.report.cross_exam.title': Record<string, never>
  'page.report.cross_exam_absent.desc': Record<string, never>
  'page.report.cross_exam_failures.empty': Record<string, never>
  'page.report.cross_exam_failures.label': Record<string, never>
  'page.report.cross_exam_failures.title': { count: number }
  'page.report.cross_exam_fallback.desc': { actual: string | number; requested: string | number }
  'page.report.cross_exam_legacy.desc': { count: number }
  'page.report.cross_exam_limitation.label': Record<string, never>
  'page.report.cross_exam_mode_unknown.desc': Record<string, never>
  'page.report.cross_exam_mode_unknown.label': Record<string, never>
  'page.report.cross_exam_mode_unknown.value': { raw: string | number }
  'page.report.cross_exam_skipped.desc': Record<string, never>
  'page.report.degradation.desc': { count: number; succeeded: string | number }
  'page.report.degradation.label': { names: string | number }
  'page.report.degradation_partial.desc': { count: number }
  'page.report.disagreement.hint': { text: string | number }
  'page.report.disagreements.title': Record<string, never>
  'page.report.dispute.empty': Record<string, never>
  'page.report.dispute.error': { reason: string | number }
  'page.report.dispute_empty.desc': Record<string, never>
  'page.report.dispute_empty.hint': Record<string, never>
  'page.report.ethics.title': Record<string, never>
  'page.report.ethics_score.label': Record<string, never>
  'page.report.ethics_stereotype.label': Record<string, never>
  'page.report.ethics_violations.label': { count: number }
  'page.report.evaluation.cta': Record<string, never>
  'page.report.evaluation.error': Record<string, never>
  'page.report.evaluation.meta': { passed: string | number; total: string | number }
  'page.report.evaluation.title': Record<string, never>
  'page.report.evaluation_critical.title': Record<string, never>
  'page.report.evaluation_dimension.empty': Record<string, never>
  'page.report.evaluation_dimension.label': Record<string, never>
  'page.report.evaluation_dimension.value': { id: string | number }
  'page.report.evaluation_full.cta': Record<string, never>
  'page.report.evaluation_overall.label': Record<string, never>
  'page.report.evaluation_run.error': { reason: string | number }
  'page.report.failed.desc': Record<string, never>
  'page.report.failed.empty': Record<string, never>
  'page.report.failed.hint': Record<string, never>
  'page.report.failed.label': { title: string | number }
  'page.report.failed.title': Record<string, never>
  'page.report.feedback.cta': Record<string, never>
  'page.report.feedback.desc': Record<string, never>
  'page.report.feedback.error': Record<string, never>
  'page.report.feedback.success': { section: string | number }
  'page.report.feedback.title': Record<string, never>
  'page.report.feedback_adopted.label': Record<string, never>
  'page.report.feedback_decision.label': Record<string, never>
  'page.report.feedback_fix.value': { index: string | number }
  'page.report.feedback_hours.label': Record<string, never>
  'page.report.feedback_pay.label': Record<string, never>
  'page.report.feedback_useful.cta': Record<string, never>
  'page.report.feedback_useless.cta': Record<string, never>
  'page.report.fix_personas.label': Record<string, never>
  'page.report.fix_suggestion.label': Record<string, never>
  'page.report.fix_why.label': Record<string, never>
  'page.report.fixes.title': Record<string, never>
  'page.report.gaps.title': Record<string, never>
  'page.report.gate.empty': Record<string, never>
  'page.report.gate.label': { raw: string | number }
  'page.report.gate.title': { count: number }
  'page.report.gated.cta': Record<string, never>
  'page.report.gated.desc': Record<string, never>
  'page.report.gated.hint': { count: number; notes: string | number }
  'page.report.gated.subtitle': Record<string, never>
  'page.report.gated_fix.title': Record<string, never>
  'page.report.gated_recommendation.label': Record<string, never>
  'page.report.gated_risk.label': Record<string, never>
  'page.report.gated_summary.title': Record<string, never>
  'page.report.header.badge': { mode: string | number }
  'page.report.header.subtitle': Record<string, never>
  'page.report.header.title': Record<string, never>
  'page.report.html.aria': Record<string, never>
  'page.report.html.cta': Record<string, never>
  'page.report.html.desc': { reason: string | number }
  'page.report.html.empty': Record<string, never>
  'page.report.html.error': { reason: string | number }
  'page.report.html.tooltip': Record<string, never>
  'page.report.limitation_demographic': Record<string, never>
  'page.report.limitation_feedback_loop': Record<string, never>
  'page.report.limitation_materials': Record<string, never>
  'page.report.limitation_synthetic': Record<string, never>
  'page.report.limitation_variance': Record<string, never>
  'page.report.limitations.title': Record<string, never>
  'page.report.link_detail.cta': Record<string, never>
  'page.report.link_login.cta': Record<string, never>
  'page.report.link_new_review.cta': Record<string, never>
  'page.report.load_error.desc': Record<string, never>
  'page.report.load_error.title': Record<string, never>
  'page.report.md_banner.desc': Record<string, never>
  'page.report.md_budget.hint': Record<string, never>
  'page.report.md_cross_exam.empty': Record<string, never>
  'page.report.md_cross_exam.hint': { text: string | number }
  'page.report.md_cross_exam.label': { mode: string | number }
  'page.report.md_cross_exam_absent.desc': Record<string, never>
  'page.report.md_cross_exam_legacy.desc': Record<string, never>
  'page.report.md_cross_exam_skipped.desc': Record<string, never>
  'page.report.md_evidence.label': { value: string | number }
  'page.report.md_failures.label': { count: number; list: string | number }
  'page.report.md_fix.label': Record<string, never>
  'page.report.md_gate.title': { count: number }
  'page.report.md_lang.empty': Record<string, never>
  'page.report.md_lang.value': { lang: string | number }
  'page.report.md_lang_en.value': Record<string, never>
  'page.report.md_lang_zh.value': Record<string, never>
  'page.report.md_risk.empty': Record<string, never>
  'page.report.md_risk.title': { risk: string | number }
  'page.report.md_stance.label': { value: string | number }
  'page.report.md_vote.empty': Record<string, never>
  'page.report.md_vote.label': { count: number }
  'page.report.md_vote_none.label': { count: number }
  'page.report.meta.title': Record<string, never>
  'page.report.next_test.title': Record<string, never>
  'page.report.next_test_audience.label': Record<string, never>
  'page.report.next_test_materials.label': Record<string, never>
  'page.report.next_test_tasks.label': Record<string, never>
  'page.report.panel_selection.label': { names: string | number }
  'page.report.panel_selection.title': Record<string, never>
  'page.report.pending.cta': Record<string, never>
  'page.report.pending.desc': Record<string, never>
  'page.report.pending.title': Record<string, never>
  'page.report.persona_evidence.label': Record<string, never>
  'page.report.persona_issues.label': Record<string, never>
  'page.report.personas.title': Record<string, never>
  'page.report.prediction_criterion.label': Record<string, never>
  'page.report.prediction_method.label': Record<string, never>
  'page.report.prediction_metric.hint': { direction: string | number }
  'page.report.prediction_metric.label': Record<string, never>
  'page.report.prediction_window.label': Record<string, never>
  'page.report.predictions.badge': { count: number }
  'page.report.predictions.desc': Record<string, never>
  'page.report.predictions.hint': { pct: string | number }
  'page.report.predictions.title': Record<string, never>
  'page.report.sep_colon': Record<string, never>
  'page.report.sep_enum': Record<string, never>
  'page.report.sep_semicolon': Record<string, never>
  'page.report.share.aria': Record<string, never>
  'page.report.share.badge': Record<string, never>
  'page.report.share.cta': Record<string, never>
  'page.report.share.desc': Record<string, never>
  'page.report.share.error': Record<string, never>
  'page.report.share.hint': Record<string, never>
  'page.report.share.title': Record<string, never>
  'page.report.share_copy.error': Record<string, never>
  'page.report.share_create.cta': Record<string, never>
  'page.report.share_hidden.label': Record<string, never>
  'page.report.share_item_account.label': Record<string, never>
  'page.report.share_item_calibration.label': Record<string, never>
  'page.report.share_item_cost.label': Record<string, never>
  'page.report.share_item_material.label': Record<string, never>
  'page.report.share_item_meta.label': Record<string, never>
  'page.report.share_item_report.label': Record<string, never>
  'page.report.share_revoke.cta': Record<string, never>
  'page.report.share_revoke.error': Record<string, never>
  'page.report.share_visible.label': Record<string, never>
  'page.report.stance.empty': Record<string, never>
  'page.report.stance.title': { count: number }
  'page.report.stance.value': Record<string, never>
  'page.report.summary.title': { risk: string | number }
  'page.report.summary_consensus.hint': { min: string | number; total: string | number }
  'page.report.summary_consensus.label': Record<string, never>
  'page.report.summary_evidence.label': Record<string, never>
  'page.report.summary_risk_absent.desc': Record<string, never>
  'page.report.summary_risk_missing.desc': { raw: string | number }
  'page.report.summary_stance.label': Record<string, never>
  'page.report.suppressed.desc': { count: number }
  'page.report.suppressed_no_update.desc': { count: number }
  'page.report.synthetic_banner.desc': Record<string, never>
  'page.report.synthetic_banner.title': Record<string, never>
  'page.report.threshold.error': { source: string | number }
  'page.report.unknown_level.value': { raw: string | number }
  'page.report.usage.desc': { calls: string | number; input: string | number; output: string | number }
  'page.report.usage.hint': Record<string, never>
  'page.report.vote.badge': { count: number }
  'page.report.vote.empty': Record<string, never>
  'page.report.vote.title': Record<string, never>
  'page.report.vote_threshold.badge': { count: number; threshold: string | number }
  'page.report.vote_unchanged.desc': Record<string, never>
  'page.reset.confirm.label': Record<string, never>
  'page.reset.confirm.placeholder': Record<string, never>
  'page.reset.done.cta': Record<string, never>
  'page.reset.done.hint': Record<string, never>
  'page.reset.done.success': Record<string, never>
  'page.reset.header.title': Record<string, never>
  'page.reset.meta.title': Record<string, never>
  'page.reset.no_token.error': Record<string, never>
  'page.reset.no_token.link': Record<string, never>
  'page.reset.password.label': { min: string | number }
  'page.reset.password.placeholder': Record<string, never>
  'page.reset.submit.cta': Record<string, never>
  'page.reset.submit.error': Record<string, never>
  'page.settings.account_card.desc': { email: string | number }
  'page.settings.account_card.title': Record<string, never>
  'page.settings.api_base.hint': Record<string, never>
  'page.settings.api_base.label': Record<string, never>
  'page.settings.api_base.placeholder': Record<string, never>
  'page.settings.api_base_compat.placeholder': Record<string, never>
  'page.settings.byok.desc': Record<string, never>
  'page.settings.byok.error': Record<string, never>
  'page.settings.byok.hint': Record<string, never>
  'page.settings.byok.title': Record<string, never>
  'page.settings.cdk.cta': Record<string, never>
  'page.settings.cdk.desc': Record<string, never>
  'page.settings.cdk.error': Record<string, never>
  'page.settings.cdk.hint': Record<string, never>
  'page.settings.cdk.placeholder': Record<string, never>
  'page.settings.cdk.success': { balance: string | number; count: number }
  'page.settings.cdk.title': Record<string, never>
  'page.settings.cdk_guest.hint': Record<string, never>
  'page.settings.cdk_plan.desc': Record<string, never>
  'page.settings.data.desc': Record<string, never>
  'page.settings.data.title': Record<string, never>
  'page.settings.delete_account.cta': Record<string, never>
  'page.settings.delete_account.error': Record<string, never>
  'page.settings.delete_confirm.cta': Record<string, never>
  'page.settings.delete_confirm.desc': Record<string, never>
  'page.settings.delete_confirm.label': { phrase: string | number }
  'page.settings.delete_done.desc': { keys: string | number; reviews: string | number }
  'page.settings.delete_done.hint': Record<string, never>
  'page.settings.delete_password.label': Record<string, never>
  'page.settings.export.cta': Record<string, never>
  'page.settings.export.error': Record<string, never>
  'page.settings.footer.link': Record<string, never>
  'page.settings.group_account.label': Record<string, never>
  'page.settings.group_data.label': Record<string, never>
  'page.settings.group_model.label': Record<string, never>
  'page.settings.group_usage.label': Record<string, never>
  'page.settings.guest_card.cta': Record<string, never>
  'page.settings.guest_card.desc': Record<string, never>
  'page.settings.guest_card.title': Record<string, never>
  'page.settings.header.desc': Record<string, never>
  'page.settings.header.title': Record<string, never>
  'page.settings.key_input.aria': Record<string, never>
  'page.settings.key_input.placeholder': Record<string, never>
  'page.settings.key_input_compat.placeholder': Record<string, never>
  'page.settings.key_item.error': Record<string, never>
  'page.settings.key_item.meta': { time: string | number }
  'page.settings.key_privacy.title': Record<string, never>
  'page.settings.meta.title': Record<string, never>
  'page.settings.model_id.error': Record<string, never>
  'page.settings.model_id.hint': Record<string, never>
  'page.settings.model_id.label': Record<string, never>
  'page.settings.model_id.placeholder': Record<string, never>
  'page.settings.model_id_compat.placeholder': Record<string, never>
  'page.settings.multimodal.desc': Record<string, never>
  'page.settings.name.error': Record<string, never>
  'page.settings.name.hint': Record<string, never>
  'page.settings.name.label': Record<string, never>
  'page.settings.name.placeholder': Record<string, never>
  'page.settings.name.success': Record<string, never>
  'page.settings.password.cta': Record<string, never>
  'page.settings.password.error': Record<string, never>
  'page.settings.password.hint': Record<string, never>
  'page.settings.password.label': Record<string, never>
  'page.settings.password.success': Record<string, never>
  'page.settings.password_confirm.placeholder': Record<string, never>
  'page.settings.password_current.placeholder': Record<string, never>
  'page.settings.password_new.placeholder': Record<string, never>
  'page.settings.privacy_device.desc': Record<string, never>
  'page.settings.privacy_device.label': Record<string, never>
  'page.settings.privacy_optout.desc': Record<string, never>
  'page.settings.privacy_optout.hint': Record<string, never>
  'page.settings.privacy_optout.label': Record<string, never>
  'page.settings.privacy_selfhost.desc': Record<string, never>
  'page.settings.privacy_source.desc': Record<string, never>
  'page.settings.privacy_use.desc': Record<string, never>
  'page.settings.privacy_use.label': Record<string, never>
  'page.settings.privacy_who.desc': Record<string, never>
  'page.settings.privacy_who.label': Record<string, never>
  'page.settings.provider_anthropic.desc': Record<string, never>
  'page.settings.provider_anthropic.label': Record<string, never>
  'page.settings.provider_openai.desc': Record<string, never>
  'page.settings.provider_openai.label': Record<string, never>
  'page.settings.revoke.confirm': Record<string, never>
  'page.settings.revoke.cta': Record<string, never>
  'page.settings.revoke.desc': Record<string, never>
  'page.settings.revoke.hint': Record<string, never>
  'page.settings.revoke.label': Record<string, never>
  'page.settings.save_key.cta': Record<string, never>
  'page.settings.save_key.error': Record<string, never>
  'page.settings.save_key.success': Record<string, never>
  'page.settings.section_account.desc': Record<string, never>
  'page.settings.section_account.tab': Record<string, never>
  'page.settings.section_account.title': Record<string, never>
  'page.settings.section_account_guest.desc': Record<string, never>
  'page.settings.section_data.desc': Record<string, never>
  'page.settings.section_data.tab': Record<string, never>
  'page.settings.section_data.title': Record<string, never>
  'page.settings.section_model.desc': Record<string, never>
  'page.settings.section_model.tab': Record<string, never>
  'page.settings.section_model.title': Record<string, never>
  'page.settings.section_usage.desc': Record<string, never>
  'page.settings.section_usage.tab': Record<string, never>
  'page.settings.section_usage.title': Record<string, never>
  'page.settings.test.cta': Record<string, never>
  'page.settings.test.error': Record<string, never>
  'page.settings.test.meta': { sample: string | number }
  'page.settings.test.success': Record<string, never>
  'page.settings.usage.hint': { window: string | number }
  'page.settings.usage.title': Record<string, never>
  'page.settings.usage_bonus.label': Record<string, never>
  'page.settings.usage_cost.label': Record<string, never>
  'page.settings.usage_credits.label': Record<string, never>
  'page.settings.usage_credits.unit': Record<string, never>
  'page.settings.usage_reviews.hint': { limit: string | number; used: string | number }
  'page.settings.usage_reviews.label': Record<string, never>
  'page.settings.usage_server_cost.label': Record<string, never>
  'page.settings.usage_tokens.hint': { limit: string | number; used: string | number }
  'page.settings.usage_tokens.label': Record<string, never>
  'page.settings.usage_tokens.unit': Record<string, never>
  'page.shared.agreed.title': Record<string, never>
  'page.shared.evidence_quality.label': { value: string | number }
  'page.shared.fixes.title': { count: number }
  'page.shared.footer.cta': Record<string, never>
  'page.shared.footer.desc': Record<string, never>
  'page.shared.gaps.title': Record<string, never>
  'page.shared.header.meta': { count: number }
  'page.shared.header.title': Record<string, never>
  'page.shared.load_error.desc': Record<string, never>
  'page.shared.load_error.title': Record<string, never>
  'page.shared.meta.title': Record<string, never>
  'page.shared.notes.title': { count: number }
  'page.shared.questioned.title': Record<string, never>
  'page.shared.release_risk.label': { value: string | number }
  'page.shared.revoked.cta': Record<string, never>
  'page.shared.revoked.desc': Record<string, never>
  'page.shared.revoked.title': Record<string, never>
  'page.shared.share_note.badge': Record<string, never>
  'page.shared.suggestion.label': { text: string | number }
  'page.shared.summary.title': Record<string, never>
  'page.skills.card.cta': Record<string, never>
  'page.skills.card_disabled.hint': Record<string, never>
  'page.skills.card_task_types.label': { count: number }
  'page.skills.card_use_cases.label': Record<string, never>
  'page.skills.header.subtitle': Record<string, never>
  'page.skills.header.title': Record<string, never>
  'page.skills.list.empty': Record<string, never>
  'page.skills.list_error.cta': Record<string, never>
  'page.skills.list_error.desc': { reason: string | number }
  'page.skills.list_error.title': Record<string, never>
  'page.skills.meta.title': Record<string, never>
  'page.task_types.card.cta': Record<string, never>
  'page.task_types.card_score.label': Record<string, never>
  'page.task_types.card_stance.label': Record<string, never>
  'page.task_types.category_community.label': Record<string, never>
  'page.task_types.category_development.label': Record<string, never>
  'page.task_types.category_operations.label': Record<string, never>
  'page.task_types.category_other.label': Record<string, never>
  'page.task_types.category_product.label': Record<string, never>
  'page.task_types.count.total': { count: number }
  'page.task_types.detail.error': Record<string, never>
  'page.task_types.detail_error.hint': Record<string, never>
  'page.task_types.detail_error.title': Record<string, never>
  'page.task_types.filter.tab': Record<string, never>
  'page.task_types.header.error': Record<string, never>
  'page.task_types.header.loading': Record<string, never>
  'page.task_types.header.title': Record<string, never>
  'page.task_types.list.empty': Record<string, never>
  'page.task_types.list.error': Record<string, never>
  'page.task_types.list_error.cta': Record<string, never>
  'page.task_types.list_error.desc': { reason: string | number }
  'page.task_types.list_error.title': Record<string, never>
  'page.task_types.meta.title': Record<string, never>
  'page.task_types.modal.title': Record<string, never>
  'page.task_types.modal_base.label': Record<string, never>
  'page.task_types.modal_desc.label': Record<string, never>
  'page.task_types.modal_id.label': Record<string, never>
  'page.task_types.modal_name.label': Record<string, never>
  'page.task_types.modal_score.label': Record<string, never>
  'page.task_types.modal_stance.label': Record<string, never>
  'page.terms.account.title': Record<string, never>
  'page.terms.account_duty.label': Record<string, never>
  'page.terms.account_duty_lawful.desc': Record<string, never>
  'page.terms.account_duty_password.desc': Record<string, never>
  'page.terms.account_duty_rights.desc': Record<string, never>
  'page.terms.account_enforcement.label': Record<string, never>
  'page.terms.account_enforcement_appeal.desc': Record<string, never>
  'page.terms.account_enforcement_suspend.desc': Record<string, never>
  'page.terms.account_forbidden.label': Record<string, never>
  'page.terms.account_forbidden_bypass.desc': Record<string, never>
  'page.terms.account_forbidden_farming.desc': Record<string, never>
  'page.terms.account_forbidden_probing.desc': Record<string, never>
  'page.terms.account_forbidden_resale.desc': Record<string, never>
  'page.terms.availability.title': Record<string, never>
  'page.terms.availability_data.label': Record<string, never>
  'page.terms.availability_data_backup.desc': Record<string, never>
  'page.terms.availability_data_copy.desc': Record<string, never>
  'page.terms.availability_data_export.desc': Record<string, never>
  'page.terms.availability_sla.label': Record<string, never>
  'page.terms.availability_sla_asis.desc': Record<string, never>
  'page.terms.availability_sla_maintenance.desc': Record<string, never>
  'page.terms.availability_sla_solo.desc': Record<string, never>
  'page.terms.availability_sla_upstream.desc': Record<string, never>
  'page.terms.billing.title': Record<string, never>
  'page.terms.billing_payment.label': Record<string, never>
  'page.terms.billing_payment_byok.desc': Record<string, never>
  'page.terms.billing_payment_manual.desc': Record<string, never>
  'page.terms.billing_payment_quota.desc': Record<string, never>
  'page.terms.billing_refund.label': Record<string, never>
  'page.terms.billing_refund_manual.desc': Record<string, never>
  'page.terms.billing_refund_used.desc': Record<string, never>
  'page.terms.contact.hint': Record<string, never>
  'page.terms.filing.label': Record<string, never>
  'page.terms.header.link': Record<string, never>
  'page.terms.header.meta': Record<string, never>
  'page.terms.header.subtitle': Record<string, never>
  'page.terms.header.title': Record<string, never>
  'page.terms.ip.title': Record<string, never>
  'page.terms.ip_ours.label': Record<string, never>
  'page.terms.ip_ours_oss.desc': Record<string, never>
  'page.terms.ip_ours_personas.desc': Record<string, never>
  'page.terms.ip_yours.label': Record<string, never>
  'page.terms.ip_yours_free_use.desc': Record<string, never>
  'page.terms.ip_yours_no_training.desc': Record<string, never>
  'page.terms.ip_yours_own.desc': Record<string, never>
  'page.terms.liability.title': Record<string, never>
  'page.terms.liability_cap.label': Record<string, never>
  'page.terms.liability_cap_amount.desc': Record<string, never>
  'page.terms.liability_cap_indirect.desc': Record<string, never>
  'page.terms.liability_change.label': Record<string, never>
  'page.terms.liability_change_accept.desc': Record<string, never>
  'page.terms.liability_change_notice.desc': Record<string, never>
  'page.terms.liability_nature.label': Record<string, never>
  'page.terms.liability_nature_mandatory.desc': Record<string, never>
  'page.terms.liability_nature_unreviewed.desc': Record<string, never>
  'page.terms.meta.title': Record<string, never>
  'page.terms.related.desc': Record<string, never>
  'page.terms.service.title': Record<string, never>
  'page.terms.service_not.label': Record<string, never>
  'page.terms.service_not_advice.desc': Record<string, never>
  'page.terms.service_not_research.desc': Record<string, never>
  'page.terms.service_not_usertest.desc': Record<string, never>
  'page.terms.service_provides.label': Record<string, never>
  'page.terms.service_provides_byok.desc': Record<string, never>
  'page.terms.service_provides_hypothesis.desc': Record<string, never>
  'page.terms.service_provides_review.desc': Record<string, never>
  'page.terms.termination.desc': Record<string, never>
  'page.terms.termination.title': Record<string, never>
  'page.tutorial.count.unknown': Record<string, never>
  'page.tutorial.count.with_number': { count: number }
  'page.tutorial.filetype_community.desc': Record<string, never>
  'page.tutorial.filetype_community.title': Record<string, never>
  'page.tutorial.filetype_crowdfunding.desc': Record<string, never>
  'page.tutorial.filetype_crowdfunding.title': Record<string, never>
  'page.tutorial.filetype_devlog.desc': Record<string, never>
  'page.tutorial.filetype_devlog.title': Record<string, never>
  'page.tutorial.filetype_gdd.desc': Record<string, never>
  'page.tutorial.filetype_gdd.title': Record<string, never>
  'page.tutorial.filetype_localization.desc': Record<string, never>
  'page.tutorial.filetype_localization.title': Record<string, never>
  'page.tutorial.filetype_store.desc': Record<string, never>
  'page.tutorial.filetype_store.title': Record<string, never>
  'page.tutorial.filetypes.desc': Record<string, never>
  'page.tutorial.filetypes.title': Record<string, never>
  'page.tutorial.flow.desc': Record<string, never>
  'page.tutorial.flow.step': { n: string | number }
  'page.tutorial.flow.title': Record<string, never>
  'page.tutorial.header.subtitle': Record<string, never>
  'page.tutorial.header.title': Record<string, never>
  'page.tutorial.limits.hint': { image_ext: string | number; image_max: string | number; text_ext: string | number; text_max: string | number }
  'page.tutorial.materials.desc': Record<string, never>
  'page.tutorial.materials.title': Record<string, never>
  'page.tutorial.materials_optional.label': Record<string, never>
  'page.tutorial.materials_required.label': Record<string, never>
  'page.tutorial.materials_task_type.label': Record<string, never>
  'page.tutorial.meta.title': Record<string, never>
  'page.tutorial.method.badge': Record<string, never>
  'page.tutorial.method_example.desc': Record<string, never>
  'page.tutorial.method_example.title': Record<string, never>
  'page.tutorial.method_example_first_use.hint': Record<string, never>
  'page.tutorial.method_file.desc': Record<string, never>
  'page.tutorial.method_file.title': Record<string, never>
  'page.tutorial.method_file_any_doc.hint': Record<string, never>
  'page.tutorial.method_file_autofill.hint': Record<string, never>
  'page.tutorial.method_file_editable.hint': Record<string, never>
  'page.tutorial.method_file_formats.hint': Record<string, never>
  'page.tutorial.method_manual.desc': Record<string, never>
  'page.tutorial.method_manual.title': Record<string, never>
  'page.tutorial.method_manual_fields.hint': Record<string, never>
  'page.tutorial.method_manual_when.hint': Record<string, never>
  'page.tutorial.result_calibration.desc': Record<string, never>
  'page.tutorial.result_calibration.label': Record<string, never>
  'page.tutorial.result_issues.desc': Record<string, never>
  'page.tutorial.result_issues.label': Record<string, never>
  'page.tutorial.result_persona.desc': Record<string, never>
  'page.tutorial.result_persona.label': Record<string, never>
  'page.tutorial.result_risk.desc': Record<string, never>
  'page.tutorial.result_risk.label': Record<string, never>
  'page.tutorial.result_stance.desc': Record<string, never>
  'page.tutorial.result_stance.label': Record<string, never>
  'page.tutorial.results.desc': Record<string, never>
  'page.tutorial.results.title': Record<string, never>
  'page.tutorial.start.cta': Record<string, never>
  'page.tutorial.step_edit.desc': Record<string, never>
  'page.tutorial.step_edit.label': Record<string, never>
  'page.tutorial.step_panel.desc': Record<string, never>
  'page.tutorial.step_panel.label': Record<string, never>
  'page.tutorial.step_select_type.desc': Record<string, never>
  'page.tutorial.step_select_type.label': Record<string, never>
  'page.tutorial.step_upload.desc': Record<string, never>
  'page.tutorial.step_upload.label': Record<string, never>
  'page.tutorial.upload.desc': Record<string, never>
  'page.tutorial.upload.hint': Record<string, never>
  'page.tutorial.upload.title': Record<string, never>
  'page.verify.confirm.error': Record<string, never>
  'page.verify.fail.hint': Record<string, never>
  'page.verify.fail.link': Record<string, never>
  'page.verify.fail.title': Record<string, never>
  'page.verify.meta.title': Record<string, never>
  'page.verify.no_token.error': Record<string, never>
  'page.verify.ok.cta': Record<string, never>
  'page.verify.ok.title': Record<string, never>
  'page.verify.pending.loading': Record<string, never>
}

/** 每条富文本 key 的 slot 名。少一个 / 多一个 / 拼错都是编译错误。 */
export interface MessageSlots {
  'page.ask.project_delete_confirm.confirm': 'name'
  'page.ask.review_delete_confirm.confirm': 'name'
  'page.create.confirm_material.meta': 'filled'
  'page.create.dropzone.cta': 'click'
  'page.create.pack_intro.desc': 'name'
  'page.forgot.signin.hint': 'link'
  'page.history.confirm_dialog.desc': 'name' | 'note'
  'page.login.signup.hint': 'link'
  'page.plans.anon.hint': 'register'
  'page.plans.banner_byok': 'mode'
  'page.plans.banner_credits': 'mode'
  'page.plans.banner_no_quota': 'mode'
  'page.plans.credits.value': 'unit'
  'page.plans.feature_reviews': 'n'
  'page.plans.request.hint': 'mail'
  'page.register.signin.hint': 'link'
  'page.register.terms.consent': 'privacy' | 'terms'
  'page.report.predictions.hint': 'emph'
  'page.report.share.desc': 'emph'
  'page.settings.delete_confirm.desc': 'strong'
  'page.settings.privacy_source.desc': 'privacy'
  'page.settings.privacy_who.desc': 'code'
  'page.settings.revoke.desc': 'strong'
  'page.shared.evidence_quality.label': 'v'
  'page.shared.release_risk.label': 'v'
  'page.terms.related.desc': 'privacy'
}

/** 参与本次生成的资源文件（调试用，改动这行说明有人加/删了资源文件）。 */
export const RESOURCE_FILES = [
  'catalog.brand.ts',
  'catalog.eval_dimension.ts',
  'catalog.material.ts',
  'catalog.mode.ts',
  'catalog.persona_pack.ts',
  'catalog.skill.ts',
  'catalog.task_type.ts',
  'common.action.ts',
  'common.calibration_gauge.ts',
  'common.meta.ts',
  'common.persona_card.ts',
  'common.persona_radar.ts',
  'common.ui.ts',
  'common.validate.ts',
  'enum.behavior_axis.ts',
  'enum.calibration.ts',
  'enum.cross_exam_mode.ts',
  'enum.direction.ts',
  'enum.disabled_reason.ts',
  'enum.ethics_severity.ts',
  'enum.evidence_quality.ts',
  'enum.gate_reason.ts',
  'enum.mode_badge.ts',
  'enum.persona_status.ts',
  'enum.primary_stance.ts',
  'enum.rebuttal_status.ts',
  'enum.release_risk.ts',
  'enum.review_status.ts',
  'enum.severity.ts',
  'enum.stereotype_risk.ts',
  'enum.stop_reason.ts',
  'enum.verdict.ts',
  'error.api.ts',
  'error.fetch.ts',
  'error.store.ts',
  'error.ws.ts',
  'nav.account.ts',
  'nav.footer.ts',
  'nav.item.ts',
  'nav.menu.ts',
  'nav.session.ts',
  'nav.verify_banner.ts',
  'page.ask.ts',
  'page.create.ts',
  'page.evaluation.ts',
  'page.forgot.ts',
  'page.history.ts',
  'page.landing.ts',
  'page.ledger.ts',
  'page.login.ts',
  'page.personas.ts',
  'page.plans.ts',
  'page.privacy.ts',
  'page.progress.ts',
  'page.register.ts',
  'page.report.ts',
  'page.reset.ts',
  'page.settings.ts',
  'page.shared.ts',
  'page.skills.ts',
  'page.task_types.ts',
  'page.terms.ts',
  'page.tutorial.ts',
  'page.verify.ts',
] as const
