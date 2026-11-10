# Report Authoring Validation

日期：2026-11-03。状态：设计用例，不是执行结果。
父设计：[authoring](report-authoring-v2.md)；唯一任务状态：[tasks](tasks.md#w6-authoring-v2)。
连续性架构：[daily/weekly](report-continuity.md)。RA41-72 是本次新增设计场景，不是测试通过记录。
复用现有 pytest、Django test client、Node测试和Ego，不新增另一套验证平台。

## 0. Layered User-Visible Coverage

2026-11-03用户批准实施前再次核对。case编号代表验收要求，只有具体执行证据才可标通过；
不能用“72个已设计场景”推导“所有功能已测试”。默认pytest不包含
project_management/provider_sync，执行必须显式给出目标路径。

| 层 | 验证边界 | 用户可见功能 / 主要RA |
| --- | --- | --- |
| L0 Pure | fragment/schema、日期/排序/状态规则、URL和额度拒绝，真实纯函数 | 内容/颜色/链接不丢，状态非AI、独立票行与稳定累积：01-03、41、46-51、54-57、65/66/69 |
| L1 Storage / Service | 实际service+临时磁盘/受控Git/ORM，原子写入、hash/CAS和恢复 | Save/reopen、模板版本、删除结果、baseline/跨日继承：04-06、20-28、43-46、52/53、59-65/68 |
| L2 HTTP / UI Contract | Django authenticated requests/forms、CSRF、载荷版本、错误/dirty状态 | 用户创建模板/系列、生成/保存/预览/定稿、失败不丢输入：12-19、29-34、44/53/58-61 |
| L3 Mounted Browser | 真正编辑器+本地资产+真实HTTP/存储，外部provider/模型用受控fake | 所见即所得、色板、高亮、#浮窗三选项、IME/键盘/撤销、长文本：07-11、36/37、41/42、45/67 |
| L4 Joined / External | 同候选跨日跨周全过程；获准时实际来源、模型和接收客户端 | 模板->AI候选->人工编辑->save->finalize->翌日/新周，复制/下载：35-40、63/64/67/68；定时70-72单独资格 |

用户界面成功链和失败链必须都到达对应层，不以mock DOM或纯函数通过替代mounted行为。
每项“用户可见完成”至少有L2或L3的对应证据；需要持久化的还必须具备L1。
涉及外部服务的最终能力若未授权/未就绪，则标未验证，不能删除case或用fake冒充。
首个CONTENT仅关闭自己的L0/L1部分；不宣称编辑器、补全、模板设计器或完整日报已交付。
项目当前桌面Chrome/Ego优先，手机/其他浏览器仍是已确认backlog，不混入当前完成口径。

2026-11-05用户批准的[交付重排](delivery-sequence.md)先补DAILY的实际两天链，
再补变化工单增量、ASSIST及导出样本，最后执行原整周。
RA43/45/52/63的补充消费者为
`ui_web/tests/test_report_daily_ui_browser.py::TestReportDailyUiBrowser::test_shouldCarryEditablePersistentReferenceIntoActualNextDay`：
周一已保存/定稿的常驻引用在真正创建的周二仍可编辑相邻文字/颜色，保存重开定稿；
周一fragment和publication不变，重复准备不重复工作，历史引用不重新上游查询。
该名称是当前实施目标，实际结果只由tasks及回执证明。
原整周的每日同源输入不证明真实增量，需另有accepted A -> captured B/failure -> captured C
的输入/接受/报告读取证明；不因此改写原周模拟或削减任何安全/外部资格要求。

## 1. Authority Matrix

| Contract / risk | Producer | Consumers | 必须拒绝的反例 |
| --- | --- | --- | --- |
| PM-EDIT-V2 / high | `app/domain/report_authoring.py`、`services/report_drafts.py` | `storage/report_drafts.py`、`reporting/html.py`、`ui_web/report_forms.py`、`static/js/report_editor/` | RA01-06/33：未知节点、source目标、旧hash重写、stale save、dirty copy |
| PM-TEMPLATE-V1 / high | `services/report_templates.py`、`out/orm_report_templates.py` | `ui_web/facades/report_templates.py`、`reporting/template_compiler.py`、draft/AI/publication | RA21-28：模板替换、跨owner、missing data、动态latest解析、额度与事务分裂 |
| PM-COMPLETION / high | `services/report_completion.py`、`provider_sync/app/api/references.py` | `ui_web/views/report_completion.py`、editor、schema2 receipt保存、最终渲染 | RA07-20：跨scope、无权限、错误principal、晚响应、伪回执、不同时间混字段 |
| PM-AI-DRAFT / high | `services/report_assists.py`、`out/report_ai_task.py` | `ui_web/views/report_assists.py`、editor、draft保存、`report_publication.py` | RA29-32/39：wrong run/profile/target、没证据编造、取消后迟到、未接受即保存 |
| PM-PUBLICATION-V2 / high | draft/template/receipt规范 -> existing publication writer | 六文件namespace validator、resume、download、HTML/Markdown/Excel/clipboard | RA05/06/34-38：schema1破坏、重复提交、未持久化即成功、导出漏字段/真实时间 |
| PM-PAINT-V2 / high | `app/domain/report_authoring.py`、`static/js/report_editor/fragment_codec.js` | `storage/report_drafts.py`、`reporting/fragment_renderers.py`、publication reader、clipboard/export | RA41-46/66/67：颜色/高亮/链接格式丢失、只改颜色未保存、Markdown有损回写 |
| PM-CONTINUITY / high | `services/report_continuity.py`、`app/domain/report_continuity.py` | `report_drafts.py`、`reporting/meeting_matrix.py`、`report_publication_reads.py`、新日准备和period view | RA43/47-57/63-69：错误基线、错票/跨stage继承、旧日状态倒填、人工修改被AI覆盖 |
| PM-PREPARE / high | `services/report_preparation.py`、原`project_runs.py` | `ui_web/views/report_daily.py`、`ui_web/facades/report_daily.py`、`project_run`CLI、`storage/report_preparations.py`、原worker | RA52/53/58-64：同日重复派发、旧command重选基线、Save假报正式baseline |
| PM-SCHEDULE / high, deferred W7 | 获准调度adapter | 同一preparation API、原operation journal和部署CLI | RA70-72：默认激活、手动race、missed回填、跨午夜改原日期、自动finalize |

每个生产接口有当前调用者或明确计划调用者；不将 `tests/` 作为唯一 consumer。
原 W6.HTML.SOURCE/EDIT/FINALIZE、W7运行状态仍有自己的权威，不被本表取代。

## 2. Consumer Universe

| 类别 | 裁定与边界 |
| --- | --- |
| public API | applies：`project_management/app/api/{reports,report_templates,report_completion,report_assists}.py`、provider references |
| internal facade | applies：report/template/assist services与 `ui_web/facades/`，只经公共API |
| UI | applies：原report editor、template library、#菜单、AI面板、locale和URL wiring |
| export/report | applies：HTML/plain/copy；Markdown/Excel保持原任务，新的片段/模板须进入其验收 |
| audit/log/event | applies：模板command、draft history、AI receipt；不记凭据或未授权工单原文 |
| validation script | applies：既有size/whitespace、pytest、Node、Ego；不修改共享checker来放宽门槛 |
| migration/schema | applies：新增模板ORM migration；draft/publication兼容reader，生产migration需授权 |
| background job | applies：原run观察/取消和手动preparation worker；W7.SCHEDULE deferred，默认禁用，不使页面GET发起模型 |
| cache/index/search | applies：有界private限流/临时lookup；无全站索引，无缓存作为权限authority |
| external artifact | applies：同六文件report publication，固定第三方静态包；无remote push |
| CLI/admin | applies：`project_run`的versioned preparation输入与同日去重；新模板CLI非首批，旧schema1解释不变 |
| docs/operator | applies：本change与current-baseline guide、README；旧Chiplet研究只导航 |
| fake/fixture | applies：已有report fixtures扩展；不加载.env，不给合成HSD命名为真实资格 |

## 3. Named Cases

RA为本附录唯一case前缀。下表函数名是设计目标；已落地测试映射见本节末尾，
不能按某个目标文件存在就宣称对应场景通过。运行结果仍只在tasks维护。

| ID | 目标文件 / test名 | 反例与可观察结果 |
| --- | --- | --- |
| RA01 | `project_management/tests/test_report_authoring_content.py::test_legacy_text_remains_literal` | 旧 `**x**/<script>` 只按字面展示；读旧revision零写入且hash不变 |
| RA02 | 同文件 `test_unknown_nodes_and_unsafe_links_are_rejected` | iframe/style/jsURL/额外字段拒绝；合法中文/长word保留 |
| RA03 | 同文件 `test_protected_data_targets_cannot_be_edited` | 修改status、coverage、owner_confirmed或伪造slot拒绝；原snapshot不变 |
| RA04 | `test_report_authoring_migration.py::test_schema2_save_replays_original_command` | 相同command lost-response仅一revision；不同payload409；旧expected revision不覆盖 |
| RA05 | 同文件 `test_v2_publication_recovery_uses_original_six_files` | 断在Git提交前后，resume仍同6文件/hash/commit，模板库修改不能重渲染 |
| RA06 | 同文件 `test_v1_publication_download_is_not_rerendered` | 启用新renderer后旧edition原字节仍相同；坏version/新文件名拒绝 |
| RA07 | `ui_web/tests/report_editor_test.mjs::hash_trigger_and_three_formats` | #ID生成三项，上下/Enter仅替换token，去#、链接/title/@owner、单undo |
| RA08 | 同文件 `removed_triggers_do_not_query` | 裸ID、URL、hotkey、按钮不存在或不发补全请求；页面GET/模板切换0query |
| RA09 | 同文件 `hash_headings_and_code_do_not_trigger` | `# 标题`、`##`、code、link、只读block不查；记录首批支持的空白边界 |
| RA10 | 同文件 `composition_and_focus_are_preserved` | IME Enter不接受；loading/error Enter不提交外层form；Esc保持正文 |
| RA11 | 同文件 `late_response_cannot_replace_new_token` | 先A后B、selection变化、销毁重建、切草稿后A迟到，0错误插入 |
| RA12 | `project_management/tests/test_report_completion.py::test_stage_routes_without_provider_input` | Jira scope/profile与HSD profile(None scope)路由同API，不接受caller endpoint |
| RA13 | 同文件 `test_provider_mismatch_is_not_fallback` | Jira Stage输入纯数字被拒；不尝试HSD或另一凭据 |
| RA14 | 同文件 `test_absent_member_never_fetches_outside_scope` | 完整成员缺ID，显示“范围外或编号有误”，禁止任何单票GET，未知全站存在性 |
| RA15 | 同文件 `test_incomplete_membership_is_not_outside` | typed proof缺失/unknown返回scope_unverified；不能用rows缺失证明outside；summary pending的已知成员仍可查 |
| RA16 | `provider_sync/tests/test_reference_lookup.py::test_unavailable_item_does_not_leak_existence` | 上游404/不可披露403统一item_unavailable，不返回旧title/owner |
| RA17 | 同文件 `test_auth_endpoint_and_principal_are_rechecked` | owner、credential origin或principal变化先拒绝；不关TLS/不换PAT |
| RA18 | `test_report_completion.py::test_missing_owner_disables_third_option_only` | unassigned/unknown区分，row1/2可用，row3禁用，无@None；title缺失只允许有效row1 |
| RA19 | 同文件 `test_timeout_and_rate_limit_keep_original_text` | 10s/30次边界、Retry-After、超响应界限，0自动重试/模型调用 |
| RA20 | `test_report_authoring_content.py::test_reference_receipt_is_bound_to_actor_and_snapshot` | 伪签名、foreign target、过期/改变fragment不能作为真实源值；人工转换明确标注 |
| RA21 | `test_report_template_library.py::test_user_creates_template_without_source_or_ai` | 空白/复制内置创建，不读工单；不同owner查不到；结构/文字由用户编辑 |
| RA22 | 同文件 `test_template_versions_are_immutable` | v2保存后旧draft仍绑定v1；同command replay，stale/template hash409 |
| RA23 | `test_report_template_compilation.py::test_missing_required_data_blocks_prevents_use` | 库可保留未就绪版本；v2缺/重复matrix不可ready/prepare，旧v1不能作为连续性回退；漏pending/action/元数据必须拒绝 |
| RA24 | 同文件 `test_slots_are_filled_without_executing_template_text` | slot UUID稳定；`{{code}}`/Django tags只是文字；未知data source不执行 |
| RA25 | `test_report_template_library.py::test_template_usage_and_revision_commit_atomically` | revision/command/head/usage任一失败全回滚；归档仍计限额，无硬删除 |
| RA26 | 同文件 `test_archive_and_cross_project_copy_preserve_history` | 只允许双owner结构复制；归档前use可按原command恢复，归档后的新command不能选择，stage锁内不回写DB |
| RA27 | `test_report_template_compilation.py::test_draft_pins_complete_template_snapshot` | template library不可用/更名/新head不改变旧draft；新unknown renderer明确拒绝 |
| RA28 | 同文件 `test_template_layout_does_not_recompute_analysis` | 改顺序/固定文字后source_hash、summary refs不变；0模型调用 |
| RA29 | `test_report_assists.py::test_manual_work_is_independent_of_ai_readiness` | 运行时不可用或profile未声明，人工create/edit/save可用；普通render 0次AI调用 |
| RA30 | 同文件 `test_authoring_profile_and_result_are_bound` | 错误runStore/scope/profile/hash、未知target、扩大context、恶意URL输出拒绝 |
| RA31 | 同文件 `test_insufficient_evidence_keeps_slot_pending` | 模型缺证据结果不编内容；可保存草稿，required slot未填禁止finalize |
| RA32 | 同文件 `test_apply_is_provisional_until_saved` | 接受到dirty不advance summary/Git；期间新revision使候选stale且原文保留 |
| RA33 | `ui_web/tests/test_report_authoring_views.py::test_auth_csrf_and_errors_preserve_editor_state` | 无auth/foreign/CSRF、POST unknown keys拒绝；错误返回输入仍在，安全en/zh |
| RA34 | 同文件 `test_copy_and_finalize_use_saved_revision` | 未保存修改/AI待接受不允许假报成功；精确revision内容和hash一致 |
| RA35 | `project_management/tests/test_report_authoring_exports.py::test_html_plain_markdown_and_excel_preserve_authored_content` | link/title/owner、table、列表与来源时间/模板ID均保留；Excel公式字串不执行 |
| RA36 | `ui_web/tests/test_report_authoring_browser.py::test_wysiwyg_template_to_publication` | 桌面创建模板->建draft->真实组件编辑/#fake ticket->save/reload->copy/download->临时Git定稿 |
| RA37 | 同文件 `test_popup_scroll_and_long_text_remain_usable` | 三候选、disabled/错误、底部翻转、长中文字、键盘focus，无文字重叠遮操作 |
| RA38 | 原HT30 joined receiving-client | 实际Windows Outlook空草稿粘贴HTML/plain，无recipient/Send；版本和表格链接实测 |
| RA39 | `project_management/tests/test_report_assists.py::test_cancel_unknown_preserves_original_run_key` | submit断线仅查原key，cancel先持久化；未知不重派/不退款，迟到输出不自动应用 |
| RA40 | `provider_sync/tests/test_reference_lookup_live.py::test_qualified_provider_reference` | 单独授权后验证Jira/HSD real auth/ID/title/assignee，未运行或不合格不得标pass |
| RA41 | `project_management/tests/test_report_authoring_content.py::test_paint_and_marks_survive_save_reload` | 红字/高亮/粗体仅改格式也产生revision；保存重开精确RGB和canonical内容不丢 |
| RA42 | `ui_web/tests/report_editor_test.mjs::colored_reference_roundtrip` | #补全后的带格式链接、相邻文字、撤销与重开保持；禁止Markdown桥梁静默删paint |
| RA43 | `project_management/tests/test_report_continuity.py::test_effective_human_text_survives_three_days` | AI原文被删除/改写后定稿，day2/day3继承最终fragment而非原候选 |
| RA44 | `ui_web/tests/test_report_authoring_views.py::test_failed_save_cannot_become_daily_baseline` | 断线/存储拒绝不显示Saved，不推进基线；dirty离开有提示，重开仅承诺已确认保存 |
| RA45 | `project_management/tests/test_report_assists.py::test_late_candidate_cannot_replace_user_paint` | 仅颜色修改也使旧AI候选stale；原人工片段仍在 |
| RA46 | `test_report_authoring_migration.py::test_v1_literal_and_v2_color_publications_keep_original_bytes` | v1字面、v2paint与context独立reader；未知版本拒绝，旧下载不重渲染 |
| RA47 | `test_report_continuity.py::test_prefix_uses_raw_provider_status_not_ai_text` | source In Analysis而AI写fixed仍显示In Analysis；同样覆盖HSD不同状态值，无健康分桶映射 |
| RA48 | 同文件 `test_missing_historical_status_is_not_backfilled` | 旧note无状态只显示日期；当前不可用明确unavailable，不能复用旧状态冒充当前 |
| RA49 | `test_report_meeting_matrix.py::test_shared_pr_keeps_independent_ticket_rows` | 同PR/owner三票三行，各自状态/AR/源refs；无串票 |
| RA50 | 同文件 `test_stable_order_appends_new_items_and_restores_returning_item` | 状态/updated变动不挪行，新票组尾、显式reorder新修订、移出重返保留身份位置 |
| RA51 | 同文件 `test_cumulative_projection_never_duplicates_or_leaks_future_notes` | day1/day2/day3顺序、去重、无未来；缺日不生成假的无变化，notes只存一次 |
| RA52 | `test_report_preparation.py::test_three_baselines_advance_independently` | capture/AI接受/Save不推进editorial；只有正式daily确认推进，weekly_view不抢head |
| RA53 | 同文件 `test_unfinalized_previous_draft_requires_explicit_gap_choice` | 默认pending；明确skip记录draft IDs但不删除；初始无基线明确initial |
| RA54 | `test_report_week_rollover.py::test_new_week_carries_last_confirmed_note_with_user_format` | 原日期/来源状态/颜色/链接不变，本周新行追加；不复制整张旧周表 |
| RA55 | 同文件 `test_older_open_actions_and_persistent_notes_survive_rollover` | 周二AR在周五note后仍带入，done不作为open；建议/常驻备注保留且无重复通知 |
| RA56 | 同文件 `test_missing_friday_week_gap_and_year_boundary_are_explicit` | 实际周三或更早baseline保留原日期，无周五/前周假记录；year+calendar区分同周号 |
| RA57 | 同文件 `test_calendar_or_stage_mismatch_refuses_inheritance` | 未映射日历/外stage/foreign owner拒绝；series显式create/get/save-CAS才可选，GET不默认创建，换周不换scope |
| RA58 | `ui_web/tests/test_report_preparation_views.py::test_get_week_navigation_never_prepares` | GET/切周/刷新仅返回已有资料；0capture/AI/draft/commit |
| RA59 | `project_management/tests/test_report_preparation.py::test_duplicate_prepare_returns_existing_work` | 同command不同payload拒绝；不同command同meeting返回existing/effective selection及差异，不假报新选项已应用，I/O前持久占位 |
| RA60 | 同文件 `test_explicit_refresh_preserves_user_edits_and_rejects_stale_baseline` | 终态reprepare核对draft/operation revision，source候选需显式合并；active或stale拒绝，无自动覆盖/清原稿 |
| RA61 | 同文件 `test_manual_only_saved_capture_works_without_base` | Base不就绪仍可人工填，source明确；0模型/意外采集，未合格changed_items不能回退 |
| RA62 | 同文件 `test_unchanged_sources_reuse_analysis_without_reauthoring_history` | changed_items仍按原增量/有效摘要复用；历史拼接/模板改动0模型，必要模型输入含用户上下文但非源事实 |
| RA63 | `test_report_continuity_publication.py::test_baseline_cas_and_old_date_corrections_do_not_overwrite` | 两窗口baseline CAS，weekly/旧日correction不抢当前head；后续定稿不反写 |
| RA64 | 同文件 `test_commit_ack_loss_repairs_head_from_exact_packet` | Git前后中断、指针丢失，核验原continuity hash/六文件，一次提交，无新source/AI |
| RA65 | `test_report_continuity.py::test_missing_corrupt_revoked_or_oversized_history_is_not_empty` | 旧fragment/hash/权限/reader缺口或超限拒绝，不能空历史/删paint/截AR继续 |
| RA66 | `test_report_authoring_exports.py::test_export_capabilities_do_not_destroy_color_authority` | HTML/JSON保真，Markdown/plain与Excel限制明确；任何有损导出不能回写fragment |
| RA67 | `ui_web/tests/test_report_authoring_browser.py::test_colored_human_note_survives_day_and_week` | 真实组件AI候选->人工删改/颜色/#->Save/reopen->Finalize->次日/新周，截图+DOM/canonical核对 |
| RA68 | `project_management/tests/test_report_preparation.py::test_restart_continues_original_prepare_and_meeting` | restart后复用原command/runKey/cutoff/meeting，跨午夜不改日期、不双发 |
| RA69 | `test_report_meeting_matrix.py::test_template_reorder_or_palette_change_cannot_rewrite_history` | 新模板色板/组序变化不覆盖旧RGB/旧归档，用户显式新顺序仅后续生效 |
| RA70 | `project_management/tests/test_report_schedule.py::test_schedule_is_disabled_until_explicitly_qualified` | W7：默认disabled/缺资格拒绝，普通GET和部署检查不启用任务 |
| RA71 | 同文件 `test_scheduled_manual_and_repeated_time_share_one_meeting_slot` | W7：按钮/定时/重复DST同日仅一准备，选项不同返回原值+冲突提示；scheduler不reprepare/finalize |
| RA72 | 同文件 `test_missed_schedule_is_not_backfilled_or_marked_published` | W7：停机/休眠/DST缺口记missed，不补造日报，迟到作业保留原日期和预算 |

保留现有test_report_templates的“拒绝任意registry替换”控制用例：
新增用户模板走受校验的 document compiler，不修改测试使任意HTML registry可以通过。
RA35补齐新的内容格式消费者，不将旧 Markdown/Excel 全功能任务因此自动关闭。
RA38/40是外部资格，不能通过mock/DOM/上游文档替代。
RA41-69 对应 W6.AUTHOR，RA70-72 只在 W7.SCHEDULE 资格时执行；
后者未执行不阻塞手动交付，但不得声称定时功能已实现。
颜色保真先验证实际组件能力再扩大接线，原13项本地样张检查不替代以上生产测试。

### Implemented Test Mapping

CONTENT已落地的具体入口如下；对应执行结果/候选/评审只在tasks记录。
该映射不宣称下游UI、收据、连续性或全部RA通过。

| Case boundary | Maintained test |
| --- | --- |
| RA01/06 legacy literal and actual pinned v1 | `test_report_authoring_migration.py::test_should_keep_schema1_legacy_publication_contract_and_literal_text_downloads` and `test_should_render_finalize_old_v1_draft_and_upgrade_second_old_draft_with_original_download_intact` |
| RA02/03 unsupported content/source targets | `test_report_authoring_content.py::test_should_reject_forged_targets_unsafe_fragments_receipts_and_stale_cas` |
| RA04 replay / stale CAS | `test_report_authoring_content.py::test_should_replay_same_save_command_and_reject_same_command_with_different_payload` |
| RA05 exact six files / recovery | `test_report_authoring_migration.py::test_should_publish_schema2_exact_packet_resume_and_download_original_bytes` and `test_should_reject_corrupt_schema2_runtime_packet_before_append_when_hashes_are_repaired` |
| RA05 selected history identity | `test_report_authoring_packet_validation.py` direct validator and resume-before-append counterexamples |
| RA41 paint persistence | `test_report_authoring_content.py::test_should_keep_colored_link_and_bold_note_when_saved_reopened_rendered_and_published` and `test_should_treat_paint_only_change_as_new_revision` |
| Empty human edit / no downgrade | `test_report_authoring_content.py::test_should_persist_explicit_empty_narrative_override_without_resurrecting_original_text` and `test_report_authoring_migration.py::test_should_refuse_legacy_save_on_schema2_current_without_losing_original_replay` |

ASSIST实际入口如下；按[交付回执](assist-delivery.md)绑定源码与结果，不执行早期表格中的占位节点：

| 合同 | 实际入口 |
| --- | --- |
| RA29/30 独立profile和目标/证据边界 | `project_management/tests/test_report_ai_task.py`、`test_report_assist_contract.py` |
| RA31 原key/取消/失败/次数上限 | `project_management/tests/test_report_assist_service.py`、`test_report_assist_recovery.py` |
| RA32 Apply与Save、相同文字接受、连续保存 | `ui_web/tests/test_report_assist_browser.py` |
| RA33 权限/CSRF及AI不可用时手工操作 | `ui_web/tests/test_report_assist_views.py`及上述browser文件 |
| RA45 文字/颜色改变后不覆盖 | `TestReportAssistBrowser.test_shouldRejectCandidateAfterNewHumanText`及`test_shouldRejectCandidateAfterPaintOnlyChange` |
| 其他可填目标保存分支 | `project_management/tests/test_report_assist_targets.py` |
| SDK/Base/Git/翌日来源引用 | `project_management/tests/test_report_assist_http.py`；不代替完整RA67工作周 |

EXPORT.SAMPLE实际入口：

| 合同 | 实际入口 |
| --- | --- |
| RA35/66 文字、链接、格式限制、公式与截断 | `project_management/tests/test_report_exports.py` |
| 原publication不重建、不改字节/Git head | `project_management/tests/test_report_export_service.py` |
| 下载权限、字段/方法、headers | `ui_web/tests/test_report_export_views.py` |
| 实际控件下载、浏览器复制、双语手机布局 | `ui_web/tests/test_report_export_browser.py` |
| 保存生命周期与修订URL | `ui_web/tests/report_exports_test.mjs`及既有authoring lifecycle测试 |

以上Excel是明确声明的文本表格能力；HTML/JSON颜色仍为权威。浏览器Clipboard API
读回不代替Outlook接收端或原完整工作周。确切候选/结果在[导出回执](export-delivery.md)。

EDIT/REFERENCES已落地的入口如下；沿tasks中的独立评审和对应候选读取结果，
此表只是可执行入口映射，不是重复的通过状态或live资格声明。

| Case boundary | Maintained test |
| --- | --- |
| RA07/09/42 atomic replacement and native history | `ui_web/tests/test_report_authoring_edit_runtime_browser.py::TestReportAuthoringEditRuntimeBrowser::test_shouldReplaceSecondTokenWithRichInlineCandidateAndUndoOnceInNativeRuntime` and `test_shouldNotCaptureSyntheticTokenAcrossHardBreak` |
| RA41/42 mixed paint and supported structures | `ui_web/tests/test_report_authoring_edit_runtime_browser.py` paint/highlight, task/table/code and save/reopen cases |
| RA10/11 mounted menu, IME and teardown | `ui_web/tests/test_report_completion_browser.py` anchored popup, region change, IME, teardown, Escape/selection, abort and invalid-envelope cases |
| RA12-19 scope, current identity, quota and errors | `project_management/tests/test_report_completion.py`, `test_report_membership.py`, `test_report_completion_admission.py` and `provider_sync/tests/test_reference_lookup.py` |
| RA20 signed references and human edits | `project_management/tests/test_report_authoring_references.py` and `ui_web/tests/test_report_completion_browser.py::TestReportCompletionBrowser::test_shouldConvertExpiredReferenceToOrdinaryHumanLinkWithoutLookup` |
| RA33/34/44 delayed or uncertain save, exit protection | `ui_web/tests/test_report_authoring_lifecycle_browser.py` original-command replay, retained newer local edits, late mount, undo and language-exit guard cases |

RA20还包括人工改title/paint、大段内插入、改link key/href、删link遗留receipt、
重复ID及跨targetID反例，不以CONTENT的早期fail-closed用例替代成功链。
模板、连续性、AI和整周的执行映射随对应实现补齐，不把目标测试名当成已有测试。

模板与HISTORY已落地的测试入口如下。纯计算、持久化及mounted UI分别列出，
不能代替后续Daily触发界面、AI辅助或完整工作周联合验收。

| Case boundary | Maintained test |
| --- | --- |
| RA21-28 library/version/use/readiness/quota | `project_management/tests/test_report_template_library.py`, `test_report_template_compilation.py`, `test_report_template_rendering.py` |
| RA21/22/24/33 mounted template/edit/save lifecycle | `ui_web/tests/test_report_template_views.py` and `test_report_template_browser.py` visual template, populated library, archived/invalid save, delayed/lost-response and Chinese lifecycle cases |
| RA41/42 readonly inherited paint rendering | `ui_web/tests/test_report_template_browser.py::TestReportTemplateBrowser::test_readonlyRegisterCssDoesNotOverrideAuthoredPaintDescendants` |
| RA43/47/50/57 pure history/series/calendar | `project_management/tests/test_report_history_core.py` and `test_report_history_core_review_regressions.py` |
| RA54-57/62 dedup and rollover | `project_management/tests/test_report_history_composer_fix2.py` and `test_report_history_metadata_fix3.py` |
| RA57/65 seed/context refusal | `project_management/tests/test_report_history_validator_fix2.py` plus standalone-baseline/old-policy cases in `test_report_history_core_review_regressions.py` |
| RA43/52/54/55/63/64 persisted history, exact publication and recovery | `project_management/tests/test_report_history_persistence_chain.py`, `test_report_history_save.py`, `test_report_history_seed.py`, `test_report_history_recovery.py`, `test_report_history_period.py` and `test_report_history_period_actions.py` |
| RA47/49/50/57/58 mounted matrix, series and weekly selection | `ui_web/tests/test_report_history_ui_browser.py` and `test_report_history_ui_routes_browser.py` |
| RA52/53/59/61 daily reservation and saved-capture manual preparation | `project_management/tests/test_report_preparation.py`, `test_report_preparation_store.py` and `test_report_preparation_links.py` |
| RA60/62/68 worker, replacement authority and recovery | `project_management/tests/test_daily_worker_backend.py`, `test_daily_worker_store.py`, `test_daily_worker_recovery.py`, `test_daily_reprepare_backend.py`, `test_daily_reprepare_review_fix.py` and `test_daily_reprepare_journal_fix2.py` |
| RA43/60/65 retained human content and historical reference editability | `project_management/tests/test_daily_preservation_backend.py`, `test_daily_preservation_fix2_backend.py`, `test_daily_preservation_reference_backend.py` and `test_historical_reference_validation.py` |
| RA52/53/58-61 preparation controls, read-only detail, exact gap and replay | `ui_web/tests/test_report_daily_ui_views.py`, `test_report_daily_forms.py`, `project_management/tests/test_report_preparation_read.py` and `test_report_preparation_initial.py` |
| RA33/44/63 HTTP authority, strict JSON, unchanged stale baseline and Chinese labels | `ui_web/tests/test_report_daily_http_contracts.py` |
| RA60/62 terminal correction, offline replacement, unchanged analysis reuse | `project_management/tests/test_daily_preparation_terminal.py` |
| RA41/58/59/61 mounted manual and registered runtime workflows | `ui_web/tests/test_report_daily_ui_browser.py` manual Save/reopen/Finalize, explicit reprepare paint retention and registered-worker refresh cases |
| RA65 invalid control records versus missing records | `project_management/tests/test_report_preparation_read_shapes.py` |

历史引用的缺字段/错误类型用例直接调用resolver，必须在打开来源存储前返回
`REFERENCE_INVALID`；合法结构仍进入真实来源解析。原临时persistence大文件已按上述
持久化职责拆分，使用当前文件名执行。最终候选/结果只以tasks及其冻结回执为准。

## 4. Execution Commands And Fixtures

当前命令从Dashboard根运行，使用
`.tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe`和
`scripts/validation/run_report_authoring_tests.py`，准确环境与作用域见
[验证指南](../../../docs/development/reporting-delivery.md)。
保留的主`.venv`仍为旧SDK，不得用于迁移后reporting验收。
新case先编写RED；未实现文件名不能当作可执行命令。
Node场景用 `node --test`，可读描述是case名，不是假的 pytest nodeid。
隔离入口后接显式pytest路径：不加载.env、临时SQLite/state/archive、仅本机测试server连接。
已落地UI专项包括`test_report_authoring_views.py`、`test_report_authoring_browser.py`、
`test_report_authoring_lifecycle_browser.py`；生命周期4场景不替代后续整周RA67。

```powershell
$reportingPython = Join-Path (Get-Location) '.tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe'
& $reportingPython -I scripts/validation/run_report_authoring_tests.py project_management/tests/test_report_preparation_publication_guard.py -q
node --test ui_web/tests/report_editor_test.mjs
```

这不是全量验收选择。专项完整路径在前节矩阵及各叶的delivery回执中，
完整周入口与负向分支由[week-qualification.md](week-qualification.md)维护；
不再沿用早期规划中的未实现测试文件名。
W7调度仍后置，准确命令在其实现包就绪后冻结。
合成时钟/adapter先验证同日去重、missed和禁止定稿，实际scheduler注册/运行另需明确授权；
不得因文档存在就在用户机器创建计划任务。

fixtures扩展现有 `report_render_fixtures.py`、`report_draft_fixtures.py`、`report_source_memory.py`。
按公开DTO创建golden数据，不照抄错误的字段名：assignee/owner_id、evidence json_pointer要用真实producer。
新增 `report_authoring_fixtures.py` 只含合成模板/收据/片段；网络fixture注入假SPI，不调用真实profile。
使用既有显式 test settings/no-dotenv 方式，查阅相邻测试；禁止导入时启动服务或读取真实凭据。
RA05/06才用受控临时Git，其他存储反例优先memory repository；不每次全栈运行诊断解析器。

UI阶段延续 `.github/skills/lsheng2-ui-design/templates/project-overlay.md`，
1440×900桌面、既有Bulma/共享class/Iconoir；实际验收浏览器记录为Ego。
新增 browser test 的生命周期复用现有合成应用fixture，不改变原保留演示实例。
RA38使用原确认的Outlook目标，执行时刷新实际版本；不可用时只把该case列为未验证。

新Python文件<=400行、测试<=600；UI文件在实施包中按明确职责拆分，
不因原项目静态文件无规则就写一个巨型editor。每个叶任务用实际路径跑size和whitespace。

## 5. Error Acceptance Beyond Completion

| Code | 场景与界面行为 |
| --- | --- |
| `REPORT_DOCUMENT_UNSUPPORTED` | 未知schema/节点/renderer；保留dirty内容，旧文件下载不受影响 |
| `REPORT_TEMPLATE_NOT_READY` | 缺系统区/非法slot；在模板块旁标错，允许保存未就绪版本但不能用于报告 |
| `REPORT_TEMPLATE_REVISION_CONFLICT` | 别处已保存；保留本地编辑，显示明确版本冲突，禁止自动覆盖 |
| `REPORT_TEMPLATE_ARCHIVED` | 新选择已归档模板；保留原draft的snapshot，回到模板选择不丢填写 |
| `REPORT_TEMPLATE_LIMIT` | 数量/字节/版本额度超限；整个事务拒绝，无部分模板或丢失历史 |
| `REPORT_REQUIRED_SLOT_EMPTY` | finalization缺必填内容；标注具体slot，草稿仍能保存 |
| `REPORT_AI_UNAVAILABLE` | profile未声明/禁用、模型未配置或运行时不可用；AI操作禁用并说明，人工编辑保持 |
| `REPORT_AI_RESULT_INVALID` | wrong identity/schema/evidence；候选拒绝，无内容覆盖或summary推进 |
| `REPORT_AI_STALE` | 原候选base revision/slot hash变化；仍可看旧候选但不能自动应用 |
| `REPORT_AI_PENDING` | unknown/cancel_requested；显示原任务状态，不能新key重派 |
| `REPORT_BASELINE_PENDING` | 前日有保存未定稿内容，提示处理或明确旧正式基线+gap，不丢原draft |
| `REPORT_BASELINE_CONFLICT` | 系列基线或期望修订被推进，保留dirty，显式选择/合并 |
| `REPORT_HISTORY_UNAVAILABLE` | 继承记录/hash/权限/旧reader缺口，不能空历史假报成功 |
| `REPORT_CALENDAR_UNAVAILABLE` | 日历映射缺失/不一致；禁止AI推测工作周 |
| `REPORT_SCHEDULE_UNAVAILABLE` | 默认关闭/未资格，手动入口仍可用 |
| `REPORT_PREPARATION_COMMAND_CONFLICT` | 同command不同payload拒绝；同meeting的不同command返回既有选择和差异提示 |

404仍用于跨owner，错误语义不得泄露隐藏模板名、工单title或用户身份。
API安全英文与zh-CN静态文案同case验证，不将上游异常直接显示给用户。

## 6. Historical Design-Only Preflight

本次只运行 OpenSpec strict、选定文档链接/围栏/空白检查、task/RA映射与独立设计审查。
本次增量预检要求RA01-72唯一、HISTORY/DAILY依赖与ledger一致，调度清楚标为W7延后。
不运行上述待实现用例、`manage.py`、模型/Provider、browser或新migration。
没有产品执行证据不勾选任一实施节点，不把新文档称作功能交付。

## 7. Full Week User Qualification

Skipped-meeting extension: the later [skip packet](meeting-skips.md) adds
single-date/range skip/restore and a direct two-week resumption scenario. Its
concrete pure, admission, HTTP and mounted entry points are
`test_report_meeting_contracts.py`, `test_report_meetings.py`,
`test_report_meeting_resumption.py`, `ui_web/tests/test_report_meeting_views.py`
and `ui_web/tests/test_report_meeting_browser.py`. This supplements RA56 and
RA67; it does not replace the original week or claim live qualifications.

2026-11-03用户追加要求：所有实现与分层测试完成后，执行一次完整工作周的full-stack
端到端验证，每天工单信息相同、每天人工note/格式/颜色不同，检查整周最终状态并保留证据。
这是RA67在W6.AUTHOR.JOIN中的必需具体场景，不增加第二套任务状态，也不授权真实模型或采集。

### Fixture And Entry

- 独立合成Project/Stage/Series及全新的周周期，使用本地正式app/HTTP/ORM/编辑器/存储/
  数据Git writer；不得以样张生成脚本或直接写最终context替代UI/API流程。
- 明确选择`iso8601`合成日历、`Asia/Shanghai`时区。相对于2026-11-03，
  上一工作周用2026-10-26至2026-10-30（ISO WW44.1至WW44.5），
  换周用2026-11-02（ISO WW45.1）；不把ISO规则声称为Intel自定义workweek规则。
- 模拟时钟仅注入被测服务/受控provider fixture，不修改Windows系统日期，不更改真实工单时间。
  每日经过相同的准备入口和正常capture/summary读写；capture ID/cutoff可以不同，
  每票标题、状态、owner、原始comments/updated保持相同。语义内容指纹相同，
  不强迫含capture元数据的整个snapshot/HTML hash相同。
- 覆盖至少三票独立行，共用PR/owner也不合并；包含Fixed及In Analysis，
  用不含企业原文的固定fixture。scope/排序/pending/AR覆盖保持显式。
  主验收首日经task-run端口与获准synthetic模型产生并接受摘要（MDB-2起为嵌入运行时；
  已完成的运行使用已安装SDK/本地Base HTTP，仅为历史）；
  后续无变化复用，原summary/input/result身份不被人工note改写。
  预置accepted summary仅可用于局部故障测试，不能替代主full-stack链路。

### Daily Journey

| 模拟日期 | 真实用户操作 | 当日和下一日必须观察到的结果 |
| --- | --- | --- |
| Mon 2026-10-26 | 创建用户模板和series，按钮准备首日；编辑一票AI叙述、删一段、加红色人工note/链接，另票加未结束AR；Save、关闭重开、显式Finalize | 日期后状态只取source；人工删除不复活，红字/link精确保留；Save尚未推进editorial baseline，Git确认后才推进 |
| Tue 2026-10-27 | 相同工单数据准备；先核对周一全部文字/颜色，再添加蓝色note及绿色常驻备注；保存、重开、定稿 | 周一note的ID/body_hash/paint不变，追加周二不复制整个周一表；旧AR继续存在，当前owner不由AI猜测 |
| Wed 2026-10-28 | 先重开服务读取前两天；新note选不同高亮及粗体，实际输入#ID并选第三格式，进行撤销/重做；保存、定稿 | 正文补全/原链接/三天历史正确，来源scope和状态仍相同；重启不导致新AI run或重复prepare |
| Thu 2026-10-29 | 当前日新note添加后删除一段，另一目标显式清空；只改颜色也保存；用第二窗口制造一次stale save并保留输入后正常处理 | 无空值回退旧AI、无丢色；409不覆盖最新修订或丢本地文字；周一至周三只读历史不改 |
| Fri 2026-10-30 | 添加第五天note与混合颜色文字；显式解决一个AR、保留另一个AR；保存/重开/定稿；生成weekly_view并下载 | 同周每票五日按真实日期递增；一票一行顺序稳定；weekly_view不会成为daily baseline；HTML/JSON颜色一致，plain/Markdown限制如实说明 |
| Mon 2026-11-02 | 新周按钮准备，相同source；检查seed后加新日note、保存/定稿 | 携带每票周五或实际最近已确认note的原日期/状态/格式，更早未结束AR及常驻备注仍在；不带已解除行动作未结束项，不把旧句重标为今日；旧周可读 |

每日点击准备两次须得到同一meeting的既有工作，不产生第二草稿/第二推理。
每天至少一次实际Save->页面重开，周中至少一次应用正常重启。
周末只读切换和午夜经过不创建草稿/模型/定稿。周一至周五的状态固定，
颜色变化不得被解释成工单状态变化；不要为了演示而改工单。
单独保留“前日已保存未定稿”分支：下一日提示pending，用户明确gap后才继续；
原未定稿内容仍可读，不影响主线已确认基线的断言。

### Evidence And Exit

运行前冻结源码候选SHA/dirty文件hash、lockfile/vendor hash、Python/Chrome/运行时版本与wheel摘要、
fixture/schema/prompt hash及日历规则。每次run使用唯一owned目录，不覆盖旧失败证据。
每日保留：

- 操作结果与request/command/preparation/draft/revision/publication/meeting/period引用；
  provider/model调用计数，source语义hash及editorial/analysis baseline独立引用。
- 编辑中、保存重开、当日定稿的桌面截图；实际DOM颜色/高亮/link和规范fragment比对。
- 原六文件publication、HTML/plain及可用Markdown/Excel导出、文件hash清单；
  继承note/action/常驻备注逐项hash与golden期望，不仅比全文或截图。
- 关键HTTP状态、冲突/拒绝记录、正常关闭/重启结果、测试用例通过/失败明细。
  日志不含凭据或未授权企业原文；expected409与意外错误分开。

最终报告汇总五日累计和下周seed，给出逐项PASS/FAIL/未验证及证据路径。
无变化期间provider读取可按显式prepare发生，但summary/AI新调用计数必须为0；
编辑/颜色/补全/模板/保存/导出都不消耗模型调用。请求synthetic首次生成与真实token计费分开。
不能用“全部脚本退出0”代替逐日内容不变量，也不能删除失败产物后只保留最终绿色。
JOIN只有本场景和原必需作者流程都通过才可关闭；Outlook/live provider/model仍单列资格。
