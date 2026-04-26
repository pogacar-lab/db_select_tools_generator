import os
import secrets
from dotenv import load_dotenv

load_dotenv()


class Config:
    DB_PATH = os.environ.get("DB_PATH", "./data/sample.db")
    HISTORY_DB_PATH = os.environ.get("HISTORY_DB_PATH", "./data/history.db")
    AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "DUMMY")
    AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
    AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "")
    OPENAI_ENDPOINT = os.environ.get("OPENAI_ENDPOINT", "")
    API_LOG_DIR = os.environ.get("API_LOG_DIR", "./data/api_logs")
    # 未設定時は起動ごとにランダム生成（開発用途）。本番では .env に固定値を設定すること
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    @property
    def is_dry_run(self):
        return self.AZURE_OPENAI_API_KEY == "DUMMY"

    @property
    def is_openai_mode(self):
        return self.AZURE_OPENAI_API_KEY == "OPENAI"
