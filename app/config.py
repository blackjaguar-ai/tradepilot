"""Configuración central de TradePilot.

Todas las credenciales y ajustes se leen desde variables de entorno (o .env
en local). Un solo punto de verdad: si algo falta, revienta aquí y no a mitad
de un flujo del agente.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Qwen ---
    dashscope_api_key: str
    qwen_base_url: str  # sin default: depende del Workspace ID de cada cuenta, ver .env.example
    qwen_model_fast: str = "qwen-flash"   # reemplaza a qwen-turbo (deprecado por Alibaba)
    qwen_model_smart: str = "qwen-plus"   # balance costo/calidad recomendado por Alibaba
    # Nota: el free quota de Model Studio es 1M tokens POR MODELO (90 días, solo Singapore).
    # Cambiar temporalmente qwen_model_smart a "qwen3.7-max" para la demo grabada del hero
    # flow consume de SU PROPIO pool separado, no toca el de qwen-plus.

    # --- Tablestore ---
    tablestore_endpoint: str
    tablestore_instance: str
    tablestore_access_key_id: str
    tablestore_access_key_secret: str

    # --- Región ---
    aliyun_region: str = "ap-southeast-1"


@lru_cache
def get_settings() -> Settings:
    """Devuelve la config cacheada. Úsala en vez de instanciar Settings()."""
    return Settings()
