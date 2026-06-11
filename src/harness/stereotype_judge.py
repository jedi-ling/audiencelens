"""两层刻板印象检测：正则初筛 + LLM 复审。

第一层（正则）：零成本、可解释，抓固定句式，离线可用。
第二层（LLM judge）：有 ANTHROPIC_API_KEY 时启用，抓换了措辞的
"人口统计特征 → 行为偏好"因果推断，正则无法覆盖的部分。
"""

import json
import os
import re
from typing import List, Optional

# 刻板印象禁止模式（第一层）
REGEX_PATTERNS = [
    re.compile(r"作为[一名个]?[男女女性男性].*?(?:所以|因此|更|偏好|倾向)", re.IGNORECASE),
    re.compile(r"(?:她|他|她们|他们)(?:天生|天然|本能地).*(?:偏好|喜欢|选择)", re.IGNORECASE),
    re.compile(r"(?:这个|那)(?:年龄|年代|岁数)(?:段|的)(?:人|玩家|用户).*(?:通常|一般|都|总是)", re.IGNORECASE),
    re.compile(r"(?:作为|身为)[A-Z]{4}.*?(?:所以|因此|决定|判断)", re.IGNORECASE),
    re.compile(r"(?:women|men|female|male)\s+(?:prefer|tend\s+to|naturally|instinctively)", re.IGNORECASE),
    re.compile(r"(?:as\s+a\s+)?(?:woman|man|girl|boy|elderly|young)\s+.*?(?:therefore|so|prefer|tend)", re.IGNORECASE),
]

JUDGE_MODEL = "claude-haiku-4-5-20251001"

JUDGE_PROMPT = """你是评审系统的伦理审查员。系统规则：人格的人口统计特征（性别、年龄、地域、MBTI）只能作为表达风格的弱修饰，绝不能作为行为偏好或判断结论的因果依据。

判断下面这段评审文本是否违反该规则，即是否存在"因为某人口统计身份，所以有某行为/偏好/判断"的因果推断。基于行为画像（如耐心低、价格敏感度高）的推断不算违规。

文本：
{text}

只输出 JSON，不要其他内容：
{{"violation": true/false, "type": "gender|age|region|mbti|none", "quoted_text": "违规原句，无则空", "reasoning": "一句话理由"}}"""


def regex_detect(text: str) -> List[dict]:
    violations = []
    for pattern in REGEX_PATTERNS:
        for match in pattern.findall(text):
            violations.append(
                {
                    "source": "regex",
                    "type": "pattern",
                    "quoted_text": str(match)[:80],
                    "reasoning": f"命中正则: {pattern.pattern[:40]}",
                }
            )
    return violations


def llm_detect(text: str, client=None) -> Optional[dict]:
    """LLM 复审单段文本。无 API key 或调用失败时返回 None（表示未执行）。"""
    if client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
        except Exception:
            return None
    try:
        response = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=512,
            messages=[
                {"role": "user", "content": JUDGE_PROMPT.format(text=text)}
            ],
        )
        raw = response.content[0].text.strip()
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            return None
        verdict = json.loads(json_match.group(0))
        if verdict.get("violation"):
            return {
                "source": "llm",
                "type": verdict.get("type", "unknown"),
                "quoted_text": str(verdict.get("quoted_text", ""))[:80],
                "reasoning": str(verdict.get("reasoning", ""))[:200],
            }
        return {"source": "llm", "violation": False}
    except Exception:
        return None


def detect_stereotypes(
    texts: List[str], use_llm: bool = False, client=None
) -> dict:
    """对一组文本执行两层检测。

    Returns:
        {"violations": [...], "method": "regex" | "regex+llm",
         "llm_checked": int, "llm_skipped": int}
    """
    violations = []
    llm_checked = 0
    llm_skipped = 0

    for text in texts:
        if not text:
            continue
        violations.extend(regex_detect(text))
        if use_llm:
            verdict = llm_detect(text, client=client)
            if verdict is None:
                llm_skipped += 1
            else:
                llm_checked += 1
                if verdict.get("source") == "llm" and verdict.get("quoted_text"):
                    violations.append(verdict)

    return {
        "violations": violations,
        "method": "regex+llm" if (use_llm and llm_checked > 0) else "regex",
        "llm_checked": llm_checked,
        "llm_skipped": llm_skipped,
    }
