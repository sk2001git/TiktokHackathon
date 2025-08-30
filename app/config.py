from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGO_URI: str    
    DIFY_EXTRACT_API_KEY: str
    DIFY_VERIFY_API_KEY: str
    DIFY_KB_API_KEY: str
    DIFY_DATASET_API_KEY: str            
    DIFY_BASE_URL: str
    DIFY_DATASET_ID: str

    class Config:
        env_file = ".env"

settings = Settings()
