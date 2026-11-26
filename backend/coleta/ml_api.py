"""Mercado Livre pela API oficial, com token de aplicação (client credentials).

Nunca toca em lista.mercadolivre.com.br (interstício anti-robô, 26/11/2026).
Credenciais em .env: ML_CLIENT_ID e ML_CLIENT_SECRET. O token vive só em
memória; não vai para log, cache nem bruto.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus

from config import _valores

URL_TOKEN = "https://api.mercadolibre.com/oauth/token"


def credenciais() -> tuple[str, str] | None:
    v = _valores()
    cid, seg = v.get("ML_CLIENT_ID", "").strip(), v.get("ML_CLIENT_SECRET", "").strip()
    return (cid, seg) if cid and seg else None


def url_busca(termo: str, limite: int = 20) -> str:
    return f"https://api.mercadolibre.com/sites/MLB/search?q={quote_plus(termo)}&limit={limite}"


@dataclass
class TokenML:
    """Pede um token de aplicação e reaproveita até 5 min antes de expirar
    (a validade informada costuma ser de horas): 1 POST a cada várias horas."""

    cliente: object  # ClienteEducado
    relogio: object
    _token: str | None = None
    _expira_em: float = 0.0

    async def cabecalhos(self) -> dict[str, str]:
        if self._token is None or self.relogio.agora() > self._expira_em - 300:
            cred = credenciais()
            if cred is None:
                raise RuntimeError("ML_CLIENT_ID/ML_CLIENT_SECRET ausentes no .env")
            resp = await self.cliente.obter_token(URL_TOKEN, {
                "grant_type": "client_credentials", "client_id": cred[0], "client_secret": cred[1],
            })
            self._token = resp["access_token"]
            self._expira_em = self.relogio.agora() + float(resp.get("expires_in", 3600))
        return {"Authorization": f"Bearer {self._token}"}
