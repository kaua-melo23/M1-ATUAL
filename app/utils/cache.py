"""
Cache simples em memória com TTL (Time-To-Live).

Substitui Redis para ambientes de VPS simples.
Thread-safe via threading.Lock.
Evita re-consultas desnecessárias ao banco em dados pouco mutáveis.

Uso:
    from app.utils.cache import cache

    # Decorador
    @cache.cached(ttl=60, key="produtos_visiveis")
    def buscar_visiveis():
        ...

    # Manual
    cache.set("configs", dados, ttl=120)
    dados = cache.get("configs")
    cache.invalidar("configs")
    cache.invalidar_prefixo("produto_")
"""

import time
import threading
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SimpleCache:
    """Cache em memória com TTL e invalidação por prefixo."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            valor, expira_em = entry
            if time.monotonic() > expira_em:
                del self._store[key]
                return None
            return valor

    def set(self, key: str, valor: Any, ttl: int = 60) -> None:
        with self._lock:
            self._store[key] = (valor, time.monotonic() + ttl)

    def invalidar(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidar_prefixo(self, prefixo: str) -> None:
        """Remove todas as chaves que começam com o prefixo."""
        with self._lock:
            chaves = [k for k in self._store if k.startswith(prefixo)]
            for k in chaves:
                del self._store[k]
            if chaves:
                logger.debug("Cache: %d chaves invalidadas com prefixo '%s'", len(chaves), prefixo)

    def limpar(self) -> None:
        with self._lock:
            self._store.clear()

    def stats(self) -> dict:
        with self._lock:
            agora = time.monotonic()
            ativos = sum(1 for _, (_, exp) in self._store.items() if agora <= exp)
            return {"total_chaves": len(self._store), "chaves_ativas": ativos}

    def cached(self, ttl: int = 60, key: str | None = None):
        """
        Decorador de cache com TTL.

        @cache.cached(ttl=120, key="produtos_visiveis")
        def buscar_visiveis():
            ...
        """
        def decorator(func):
            from functools import wraps

            @wraps(func)
            def wrapper(*args, **kwargs):
                cache_key = key or f"{func.__module__}.{func.__qualname__}"
                valor = self.get(cache_key)
                if valor is not None:
                    return valor
                valor = func(*args, **kwargs)
                self.set(cache_key, valor, ttl=ttl)
                return valor

            wrapper.invalidar = lambda: self.invalidar(key or f"{func.__module__}.{func.__qualname__}")
            return wrapper

        return decorator


# Instância global — importar este objeto em qualquer módulo
cache = SimpleCache()
