"""议题相似度计算：优先使用本地语义 embedding，不可用时回退到字符串相似度。

语义档依赖 sentence-transformers（可选依赖）：
    pip install sentence-transformers
首次使用会下载 BAAI/bge-small-zh-v1.5（约 100MB），之后离线可用。

除"像不像"之外，本模块还实现了一道**极性冲突否决**（见下方 polarity guard 一节）：
两段文本词法/语义再像，只要方向相反，就不许合并成同一议题。
"""

import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

SEMANTIC_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
SEMANTIC_THRESHOLD = 0.65
LEXICAL_THRESHOLD = 0.7

_model = None
_model_load_failed = False


def lexical_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# ===========================================================================
# 极性冲突保护（polarity guard）
# ===========================================================================
# 为什么需要这一层：
#   中文里语义**相反**的短句往往只差一两个字，字符级相似度反而奇高——
#   "价格太高" vs "价格太低" = 0.750，"美术风格不统一" vs "美术风格很统一" = 0.857，
#   "战斗手感差" vs "战斗手感好" = 0.800，全都越过了 LEXICAL_THRESHOLD=0.7。
#   语义 embedding 也救不了：反义句共享几乎全部主题词，余弦相似度同样偏高。
#   后果是支持方和反对方被塞进同一个聚类，compute_disagreements 把两条**对立证据**
#   混在一个 topic 下——这正好把"暴露分歧"这个核心价值算反了。
#
# 为什么不是调阈值：
#   0.857 这种要把阈值提到 0.9 才拦得住，而那会顺手拆散所有正常的同义改写
#   （"付费墙太早" vs "付费墙太早出现" 才 0.86）。问题会从"漏合并"变成"过度拆分"。
#   所以阈值不动，极性判定作为一道**独立的否决票**加在 is_same_issue 上，
#   对 lexical / semantic 两个档同时生效。
#
# 为什么是"只在明确冲突时否决"，而不是"缺极性词就否决"：
#   绝大多数议题标题（"缺少手柄支持"、"存档丢失"）没有极性词。若把"判不出极性"
#   也当成不许合并，等于把去重整体关掉。所以规则是**双向都读出极性、且同一维度上
#   互为反向**才否决；读不出来就放行，交回给词法/语义分数决定。
# ---------------------------------------------------------------------------

# 极性维度表：维度名 -> {极名: (词条, ...)}。
# 一个词可以属于多个维度（例如"贵"既是价格维度的一极，也代表"高"这个方向），
# 这样"价格太低" vs "定价偏贵" 能通过共享的 high_low 维度对上并判为冲突。
# 只用规则表，不引入任何 NLP 依赖。
POLARITY_DIMENSIONS: Dict[str, Dict[str, Tuple[str, ...]]] = {
    # 高 / 低（含价格的"贵"，让"太低"和"偏贵"能在同一维度上对撞）
    "high_low": {
        "high": (
            "高", "偏高", "过高", "偏多",
            "贵", "昂贵", "高价",
            "难", "困难", "硬核",
            "high", "higher", "highest", "expensive", "pricey", "overpriced",
            "hard", "difficult",
        ),
        "low": (
            "低", "偏低", "过低",
            "便宜", "低价",
            "易", "简单", "容易",
            "low", "lower", "lowest", "cheap", "inexpensive",
            "easy", "simple",
        ),
    },
    # 价格本身（独立维度，"贵" vs "便宜" 必须冲突）
    "price": {
        "expensive": ("贵", "昂贵", "高价", "expensive", "pricey", "overpriced"),
        "cheap": ("便宜", "低价", "cheap", "inexpensive", "affordable"),
    },
    # 多 / 少（含"丰富"这类程度词，"音效不够丰富" vs "音效很丰富" 靠它 + 否定词命中）
    "amount": {
        "many": (
            "多", "过多", "冗余", "多余", "丰富", "充足", "充裕", "饱满",
            "too much", "too many", "plenty", "abundant", "rich", "many", "much",
        ),
        "few": (
            "少", "过少", "稀少", "匮乏", "单薄", "贫乏", "寡淡",
            "too little", "too few", "scarce", "sparse", "few", "little",
        ),
    },
    # 大 / 小
    "size": {
        "big": ("大", "偏大", "巨大", "big", "large", "huge"),
        "small": ("小", "偏小", "细小", "small", "tiny", "little"),
    },
    # 长 / 短（"啰嗦/冗长/拖沓" 同向，"仓促/草率" 同向）
    "length": {
        "long": (
            "长", "偏长", "冗长", "啰嗦", "唠叨", "拖沓", "冗长啰嗦",
            "long", "lengthy", "verbose", "drawn out",
        ),
        "short": (
            "短", "偏短", "仓促", "草率", "潦草",
            "short", "brief", "rushed",
        ),
    },
    # 快 / 慢
    "speed": {
        "fast": ("快", "偏快", "过快", "fast", "quick", "rapid", "speedy"),
        "slow": ("慢", "偏慢", "过慢", "拖沓缓慢", "slow", "sluggish"),
    },
    # 强 / 弱
    "strength": {
        "strong": ("强", "强烈", "厚重", "有力", "strong", "powerful", "punchy"),
        "weak": ("弱", "薄弱", "疲软", "绵软", "weak", "feeble", "floaty"),
    },
    # 好 / 差（"不错"整体收作正向，避免被误拆成"不 + 错"）
    "quality": {
        "good": (
            "好", "很好", "不错", "优秀", "出色", "优异", "棒", "友好", "舒服", "顺手",
            "good", "great", "excellent", "nice", "solid", "better", "best",
        ),
        "bad": (
            "差", "糟", "糟糕", "拙劣", "低劣", "烂", "劣",
            "bad", "poor", "terrible", "awful", "worse", "worst",
        ),
    },
    # 清晰 / 模糊
    "clarity": {
        "clear": ("清晰", "清楚", "明确", "明晰", "直观", "clear", "obvious", "explicit"),
        "vague": ("模糊", "含糊", "晦涩", "费解", "vague", "unclear", "confusing", "ambiguous"),
    },
    # 统一 / 杂乱
    "coherence": {
        "consistent": ("统一", "一致", "协调", "整齐", "consistent", "cohesive", "coherent", "unified"),
        "messy": ("杂乱", "混乱", "割裂", "凌乱", "inconsistent", "messy", "chaotic", "incoherent"),
    },
    # 难 / 易（"难/简单"同时挂到 high_low 上，让"难度太高" vs "难度太简单"这类
    # 换说法的反向表达也能对撞；否则一个只读出 high、一个只读出 easy，没有共享维度）
    "difficulty": {
        "hard": ("难", "偏难", "硬核", "hard", "difficult", "punishing"),
        "easy": ("易", "简单", "容易", "轻松", "easy", "simple", "trivial"),
    },
    # 有趣 / 无聊
    "fun": {
        "fun": ("有趣", "好玩", "上瘾", "吸引人", "fun", "engaging", "addictive", "interesting"),
        "boring": ("无聊", "枯燥", "乏味", "沉闷", "boring", "dull", "tedious", "bland"),
    },
}

# 前置否定词：出现在极性词**之前**时把该极性翻转。
# "不X / 没有X / 无X / 缺少X" 这类是中文评审意见里最常见、也最容易漏的反向表达。
PRE_NEGATORS: Tuple[str, ...] = (
    "不够", "不太", "不是很", "不是", "不怎么", "不",
    "没有", "没", "无", "未", "非",
    "缺少", "缺乏", "缺失", "欠缺", "毫无", "全无",
    "not", "no", "never", "without", "lack of", "lacks", "lack",
    "lacking", "isn't", "aren't", "wasn't", "don't", "doesn't",
    "didn't", "cannot", "can't", "hardly", "barely",
)

# 后置否定词：中文常写成"统一性不足 / 打击感不够 / 手感不佳"，
# 否定跟在极性词后面，只看前文会漏掉。
POST_NEGATORS: Tuple[str, ...] = ("不足", "不够", "不佳", "不行", "欠缺", "缺失")

# 中性短语：整体消费掉，防止里面的"不/好/多/难"被误当成否定词或极性词。
# "难度"是最典型的坑——它是维度**名词**而不是"难"这个方向，
# 不屏蔽的话"难度太高"和"难度太低"都会先读出一个 hard，白白污染判定。
NEUTRAL_PHRASES: Tuple[str, ...] = (
    "差不多", "不过", "不仅", "不但", "不只", "不管", "无论", "不论",
    "好像", "好评", "不妨",
    "难度", "高低", "大小", "长短", "快慢", "多少", "好坏", "强弱",
)

# 否定词与极性词之间允许出现的"填充"成分（程度副词、系动词、名词化后缀等）。
# 只允许这些东西夹在中间，是为了限制否定的作用域：
# "不统一" / "不够丰富" / "不是很清晰" / "统一性不足" 算否定命中，
# 而隔着实义内容的（"不玩这类游戏的人觉得美术统一"）不算。
_FILLER_TOKENS: Tuple[str, ...] = (
    "很", "太", "非常", "特别", "十分", "挺", "比较", "够", "足够",
    "这么", "那么", "更", "过于", "有点", "有些", "稍微", "略", "偏",
    "是", "会", "得", "地", "的", "了", "感觉", "显得", "算",
    "性", "度", "感", "上", "程度",
    "very", "really", "so", "too", "quite", "that", "enough", "at", "all",
    "is", "are", "be", "been", "feel", "feels", "felt", "seem", "seems",
    "it", "a", "an", "the",
)
_FILLER_RE = re.compile(
    r"^(?:\s|" + "|".join(re.escape(t) for t in _FILLER_TOKENS) + r")*$",
    re.IGNORECASE,
)
_MAX_NEGATION_GAP = 8  # 否定词与极性词之间最多允许的字符距离


def _build_token_regex() -> re.Pattern:
    """把中性短语 / 否定词 / 极性词编成一条按长度降序的 alternation。

    为什么要一条正则统一扫：re.finditer 从左到右取非重叠匹配，且 alternation
    会优先命中先出现的分支——按长度降序排列后就天然实现了"最长匹配优先"。
    这样"无聊"不会被拆成否定词"无"+"聊"，"缺少"不会被读成极性词"少"，
    "不够丰富"里"不够"整体作否定词而不是"不"。
    """
    words: Set[str] = set(NEUTRAL_PHRASES)
    words.update(PRE_NEGATORS)
    words.update(POST_NEGATORS)
    for poles in POLARITY_DIMENSIONS.values():
        for terms in poles.values():
            words.update(terms)
    ordered = sorted(words, key=lambda w: (-len(w), w))
    parts = []
    for w in ordered:
        esc = re.escape(w)
        # 英文词条要求词边界，否则 "low" 会命中 "slow"、"no" 会命中 "not"
        if re.fullmatch(r"[a-z0-9 '\-]+", w):
            esc = r"\b" + esc + r"\b"
        parts.append(esc)
    return re.compile("|".join(parts), re.IGNORECASE)


_TOKEN_RE = _build_token_regex()

# 词条 -> [(维度, 极), ...]
_TERM_INDEX: Dict[str, List[Tuple[str, str]]] = {}
for _dim, _poles in POLARITY_DIMENSIONS.items():
    for _pole, _terms in _poles.items():
        for _t in _terms:
            _TERM_INDEX.setdefault(_t.lower(), []).append((_dim, _pole))

_PRE_NEG_SET = {w.lower() for w in PRE_NEGATORS}
_POST_NEG_SET = {w.lower() for w in POST_NEGATORS}
_NEUTRAL_SET = {w.lower() for w in NEUTRAL_PHRASES}


def _opposite_pole(dim: str, pole: str) -> str:
    """取同维度的另一极（每个维度恰好两极）。"""
    poles = list(POLARITY_DIMENSIONS[dim].keys())
    return poles[0] if poles[1] == pole else poles[1]


def _scan(text: str) -> Tuple[List[dict], bool]:
    """扫描一段文本，返回 (匹配列表, 是否出现否定词)。

    匹配列表元素：{"kind": "term"/"pre_neg"/"post_neg"/"neutral", "text", "start", "end"}
    """
    matches: List[dict] = []
    has_negation = False
    for m in _TOKEN_RE.finditer(text):
        raw = m.group(0).lower()
        if raw in _NEUTRAL_SET:
            kind = "neutral"
        elif raw in _PRE_NEG_SET:
            kind = "pre_neg"
            has_negation = True
        elif raw in _POST_NEG_SET:
            kind = "post_neg"
            has_negation = True
        elif raw in _TERM_INDEX:
            kind = "term"
        else:
            continue
        matches.append(
            {"kind": kind, "text": raw, "start": m.start(), "end": m.end()}
        )
    return matches, has_negation


def _gap_is_filler(text: str, start: int, end: int) -> bool:
    """两个匹配之间的间隔是否只有程度副词/系动词这类填充成分。"""
    if end <= start:
        return True
    if end - start > _MAX_NEGATION_GAP:
        return False
    return bool(_FILLER_RE.match(text[start:end]))


def polarity_profile(text: str) -> Dict[str, Set[str]]:
    """把一段文本读成 {维度: {极, ...}}。

    否定词会翻转它作用域内极性词的极：
      "美术风格不统一"  -> {"coherence": {"messy"}}
      "美术风格很统一"  -> {"coherence": {"consistent"}}
      "音效不够丰富"    -> {"amount": {"few"}}
      "统一性不足"      -> {"coherence": {"messy"}}
    同一维度上同时读出两极时会保留两者，调用方据此判定"该维度模糊、不参与否决"。
    """
    if not text:
        return {}
    matches, _ = _scan(text)
    profile: Dict[str, Set[str]] = {}
    for i, m in enumerate(matches):
        if m["kind"] != "term":
            continue
        negated = False
        # 向前找最近的否定词（中间只允许填充成分）
        for prev in reversed(matches[:i]):
            if prev["kind"] == "term":
                break  # 中间隔了另一个极性词，否定作用域到此为止
            if prev["kind"] == "pre_neg" and _gap_is_filler(
                text, prev["end"], m["start"]
            ):
                negated = True
            break
        # 向后找紧跟的后置否定词（"统一性不足"）
        if not negated:
            for nxt in matches[i + 1 :]:
                if nxt["kind"] == "term":
                    break
                if nxt["kind"] == "post_neg" and _gap_is_filler(
                    text, m["end"], nxt["start"]
                ):
                    negated = True
                break
        for dim, pole in _TERM_INDEX[m["text"]]:
            profile.setdefault(dim, set()).add(
                _opposite_pole(dim, pole) if negated else pole
            )
    return profile


def _strip_polarity_noise(text: str) -> str:
    """去掉否定词和程度副词，用于"否定 vs 肯定"的兜底比对。"""
    out = _TOKEN_RE.sub(
        lambda m: "" if m.group(0).lower() in (_PRE_NEG_SET | _POST_NEG_SET) else m.group(0),
        text,
    )
    for tok in _FILLER_TOKENS:
        if re.fullmatch(r"[a-z0-9 '\-]+", tok):
            out = re.sub(r"\b" + re.escape(tok) + r"\b", "", out, flags=re.IGNORECASE)
        else:
            out = out.replace(tok, "")
    return re.sub(r"\s+", " ", out).strip()


# 兜底规则的触发线：去掉否定/程度词后两段文本几乎一模一样，
# 才认为它们的差别就是"那个否定词"本身。设得高（0.8）是为了不误伤
# "美术风格不统一" vs "美术风格杂乱"（去噪后只有 0.67，同向、应当合并）。
_NEGATION_ECHO_THRESHOLD = 0.8


def has_polarity_conflict(a: str, b: str) -> bool:
    """两段文本的极性/方向是否明确冲突（冲突则不许合并成同一议题）。

    判定分三步，任何一步得不出"明确冲突"就放行（返回 False）：
      1. 维度对撞：同一维度上，一边只读出 A 极、另一边只读出 B 极 -> 冲突。
      2. 同向豁免：若存在某个维度双方读出同一极，说明方向一致，直接放行；
         这条保护的是"不统一 / 杂乱"这类"一个用否定、一个用反义词"的同义表述。
      3. 否定兜底：一边有否定词、另一边没有，且去掉否定/程度词后两段几乎相同
         （如"没有手柄支持" vs "有手柄支持"）-> 冲突。这一步覆盖极性词表里
         没有的任意实义内容。
    """
    if not a or not b:
        return False

    pa, pb = polarity_profile(a), polarity_profile(b)

    agreed = False
    for dim in set(pa) & set(pb):
        sa, sb = pa[dim], pb[dim]
        # 某一边在同一维度上自带两极（"不高也不低"），方向本身就不明确，不参与否决
        if len(sa) != 1 or len(sb) != 1:
            continue
        if sa == sb:
            agreed = True
        else:
            return True  # 明确反向：一票否决

    if agreed:
        return False

    _, neg_a = _scan(a)
    _, neg_b = _scan(b)
    if neg_a != neg_b:
        if (
            lexical_similarity(_strip_polarity_noise(a), _strip_polarity_noise(b))
            >= _NEGATION_ECHO_THRESHOLD
        ):
            return True
    return False


# ===========================================================================


def _load_model():
    global _model, _model_load_failed
    if _model is not None or _model_load_failed:
        return _model
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(SEMANTIC_MODEL_NAME)
    except Exception:
        _model_load_failed = True
    return _model


class IssueSimilarity:
    """带 embedding 缓存的议题相似度比较器。

    method 为 "semantic" 或 "lexical"，报告中应记录该值以声明去重精度。

    check_polarity 默认开启：无论走语义档还是词法档，极性冲突都会否决合并
    （语义模型对反义句同样会给出高相似度，所以两档都要这道保护）。
    """

    def __init__(self, force_lexical: bool = False, check_polarity: bool = True):
        self._model = None if force_lexical else _load_model()
        self.method = "semantic" if self._model is not None else "lexical"
        self.threshold = (
            SEMANTIC_THRESHOLD if self.method == "semantic" else LEXICAL_THRESHOLD
        )
        self.check_polarity = check_polarity
        self._cache = {}

    def _embed(self, text: str):
        emb = self._cache.get(text)
        if emb is None:
            emb = self._model.encode(text, normalize_embeddings=True)
            self._cache[text] = emb
        return emb

    def similarity(self, a: str, b: str) -> float:
        """原始相似度分数。

        这里**不做**极性修正：ablation / evaluator 把它当连续距离用，
        动了会污染那些指标。否决只发生在 is_same_issue（合并决策点）。
        """
        if self.method == "lexical":
            return lexical_similarity(a, b)
        ea, eb = self._embed(a), self._embed(b)
        return float((ea * eb).sum())

    def is_same_issue(
        self, a: str, b: str, check_polarity: Optional[bool] = None
    ) -> bool:
        use_guard = self.check_polarity if check_polarity is None else check_polarity
        if use_guard and has_polarity_conflict(a, b):
            return False
        return self.similarity(a, b) > self.threshold


def get_issue_similarity(
    force_lexical: bool = False, check_polarity: bool = True
) -> IssueSimilarity:
    return IssueSimilarity(force_lexical=force_lexical, check_polarity=check_polarity)
