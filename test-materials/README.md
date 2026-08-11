# 测试材料说明

这个目录不是仓库正式内容，是给你手动测试评审功能用的样例材料。

| 文件 | 格式 | 建议搭配的任务类型 |
|---|---|---|
| `01_kickstarter_星轨迷航.pdf` | PDF | 众筹页评审（kickstarter_review） |
| `02_创业BP_云会计SaaS.pdf` | PDF | 创业项目评审（pitch_review） |
| `03_steam商店页_深渊回响.md` | Markdown | Steam 页评审（steam_page_review） |
| `04_定价页_云笔记订阅.md` | Markdown | 定价页评审（pricing_page_review） |
| `05_开发日志_第7期.md` | Markdown | 开发日志评审（devlog_review） |

## 关于文件格式的选择

系统目前支持的上传格式是：
- 文本类：`.txt` `.md` `.json` `.yaml` `.yml`（对话页走 `/api/uploads`）
- 文档类：额外支持 `.pdf` `.docx`（走 `/api/extract-materials`，PDF 用 pypdf 抽取文字）
- 图片类：`.png` `.jpg` `.jpeg` `.webp` `.gif`

**没有做 `.html` 文件**：系统不接受直接上传 `.html`。如果你想测试"网页文案"
类材料，用 Markdown 模拟内容即可（03/04 就是这么做的），系统评审的是文字内容
本身，不是网页排版。

## 内容是虚构的

所有产品名、公司名、数字（销量、MRR、评价）均为虚构，专为测试评审效果编写，
不对应任何真实项目。里面故意留了一些"真实材料常见的毛病"（比如 BP 里数字
不完全自洽、开发日志有个未解决的疑问句），方便你观察评审团会不会真的抓到这些点。

## PDF 是怎么生成的

用 `reportlab` 脚本生成，已在生成后验证过能被系统的 `pypdf` 正常抽取出中文文字
（不是空文件或乱码）。生成脚本用完即删，没有留在这个目录里。
