import json
import time
from typing import Protocol
from urllib.parse import urlsplit
import httpx
import numpy as np

class ProviderError(ValueError): pass
class ChatProvider(Protocol):
    def generate(self, system: str, payload: dict) -> dict: ...
class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

def configured(base, model, key):
    host = urlsplit(base).hostname
    return bool(base and model and (key or host in ("localhost","127.0.0.1","::1")))

def request_json(base, key, endpoint, body, settings):
    url = base.rstrip("/") + "/" + endpoint
    if urlsplit(base).scheme not in ("https","http"): raise ProviderError("模型服务地址必须为 HTTP(S)")
    headers = {"Content-Type":"application/json"}
    if key: headers["Authorization"] = "Bearer " + key
    for attempt in range(min(max(settings.ai_retries,0),2)+1):
        try:
            with httpx.Client(timeout=settings.ai_timeout_seconds, follow_redirects=False) as client:
                response = client.post(url, headers=headers, json=body)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < min(max(settings.ai_retries,0),2):
                    time.sleep(0.4 * (attempt + 1))
                    continue
            if response.status_code >= 400:
                raise ProviderError(f"模型服务返回 HTTP {response.status_code}，请检查服务与模型配置")
            return response.json()
        except httpx.TransportError:
            if attempt < min(max(settings.ai_retries,0),2): continue
            raise ProviderError("模型请求超时或网络不可用，请稍后重试") from None
        except (ValueError, KeyError) as exc:
            if isinstance(exc, ProviderError): raise
            raise ProviderError("模型服务响应格式无效") from None

class CompatibleChatProvider:
    """Chat Completions compatible adapter; no tools or remote conversation storage."""
    def __init__(self, settings): self.settings = settings
    def generate(self, system, payload):
        settings = self.settings
        body = {"model":settings.ai_chat_model,
            "messages":[{"role":"system","content":system},
                        {"role":"user","content":json.dumps(payload,ensure_ascii=False)}],
            settings.ai_token_parameter: settings.ai_max_output_tokens}
        if settings.ai_json_mode: body["response_format"] = {"type":"json_object"}
        result = request_json(settings.ai_base_url, settings.ai_api_key, "chat/completions", body, settings)
        try:
            content = result["choices"][0]["message"]["content"].strip()
            if content.startswith(chr(96)*3):
                content = content.split("\n",1)[1].rsplit(chr(96)*3,1)[0]
            data = json.loads(content)
            if not isinstance(data, dict): raise ValueError()
            return data
        except (KeyError, ValueError, TypeError, IndexError, AttributeError):
            raise ProviderError("模型未返回有效的结构化 JSON，请重试或更换兼容模型") from None

class CompatibleEmbeddingProvider:
    def __init__(self, settings): self.settings = settings
    def embed(self, texts):
        settings = self.settings
        result = request_json(settings.embedding_base_url or settings.ai_base_url,
            settings.embedding_api_key, "embeddings", {"model":settings.embedding_model,"input":texts}, settings)
        try:
            rows = sorted(result["data"],key=lambda x:x["index"])
            if [r["index"] for r in rows] != list(range(len(texts))): raise ValueError()
            vectors = [r["embedding"] for r in rows]
            array = np.asarray(vectors, dtype=float)
            if array.ndim!=2 or array.shape[1]<1 or not np.isfinite(array).all() or (np.linalg.norm(array,axis=1)==0).any(): raise ValueError()
            return array.tolist()
        except (KeyError, ValueError, TypeError):
            raise ProviderError("向量服务返回的维度、数量或数值无效") from None
