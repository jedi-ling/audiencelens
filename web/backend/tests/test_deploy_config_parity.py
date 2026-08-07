"""部署配置的自洽性：compose 要的东西，模板里必须有。

这条缺陷的形状在本次审计里反复出现——**文档指着一个文件说"按它填"，
而那个文件里根本没有它说的东西**。具体到这里：

  docker-compose.prod.yml 开头写着
      「cp .env.production.example .env 并填写（含 FRONTEND_BIND 和 SITE_DOMAIN）」
  而 .env.production.example 里这两项一个都不存在。照做的后果是：
    · FRONTEND_BIND 回落 80  → frontend 直接占用公网 80，与 Caddy 抢端口，起不来；
    · SITE_DOMAIN 回落 localhost → Caddy 向 Let's Encrypt 申请 localhost 的证书，
      必然失败，站点没有 HTTPS。
  两处都不会明说原因，运维只会看到"容器起不来 / 证书申不下来"。

用测试而不是靠人肉核对，是因为这类漂移只会越来越多：以后往 compose 里加一个
变量却忘了写进模板，这条测试立刻红。
"""

import os
import re

WEB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE = os.path.join(WEB_DIR, ".env.production.example")
COMPOSE_FILES = [
    os.path.join(WEB_DIR, "docker-compose.yml"),
    os.path.join(WEB_DIR, "docker-compose.prod.yml"),
]

# compose 自己就带了合理默认值、且运维无需知道的内部项，不要求模板列出。
# 白名单要小而明确——它每多一项，这条测试就少守一块地方。
_NOT_REQUIRED_IN_TEMPLATE = {
    "VAR",  # 注释里 ${VAR:?...} 的示例写法，不是真变量
}


def _referenced_vars() -> set:
    names = set()
    for path in COMPOSE_FILES:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.lstrip().startswith("#"):
                    continue  # 注释里的说明不算引用
                names.update(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)", line))
    return names - _NOT_REQUIRED_IN_TEMPLATE


def test_every_compose_var_appears_in_the_template():
    with open(TEMPLATE, encoding="utf-8") as fh:
        template_text = fh.read()

    missing = sorted(v for v in _referenced_vars() if v not in template_text)
    assert not missing, (
        "docker-compose 引用了这些变量，但 web/.env.production.example 里一个字都没提，"
        "照模板部署的人不可能知道要设它们：\n  " + "\n  ".join(missing)
    )


def test_tls_overlay_vars_are_marked_required():
    """FRONTEND_BIND / SITE_DOMAIN 不能只是"提到"，必须标成要改的。

    它们没有可用的默认值：80 会和 Caddy 抢端口，localhost 申不到证书。
    只写一行注释而不给出待填项，等于把坑留在原地。
    """
    with open(TEMPLATE, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    for var in ("FRONTEND_BIND", "SITE_DOMAIN"):
        assigned = [ln for ln in lines if re.match(rf"^\s*{var}\s*=", ln)]
        assert assigned, f"{var} 必须在模板里作为待填项出现（而不是只在注释里被提到）"


# ---------------------------------------------------------------------------
# 反方向：模板/代码里有的 AL_* 配置项，compose 必须真的透传下去
#
# 上面那条守的是"compose 引用了、模板没写"。这次审计发现漏的是**反方向**：
# 模板明写 AL_QUOTA_TOKENS_TOTAL=3000000，运维照填，但 compose 的
# environment 是显式白名单、没有 env_file，容器里也不存在 /app/web/.env
# （build context 是 ./backend），于是容器读到的是默认值 0 = 不限制——
# 整条钱包闸静默关着，而运维以为它开着。
#
# 这与 enable_evaluation 那次"从 UI 传到后端被 schema 静默丢弃"是同一形状：
# 配置项在链路的某一环被吞掉，两端都不报错。只是这次吞在编排层。
# ---------------------------------------------------------------------------

def _template_al_vars() -> set:
    """模板里**未被注释掉**的 AL_* / ANTHROPIC_* 变量。

    注释掉的（# AL_XXX=...）是"可选调优"提示，不强制要求透传——
    但一旦有人取消注释填了值，就会踩同一个坑。所以下面的断言只管非注释项，
    另有一条测试单独提醒可选项的风险。
    """
    names = set()
    with open(TEMPLATE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^(AL_[A-Z0-9_]+|ANTHROPIC_API_KEY)=", line)
            if m:
                names.add(m.group(1))
    return names


def _compose_passthrough_vars() -> set:
    """compose 的 environment 里真正透传给 backend 的变量名。"""
    names = set()
    path = os.path.join(WEB_DIR, "docker-compose.yml")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"^\s*-\s*(AL_[A-Z0-9_]+|ANTHROPIC_API_KEY)=", line)
            if m:
                names.add(m.group(1))
    return names


# compose 故意不透传、且模板已诚实标注"写在这里不生效"的项。
# 这个集合必须保持极小，每加一项都等于承认一处配置不生效。
_KNOWN_NOT_PASSED = {
    # 模板里明写了"docker-compose.yml 没有透传这一项，所以在 Docker 部署下
    # 写在这里是不生效的——故意不列成配置项"
    "AL_SMTP_TIMEOUT_SECONDS",
}


def test_every_template_var_is_passed_through_by_compose():
    """模板要求填的每一项，Docker 下都必须真的到得了容器。

    失败时说明有人加了配置项、写进了模板，却忘了加进 compose 的白名单——
    照模板配置的运维会得到一个静默失效的开关。
    """
    missing = _template_al_vars() - _compose_passthrough_vars() - _KNOWN_NOT_PASSED
    assert not missing, (
        f"这些变量在 .env.production.example 里要求填写，但 docker-compose.yml 的 "
        f"environment 白名单没有透传，Docker 部署下填了等于没填：{sorted(missing)}"
    )


def test_security_relevant_settings_are_passed_through():
    """几个有安全/钱包含义的开关必须在透传列表里，不允许靠默认值。

    单独钉住是因为上一条依赖"模板里写了"——万一有人把某项从模板里删掉，
    上一条会跟着变绿，而这几项一旦失效是有真实代价的。
    """
    passed = _compose_passthrough_vars()
    required = {
        "AL_QUOTA_ENABLED",          # 关掉 = 配额整套不工作
        "AL_QUOTA_TOKENS_TOTAL",     # 关掉 = 终身钱包闸不工作
        "AL_RATELIMIT_ENABLED",      # 关掉 = 限流不工作
        "AL_SKILL_FREE_USES",        # 关掉 = 高级技能免费次数不受控
        "AL_AUTH_ENABLED",           # 关掉 = 所有人共用匿名桶
    }
    assert required <= passed, f"未透传：{sorted(required - passed)}"
