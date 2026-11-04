# AudienceLens 优化方向交接文档

> ## ⚠ 本文档已部分过期（2026-09-20 复核）
>
> 它是 commit `9a90599` 那一轮的交接稿，多数条目已经完成或前提已变。下面用
> ~~删除线~~ 标出**已完成/已失效**的条目并注明现状，未划掉的仍然有效。
> 新接手请先读 [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) 与 [`AGENTS.md`](../AGENTS.md)，
> 本文只当作"还剩哪些方向没做"的清单。
>
> 原基线里那个写死的测试数已删除而不是更新：测试数
> 每次提交都在变，写死一个就等着它再过期一次（仓库规则见 AGENTS.md「变更校验」，
> 由 `tests/test_public_claims.py::test_test_counts_are_stated_once_and_dated` 卡着）。
> 判据只有一条：`python -m pytest tests/ -q` 退出码为 0。

> 写给接手的开发者/AI（GLM 等）。本文档假设你没有任何上下文，按优先级列出具体任务、涉及文件、验收标准。

## 接手前先做的三件事

```bash
# 1. 确认测试基线没有退化（判据是退出码 0，这里不写期望条数——写死必过期）
python -m pytest tests/ -q

# 2. 跑离线刻板印象评测，记录正则层基线数字（准确率/精确率/召回率）
python -m src.cli stereotype-eval

# 3. 有 ANTHROPIC_API_KEY 后跑这两个，拿到本文档多处引用的"关键数字"
python -m src.cli stereotype-eval --llm
python -m src.cli ablation concept_review examples/steam-page-sample/artifact.json --limit 4 --output ablation.json
```

**重要约定（不要破坏）：**
- 无 API key 时系统退回模拟模式，模拟输出是无价值占位数据，CLI 和报告中的警告（`src/runner/cli.py` 的 `SIMULATION_WARNING`）**不可删除或弱化**
- 人格只能用行为向量（patience、price_sensitivity 等 12 轴）做因果推断，人口统计特征（性别/年龄/地域/MBTI）只能修饰表达风格——这是全项目的伦理底线，详见 `ETHICS.md`
- `pytest.ini` 设了 `pythonpath = src`，测试内 import 用 `from runner.xxx` / `from harness.xxx`，不带 `src.` 前缀；`src/cli.py`（统一 CLI）则用 `from src.runner import ...`，从仓库根目录以 `python -m src.cli` 运行

---

## P0：把已搭好的实验跑出数字（半天，需要 API key）

代码都写完了，缺的只是执行和记录结果。

1. **消融实验出数**：跑上面第 3 步的 ablation 命令。预期故事线：`full` 条件的三项分化度指标（issue_divergence / severity_js / stance_entropy）显著高于 `bare`，且 `full` 对 `no_behavior` 的增量证明分化主要来自行为向量。
   - 结果写入 `docs/` 下新建的实验记录，并更新 README 的卖点段落
   - 如果 `full ≈ no_behavior`，这是重要负面发现：说明行为向量没起作用，需要回头检查 `src/templates/persona-prompt.md` 里行为向量的呈现方式（可能被模型忽略了）
2. **两层刻板印象检测出数**：对比 `stereotype-eval` 和 `stereotype-eval --llm` 的召回率差距，写进 README 第 7 节（Ethics Framework），替换掉现在没有数据支撑的描述
3. **建议把多次运行的稳定性也测了**：ablation 加 `--limit 6` 跑 3 次，看指标方差。指标波动大于条件间差距的话，结论不成立，需要加大 N

## P1：语义去重的覆盖面扩展（1~2 天）

`src/runner/similarity.py` 已实现语义/词法双档（bge-small-zh-v1.5，无依赖时回退 SequenceMatcher），但目前只接入了一个调用点。

1. ~~**`src/runner/cross_exam.py:128` 附近**：`find_opposing_stances` 里还在用旧的 `_similarity(...) > 0.5` 词法匹配~~ ✅ 已完成：`cross_exam.py` 现在三处（181 / 245 / 348 行）统一走 `similarity if similarity is not None else get_issue_similarity()`，文中那行 `_similarity(...) > 0.5` 已不存在
2. **`src/runner/aggregator.py:56-70`**：`compute_disagreements` 用议题 title **精确相等**分组（`issue_map[title]`），比 cross_exam 还原始——同一问题换措辞就分不到一组。改成与 cross_exam 相同的相似度合并逻辑，并复用同一个 `IssueSimilarity` 实例（embedding 有缓存，复用才省算力）
3. **`src/harness/evaluator.py` 的 persona_differentiation 维度**：现在用 Jaccard ≥ 0.3，可加语义档算分化度，与 ablation 的 `issue_divergence` 指标统一口径
4. **贪心合并改聚类**：`extract_controversy_points` 目前是"遍历时贪心合并到第一个相似项"，结果依赖输入顺序。改成简单的层次聚类（每轮合并相似度最高的一对，低于阈值停止）
5. 验收：新增对应单测；`tests/test_similarity.py` 的语义测试装上 `sentence-transformers` 后必须通过（目前是 skip 状态，**还没在真模型上验证过阈值 0.75 是否合理**，这是已知未验证点）

## P2：LLM judge 的成本与质量（1~2 天，需要 API key）

`src/harness/stereotype_judge.py` 的已知弱点：

1. **逐段调用太贵**：`detect_stereotypes` 对每段文本单独调一次 Haiku。改成按 persona 批量：一次请求带多段文本，返回 JSON 数组。注意保持 `llm_detect` 的单段接口兼容（有测试依赖）
2. **judge prompt 没有 few-shot**：把 `tools/stereotype_eval_cases.yaml` 里挑 4 条典型（2 违规 2 合规，注意从评测集里**移除**被用作示例的条目，否则数据泄漏）放进 prompt，预期精确率提升
3. **评测集扩容**（部分完成）：`tools/stereotype_eval_cases.yaml` 已扩到 50 条（写这行时的实测值，条数以 `test_public_claims.py` 的现算为准）。仍值得继续补的方向：地域刻板印象的隐式表达、"数据显示某群体如何"的伪证据句式、行为向量与身份混写的边界用例
4. **失败静默问题**：`llm_detect` 所有异常都返回 None（按跳过处理）。加一个可选的 verbose/日志通道，否则线上 key 失效时检测会无声降级为纯正则——`detection_method` 字段虽然会如实记录，但没人主动看

## P3：工程收尾（1 天，无 API key 也能做）

1. ~~**仓库根目录清理**~~ ✅ 已完成（2026-07-19）：一次性脚本已移入 `scripts/archive/`（含 README 声明其为非标准流水线的一次性会话脚本，禁止静默复用）；`audiencelens-landing-page.zip`/根目录 `index.html`/`docs/landing-page.html` 在此前会话中已删除；`tools/parity-check.py` 死代码副本已删除（保留 `tools/parity_check.py`，并同步修正了各文档引用）；重复的 `arxiv-paper*.md` 已统一到 `docs/paper/`；`docs/project-guide.md`/`docs/operation-guide.html` 顶层副本已删除（保留 `docs/project/` 下的版本；`docs/project/operation-guide.html` 已于 2026-11-04 删除）；`demo-report.html`/`demo-summary.md`/`CODE_WIKI.md` 孤立文件已删除。三个 harness 关系已在 [ARCHITECTURE.md](ARCHITECTURE.md) 补充说明：`src/harness/` 是内置引擎，`audiencelens-v0.2-harness/` 是后端运行时依赖（已修复其双重嵌套的目录结构问题），`audiencelens-harness/` 是完全独立的开源发行仓库（有自己的 `.git`，不做迁移——其 `.git/config` 里曾发现疑似明文 GitHub PAT，已于 2026-07-22 轮换并移除）
   - **保留原因**: `scripts/archive/` 保留作为历史参考，防止未来会话误用同名脚本；如需彻底清理可直接删除
2. ~~**CLI 入口统一**~~ ✅ 已完成：`pyproject.toml` 的 `[project.scripts]` 已注册 `audiencelens = "src.cli:main"` 与 `audiencelens-mcp = "src.mcp_server:main"`；`src/runner/cli.py` 的 `main()` 保留但不再是首选入口
3. ~~**`VALID_TASK_TYPES` 不一致**~~ ✅ 已完成：任务类型已从 `cli.py` 搬到唯一事实源 `src/runner/task_types.py::VALID_TASK_TYPES`，两边同源不再可能不一致；条数由 `tests/test_public_claims.py` 现算并与 README 比对（所以这里也不写死条数）
4. ~~**Python 版本确认**~~ ✅ 2026-09-14 已统一到 3.11：pyproject `requires-python>=3.11`、`.claude/launch.json` 后端改用 `py -3.11`、README 徽章同步；引擎/后端两套测试在 3.11 下全绿。顺带修了 `web/backend/requirements.txt` 在中文 Windows 上被 pip 按 GBK 解码报错的问题（PEP 263 编码声明）并补上漏列的 `click`。`sentence-transformers` 仍是可选项，未在 3.11 验证安装

## 不要做的事

- 不要给模拟模式增加"更逼真的假数据"——方向相反，假数据越不像真的越好
- 不要把 LLM judge 默认打开（`use_llm` 默认 False 是有意的，成本控制权在用户）
- 不要在 persona YAML 里加人口统计字段的行为推断，schema 校验和 harness 维度会拦，但别绕过它们

## 关键文件地图

| 文件 | 作用 |
|---|---|
| `src/runner/similarity.py` | 语义/词法双档相似度（IssueSimilarity，带缓存） |
| `src/runner/cross_exam.py` | 争议点提取（已接语义去重）+ 交叉质询协议 |
| `src/runner/aggregator.py` | 聚合（P1-2 的改造目标，仍是精确匹配） |
| `src/harness/stereotype_judge.py` | 两层刻板印象检测（正则 + Haiku judge） |
| `src/harness/ablation.py` | 消融实验（条件构造 + 三个分化度指标，指标是纯函数） |
| `src/harness/evaluator.py` | 8 维质量评估（stereotype_check 已接两层检测） |
| `src/cli.py` | 统一 CLI：run / personas-validate / harness-evaluate / parity-check / stereotype-eval / ablation |
| `tools/stereotype_eval.py` + `_cases.yaml` | 检测评测脚本 + 标注集（条数现算，见 `test_public_claims.py` 的 `stereotype_case` 指标） |
| `tests/test_similarity.py` `test_stereotype_judge.py` `test_ablation.py` | 本轮新增测试，全部离线可跑 |
