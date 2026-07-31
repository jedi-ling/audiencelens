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
