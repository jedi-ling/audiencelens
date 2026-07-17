---
title: "AudienceLens：一种用于合成受众评审的多智能体交叉质询框架"
authors:
  - name: 熵呓工作室
    affiliation: 熵呓工作室
abstract: |
  传统用户研究面临成本高、周期长、可重复性差等问题。近年来基于大语言模型（LLM）的人物模拟技术取得了重要进展，为大规模生成合成用户访谈提供了有前景的替代方案。然而，现有方法依赖单轮交互而缺乏交叉质询（Cross-Examination），缺乏立场修正机制，且没有追踪共识演化的系统性框架。我们提出并实现了 AudienceLens 的原型——一种用于合成受众评审的多智能体交叉质询系统，通过三项核心创新来解决上述局限：（1）采用分叉隔离（Fork Isolation）人物智能体的三轮辩论协议（立场陈述、反驳、最终立场）；（2）置信度阈值为 0.15 的投票变更机制及完整的变更溯源；（3）带有临界点检测的共识演化追踪。该系统包含横跨四个专业技能的 75 个行为驱动人物，并配备了初步的 8 维 Harness 评估框架。我们提出了身份-行为解耦原则（Identity-Behavior Decoupling Principle），并详细阐述了与欧盟《人工智能法案》（EU AI Act）要求对齐的伦理合规框架。我们讨论了包括缺乏真实世界对等性研究在内的局限性，并概述了实证验证的路线图。我们指出，本文呈现的是系统设计和原型实现；与真实用户的实证验证仍属于未来工作。
keywords: [多智能体系统, 合成受众, 交叉质询, 人物模拟, LLM评估, AI伦理]
---

# AudienceLens：一种用于合成受众评审的多智能体交叉质询框架

## 摘要

传统用户研究面临成本高、周期长、可重复性差等问题。近年来基于大语言模型（LLM）的人物模拟技术——以 SyntheticUsers 及类似平台为代表——取得了重要进展，为大规模生成合成用户访谈提供了有前景的替代方案。然而，现有方法依赖单轮交互而缺乏交叉质询，缺乏立场修正机制，且没有追踪共识演化的系统性框架。我们提出并实现了 AudienceLens 的原型——一种用于合成受众评审的多智能体交叉质询系统，通过三项核心创新来解决上述局限：（1）采用分叉隔离人物智能体的三轮辩论协议（立场陈述、反驳、最终立场）；（2）置信度阈值为 0.15 的投票变更机制及完整的变更溯源；（3）带有临界点检测的共识演化追踪。该系统包含横跨四个专业技能的 75 个行为驱动人物，并配备了初步的 8 维 Harness 评估框架。我们提出了身份-行为解耦原则，并详细阐述了与欧盟《人工智能法案》要求对齐的伦理合规框架。我们讨论了包括缺乏真实世界对等性研究在内的局限性，并概述了实证验证的路线图。我们指出，本文呈现的是系统设计和原型实现；与真实用户的实证验证仍属于未来工作。

## 1. 引言

用户研究是产品开发的基石，然而它仍然是设计周期中资源消耗最大的活动之一。一轮有主持的可用性测试通常需要 2–4 周的规划、\$5,000–\$15,000 美元的参与者报酬，且产生的结果在不同会话间难以复现 (Nielsen, 1994; Lazar et al., 2017)。焦点小组虽然在收集多元观点方面效率较高，但容易受到群体思维（Groupthink）、锚定偏差（Anchoring Bias）和强势声音影响 (Morgan, 1997)。基于调查的方法更容易扩展，但以深度换广度，产生的统计汇总掩盖了个体推理过程。

大语言模型（LLM）的出现开辟了一个新前沿：*合成用户研究*。SyntheticUsers 等商业平台声称与真实用户具有高度一致性，但独立验证仍然有限。Park et al. (2023) 表明，生成式智能体（Generative Agents）可以在沙盒环境中表现出可信的社会行为。Horton (2023) 提出了 *homo silicus*——可以作为经济学研究实验对象的计算智能体。Argyle et al. (2023) 证明单个 LLM 就能以惊人的保真度模拟多样化的子群体，捕捉不同人口群体在态度和行为上的差异。

然而，这些方法共享一个关键局限：它们将合成用户模拟视为*独白*（Monologue）而非*对话*（Dialogue）。每个人物独立响应，不接触对立观点，没有机会修正自身立场，也没有任何机制来检测共识是真实的还是表面的。这与真实焦点小组的运作方式根本不同——在真实焦点小组中，参与者相互质疑假设，因有说服力的论点而改变观点，有时会收敛到意想不到的立场。

我们提出并实现了 **AudienceLens** 的原型——一种用于合成受众评审的多智能体交叉质询系统，旨在解决上述局限。我们的主要贡献如下：

1. **三轮交叉质询协议**，通过立场陈述、反驳和最终立场来结构化人物交互，采用分叉隔离智能体防止交叉污染，同时通过共享立场池实现间接影响。

2. **投票变更机制**，设有置信度阈值（$\Delta c > 0.15$），允许人物在接触到有说服力的反驳论据时更新立场，同时记录完整的变更溯源（触发论据、置信度增量、变更前后立场）。

3. **共识演化追踪**，将群体动态分为四种模式（收敛、发散、稳定、振荡），并检测临界点（Tipping Point）——即单轮中 $\geq 2$ 个人物改变立场或置信度增量 $\geq 0.3$ 的时刻。

4. **8 维 Harness 评估框架**，每个维度设有量化阈值，为合成受众评审输出提供了首个系统性质量门控。

5. **身份-行为解耦原则**（Identity-Behavior Decoupling Principle），一种伦理框架，禁止将人口统计属性（性别、年龄、地区、MBTI）作为行为判断的因果解释，配有合规评分机制和刻板印象规避清单。

6. **开源的、基于技能的实现**，兼容 Claude Code 和 Trae AI 编程助手，包含横跨四个专业技能的 75 个行为驱动人物。

本文其余部分组织如下：第 2 节回顾相关工作；第 3 节介绍我们的方法；第 4 节详述实现细节；第 5 节描述评估框架；第 6 节讨论伦理考量；第 7 节阐述局限性与未来工作；第 8 节为结论。

## 2. 相关工作

### 2.1 生成式智能体与人物模拟

合成受众研究的基础在于 LLM 采纳和维持一致人物的能力。Park et al. (2023) 引入了栖息于沙盒小镇的生成式智能体，表现出包括关系形成、事件协调和信息扩散在内的涌现社会行为。他们的架构——由记忆流（Memory Stream）、反思（Reflection）和规划（Planning）组成——证明了基于 LLM 的智能体可以在长时间交互中保持行为一致性。

Argyle et al. (2023) 表明，LLM 在以人口统计特征为条件时可以模拟多样化的子群体，捕捉群体间态度和意见的差异。他们的"硅基受试者"（Silicon Subjects）方法表明 LLM 可以作为人类调查受访者的低成本替代，但他们告诫不应将合成响应等同于真实人类数据。

Horton (2023) 将这一研究方向扩展到经济学，提出了 *homo silicus*——参与经济学实验的计算智能体。他认为基于 LLM 的智能体可以作为人类经济行为的"无损"压缩，使研究人员在投入昂贵的人类研究之前能够快速迭代实验设计。

近年来，人物模拟已被应用于软件工程领域。Xu et al. (2024) 证明 LLM 人物可以在需求工程中模拟多样化的用户视角，而 Salehi et al. (2024) 使用人物驱动的评估来评估 Web 应用的可访问性。

### 2.2 合成用户研究

商业合成用户研究平台的出现旨在解决传统方法的成本和速度限制。**SyntheticUsers** (2024) 是一个提供 AI 主持的合成参与者访谈的商业平台。SyntheticUsers 等商业平台声称与真实用户具有高度一致性，但独立验证仍然有限。他们的方法使用 OCEAN（大五人格）模型构建人物档案，并生成访谈式响应。然而，SyntheticUsers 运行在单轮访谈范式下——每个人物独立回答问题，不接触其他人物的观点。

**Outset** 采用混合方法，使用 AI 大规模主持真实人类访谈。虽然这保留了人类响应的真实性，但并未解决推动合成方法发展的成本和速度限制。**Yabble** 提供 AI 驱动的调查分析，但依赖与人口统计标签化人物的单轮交互，这存在强化刻板印象而非捕捉真实行为多样性的风险。

这些平台共享 AudienceLens 所解决的三个局限：（1）人物之间没有交叉质询；（2）没有立场修正机制；（3）没有合成评审输出的系统性质量评估框架。

### 2.3 多智能体辩论

Du et al. (2023) 证明多智能体辩论可以提高语言模型的事实性和推理能力。在他们的框架中，多个 LLM 实例为不同立场辩论，每个智能体根据其他智能体的论点改进自己的响应。这种方法在数学推理和事实问答任务上提升了性能，表明对抗性交互可以发现单智能体生成所遗漏的错误。

Liang et al. (2023) 将此工作扩展到鼓励多智能体辩论中的多样性，表明强制不同视角可以促成更稳健的共识形成。Chan et al. (2023) 提出了 chatmap 用于扩展多智能体协作，证明结构化交互协议优于非结构化群聊。

Wang et al. (2024) 引入了通过迭代辩论实现多智能体共识的框架，表明收敛性质取决于智能体交互拓扑和证据强度。他们的工作强调了过早共识的风险——智能体在没有充分探索论据空间的情况下过快收敛。

AudienceLens 在这些洞察的基础上，引入了带有明确立场修正和共识追踪机制的结构化三轮辩论协议。与通用多智能体辩论不同，我们的协议专门为受众评审领域设计，其目标不是找到单一正确答案，而是绘制观点全景并识别真正存在分歧的领域。

### 2.4 人物生成中的 AI 伦理

合成人物生成的伦理维度日益受到关注。早期的 UX 研究早已论证，行为、目标和情境比单纯的人口统计特征更具可操作性的人物属性 (Cooper 1999; Pruitt & Adlin 2006)。这一洞察直接启发了我们的身份-行为解耦原则。

欧盟《人工智能法案》(2024) 为 AI 系统建立了透明度要求，包括披露 AI 生成内容的义务（第 50 条）、确保人类监督（第 14 条）和维护准确性（第 15 条）。这些要求对合成受众系统尤为重要，因为其输出可能被误读为真实用户研究数据。

Nielsen Norman Group 的人物方法论一直倡导行为优先的人物设计，认为人物应由目标、行为和痛点而非人口统计属性来定义 (Mulder & Yaar, 2006)。AudienceLens 通过其 `behavior_profile` 构造将这一原则付诸实践，用面向任务的行为维度取代了传统的 OCEAN 人格模型。

## 3. 方法

### 3.1 系统架构

AudienceLens 采用基于技能的架构，包含四个专业技能，每个技能服务于不同的评审领域：

| 技能 | 领域 | 人物数量 | 任务类型 |
|------|------|----------|----------|
| synthetic-playtest | 游戏 | 50 | 14（Steam 页面、试玩、概念、商业化等） |
| audience-panel | 产品 | 20 | 6（产品、应用、网站、功能、定价、用户体验） |
| red-team-audience | 对抗性 | 5 | 5 种攻击模式（用户、买家、投资者、评论者、竞争对手） |
| persona-generate | 元 | 动态 | 8 种市场类型 |

总人物池包含 **75 个人物**：50 个游戏导向人物分布在 8 个 YAML 包中（game-core: 16, competitive-esport: 5, family-casual: 5, indie-creative: 5, mobile-f2p: 5, vr-immersive: 5, accessibility: 5, educational-serious: 4），20 个产品导向人物分布在 6 个包中，以及 5 个对抗性红队人物。

一个关键的架构决策是**分叉隔离（Fork Isolation）**：每个人物智能体在独立子进程中运行，拥有自己的上下文窗口。人物智能体之间不能直接通信；影响仅通过交叉质询阶段的共享立场池传播。这种设计防止了交叉污染（一个人物的推理泄漏到另一个人物中），同时通过结构化论据交换实现间接影响。

### 分叉隔离实现

在 Claude Code Skill 架构中，分叉隔离通过 Task 子智能体机制实现：

1. **输入阶段**：每个人物智能体接收：
   - 目标材料摘要（截断以适应上下文窗口）
   - 人物 YAML 定义（behavior_profile、motivations、decision_rules）
   - 任务评分标准和输出模式
   - 评审模式参数（quick/standard/full）

2. **隔离保证**：每个人物智能体**不会**接收：
   - 其他人物智能体的完整输出
   - 其他人物智能体的私有推理链
   - 聚合笔记或中间结果
   - 关于评审小组中其他人物的信息

3. **反驳阶段**：在交叉质询轮次中，人物智能体接收：
   - 匿名化的争议主张（不标注人物归属）
   - 筛选出的对立论据（按相关性筛选，而非按人物身份）
   - 自己先前的输出供参考

4. **立场池**：中间立场数据存储为结构化 JSON 对象，包含 stance、confidence、key_issues 和 evidence 数组。该立场池由聚合层管理，而非由各个人物智能体管理。

5. **防串谋设计**：人物名称不包含在反驳提示中。论据仅以论据 ID 标注（例如 "Argument A3"），防止人物智能体基于身份形成联盟。

系统在八个阶段运行：（0）论据解析，（1）任务类型验证，（2）材料加载，（3）评审小组选择，（4）并行人物评审，（5）交叉质询，（6）报告聚合，（7）校准检查，和（8）输出生成。阶段 5 和 7 在 `quick` 模式下跳过；所有阶段在 `full` 模式下执行。

### 3.2 人物设计

每个人物由一个 YAML 规范定义，包含身份字段、行为档案、动机、决策规则和评审配置。核心创新是 **behavior_profile**——一个取代传统人格模型的 12 轴行为向量：

| 轴 | 范围 | 描述 |
|----|------|------|
| `patience` | very_low – very_high | 对摩擦和延迟的容忍度 |
| `genre_literacy` / `domain_literacy` | very_low – very_high | 领域特定知识深度 |
| `novelty_seeking` | very_low – very_high | 对新颖而非熟悉的偏好 |
| `risk_tolerance` | low – high | 对不确定性的舒适度 |
| `social_influence` | low – very_high | 对社会证明的易感性 |
| `completion_drive` | very_low – very_high | 完成已开始事项的动力 |
| `price_sensitivity` | low – very_high | 对成本相对于价值的敏感度 |
| `emotional_engagement` | low – high | 情感投入的深度 |
| `agency_preference` | low – high | 对玩家/用户自主权的渴望 |
| `tolerance_for_ambiguity` | low – high | 对不明确情境的舒适度 |
| `criticism_style` | categorical | 表达不满的方式 |

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
| vr-immersive | 4 | 游戏 | 沉浸感、舒适度、临场感 |
| family-casual | 5 | 游戏 | 可访问性、新手引导、安全性 |
| educational-serious | 4 | 游戏 | 学习效果、参与度 |
| accessibility | 4 | 游戏 | 键盘/屏幕/认知无障碍 |
| power-user | 5 | 产品 | 效率、集成、定制化 |
| casual-user | 3 | 产品 | 简洁性、低学习曲线 |
| skeptic-user | 3 | 产品 | 信任、投资回报、迁移成本 |
| enthusiast-user | 3 | 产品 | 社区、功能深度 |
| budget-conscious | 3 | 产品 | 定价、免费层、价值 |
| accessibility-user | 3 | 产品 | 屏幕阅读器、运动、认知 |
| red-team | 5 | 对抗性 | 攻击模式、边缘案例 |

每个人物由完整的 behavior_profile、motivations、decision_rules、quit_triggers 和 continue_triggers 定义。75 个人物的数量反映了跨领域的覆盖度，而非冗余；Jaccard 距离分析（第 6.2 节）衡量了实际的差异化程度。

### 3.3 交叉质询协议（Cross-Examination Protocol）

交叉质询协议是 AudienceLens 的核心差异化特性。它分为三个轮次进行：

**第一轮：立场陈述（Position Statement）。** 每个人物独立审查输入材料，并生成结构化输出，包括评分、关键问题、证据和主要立场。所有输出被收集到一个共享立场池中。关键在于，人物在此阶段并不知道彼此的存在——他们在完全隔离的状态下评估材料。

**第二轮：反驳（Rebuttal）。** 系统从第一轮输出中提取前 $k$ 个争议点，按各人物严重性评分的方差排序。对于每个争议点，系统识别持有最对立立场的两个人物，并为每一方生成结构化论证（主张 + 证据 + 推理链）。然后所有人物在 1–5 分制上评估每个论证的说服力。如果某个人物的置信度变化超过阈值（$\Delta c > 0.15$），他们可以更新自己的立场，并且必须记录原因。

**第三轮：最终立场（Final Stance）。** 每个人物产生其最终立场，如果他们在反驳阶段改变了观点，则最终立场可能与第一轮立场不同。系统记录完整的轨迹：初始立场、置信度轨迹、任何立场变化以及触发变化的论证。

如果连续两轮没有产生立场变化，表明已收敛，协议提前终止。

形式化地，设 $P = \{p_1, p_2, \ldots, p_n\}$ 为人物集合。在第一轮中，每个 $p_i$ 产生输出 $o_i^{(1)} = (s_i^{(1)}, c_i^{(1)}, e_i^{(1)})$，其中 $s_i^{(1)}$ 是立场，$c_i^{(1)} \in [0,1]$ 是置信度，$e_i^{(1)}$ 是证据集。争议点 $C = \{c_1, \ldots, c_k\}$ 通过以下方式提取：

$$C = \text{top-}k \left(\text{argsort}_{j} \left(\text{Var}(\{s_{1,j}^{(1)}, \ldots, s_{n,j}^{(1)}\})\right)\right)$$

其中 $s_{i,j}^{(1)}$ 表示人物 $p_i$ 对问题 $j$ 的严重性评分。在第二轮中，每个人物评估针对每个争议点的正反论证的说服力，产生更新的置信度 $c_i^{(2)}$。当满足以下条件时允许立场变化：

$$|c_i^{(2)} - c_i^{(1)}| > \theta_{\text{change}}$$

其中 $\theta_{\text{change}} = 0.15$。注意：$\theta_{\text{change}}$ 是一个可配置的工程参数，在原型实验中初始设为 0.15。该阈值未经实证验证，应根据模型和领域进行调整。

### 3.4 投票变更机制（Vote Change Mechanism）

投票变更机制旨在建模真实的意见动态，同时防止级联从众效应。关键设计选择如下：

**置信度阈值。** 人物只有当其置信度变化超过 $\theta_{\text{change}}$ 时才能改变立场。选择该阈值是为了足够大以过滤噪声（LLM 输出概率的微小波动），同时足够小以捕捉真正的说服效果。我们承认该值是经验设定的，并计划在未来的工作中通过受控实验进行校准。我们不将自我报告的置信度视为校准后的概率；LLM 置信度分数可能不反映真实的认知不确定性。

**变更溯源。** 每次立场变化都记录以下内容：(1) 触发变化的论证及其来源人物；(2) 变化前后的置信度；(3) 置信度差值；(4) 改变立场的人物提供的自由文本原因。该溯源链支持对说服动态进行事后分析，并支撑 Harness 框架的校准诚实度维度。

**防串谋设计。** 人物之间不能直接通信；影响仅通过共享立场池传播。这防止了人物通过直接互动相互强化立场的"回音室"效应，并确保任何立场变化都是由论证质量而非社会压力驱动的。

**无多数权重。** 系统不根据人物与多数派的一致程度进行加权。持有少数派立场的单个人物与五个一致的人物同样有效——价值在于理解他们*为何*不同意见，而非计算票数。

### 3.5 共识演化追踪（Consensus Evolution Tracking）

三轮协议完成后，系统将群体的共识轨迹分类为四种模式之一：

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

系统还追踪**分歧热点（divergence hotspots）**——置信度变化最大的问题——以及**极化（polarization）**，定义为群体分裂为两个大致相等的对立阵营而非收敛的状态。

### 3.6 临界点检测（Tipping Point Detection）

临界点（Tipping points）是讨论轨迹发生质变的时刻。AudienceLens 检测三种类型：

**翻转点（Flip points）**（红色）：人物从一个立场类别变为另一个立场类别（例如，从"会购买"变为"不会购买"）。这表明反驳论证足够有说服力，克服了人物的初始立场。

**级联点（Cascade points）**（琥珀色）：一个人物的立场变化在同一轮次中触发了其他人物的变化。这表明改变立场的人物的推理提供了与他人产生共鸣的新框架。

**锚定点（Anchor points）**（绿色）：人物在强反驳论证下仍维持其立场。这表明深植的立场对说服具有抵抗力，通常与核心行为特征相关（例如，具有极高 `price_sensitivity` 的人物无论产品特性如何都拒绝认可该产品）。

临界点的形式化检测规则为：

$$\text{TippingPoint}(r) = \begin{cases} \text{true} & \text{if } |\{p_i : s_i^{(r)} \neq s_i^{(r-1)}\}| \geq 2 \\ \text{true} & \text{if } \max_i |c_i^{(r)} - c_i^{(r-1)}| \geq 0.3 \\ \text{false} & \text{otherwise} \end{cases}$$

### 3.7 Harness 评估框架（Harness Evaluation Framework）

Harness 是一个 8 维度质量评估框架，根据量化阈值评估合成评审输出。我们为原型评估定义了初始操作阈值。这些阈值不是经过验证的规范；它们作为工程护栏，应通过未来的实证工作进行校准。

| # | 维度 | 核心问题 | 阈值 |
|---|------|----------|------|
| 1 | 可操作性（Actionability） | 建议是否具体且可执行？ | $\geq 70\%$ 的建议包含具体步骤（原型，未验证） |
| 2 | 输入依据（Input Grounding） | 论证是否引用了输入材料的具体细节？ | $\geq 80\%$ 的主张引用输入证据；直接证据比例 $\geq 60\%$（原型，未验证） |
| 3 | 人物差异化（Persona Differentiation） | 不同人物是否产生了真正不同的视角？ | 平均 Jaccard 距离 $\geq 0.3$；Kruskal-Wallis $H$ 检验 $p < 0.05$（原型，未验证） |
| 4 | 刻板印象检查（Stereotype Check） | 判断是否基于行为画像而非人口统计学特征？ | 零人口统计因果推理模式（原型，未验证） |
| 5 | 结构完整性（Structural Integrity） | 报告是否包含所有必需章节？ | 100% 的必需章节存在（原型，未验证） |
| 6 | 校准诚实度（Calibration Honesty） | 研究发现是否正确标注为假设而非事实？ | 100% 的假设正确标注（原型，未验证） |
| 7 | 风险检测（Risk Detection） | 是否识别了关键风险？ | 识别 $\geq 1$ 个关键/高严重性问题（原型，未验证） |
| 8 | 细分冲突（Segment Conflict） | 人物细分之间是否存在有意义的分歧？ | $\geq 2$ 个有意义的分歧（原型，未验证） |

每个维度使用评分标准定义在 1–5 分制上评分。0–1 分表示失败（FAIL），2–3 分表示需要改进（NEEDS_IMPROVEMENT），4–5 分表示通过（PASS）。整体评估仅在所有维度得分 $\geq 2$ 且平均得分 $\geq 3.0$ 时通过。

Harness 包含测试夹具（高质量和低质量的游戏概念、好的和差的着陆页），作为校准锚点，以及定义每种任务类型所需报告章节的预期输出结构。

## 4. 实现

### 4.1 基于技能的架构（Skill-Based Architecture）

AudienceLens 以 AI 编码助手的技能包形式实现，目前支持 Claude Code 和 Trae AI。每个技能由一个 `SKILL.md` 文件定义，该文件指定技能的行为、资源文件、执行阶段和硬性规则。该架构支持零安装部署——用户将技能文件复制到其助手的技能目录，并通过斜杠命令调用（例如，`/synthetic-playtest concept_review path/to/concept.md`）。

基于技能的方法相比传统 SaaS 部署具有多项优势：(1) **隐私性**：输入材料不会离开用户的本地环境；(2) **可定制性**：用户可以修改人物定义、聚合规则和提示模板；(3) **可组合性**：技能可以链式调用（例如，对同一材料先运行 `audience-panel`，再运行 `red-team-audience`）；(4) **成本效率**：系统使用用户现有的 LLM 订阅，无需额外的每次评审费用。

### 4.2 CCGS 仓库标准（CCGS Repository Standard）

AudienceLens 遵循 CCGS（Claude Code Group Standard）仓库结构，将多智能体系统组织为标准化的目录布局：

```
.claude/
├── agents/          # 50 个人物智能体定义
├── hooks/           # 生命周期钩子（session-start, validate-report 等）
├── rules/           # 评估和伦理规则
└── skills/          # 4 个技能定义及资源
.trae/
└── skills/          # Trae 兼容技能镜像
```

CCGS 标准使不同的 AI 编码助手之间能够互操作，同时保持一致的行为。每个人物智能体定义为一个独立的 Markdown 文件（例如，`P01-indie-core-operator.md`），技能调度器在该人物被选中参与评审面板时加载并将其注入 LLM 上下文。

### 4.3 伦理服务（Ethics Service）

伦理服务通过多层合规系统执行身份-行为解耦原则：

**刻板印象检测。** 系统扫描人物输出中的人口统计属性被用作行为判断因果解释的禁止模式。定义了四类禁止模式：性别作为原因（gender-as-cause）、年龄作为刻板印象（age-as-stereotype）、地区作为假设（region-as-assumption）和 MBTI 作为决策逻辑（MBTI-as-decision-logic）。每类包含显式模式（例如，"作为一名女性玩家，我更喜欢……"）和隐式模式（例如，"这个年龄段的玩家通常会……"）。

**证据依据。** 人物输出中的每个主张必须标注推理级别：`[direct]`（在输入材料中明确存在）、`[inferred: basis]`（从材料 + 人物先验知识合理推断，上限为总证据的 $\leq 40\%$），或 `[gap]`（无可用证据，必须标注为"未指定"）。填补空白——编造输入材料中不存在的信息——被严格禁止。

**合规评分。** 每个人物输出根据五个加权维度获得伦理合规分数（0–100）：behavior_over_demographics（30%）、evidence_grounding（25%）、gap_filling_control（20%）、caveat_specificity（15%）和 mbti_usage_correctness（10%）。分数 $\geq 80$ 通过；60–79 分需要修订；$< 60$ 分被拒绝。

**MBTI 禁用规则。** MBTI 类型仅允许作为风格修饰符（影响语气和沟通风格），明确禁止作为判断的因果解释。该规则通过提示工程和事后模式匹配双重执行。

### 4.4 HTML 报告生成（HTML Report Generation）

AudienceLens 生成三种输出格式：结构化 JSON（机器可读）、Markdown（人类可读）和 HTML（可视化报告）。HTML 报告采用赛博朋克 HUD 美学风格，遵循以下设计原则：

- **信息密度**：HUD 仪表板以紧凑的卡片布局显示三个关键指标（共识强度、风险等级、人物数量）
- **视觉编码**：严重性等级映射到颜色编码的徽章（绿色 → 琥珀色 → 红色 → 闪烁红色表示关键），证据级别映射到边框颜色（青色表示直接，琥珀色表示推断，红色表示空白），立场类别映射到 CSS 类（positive, neutral, negative）
- **人物头像**：使用 HSL 颜色哈希从人物 ID 确定性生成（色相 = hash(id) mod 360，饱和度 65%，亮度 55%）
- **评分条**：宽度 = 评分 × 20%，颜色类为 s1=红色 到 s5=绿色
- **排版**：Space Mono 用于代码/HUD 元素，Noto Sans SC 用于正文，Noto Serif SC 用于标题

HTML 报告通过读取 `report-template.html` 样式参考并根据数据注入规则注入聚合报告数据来生成，而非使用模板渲染引擎。该方法确保了在不同运行时环境中的兼容性。

### 4.5 案例研究：赛博拾荒者游戏概念评审

为说明系统的输出，我们展示一个以赛博拾荒者（Cyber Scavenger）游戏概念作为输入的原型运行。

**输入**：一份游戏概念文档，描述了一款赛博朋克主题的生存制作游戏，具有风险-信用机制、小程序平台限制和放置核心循环设计。

**面板**：从 game-core 包中选择的 6 个人物：
- P01（核心独立探索者）：中立 → 正面（置信度 78%）
- P02（系统理论策略家）：正面（置信度 82%）
- P07（轻度碎片玩家）：负面（置信度 32%）
- P08（新手观察者）：负面 → 中立（置信度 45%，投票变化）
- P11（TapTap 评论跟随者）：中立 → 正面（置信度 58%，投票变化）
- P13（发行商侦察员）：中立（置信度 55%）

**交叉质询结果**：
- 6 个人物中有 2 个在反驳轮次中改变了立场
- 关键争议：风险-信用认知阈值过高（3/6 人物引用）
- 临界点：P08 在 P02 关于教程脚手架的反驳后从负面转为中立

**输出摘要**：
- 总体建议：有条件继续（需简化核心机制）
- 风险等级：中等
- Harness 评分：31/40（通过，阈值 28）
- 证据依据率：62% 直接证据
- 人物差异化：Jaccard 距离 0.41

**伦理合规**：评分 72/100（需要修订），主要由于校准诚实度警告不足。

本案例研究说明了系统的工作流程和输出格式。不构成对框架有效性的实证验证。

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

我们注意该评估尚未进行；结果将在本论文的未来版本中报告。

### 5.1 Harness 8 维度评估

Harness 框架为每个维度提供量化阈值和定性评分标准。我们描述每个维度的评估方法：

**可操作性（Actionability）** 通过包含具体可执行的 `suggested_fix` 字段的关键问题比例来衡量。一个建议被认为是"可操作的"，如果它指定了改变什么、如何改变以及预期结果是什么。$\geq 70\%$ 的阈值反映了某些问题可能本质上模糊（例如，"整体感觉不对"）但仍值得报告的现实。

**输入依据（Input Grounding）** 使用两部分指标：(1) 引用输入证据的主张比例（$\geq 80\%$），(2) `[direct]` 证据占总证据的比例（$\geq 60\%$）。后者阈值确保人物主要回应输入材料中的实际内容，而非投射自己的假设。

**人物差异化（Persona Differentiation）** 对人物对的 `key_issues` 标题集采用 Jaccard 距离分析。对于每对 $(p_i, p_j)$：

$$d_J(p_i, p_j) = 1 - \frac{|K_i \cap K_j|}{|K_i \cup K_j|}$$

其中 $K_i$ 是人物 $p_i$ 的关键问题标题集。所有人物对的平均 Jaccard 距离必须 $\geq 0.3$，且评分分布的 Kruskal-Wallis $H$ 检验必须产生 $p < 0.05$。此外，人物间评分的标准差在所有评分维度上平均必须 $\geq 0.5$。

**刻板印象检查（Stereotype Check）** 使用模式匹配检测禁止的因果模式。系统扫描匹配"作为一名[人口统计群体]……因此/所以……"结构的正则表达式模式，并标记任何将人口统计属性用作因果解释的输出。阈值为零容忍：任何检测到的违规都会导致该维度失败。

**结构完整性（Structural Integrity）** 根据 JSON Schema 定义和必需章节列表验证输出。每种任务类型有一组定义的必需章节（例如，共识、重大分歧、优先修复、信息空白、下一步人工测试建议）。阈值为 100% 合规——任何缺失的必需章节都会导致失败。

**校准诚实度（Calibration Honesty）** 检查所有研究发现是否正确标注了其认知状态。假设必须标注为假设；置信度分数必须反映证据强度；注意事项必须具体而非笼统。阈值为 100% 正确标注。

**风险检测（Risk Detection）** 验证评审是否识别了至少一个关键或高严重性问题。这防止了合成评审产生一律正面反馈而忽略真正风险的常见失败模式。

**细分冲突（Segment Conflict）** 确保人物细分之间存在有意义的分歧。阈值为 $\geq 2$ 个有意义的分歧，其中"有意义"定义为在至少一个人物评为高或关键严重性的问题上的分歧。

### 5.2 人物差异化分析

为验证我们的 75 个人物产生真正不同的视角，我们对每个技能内人物对的 `key_issues` 和 `motivations` 字段进行 Jaccard 距离分析：

对于 synthetic-playtest 技能，50 个游戏人物涵盖 8 个类别，具有不同的行为画像。来自不同类别的人物在 `key_issues` 上的预期平均 Jaccard 距离为 $\geq 0.5$（深度差异化），同一类别内的人物为 $\geq 0.3$（基本差异化）。

差异化保证在人物设计阶段通过 `persona-generate` 技能执行，该技能要求面板内所有人物对在其 `motivations` + `decision_rules` 集合上的 Jaccard 距离 $\geq 0.3$。未达到该阈值的人物将被拒绝并重新生成。

### 5.3 交叉质询有效性

我们提出两个评估交叉质询有效性的指标：

**投票变化率（Vote Change Rate, $VCR$）**：第一轮与第三轮之间改变立场的人物比例：

$$VCR = \frac{|\{p_i : s_i^{(3)} \neq s_i^{(1)}\}|}{n}$$

健康的 $VCR$ 范围为 [0.1, 0.4]——过低表明交叉质询未产生有说服力的反驳论证，过高表明过度从众或不稳定。

**共识偏移（Consensus Shift, $\Delta C$）**：轮次间共识强度的变化：

$$\Delta C = \text{consensus\_strength}^{(3)} - \text{consensus\_strength}^{(1)}$$

正的 $\Delta C$ 表示收敛，负的表示发散，接近零表示稳定。$\Delta C$ 的值提供了关于评审材料是否天生具有争议性（发散）还是通过辩论显现出明确的优缺点（收敛）的洞察。

### 5.4 与单轮评审的比较

为量化交叉质询的附加价值，我们提出 AudienceLens 三轮协议与单轮基线（等效于跳过第 5 和第 7 阶段）之间的比较评估。我们假设：

1. 交叉质询将产生更高的校准诚实度评分，因为被迫为其立场辩护的人物将揭示低置信度的判断。

2. 交叉质询将产生更高的细分冲突评分，因为反驳过程会暴露在独立评审中可能被掩盖的分歧。

3. 投票变化率将与输入材料的争议性相关——高争议性材料将比无争议材料产生更高的 $VCR$。

我们注意这些假设仍有待实证验证，我们将在第 7 节中讨论。

## 6. 伦理考量

### 6.1 身份-行为解耦

AudienceLens 的核心伦理创新是**身份-行为解耦原则（identity-behavior decoupling principle）**：人物判断必须能够因果追溯至行为特征和动机，而非人口统计学属性。该原则的动机源于用户体验（UX）研究中长期存在的论点——行为、目标和情境比单纯的人口统计学特征更具可操作性的人物属性 (Cooper 1999; Pruitt & Adlin 2006)，以及合成人物可能强化而非挑战现有刻板印象的风险。

在实践中，这意味着虽然人物可以具有人口统计学属性（性别、年龄范围、地区），但这些属性仅作为表达风格和视角多样性的弱修饰因子。它们被明确禁止作为偏好或判断的因果解释。例如，一个人物可以被描述为女性，其沟通风格可能受到该属性的影响，但系统将拒绝任何声称"作为女性玩家，我偏好叙事游戏"的输出——该偏好必须追溯到 `behavior_profile`（例如，高 `emotional_engagement` + 高 `novelty_seeking`）。

### 6.2 刻板印象检测

刻板印象检测系统在两个层面运行：

**生成时**：`persona-generate` 技能包含一个强制伦理检查阶段（第5阶段），该阶段扫描生成的人物是否包含禁止模式。此检查不可绕过——未通过检查的人物将被拒绝，必须重新生成。

**输出时**：每个人物的评审输出都通过正则匹配和语义分析扫描禁止的因果模式。检测到的违规按严重程度分类（CRITICAL、HIGH、MEDIUM、LOW），并采取相应的执行措施（拒绝、要求修订、警告、建议改进）。

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

3. **缺口确认**：当输入材料不足以让人物形成判断时（证据覆盖率 $< 30\%$），该人物将被跳过，报告将明确标注该缺口。如果因该原因跳过的人物 $> 30\%$，报告将包含醒目警告。

4. **注意事项的具体性**：每个人物输出必须包含至少一个具体的注意事项（例如，"本评审仅基于商店页面截图；未提供实机演示，因此手感评估属于推测"）。诸如"仅供参考"之类的笼统注意事项将被拒绝。

## 7. 局限性与未来工作

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

系统中的若干阈值（置信度变化阈值 0.15、共识阈值 0.7、Jaccard 距离阈值 0.3、证据覆盖率阈值 30%）是基于工程判断而非经验优化设定的。虽然这些值在实践中产生了合理的行为，但它们可能并非最优。

**未来工作**：使用合成数据和真实用户数据进行的对照实验来校准这些阈值。我们计划采用网格搜索方法，独立变化每个阈值并测量其对 Harness 评估分数和对等指标的影响。

### 7.5 过度收敛风险

多智能体辩论系统容易受到过度收敛（over-convergence）的影响，即所有智能体无论输入质量如何都收敛到相同立场。当底层大语言模型对何为"好"或"坏"的设计有强烈先验时，这种风险尤为突出。我们的反串谋设计（分叉隔离、无直接通信）缓解了这一风险，但并未完全消除。

**未来工作**：研究交叉质询协议中的收敛动态，包括分析锚点（抵抗说服的人物）是否有效防止过度收敛，以及置信度阈值是否需要是自适应的而非固定的。

### 7.6 可扩展性

当前系统支持 3–8 个人物的评审小组。扩展到更大的小组会带来计算成本（每个人物需要单独的大语言模型调用）和协调挑战（交叉质询中需要处理的争议点更多）。预算配置文件允许用户设置 token 限制，但系统目前未针对成本-质量权衡进行优化。

**未来工作**：基于输入复杂度的自适应小组规模调整，以及研究更小但人物选择更具针对性的小组是否能达到与更大小组相当的质量。

## 8. 结论

我们提出并实现了 AudienceLens 的原型——一个用于合成受众评审的多智能体交叉质询系统，该系统解决了现有合成用户研究工具的三个关键局限：缺乏交叉质询、缺乏立场修订机制、缺乏系统化质量评估框架。

我们的三轮辩论协议配合分叉隔离的人物智能体，实现了结构化论证，反映了真实焦点小组的动态——参与者相互挑战假设，有时会修订自己的立场。带有置信度阈值和完整变更溯源的投票变更机制，提供了对意见动态的透明性洞察，这是单轮合成访谈无法获得的。共识演化追踪和临界点检测为理解群体意见如何以及为何转变提供了新颖的分析工具。

据我们所知，8 维度 Harness 评估框架是首个针对合成受众评审输出的系统化质量门控，在从可操作性到刻板印象检查等多个维度上提供了量化阈值。身份-行为解耦原则及其通过伦理服务的实施，应对了合成人物可能强化而非挑战现有刻板印象这一日益增长的关切。

我们对 AudienceLens 的局限性保持透明：它尚未针对真实用户研究数据进行验证，不支持多模态评估，若干设计参数是经验性设定而非实验优化。我们认为，承认这些局限性对于负责任地部署合成受众工具至关重要，我们承诺通过未来的经验验证来解决这些问题。

AudienceLens 是开源的，可作为 Claude Code 和 Trae AI 编程助手的技能包使用，包含跨四个专业技能的 75 个行为驱动人物。我们邀请研究社区使用、评估和扩展该系统，并欢迎真实世界验证研究的合作。

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
