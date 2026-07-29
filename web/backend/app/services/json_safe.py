"""JSON 列的落地口径：把不能序列化的字典键递归转成字符串。

单独成模块，是因为 v1（services/__init__.py）和 v2（review_service.py）
两条链路都要用同一份口径。以前这两个函数只长在 v1 里，v2 就直接漏了 ——
参见下面 _json_safe 的注释，那是一个把整档评审打挂的真实故障。
本仓库的老病灶就是「同一件事修了一条路径、另一条成了后门」，
所以凡是两条链路共用的东西一律只留一份实现。
"""


def json_safe_key(key):
    if isinstance(key, tuple):
        return "|".join(str(k) for k in key)
    if key is None or isinstance(key, (str, int, float, bool)):
        return key
    return str(key)


def json_safe(value):
    """把不能进 JSON 列的字典键递归转成字符串。

    起因是一个真挂的路径：run_calibration_check 返回的
    coverage.pairwise_distances 用 (id1, id2) **元组**做键 —— 在 CLI 里被 Python
    直接消费没问题，但 review.calibration 是 JSON 列，序列化时元组键直接
    TypeError("keys must be str, int, float, bool or None, not tuple")，
    整条 UPDATE 失败，评审被标成 failed，用户拿到的错误还是一句与评审
    毫无关系的 "keys must be str"。full 是唯一跑校准的档位，所以只要
    ≥2 位人格，该档 100% 失败。

    元组键按 "id1|id2" 落地。修在持久化侧而不是 calibration.py：那是引擎的返回值，
    元组键对它的 Python 消费方（CLI）完全合理，能不能进 JSON 列是这里的责任。
    """
    if isinstance(value, dict):
        return {json_safe_key(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value
