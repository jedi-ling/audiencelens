# AudienceLens 基线盲测协议

## 要回答的问题

AudienceLens 是否比“直接问一次通用模型”和“人工快速审阅”更接近后续真人研究结果？如果更好，增益是否足以覆盖额外成本与耗时？

## 实验单位

每个案例必须包含：

- 冻结版本的输入材料；
- AudienceLens 输出；
- 单次通用模型输出；
- 不超过约定时长的人工快评输出；
- 在三个候选输出完成后才收集的真人测试参考数据。

三个候选方法必须看到完全相同的材料。参考数据不能进入任何候选方法的上下文。

## JSON 契约

候选输出沿用 `parity-check` 支持的 `reviews` 或 `persona_notes` 结构，可附加：

```json
{
  "benchmark_meta": {
    "cost_usd": 0.42,
    "duration_minutes": 6.5
  },
  "reviews": []
}
```

参考数据使用：

```json
{
  "reviewers": [
    {
      "id": "participant-001",
      "stance": "negative",
      "key_issues": ["教程过长"],
      "scores": {"clarity": 2}
    }
  ]
}
```

## 运行

```bash
audiencelens benchmark-compare \
  --reference reference.json \
  --candidate audiencelens=audiencelens.json \
  --candidate single_prompt=single-prompt.json \
  --candidate expert_quick=expert-quick.json \
  --output benchmark-result.json
```

Windows 或未安装 console script 时可使用 `python src/cli.py benchmark-compare ...`。

## 解释规则

- 少于 10 名真人参与者时结果强制标记为低置信度。
- 同时报告主题重叠、评分相关性、立场对齐和深度对齐，不能只挑最好看的指标。
- 同时报告成本与耗时；质量增益不能脱离单位经济性解释。
- 候选文件与参考文件完全相同时拒绝运行，防止最直接的数据泄漏。
- 单个案例不能用于产品宣传。至少跨多个项目报告均值、方差和失败案例。

## 跨案例套件

推荐为每个真实项目运行脚手架命令，它会创建三个隔离候选、参考文件和套件清单，并拒绝覆盖已有案例：

```bash
audiencelens benchmark-init --dir ./pilot-data --case-id studio-001 --title "内部项目名"
```

也可以复制 `docs/templates/benchmark-suite-manifest.json` 手工建立。为每个项目填写参考数据和三个候选输出后运行：

```bash
audiencelens benchmark-suite \
  --manifest benchmark-suite.json \
  --output benchmark-suite-result.json
```

套件报告包含各方法的平均得分、标准差、胜率、平均成本、平均耗时和单位成本质量；同时给出 AudienceLens 相对指定基线的案例级配对增益及 bootstrap 95% 置信区间。少于 10 个案例时仍强制标记低置信度。

## 尚未自动化的控制项

- 候选展示顺序随机化和人工评分者盲法；
- 跨案例置信区间与显著性检验；
- 中文主题匹配目前仍受词法切分限制；
- 真人研究质量审计与参与者筛选。
