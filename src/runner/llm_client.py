"""统一 LLM 调用出口——不依赖 litellm。

历史：这条"不用 litellm、自己手搓两条 provider 路径"的路线最初是被开发机的
Python 3.8 逼出来的（litellm 的分词器依赖要 >=3.9 且需 Rust 编译）。2026-09 起项目
统一到 3.11（pyproject requires-python，与生产 Dockerfile 一致），这个约束已经不存在，
但**没有理由换回 litellm**：现在两条路径各只有几十行、无额外依赖、按需引入 SDK，
而且 Prompt Caching 的 cache_control / 强制工具调用的结构化输出都是在这里直接对着
官方参数写的，中间再垫一层抽象只会把这些能力藏起来。
原生 Anthropic 走官方 SDK，其余提供商按 OpenAI 兼容协议直接发 HTTP 请求——
DeepSeek/Kimi/通义千问/智谱GLM/Ollama 等都遵循这个协议，不需要额外依赖。

多模态：prompt 可以是纯字符串，也可以是 OpenAI Vision 格式的内容块列表：
    [{"type": "text", "text": "..."},
     {"type": "image_url", "image_url": {"url": "data:image/png;base64,...."}}]
两条 provider 路径各自把这份内容块转换成自己认的格式。
"""

import json
import random
import time
from typing import List, Optional, Tuple, Union

PromptContent = Union[str, List[dict]]

# 结构化输出走"定义一个工具让模型调用"这条路，而不是较新的 output_format 参数。
# 理由**不再是**"默认模型太老、不支持 output_format"——budget.yaml 的 default_model
# 已经是 claude-sonnet-5。真正的、今天仍然成立的理由是：**本仓库的模型 ID 是自由
# 文本**（BYOK 用户自己填、后台可配第三方 OpenAI 兼容中转、管理员可覆盖），谁也
# 保证不了跑起来的那个模型认 output_format；而"定义工具 + 模型回一个 tool_use 块"
# 是从第一代 Claude 到今天每一代都在、且中转普遍照抄的老参数。
# 模型的回复是一个已按 input_schema 约束好的 tool_use 块，拿到的 input 天然是
# 合法 JSON——不需要再从散文里用正则把 JSON 抠出来。
# 注意：**强制** tool_choice 本身已经在部分新模型上被移除，见 _NO_FORCED_TOOL_FAMILIES。
STRUCTURED_OUTPUT_TOOL_NAME = "submit_review"

# 已移除"强制工具调用"的模型家族：对它们传 tool_choice={"type":"tool"} 或
# {"type":"any"} 会直接 400（Claude Fable 5.1 / Mythos 5.1 起），而 400 是不可重试
# 的死错，等于整次评审全灭。
# 这里按**模型家族子串**匹配而不是精确 ID：模型 ID 是自由文本（带不带日期后缀、
# 带不带 us.anthropic. 之类的供应商前缀、BYOK 手填的拼法都不一样），精确列表必漏。
# 宁可多匹配几个——命中只是退回 tool_choice="auto" 再在提示词里点名要它调这个
# 工具，对本来支持强制的模型也完全合法，代价仅仅是少一层硬约束。
_NO_FORCED_TOOL_FAMILIES = ("fable", "mythos")

# 退回 auto 时补进提示词的一句话：没有强制约束，就得明着让模型交卷到工具里，
# 否则它很可能直接写一段散文，白跑一次付费调用。
_FORCED_TOOL_FALLBACK_INSTRUCTION = (
    "\n\n[OUTPUT RULES] 你必须通过调用 `" + STRUCTURED_OUTPUT_TOOL_NAME + "` 工具来提交结果，"
    "不要用普通文本作答，也不要在工具调用之外另写解释。"
)


def _supports_forced_tool_choice(model: str) -> bool:
    model_lower = (model or "").lower()
    return not any(family in model_lower for family in _NO_FORCED_TOOL_FAMILIES)

# JSON Schema 里这几个键只对校验器有意义，Anthropic 的 input_schema 不认，剔掉。
_SCHEMA_KEYS_TO_STRIP = ("$schema", "$id")


def _tool_input_schema(json_schema: dict) -> dict:
    return {k: v for k, v in json_schema.items() if k not in _SCHEMA_KEYS_TO_STRIP}

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


def _append_text_instruction(content: PromptContent, extra: str) -> PromptContent:
    """在提示词末尾追加一段纯文字。内容块列表时追加一个 text 块（不能直接字符串
    相加——多模态材料就是列表形状）。"""
    if isinstance(content, str):
        return content + extra
    return list(content) + [{"type": "text", "text": extra}]


def _anthropic_chat(
    model: str,
    content: PromptContent,
    api_key: str,
    max_tokens: int,
    temperature: Optional[float] = None,
    api_base: Optional[str] = None,
    system: Optional[str] = None,
    json_schema: Optional[dict] = None,
    usage_details: Optional[dict] = None,
) -> Tuple[str, int, int]:
    import anthropic

    # api_base 留空时用 SDK 默认（官方 api.anthropic.com）；填了就走第三方中转/代理——
    # cc-switch 那类工具管理的"聚合商/relay"场景，Anthropic 侧同样存在，不是 OpenAI 兼容独有。
    # 显式给个超时（openai 兼容那条路径 httpx.post 一直是 120s）：SDK 默认超时很长，
    # 一个不回应的中转会长时间占着调用它的线程（测试连接在线程池里跑，评审在 worker 线程池里跑，
    # 但线程池都是有限资源，一直占用迟早耗尽）。
    client = anthropic.Anthropic(api_key=api_key, base_url=api_base or None, timeout=120.0)

    # 强制工具调用在 Fable/Mythos 这代模型上已被移除，命中就退回 auto 并把
    # "必须调这个工具"写进提示词（见 _NO_FORCED_TOOL_FAMILIES）。
    forced_tool_choice = bool(json_schema) and _supports_forced_tool_choice(model)
    if json_schema and not forced_tool_choice:
        content = _append_text_instruction(content, _FORCED_TOOL_FALLBACK_INSTRUCTION)

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": _to_anthropic_content(content)}],
    }
    if temperature is not None:
        # temperature 只在调用方**明确指定**时才发出去，见 chat_completion 的形参注释：
        # Sonnet 5 / Opus 5 已移除采样参数，传任何非默认值都是 400。
        kwargs["temperature"] = temperature
    if system:
        # cache_control 打在 system 块上：同一次评审里 N 位人格的 system 逐字相同
        # （见 persona_agent.py::render_prompt_split），第 2 次起命中缓存只按
        # 全价的 10% 计费。system 参数只接受纯文本块，图片必须留在 messages 里
        # （见调用方 run_single_persona 的拆分）。
        kwargs["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    if json_schema:
        # 让模型通过这个工具"交卷"：回复里是一个 input 已按 schema 约束的
        # tool_use 块，不再有"模型写了段散文/JSON 被截断/裹在 ```json 里"这些
        # 解析失败再整次重发的情况。见文件头 STRUCTURED_OUTPUT_TOOL_NAME 的注释。
        # 工具定义本身对所有模型都发；只有 tool_choice 是否"强制"要看模型家族。
        kwargs["tools"] = [{
            "name": STRUCTURED_OUTPUT_TOOL_NAME,
            "description": "提交你的评审结果。字段含义见提示词里的输出骨架。",
            "input_schema": _tool_input_schema(json_schema),
        }]
        kwargs["tool_choice"] = (
            {"type": "tool", "name": STRUCTURED_OUTPUT_TOOL_NAME}
            if forced_tool_choice
            else {"type": "auto"}
        )
    response = client.messages.create(**kwargs)

    text = None
    if json_schema:
        # stop_reason 必须在取 tool_use 块**之前**看一眼，这两种结束方式都会伪装成成功：
        #   max_tokens —— API 仍然返回一个结构上能解析、但内容被截断的 tool_use
        #     （字段缺失、字符串切一半）。json.dumps 出来的东西下游 parse/validate
        #     一路畅通，于是半份评审被当成完整结论进报告、进账单。
        #   refusal   —— 压根没有 tool_use 块，这里会静默落到下面的"拼接文本"分支
        #     拿到空串，再被当成 schema 解析失败白白重试 3 次（每次都是真金白银）。
        # 两者都不是"再发一次就会好"的错，标成不可重试直接进失败路径，
        # 让报告如实显示这位人格没有完成，而不是端上一份残缺品。
        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "max_tokens":
            raise LLMCallError(
                f"模型 {model} 的结构化输出被 max_tokens（上限 {max_tokens}）**截断**，"
                "拿到的是残缺的评审结果，按失败处理（请调大 max_tokens 后重跑）",
                retryable=False,
            )
        if stop_reason == "refusal":
            raise LLMCallError(
                f"模型 {model} **拒绝作答**（stop_reason=refusal），本次没有产出任何评审内容",
                retryable=False,
            )
        tool_block = next(
            (b for b in response.content if getattr(b, "type", None) == "tool_use"), None
        )
        if tool_block is not None:
            # 序列化成 JSON 字符串再交出去，而不是改返回值形状：下游
            # parse_persona_output 的最后一条兜底就是裸 json.loads，直接命中，
            # 所有调用方和既有测试一个字都不用动。
            text = json.dumps(tool_block.input, ensure_ascii=False)
    if text is None:
        # 没要求结构化输出，或（理论上不该发生）强制了工具模型仍没调：退回文本，
        # 让下游按老路子解析并如实报"无法解析"，不在这里编一个空结果。
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
    usage = response.usage
    # usage.input_tokens 在打了 cache_control 之后只统计**没命中缓存的新增部分**，
    # 缓存读写各自单独记账。这里返回三者之和，即**真实输入 token 总数**。
    #
    # 不变式（别再改回去了）：返回的 input_tokens 必须是真实 token 数，而算出来的
    # 钱必须仍然带缓存折扣。这两件事以前被合并成一个数——把 0.1x/1.25x 的**计费
    # 倍率**直接折进返回值，账确实对，但 web 后端是把这个数当**token 用量**落库的
    # （终身 token 上限、后台用量面板都读它），于是命中缓存的 1000 个 token 在用量
    # 统计里变成了 100 个。现在折扣挪到算钱那一步（persona_agent.estimate_cost 的
    # cache_breakdown 参数），明细通过 usage_details 交给调用方。
    cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    if usage_details is not None:
        usage_details["uncached_input_tokens"] = usage.input_tokens
        usage_details["cache_creation_input_tokens"] = cache_creation
        usage_details["cache_read_input_tokens"] = cache_read
    return text, usage.input_tokens + cache_creation + cache_read, usage.output_tokens


def _openai_compatible_chat(
    model: str,
    content: PromptContent,
    api_key: str,
    api_base: str,
    max_tokens: int,
    temperature: Optional[float] = None,
    system: Optional[str] = None,
    json_schema: Optional[dict] = None,
) -> Tuple[str, int, int]:
    import httpx

    # 共享前缀放进单独的 system 消息、摆在消息列表最前面：DeepSeek/Kimi/通义千问等
    # OpenAI 兼容服务商大多对重复的前缀 token 有隐式缓存折扣（不需要任何 cache_control
    # 字段，纯靠"这段 token 跟上次请求逐字重复"命中），但前提是它必须真的排在最前——
    # 混进用户消息里或者顺序调换，等于让每次请求的开头都不一样，缓存永远 miss。
    # 这些服务商的计费口径已经把折扣直接算进返回的 usage.prompt_tokens 里，
    # 不需要像 Anthropic 那样在这一层做换算。
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": content})

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if temperature is not None:
        # 同 Anthropic 路径：不指定就不发这个字段，让每个模型用自己的默认采样
        body["temperature"] = temperature
    if json_schema:
        # OpenAI 兼容协议里各家对"按 schema 约束"的支持参差不齐（有的叫 json_schema、
        # 有的只认 json_object、有的干脆不认），这里只要最大公约数 json_object：
        # 它保证回来的是**合法 JSON**（不是散文、不裹 ```json、括号不缺），这已经
        # 覆盖了绝大多数解析失败；字段是否齐全仍交给下游 validate_output 把关。
        # 注意：OpenAI/DeepSeek 都要求启用它时提示词里得出现 "JSON" 一词，
        # persona-prompt-shared.md 的 [OUTPUT RULES] 一直有。
        body["response_format"] = {"type": "json_object"}

    url = api_base.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        resp = httpx.post(url, headers=headers, json=body, timeout=120.0)
        if resp.status_code == 400 and "response_format" in body:
            # 个别服务商/本地模型（老版本 Ollama、某些中转）不认 response_format，
            # 会以 400 拒收整个请求。这不是用户的错也不是模型的错，退回不带它的
            # 老请求再发一次，让评审继续跑（解析仍走下游的老兜底）。只多发这一次，
            # 且仅限 400——401/429/5xx 各有各的含义，不在这里混着处理。
            # 另起一个 dict 而不是就地 pop：原 body 可能已被日志/调用记录引用，
            # 就地改会让"第一次到底发了什么"这条记录也跟着失真。
            body = {k: v for k, v in body.items() if k != "response_format"}
            resp = httpx.post(url, headers=headers, json=body, timeout=120.0)
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
    # temperature 默认 None = **整个字段都不发出去**，每个模型用自己的默认采样。
    # 以前默认 0.7 且无条件塞进请求体，在 Claude Sonnet 5 / Opus 5 上是致命的：
    # 这两代模型移除了采样参数，temperature/top_p/top_k 只要不是默认值就返回
    # HTTP 400，而 400 被 is_retryable_error 正确地判为不可重试——于是每一位人格
    # 的调用都**永久失败**，整次评审全灭。它们又恰好是 budget.yaml 现在的
    # default_model / premium_model。只有明确知道目标模型认这个参数的调用方才传它。
    temperature: Optional[float] = None,
    max_retries: int = 0,
    backoff_base_seconds: float = 1.0,
    sleep: Optional[callable] = None,
    system: Optional[str] = None,
    json_schema: Optional[dict] = None,
    usage_details: Optional[dict] = None,
) -> Tuple[str, int, int]:
    """返回 (回复文本, input_tokens, output_tokens)。provider='anthropic' 走官方 SDK，
    其余一律按 OpenAI 兼容协议处理（api_base 必填，否则默认 OpenAI 官方地址）。

    system：同一次评审里对所有人格逐字相同的共享前缀（见 persona_agent.py::
    render_prompt_split）。不传 = 老行为完全不变（单条 user 消息，无缓存）。
    传了：Anthropic 路径打 cache_control 走 Prompt Caching；OpenAI 兼容路径
    把它放进消息列表最前面的 system 消息，吃第三方服务商的隐式前缀缓存折扣。

    json_schema：要求模型按这份 JSON Schema 结构化输出。不传 = 老行为（模型自由
    发挥，下游用正则从文本里抠 JSON）。传了：Anthropic 路径强制调用一个以它为
    input_schema 的工具，回复必然是合法 JSON；OpenAI 兼容路径开 response_format=
    json_object（各家的最大公约数，只保证合法 JSON 不保证字段齐全）。两条路径
    返回的仍是 JSON **字符串**，下游解析入口不变。

    max_retries：**只对可重试错误**（限流/超时/5xx，见 is_retryable_error）重试，
    指数退避 + 抖动。默认 0 = 不重试，保持所有既有调用方的行为不变；
    引擎链路由 runner/cli.py 从 budget.yaml 的 retry 段读出来显式传进来——
    那一段配置以前全仓零读取点，是标准的"假旋钮"。
    退避里不重试 401/余额不足这类死错：那只会把成本和延迟按倍数放大，
    并且把"key 配错了"这种要立刻告诉用户的事拖慢好几秒才报出来。

    usage_details：传一个空 dict 进来，Anthropic 路径会把本次调用的缓存明细
    （uncached / cache_creation / cache_read input tokens）写进去。返回的
    input_tokens 始终是**真实 token 总数**，缓存折扣由算钱那一层
    （persona_agent.estimate_cost 的 cache_breakdown 参数）按这份明细折算。
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
                    model, prompt, api_key, max_tokens, temperature,
                    api_base=api_base, system=system, json_schema=json_schema,
                    usage_details=usage_details,
                )
            effective_base = api_base or OPENAI_COMPATIBLE_PRESETS["openai"]["api_base"]
            return _openai_compatible_chat(
                model, prompt, api_key, effective_base, max_tokens, temperature,
                system=system, json_schema=json_schema,
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
