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


def ultima_vez_anuncios(url_banco: str, produtos: list[dict]) -> dict[tuple[str, str], float]:
    """Última vez que cada anúncio dos grupos [[produto]] apareceu numa busca
    (anuncio.ultima_coleta_em anda a cada aparição, mesmo sem snapshot novo). Só leitura."""
    import psycopg

    pares = {(a["loja"], a["id"]) for p in produtos for a in p["anuncios"]}
    with psycopg.connect(url_banco, connect_timeout=3) as c:
        linhas = c.execute(
            "SELECT l.slug, a.id_externo, a.ultima_coleta_em FROM anuncio a JOIN loja l ON l.id = a.loja_id"
            " WHERE l.slug = ANY(%s) AND a.id_externo = ANY(%s)",
            (sorted({l for l, _ in pares}), sorted({i for _, i in pares}))).fetchall()
    return {(l, i): t.timestamp() for l, i, t in linhas if (l, i) in pares}


def linhas_grupos(produtos: list[dict], visto: dict[tuple[str, str], float],
                  ultima_ok: dict[str, float | None], agora: float) -> tuple[list[str], list[str]]:
    """Por grupo, a última aparição de cada anúncio na busca. Sumido = a loja seguiu
    coletando ok por mais de 2 períodos depois da última aparição. Sem coleta da loja
    (worker parado, loja inativa) não é sumiço: a busca nem rodou."""
    linhas: list[str] = []
    alertas: list[str] = []
    for p in produtos:
        linhas.append(p["nome"] + (" (edição a confirmar)" if p.get("edicao_a_confirmar") else ""))
        for a in p["anuncios"]:
            loja, id_ = a["loja"], a["id"]
            cad = LOJAS[loja]
            v = visto.get((loja, id_))
            ok = ultima_ok.get(loja)
            periodo = cad.periodo_min * 60
            if not cad.ativa:
                sit = "loja inativa"
            elif v is None:
                sit = ">>> nunca visto na busca <<<"
                alertas.append(f"{loja} {id_} ({p['nome']}): nunca apareceu na busca. id certo na vigia.toml?")
            elif ok is not None and ok - v > 2 * periodo:
                n = int((ok - v) // periodo)
                sit = f">>> SUMIU DA BUSCA <<< ({n} rodadas sem aparecer)"
                alertas.append(f"{loja} {id_} ({p['nome']}): fora da busca há {n} rodadas. Saiu do topo ou do catálogo?")
            else:
                sit = "ok"
            linhas.append(f"  {loja:<12}{id_:<14}{_hora(v) if v else '-':>14}  {sit}")
    return linhas, alertas


def situacao_loja(loja: str, estado: Estado, agora: float) -> tuple[str, str, str | None]:
    """(código, texto, alerta) da loja. Usado pelo status e pela /api/v1/saude:
    a regra de "loja quebrada aparece, não some" fica num lugar só."""
    ok = estado.ultima_por_classe(loja, "ok")
    b = estado.breaker(loja)
    cadastro = LOJAS.get(loja)
    if cadastro and not cadastro.ativa:
        # Prioridade máxima: loja fora do worker nunca aparece como "ok".
        return "inativa", f"INATIVA ({cadastro.motivo_inativa})", None
    if cadastro is None:
        # Só sondada (recon/detecção): nada é coletado dela.
        pausa = f"; {b.tipo_motivo} até {_hora(b.pausada_ate)}" if b.pausada_ate > agora else ""
        return "fora_do_worker", f"fora do worker (só sondagem{pausa})", None
    if b.desligada:
        return ("desligada", f"DESLIGADA por bloqueio: {b.motivo}",
                f"{loja}: desligada ({b.motivo}). Religar: .\\sossego.ps1 religar {loja}")
    if b.pausada_ate > agora and b.tipo_motivo == "molde_quebrado":
        return ("molde_quebrado", f">>> MOLDE QUEBRADO <<< pausa até {_hora(b.pausada_ate)}: {b.motivo}",
                f"{loja}: o PARSER/URL quebrou, não é bloqueio. Bruto salvo; corrigir molde.")
    if b.pausada_ate > agora:
        return ("bloqueio", f"BLOQUEIO, pausa até {_hora(b.pausada_ate)}: {b.motivo}",
                f"{loja}: a loja barrou ({b.motivo}). Aguardando a pausa.")
    if ok is None or agora - ok > 2 * cadastro.periodo_min * 60:
        # Sem bloqueio, mas sem dado: worker ou máquina parados. "ok" aqui mentiria.
        desde = f"última ok há {(agora - ok) / 3600:.0f} h" if ok else "nenhuma coleta ok"
        return ("atrasada", f"ATRASADA ({desde}; período {cadastro.periodo_min} min)",
                f"{loja}: {desde}. Worker vivo? Máquina ficou desligada/dormindo?")
    return "ok", "ok", None


def status(cfg: ConfigColeta, produtos: list[dict] | None = None, url_banco: str | None = None) -> None:
    import json

    agora = time.time()
    arq = cfg.dir_dados / "worker.json"
    if arq.exists():
        w = json.loads(arq.read_text(encoding="utf-8"))
        idade = agora - w["batimento_em"]
        vivo = idade < 180  # batimento a cada 60 s
        print(f"worker: {'VIVO' if vivo else 'SEM BATIMENTO (morto ou travado?)'}  pid {w['pid']}, "
              f"desde {_hora(w['iniciado_em'])}, último batimento há {int(idade)} s")
    elif not (cfg.dir_dados / "DESLIGADO").exists():  # desligado: a linha abaixo já diz como ligar
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
        _, sit, alerta = situacao_loja(loja, estado, agora)
        if alerta:
            alertas.append(alerta)
        print(f"{loja:<16}{_hora(ok) if ok else '-':>14}{estado.enviadas_desde(loja, agora - 3600):>5}"
              f"{estado.enviadas_desde(loja, agora - 86400):>6}  {sit}")
    if produtos:
        print(f"\n{'produto / loja':<26}{'última vez':>14}  situação")
        try:
            visto = ultima_vez_anuncios(url_banco, produtos)
        except Exception as e:  # banco fora do ar não pode derrubar o status
            print(f"  (banco indisponível: {type(e).__name__}; grupos sem dado)")
        else:
            ultima_ok = {a["loja"]: estado.ultima_por_classe(a["loja"], "ok")
                         for p in produtos for a in p["anuncios"]}
            linhas, extra = linhas_grupos(produtos, visto, ultima_ok, agora)
            print("\n".join(linhas))
            alertas += extra
    if alertas:
        print("\nATENÇÃO:")
        for a in alertas:
            print(f"  - {a}")


def main(argv: list[str]) -> int:
    cfg = ConfigColeta.carregar()
    cmd = argv[0] if argv else "orcamento"
    parar = cfg.dir_dados / "PARAR"
    if cmd == "status":
        from config import database_url
        from coleta.vigiar import ler_produtos

        status(cfg, ler_produtos(), database_url())
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
