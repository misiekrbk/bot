# config.py
import os
from pydantic import BaseModel, validator, Field
from dotenv import load_dotenv

load_dotenv()

class BotConfig(BaseModel):
    mode: str = Field(default="test", description="Tryb pracy: 'test' lub 'prod'")
    simulation_mode: bool = Field(default=True, description="Czy działać w trybie symulacyjnym")
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""
    comment_limit: int = 100
    analysis_interval: int = 3600
    max_trade_usd: float = 5000.0
    risk_tolerance: float = 0.15
    enable_news: bool = True
    api_rate_limit: int = 10
    api_rate_window: int = 5
    cryptopanic_api_key: str = ""
    reddit_timeout: int = 30
    news_weight: float = 0.2

    @validator('telegram_chat_id')
    def validate_chat_id(cls, v):
        if v and not v.lstrip('-').isdigit():
            raise ValueError("Nieprawidłowy Chat ID")
        return v

    @validator('mode')
    def validate_mode(cls, v):
        if v not in ["test", "prod"]:
            raise ValueError("Nieprawidłowy tryb pracy. Dopuszczalne wartości: 'test', 'prod'")
        return v

    @property
    def binance_api_key(self):
        return os.getenv("TESTNET_API_KEY") if self.mode == "test" else os.getenv("BINANCE_API_KEY")

    @property
    def binance_api_secret(self):
        return os.getenv("TESTNET_API_SECRET") if self.mode == "test" else os.getenv("BINANCE_API_SECRET")

def load_config() -> BotConfig:
    """Zwraca instancję konfiguracji z domyślnymi wartościami."""
    return BotConfig()