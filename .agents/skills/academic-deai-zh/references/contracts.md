# 本地接口契约（运行版1.5.0，补丁schema 1.0）

## v1.4精简读取与直接应用

`review-request --format compact`保留完整before/after、原段定位、补丁ID/依赖、全部判断模板、原样分句和限定词，省略重复全文、旧完整模板以及重叠句/分句清单。默认full仍兼容旧调用。两种格式不改变复核要求。

`apply --review review-quotes.json`现可直接读取带`review_format: "compact-1"`的真实模型复核。工具仅在内存中计算坐标和固定结构，不必再保存巨大的展开文件。原始复核仍应保留；旧式先bind-review再apply的结果相同。

精确引文支持`{text:"使用",context:"研究A使用自报活动量"}`。context须在对应侧全文中唯一；若其内部仍有重复text，提供context内部从0起的occurrence。没有context时occurrence按全文计数。缺失、歧义、假引用与越界一律拒绝。

`check-review --input input.md --patches patches.json --review review-quotes.json --output diagnostics.json`是只读预检。review_ready仅表示当前全部门控可通过；review_blocked的具体路径用于查错，不是自动修复或额外补取授权。实质判断与恢复边界见[information](information.md)和[recovery](recovery.md)。

所有文本区间为**解码后原文的 Python Unicode codepoint 半开区间**，不是 UTF-16、字节或视觉字宽。`original_hash` 为解码正文 UTF-8 的 SHA-256；原件字节哈希另记。BOM 不计入正文位置。脚本不归一化，不重新序列化 Markdown。

Python 导入 `deai_core`：

- `document_from_path(path)` / `document_from_text(text, source='pasted.txt')` → `Document`。
- `prepare_path(path, mode='standard', genre='auto')` / `prepare_document(doc,...)` → 完整原文、段落、相邻上下文、保护区、定位候选。
- `scan_document(doc)` → 候选定位。零命中仍要求语义诊断；候选不取得删除权。
- `build_review_request(doc, bundle)` → 完整 before/after、哈希、补丁及默认 `unknown` 复核模板。
- `build_bundle(doc, proposal)` → 将带原文hash的段落提案编译为较小的合法补丁；不生成通过结论。
- `bind_review(doc, bundle, review)` → 将模型的精确文字引用编译为坐标，保留所有判断；支持旧坐标输入，不调用模型。
- `mechanical_check(before, after, doc=None)` → 机械检查记录，`equivalence_proven=false`。
- `apply_bundle(doc, bundle, review=None, repair_bundle=None, repair_review=None, coherence_review=None)` → `(final_text, report)`。
- `result_envelope(doc, final, report)` → 可供 CLI export 读取的结果。
- `export_result(doc, final, report, output_dir)` → 新文件改稿、HTML 差异、说明、检查 JSON。输出已存在则拒绝，原件不覆盖。

## 补丁

推荐先生成段落提案，再运行 `build-bundle`。`original_hash` 必须复制自本次prepare；每个段落最多一项，`new` 是完整替换段，不含段落外换行。脚本只缩去相同前后缀并保护原子锚点，不自行改写文字。保持原文的提案会成为no-op。

```json
{"original_hash":"本次prepare的hash","mode":"standard","review_policy":{"require_information_units":true,"require_benefit":true},"edits":[{"paragraph_id":"p00001","new":"完整替换段","reason":"原文中的具体问题及本次收益"}]}
```

脚本不能从文字推断跨段依赖；若编辑涉及其他段落的指代，需显式补上依赖后再生成复核请求。直接提交下列补丁schema仍兼容。

新提案推荐开启上述两个复核要求。`review_policy` 可省略，保留旧直接API；它只接受这两个布尔字段。编译、复核请求、应用报告及导出保留该策略，repair不能删除或改变策略。未改动的no-op无需收益证据。策略并不授权放宽数字、引文或结构。

```json
{
  "schema_version": "1.0",
  "original_hash": "正文SHA256",
  "mode": "standard",
  "patches": [{
    "id": "e001", "paragraph_id": "p00001", "start": 0, "end": 10,
    "old": "原文精确子串", "new": "改文",
    "reason": "语境中的实际问题与收益",
    "claim_ids": ["claim001"], "protect_ids": [], "depends_on": []
  }]
}
```

`protect_ids` 必须精确枚举相交的非结构保护区；含数字/引用等的整段替换允许，但原锚点的完整文本及顺序必须保留。不能切开锚点，不能触碰 locked 标题、表格、公式块、代码块、参考文献等。换行序列必须保持。同段补丁及 depends_on 联通组件构成整体事务。重复 ID、重叠、缺失依赖、旧文/哈希不符均拒绝。

## 语义复核

使用 `build_review_request` 取得待填模板，不手工计算候选哈希。复核绑定整个候选文稿，而不是只绑定原文或只看局部新文。

top-level 字段：`before_hash`、`after_hash`、`reviewer: {model, role, request_id}`、`transactions`、`global_coherence`。model 必填，其余来源字段可选，应据实际能力记录。

每个 transactions 项：

- `covered_patch_ids`：与一个事务中的全部补丁 ID **完全相同**。
- `covered_paragraph_ids`：至少包含改动原段及左右相邻原段的 ID。
- `status`：`pass`、`fail`、`unknown`。
- `before_to_after` 和 `after_to_before`：各为 `{status,note}`，检查遗漏与新增；不能只做一个方向。
- `dimensions`：以下全部维度各自有 `{status,before,after,note}`。没有该项也需明确写原文/改文不适用，而不是省略。
- `claims`：涵盖全部 claim_ids，每项 `{id,status,before,after,note}`。

全部语义维度：`subject, object, group, intervention, outcome, quantity, comparison, negation, modality, condition, time, status, attribution, citation`。

所有 pass 必须附可读、非空的 note 与 before/after 记录；缺项、fail、unknown、哈希过期、响应截断均回退相应事务。此结构只保证复核证据绑定和覆盖字段，不保证模型判断正确。

`global_coherence` / 单独 `coherence_review` 字段：`{before_hash,after_hash,status,covered_paragraph_ids,note,reviewer_model}`。正常全通过时读取 review.global_coherence。局部回退产生新候选哈希后，必须**重新**通读该最终候选并传入单独 coherence_review；缺少匹配证据时其余改动也回退，防止残留错误指代或接续。

## v1.2精确信息单元与限定词证据

`require_information_units=true` 时，每个事务另需 `information_review`。即使未开启策略，也只有提供完整且通过的该证据，才可能裁定特定正向限定词计数告警。其他机械错误仍为硬约束。原复核的双向检查、全部维度、claims和全文连贯性仍全部必需；claims须与该事务所有补丁的claim_ids并集精确对应，重复、额外项、pass/fail冲突均拒绝。

一个span只有三个字段：`{start,end,text}`。before区间取完整原文，after区间取完整候选文稿；每项必须对应精确非空子串，不能用片段内位置、占位文字、近似匹配或猜测位置。数组内不能重复同一位置。主程序只验证实际文本、覆盖和有限不变量，不生成事实、不计算语义正确率。

```json
{
  "information_review": {
    "status": "pass",
    "before_hash": "原文全文hash", "after_hash": "候选全文hash",
    "covered_paragraph_ids": ["p00001"],
    "units": [{
      "id": "事实A", "kind": "research_fact", "status": "pass",
      "before": [{"start": 0, "end": 8, "text": "实际精确原文片段"}],
      "after": [{"start": 0, "end": 8, "text": "实际精确候选片段"}],
      "subject": {"before": [], "after": []},
      "action": {"before": [], "after": []},
      "conditions": {"before": [], "after": []},
      "pure_discourse": false, "no_research_commitment": false, "topic_units": [],
      "note": "实际逐命题判断依据"
    }],
    "qualifier_bindings": [{
      "unit_id": "事实A", "status": "pass", "before": [], "after": [],
      "note": "每个实际限定词的命题与作用范围对应理由"
    }],
    "topic_preserved": {"status": "pass", "note": "实际主题对应依据"}
  }
}
```

以上是字段示意，假位置与事实锚点空数组不是有效通过记录。信息单元规则：

- `kind` 为 `research_fact, condition, stance, citation, topic, discourse_preview` 之一。ID唯一，每项必须实际pass并有具体说明；fail/unknown/缺项拒绝。
- 覆盖段落ID须与该事务实际改动段落精确相同，不是含相邻段落的语义复核ID。before和after信息单元需覆盖这些段落内全部非标点文字。`build_review_request.information_requirements` 显示原/候选段落、整句、逗号/顿号子句及限定词的精确位置，帮助复核；这些仅是词法覆盖锚点，不是语义命题抽取。
- 每个逗号/顿号子句须有其中的事实动作锚点，或由经过验证的未变条件/立场/引用/主题与合法行文预告的span并集完整覆盖。若该子句与研究事实单元相交，仍须有该子句内的事实动作锚点，不能借非事实片段并集绕过。一个覆盖整段但只列一个动作的事实单元不能替代其他子句。
- 所有单元均有subject/action/conditions双向span数组。研究事实的action不可为空；subject通常不可为空，仅该事实单元before/after的整体精确文字数组完全相同时，允许subject双向为空，表示原句隐含主体未经修改，不推断或补出主体。事实片段有任何文字改变时，此例外失效；条件缺席可双向为空。锚点须位于相应单元片段内，前后精确文字数组一致。条件、立场、引用、主题单元的整体精确文字数组也须一致。模型仍负责判断这些锚点是否真的代表完整事实。
- `discourse_preview` 仅为删除的行文动作，before非空、after为空、两个布尔标志均true；其他单元两个标志均false。它需包含实际“下面/以下/接下来/将介绍”等导航措辞，不能含研究目的、假设、创新、拟/计划/预计实施、承诺或将开展/验证等风险措辞。这些词法规则只用于拒绝部分高风险情况，不构成“纯行文”的证明。
- 每个预告须有非空 `topic_units`，精确引用同一原文整句内的 `topic` 单元；主题可与删除的导航片段分开标注，该主题必须在候选稿中逐字保留，整个子句仍须通过span并集覆盖。跨原文整句的主题不能用于此例外。真实目的、假设、条件或承诺不能凭模型把标志填true而获得删除权。任何引文原话/引号内文字不能用于本版信息单元裁定，包括仅引用其内部的子串。
- `qualifier_bindings` 须覆盖改动段落中全部已识别限定词实际位置；每项引用一个存活单元，同一单元可有多个不同原词位置的对应项，before/after非空、pass、有说明。每个对应项的标记集合一致，仅 `已经/已` 作为同一完成状态对应。每个原始位置只能属于一个对应项；不能用同一个原词解释两次删除。信息单元ID本身仍须唯一。
- 候选稿一个限定词可由多个动作共享，须与各动作位于同一整句并有完整、未变主体/动作/条件。事实动作须在共享词之后，词与动作之间出现另一个相同显式主体时拒绝，保守排除语法治理不明。共享范围仍由实际模型判断，不由正则证明。

裁定只处理 `modality_negation_status_changed` 的正向标记**减少**：`可能/也许/或许/大约/至少/至多/预计/拟/计划/正在/已经/已`。增加、替换，以及不/未/尚未/无/不能等否定标记的数量改变全部拒绝；已识别的 `modality_scope_changed`、数字归属错误等关系告警不豁免。被删每个词均须有唯一原位置及存活作用域证据，裁定的实际multiset减少量须与最终稿精确一致。没有全局忽略计数开关。

### v1.3原样分句的简化复核

`information_requirements[].verbatim_candidates` 给出同一原段中位置对齐、完整且逐字未变的分句及其before/after。它们不含status，不是自动复核结论。`information_review` 可另带 `verbatim_units: [{id,status,note}]`；每项必须是本次实际候选的唯一id、pass及具体上下文判断。原样文字仍可能因上文改变而失去原意，模型须核查主体、范围和指代后再判断。

程序重新计算并核对分句坐标，将明确通过的原样分句计入文字覆盖和限定词对应。这些分句不用重复填写units或内部qualifier_bindings；缺失、伪造、重复、fail/unknown或额外篡改坐标均拒绝。发生文字改变的分句、原分句子串、跨原段调换或接入新限定词的分句不能使用此简化。改动处的命题对应、14维、claims、双向检查、收益及全文衔接仍完整保留。提供完整旧式units也继续有效。

预告unit覆盖的“本项目/该研究/本阶段/仅在/截至”等已识别范围词，必须由相同原位置的存留主题/条件/立场/引文或原样分句证据覆盖。范围词检测只是有限词法拦截，不能证明其他范围和语义完整。

### v1.3精确引文编译

推荐从 `compact_review_template` 使用 `review_format: "compact-1"`。该模板所有判断仍是unknown。简式中，dimensions每个维度只需 `{status,note}`，claims每项只需 `{id,status,note}`；程序把当前完整原文及候选作为各项before/after证据上下文，并明确记录此来源。note须说明该维度实际核对的对象、关系或两文为什么没有该项，不能用空串或笼统“通过”。逐信息单元仍须给精确局部引用。少一个维度、明确失败或没有依据均不能通过。

简式information_review沿用status、covered_paragraph_ids、units、verbatim_units、qualifier_bindings和topic_preserved；不重复填写before_hash/after_hash，由顶层绑定值展开。units按kind提交：

- `discourse_preview`：仅id/kind/status/before/topic_units/note。选择该kind即声明所引文字是纯行文动作、没有研究承诺，仍须实际复核；after与三种anchor字段省略，由程序填空。不能填存留的主题。
- `topic/condition/stance/citation`：id/kind/status/before/after/note；三种anchor可省略，topic_units省略。
- `research_fact`：id/kind/status/before/after/subject/action/conditions/note；anchor的before/after精确引用照旧，topic_units省略。

所有简式units省略pure_discourse/no_research_commitment，程序按已声明kind展开这两项固定布尔值，不推断文本分类，也不生成status/note。无证据的事实不能靠省略anchor通过。global_coherence可省略重复哈希与reviewer_model，程序使用顶层绑定哈希及实际reviewer.model。显式提供相冲突的哈希或旧式旗标覆盖会被拒绝。编译后去掉review_format并记录binding_metadata，产物可重复编译，判断不变。旧完整格式继续支持。

`bind-review` 读取普通review形状。information units、subject/action/conditions、qualifier_bindings和benefit的span列表可暂用 `{text:"精确子串",occurrence:0}`；occurrence是该子串在完整before或after中的出现序号，包含重叠出现，从0计。唯一出现可只写text；重复出现未指定序号则拒绝。已计算的 `{start,end,text}` 仍可使用。不可混入额外字段、猜测引文、负数或不存在的序号。

它只深拷贝并编译引用；不改变正文、判断、reviewer来源，不补缺失通过结论，不替代apply。before_hash/after_hash必须已绑定本次原文及候选。重复编译合法坐标不改变结果；原始模型review和编译后的review分别保存。JSON字段缺失仍按恢复流程处理，不能借编译重试覆写首次失败判断。

事务 `mechanical` 和报告 `final_mechanical` 保留原始fail。通过裁定时另有 `model_adjudications` 与 `final_validation`，后者明确 `raw_mechanical_status=fail`、`count_adjudicated_by_model=true`、`equivalence_proven=false`。不能把它写成“机械全通过”或人工验证。局部回退改变最终候选hash时，不复用旧计数裁定；本版保守回退相关裁定改动，不能仅补全文连贯性就借旧作用域证据放行。

## v1.2编辑收益复核

`require_benefit=true` 时，事务还需下列字段；主动提供该字段也会验证，不会忽略fail/unknown。

```json
{"benefit_review":{"status":"pass","problem_type":"buried_topic","problem_before":[{"start":0,"end":8,"text":"实际原文问题片段"}],"resolution_after":[{"start":0,"end":8,"text":"实际改后解决片段"}],"observed_gain":"描述读者能观察到的问题解决","note":"具体判断依据"}}
```

`problem_type` 只接受 `redundant_discourse, duplicate_information, unclear_referent, buried_topic, reading_order`。两个片段数组均非空、位于改动段落，原问题须与实际补丁相交；完全删除整段而没有解决片段不能通过。缺项、fail/unknown、假引文，以及单称“更短/简洁/替换近义词”的收益拒绝。具体问题是否成立、改后是否真正改善仍由模型复核；该门只校验结构、引用位置、覆盖和最低说明，不能把文字说明当作客观表达效果证明。

## 修复与停止

复核格式缺失与正文错误分开恢复，见 [失败处理](recovery.md)。相同候选允许一次格式补取，完整fail/unknown不能靠反复补取改成pass。机械报告的 `duplicate_deletion_evidence` 记录相邻完全重复句的限定词计数依据；数值/引用不豁免。`unresolved_group_bindings` 非空时，当前机械层没有验证该多组关系。

至多一次修复。repair_bundle 以原稿坐标提交完整补丁包，原补丁 ID 集合必须保持；已通过的无关补丁不能改变；原段、原范围、old、depends_on、claim_ids 不变。修复只针对首轮失败事务，重新审查候选哈希。第二次仍 fail/unknown 则回退；核心函数不调用模型、不递归修复。

最终状态：`no_op`、`checked_edit`、`partial_rollback`、`all_rollback`、`execution_failed`。`checked_edit` 表示通过当前机械检查及已提供模型复核，绝非完全等义证明。

## CLI

```powershell
python .agents/skills/academic-deai-zh/scripts/deai.py prepare --input input.md --output task.json --mode standard --genre paper
python .agents/skills/academic-deai-zh/scripts/deai.py scan --input input.md --output scan.json
python .agents/skills/academic-deai-zh/scripts/deai.py build-bundle --input input.md --edits edits.json --output patches.json
python .agents/skills/academic-deai-zh/scripts/deai.py review-request --input input.md --patches patches.json --format compact --output review-request.json
python .agents/skills/academic-deai-zh/scripts/deai.py bind-review --input input.md --patches patches.json --review review-quotes.json --output review.json
python .agents/skills/academic-deai-zh/scripts/deai.py apply --input input.md --patches patches.json --review review.json --output result.json
python .agents/skills/academic-deai-zh/scripts/deai.py check --before input.md --after draft.md --output mechanical.json
python .agents/skills/academic-deai-zh/scripts/deai.py export --input input.md --result result.json --output-dir fresh-output
```

`apply` 还可同时给 `--output-dir`。修复参数为 `--repair-patches`、`--repair-review`；局部回退通读用 `--coherence-review`。CLI 无模型调用，不要求 API Key，机械 check 不会放行改稿。

标准库-only；Word 只读抽取导出 TXT，不支持保格式回写。
