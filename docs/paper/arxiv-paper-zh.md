---
title: "AudienceLens：一种用于合成受众评审的多智能体交叉质询框架"
authors:
  - name: 熵呓工作室
    affiliation: 熵呓工作室
abstract: |
  传统用户研究面临成本高、周期长、可重复性差等问题。近年来基于大语言模型（LLM）的人物模拟技术取得了重要进展，为大规模生成合成用户访谈提供了有前景的替代方案；但它同样让"听上去很像、实则没有任何依据"的合成用户反馈变得极其廉价。我们提出 AudienceLens——一个用于合成受众评审的开源原型，其**已实现**的贡献是约束机制而非模拟保真度：（1）三级证据溯源——每条主张都标注 `direct` / `inferred` / `gap`，校验器会驳回推断证据占比超过 40% 的人格输出；（2）结构性的身份-行为解耦——人口统计字段（性别、年龄、地区）在人格载荷送入模型之前即被剔除，因此人口统计因果推理对模型而言是"不可得"，而非"被劝阻"；（3）8 维 Harness 评估量表，其阈值集中声明在单一配置文件中、由代码在运行时读取，并自带"原型阈值，未经实证验证"标注。此外我们**给出规范但尚未实现**三轮交叉质询协议、置信度门控的投票变更机制与共识演化追踪；在当前版本（v0.3.0）中，报告里的交叉质询区块是从单轮人格输出派生出的摘要，运行时自身即如实标注（`mode: "derived_summary"`、`is_live_debate: false`、`vote_changes` 恒为空）。本次发布包含 10 个人格包共 66 个行为驱动人物、14 种任务类型。我们讨论了包括缺乏真实世界对等性研究在内的局限性，并给出同时覆盖"补齐未实现机制"与"实证验证"的路线图。
keywords: [多智能体系统, 合成受众, 交叉质询, 人物模拟, LLM评估, AI伦理]
---

# AudienceLens：一种用于合成受众评审的多智能体交叉质询框架

## 摘要

传统用户研究面临成本高、周期长、可重复性差等问题。近年来基于大语言模型（LLM）的人物模拟技术——以 SyntheticUsers 及类似平台为代表——取得了重要进展，为大规模生成合成用户访谈提供了有前景的替代方案。但它同样让"听上去很像、实则没有任何依据"的合成用户反馈变得极其廉价，这正是本工作针对的失效模式。

我们提出 **AudienceLens**——一个用于合成受众评审的开源原型。它已实现的贡献是约束机制，而非模拟保真度：

1. **带硬上限的三级证据溯源。** 人格输出中每条主张都标注 `direct`、`inferred` 或 `gap`；校验器驳回 `inferred` 占比超过 40% 的输出。
2. **结构性的身份-行为解耦。** 人口统计字段（性别、年龄、地区）在人格载荷序列化进提示词之前即被剔除，因此人口统计因果推理对模型是*不可得的*，而不只是被指令劝阻。
3. **8 维 Harness 评估量表**，其阈值集中声明在单一配置文件中、由代码在运行时读取，并自带"原型阈值，未经实证验证"标注。

此外，我们**给出规范但尚未实现**三轮交叉质询协议（立场陈述、反驳、最终立场）、置信度门控的投票变更机制（$\theta_{\text{change}} = 0.15$）、变更溯源、共识演化分类与临界点检测。在当前版本（v0.3.0）中**不存在任何真实的多智能体辩论**：报告中的交叉质询区块是从单轮人格输出派生的摘要，运行时将其标注为 `mode: "derived_summary"`、`is_live_debate: false`，且 `vote_changes` 为空列表。第 4.6 节逐条给出每项机制的实现状态。

本次发布包含 10 个 YAML 人格包共 66 个行为驱动人物、14 种任务类型。我们提出身份-行为解耦原则，并阐述以欧盟《人工智能法案》为参考的设计考量。我们讨论了包括缺乏真实世界对等性研究在内的局限性，并给出同时覆盖"补齐未实现机制"与"实证验证"的路线图。与真实用户的实证验证对*全部*组件（无论已实现还是仅有规范）都仍属于未来工作。

## 1. 引言

用户研究是产品开发的基石，然而它仍然是设计周期中资源消耗最大的活动之一。一轮有主持的可用性测试通常需要 2–4 周的规划、\$5,000–\$15,000 美元的参与者报酬，且产生的结果在不同会话间难以复现 (Nielsen, 1994; Lazar et al., 2017)。焦点小组虽然在收集多元观点方面效率较高，但容易受到群体思维（Groupthink）、锚定偏差（Anchoring Bias）和强势声音影响 (Morgan, 1997)。基于调查的方法更容易扩展，但以深度换广度，产生的统计汇总掩盖了个体推理过程。

大语言模型（LLM）的出现开辟了一个新前沿：*合成用户研究*。SyntheticUsers 等商业平台声称与真实用户具有高度一致性，但独立验证仍然有限。Park et al. (2023) 表明，生成式智能体（Generative Agents）可以在沙盒环境中表现出可信的社会行为。Horton (2023) 提出了 *homo silicus*——可以作为经济学研究实验对象的计算智能体。Argyle et al. (2023) 证明单个 LLM 就能以惊人的保真度模拟多样化的子群体，捕捉不同人口群体在态度和行为上的差异。

然而，这些方法共享一个关键局限：它们将合成用户模拟视为*独白*（Monologue）而非*对话*（Dialogue）。每个人物独立响应，不接触对立观点，没有机会修正自身立场，也没有任何机制来检测共识是真实的还是表面的。这与真实焦点小组的运作方式根本不同——在真实焦点小组中，参与者相互质疑假设，因有说服力的论点而改变观点，有时会收敛到意想不到的立场。

我们提出 **AudienceLens**——一个用于合成受众评审的开源原型。我们把"当前版本（v0.3.0）真正执行的"与"仅有规范的"分开列出，因为这个区分决定了读者能依赖什么。

**已实现的贡献。**

1. **带硬上限的三级证据溯源。** 人格输出中每条主张都带有 `direct` / `inferred` / `gap` 标注，校验器驳回 `inferred` 占比超过 40% 的输出（`src/runner/validator.py`）。这是代码强制执行的，不是提示词里的请求。

2. **结构性的身份-行为解耦。** 人格记录在序列化前被裁剪：只有固定的 `CORE_FIELDS` 白名单（行为画像、动机、决策规则、退出/继续触发器、首屏关注点）会被注入提示词。模型自始至终看不到性别、年龄、地区，因此人口统计因果推理在结构上不可得，而非仅被禁止。输出侧另有两层刻板印象检测（正则初筛，以及配置了 API Key 时启用的 LLM 复审）作为第二道防线。

3. **8 维 Harness 评估量表**，阈值集中声明在运行时读取的单一配置文件（`src/harness/thresholds.yaml`）中，且该文件自带机器可读的"原型阈值，未经实证验证"标注。我们将其描述为*事后打分卡而非门控*：默认关闭，在评审完成之后运行，不过滤、不拦截、不重跑任何人格输出。

4. **开源实现**（MIT），具备 CLI、Python API、MCP 服务、Web 与 Docker 多个入口，内置 10 个 YAML 人格包共 66 个行为驱动人物、14 种任务类型，并预置六家模型供应商配置。

**设计贡献：有规范，未实现。**

5. **三轮交叉质询协议**（立场陈述、反驳、最终立场），含置信度门控的投票变更机制（$\Delta c > \theta_{\text{change}}$，$\theta_{\text{change}} = 0.15$）、完整变更溯源、四模式共识演化分类与临界点检测。第 3.3–3.6 节给出规范；**第 4.6 节记录了这些在 v0.3.0 中一项也没有执行**。简言之：报告中的交叉质询区块是从单轮人格输出派生的摘要，由运行时自身标注为 `mode: "derived_summary"` 和 `is_live_debate: false`；`vote_changes` 恒为空，所报告的置信度增量被硬编码为 0；$\theta_{\text{change}} = 0.15$ 只存在于配置文件和提示词文本中，没有任何 Python 模块读取它；共识演化与临界点检测则完全没有实现。

**规范性贡献。**

6. **身份-行为解耦原则**：主张人格判断必须能因果追溯到行为画像与动机，绝不能追溯到人口统计属性（性别、年龄、地区、MBTI）。上文第 2 项是它已落地的执行手段。

本文其余部分组织如下：第 2 节回顾相关工作；第 3 节介绍方法，其中同时包含已实现与仅有规范的机制；第 4 节详述实现，并在第 4.6 节给出实现与规范的逐条对照；第 5 节描述评估框架；第 6 节讨论伦理考量；第 7 节阐述局限性与未来工作；第 8 节为结论。

## 2. 相关工作

### 2.1 生成式智能体与人物模拟

合成受众研究的基础在于 LLM 采纳和维持一致人物的能力。Park et al. (2023) 引入了栖息于沙盒小镇的生成式智能体，表现出包括关系形成、事件协调和信息扩散在内的涌现社会行为。他们的架构——由记忆流（Memory Stream）、反思（Reflection）和规划（Planning）组成——证明了基于 LLM 的智能体可以在长时间交互中保持行为一致性。

Argyle et al. (2023) 表明，LLM 在以人口统计特征为条件时可以模拟多样化的子群体，捕捉群体间态度和意见的差异。他们的"硅基受试者"（Silicon Subjects）方法表明 LLM 可以作为人类调查受访者的低成本替代，但他们告诫不应将合成响应等同于真实人类数据。

Horton (2023) 将这一研究方向扩展到经济学，提出了 *homo silicus*——参与经济学实验的计算智能体。他认为基于 LLM 的智能体可以作为人类经济行为的"无损"压缩，使研究人员在投入昂贵的人类研究之前能够快速迭代实验设计。

近年来，人物模拟已被应用于软件工程领域。Xu et al. (2024) 证明 LLM 人物可以在需求工程中模拟多样化的用户视角，而 Salehi et al. (2024) 使用人物驱动的评估来评估 Web 应用的可访问性。

### 2.2 合成用户研究

商业合成用户研究平台的出现旨在解决传统方法的成本和速度限制。**SyntheticUsers** (2024) 是一个提供 AI 主持的合成参与者访谈的商业平台。SyntheticUsers 等商业平台声称与真实用户具有高度一致性，但独立验证仍然有限。他们的方法使用 OCEAN（大五人格）模型构建人物档案，并生成访谈式响应。然而，SyntheticUsers 运行在单轮访谈范式下——每个人物独立回答问题，不接触其他人物的观点。

**Outset** 采用混合方法，使用 AI 大规模主持真实人类访谈。虽然这保留了人类响应的真实性，但并未解决推动合成方法发展的成本和速度限制。**Yabble** 提供 AI 驱动的调查分析，但依赖与人口统计标签化人物的单轮交互，这存在强化刻板印象而非捕捉真实行为多样性的风险。

这些平台共享三个局限：（1）人物之间没有交叉质询；（2）没有立场修正机制；（3）没有合成评审输出的系统性质量评估框架。AudienceLens 以已实现的评估量表回应了（3）（第 3.7 节），并对（1）（2）给出了规范但尚未实现（第 3.3–3.6 节，状态见第 4.6 节）。

### 2.3 多智能体辩论

Du et al. (2023) 证明多智能体辩论可以提高语言模型的事实性和推理能力。在他们的框架中，多个 LLM 实例为不同立场辩论，每个智能体根据其他智能体的论点改进自己的响应。这种方法在数学推理和事实问答任务上提升了性能，表明对抗性交互可以发现单智能体生成所遗漏的错误。

Liang et al. (2023) 将此工作扩展到鼓励多智能体辩论中的多样性，表明强制不同视角可以促成更稳健的共识形成。Chan et al. (2023) 提出了 chatmap 用于扩展多智能体协作，证明结构化交互协议优于非结构化群聊。

Wang et al. (2024) 引入了通过迭代辩论实现多智能体共识的框架，表明收敛性质取决于智能体交互拓扑和证据强度。他们的工作强调了过早共识的风险——智能体在没有充分探索论据空间的情况下过快收敛。

AudienceLens 在这些洞察的基础上，*给出*了带有明确立场修正和共识追踪机制的结构化三轮辩论协议规范。与通用多智能体辩论不同，该协议专门为受众评审领域设计，其目标不是找到单一正确答案，而是绘制观点全景并识别真正存在分歧的领域。需要强调：该协议是本文的设计贡献，当前实现并不执行它（第 4.6 节）。因此我们不对其行为作任何实证声称，读者也不应把上述辩论文献当作 AudienceLens 输出质量的佐证。

### 2.4 人物生成中的 AI 伦理

合成人物生成的伦理维度日益受到关注。早期的 UX 研究早已论证，行为、目标和情境比单纯的人口统计特征更具可操作性的人物属性 (Cooper 1999; Pruitt & Adlin 2006)。这一洞察直接启发了我们的身份-行为解耦原则。

欧盟《人工智能法案》(2024) 为 AI 系统建立了透明度要求，包括披露 AI 生成内容的义务（第 50 条）、确保人类监督（第 14 条）和维护准确性（第 15 条）。这些要求对合成受众系统尤为重要，因为其输出可能被误读为真实用户研究数据。

Nielsen Norman Group 的人物方法论一直倡导行为优先的人物设计，认为人物应由目标、行为和痛点而非人口统计属性来定义 (Mulder & Yaar, 2006)。AudienceLens 通过其 `behavior_profile` 构造将这一原则付诸实践，用面向任务的行为维度取代了传统的 OCEAN 人格模型。

## 3. 方法

### 3.1 系统架构

人物池包含 **10 个 YAML 包共 66 个人物**，服务 **14 种任务类型**。下表全部数字均可对照 `src/personas/` 目录与唯一权威注册表 `src/runner/task_types.py` 中的 `VALID_TASK_TYPES` 核验：

| 人格领域 | 包 | 人物数 | 服务的任务类型 |
|---|---|---|---|
| 游戏 | 8（`game-core` 16、`mobile-f2p` 7、`competitive-esport` 5、`family-casual` 5、`indie-creative` 5、`accessibility` 4、`educational-serious` 4、`vr-immersive` 4） | 50 | 10（`steam_page_review`、`demo_first_play`、`concept_review`、`monetization_review`、`looking_for_party_post`、`update_announcement_review`、`devlog_review`、`kickstarter_review`、`localization_review`、`discord_community_review`） |
| 通用产品 | 1（`general-consumer` 8） | 8 | 3（`product_feedback_review`、`pricing_page_review`、`onboarding_review`） |
| 创业 / 路演 | 1（`startup-panel` 8） | 8 | 1（`pitch_review`） |
| **合计** | **10** | **66** | **14** |

三个评审技能（`synthetic-playtest`、`audience-panel`、`red-team-audience`）与一个元技能（`persona-generate`）作为该人物池之上的技能包前端。这里需要澄清两点，因为本系统此前的描述在这两点上都不准确。第一，**`red-team-audience` 没有自己的人格包**：`src/personas/` 中不存在任何红队人格，"红队"只是覆盖在既有人物池之上的技能层框定方式，而非一组独立的人格定义。第二，`persona-generate` 是写在技能 Markdown 里、由 LLM 驱动的人格创作流程，不是代码路径；它产出的是新的 YAML 人格包，而非运行时实体。

一个关键的架构性质是人格之间的**上下文隔离**。每次人格评审都是一次独立、无状态的模型调用，由线程池派发（`src/runner/cli.py` 中的 `concurrent.futures.ThreadPoolExecutor`）；每次调用只收到它自己的人格载荷、目标材料与任务评分标准。人格调用之间不共享任何对话状态、推理链或中间结果。这防止了交叉污染（一个人物的推理泄漏到另一个人物中）。请注意我们描述的是"线程 + 逐调用构造提示词"，而非操作系统子进程；隔离保证来自调用本身的无状态与独立构造，而非进程边界。第 3.3 节所述"影响通过共享立场池传播"属于交叉质询规范，v0.3.0 并不执行（第 4.6 节）。

### 上下文隔离实现

下面第 1、2、4 项描述已实现的流水线。**第 3、5 项描述的是交叉质询规范，在 v0.3.0 中并不执行**（第 4.6 节）；列在此处只为设计的完整性。

1. **输入阶段**（已实现）：每个人物智能体接收：
   - 目标材料摘要（截断以适应上下文窗口）
   - 人物 YAML 定义（behavior_profile、motivations、decision_rules）
   - 任务评分标准和输出模式
   - 评审模式参数（quick/standard/full）

   人口统计字段在这一步被排除：只有 `CORE_FIELDS` 白名单会被序列化（第 6.1 节）。

2. **隔离保证**（已实现）：每个人物智能体**不会**接收：
   - 其他人物智能体的完整输出
   - 其他人物智能体的私有推理链
   - 聚合笔记或中间结果
   - 关于评审小组中其他人物的信息

3. **反驳阶段**（有规范；未实现）：在规范中的交叉质询轮次里，人物智能体将接收匿名化的争议主张、按相关性筛选出的对立论据，以及自己先前的输出供参考。v0.3.0 不执行任何此类轮次。

4. **立场池**（作为聚合输入已实现）：人格输出存储为结构化 JSON 对象，包含 stance、confidence、key_issues 和 evidence 数组，由聚合层消费而非由各人物智能体管理。在 v0.3.0 中该池仅在单轮评审之后被读取一次。

5. **匿名化归属**（有规范；随包发布的模板恰恰相反）：设计意图是反驳提示中不出现人物名称，论据仅以论据 ID 标注（例如 "Argument A3"），使智能体无法基于身份结盟。**我们必须如实报告：随包发布的模板并没有这样做。** `src/templates/cross-exam-prompt.md` 直接把 `{{pro_persona_name}}` 与 `{{con_persona_name}}` 插值进提示词正文。由于反驳轮次根本不执行，该模板在 v0.3.0 中从未被送入模型，这一出入对当前输出没有影响——但匿名化绝不能被当作本系统的方法有效性保证来宣称，我们也不作此宣称。

系统在九个阶段运行，编号 0–8：（0）论据解析，（1）任务类型验证，（2）材料加载，（3）评审小组选择，（4）并行人物评审，（5）交叉质询，（6）报告聚合，（7）校准检查，和（8）输出生成。阶段 5 和 7 在 `quick` 模式下跳过；所有阶段在 `full` 模式下执行。`full` 模式下的阶段 5 产出的是派生摘要，而非真实辩论（第 4.6 节）。

### 3.2 人物设计

每个人物由一个 YAML 规范定义，包含身份字段、行为档案、动机、决策规则和评审配置。核心创新是 **behavior_profile**——一个取代传统人格模型的 12 轴行为向量：

全部十二轴在 `src/schemas/persona-schema.json` 中均为 `required`，且该 schema 设置了 `additionalProperties: false`；下表即完整且精确的轴列表：

| # | 轴 | 范围 | 描述 |
|---|----|------|------|
| 1 | `patience` | very_low – very_high | 对摩擦和延迟的容忍度 |
| 2 | `genre_literacy` | very_low – very_high | 领域特定知识深度 |
| 3 | `novelty_seeking` | very_low – very_high | 对新颖而非熟悉的偏好 |
| 4 | `risk_tolerance` | low – high | 对不确定性的舒适度 |
| 5 | `social_influence` | low – very_high | 对社会证明的易感性 |
| 6 | `completion_drive` | very_low – very_high | 完成已开始事项的动力 |
| 7 | `price_sensitivity` | low – very_high | 对成本相对于价值的敏感度 |
| 8 | `criticism_style` | categorical | 表达不满的方式 |
| 9 | `emotional_engagement` | low – high | 情感投入的深度 |
| 10 | `agency_preference` | low – high | 对玩家/用户自主权的渴望 |
| 11 | `tolerance_for_ambiguity` | very_low – very_high | 对不明确情境的舒适度 |
| 12 | `platform_loyalty` | very_low – high | 对特定平台或商店的黏着度 |

所有人格包（包括非游戏包）该轴一律命名为 `genre_literacy`；不存在单独的 `domain_literacy` 字段。

这一设计有别于 SyntheticUsers 所使用的 OCEAN（大五人格）模型。我们认为 `behavior_profile` 更适合评审任务，原因有四：

1. **任务导向性**：评审是一种任务导向行为，而非社会行为。OCEAN 维度中的外向性（Extraversion）和宜人性（Agreeableness）主要描述社会交互模式，在人物独立评估产品时基本无关。`behavior_profile` 直接建模与任务相关的行为（耐心、完成驱动力、风险容忍度），每个维度的信息密度更高。

2. **预测性 vs 描述性**：OCEAN 回答"这是什么样的人？"，而 `behavior_profile` 回答"这个人物在评审任务中会怎么做？"后者直接服务于输出的可解释性和可追溯性。

3. **降低共线性**：在评审情境中，OCEAN 的尽责性（Conscientiousness）和开放性（Openness）维度以高度相似的方式影响评审行为（两者都表现为对细节的关注）。`behavior_profile` 将这些分解为更细粒度的行为驱动因子（`completion_drive` 与 `novelty_seeking`），避免了维度冗余。

4. **直接可追溯性**：我们的伦理框架要求所有判断可追溯到 `behavior_profile` 或 `motivations`。使用 OCEAN 标签会引入间接映射层，增加合规审计的复杂度。

OCEAN 与 `behavior_profile` 之间的映射如下：openness_to_experience 映射到 `novelty_seeking` + `tolerance_for_ambiguity`；conscientiousness 映射到 `completion_drive` + `patience`；extraversion 映射到 `social_influence`；agreeableness 反向映射到 `emotional_engagement`；neuroticism 反向映射到 `risk_tolerance`。

每个人物还包括 `decision_rules`——控制判断的显式条件语句（例如"如果核心钩子在 15 秒内不可见，则不加入愿望单"）、定义留存/流失边界的 `quit_triggers` 和 `continue_triggers`，以及指定人物形成有据判断所需证据类型的 `evidence_types_needed`。

### 人物分类

| 包 | 数量 | 领域 | 关键行为 |
|----|------|------|----------|
| game-core | 16 | 游戏 | 核心探索、系统分析 |
| mobile-f2p | 7 | 游戏 | 商业化敏感度、会话设计 |
| indie-creative | 5 | 游戏 | 创新关注、审美判断 |
| competitive-esport | 5 | 游戏 | 技能上限、平衡性、公平性 |
| family-casual | 5 | 游戏 | 可访问性、新手引导、安全性 |
| vr-immersive | 4 | 游戏 | 沉浸感、舒适度、临场感 |
| educational-serious | 4 | 游戏 | 学习效果、参与度 |
| accessibility | 4 | 游戏 | 键盘/屏幕/认知无障碍 |
| general-consumer | 8 | 产品 | 日常产品/应用评估、定价、上手流程 |
| startup-panel | 8 | 创业 | 商业计划、路演材料、市场与融资质询 |
| **合计** | **66** | | |

每个人物由完整的 behavior_profile、motivations、decision_rules、quit_triggers 和 continue_triggers 定义。66 个人物的数量反映了跨领域的覆盖度，而非冗余；Jaccard 距离分析（第 5.2 节）衡量实际的差异化程度。这是 v0.3.0 版本的完整清单：不存在红队人格包，面向产品的人物池是两个包共 16 人，而非此前草稿中描述的六个更细分的包。

### 3.3 交叉质询协议（Cross-Examination Protocol）——规范，v0.3.0 未实现

> **实现状态。** 第 3.3 至 3.6 节给出的协议，当前版本并不执行。不存在真实的多智能体反驳：交叉质询没有发起任何 LLM 调用，`vote_changes` 恒为空，所报告的置信度增量被硬编码为 0，$\theta_{\text{change}}$ 没有任何代码路径读取。第 4.6 节给出逐条机制状态。这四节的全部内容都应被读作设计提案，而非系统行为的描述；本文任何一处报告的结果都不依赖于它们。

交叉质询协议是 AudienceLens *意图中的*核心差异化特性。按规范，它分为三个轮次进行：

**第一轮：立场陈述（Position Statement）。** 每个人物独立审查输入材料，并生成结构化输出，包括评分、关键问题、证据和主要立场。所有输出被收集到一个共享立场池中。关键在于，人物在此阶段并不知道彼此的存在——他们在完全隔离的状态下评估材料。

**第二轮：反驳（Rebuttal）。** 系统从第一轮输出中提取前 $k$ 个争议点，按各人物严重性评分的方差排序。对于每个争议点，系统识别持有最对立立场的两个人物，并为每一方生成结构化论证（主张 + 证据 + 推理链）。然后所有人物在 1–5 分制上评估每个论证的说服力。如果某个人物的置信度变化超过阈值（$\Delta c > 0.15$），他们可以更新自己的立场，并且必须记录原因。

**第三轮：最终立场（Final Stance）。** 每个人物产生其最终立场，如果他们在反驳阶段改变了观点，则最终立场可能与第一轮立场不同。系统记录完整的轨迹：初始立场、置信度轨迹、任何立场变化以及触发变化的论证。

如果连续两轮没有产生立场变化，表明已收敛，协议提前终止。

形式化地，设 $P = \{p_1, p_2, \ldots, p_n\}$ 为人物集合。在第一轮中，每个 $p_i$ 产生输出 $o_i^{(1)} = (s_i^{(1)}, c_i^{(1)}, e_i^{(1)})$，其中 $s_i^{(1)}$ 是立场，$c_i^{(1)} \in [0,1]$ 是置信度，$e_i^{(1)}$ 是证据集。争议点 $C = \{c_1, \ldots, c_k\}$ 通过以下方式提取：

$$C = \text{top-}k \left(\text{argsort}_{j} \left(\text{Var}(\{s_{1,j}^{(1)}, \ldots, s_{n,j}^{(1)}\})\right)\right)$$

其中 $s_{i,j}^{(1)}$ 表示人物 $p_i$ 对问题 $j$ 的严重性评分。在第二轮中，每个人物评估针对每个争议点的正反论证的说服力，产生更新的置信度 $c_i^{(2)}$。当满足以下条件时允许立场变化：

$$|c_i^{(2)} - c_i^{(1)}| > \theta_{\text{change}}$$

其中 $\theta_{\text{change}} = 0.15$。注意：$\theta_{\text{change}}$ 是规范中提出的工程参数，取值 0.15。它未经实证验证，需要按模型和领域调整。在当前代码库中，该值仅出现在 `src/config/aggregation-rules.yaml` 与提示词文本中；没有任何 Python 模块读取它，因此它目前是失效的（inert）。

### 3.4 投票变更机制（Vote Change Mechanism）——规范，v0.3.0 未实现

投票变更机制旨在建模真实的意见动态，同时防止级联从众效应。关键设计选择如下：

**置信度阈值。** 人物只有当其置信度变化超过 $\theta_{\text{change}}$ 时才能改变立场。选择该阈值是为了足够大以过滤噪声（LLM 输出概率的微小波动），同时足够小以捕捉真正的说服效果。我们承认该值是经验设定的，并计划在未来的工作中通过受控实验进行校准。我们不将自我报告的置信度视为校准后的概率；LLM 置信度分数可能不反映真实的认知不确定性。

**变更溯源。** 按规范，每次立场变化都将记录：(1) 触发变化的论证及其来源人物；(2) 变化前后的置信度；(3) 置信度差值；(4) 改变立场的人物提供的自由文本原因。这样的溯源链可支持对说服动态的事后分析。在 v0.3.0 中，交叉质询结果里的 `vote_changes` 数组被构造为空且从不填充，`confidence_changes` 每一项的 `delta` 字段被硬编码为 0，因此不会产生任何溯源数据。

**防串谋设计。** 人物之间不能直接通信；按规范，影响仅通过共享立场池传播，意在防止人物通过直接互动相互强化立场的"回音室"效应，并确保立场变化由论证质量而非社会压力驱动。此处需注明两点。第一，与之配套的论据匿名化性质并不存在于随包发布的提示词模板中（第 3.1 节第 5 项）。第二，由于反驳轮次根本不执行，该设计从未被检验过，我们不提供任何证据表明它达成了预期目标。

**无多数权重。** 系统不根据人物与多数派的一致程度进行加权。持有少数派立场的单个人物与五个一致的人物同样有效——价值在于理解他们*为何*不同意见，而非计算票数。

### 3.5 共识演化追踪（Consensus Evolution Tracking）——规范，v0.3.0 未实现

> **实现状态。** 代码库中不存在任何共识演化机制。标识符 `consensus_strength`、`converging`、`diverging`、`oscillating`、`tipping_point`、`cascade_point` 在 `src/` 下均无任何出现。系统实际计算的是 `src/runner/aggregator.py` 中的*单轮*立场分布，使用从 `src/config/aggregation-rules.yaml` 读取的 `consensus_threshold = 0.7`。既没有多轮轨迹可供分类，也没有分歧热点或极化输出。本小节其余内容描述的是"若实现了该机制会计算什么"。

按规范，三轮协议完成后，系统将把群体的共识轨迹分类为四种模式之一：

| 模式 | 定义 | 指标 |
|------|------|------|
| **收敛（Converging）** | 跨轮次一致性增加 | $\text{consensus\_strength}^{(3)} > \text{consensus\_strength}^{(1)}$ |
| **发散（Diverging）** | 跨轮次一致性降低 | $\text{consensus\_strength}^{(3)} < \text{consensus\_strength}^{(1)}$ |
| **稳定（Stable）** | 一致性近似不变 | $|\text{consensus\_strength}^{(3)} - \text{consensus\_strength}^{(1)}| < 0.1$ |
| **振荡（Oscillating）** | 一致性非单调波动 | 轮次间方向变化 |

共识强度定义为共享众数立场的人物比例：

$$\text{consensus\_strength}^{(r)} = \frac{|\{p_i : s_i^{(r)} = \text{mode}(S^{(r)})\}|}{n}$$

其中 $S^{(r)} = \{s_1^{(r)}, \ldots, s_n^{(r)}\}$ 是第 $r$ 轮的立场集合。

我们承认众数立场比例是一个粗粒度指标。未来版本应纳入：

- **置信度加权共识（Confidence-weighted consensus）**：按每个人物自我报告的置信度对其立场进行加权，使高置信度立场比低置信度立场贡献更大。
- **细分加权分歧（Segment-weighted disagreement）**：按人物细分相关性对分歧进行加权，使领域专家人物的反对比普通用户的反对权重更大。
- **少数派报告保留（Minority report preservation）**：即使共识很强，也明确标记并保留少数派立场，因为少数派视角往往能识别多数派忽略的风险。

规范还要求追踪**分歧热点（divergence hotspots）**——置信度变化最大的问题——以及**极化（polarization）**，定义为群体分裂为两个大致相等的对立阵营而非收敛的状态。两者均未实现。

### 3.6 临界点检测（Tipping Point Detection）——规范，v0.3.0 未实现

临界点（Tipping points）是讨论轨迹发生质变的时刻。规范定义了三种类型；**当前实现一种也检测不到**，因为它没有可供比较的跨轮次状态：

**翻转点（Flip points）**（红色）：人物从一个立场类别变为另一个立场类别（例如，从"会购买"变为"不会购买"）。这将表明反驳论证足够有说服力，克服了人物的初始立场。

**级联点（Cascade points）**（琥珀色）：一个人物的立场变化在同一轮次中触发了其他人物的变化。这将表明改变立场的人物的推理提供了与他人产生共鸣的新框架。

**锚定点（Anchor points）**（绿色）：人物在强反驳论证下仍维持其立场。这将表明深植的立场对说服具有抵抗力，通常与核心行为特征相关（例如，具有极高 `price_sensitivity` 的人物无论产品特性如何都拒绝认可该产品）。

规范中临界点的形式化检测规则为：

$$\text{TippingPoint}(r) = \begin{cases} \text{true} & \text{if } |\{p_i : s_i^{(r)} \neq s_i^{(r-1)}\}| \geq 2 \\ \text{true} & \text{if } \max_i |c_i^{(r)} - c_i^{(r-1)}| \geq 0.3 \\ \text{false} & \text{otherwise} \end{cases}$$

### 3.7 Harness 评估框架（Harness Evaluation Framework）

Harness 是一个 8 维度质量评估量表，根据量化阈值为已完成的合成评审打分。我们为原型评估定义了初始操作阈值。这些阈值不是经过验证的规范；它们作为工程护栏，应通过未来的实证工作进行校准。

在列出阈值之前，需要先说明实现的两项性质，因为它们界定了 Harness 能被声称做到什么：

- **它是事后打分卡，不是门控。** 该评估默认关闭（`enable_evaluation = False`），启用时也是在评审*完成之后*才运行。它不过滤、不驳回、不拦截、不重跑任何人格输出；不及格的分数也不会阻止报告产出。Harness 报告的一切都是诊断性的。
- **阈值集中声明、运行时读取。** 八项阈值全部位于 `src/harness/thresholds.yaml`，由评估器加载而非硬编码在代码里，且该文件带有 `threshold_note`，记录它们是未经实证验证的原型值。下表即该文件的逐条转录。

| # | 维度 | 核心问题 | 阈值 |
|---|------|----------|------|
| 1 | 可操作性（Actionability） | 建议是否具体且可执行？ | $\geq 70\%$ 的建议包含具体步骤（原型，未验证） |
| 2 | 输入依据（Input Grounding） | 论证是否引用了输入材料的具体细节？ | $\geq 80\%$ 的主张引用输入证据；直接证据比例 $\geq 60\%$（原型，未验证） |
| 3 | 人物差异化（Persona Differentiation） | 不同人物是否产生了真正不同的视角？ | 平均 Jaccard 距离 $\geq 0.3$（原型，未验证） |
| 4 | 刻板印象检查（Stereotype Check） | 判断是否基于行为画像而非人口统计学特征？ | 零人口统计因果推理模式（原型，未验证） |
| 5 | 结构完整性（Structural Integrity） | 报告是否包含所有必需章节？ | 100% 的必需章节存在（原型，未验证） |
| 6 | 校准诚实度（Calibration Honesty） | 研究发现是否正确标注为假设而非事实？ | 100% 的假设正确标注（原型，未验证） |
| 7 | 风险检测（Risk Detection） | 是否识别了关键风险？ | 识别 $\geq 1$ 个关键/高严重性问题（原型，未验证） |
| 8 | 细分冲突（Segment Conflict） | 人物细分之间是否存在有意义的分歧？ | $\geq 2$ 个有意义的分歧（原型，未验证） |

每个维度使用评分标准定义在 1–5 分制上评分。0–1 分表示失败（FAIL），2–3 分表示需要改进（NEEDS_IMPROVEMENT），4–5 分表示通过（PASS）。各维度带权重（刻板印象检查 1.5，校准诚实度 1.2，其余均为 1.0），整体结果是**同在 1–5 量纲上的加权均值**；仅在每个维度得分 $\geq 2$ 且加权均值 $\geq 3.0$ 时通过。不存在"总分 40 分"之类的汇总量纲；任何以该量纲归于本系统的分数都不是评估器会输出的东西。

Harness 包含测试夹具（高质量和低质量的游戏概念、好的和差的着陆页），作为校准锚点，以及定义每种任务类型所需报告章节的预期输出结构。

## 4. 实现

### 4.1 架构与入口（Architecture and Entry Points）

AudienceLens v0.3.0 是一个采用 MIT 协议的 Python 包（`audiencelens`），评审引擎位于 `src/runner/`，评估量表位于 `src/harness/`。它提供五个入口：命令行界面、Python API、MCP 服务、Web 应用（FastAPI 后端）与 Docker 镜像，并预置六家模型供应商配置。在引擎之上，另为 AI 编程助手（Claude Code 与 Trae AI）提供技能包前端；每个技能由一个 `SKILL.md` 文件定义其行为、资源文件、执行阶段和硬性规则，并通过斜杠命令调用（例如，`/synthetic-playtest concept_review path/to/concept.md`）。

本地优先的部署方式相比托管 SaaS 具有多项优势：(1) **隐私性**：输入材料不会离开用户的本地环境；(2) **可定制性**：用户可以修改人物定义、聚合规则和提示模板；(3) **可组合性**：技能可以链式调用（例如，对同一材料先运行 `audience-panel`，再运行 `red-team-audience`）；(4) **成本效率**：系统使用用户自己的模型凭证，无需额外的每次评审费用。

### 4.2 CCGS 仓库标准（CCGS Repository Standard）

AudienceLens 遵循 CCGS（Claude Code Group Standard）仓库结构，将多智能体系统组织为标准化的目录布局：

```
.claude/
├── agents/          # 50 个人物智能体定义（游戏池）
├── hooks/           # 生命周期钩子（session-start, validate-report 等）
├── launch.json
└── skills/          # 1 个技能定义（synthetic-playtest）及资源
.trae/
├── documents/
├── skills/          # 4 个技能镜像（synthetic-playtest、audience-panel、
│                    #   red-team-audience、persona-generate）
└── specs/
```

对此前描述的两处更正：不存在 `.claude/rules/` 目录——评估阈值位于 `src/harness/thresholds.yaml`，聚合参数位于 `src/config/aggregation-rules.yaml`；且 `.claude/skills/` 目前只有 1 个技能而非 4 个，完整的四个技能定义只存在于 `.trae/skills/` 下。因此两个助手之间的技能包覆盖是不对称的。

每个人物智能体定义为一个独立的 Markdown 文件（例如，`P01-indie-core-operator.md`），技能调度器在该人物被选中参与评审面板时加载并将其注入 LLM 上下文。注意这 50 个 agent Markdown 文件只镜像了游戏池；Python 引擎使用的权威人格定义是 `src/personas/` 下的 10 个 YAML 包。

### 4.3 伦理服务（Ethics Service）

伦理服务通过多层合规系统执行身份-行为解耦原则：

**刻板印象检测。** 系统扫描人物输出中"以人口统计属性作为行为判断因果解释"的禁止模式。检测分两层。第一层是正则初筛，覆盖四类模式——性别作为原因（gender-as-cause）、年龄作为刻板印象（age-as-stereotype）、地区作为假设（region-as-assumption）和 MBTI 作为决策逻辑（MBTI-as-decision-logic），中英文均含显式模式（例如，"作为一名女性玩家，我更喜欢……"）与隐式模式（例如，"这个年龄段的玩家通常会……"）。第二层是 LLM 复审，用于捕捉正则覆盖不到的、换了措辞的"人口统计特征 → 行为偏好"因果推断；该层**以配置了 API Key 为前提**，在不可用时系统会如实报告未被复审的输出数量，而不是把它们默认当作合规。

**证据依据。** 人物输出中的每个主张必须标注推理级别：`[direct]`（在输入材料中明确存在）、`[inferred: basis]`（从材料 + 人物先验知识合理推断，上限为总证据的 $\leq 40\%$），或 `[gap]`（无可用证据，必须标注为"未指定"）。填补空白——编造输入材料中不存在的信息——被严格禁止。

**合规评分。** 报告携带一个 0–100 区间的伦理合规分数。我们精确描述它，因为它比数值区间所暗示的要粗得多。该分数在 `src/runner/aggregator.py` 中计算为 $100 - 10 \times |V|$ 并截断到 $[0, 100]$，其中 $V$ 是全部人格输出中被检出的身份-行为解耦违规集合。因此它只能取 10 的倍数，且唯一输入就是解耦检查——它**不是**五维加权合成，证据依据、填补空白、注意事项具体性与 MBTI 使用规范是在别处（校验器与 Harness 量表）执行的，并未并入这个数字。分段为：$\geq 80$ 通过，$50$–$79$ 需修订，$< 50$ 驳回。五维加权合成（behavior_over_demographics 30%、evidence_grounding 25%、gap_filling_control 20%、caveat_specificity 15%、mbti_usage_correctness 10%）仍是设计目标，尚未实现。

**MBTI 禁用规则。** MBTI 类型仅允许作为风格修饰符（影响语气和沟通风格），明确禁止作为判断的因果解释。该规则通过提示工程和事后模式匹配双重执行。

### 4.4 HTML 报告生成（HTML Report Generation）

AudienceLens 生成三种输出格式：结构化 JSON（机器可读）、Markdown（人类可读）和 HTML（可视化报告）。HTML 报告采用赛博朋克 HUD 美学风格，遵循以下设计原则：

- **信息密度**：HUD 仪表板以紧凑的卡片布局显示三个关键指标（共识强度、风险等级、人物数量）
- **视觉编码**：严重性等级映射到颜色编码的徽章（绿色 → 琥珀色 → 红色 → 闪烁红色表示关键），证据级别映射到边框颜色（青色表示直接，琥珀色表示推断，红色表示空白），立场类别映射到 CSS 类（positive, neutral, negative）
- **人物头像**：使用 HSL 颜色哈希从人物 ID 确定性生成（色相 = hash(id) mod 360，饱和度 65%，亮度 55%）
- **评分条**：宽度 = 评分 × 20%，颜色类为 s1=红色 到 s5=绿色
- **排版**：Space Mono 用于代码/HUD 元素，Noto Sans SC 用于正文，Noto Serif SC 用于标题

HTML 报告由聚合层基于 `report-template.html` 使用 Jinja2 渲染（`src/runner/aggregator.py` 中的 `jinja2.Environment` + `FileSystemLoader`）；人格提示词与交叉质询提示词则来自 Handlebars 风格的 Markdown 模板，在渲染前先被转换为 Jinja2 语法。

### 4.5 关于案例研究的缺席

本文早先的版本包含一个工作示例（"赛博拾荒者游戏概念评审"），报告了 6 人面板、2 次立场变化、1 个临界点、Harness 评分 31/40（阈值 28）以及伦理合规评分 72/100。**我们已将其删除，并在此说明原因，而不是悄悄拿掉。**

那些数字无法由系统的实际实现复现。其中三个不只是未经核验，而是根本不可达：伦理合规分数只能取 10 的倍数（第 4.3 节），因此 72 不在其取值范围内，且所归因的原因——校准诚实度警告不足——根本不是该分数的输入；"6 个人物中有 2 个改变立场"依赖投票变更机制，而该机制产出的是空结果集（第 3.4 节）；"31/40（阈值 28）"不是评估器会输出的量纲，评估器输出的是 $[1,5]$ 区间的加权均值（第 3.7 节）。仓库中也没有归档该次运行的任何输入或输出产物。呈现这样的数字——即便加上"不构成实证验证"的免责声明——仍会让读者认为系统执行了交叉质询与临界点检测，而这正是本文要避免的误读。

因此我们不报告任何示例运行。AudienceLens 产出三种输出格式（结构化 JSON、Markdown 与 HTML；第 4.4 节），想看实际输出的读者可以从开源仓库自行生成。发布一个可归档、可复现的示例运行——连同输入材料、所用模型及其版本、以及完整输出目录一并随论文提交——在工程上并不困难，已列入下一版计划。在此之前，我们宁可让示例缺席，也不要一个"示意性"的示例。

### 4.6 实现状态：规范 vs. v0.3.0

由于本文同时包含已实现的机制与仅有规范的机制，我们用一张表统一给出每项的状态以及读者可以核对的文件。这是权威表述；本文其它任何行文若与此表冲突，以此表为准。

| 机制 | 章节 | v0.3.0 中的状态 | 核验位置 |
|---|---|---|---|
| 三级证据标注（`direct`/`inferred`/`gap`） | 4.3 | **已实现** | `src/runner/validator.py` |
| 40% 推断证据上限，以驳回方式强制 | 4.3 | **已实现** | `src/runner/validator.py` |
| 人口统计字段不进入模型提示词 | 6.1 | **已实现** | `src/runner/persona_agent.py` 的 `CORE_FIELDS` |
| 刻板印象检测（正则层） | 6.2 | **已实现** | `src/harness/stereotype_judge.py` |
| 刻板印象检测（LLM 复审层） | 6.2 | **已实现，以配置 API Key 为条件** | `src/harness/stereotype_judge.py` |
| 8 维 Harness 量表与阈值 | 3.7 | **已实现**；默认关闭、事后运行、不拦截 | `src/harness/thresholds.yaml`、`src/harness/evaluator.py` |
| 单轮共识（众数立场 vs. 阈值 0.7） | 3.5 | **已实现** | `src/runner/aggregator.py`、`src/config/aggregation-rules.yaml` |
| 伦理合规分数 | 4.3 | **已实现**，形式为 $100 - 10\lvert V\rvert$，单一输入 | `src/runner/aggregator.py` |
| 人格调用间的上下文隔离 | 3.1 | **已实现**（逐调用无状态提示词，线程池） | `src/runner/cli.py` |
| 人格之间的真实三轮反驳 | 3.3 | **未实现。** 运行时返回 `mode: "derived_summary"`、`is_live_debate: false`，并附 `limitation` 字符串说明未执行真实反驳。渲染出的交叉质询提示词从未被送入模型。 | `src/runner/cross_exam.py`、`src/runner/cli.py` |
| 投票变更机制与变更溯源 | 3.4 | **未实现。** `vote_changes` 恒为空；每个置信度 `delta` 被硬编码为 0。 | `src/runner/cross_exam.py` |
| 置信度阈值 $\theta_{\text{change}} = 0.15$ | 3.3 | **失效（inert）。** 存在于 YAML 与提示词文本中；无任何 Python 模块读取。 | `src/config/aggregation-rules.yaml` |
| 跨轮共识演化（收敛 / 发散 / 稳定 / 振荡） | 3.5 | **未实现。** 这些标识符在 `src/` 下均不存在。 | — |
| 临界点与级联点检测 | 3.6 | **未实现。** 两个标识符在 `src/` 下均不存在。 | — |
| 反驳提示词中的论据匿名化 | 3.1 | **未实现，且随包模板恰恰相反**（插值人格名）。因反驳不运行，该模板从未被使用。 | `src/templates/cross-exam-prompt.md` |
| Kruskal-Wallis 检验 / 评分标准差校验 | 5.1 | **未实现。** 差异化维度只计算 Jaccard 距离；项目没有统计检验依赖。 | `src/harness/evaluator.py` |
| 超过 30% 人格因证据不足被跳过时的醒目警告 | 6.5 | **未实现。** 存在降级横幅，但触发条件是模型调用失败数，而非跳过比例。 | `src/runner/cli.py` |
| 自动化回归测试 | — | **已实现**：截至 v0.3.0 标签，引擎 394 项、后端 294 项测试通过（另 1 项跳过）；该数字会随开发变动。 | `tests/`、`web/backend/tests/` |

## 5. 评估

### 5.0 计划评估设计

为验证交叉质询的有效性，我们计划以下受控实验：

**设计**：单轮评审与三轮交叉质询的 A/B 对比。

**协议**：
- **A 组（基线）**：每个人物独立审查目标材料并产生单次评审输出，人物之间无交互。
- **B 组（交叉质询）**：人物首先产生独立评审，然后进行三轮交叉质询（立场陈述、反驳、最终立场），并追踪投票变化。

**材料**：4 个标准测试夹具（2 个高质量、2 个低质量输入），涵盖游戏概念和产品着陆页。

**指标**：Harness 8 维度评分、人物差异化（Jaccard 距离）、可操作性比率、风险检测覆盖率和人类评估者偏好评分。

**假设**：B 组将表现出比 A 组更高的人物差异化、更好的风险检测和更具可操作性的建议，代价是增加的 token 使用量。

该评估尚未进行。它也无法针对已发布的 v0.3.0 进行：B 组需要真实的交叉质询实现，而该实现并不存在（第 4.6 节）。因此，实现该协议是这项实验的前置条件，而不只是执行实验中的一步。

### 5.1 Harness 8 维度评估

Harness 框架为每个维度提供量化阈值和定性评分标准。我们描述每个维度的评估方法：

**可操作性（Actionability）** 通过包含具体可执行的 `suggested_fix` 字段的关键问题比例来衡量。一个建议被认为是"可操作的"，如果它指定了改变什么、如何改变以及预期结果是什么。$\geq 70\%$ 的阈值反映了某些问题可能本质上模糊（例如，"整体感觉不对"）但仍值得报告的现实。

**输入依据（Input Grounding）** 使用两部分指标：(1) 引用输入证据的主张比例（$\geq 80\%$），(2) `[direct]` 证据占总证据的比例（$\geq 60\%$）。后者阈值确保人物主要回应输入材料中的实际内容，而非投射自己的假设。

**人物差异化（Persona Differentiation）** 对人物对的 `key_issues` 标题集采用 Jaccard 距离分析。对于每对 $(p_i, p_j)$：

$$d_J(p_i, p_j) = 1 - \frac{|K_i \cap K_j|}{|K_i \cup K_j|}$$

其中 $K_i$ 是人物 $p_i$ 的关键问题标题集。所有人物对的平均 Jaccard 距离必须 $\geq 0.3$。已实现的校验到此为止：**评估器不做任何统计假设检验**。此前对该维度的描述提到 Kruskal-Wallis $H$ 检验（$p < 0.05$）以及跨人物评分标准差平均 $\geq 0.5$；这两项都未实现，项目也没有能支撑它们的统计计算依赖。补上显著性检验是值得做的——仅凭平均 Jaccard 距离无法区分真正的视角多样性与噪声——但在它存在之前，我们不作任何分布性声称。

**刻板印象检查（Stereotype Check）** 使用模式匹配检测禁止的因果模式。系统扫描匹配"作为一名[人口统计群体]……因此/所以……"结构的正则表达式模式，并标记任何将人口统计属性用作因果解释的输出。阈值为零容忍：任何检测到的违规都会导致该维度失败。

**结构完整性（Structural Integrity）** 根据 JSON Schema 定义和必需章节列表验证输出。每种任务类型有一组定义的必需章节（例如，共识、重大分歧、优先修复、信息空白、下一步人工测试建议）。阈值为 100% 合规——任何缺失的必需章节都会导致失败。

**校准诚实度（Calibration Honesty）** 检查所有研究发现是否正确标注了其认知状态。假设必须标注为假设；置信度分数必须反映证据强度；注意事项必须具体而非笼统。阈值为 100% 正确标注。

**风险检测（Risk Detection）** 验证评审是否识别了至少一个关键或高严重性问题。这防止了合成评审产生一律正面反馈而忽略真正风险的常见失败模式。

**细分冲突（Segment Conflict）** 确保人物细分之间存在有意义的分歧。阈值为 $\geq 2$ 个有意义的分歧，其中"有意义"定义为在至少一个人物评为高或关键严重性的问题上的分歧。

### 5.2 人物差异化分析

为评估这 66 个人物是否产生真正不同的视角，系统对面板内人物对的 `key_issues` 标题集计算 Jaccard 距离（第 5.1 节）。50 个游戏人物分布在 8 个包中，具有不同的行为画像；目标是：来自不同包的人物在 `key_issues` 上的平均 Jaccard 距离 $\geq 0.5$（深度差异化），同一包内的人物 $\geq 0.3$（基本差异化）。

这些目标是设计意图。我们尚未在随包发布的人格集合上跑过该分析，因此不报告任何实测差异化数值。

在人物*设计*阶段也存在一条差异化准则：`persona-generate` 技能要求面板内所有人物对在其 `motivations` + `decision_rules` 集合上的 Jaccard 距离达到 $\geq 0.3$，未达标者应重新生成。这里必须说清它的强度：`persona-generate` 是由 LLM 智能体执行的技能 Markdown 文件，因此该准则是"要求智能体遵守的指令"，**不是程序化的门控**。它不应被读作对仓库中任何人格包的保证。

### 5.3 交叉质询有效性（拟议指标；v0.3.0 无法计算）

我们提出两个评估交叉质询有效性的指标。两者在当前实现下均无法计算，因为它们都需要 v0.3.0 不产出的多轮立场数据（第 4.6 节）。列出它们是为了让第 5.0 节的计划实验有明确定义。

**投票变化率（Vote Change Rate, $VCR$）**：第一轮与第三轮之间改变立场的人物比例：

$$VCR = \frac{|\{p_i : s_i^{(3)} \neq s_i^{(1)}\}|}{n}$$

健康的 $VCR$ 范围为 [0.1, 0.4]——过低表明交叉质询未产生有说服力的反驳论证，过高表明过度从众或不稳定。

**共识偏移（Consensus Shift, $\Delta C$）**：轮次间共识强度的变化：

$$\Delta C = \text{consensus\_strength}^{(3)} - \text{consensus\_strength}^{(1)}$$

正的 $\Delta C$ 表示收敛，负的表示发散，接近零表示稳定。$\Delta C$ 的值提供了关于评审材料是否天生具有争议性（发散）还是通过辩论显现出明确的优缺点（收敛）的洞察。

### 5.4 与单轮评审的比较

为量化交叉质询的附加价值，我们提出规范中的三轮协议与单轮基线（等效于跳过第 5 和第 7 阶段）之间的比较评估。该比较以协议先被实现为前提（第 4.6 节）。我们假设：

1. 交叉质询将产生更高的校准诚实度评分，因为被迫为其立场辩护的人物将揭示低置信度的判断。

2. 交叉质询将产生更高的细分冲突评分，因为反驳过程会暴露在独立评审中可能被掩盖的分歧。

3. 投票变化率将与输入材料的争议性相关——高争议性材料将比无争议材料产生更高的 $VCR$。

我们注意这些假设仍有待实证验证，我们将在第 7 节中讨论。

## 6. 伦理考量

### 6.1 身份-行为解耦

AudienceLens 的核心伦理创新是**身份-行为解耦原则（identity-behavior decoupling principle）**：人物判断必须能够因果追溯至行为特征和动机，而非人口统计学属性。该原则的动机源于用户体验（UX）研究中长期存在的论点——行为、目标和情境比单纯的人口统计学特征更具可操作性的人物属性 (Cooper 1999; Pruitt & Adlin 2006)，以及合成人物可能强化而非挑战现有刻板印象的风险。

在实践中，这意味着虽然人物*定义*中可以带有人口统计学属性（性别、年龄范围、地区），但这些属性只用于让被创作出来的人物池更具多样性。它们被明确禁止作为偏好或判断的因果解释。

这里的执行是**结构性的而非指令性的**，这正是我们最想强调的一点。当一个人格被准备送入模型调用时，`_minify_persona` 只序列化固定的 `CORE_FIELDS` 白名单——`id`、`name`、`archetype`、`identity_summary`、`behavior_profile`、`motivations`、`decision_rules`、`quit_triggers`、`continue_triggers`、`first_scan_focus`、`review_output`。性别、年龄、地区不在这个列表里，因此**模型从头到尾看不到它们**。一个人格无法基于自身记录写出"作为女性玩家，我偏好叙事游戏"，因为它手上根本没有那条记录；它表达的任何偏好都只能来自白名单里确实存在的 `behavior_profile`（例如高 `emotional_engagement` 加高 `novelty_seeking`）。

我们刻意区分这两者。"指示模型不要从人口统计推理"是一个模型可能遵守也可能不遵守的请求，它会在改写、换模型或长上下文下静默失效。把字段从载荷里拿掉改变的是"可能性"而不是"请求"，且不依赖调用背后是哪个模型。残余风险在于模型可能从人格的名字或 `identity_summary` 反推人口统计特征；刻板印象检测（第 6.2 节）是针对这一点的第二道防线，而它是检测器，不是保证。

### 6.2 刻板印象检测

刻板印象检测系统在两个层面运行：

**生成时**（指令，非代码门控）：`persona-generate` 技能定义了一个伦理检查阶段（第 5 阶段），扫描生成的人物是否包含禁止模式，其硬性规则写明 FAIL 状态不可跳过。由于该技能是由 LLM 智能体执行的 Markdown 规范，这是一条强制*指令*而非程序化屏障；我们据实这样描述它，不声称它"不可绕过"。

**输出时**（代码已实现）：每个人物的评审输出都会被正则层扫描；在配置了 API Key 时，还会经由 LLM 复审捕捉换了措辞的人口统计到行为的推断。检出的违规计入驱动伦理合规分数的身份-行为解耦违规计数（第 4.3 节），以及 Harness 的刻板印象检查维度（第 3.7 节）。需要说明当前执行力度的边界：合规分数按每条违规扣 10 分并随评审一并报告，Harness 维度是事后打分——两者都不会压制或重新生成有问题的输出。带差异化执行动作（拒绝、要求修订、警告、建议改进）的严重程度分级（CRITICAL、HIGH、MEDIUM、LOW）是设计目标，尚未实现。

### 6.3 MBTI 禁用规则

我们将 MBTI 标签视为**可选的虚构声音塑造标签**，而非心理测量学构念。遵循 Pittenger (2005) 的观点，我们承认 MBTI 缺乏稳健的心理测量学效度。在 AudienceLens 中，MBTI 标签可以出现在人物定义中，但仅作为沟通风格的叙事调味（例如，"以结构化、分析性语言进行沟通"），并被明确禁止作为行为或决策的因果解释。

### 6.4 以 AI 法案为参考的设计考量

AudienceLens 的设计参考了欧盟 AI 法案（EU AI Act）。以下条款已被纳入考量：

- **第50条（透明性）**：每份报告都包含醒目的"AI 生成的合成评审，非真实用户研究数据"横幅。此声明不可移除或弱化。
- **第13条（系统透明性）**：方法论、局限性和验证状态均公开记录。AudienceLens 明确将其验证状态标注为"待验证（pending validation）"而非"已验证"。
- **第14条（人类监督）**：每份报告都包含"下一步人类测试建议"，引导用户进行真实世界验证。
- **第15条（准确性）**：Harness 8维度框架提供了系统化的准确性评估。
- **第12条（记录保存）**：每个人物输出都包含人物 ID、版本和时间戳，以确保可追溯性。

我们不声称法律合规；这些考量反映的是设计意图，而非经认证的合规性。

### 6.5 透明性与校准诚实

AudienceLens 的一个核心设计原则是**校准诚实（calibration honesty）**：系统不得夸大其能力或输出的可靠性。这体现在以下几个方面：

1. **验证状态透明性**：系统明确将其输出标注为"合成评审，非真实用户研究"，并将其验证状态标注为"待定"，而非声称未经独立验证的准确率。

2. **置信度校准**：人物置信度评分必须反映证据强度。缺乏充分证据的人物必须报告低置信度，而非编造高置信度判断。

3. **缺口确认**：当输入材料不足以让人物形成判断时，证据预检会跳过该人物，跳过数量会一路带到报告中。另有一个降级横幅，在运行过程中有人格失败时加入，说明有多少位完成评审、以及结论仅基于这些输出。此处更正此前的一条声称：**并不存在**"当因证据不足被跳过的人格超过 30% 时加醒目警告"这条规则。该横幅的触发条件是失败数，而非跳过比例。按跳过比例告警是合理的补充，目前没有。

4. **注意事项的具体性**：每个人物输出必须包含至少一个具体的注意事项（例如，"本评审仅基于商店页面截图；未提供实机演示，因此手感评估属于推测"）。诸如"仅供参考"之类的笼统注意事项将被拒绝。

## 7. 局限性与未来工作

### 7.0 交叉质询协议尚未实现

本工作最要紧的局限是：它的招牌机制并不运行。第 3.3–3.6 节给出了三轮辩论协议、置信度门控的投票变更机制、共识演化分类与临界点检测；第 4.6 节记录了 v0.3.0 一项也没有实现。系统今天做的事情是：一轮相互隔离的人格评审，然后聚合；报告中的交叉质询区块从这一轮输出派生而来，并由运行时自己标注为"派生"。

这如实框定了本文的贡献边界。AudienceLens 已落地的价值在于*约束*合成评审输出——带驳回阈值的证据溯源、人口统计字段不进模型、公开声明且自带未验证标注的评估量表——而不在于多智能体审议。考虑基于本系统继续开发的读者，应把第 3.3–3.6 节当作"需要自己去实现的规范"，也不应把本工作当作关于多智能体辩论行为的证据来引用。

**未来工作**：把协议实现出来。具体而言：把已经渲染好的交叉质询提示词接上模型调用；从解析后的模型输出填充 `vote_changes`；让 $\theta_{\text{change}}$ 成为被真正读取的参数而非休眠的配置键；补上跨轮状态，使共识轨迹与临界点变得可计算。规范和提示词模板都已存在，缺的是执行，以及执行之后才谈得上的评估（第 5.0 节）。

### 7.1 缺乏真实世界对等研究

AudienceLens 最显著的局限性是缺乏将合成评审输出与真实用户研究数据进行比较的对照研究。诸如 SyntheticUsers 等商业平台声称与真实用户高度一致，但独立验证仍然有限。我们设计了具有四维加权评分系统的对等检查工具（主题重叠：0.30，评分相关性：0.25，立场对齐：0.25，深度对齐：0.20），但尚未收集计算这些分数所需的真实用户数据。

**未来工作**：我们计划与学术机构合作进行对照对等研究，将 AudienceLens 输出与针对相同材料的真实焦点小组结果进行比较。该研究将建立基线准确率并识别合成评审中的系统性偏差。

### 7.2 缺乏视频/语音模态

当前人物仅能评估基于文本和图像的材料。它们无法与实时产品交互、观看带音频的视频内容或体验沉浸式环境。这限制了系统在评估交互体验、游戏手感或视听冲击力方面的适用性。

**未来工作**：多模态人物评估，使人物能够处理视频、音频和交互内容。这需要与多模态大语言模型（LLM）能力集成，并可能需要与浏览器自动化工具集成以实现实时产品交互。

### 7.3 缺乏 SOC 2 认证

AudienceLens 未持有 SOC 2 认证，这可能限制其在需要数据处理合规性的企业场景中的采用。当前基于技能的架构在本地处理数据（在用户的 AI 编程助手内），这缓解了一些数据处理方面的顾虑，但未提供 SOC 2 认证所提供的正式保证。

**未来工作**：为 AudienceLens 的托管版本获取 SOC 2 Type II 认证，面向需要正式合规保证的企业客户。

### 7.4 经验性设定的阈值

系统中的若干阈值（共识阈值 0.7、Jaccard 距离阈值 0.3、证据覆盖率阈值，以及 8 项 Harness 阈值）是基于工程判断而非经验优化设定的。它们可能并非最优，我们也不声称它们是最优。置信度变化阈值 0.15 还要更进一步：它不只是未经验证，而且目前根本没被使用——没有任何代码路径读取它（第 4.6 节）。

**未来工作**：使用合成数据和真实用户数据进行的对照实验来校准这些阈值。我们计划采用网格搜索方法，独立变化每个阈值并测量其对 Harness 评估分数和对等指标的影响。

### 7.5 过度收敛风险

多智能体辩论系统容易受到过度收敛（over-convergence）的影响，即所有智能体无论输入质量如何都收敛到相同立场。当底层大语言模型对何为"好"或"坏"的设计有强烈先验时，这种风险尤为突出。此处有两点。在 v0.3.0 中，该风险并非来自辩论——因为根本没有辩论——而是来自共享的模型先验让名义上不同的人格产出相似的单轮评审；Jaccard 差异化校验本应暴露这一点，但我们尚未实测（第 5.2 节）。等第 3.3 节的协议被实现之后，辩论形态的风险才会出现，隔离设计意在缓解它——但该缓解未经检验，我们不声称它有效。

**未来工作**：研究交叉质询协议中的收敛动态，包括分析锚点（抵抗说服的人物）是否有效防止过度收敛，以及置信度阈值是否需要是自适应的而非固定的。

### 7.6 可扩展性

当前系统支持 3–8 个人物的评审小组。扩展到更大的小组会带来计算成本（每个人物需要单独的大语言模型调用）和协调挑战（交叉质询中需要处理的争议点更多）。预算配置文件允许用户设置 token 限制，但系统目前未针对成本-质量权衡进行优化。

**未来工作**：基于输入复杂度的自适应小组规模调整，以及研究更小但人物选择更具针对性的小组是否能达到与更大小组相当的质量。

## 8. 结论

我们提出了 AudienceLens——一个用于合成受众评审的开源原型，并在全文中明确区分了它的哪些机制真正执行、哪些只是等待实现的规范。

系统今天做的事情是约束合成评审输出，而非模拟审议。承担这一价值的是三项机制。证据溯源是强制且被执行的：每条主张都带 `direct` / `inferred` / `gap` 标注，校验器驳回推断占比超过 40% 的输出，因此人格无法用貌似合理的编造把评审灌满还顺利通过。身份-行为解耦是结构性而非指令性的：人口统计字段在载荷送达模型之前即被剔除，因此人口统计因果推理是"不可得"而非"被劝阻"——这一性质在更换模型后依然成立，而提示词指令不然。8 维 Harness 量表把阈值放在单一的、运行时读取的文件里，并随包标注为未经验证的原型值，因此读者可以拿第 3.7 节的每一个数字去比对同一个文件，并确认本系统没有为它们声称超出我们所写的东西。

同样重要的是系统没有做到什么。三轮交叉质询协议、投票变更机制、共识演化分类与临界点检测，在本文中是规范，不是已发布版本的行为。运行时自己就是这么说的——它把自己的交叉质询输出标注为"派生"而非"辩论"；第 4.6 节按机制逐条记录了状态与可核验的文件位置。我们删除了本文早先版本中的工作示例，因为它的数字无法复现，且其中两项依赖并不存在的机制。

其余局限是常见的那些，我们不淡化：没有针对真实用户研究的对等研究，不支持多模态评估，未在随包人格集合上实测差异化，若干阈值出自工程判断而非实验。结果是这篇论文比它早先的草稿更窄。我们认为，一个能经受读者对仓库执行一次 `grep` 的窄声称，比一个经受不住的宽声称更有价值。

AudienceLens 以 MIT 协议开源，提供 CLI、Python、MCP、Web 与 Docker 入口，内置 10 个人格包共 66 个行为驱动人物、14 种任务类型。我们邀请研究社区使用、评估和扩展该系统——包括去实现本文给出的协议规范——并欢迎真实世界验证研究的合作。

## 参考文献

1. Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. *Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology (UIST '23)*, 1–22. ✅ Reliable; peer-reviewed venue.

2. Argyle, L. P., Busby, E. C., Fulda, N., Gubler, J. R., Rytting, C., & Wingate, D. (2023). Out of one, many: Using language models to simulate human samples. *Political Analysis*, 31(3), 337–351. ✅ Reliable; peer-reviewed venue.

3. Horton, J. J. (2023). Homo silicus: A new kind of social scientist. *SSRN Electronic Journal*. https://doi.org/10.2139/ssrn.4434769 ✅ Retained; note corrected subtitle "A New Kind of Social Scientist."

4. Du, Y., Li, S., Torralba, A., Tenenbaum, J. B., & Mordatch, I. (2023). Improving factuality and reasoning in language models through multiagent debate. *Proceedings of the 40th International Conference on Machine Learning (ICML '23)*. ✅ Reliable; peer-reviewed venue.

5. Liang, T., Chen, Z., He, J., Wang, M., Zhou, Y., & Zhang, Z. (2023). Encouraging divergent thinking in large language models through multi-agent debate. *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing*. ⚠️ <!-- TODO: verify venue and exact title -->

6. SyntheticUsers. (2024). SyntheticUsers: AI-moderated synthetic user research platform [Commercial product]. https://syntheticusers.com ⚠️ Commercial citation; not peer-reviewed. Should not be cited as academic evidence.

7. ~~Mancini, T., et al. (2024). SCOPE: Demographics explain minimal behavioral variance in user research.~~ ❌ Specific 1.5% figure removed; replaced with domain consensus references (Cooper 1999; Pruitt & Adlin 2006). The SCOPE study's specific quantitative claims could not be independently verified.

8. European Parliament and Council. (2024). Regulation (EU) 2024/1689 laying down harmonised rules on artificial intelligence (Artificial Intelligence Act), Article 50. *Official Journal of the European Union*. ✅ Updated to correct article number (Article 50, not Article 52).

9. Pittenger, D. J. (2005). Cautionary comments regarding the Myers-Briggs Type Indicator. *Consulting Psychology Journal: Practice and Research*, 57(3), 210–221. ✅ Reliable; peer-reviewed venue.

10. Wang, Z., Mao, S., & Wang, W. (2024). Multi-agent consensus through iterative debate with convergence guarantees. *Proceedings of the AAAI Conference on Artificial Intelligence*. ⚠️ <!-- TODO: verify venue and exact title -->

11. Xu, Y., Wang, S., & Li, Z. (2024). Persona-driven requirements engineering with large language models. *IEEE Transactions on Software Engineering*, 50(4), 892–910. ⚠️ <!-- TODO: verify venue and exact title -->

12. Salehi, N., Kaur, J., & Bernstein, M. S. (2024). Persona-based accessibility evaluation using large language models. *Proceedings of the ACM on Human-Computer Interaction*, 8(CSCW1), 1–28. ⚠️ <!-- TODO: verify venue and exact title -->

13. Nielsen, J. (1994). *Usability Engineering*. Morgan Kaufmann.

14. Lazar, J., Feng, J. H., & Hochheiser, H. (2017). *Research Methods in Human-Computer Interaction*. Morgan Kaufmann.

15. Morgan, D. L. (1997). *Focus Groups as Qualitative Research* (2nd ed.). Sage Publications.

16. Mulder, S., & Yaar, Z. (2006). *The User Is Always Right: A Practical Guide to Creating and Using Personas for the Web*. New Riders.

17. Chan, C.-M., Chen, W., Su, Y., Yu, J., Xue, W., Zhang, S., Fu, J., & Liu, P. (2023). Chatmap: Scaling large language model-based multi-agent collaboration. *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing*.

18. Outset. (2024). AI-moderated interview platform [Commercial product]. https://outset.ai

19. Yabble. (2024). AI-powered survey and research platform [Commercial product]. https://yabble.com

**审计后新增参考文献：**

20. Cooper, A. (1999). *The Inmates Are Running the Asylum*. SAMS. ✅ Domain consensus reference for behavior-first persona design.

21. Pruitt, J., & Adlin, T. (2006). *The Persona Lifecycle: Keeping People in Mind Throughout Product Design*. Morgan Kaufmann. ✅ Domain consensus reference for behavior-first persona design.

22. RealSim (2026). Synthetic users, real differences. *arXiv preprint arXiv:2605.02624*. ⚠️ Pre-print; provides independent assessment of synthetic user alignment claims.

23. Can LLM agents really debate? (2025). *arXiv preprint arXiv:2511.07784*. ⚠️ Pre-print; relevant to cross-examination protocol validity.
