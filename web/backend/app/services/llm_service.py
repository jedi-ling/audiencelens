import base64
import json
import os
from typing import Optional, Dict, Any, List

API_FORMATS = {
    "anthropic": {
        "name": "Anthropic 原生格式",
        "description": "使用 Anthropic Messages API (/v1/messages)，适用于 Claude 系列模型",
        "default_base": "https://api.anthropic.com",
        "requires_api_key": True,
    },
    "openai_compatible": {
        "name": "OpenAI 兼容格式",
        "description": "使用 OpenAI Chat Completions API (/v1/chat/completions)，适用于 GPT、DeepSeek、Ollama 等",
        "default_base": "https://api.openai.com/v1",
        "requires_api_key": True,
    },
}

API_PRESETS = [
    {
        "id": "anthropic_claude",
        "name": "Anthropic Claude",
        "api_format": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "api_base": "https://api.anthropic.com",
        "env_key": "ANTHROPIC_API_KEY",
    },
    {
        "id": "openai_gpt",
        "name": "OpenAI GPT",
        "api_format": "openai_compatible",
        "model": "gpt-4o",
        "api_base": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "api_format": "openai_compatible",
        "model": "deepseek-chat",
        "api_base": "https://api.deepseek.com",
        "env_key": "DEEPSEEK_API_KEY",
    },
    {
        "id": "ollama",
        "name": "Ollama 本地模型",
        "api_format": "openai_compatible",
        "model": "llama3",
        "api_base": "http://localhost:11434/v1",
        "env_key": "",
    },
]

REVIEW_MODE_CONFIGS = {
    "quick": {
        "persona_count": 3,
        "cross_examination": False,
        "calibration": False,
        "description": "快速初筛，5分钟内出结果",
    },
    "standard": {
        "persona_count_range": [4, 6],
        "cross_examination": True,
        "calibration": False,
        "description": "日常评审，平衡速度和深度",
    },
    "full": {
        "persona_count_range": [6, 8],
        "cross_examination": True,
        "calibration": True,
        "description": "正式评审，完整流程",
    },
}

_llm_config_cache: Dict[str, Dict] = {}


class LLMService:
    @staticmethod
    def get_formats() -> Dict[str, Any]:
        result = {}
        for fid, fconfig in API_FORMATS.items():
            result[fid] = {
                "name": fconfig["name"],
                "description": fconfig["description"],
                "default_base": fconfig["default_base"],
                "requires_api_key": fconfig["requires_api_key"],
            }
        return result

    @staticmethod
    def get_presets() -> List[Dict[str, Any]]:
        result = []
        for preset in API_PRESETS:
            result.append({
                "id": preset["id"],
                "name": preset["name"],
                "api_format": preset["api_format"],
                "model": preset["model"],
                "api_base": preset["api_base"],
                "has_env_key": bool(os.environ.get(preset.get("env_key", ""), "")),
            })
        return result

    @staticmethod
    def save_config(
        session_id: str,
        api_format: str,
        model: str,
        api_key: str = "",
        api_base: Optional[str] = None,
    ):
        if api_format not in API_FORMATS:
            raise ValueError(f"Unsupported API format: {api_format}")
        if not model.strip():
            raise ValueError("Model name cannot be empty")
        encoded_key = base64.b64encode(api_key.encode("utf-8")).decode("utf-8") if api_key else ""
        _llm_config_cache[session_id] = {
            "api_format": api_format,
            "api_key": encoded_key,
            "model": model.strip(),
            "api_base": api_base or API_FORMATS[api_format]["default_base"],
        }

    @staticmethod
    def get_config(session_id: str) -> Optional[Dict]:
        cached = _llm_config_cache.get(session_id)
        if cached:
            decoded_key = base64.b64decode(cached["api_key"].encode("utf-8")).decode("utf-8") if cached.get("api_key") else ""
            return {
                "api_format": cached["api_format"],
                "api_key": decoded_key,
                "model": cached["model"],
                "api_base": cached.get("api_base"),
            }
        for preset in API_PRESETS:
            env_key = os.environ.get(preset.get("env_key", ""), "")
            if env_key:
                return {
                    "api_format": preset["api_format"],
                    "api_key": env_key,
                    "model": preset["model"],
                    "api_base": preset["api_base"],
                }
        return None

    @staticmethod
    def _build_litellm_model(api_format: str, model: str) -> str:
        if "/" in model:
            return model
        if api_format == "anthropic":
            return f"anthropic/{model}"
        return f"openai/{model}"

    @staticmethod
    def chat(
        model: str,
        messages: List[Dict],
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_format: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        import litellm
        litellm_model = LLMService._build_litellm_model(api_format or "openai_compatible", model)
        response = litellm.completion(
            model=litellm_model,
            messages=messages,
            api_key=api_key,
            api_base=api_base,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choice = response.choices[0]
        return {
            "content": choice.message.content,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "model": response.model,
        }

    @staticmethod
    def test_connection(
        api_format: str,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> Dict[str, Any]:
        if api_format not in API_FORMATS:
            return {"connected": False, "error": f"Unknown API format: {api_format}"}
        try:
            effective_base = api_base or API_FORMATS[api_format]["default_base"]
            result = LLMService.chat(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                api_key=api_key,
                api_base=effective_base,
                api_format=api_format,
                max_tokens=10,
            )
            return {"connected": True, "model": result["model"]}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    @staticmethod
    def get_review_modes() -> List[Dict[str, Any]]:
        result = []
        for mode, config in REVIEW_MODE_CONFIGS.items():
            entry = {
                "mode": mode,
                "cross_examination": config["cross_examination"],
                "calibration": config["calibration"],
                "description": config["description"],
            }
            if "persona_count" in config:
                entry["persona_count"] = config["persona_count"]
                entry["persona_count_range"] = [config["persona_count"], config["persona_count"]]
            else:
                entry["persona_count_range"] = config["persona_count_range"]
            result.append(entry)
        return result

    @staticmethod
    def run_persona_review(
        persona: Dict[str, Any],
        task_type: str,
        artifact_bundle: Dict[str, Any],
        persona_prompt_template: str,
    ) -> Dict[str, Any]:
        from app.services import PERSONA_PROMPT_PATH
        from runner.persona_agent import render_prompt, select_model, parse_persona_output, estimate_cost

        config = LLMService.get_config("default")
        if not config:
            return {"error": "No LLM configuration available", "status": "failed"}

        artifact_summary = artifact_bundle.get("title", "")
        prompt = render_prompt(persona, task_type, artifact_summary, PERSONA_PROMPT_PATH, artifact_bundle)

        try:
            result = LLMService.chat(
                model=config["model"],
                messages=[{"role": "user", "content": prompt}],
                api_key=config["api_key"],
                api_base=config["api_base"],
                api_format=config["api_format"],
                max_tokens=4096,
                temperature=0.7,
            )
            output = parse_persona_output(result["content"])
            output["_input_tokens"] = result["input_tokens"]
            output["_output_tokens"] = result["output_tokens"]
            return output
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def run_cross_examination(
        persona_outputs: List[Dict[str, Any]],
        controversy_points: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        from app.services import CROSS_EXAM_PROMPT_PATH
        from runner.cross_exam import render_cross_exam_prompt, parse_cross_exam_output

        config = LLMService.get_config("default")
        if not config:
            return {"error": "No LLM configuration available", "cross_exam_results": []}

        try:
            cross_exam_prompt = render_cross_exam_prompt(
                controversy_points, persona_outputs, CROSS_EXAM_PROMPT_PATH
            )
            result = LLMService.chat(
                model=config["model"],
                messages=[{"role": "user", "content": cross_exam_prompt}],
                api_key=config["api_key"],
                api_base=config["api_base"],
                api_format=config["api_format"],
                max_tokens=4096,
                temperature=0.5,
            )
            cross_exam_results = parse_cross_exam_output(result["content"])
            return {
                "cross_exam_results": cross_exam_results,
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
            }
        except Exception as e:
            return {"error": str(e), "cross_exam_results": []}

    @staticmethod
    def generate_structured_report(
        persona_outputs: List[Dict[str, Any]],
        task_type: str,
        artifact_summary: str,
        cross_exam_results: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        from app.services import RULES_PATH, REPORT_TEMPLATE_PATH
        from runner.aggregator import aggregate_report, load_aggregation_rules, render_markdown_report

        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(
            persona_outputs,
            task_type,
            artifact_summary,
            rules,
            cross_exam_results,
        )
        markdown = render_markdown_report(report, REPORT_TEMPLATE_PATH)
        return {
            "report_json": report,
            "report_markdown": markdown,
        }
