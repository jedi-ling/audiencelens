"""议题相似度计算：优先使用本地语义 embedding，不可用时回退到字符串相似度。

语义档依赖 sentence-transformers（可选依赖）：
    pip install sentence-transformers
首次使用会下载 BAAI/bge-small-zh-v1.5（约 100MB），之后离线可用。
"""

from difflib import SequenceMatcher
from typing import Optional

SEMANTIC_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
SEMANTIC_THRESHOLD = 0.75
LEXICAL_THRESHOLD = 0.7

_model = None
_model_load_failed = False


def lexical_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


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
    """

    def __init__(self, force_lexical: bool = False):
        self._model = None if force_lexical else _load_model()
        self.method = "semantic" if self._model is not None else "lexical"
        self.threshold = (
            SEMANTIC_THRESHOLD if self.method == "semantic" else LEXICAL_THRESHOLD
        )
        self._cache = {}

    def _embed(self, text: str):
        emb = self._cache.get(text)
        if emb is None:
            emb = self._model.encode(text, normalize_embeddings=True)
            self._cache[text] = emb
        return emb

    def similarity(self, a: str, b: str) -> float:
        if self.method == "lexical":
            return lexical_similarity(a, b)
        ea, eb = self._embed(a), self._embed(b)
        return float((ea * eb).sum())

    def is_same_issue(self, a: str, b: str) -> bool:
        return self.similarity(a, b) > self.threshold


def get_issue_similarity(force_lexical: bool = False) -> IssueSimilarity:
    return IssueSimilarity(force_lexical=force_lexical)
