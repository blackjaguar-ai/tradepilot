"""Cliente Qwen vía endpoint OpenAI-compatible de DashScope.

Dos modelos por diseño de costos:
  - fast  (qwen-turbo): clasificación de intención, extracción. Alto volumen.
  - smart (qwen-plus/max): redacción y negociación. Solo el output final.

Regla de disciplina: no llames al modelo smart para tareas que el fast resuelve.
"""
from openai import OpenAI

from app.config import get_settings


class QwenClient:
    def __init__(self) -> None:
        s = get_settings()
        self._client = OpenAI(api_key=s.dashscope_api_key, base_url=s.qwen_base_url)
        self._model_fast = s.qwen_model_fast
        self._model_smart = s.qwen_model_smart

    def fast(self, messages: list[dict], **kwargs) -> str:
        """Modelo barato. Para clasificar/extraer. Devuelve el texto plano."""
        resp = self._client.chat.completions.create(
            model=self._model_fast, messages=messages, **kwargs
        )
        return resp.choices[0].message.content or ""

    def smart(self, messages: list[dict], **kwargs) -> str:
        """Modelo caro. Solo para el output final (negociación/redacción)."""
        resp = self._client.chat.completions.create(
            model=self._model_smart, messages=messages, **kwargs
        )
        return resp.choices[0].message.content or ""

    def raw(self, model: str, messages: list[dict], **kwargs):
        """Acceso crudo al SDK cuando necesites tools/function-calling completo."""
        return self._client.chat.completions.create(
            model=model, messages=messages, **kwargs
        )


# Instancia perezosa reutilizable
_qwen: QwenClient | None = None


def get_qwen() -> QwenClient:
    global _qwen
    if _qwen is None:
        _qwen = QwenClient()
    return _qwen
