# Q1 合成评审材料

状态：review fixture v1，已纳入FZ-01应用方设计冻结回执；不是已注册bundle或产品验收。
所有数据合成；不访问URL、不加载App配置、不调用模型。
本目录不负责定义基座Run HTTP envelope、tokenizer或最终协议版本。

## 文件与边界

- `summary-review.schema.json`：包含应用input/candidate及仅供测试的acceptance_context。
- `summary-golden.json`：完整材料与可接受候选。
- `partial-golden.json`：缺少完整comment coverage，允许记录partial进度但不得推进完整accepted水位。

领域字段来自旧`summary-output.schema.json`的what/current_position/next_actions语义，
但这是provider-neutral的小样例，不声称覆盖旧schema所有span/分片/多票能力。
本例数组/字符串上限是fixture保护值，不是生产吞吐KPI或最终模型context上限。

`input_hash = sha256(UTF8(json.dumps(input, sort_keys=True, separators=(",", ":"), ensure_ascii=False)))`。
这是本fixture定义的规范化，不声称是通用JCS；input_hash不参与自身计算。
`source_hash`按同一规则仅计算每个evidence.value，不能冒充原HTTP响应字节hash。
生产中原bytes hash、逻辑hash、effective compiled hash须各有版本化算法和来源。
所有输入字段（含baseline、coverage、required_parts和有序evidence）都参与逻辑hash。
candidate的binding/input_hash/base_summary_id/target必须与本轮固定输入一致。
`acceptance_context`是可信应用实时读取的测试状态，不发给模型，也不能由模型回传值代替。

## 应用接受算法的预期

先校验schema，再核对live授权、绑定/policy/target、输入hash、baseline ID及accepted_revision。
schema本身不证明引用/引用文本/owner身份真实，也不执行CAS。
coverage是应用对完整采集的声明，基座不能从本例少量evidence推导实际分页完整；
本例仅发送本次分析必要证据，全部原文归档不在基座fixture中。
full候选还要求所有required_parts complete，evidence引用存在且source_hash可重建；
显式owner的owner_quote须在被引评论中，并能定位到该owner_id；模型owner_confirmed始终false。
通过后仅应用执行accepted CAS；CAS冲突/存储失败不推进任何成功水位，也不要求重跑模型。
partial只记录部分进度，保留旧成功摘要和未总结delta；本例期望`record_partial/no_watermark_advance`。
partial-golden是接受层防御及无模型进度输出样例，不授权把缺required part的输入发给完整摘要任务。
首次完整摘要需要完整材料；本例只演示增量输入，不代表首次/分片流程已经覆盖。

## 精确反例

以下变换在完整样例的独立副本上执行；它们是待实现的验收期待，不是本轮已经运行的业务测试。

| ID | 修改 | 预期 |
| --- | --- | --- |
| Q1-FULL | 不修改summary-golden | 应用全部语义校验及CAS成功后，接受summary-1到新目标 |
| Q1-PARTIAL | 使用partial-golden | 记录partial，accepted仍为summary-1/revision 1 |
| Q1-STALE | acceptance_context.current_accepted_revision改为2 | CAS拒绝，零accepted/publication写入 |
| Q1-BASE | acceptance_context.current_summary_id改为summary-other | 基线冲突拒绝 |
| Q1-TARGET | acceptance_context.current_target_capture_id改为capture-3 | 目标过期拒绝 |
| Q1-AUTH | acceptance_context.authorized改为false | 拒绝，不公开/接受候选 |
| Q1-SITE | candidate.binding.site改为https://other.example.invalid | 来源绑定拒绝，即使其他字段相同 |
| Q1-HASH | 修改input.delta而不改candidate.input_hash | hash拒绝 |
| Q1-QUOTE | explicit action的owner_quote改为null | 应用语义拒绝，不能默认显式指派 |
| Q1-CONFIRMED | action.owner_confirmed改为true | schema拒绝，模型不能自行确认 |
| Q1-PART-AS-FULL | partial-golden的candidate.kind改为summary | required_parts拒绝，不能推进完整水位 |
| Q1-SUGGESTED | summary action.owner_basis改suggested、owner_quote改null | 可作为建议但owner_confirmed仍false；不把建议当指派 |
| Q1-UNKNOWN | action.owner_basis改unknown、owner_id/owner_quote改null | 保留未知owner，不补造负责人 |

只有schema、JSON/hash自洽可以在本轮离线核验；实际应用拒绝/CAS/归档仍由W4/W5实施验证。
一个完整与一个partial样例是同一种业务schema，不算E7要求的两种不同领域consumer；
另一个通用文档提取schema/fake consumer由基座提供。

## CF-01 严格投影与 hash 归属

基座task-run/1草案返回后，新增三个应用方草案文件，原fixture不改写：

- `strict-summary-input.schema.json`：仅接受`summary-golden.json.input`，不是fixture总根。
- `strict-summary-output.schema.json`：只允许summary，**原始模型输出不含input_hash**。
- `strict-summary-output-golden.json`：原始模型输出样例；应用补入已验证的本地input hash后，
  应与原`summary-golden.json.candidate`完全一致。

原因：fixture.input没有input_hash；不能让模型可靠计算未提供的SHA-256值。
RunSubmit.logicalInputHash和本地持久attempt已有该值，应由应用核验RunResult后绑定。
这是对基座旧稿“candidate投影仅收窄kind”的修订，已被最终稿采纳并获我方冻结确认；
准确design/schema字节版本见[回复第10节](../ai-base-review-response.md)，不是运行资格。
应用补字段只生成本地候选，不改写平台原content或其output hash，不新增基座私有映射服务。

该示例profile固定required_parts为facts/comments/history，并要求三者complete。
不能只遍历调用者自报required_parts而允许其删去comments来绕过完整性。
正式其他profile可以有自己的固定集合，但需新revision/schema；这些业务字段不进入平台核心。
profile_revision的常量属于这个review profile，不是所有项目的全局版本。

本地schema闭包为三个文件：原`summary-review.schema.json`及两个strict schema。
两个strict文件使用相对文件`$ref`，原文档中的`#/$defs`仍在原文档解析，不能只复制子树。
`$id`中的example.invalid仅是稳定资源标识，不是下载地址。
验证/装载必须将这三个完整文档预登记到本地registry，缺引用或外部引用立即拒绝，不发HTTP。
golden JSON、README、acceptance_context不属于注册的schema资源或模型输入。

应用绑定顺序：

1. 持久attempt保存原input bytes/hash、logical hash、profile/schema、scope、runStoreId和clientRunKey。
2. 重取RunResult，先核对Run身份、schema/profile hash、inputSha256及logicalInputHash。
3. 检查原content bytes的输出hash及strict output schema，再核对候选binding/baseline/target/profile。
4. 用本地attempt已核验的logical hash填入本地候选input_hash，交给既有引用/owner/accepted CAS。
5. 不接受模型自报input_hash；返回metadata缺失/不符也不能靠补字段把无效结果变成成功。

首批本profile要求logicalInputHash.algorithm为dashboard-json-review-1且digest与本地一致；
这是应用客户端/接受层要求，不要求平台理解该算法或强迫其他应用必须提供logicalInputHash。
实际RunResult绑定、鉴权和CAS测试尚未实现；本轮只验证投影及纯数据重建。
