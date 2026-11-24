from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", env_file_encoding="utf-8", hide_input_in_errors=True)
    data_dir: str = str(ROOT / "data")
    deployment_mode: Literal["local", "demo"] = "local"
    demo_public_url: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_chat_model: str = ""
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_min_similarity: float = 0.35
    embedding_model: str = ""
    ai_json_mode: bool = True
    ai_token_parameter: str = 'max_completion_tokens'
    ai_timeout_seconds: float = 45
    ai_max_output_tokens: int = 1800
    ai_context_chars: int = 18000
    ai_retries: int = 1
    max_upload_mb: int = 30
    max_pdf_pages: int = 300
    parse_timeout_seconds: int = 60
    max_dataset_rows: int = 100000
    max_dataset_columns: int = 200
    max_xlsx_uncompressed_mb: int = 150

    @model_validator(mode="after")
    def validate_demo(self):
        if self.deployment_mode != "demo":
            return self
        value = self.demo_public_url.strip()
        try:
            parsed = urlsplit(value)
            port = parsed.port
            host = parsed.hostname
        except ValueError:
            raise ValueError("DEMO_PUBLIC_URL 必须是完整的 HTTPS 站点地址") from None
        if (parsed.scheme != "https" or not host or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or "*" in host or any(c.isspace() for c in value)):
            raise ValueError("DEMO_PUBLIC_URL 必须是无账号、路径、查询和通配符的 HTTPS origin")
        host = host.encode("idna").decode("ascii").lower()
        authority = "[" + host + "]" if ":" in host else host
        self.demo_public_url = "https://" + authority + (":" + str(port) if port and port != 443 else "")
        if self.directory() == (ROOT / "data").resolve():
            raise ValueError("公开演示必须使用独立 DATA_DIR，不能使用本机 data 目录")
        # A public demo must never call an owner's configured model service.
        self.ai_api_key = self.ai_chat_model = self.ai_base_url = ""
        self.embedding_api_key = self.embedding_model = self.embedding_base_url = ""
        return self

    def directory(self) -> Path:
        path = Path(self.data_dir)
        return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
