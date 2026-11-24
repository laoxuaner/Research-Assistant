from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", env_file_encoding="utf-8")
    data_dir: str = str(ROOT / "data")
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

    def directory(self) -> Path:
        path = Path(self.data_dir)
        return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
