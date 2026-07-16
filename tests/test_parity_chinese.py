from tools.parity_check import extract_tokens, jaccard_similarity


def test_chinese_issue_paraphrases_share_tokens():
    a = extract_tokens("新手教程太长")
    b = extract_tokens("教程长度过高导致新手退出")
    assert "教程" in a & b
    assert jaccard_similarity(a, b) > 0


def test_unrelated_chinese_issues_do_not_overlap():
    a = extract_tokens("新手教程太长")
    b = extract_tokens("画面色彩鲜艳")
    assert jaccard_similarity(a, b) == 0


def test_english_tokenization_remains_supported():
    assert extract_tokens("Long onboarding tutorial") == {"long", "onboarding", "tutorial"}
