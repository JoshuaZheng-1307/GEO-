"""全局配置：数据库、Redis、采集与分析参数。"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 基础设施
    DATABASE_URL: str = "postgresql+psycopg2://geo:geo123@localhost:5432/geo_monitor"
    REDIS_URL: str = "redis://localhost:6379/0"

    # 采集
    CRAWL_TIMEOUT_MS: int = 30000
    NAV_TIMEOUT_MS: int = 20000
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    HEADLESS: bool = True

    # 分析基准（对齐 SheepGEO 模板的行业平均 65 分）
    INDUSTRY_BENCHMARK: int = 65
    CONTENT_TARGET_CHARS: int = 1500  # 模板建议产品页 1500-2000 字符

    # 多生成式引擎模拟（可扩展为真实 API）
    SIMULATED_ENGINES: list = [
        "BaiduAI", "Perplexity", "ChatGLM", "Kimi", "Tongyi",
    ]

    class Config:
        env_file = ".env"
        env_prefix = "GEO_"


settings = Settings()
