#!/usr/bin/env python3
"""打一个可直接上传服务器的部署包（前端 + 后台面板 + 后端 + 引擎）。

用法：
    python scripts/make_deploy_package.py            # 打包（前端需已构建）
    python scripts/make_deploy_package.py --build    # 先跑 npm build 再打包

产物：dist-package/audiencelens-<版本>-<日期>.tar.gz

── 这个包的定位 ──

服务器上**不需要装 Node**：前端与后台面板的静态产物已经构建好放进包里。
服务器只需要 Python 3.11+ 与 nginx，按包内 DEPLOY-BAREMETAL.md 走即可。
（3.11 不是"建议"而是硬要求：pyproject.toml 写着 `requires-python = ">=3.11"`，
3.10 上 `pip install -e .` 会被直接拒掉。这行以前写 3.10+，照着装的人会在
第一步就卡住，而报错信息跟部署手册对不上。）

── 绝不进包的东西（这是本脚本最重要的部分）──

排除不是"顺手清理体积"，是安全边界。逐条列出理由，避免后来者放宽：

  · web/.env、web/frontend/.env  —— 真实密钥（SMTP 密码、AL_ADMIN_TOKEN、
    QQ APP KEY）。这些文件在开发机上存在，一旦被打进包，密钥就会随包
    扩散到服务器、备份、聊天记录里。包里只给 .env.production.example 模板。
  · web/backend/data/            —— 运行时数据库与上传的用户文件。带上它
    等于把开发机上的测试账号、评审内容一起发到生产。
  · node_modules / .venv / __pycache__ / .git —— 体积且与目标机器架构无关。
  · *.db / *.sqlite3            —— 同 data/，任何位置的库文件都不带。

打包完成后脚本会**扫描产物**做一次密钥自查（见 _audit_archive），
发现可疑内容直接删包并报错——宁可打不出包，也不要发出一个带密钥的包。
"""

import argparse
import io
import os
import re
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

# Windows 默认控制台是 GBK，脚本里的 ✓/✗ 与中文会在 print 时抛
# UnicodeEncodeError——而那时包**已经打好了**，报错发生在最后一行提示上，
# 看起来却像"打包失败"。统一把输出流切成 UTF-8，别让编码问题伪装成功能故障。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 非 TTY / 老 Python：维持默认，最坏只是提示行乱码

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "dist-package"

# 要打进包的路径（相对仓库根）。顺序即包内结构。
INCLUDE = [
    # ---- 引擎：后端 import runner，人格/预设/模板/schema 都是运行时必需 ----
    "src/runner",
    "src/personas",
    "src/presets",
    "src/templates",
    "src/schemas",
    "src/config",
    "src/__init__.py",
    "src/cli.py",
    "src/mcp_server.py",
    "src/mcp_tools.py",
    # 质量评估引擎。包内 src/cli.py 的 harness-evaluate / ablation / stereotype-eval
    # 三个子命令都 import 它，缺了就是 `python -m src.cli --help` 直接 ImportError。
    "src/harness",
    # ---- 评委规则集（ethics/evaluation 服务启动时读取，缺失会降级为内置规则）----
    "audiencelens-v0.2-harness",
    # ---- 后端 ----
    "web/backend/app",
    # 注意：**不带 web/backend/libs**。那是开发机上的本地依赖副本
    # （.gitignore 忽略、无任何代码引用），里面是 .cp311-win_amd64.pyd 这类
    # **Windows 架构的原生扩展**。发到 Linux 服务器不只是白占 27MB，
    # 更可能被 Python 优先搜到、覆盖掉 pip 正确装出来的 Linux 版本，
    # 表现为一堆莫名其妙的 ImportError。依赖一律由服务器 pip install
    # requirements.txt 自己装（见 DEPLOY-BAREMETAL.md 第 1 节）。
    "web/backend/scripts",
    "web/backend/run.py",
    "web/backend/requirements.txt",
    "web/backend/pytest.ini",
    # ---- 前端 / 后台面板：只带构建产物与 nginx 配置，不带源码与 node_modules ----
    "web/frontend/dist",
    "web/frontend/nginx.conf",
    "web/admin/dist",
    # admin 镜像的 nginx 配置。少了它 `docker compose up --build` 起 admin
    # 容器时 COPY 那一步直接失败——而包里明明带着 docker-compose.yml。
    "web/admin/nginx.conf",
    # ---- Dockerfile 三件套 ----
    # 包里带着两个 compose 文件，两个都是 `build:` 而不是 `image:`，
    # 所以没有 Dockerfile 时 `docker compose up --build` 在第一步就报
    # "failed to read dockerfile"。DEPLOY.md 第 2 步写的正是这条命令。
    "web/backend/Dockerfile",
    "web/frontend/Dockerfile",
    "web/admin/Dockerfile",
    # ---- 运维脚本与反代配置 ----
    # 包里的 docker-compose.prod.yml 把 deploy/Caddyfile 挂进 caddy 容器，
    # DEPLOY.md 第 4 步让运维跑 deploy/install-backup-cron.sh，
    # DEPLOY-BAREMETAL.md 的恢复演练一节让他跑 deploy/restore.sh。
    # 三份文档都进了包，被它们引用的脚本却没有——照着做必然卡住。
    "web/deploy",
    # ---- 部署文档与配置模板 ----
    "web/DEPLOY.md",
    "web/DEPLOY-BAREMETAL.md",
    "web/docker-compose.yml",
    "web/docker-compose.prod.yml",
    "requirements.txt",
    # 包内 README 写着 `pip install -e .`，而它读的是 pyproject.toml
    # （console_scripts 也在里面）。缺了这个文件那行命令直接报错。
    "pyproject.toml",
    "pytest.ini",
    "README.md",
    "LICENSE",
    "docs/MAINTENANCE.md",
    # ---- 测试套件 ----
    # DEPLOY-BAREMETAL.md 让运维在服务器上跑这两套测试确认部署没问题。
    # 不带测试的话那一步是空指令。体积很小，且不含任何运行时数据。
    "tests",
    "web/backend/tests",
]

# 这些文件最终在 Linux 上执行/被 docker 解析。开发机 core.autocrlf=true 会让
# 工作区里的它们带 CRLF（`web/deploy/backup.sh` 现在就有 198 行），而
# `#!/usr/bin/env bash\r` 在 Linux 上报的是 "bad interpreter: No such file or
# directory"——看起来像 bash 没装。打包时统一转成 LF，让一个 Windows 检出
# 也打不出跑不起来的包。（仓库侧另有 .gitattributes 钉住签出换行。）
LF_SUFFIXES = {".sh"}
LF_NAMES = {"Dockerfile", "Caddyfile"}

# 目录树里一律跳过的名字
EXCLUDE_NAMES = {
    "node_modules", ".venv", "venv", "__pycache__", ".git", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "data", "outbox", "backups",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log"}
# .env 一律不带（模板 .env.production.example 是单独显式加进去的）
EXCLUDE_EXACT = {".env", ".env.local", ".env.production"}


def _should_skip(path: Path) -> bool:
    if path.name in EXCLUDE_NAMES or path.name in EXCLUDE_EXACT:
        return True
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    # .env.xxx 一概不要，除非是 example/sample 模板
    if path.name.startswith(".env") and not path.name.endswith(("example", "sample")):
        return True
    return False


def _iter_files(root: Path):
    if root.is_file():
        if not _should_skip(root):
            yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        # 就地裁剪，避免走进 node_modules 这类巨型目录
        dirnames[:] = [n for n in dirnames if not _should_skip(d / n)]
        for name in filenames:
            f = d / name
            if not _should_skip(f):
                yield f


def _add(tf: tarfile.TarFile, src: Path, arcname: str) -> None:
    """加一个文件进包；shell 脚本 / Dockerfile / Caddyfile 顺手把 CRLF 抹平。

    顺带把 .sh 的权限位设成 0o755：tar 里存的是源文件的权限，而 Windows
    检出出来的文件没有可执行位，解包后 `./deploy/install-backup-cron.sh`
    会是 Permission denied。手册里那几条命令就该开箱即用。
    """
    needs_lf = src.suffix.lower() in LF_SUFFIXES or src.name in LF_NAMES
    if not needs_lf:
        tf.add(src, arcname=arcname)
        return

    data = src.read_bytes().replace(b"\r\n", b"\n")
    info = tf.gettarinfo(str(src), arcname=arcname)
    info.size = len(data)
    if src.suffix.lower() == ".sh":
        info.mode = 0o755
    tf.addfile(info, io.BytesIO(data))


def _version() -> str:
    """版本号以 `pyproject.toml` 的 `version` 为准；取不到才回落 git。

    为什么不再优先用 git tag：仓库里同时存在四个说法——git tag `v1.0.0`、
    pyproject `0.3.0`、README 路线图「v0.3 当前 / v1.0 计划中」、
    web/DEPLOY.md 标题。包名跟着 tag 走的结果是打出
    `audiencelens-v1.0.0-…tar.gz`，而包里的 README 明写 v1.0 还没做。
    唯一能被程序读到、且和发布物一致的声明是 pyproject 里的那个，
    所以以它为单一事实源。（git tag 与它不一致是另一件事，需要重新打标签。）
    """
    pyproject = REPO / "pyproject.toml"
    if pyproject.exists():
        m = re.search(
            r'^version\s*=\s*["\']([^"\']+)["\']',
            pyproject.read_text(encoding="utf-8"),
            re.M,
        )
        if m:
            return "v" + m.group(1)

    for cmd in (["git", "describe", "--tags", "--abbrev=0"], ["git", "rev-parse", "--short", "HEAD"]):
        try:
            out = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=10)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return "dev"


# 打包后的自查：这些形状一旦出现在包里，几乎必然是真密钥而不是示例。
# 宁可误报（人工确认一下），也不要漏报（把密钥发出去）。
SECRET_PATTERNS = [
    (re.compile(rb"sk-ant-[A-Za-z0-9_\-]{20,}"), "Anthropic API Key"),
    (re.compile(rb"sk-[A-Za-z0-9]{32,}"), "疑似 OpenAI/第三方 API Key"),
    # 这四条只在"等号后面**同一行**真的跟了一串值"时才算命中。
    # 用 [ 	]* 而不是 \s*：\s 含换行，空值行（AL_SMTP_PASSWORD=）会一路
    # 匹配到下一行的内容去，把模板文件全部误报成"含密钥"。
    # 空值（AL_SMTP_PASSWORD=）是模板的正常写法；${VAR} 是 compose 的变量引用，
    # 两者都不含任何秘密——早期版本没排除它们，每次打包都误报两条，
    # 而一个天天误报的自查很快就会被人无视，那才是真正的风险。
    (re.compile(rb"AL_ADMIN_TOKEN[ \t]*=[ \t]*[A-Za-z0-9]{16,}"), "AL_ADMIN_TOKEN 实值"),
    (re.compile(rb"AL_QQ_APP_KEY[ \t]*=[ \t]*(?!\$\{)\S{8,}"), "QQ APP KEY 实值"),
    (re.compile(rb"AL_SMTP_PASSWORD[ \t]*=[ \t]*(?!\$\{)\S+"), "SMTP 密码实值"),
    (re.compile(rb"AL_JWT_SECRET[ \t]*=[ \t]*(?!\$\{)[A-Za-z0-9]{16,}"), "JWT 密钥实值"),
]
# 模板文件里出现占位写法是正常的，不算命中
PLACEHOLDER = re.compile(rb"(your[-_]|xxx|placeholder|<[^>]{1,40}>|\.\.\.|example|\$\{)", re.I)

# 自查跳过测试目录。
#
# 理由不是"测试文件不重要"，而是它们里面的 `sk-ant-…` 按定义就不是秘密：
# 这些是断言用的假 key（`sk-ant-must-never-appear-in-health-9876543210` 这种），
# 随 MIT 开源仓库公开在 GitHub 上，任何人都能看到。把它们算作"包里有密钥"
# 会让打包直接失败，而唯一的"修法"是从包里删掉测试——但 DEPLOY-BAREMETAL.md
# 恰恰让运维在服务器上跑这两套测试。
#
# 换句话说：真密钥进了测试文件，问题在"它被提交进了 git"这一步，
# 那是另一条防线的事（pre-commit / 密钥扫描），不该由打包自查来兜底——
# 让一个必然误报的检查天天红，结果一定是它被整体忽略。
AUDIT_SKIP_DIR_PARTS = ("/tests/",)


def _audit_archive(tar_path: Path) -> list:
    """扫描已生成的包，找疑似真密钥。返回命中清单（空 = 干净）。"""
    hits = []
    with tarfile.open(tar_path, "r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile() or member.size > 2_000_000:
                continue
            if any(part in "/" + member.name for part in AUDIT_SKIP_DIR_PARTS):
                continue
            fp = tf.extractfile(member)
            if fp is None:
                continue
            blob = fp.read()
            for pattern, label in SECRET_PATTERNS:
                for m in pattern.finditer(blob):
                    line_start = blob.rfind(b"\n", 0, m.start()) + 1
                    line_end = blob.find(b"\n", m.end())
                    line = blob[line_start : line_end if line_end != -1 else len(blob)]
                    if PLACEHOLDER.search(line):
                        continue  # 模板占位，放行
                    hits.append(f"{member.name}: {label}")
                    break
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="打包前先构建前端与后台面板")
    args = ap.parse_args()

    if args.build:
        for sub in ("frontend", "admin"):
            print(f"[构建] web/{sub} …")
            r = subprocess.run("npm run build", cwd=REPO / "web" / sub, shell=True)
            if r.returncode != 0:
                print(f"✗ web/{sub} 构建失败，中止打包", file=sys.stderr)
                return 1

    # 构建产物必须存在——否则打出来的是个前端全空的包，
    # 而这种包上传后表现为"网站打不开"，排查起来毫无线索。
    missing = [p for p in ("web/frontend/dist/index.html", "web/admin/dist/index.html")
               if not (REPO / p).exists()]
    if missing:
        print("✗ 缺少前端构建产物：" + "、".join(missing), file=sys.stderr)
        print("  先跑一次 npm run build，或给本脚本加 --build", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    name = f"audiencelens-{_version()}-{stamp}"
    tar_path = OUT_DIR / f"{name}.tar.gz"
    if tar_path.exists():
        tar_path.unlink()

    count = 0
    with tarfile.open(tar_path, "w:gz") as tf:
        for rel in INCLUDE:
            src = REPO / rel
            if not src.exists():
                print(f"  · 跳过（不存在）：{rel}")
                continue
            for f in _iter_files(src):
                _add(tf, f, f"{name}/{f.relative_to(REPO).as_posix()}")
                count += 1
        # 配置模板显式加：它是 .env.production.example，被上面的 .env 规则挡掉了
        example = REPO / "web" / ".env.production.example"
        if example.exists():
            _add(tf, example, f"{name}/web/.env.production.example")
            count += 1

    hits = _audit_archive(tar_path)
    if hits:
        tar_path.unlink()
        print("\n✗ 包内发现疑似真实密钥，已删除该包：", file=sys.stderr)
        for h in sorted(set(hits)):
            print(f"    {h}", file=sys.stderr)
        return 2

    size_mb = tar_path.stat().st_size / 1024 / 1024
    print(f"\n✓ 打包完成：{tar_path.relative_to(REPO)}")
    print(f"  文件数 {count} · 体积 {size_mb:.1f} MB · 密钥自查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
