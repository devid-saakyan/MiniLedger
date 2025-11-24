from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://miniledger_user:1234@37.1.215.158:5432/miniledger"
    app_name: str = "Mini Ledger"
    app_version: str = "1.0.0"
    debug: bool = False
    transfer_fee_percent: float = 0.1
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

