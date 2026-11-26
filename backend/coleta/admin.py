"""Comandos de operação da coleta.

    python -m coleta.admin orcamento        # por loja: req na última hora/dia, breaker
    python -m coleta.admin pausar           # worker vivo, sem requisição (cria dados/PARAR); `parar` = alias
    python -m coleta.admin retomar          # remove dados/PARAR
    python -m coleta.admin desligar         # cria dados/DESLIGADO: worker sai e a tarefa não o sobe
    python -m coleta.admin ligar            # remove dados/DESLIGADO
    (encerrar e subir o processo fica no .\sossego.ps1 desligar / ligar)
    python -m coleta.admin religar <loja>   # zera o breaker de uma loja desligada
"""

from __future__ import annotations

import sys
import time

from config import ConfigColeta, coleta_pausada
from coleta.estado import EstadoBreaker, Estado
from coleta.lojas_mvp import LOJAS


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
            br = f"aberto até {_hora(b.pausada_ate)} [{b.tipo_motivo}] ({b.motivo})"
        else:
            br = "fechado"
        print(f"{loja:<16}{f'{h}/{cfg.orcamento_hora}':>10}{f'{d}/{cfg.orcamento_dia}':>13}  {br}")


def status(cfg: ConfigColeta) -> None:
    import json

    agora = time.time()
    arq = cfg.dir_dados / "worker.json"
    if arq.exists():
        w = json.loads(arq.read_text(encoding="utf-8"))
        idade = agora - w["batimento_em"]
        vivo = idade < 180  # batimento a cada 60 s
        print(f"worker: {'VIVO' if vivo else 'SEM BATIMENTO (morto ou travado?)'}  pid {w['pid']}, "
              f"desde {_hora(w['iniciado_em'])}, último batimento há {int(idade)} s")
    else:
        print("worker: PARADO (sem dados/worker.json). Ligue com: .\\sossego.ps1 worker")
    if (cfg.dir_dados / "DESLIGADO").exists():
        print("worker: DESLIGADO (dados/DESLIGADO); a tarefa agendada sai na hora. Ligue com: .\\sossego.ps1 ligar")
    if coleta_pausada() or (cfg.dir_dados / "PARAR").exists():
        print("coleta: PAUSADA (worker vivo, nenhuma requisição). Retome com: .\\sossego.ps1 retomar")
    estado = Estado(cfg.dir_dados / "coleta.sqlite3")
    print(f"\n{'loja':<16}{'última ok':>14}{'h':>5}{'24h':>6}  situação")
    alertas = []
    for loja in estado.lojas_com_atividade():
        ok = estado.ultima_por_classe(loja, "ok")
        b = estado.breaker(loja)
        cadastro = LOJAS.get(loja)
        if cadastro and not cadastro.ativa:
            # Prioridade máxima: loja fora do worker nunca aparece como "ok".
            sit = f"INATIVA ({cadastro.motivo_inativa})"
        elif cadastro is None:
            # Só sondada (recon/detecção): nada é coletado dela.
            pausa = f"; {b.tipo_motivo} até {_hora(b.pausada_ate)}" if b.pausada_ate > agora else ""
            sit = f"fora do worker (só sondagem{pausa})"
        elif b.desligada:
            sit = f"DESLIGADA por bloqueio: {b.motivo}"
            alertas.append(f"{loja}: desligada ({b.motivo}). Religar: .\\sossego.ps1 religar {loja}")
        elif b.pausada_ate > agora and b.tipo_motivo == "molde_quebrado":
            sit = f">>> MOLDE QUEBRADO <<< pausa até {_hora(b.pausada_ate)}: {b.motivo}"
            alertas.append(f"{loja}: o PARSER/URL quebrou, não é bloqueio. Bruto salvo; corrigir molde.")
        elif b.pausada_ate > agora:
            sit = f"BLOQUEIO, pausa até {_hora(b.pausada_ate)}: {b.motivo}"
            alertas.append(f"{loja}: a loja barrou ({b.motivo}). Aguardando a pausa.")
        else:
            sit = "ok"
        print(f"{loja:<16}{_hora(ok) if ok else '-':>14}{estado.enviadas_desde(loja, agora - 3600):>5}"
              f"{estado.enviadas_desde(loja, agora - 86400):>6}  {sit}")
    if alertas:
        print("\nATENÇÃO:")
        for a in alertas:
            print(f"  - {a}")


def main(argv: list[str]) -> int:
    cfg = ConfigColeta.carregar()
    cmd = argv[0] if argv else "orcamento"
    parar = cfg.dir_dados / "PARAR"
    if cmd == "status":
        status(cfg)
    elif cmd == "orcamento":
        orcamento(cfg)
    elif cmd in ("pausar", "parar"):
        cfg.dir_dados.mkdir(parents=True, exist_ok=True)
        parar.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        print("Coleta PAUSADA. O worker segue vivo, sem requisição, até: .\\sossego.ps1 retomar")
    elif cmd == "retomar":
        parar.unlink(missing_ok=True)
        print("dados/PARAR removido." + (" Atenção: SOSSEGO_COLETA_PAUSADA=true ainda vale." if coleta_pausada() else ""))
    elif cmd == "desligar":
        cfg.dir_dados.mkdir(parents=True, exist_ok=True)
        (cfg.dir_dados / "DESLIGADO").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        print("dados/DESLIGADO criado: o worker não sobe mais até: .\\sossego.ps1 ligar")
    elif cmd == "ligar":
        (cfg.dir_dados / "DESLIGADO").unlink(missing_ok=True)
        print("dados/DESLIGADO removido.")
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
