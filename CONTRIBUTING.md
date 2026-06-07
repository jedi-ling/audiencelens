# 贡献指南

欢迎为 AudienceLens 贡献代码、文档或新的人格定义！

## 开发环境

```bash
git clone https://github.com/your-repo/audiencelens.git
cd audiencelens
pip install -r requirements.txt
```

## 测试

AudienceLens 使用 TDD（测试驱动开发）。所有新功能必须先写测试。

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定模块的测试
python -m pytest tests/test_panel_selector.py -v

# 带覆盖率报告
python -m pytest tests/ --cov=src/runner --cov-report=term-missing
```

**规则：**
- 先写失败测试，验证失败，再写最小实现代码使测试通过
- 测试通过后可以重构代码，但必须保持测试绿色
- 不允许在没有测试的情况下添加功能代码

## 代码风格

- Python 标准风格（PEP 8）
- 函数/变量名使用 snake_case
- 类名使用 PascalCase
- **不添加注释**（README 中已明确要求）

## 提交 PR

1. Fork 本仓库
2. 从 `main` 分支创建新分支：`git checkout -b feature/your-feature-name`
3. 编写测试和功能代码
4. 确保所有测试通过：`python -m pytest tests/`
5. 提交并 push
6. 创建 Pull Request，描述改动内容和动机

## 新增 Persona

新增 persona 需要：

1. 在 `src/personas/game-core.yaml` 中添加定义
2. 确保符合 `persona-schema.json` 的校验规则
3. 在 `src/presets/panel-presets.yaml` 中为相关任务类型添加适配度
4. 运行测试确保 schema 校验通过
5. 提供至少一个评审示例

## 新增任务类型

新增任务类型需要：

1. 在 `src/presets/panel-presets.yaml` 中添加预设
2. 在 `src/schemas/output-schema.json` 中为 `task_type` 枚举添加新类型
3. 定义该任务类型的 `primary_stance` 枚举值
4. 定义该任务类型的 `task_specific` scores 维度
5. 准备至少一个示例素材

## 报告问题

请通过 GitHub Issues 报告：

- Bug（附上复现步骤）
- 缺失的功能
- 伦理问题或偏见
- 文档错误

---

感谢您的贡献！
