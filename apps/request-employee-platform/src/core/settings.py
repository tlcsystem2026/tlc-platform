from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    env:str='test'; database_url:str='sqlite:///C:/TLC-BOS/data/test/request_platform_test.db'; document_root:str='C:/TLC-BOS/data/test/documents'; legal_entity_default:str='TEST-JP-01'
    model_config=SettingsConfigDict(env_file='.env',env_prefix='TLC_',extra='ignore')
@lru_cache
def get_settings(): return Settings()
