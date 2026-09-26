"""OpenAI 兼容 LLM 客户端（零第三方依赖，纯 urllib）。

密钥用户自持：环境变量 AMBER_LLM_API_KEY / AMBER_LLM_BASE_URL / AMBER_LLM_MODEL，
或显式传参。`local` 档（Ollama/vLLM 等 OpenAI 兼容端点）天然零外发。
移植自 relationship-companion persona_engine/providers.py 的容错纪律：
429 独立退避、瞬时错误重试、错误体截断透传。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


class ProviderError(RuntimeError):
    pass


@dataclass
class LLMConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout: int = 120
    retries: int = 3

    @classmethod
    def from_env(cls) -> LLMConfig:
        return cls(
            base_url=os.environ.get("AMBER_LLM_BASE_URL", ""),
            api_key=os.environ.get("AMBER_LLM_API_KEY", ""),
            model=os.environ.get("AMBER_LLM_MODEL", ""),
        )

    def validate(self) -> None:
        required = (("base_url", self.base_url), ("api_key", self.api_key), ("model", self.model))
        missing = [k for k, v in required if not v]
        if missing:
            raise ProviderError(f"LLM 配置缺失：{missing}（环境变量 AMBER_LLM_BASE_URL/API_KEY/MODEL 或显式传参）")


@dataclass
class ChatResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class LLMClient:
    """最小 OpenAI 兼容 chat/completions 客户端；可被 Fake 实现替换用于测试。"""

    config: LLMConfig = field(default_factory=LLMConfig.from_env)
    temperature: float = 0.3

    def chat(self, system: str, user: str, json_mode: bool = False) -> ChatResult:
        self.config.validate()
        payload: dict[str, Any] = {
            "model": self.config.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        backoff = 1
        last_err = ""
        for _attempt in range(self.config.retries):
            req = urllib.request.Request(
                self.config.base_url.rstrip("/") + "/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config.api_key}",
                    "User-Agent": "amber-core/0.1",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                usage = data.get("usage") or {}
                choices = data.get("choices") or []
                if not choices:
                    raise ProviderError(f"响应无 choices：{str(data)[:200]}")
                text = choices[0].get("message", {}).get("content", "")
                return ChatResult(
                    text=text,
                    prompt_tokens=int(usage.get("prompt_tokens") or 0),
                    completion_tokens=int(usage.get("completion_tokens") or 0),
                )
            except urllib.error.HTTPError as e:
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8", errors="replace")[:200]
                except Exception:  # noqa: BLE001 - 错误体不可读仍继续
                    pass
                last_err = f"HTTP {e.code}: {err_body}"
                if e.code == 429:
                    time.sleep(backoff * 4)
                    backoff += 4
                    continue
                if e.code >= 500:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                break  # 4xx 快速失败
            except urllib.error.URLError as e:
                last_err = f"URLError: {e.reason}"
                time.sleep(backoff)
                backoff *= 2
        raise ProviderError(f"LLM 调用失败（{self.config.retries} 次尝试）：{last_err}")


class FakeLLMClient(LLMClient):
    """测试替身：按序返回预置回复；记录调用。"""

    def __init__(self, replies: list[str]):
        super().__init__(config=LLMConfig(base_url="mock", api_key="mock", model="mock"))
        self.replies = list(replies)
        self.calls: list[dict[str, str]] = []

    def chat(self, system: str, user: str, json_mode: bool = False) -> ChatResult:
        self.calls.append({"system": system, "user": user})
        if not self.replies:
            raise ProviderError("FakeLLMClient 回复已耗尽")
        return ChatResult(text=self.replies.pop(0), prompt_tokens=10, completion_tokens=20)
