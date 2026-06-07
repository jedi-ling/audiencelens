# 贡献指南

感谢你对 AudienceLens 的关注！我们欢迎各种形式的贡献。

## 如何贡献

### 报告问题

- 使用 GitHub Issues 提交 Bug 报告或功能请求
- 请提供复现步骤、预期行为和实际行为
- 对于 Bug 报告，请附上相关的 Skill 名称和任务类型

### 提交代码

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'Add your feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request

### 贡献 Persona

我们特别欢迎新的 Persona 贡献！请遵循以下规范：

1. **行为驱动**：Persona 的核心必须由 `behavior_profile` 定义
2. **Schema 合规**：必须通过 `persona-schema.json` 校验
3. **伦理合规**：不得包含基于性别/年龄/地域的刻板印象
4. **区分度**：与现有 Persona 的 Jaccard 距离 ≥ 0.3
5. **完整性**：所有必填字段必须有有效值

### 贡献 Skill

1. 遵循现有 Skill 的 SKILL.md 格式
2. 包含完整的 Phase 定义和 Hard rules
3. 提供 Schema、模板和预设文件
4. 编写 Harness 评估器

### 贡献 Harness 评估器

1. 每个评估器必须包含核心问题、评分标准和示例
2. 评分标准使用 1-5 分制
3. 提供通过/失败阈值

## 开发规范

### 代码风格

- Python：遵循 PEP 8
- YAML：2 空格缩进
- Markdown：中文文档使用中文标点

### 提交信息

- 使用清晰、描述性的提交信息
- 格式：`type(scope): description`
- 类型：feat / fix / docs / refactor / test / chore

### 伦理审查

所有涉及 Persona 的贡献都会经过伦理审查：

1. 身份-行为解耦检查
2. 刻板印象检查
3. 包容性检查
4. 公平性检查

## 社区准则

- 尊重所有贡献者
- 建设性的讨论和反馈
- 不得发布歧视性或攻击性内容

## 许可证

通过向本仓库贡献代码，你同意你的贡献将在 MIT 许可证下发布。
