# -*- coding: utf-8 -*-
"""测试环境自身的隔离性。

这一条守的不是被测代码，而是**测试套自己不会毁掉数据**。

conftest 里原本写的是 os.environ.setdefault("AL_DATABASE_URL", 临时库)，
而 AL_DATABASE_URL 正是真实部署用的变量名。于是在配了它的机器上
（部署环境、CI、或者刚 source 过 .env 的 shell）跑一次 pytest，
整个测试套会对着那个库建用户、删用户、写用量流水——
注释还写着"绝不碰开发数据"。

失败模式的严重性差一个量级：普通 bug 是测试红，这个是数据没了。
"""

import os

from app.config import settings


def test_database_url_is_a_temp_test_db():
    url = settings.database_url
    assert "al-test-" in url or os.environ.get("AL_TEST_DATABASE_URL"), (
        f"测试跑在一个非临时库上：{url}。"
        "conftest 必须强制覆盖 AL_DATABASE_URL，不能用 setdefault。"
    )


def test_ambient_database_url_cannot_hijack_the_suite(monkeypatch):
    """模拟"机器上导出了生产 AL_DATABASE_URL"：conftest 的赋值必须赢。

    这里断言的是 conftest 已经执行完的结果——环境里那个值已经被替换掉了，
    所以任何后续读取（app.config 在导入期就读过一次）都拿不到外部值。
    """
    assert "al-test-" in os.environ["AL_DATABASE_URL"] or os.environ.get(
        "AL_TEST_DATABASE_URL"
    ), "AL_DATABASE_URL 仍然是外部传进来的值，隔离没生效"


def test_explicit_opt_in_var_is_the_only_escape_hatch():
    """想把测试指向别的库，只能用显式的 AL_TEST_DATABASE_URL。

    钉住这个设计：逃生舱必须是一个**不同于生产配置**的变量名，
    否则"我只是配了部署环境"就会变成"我把测试指向了生产库"。
    """
    src = open(
        os.path.join(os.path.dirname(__file__), "conftest.py"), encoding="utf-8"
    ).read()
    assert 'os.environ["AL_DATABASE_URL"]' in src, "AL_DATABASE_URL 必须强制赋值"
    assert "AL_TEST_DATABASE_URL" in src, "逃生舱变量名必须与生产配置区分开"
    assert 'setdefault("AL_DATABASE_URL"' not in src, "不能退回 setdefault"
