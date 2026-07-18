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

from typing import List, Optional, Tuple, Union

PromptContent = Union[str, List[dict]]

# 各服务商在官网文档里给出的 OpenAI 兼容 base_url——设置页/BYOK 面板的下拉预设复用这份。
OPENAI_COMPATIBLE_PRESETS = {
    "openai": {"name": "OpenAI", "api_base": "https://api.openai.com/v1", "model": "gpt-4o"},
    "deepseek": {"name": "DeepSeek", "api_base": "https://api.deepseek.com", "model": "deepseek-chat"},
    "kimi": {"name": "Kimi (月之暗面)", "api_base": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    "qwen": {"name": "通义千问", "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "glm": {"name": "智谱 GLM", "api_base": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4"},
    "ollama": {"name": "Ollama 本地模型", "api_base": "http://localhost:11434/v1", "model": "llama3"},
}

# 已知具备视觉能力的模型——多模态材料只在这些模型上才有意义，其余模型静默丢弃图片块
# （不报错阻断评审：没有视觉能力的模型至少还能读文字材料）。
VISION_CAPABLE_PREFIXES = ("claude-", "gpt-4o", "gpt-4-turbo", "gpt-4-vision", "qwen-vl", "glm-4v")


class LLMCallError(Exception):
    pass


def supports_vision(model: str) -> bool:
    return any(model.startswith(p) for p in VISION_CAPABLE_PREFIXES)


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
    model: str, content: PromptContent, api_key: str, max_tokens: int, temperature: float
) -> Tuple[str, int, int]:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
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
        raise LLMCallError(f"请求 {url} 失败: {e}") from e

    if resp.status_code != 200:
        raise LLMCallError(f"HTTP {resp.status_code} from {url}: {resp.text[:300]}")

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
) -> Tuple[str, int, int]:
    """返回 (回复文本, input_tokens, output_tokens)。provider='anthropic' 走官方 SDK，
    其余一律按 OpenAI 兼容协议处理（api_base 必填，否则默认 OpenAI 官方地址）。"""
    if not isinstance(prompt, str) and not supports_vision(model):
        # 模型不认图，把内容块降级成纯文字，别让评审因为模型选错而整体失败
        prompt = "\n\n".join(b.get("text", "") for b in prompt if b.get("type") == "text")

    if provider == "anthropic":
        return _anthropic_chat(model, prompt, api_key, max_tokens, temperature)
    effective_base = api_base or OPENAI_COMPATIBLE_PRESETS["openai"]["api_base"]
    return _openai_compatible_chat(model, prompt, api_key, effective_base, max_tokens, temperature)


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
