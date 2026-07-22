# scripts/archive/ — 归档的一次性会话脚本

> **归档日期**: 2026-07-19
> **状态**: 已归档，不属于标准流水线

## 重要声明

本目录下的所有文件均为**历史会话中的一次性实用脚本**，用于特定的临时任务（如批量文件写入、格式修复、模板同步等）。它们：

- **不是** AudienceLens 标准评审流水线的一部分
- **不应**被 `src/`、`web/` 或任何运行时代码导入或依赖
- **不应**在新会话中静默复用——如需类似功能，请重新评估并编写新脚本

## 文件清单

| 文件 | 原用途 |
|------|--------|
| `_fix_contrast.py` | 修复对比度问题的临时脚本 |
| `_sync_css.py` | CSS 同步临时脚本 |
| `_write_parity.py` | 生成本地化奇偶校验报告的临时脚本 |
| `copy-files.ps1` | 批量复制文件的 PowerShell 脚本 |
| `fix_contrast.py` | 对比度修复（另一版本） |
| `modify-paper.ps1` | 修改论文文档的临时脚本 |
| `patch_template.py` | 模板补丁脚本 |
| `sync_and_create.py` | 同步并创建文件的临时脚本 |
| `validate_syntax.py` | 语法验证临时脚本 |
| `write-personas.ps1` | 批量写入人格配置的临时脚本 |
| `write-schemas.ps1` | 批量写入 Schema 的临时脚本 |
| `write-support-1.ps1` | 支持文件写入临时脚本 |
| `write-templates.ps1` | 批量写入模板的临时脚本 |
| `write_report.py` | 报告生成临时脚本 |

## 处理建议

如需清理，可直接删除本目录；如需保留，请确保：
1. 本 README 存在且日期更新
2. `git grep` 确认无运行时导入
3. 在 `docs/optimization-roadmap.md` 中记录保留原因
