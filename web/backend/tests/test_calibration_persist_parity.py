"""校准结果落库：两条链路必须用同一份口径。

背景：run_calibration_check 返回的 coverage.pairwise_distances 用 (id1, id2)
**元组**做键。元组键对它的 Python 消费方（CLI）完全合理，但 review.calibration
是 JSON 列，json.dumps 遇到元组键直接
    TypeError: keys must be str, int, float, bool or None, not tuple
整条 UPDATE 失败，评审被标成 failed，用户看到的报错还跟评审内容毫无关系。
full 是唯一跑校准的档位，所以该档只要 ≥2 位人格就 100% 失败。

v1 很早就修了（services/__init__.py 调 _json_safe），并且有一条专门的测试
test_v1_engine_hardening.py::test_full_mode_completes_and_persists_calibration
一直是绿的 —— 但 v2（review_service.py）漏了同一步，而前端走的正是 v2。
一条链路的测试通过，恰恰掩盖了另一条链路是坏的。

所以这个文件的两条测试分工明确：
  · test_real_calibration_output_is_persistable —— 用**引擎真实返回值**验口径本身；
  · test_every_calibration_assignment_is_wrapped —— 源码级卡口，任何新增的
    `.calibration = ...` 赋值只要没过 json_safe 就红。后者才是防复发的那一道，
    因为「又加了一条链路却忘了洗」正是这个仓库反复犯的错。
"""

import json
import os
import re

import pytest

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")


def test_real_calibration_output_is_persistable():
    """拿引擎真跑出来的 calibration，洗过之后必须能进 JSON 列。"""
    from app.services.json_safe import json_safe

    import sys

    from app.config import settings

    src = os.path.join(settings.repo_root, "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from runner.calibration import run_calibration_check

    persona_outputs = [
        {
            "persona_id": "P01",
            "persona_name": "甲",
            "key_issues": [{"issue": "定价不透明", "severity": "high"}],
        },
        {
            "persona_id": "P02",
            "persona_name": "乙",
            "key_issues": [{"issue": "首屏信息过载", "severity": "medium"}],
        },
    ]
    raw = run_calibration_check(persona_outputs, [])

    # 先坐实「不洗就是坏的」——否则这条测试可能在引擎改了结构后悄悄失去意义
    with pytest.raises(TypeError):
        json.dumps(raw)

    cleaned = json_safe(raw)
    dumped = json.dumps(cleaned)  # 不抛异常即为通过
    assert dumped

    # 洗完不能把数据洗没了：元组键按 "id1|id2" 落地，值原样保留
    pair_keys = list(cleaned["coverage"]["pairwise_distances"].keys())
    assert pair_keys, "pairwise_distances 不该被洗空"
    assert all(isinstance(k, str) for k in pair_keys)
    assert "P01|P02" in pair_keys


def test_every_calibration_assignment_is_wrapped():
    """源码级卡口：所有给 .calibration 赋值的地方都必须过 json_safe。

    这条不测行为测写法，是有意为之 —— 行为测试只能覆盖到已经存在的链路，
    而这个 bug 的本质是「新开了一条链路，忘了带上这一步」。
    """
    offenders = []
    pattern = re.compile(r"^\s*\w+\.calibration\s*=\s*(?!.*json_safe)(.+)$")

    for root, _dirs, files in os.walk(APP_DIR):
        if "__pycache__" in root:
            continue
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    if pattern.match(line):
                        rel = os.path.relpath(path, APP_DIR)
                        offenders.append("%s:%d  %s" % (rel, lineno, line.strip()))

    assert not offenders, (
        "以下位置直接把 calibration 赋给 JSON 列，没有过 json_safe —— "
        "元组键会让整条 UPDATE 抛 TypeError：\n  " + "\n  ".join(offenders)
    )
