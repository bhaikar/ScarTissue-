import os


class Settings:
    environment = os.getenv("ENVIRONMENT", "development")
    frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    demo_mode = os.getenv("DEMO_MODE", "fake")
    llm_model = os.getenv("LLM_MODEL", "fake-diagnosis-v1")
    hindsight_bank_id = os.getenv("HINDSIGHT_BANK_ID", "scar-tissue-demo")


settings = Settings()
