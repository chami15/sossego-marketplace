"""Comandos de operação da coleta.

    python -m coleta.admin orcamento        # por loja: req na última hora/dia, breaker
    python -m coleta.admin parar            # kill switch imediato (cria dados/PARAR)
    python -m coleta.admin retomar          # remove dados/PARAR
    python -m coleta.admin religar <loja>   # zera o breaker de uma loja desligada
"""

from __future__ import annotations

import sys
import time

from config import ConfigColeta, coleta_pausada
from coleta.estado import EstadoBreaker, Estado


def _hora(t: float) -> str:
    return time.strftime("%d/%m %H:%M", time.localtime(t))


def orcamento(cfg: ConfigColeta) -> None:
    estado = Estado(cfg.dir_dados / "coleta.sqlite3")
    agora = time.time()
    parado = coleta_pausada() or (cfg.dir_dados / "PARAR").exists()
    print(f"kill switch: {'LIGADO (coleta parada)' if parado else 'desligado'}\n")
    print(f"{'loja':<16}{'última h':>10}{'últimas 24h':>13}  breaker")
    for loja in estado.lojas_com_atividade():
        h = estado.enviadas_desde(loja, agora - 3600)
        d = estado.enviadas_desde(loja, agora - 86400)
        b = estado.breaker(loja)
        if b.desligada:
            br = f"DESLIGADA ({b.motivo}) -> python -m coleta.admin religar {loja}"
        elif b.pausada_ate > agora:
            br = f"aberto até {_hora(b.pausada_ate)} ({b.motivo})"
        else:
            br = "fechado"
        print(f"{loja:<16}{f'{h}/{cfg.orcamento_hora}':>10}{f'{d}/{cfg.orcamento_dia}':>13}  {br}")


def main(argv: list[str]) -> int:
    cfg = ConfigColeta.carregar()
    cmd = argv[0] if argv else "orcamento"
    parar = cfg.dir_dados / "PARAR"
    if cmd == "orcamento":
        orcamento(cfg)
    elif cmd == "parar":
        cfg.dir_dados.mkdir(parents=True, exist_ok=True)
        parar.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        print("Coleta PARADA. Nenhuma requisição sai até: python -m coleta.admin retomar")
    elif cmd == "retomar":
        parar.unlink(missing_ok=True)
        print("dados/PARAR removido." + (" Atenção: SOSSEGO_COLETA_PAUSADA=true ainda vale." if coleta_pausada() else ""))
    elif cmd == "religar" and len(argv) == 2:
        estado = Estado(cfg.dir_dados / "coleta.sqlite3")
        estado.salvar_breaker(EstadoBreaker(loja=argv[1]))
        print(f"{argv[1]} religada (breaker zerado).")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
