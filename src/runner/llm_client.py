"""统一 LLM 调用出口——不依赖 litellm。

litellm 在这个项目当前跑的 Python 3.8 环境装不上（它的分词器依赖 `puccinialin` 需要
Python>=3.9 且要 Rust 编译，见 web/backend/requirements.txt 里的 litellm 条目——列了但装不上，
`app/services/llm_service.py` 那套"测试连接"其实从未真正跑通过）。这里换一条更轻的路：
原生 Anthropic 走官方 SDK（已验证可装），其余提供商按 OpenAI 兼容协议直接发 HTTP 请求——
DeepSeek/Kimi/通义千问/智谱GLM/Ollama 等都遵循这个协议，不需要额外依赖。

多模态：prompt 可以是纯字符串，也可以是 OpenAI Vision 格式的内容块列表：
    [{"type": "text", "text": "..."},
     {"type": "image_url", "image_url": {"url": "data:image/png;base64,...."}}]
两条 provider 路径各自把这份内容块转换成自己认的格式。
"""

import random
import time
from typing import List, Optional, Tuple, Union

PromptContent = Union[str, List[dict]]

# 哪些 HTTP 状态值得重试。判断依据只有一条：**再发一次有可能成功吗**。
#   429 / 5xx / 408 —— 限流、服务端抖动、网关超时，重试有意义；
#   401/403（key 错、无权限）、400/422（请求本身不合法）、404（模型名不存在）、
#   402（余额不足）—— 再发一百次也是同样的错，重试只会把成本和延迟按倍数放大，
#   还会把"key 配错了"这种要立刻告诉用户的错误拖成一分钟后才报。
RETRYABLE_HTTP_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

# 连接/超时类异常的类名关键字。这里按类名而不是 isinstance 判断，是因为
# anthropic SDK 只在 _anthropic_chat 内部 import（模块顶层不依赖它），
# 顶层写 except anthropic.APIConnectionError 会把这个"可选依赖"变成硬依赖。
_TRANSIENT_EXC_NAMES = (
    "Timeout", "TimedOut", "ConnectError", "ConnectionError",
    "APIConnectionError", "ReadError", "WriteError", "RemoteProtocolError",
    "PoolTimeout", "InternalServerError", "RateLimitError", "OverloadedError",
)

# 各服务商在官网文档里给出的 OpenAI 兼容 base_url——设置页/BYOK 面板的下拉预设复用这份
# （前端 web/frontend/src/lib/types.ts、web/admin/src/lib/types.ts 各有一份手抄副本，
# 三处需要保持一致；模型名核实于 2026-07-21，见 docs/project/methodology.md）。
OPENAI_COMPATIBLE_PRESETS = {
    "openai": {"name": "OpenAI", "api_base": "https://api.openai.com/v1", "model": "gpt-5.2"},
    "deepseek": {"name": "DeepSeek", "api_base": "https://api.deepseek.com", "model": "deepseek-v4-pro"},
    "kimi": {"name": "Kimi (月之暗面)", "api_base": "https://api.moonshot.cn/v1", "model": "kimi-k3"},
    "qwen": {"name": "通义千问", "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "glm": {"name": "智谱 GLM", "api_base": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-5"},
    "ollama": {"name": "Ollama 本地模型", "api_base": "http://localhost:11434/v1", "model": "llama3"},
}

# 已知具备视觉能力的模型——多模态材料只在这些模型上才有意义，其余模型静默丢弃图片块
# （不报错阻断评审：没有视觉能力的模型至少还能读文字材料）。
# 核实日期见各前缀后的注释；漏了新模型就是本列表滞后，不是模型真没有视觉能力——
# 之前漏收 MiniMax-M3（原生多模态，训练第一步就融合文本/图像/视频，2026-07
# 官方发布确认）就是这类维护滞后，误伤了一个真正支持视觉的模型。
VISION_CAPABLE_PREFIXES = (
    "claude-", "gpt-4o", "gpt-4-turbo", "gpt-4-vision", "gpt-5", "qwen-vl", "glm-4v", "glm-5",
    "minimax",  # MiniMax-M3 起原生多模态（大小写不敏感匹配，见 supports_vision）
)


class LLMCallError(Exception):
    """LLM 调用失败。

    retryable 明确区分"再试一次可能成功"（限流/超时/5xx）与"再试也是白花钱"
    （key 错、余额不足、模型名不存在）。没有这个区分就只有两种糟糕选择：
    一律不重试（一次网络抖动就废掉一位人格），或一律重试（把 401 重试 3 次，
    延迟和账单一起翻倍）。
    """

    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def is_retryable_error(exc: BaseException) -> bool:
    """判断一个异常是否值得重试。

    三条依据依次尝试：LLMCallError 自带的 retryable 标记 → 异常对象上的
    status_code（anthropic SDK 的 APIStatusError 有这个属性）→ 类名关键字
    （连接/超时类）。都不命中就当成死错，不重试。
    """
    if isinstance(exc, LLMCallError):
        return exc.retryable

    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status in RETRYABLE_HTTP_STATUS

    name = type(exc).__name__
    return any(k in name for k in _TRANSIENT_EXC_NAMES)


def supports_vision(model: str) -> bool:
    # 各家模型名大小写不统一（"MiniMax-M3" vs 假设的 "minimax-m3"）——
    # 前缀表统一写小写，比对时把 model 也转小写，别让大小写差异导致
    # 明明在白名单里的模型被误判成不支持视觉。
    model_lower = model.lower()
    return any(model_lower.startswith(p) for p in VISION_CAPABLE_PREFIXES)


def _parse_data_uri(url: str) -> Tuple[str, str]:
    if not url.startswith("data:"):
        raise LLMCallError("图片材料必须是 data URI 格式（data:image/png;base64,...）")
    header, _, b64_data = url.partition(",")
    media_type = header[len("data:"):].split(";")[0] or "image/png"
    return media_type, b64_data


def _to_anthropic_content(content: PromptContent):
    if isinstance(content, str):
        return content
    blocks = []
    for block in content:
        if block.get("type") == "text":
            blocks.append({"type": "text", "text": block.get("text", "")})
        elif block.get("type") == "image_url":
            media_type, b64_data = _parse_data_uri(block["image_url"]["url"])
            blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64_data},
            })
    return blocks


def _anthropic_chat(
    model: str,
    content: PromptContent,
    api_key: str,
    max_tokens: int,
    temperature: float,
    api_base: Optional[str] = None,
) -> Tuple[str, int, int]:
    import anthropic

    # api_base 留空时用 SDK 默认（官方 api.anthropic.com）；填了就走第三方中转/代理——
    # cc-switch 那类工具管理的"聚合商/relay"场景，Anthropic 侧同样存在，不是 OpenAI 兼容独有。
    # 显式给个超时（openai 兼容那条路径 httpx.post 一直是 120s）：SDK 默认超时很长，
    # 一个不回应的中转会长时间占着调用它的线程（测试连接在线程池里跑，评审在 worker 线程池里跑，
    # 但线程池都是有限资源，一直占用迟早耗尽）。
    client = anthropic.Anthropic(api_key=api_key, base_url=api_base or None, timeout=120.0)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": _to_anthropic_content(content)}],
    )
    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    return text, response.usage.input_tokens, response.usage.output_tokens


def _openai_compatible_chat(
    model: str,
    content: PromptContent,
    api_key: str,
    api_base: str,
    max_tokens: int,
    temperature: float,
) -> Tuple[str, int, int]:
    import httpx

    url = api_base.rstrip("/") + "/chat/completions"
    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=120.0,
        )
    except httpx.HTTPError as e:
        # 连接失败/超时属于瞬时故障，标成可重试
        raise LLMCallError(f"请求 {url} 失败: {e}", retryable=True) from e

    if resp.status_code != 200:
        raise LLMCallError(
            f"HTTP {resp.status_code} from {url}: {resp.text[:300]}",
            status_code=resp.status_code,
            retryable=resp.status_code in RETRYABLE_HTTP_STATUS,
        )

    data = resp.json()
    try:
        choice = data["choices"][0]
        text = choice["message"]["content"] or ""
    except (KeyError, IndexError) as e:
        raise LLMCallError(f"响应格式不是标准的 OpenAI 兼容格式: {data}") from e

    usage = data.get("usage") or {}
    return text, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


def chat_completion(
    model: str,
    prompt: PromptContent,
    api_key: str,
    provider: str = "anthropic",
    api_base: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    max_retries: int = 0,
    backoff_base_seconds: float = 1.0,
    sleep: Optional[callable] = None,
) -> Tuple[str, int, int]:
    """返回 (回复文本, input_tokens, output_tokens)。provider='anthropic' 走官方 SDK，
    其余一律按 OpenAI 兼容协议处理（api_base 必填，否则默认 OpenAI 官方地址）。

    max_retries：**只对可重试错误**（限流/超时/5xx，见 is_retryable_error）重试，
    指数退避 + 抖动。默认 0 = 不重试，保持所有既有调用方的行为不变；
    引擎链路由 runner/cli.py 从 budget.yaml 的 retry 段读出来显式传进来——
    那一段配置以前全仓零读取点，是标准的"假旋钮"。
    退避里不重试 401/余额不足这类死错：那只会把成本和延迟按倍数放大，
    并且把"key 配错了"这种要立刻告诉用户的事拖慢好几秒才报出来。
    """
    if not isinstance(prompt, str) and not supports_vision(model):
        # 模型不认图，把内容块降级成纯文字，别让评审因为模型选错而整体失败
        prompt = "\n\n".join(b.get("text", "") for b in prompt if b.get("type") == "text")

    sleep = sleep or time.sleep
    attempts = max(0, int(max_retries)) + 1
    last_exc = None

    for attempt in range(attempts):
        try:
            if provider == "anthropic":
                return _anthropic_chat(
                    model, prompt, api_key, max_tokens, temperature, api_base=api_base
                )
            effective_base = api_base or OPENAI_COMPATIBLE_PRESETS["openai"]["api_base"]
            return _openai_compatible_chat(
                model, prompt, api_key, effective_base, max_tokens, temperature
            )
        except Exception as e:  # 分类后要么重试要么原样抛，不吞
            last_exc = e
            if attempt >= attempts - 1 or not is_retryable_error(e):
                raise
            # 指数退避 + 抖动：并发跑 6 个人格时若一起撞上 429，
            # 固定间隔会让它们继续同步重试、继续一起被限流。
            delay = backoff_base_seconds * (2 ** attempt)
            sleep(delay + random.uniform(0, backoff_base_seconds))

    raise last_exc  # 理论上到不了这里（循环里要么 return 要么 raise）


def test_connection(
    model: str, api_key: str, provider: str = "anthropic", api_base: Optional[str] = None
) -> dict:
    """真实发一次最小请求验证 key/模型/端点是否可用——不是格式校验，是真连接。"""
    try:
        text, _, _ = chat_completion(
            model=model, prompt="Hi", api_key=api_key, provider=provider, api_base=api_base, max_tokens=10
        )
        return {"connected": True, "model": model, "sample": text[:200]}
    except Exception as e:
        return {"connected": False, "error": str(e)}
