import json

from harness.stereotype_judge import (
    detect_stereotypes,
    llm_detect,
    regex_detect,
)


class TestRegexLayer:
    def test_gender_causal_detected(self):
        violations = regex_detect("作为女性玩家，所以我更偏好剧情向内容")
        assert len(violations) >= 1
        assert violations[0]["source"] == "regex"

    def test_mbti_causal_detected(self):
        violations = regex_detect("身为INTJ，因此我判断这个系统深度不够")
        assert len(violations) >= 1

    def test_behavior_profile_clean(self):
        violations = regex_detect("我的耐心阈值很低，这个教程太长了")
        assert violations == []

    def test_empty_text(self):
        assert regex_detect("") == []


class TestDetectStereotypes:
    def test_regex_only_method(self):
        result = detect_stereotypes(["我的耐心阈值很低"], use_llm=False)
        assert result["method"] == "regex"
        assert result["violations"] == []
        assert result["llm_checked"] == 0

    def test_no_api_key_degrades_gracefully(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = detect_stereotypes(["一段普通文本"], use_llm=True)
        # 无 key 时 LLM 层跳过，方法回落为 regex
        assert result["method"] == "regex"
        assert result["llm_skipped"] == 1


class _FakeClient:
    """模拟 anthropic client，返回固定 judge 判定。"""

    def __init__(self, verdict: dict):
        self._verdict = verdict
        self.messages = self

    def create(self, **kwargs):
        class _Block:
            pass

        class _Resp:
            pass

        block = _Block()
        block.text = json.dumps(self._verdict, ensure_ascii=False)
        resp = _Resp()
        resp.content = [block]
        return resp


class TestLLMLayer:
    def test_llm_violation_parsed(self):
        client = _FakeClient(
            {
                "violation": True,
                "type": "gender",
                "quoted_text": "女生不适合硬核游戏",
                "reasoning": "性别到偏好的因果推断",
            }
        )
        verdict = llm_detect("考虑到我是女生……", client=client)
        assert verdict["source"] == "llm"
        assert verdict["type"] == "gender"

    def test_llm_clean_text(self):
        client = _FakeClient({"violation": False, "type": "none", "quoted_text": "", "reasoning": ""})
        verdict = llm_detect("耐心阈值低所以教程太长", client=client)
        assert verdict == {"source": "llm", "violation": False}

    def test_detect_combines_layers(self):
        client = _FakeClient(
            {
                "violation": True,
                "type": "age",
                "quoted_text": "年纪大了学不会",
                "reasoning": "年龄因果推断",
            }
        )
        result = detect_stereotypes(["我年纪大了学不会这个"], use_llm=True, client=client)
        assert result["method"] == "regex+llm"
        assert any(v["source"] == "llm" for v in result["violations"])
