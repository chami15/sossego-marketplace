"""CLI de vigia: monta o plano de coleta e (só sem --dry-run) executa.

    python -m coleta.vigiar --dry-run              # plano da lista vigia.toml, sem rede
    python -m coleta.vigiar "dixit" --categoria tabuleiro --dry-run
    python -m coleta.vigiar https://www.amazon.com.br/dp/B0XXXX --dry-run
    python -m coleta.vigiar --uma-vez              # uma rodada e sai
    python -m coleta.vigiar --continuo             # worker: rodadas espalhadas ao longo da hora
    python -m coleta.vigiar --adicionar "air fryer" --categoria eletronicos
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from config import RAIZ, ConfigColeta, coleta_pausada
from coleta.estado import Estado
from coleta.http import (
    ClienteEducado, ColetaPausada, ColetaRecusada, FalhaTransitoria, LojaDesligada,
    LojaEmPausa, MoldeQuebrado, OrcamentoEsgotado, Resposta, TransporteCurlCffi,
)
from coleta.lojas_mvp import LOJAS, loja_do_host, sem_acento
from coleta.ml_api import TokenML
from coleta.ml_api import credenciais as credenciais_ml

ARQUIVO_VIGIA = RAIZ / "vigia.toml"
ESPERA_PAUSA_S = 30  # pausado: confere a cada 30 s se já pode seguir


class WorkerDesligado(Exception):
    """dados/DESLIGADO existe: o worker sai, e a tarefa agendada não o sobe de novo."""


def desligado(dir_dados: Path) -> bool:
    return (dir_dados / "DESLIGADO").exists()
log = logging.getLogger("sossego.vigiar")


@dataclass(frozen=True)
class Tarefa:
    loja: str
    url: str
    tipo: str     # busca | produto
    termo: str | None


def ler_alvos(caminho: Path = ARQUIVO_VIGIA) -> list[dict]:
    if not caminho.exists():
        return []
    return tomllib.loads(caminho.read_text(encoding="utf-8")).get("alvo", [])


def _liberada(slug: str, lojas: list[str] | None, recon: bool) -> bool:
    l = LOJAS.get(slug)
    if l is None or l.ativa:
        return True
    # Recon pontual: só loja "em avaliação" citada explicitamente. Loja inativa
    # por bloqueio (Magalu) nunca volta por aqui.
    return recon and lojas is not None and slug in lojas and l.motivo_inativa.startswith("em avaliação")


def planejar(alvos: list[dict], lojas: list[str] | None = None, recon: bool = False) -> list[Tarefa]:
    tarefas: list[Tarefa] = []
    vistos: set[str] = set()
    for alvo in alvos:
        if "url" in alvo:
            url = alvo["url"]
            loja = loja_do_host(urlsplit(url).hostname or "")
            novas = [Tarefa(loja, url, "produto", None)]
        else:
            cat = alvo.get("categoria", "eletronicos")
            novas = [
                Tarefa(l.slug, l.url_busca(alvo["termo"]), "busca", alvo["termo"])
                for l in LOJAS.values() if cat in l.categorias
            ]
        for t in novas:
            if not _liberada(t.loja, lojas, recon):
                continue  # loja inativa não recebe nem URL direta
            if (lojas is None or t.loja in lojas) and t.url not in vistos:
                vistos.add(t.url)
                tarefas.append(t)
    return tarefas


def periodo_min(loja: str) -> int:
    return LOJAS[loja].periodo_min if loja in LOJAS else 60


def imprimir_dry_run(tarefas: list[Tarefa], cfg: ConfigColeta) -> None:
    print("DRY-RUN: nenhuma requisição foi feita.\n")
    por_loja: dict[str, list[Tarefa]] = {}
    for t in tarefas:
        por_loja.setdefault(t.loja, []).append(t)
    for loja, ts in por_loja.items():
        hosts = sorted({urlsplit(t.url).hostname for t in ts})
        verif = "" if LOJAS.get(loja) and LOJAS[loja].verificada else "  [molde de URL NÃO verificado]"
        print(f"== {loja}  (a cada {periodo_min(loja)} min){verif}")
        for h in hosts:
            print(f"   GET https://{h}/robots.txt   (1x a cada 24 h)")
        for t in ts:
            print(f"   GET {t.url}")
        print()

    print(f"{'loja':<15}{'por rodada':>11}{'rodadas/h':>11}{'req/h':>8}{'req/dia':>9}"
          f"{'limite h':>10}{'limite dia':>12}")
    total_h = total_d = 0.0
    for loja, ts in por_loja.items():
        hosts = len({urlsplit(t.url).hostname for t in ts})
        rodadas_h = 60 / periodo_min(loja)
        req_h = len(ts) * rodadas_h + hosts  # robots só na 1ª hora do dia
        req_d = len(ts) * rodadas_h * 24 + hosts
        total_h += req_h
        total_d += req_d
        alerta = "  << ACIMA DO LIMITE" if req_h > cfg.orcamento_hora or req_d > cfg.orcamento_dia else ""
        print(f"{loja:<15}{len(ts):>11}{rodadas_h:>11.1f}{req_h:>8.0f}{req_d:>9.0f}"
              f"{cfg.orcamento_hora:>10}{cfg.orcamento_dia:>12}{alerta}")
    print(f"{'TOTAL':<15}{len(tarefas):>11}{'':>11}{total_h:>8.0f}{total_d:>9.0f}")
    print("\nCada loja: 1 requisição por vez, >= 5 s (+0-3 s de jitter) entre elas,"
          " espalhadas ao longo do período.")


def validador_busca(termo: str):
    """Página de busca 'boa' é grande e menciona o termo. Página de desafio
    ou vazia não. Na dúvida abre o breaker (lado seguro)."""
    palavras = [p for p in sem_acento(termo).split() if len(p) >= 3] or [sem_acento(termo)]

    def ok(r: Resposta) -> bool:
        tipo = r.cabecalhos.get("content-type", "")
        texto = sem_acento(r.corpo[:3_000_000].decode("utf-8", errors="ignore"))
        if "json" in tipo:
            # VTEX devolve lista; ML devolve {"results": [...]} e ecoa o termo
            # em "query", então ali o termo no texto não prova nada.
            try:
                dados = json.loads(r.corpo)
            except ValueError:
                return False
            if isinstance(dados, dict):
                dados = dados.get("results") or []
            return bool(dados) and any(p in texto for p in palavras)
        if len(r.corpo) < 10_000:
            return False
        if "html" in tipo and texto.count("r$") < 3:
            # Página de busca de loja sem preço nenhum não é página de busca.
            return False
        return any(p in texto for p in palavras)

    return ok


async def executar_tarefa(cliente: ClienteEducado, t: Tarefa, token_ml: TokenML | None = None) -> str:
    try:
        validar = validador_busca(t.termo) if t.termo else None
        cab = None
        if t.loja == "mercado-livre":
            if token_ml is None:
                return "pulada: sem token do ML"
            cab = await token_ml.cabecalhos()
        res = await cliente.obter(t.url, tipo=t.tipo, validar=validar, cabecalhos=cab)
        return "cache" if res.do_cache else f"ok {res.status} {len(res.corpo) // 1024} KB"
    except ColetaPausada:
        raise
    except (LojaEmPausa, LojaDesligada, OrcamentoEsgotado) as e:
        return f"pulada: {e}"
    except MoldeQuebrado as e:
        return f"MOLDE QUEBRADO (bruto salvo): {e}"
    except (ColetaRecusada, FalhaTransitoria) as e:
        return f"falhou: {e}"


async def rodada_da_loja(cliente: ClienteEducado, loja: str, tarefas: list[Tarefa],
                         espalhar_s: float, rng: random.Random, token_ml: TokenML | None = None,
                         apos=None) -> None:
    """Espalha as tarefas ao longo de `espalhar_s`: cada uma cai num ponto
    aleatório da sua fatia. Nada de disparar tudo no minuto 00.
    `apos(loja)` roda no fim, mesmo se o breaker interromper: o que já foi
    coletado nesta rodada está no bruto e deve virar snapshot."""
    fatia = espalhar_s / max(1, len(tarefas))
    inicio = time.time()
    try:
        for i, t in enumerate(tarefas):
            alvo = inicio + i * fatia + rng.uniform(0, fatia * 0.8)
            await asyncio.sleep(max(0, alvo - time.time()))
            # Pausado: o worker fica vivo, mas nem tenta (sem log de recusa a cada tarefa).
            while True:
                if desligado(cliente.cfg.dir_dados):
                    raise WorkerDesligado
                if not cliente.pausada():
                    break
                await asyncio.sleep(ESPERA_PAUSA_S)
            b = cliente.estado.breaker(loja)
            if b.desligada or b.pausada_ate > time.time():
                log.warning(json.dumps({"evento": "rodada_interrompida", "loja": loja, "motivo": b.motivo}))
                return
            status = await executar_tarefa(cliente, t, token_ml)
            print(f"[{time.strftime('%H:%M:%S')}] {loja:<14} {status:<40} {t.url}", flush=True)
    finally:
        if apos is not None:
            await apos(loja)


async def executar(tarefas: list[Tarefa], continuo: bool) -> None:
    cfg = ConfigColeta.carregar()
    estado = Estado(cfg.dir_dados / "coleta.sqlite3")
    transporte = TransporteCurlCffi()
    cliente = ClienteEducado(estado, transporte, cfg, loja_de=loja_do_host, dir_bruto=cfg.dir_dados / "bruto",
                             estritas=frozenset({"mercado-livre"}))  # 403 com token: desliga e avisa
    token_ml = TokenML(cliente, cliente.relogio) if credenciais_ml() else None
    # Bruto → snapshots no fim de cada rodada: local, idempotente, sem rede.
    from coleta.historico import ReprocessoAposRodada
    from config import database_url

    apos = ReprocessoAposRodada(database_url(), cfg.dir_dados / "bruto")
    rng = random.Random()
    por_loja: dict[str, list[Tarefa]] = {}
    for t in tarefas:
        por_loja.setdefault(t.loja, []).append(t)

    async def ciclo(loja: str, ts: list[Tarefa]):
        await asyncio.sleep(rng.uniform(0, 120) if continuo else 0)  # lojas não começam juntas
        while True:
            periodo = periodo_min(loja) * 60
            t0 = time.time()
            ordem = ts[:]
            rng.shuffle(ordem)
            # --uma-vez: espalha só um pouco (as regras de intervalo já valem).
            await rodada_da_loja(cliente, loja, ordem, periodo * 0.9 if continuo else 0, rng, token_ml, apos)
            if not continuo:
                return
            await asyncio.sleep(max(0, periodo - (time.time() - t0)))

    batimento = cfg.dir_dados / "worker.json"
    iniciado = time.time()

    async def bater():
        # `status` decide se o worker está vivo pela idade deste arquivo.
        import os

        while True:
            batimento.write_text(json.dumps({
                "pid": os.getpid(), "modo": "continuo" if continuo else "uma-vez",
                "iniciado_em": iniciado, "batimento_em": time.time(),
                "lojas": sorted(por_loja),
            }), encoding="utf-8")
            await asyncio.sleep(60)

    pulso = asyncio.create_task(bater())
    try:
        await asyncio.gather(*(ciclo(l, ts) for l, ts in por_loja.items()))
    except ColetaPausada as e:
        print(f"PARADO pelo kill switch: {e}", flush=True)
    except WorkerDesligado:
        print("DESLIGADO (dados/DESLIGADO): encerrando.", flush=True)
    finally:
        pulso.cancel()
        batimento.unlink(missing_ok=True)
        await transporte.fechar()


def adicionar(termo_ou_url: str, categoria: str) -> None:
    if termo_ou_url.startswith("http"):
        bloco = f'\n[[alvo]]\nurl = "{termo_ou_url}"\n'
    else:
        bloco = f'\n[[alvo]]\ntermo = "{termo_ou_url}"\ncategoria = "{categoria}"\n'
    with ARQUIVO_VIGIA.open("a", encoding="utf-8") as f:
        f.write(bloco)
    print(f"adicionado a {ARQUIVO_VIGIA.name}: {termo_ou_url}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m coleta.vigiar")
    p.add_argument("alvos", nargs="*", help="termos ou URLs; vazio = vigia.toml")
    p.add_argument("--categoria", default="eletronicos")
    p.add_argument("--lojas", help="restringe a estas lojas (separadas por vírgula)")
    p.add_argument("--dry-run", action="store_true", help="mostra as URLs e totais, sem rede")
    modo = p.add_mutually_exclusive_group()
    modo.add_argument("--uma-vez", action="store_true")
    modo.add_argument("--continuo", action="store_true")
    p.add_argument("--adicionar", action="store_true", help="grava os alvos em vigia.toml")
    p.add_argument("--recon", action="store_true",
                   help="inclui lojas 'em avaliação' citadas em --lojas (só com --uma-vez ou --dry-run)")
    a = p.parse_args(argv)
    if a.recon and (a.continuo or not a.lojas):
        p.error("--recon exige --lojas e não vale para --continuo")

    if not (a.dry_run or a.adicionar) and desligado(ConfigColeta.carregar().dir_dados):
        # Sai antes de lock, log e rede. Pela tarefa agendada (--continuo), em
        # silêncio: ela tenta a cada 15 min e não deve encher o tarefa.out.
        if not a.continuo:
            print("Worker DESLIGADO (dados/DESLIGADO). Ligue com: .\\sossego.ps1 ligar")
        return 0

    if a.adicionar:
        for alvo in a.alvos:
            adicionar(alvo, a.categoria)
        return 0

    alvos = [{"url": x} if x.startswith("http") else {"termo": x, "categoria": a.categoria} for x in a.alvos]
    tarefas = planejar(alvos or ler_alvos(), a.lojas.split(",") if a.lojas else None, recon=a.recon)
    cfg = ConfigColeta.carregar()
    if a.dry_run:
        imprimir_dry_run(tarefas, cfg)
        return 0
    if not (a.uma_vez or a.continuo):
        p.error("use --dry-run, --uma-vez ou --continuo")
    if coleta_pausada():
        print("SOSSEGO_COLETA_PAUSADA=true: nada a fazer.")
        return 1

    from filelock import FileLock, Timeout

    cfg.dir_dados.mkdir(parents=True, exist_ok=True)
    # Log JSON de toda requisição vai para arquivo; o terminal mostra o resumo.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(cfg.dir_dados / "coleta.log", encoding="utf-8")])
    try:
        # Um coletor por vez na máquina: dois processos furariam o intervalo por loja.
        # --recon só toca lojas inativas (que o worker não coleta): lock próprio.
        nome_lock = f"recon-{a.lojas.replace(',', '_')}.lock" if a.recon else "coleta.lock"
        with FileLock(cfg.dir_dados / nome_lock, timeout=0):
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            asyncio.run(executar(tarefas, continuo=a.continuo))
    except Timeout:
        print("Já existe um coletor rodando (dados/coleta.lock). Saindo.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
