from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    polymarket_private_key: str = ""
    polymarket_wallet_address: str | None = None

    mode: str = "paper"
    initial_paper_balance: float = 1000.0

    move_threshold_points: int = 30
    window_1_duration: int = 30
    activation_timer: int = 210
    min_dominant_price: float = 0.55
    min_profit_buffer: float = 0.50
    pre_entry_seconds: int = 30
    max_consecutive_losses: int = 3

    log_level: str = "INFO"
    db_path: str = "./bot.db"

    class Config:
        env_file = ".env"


settings = Settings()
