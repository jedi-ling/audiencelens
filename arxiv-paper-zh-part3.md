## 6. 伦理考量

### 6.1 身份-行为解耦

AudienceLens 的核心伦理创新是**身份-行为解耦原则（identity-behavior decoupling principle）**：角色判断必须能够因果追溯至行为特征和动机，而非人口统计学属性。该原则的动机源于用户体验（UX）研究中长期存在的论点——行为、目标和情境比单纯的人口统计学特征更具可操作性的角色属性 (Cooper 1999; Pruitt & Adlin 2006)，以及合成角色可能强化而非挑战现有刻板印象的风险。

在实践中，这意味着虽然角色可以具有人口统计学属性（性别、年龄范围、地区），但这些属性仅作为表达风格和视角多样性的弱修饰因子。它们被明确禁止作为偏好或判断的因果解释。例如，一个角色可以被描述为女性，其沟通风格可能受到该属性的影响，但系统将拒绝任何声称"作为女性玩家，我偏好叙事游戏"的输出——该偏好必须追溯到 `behavior_profile`（例如，高 `emotional_engagement` + 高 `novelty_seeking`）。

### 6.2 刻板印象检测

刻板印象检测系统在两个层面运行：

**生成时**：`persona-generate` 技能包含一个强制伦理检查阶段（第5阶段），该阶段扫描生成的角色是否包含禁止模式。此检查不可绕过——未通过检查的角色将被拒绝，必须重新生成。

**输出时**：每个角色的评审输出都通过正则匹配和语义分析扫描禁止的因果模式。检测到的违规按严重程度分类（CRITICAL、HIGH、MEDIUM、LOW），并采取相应的执行措施（拒绝、要求修订、警告、建议改进）。

### 6.3 MBTI 禁用规则

我们将 MBTI 标签视为**可选的虚构声音塑造标签**，而非心理测量学构念。遵循 Pittenger (2005) 的观点，我们承认 MBTI 缺乏稳健的心理测量学效度。在 AudienceLens 中，MBTI 标签可以出现在角色定义中，但仅作为沟通风格的叙事调味（例如，"以结构化、分析性语言进行沟通"），并被明确禁止作为行为或决策的因果解释。

### 6.4 以 AI 法案为参考的设计考量

AudienceLens 的设计参考了欧盟 AI 法案（EU AI Act）。以下条款已被纳入考量：

- **第50条（透明性）**：每份报告都包含醒目的"AI 生成的合成评审，非真实用户研究数据"横幅。此声明不可移除或弱化。
- **第13条（系统透明性）**：方法论、局限性和验证状态均公开记录。AudienceLens 明确将其验证状态标注为"待验证（pending validation）"而非"已验证"。
- **第14条（人类监督）**：每份报告都包含"下一步人类测试建议"，引导用户进行真实世界验证。
- **第15条（准确性）**：Harness 8维度框架提供了系统化的准确性评估。
- **第12条（记录保存）**：每个角色输出都包含角色 ID、版本和时间戳，以确保可追溯性。

我们不声称法律合规；这些考量反映的是设计意图，而非经认证的合规性。

### 6.5 透明性与校准诚实

AudienceLens 的一个核心设计原则是**校准诚实（calibration honesty）**：系统不得夸大其能力或输出的可靠性。这体现在以下几个方面：

1. **验证状态透明性**：系统明确将其输出标注为"合成评审，非真实用户研究"，并将其验证状态标注为"待定"，而非声称未经独立验证的准确率。

2. **置信度校准**：角色置信度评分必须反映证据强度。缺乏充分证据的角色必须报告低置信度，而非编造高置信度判断。

3. **缺口确认**：当输入材料不足以让角色形成判断时（证据覆盖率 $< 30\%$），该角色将被跳过，报告将明确标注该缺口。如果因该原因跳过的角色 $> 30\%$，报告将包含醒目警告。

4. **注意事项的具体性**：每个角色输出必须包含至少一个具体的注意事项（例如，"本评审仅基于商店页面截图；未提供实机演示，因此手感评估属于推测"）。诸如"仅供参考"之类的笼统注意事项将被拒绝。

## 7. 局限性与未来工作

### 7.1 缺乏真实世界对等研究

AudienceLens 最显著的局限性是缺乏将合成评审输出与真实用户研究数据进行比较的对照研究。诸如 SyntheticUsers 等商业平台声称与真实用户高度一致，但独立验证仍然有限。我们设计了具有四维加权评分系统的对等检查工具（主题重叠：0.30，评分相关性：0.25，立场对齐：0.25，深度对齐：0.20），但尚未收集计算这些分数所需的真实用户数据。

**未来工作**：我们计划与学术机构合作进行对照对等研究，将 AudienceLens 输出与针对相同材料的真实焦点小组结果进行比较。该研究将建立基线准确率并识别合成评审中的系统性偏差。

### 7.2 缺乏视频/语音模态

当前角色仅能评估基于文本和图像的材料。它们无法与实时产品交互、观看带音频的视频内容或体验沉浸式环境。这限制了系统在评估交互体验、游戏手感或视听冲击力方面的适用性。

**未来工作**：多模态角色评估，使角色能够处理视频、音频和交互内容。这需要与多模态大语言模型（LLM）能力集成，并可能需要与浏览器自动化工具集成以实现实时产品交互。

### 7.3 缺乏 SOC 2 认证

AudienceLens 未持有 SOC 2 认证，这可能限制其在需要数据处理合规性的企业场景中的采用。当前基于技能的架构在本地处理数据（在用户的 AI 编程助手内），这缓解了一些数据处理方面的顾虑，但未提供 SOC 2 认证所提供的正式保证。

**未来工作**：为 AudienceLens 的托管版本获取 SOC 2 Type II 认证，面向需要正式合规保证的企业客户。

### 7.4 经验性设定的阈值

系统中的若干阈值（置信度变化阈值 0.15、共识阈值 0.7、Jaccard 距离阈值 0.3、证据覆盖率阈值 30%）是基于工程判断而非经验优化设定的。虽然这些值在实践中产生了合理的行为，但它们可能并非最优。

**未来工作**：使用合成数据和真实用户数据进行的对照实验来校准这些阈值。我们计划采用网格搜索方法，独立变化每个阈值并测量其对 Harness 评估分数和对等指标的影响。

### 7.5 过度收敛风险

多智能体辩论系统容易受到过度收敛（over-convergence）的影响，即所有智能体无论输入质量如何都收敛到相同立场。当底层大语言模型对何为"好"或"坏"的设计有强烈先验时，这种风险尤为突出。我们的反串谋设计（分叉隔离、无直接通信）缓解了这一风险，但并未完全消除。

**未来工作**：研究交叉质询协议中的收敛动态，包括分析锚点（抵抗说服的角色）是否有效防止过度收敛，以及置信度阈值是否需要是自适应的而非固定的。

### 7.6 可扩展性

当前系统支持 3–8 个角色的评审小组。扩展到更大的小组会带来计算成本（每个角色需要单独的大语言模型调用）和协调挑战（交叉质询中需要处理的争议点更多）。预算配置文件允许用户设置 token 限制，但系统目前未针对成本-质量权衡进行优化。

**未来工作**：基于输入复杂度的自适应小组规模调整，以及研究更小但角色选择更具针对性的小组是否能达到与更大小组相当的质量。

## 8. 结论

我们提出并实现了 AudienceLens 的原型——一个用于合成受众评审的多智能体交叉质询系统，该系统解决了现有合成用户研究工具的三个关键局限：缺乏交叉质询、缺乏立场修订机制、缺乏系统化质量评估框架。

我们的三轮辩论协议配合分叉隔离的角色智能体，实现了结构化论证，反映了真实焦点小组的动态——参与者相互挑战假设，有时会修订自己的立场。带有置信度阈值和完整变更溯源的投票变更机制，提供了对意见动态的透明性洞察，这是单轮合成访谈无法获得的。共识演化追踪和转折点检测为理解群体意见如何以及为何转变提供了新颖的分析工具。

据我们所知，8 维度 Harness 评估框架是首个针对合成受众评审输出的系统化质量门控，在从可操作性到刻板印象检查等多个维度上提供了量化阈值。身份-行为解耦原则及其通过伦理服务的实施，应对了合成角色可能强化而非挑战现有刻板印象这一日益增长的关切。

我们对 AudienceLens 的局限性保持透明：它尚未针对真实用户研究数据进行验证，不支持多模态评估，若干设计参数是经验性设定而非实验优化。我们认为，承认这些局限性对于负责任地部署合成受众工具至关重要，我们承诺通过未来的经验验证来解决这些问题。

AudienceLens 是开源的，可作为 Claude Code 和 Trae AI 编程助手的技能包使用，包含跨四个专业技能的 75 个行为驱动角色。我们邀请研究社区使用、评估和扩展该系统，并欢迎真实世界验证研究的合作。

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
