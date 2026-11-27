"""Taxas do Banco Central (API SGS, pública, sem chave) → taxa_referencia.

    python -m pagamento.taxas --dry-run   # o que seria pedido, sem rede
    python -m pagamento.taxas             # uma atualização agora

O worker chama `atualizar_se_preciso` a cada hora e só vai à rede se a última
atualização tiver mais de 20 h: na prática, 1 vez por dia (2 séries + o
robots.txt, que o cliente educado guarda por 24 h). Tudo pelo ClienteEducado.
Se a API cair, a calculadora usa o último valor salvo e mostra a data dele.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import psycopg

from coleta.http import Resposta

log = logging.getLogger("taxas")

# Códigos conferidos em 27/11/2026: ver docs/fontes/bcb.md.
SERIES = {"cdi_anual": 4389, "selic_meta": 432}
URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/1?formato=json"
VALIDADE = timedelta(hours=20)


def url_da(serie: str) -> str:
    return URL.format(serie=SERIES[serie])


def ler_sgs(corpo: bytes) -> tuple[date, Decimal]:
    """[{"data": "26/11/2026", "valor": "14.90"}] → (data, valor em % a.a.)."""
    try:
        (item,) = json.loads(corpo)
        valor = Decimal(str(item["valor"]).replace(",", "."))
        data = datetime.strptime(item["data"], "%d/%m/%Y").date()
    except (ValueError, KeyError, TypeError, InvalidOperation) as e:
        raise ValueError(f"resposta do SGS fora do formato esperado: {e}") from e
    if not Decimal(0) <= valor < Decimal(100):
        raise ValueError(f"taxa fora do plausível: {valor}")
    return data, valor


def _valido(r: Resposta) -> bool:
    try:
        ler_sgs(r.corpo)
        return True
    except ValueError:
        return False


async def atualizar(cliente, url_banco: str) -> dict:
    res = await cliente.obter(url_da("cdi_anual"), tipo="produto", validar=_valido)
    data, cdi = ler_sgs(res.corpo)
    # Só o CDI entra na conta; a Selic é referência. Falhou (304 do BCB, 27/11): fica nula.
    selic_data = selic = None
    try:
        res = await cliente.obter(url_da("selic_meta"), tipo="produto", validar=_valido)
        selic_data, selic = ler_sgs(res.corpo)
    except Exception as e:
        log.warning(json.dumps({"evento": "selic_falhou", "erro": f"{type(e).__name__}: {e}"}))
    with psycopg.connect(url_banco, connect_timeout=10) as c:
        c.execute("""INSERT INTO taxa_referencia (data, cdi_anual, selic_meta, selic_data, atualizado_em)
                     VALUES (%s, %s, %s, %s, now())
                     ON CONFLICT (data) DO UPDATE SET cdi_anual = EXCLUDED.cdi_anual,
                         selic_meta = EXCLUDED.selic_meta, selic_data = EXCLUDED.selic_data,
                         atualizado_em = now()""", (data, cdi, selic, selic_data))
    return {"data": data.isoformat(), "cdi_anual": str(cdi), "selic_meta": None if selic is None else str(selic)}


def precisa_atualizar(url_banco: str, agora: datetime | None = None) -> bool:
    agora = agora or datetime.now(timezone.utc)
    with psycopg.connect(url_banco, connect_timeout=10) as c:
        (ultima,) = c.execute("SELECT max(atualizado_em) FROM taxa_referencia").fetchone()
    return ultima is None or agora - ultima > VALIDADE


async def atualizar_se_preciso(cliente, url_banco: str) -> str:
    """Nunca levanta: taxa velha é melhor que worker caído."""
    try:
        if not precisa_atualizar(url_banco):
            return "em_dia"
        r = await atualizar(cliente, url_banco)
        log.info(json.dumps({"evento": "taxas", **r}))
        return "atualizada"
    except Exception as e:
        log.warning(json.dumps({"evento": "taxas_falhou", "erro": f"{type(e).__name__}: {e}"}))
        return f"falhou: {type(e).__name__}"


def ultima(conn) -> dict | None:
    from psycopg.rows import dict_row

    return conn.cursor(row_factory=dict_row).execute(
        """SELECT data, cdi_anual, selic_meta, atualizado_em FROM taxa_referencia
           ORDER BY data DESC LIMIT 1""").fetchone()


def plano() -> list[str]:
    return ["GET https://api.bcb.gov.br/robots.txt   (1x a cada 24 h)"] + [
        f"GET {url_da(s)}   ({s}, 1x por dia)" for s in SERIES]


async def _main(argv: list[str]) -> int:
    if "--dry-run" in argv:
        print("Banco Central (SGS), pelo ClienteEducado:")
        print("\n".join(f"   {linha}" for linha in plano()))
        print("   total: até 3 requisições/dia (2 séries + robots.txt)")
        return 0
    from config import ConfigColeta, database_url
    from coleta.estado import Estado
    from coleta.http import ClienteEducado, TransporteCurlCffi

    cfg = ConfigColeta.carregar()
    transporte = TransporteCurlCffi()
    try:
        cliente = ClienteEducado(Estado(cfg.dir_dados / "coleta.sqlite3"), transporte, cfg,
                                 dir_bruto=cfg.dir_dados / "bruto")
        print(json.dumps(await atualizar(cliente, database_url()), ensure_ascii=False))
    finally:
        await transporte.fechar()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
