"""API do Sossego (/api/v1). Só lê e grava o banco: nenhuma rota faz
requisição a loja. Coleta continua sendo do worker, com o cliente educado.

    uvicorn api.app:app --port 8000      (ou .\\sossego.ps1 api)
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from api import modelos as m
from db.consultas import consultas
from matching.normalizar import normalizar, termos_busca
from coleta.lojas_mvp import sem_acento

Q = consultas("api")
SP = ZoneInfo("America/Sao_Paulo")
PERIODOS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30), "tudo": None}


def _conn(request: Request):
    with request.app.state.pool.connection() as c:
        yield c


Conn = Depends(_conn)


# ---------- cards (a peça que busca, início, parecidos e quedas reusam) ----------

def _pct(agora: Decimal, antes: Decimal) -> Decimal:
    return ((agora / antes - 1) * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)


def cards(conn, ids: list[int], lojas: list[str] | None = None) -> dict[int, m.Card]:
    if not ids:
        return {}
    hoje = datetime.now(SP).date()
    out = {}
    for r in conn.execute(Q["cards"], {"ids": ids, "lojas": lojas}):
        tem_ref = r["ref_preco"] is not None and r["ref_dia"] < hoje
        out[r["id"]] = m.Card(
            **{k: v for k, v in r.items() if k not in ("ref_preco", "ref_dia")},
            variacao_pct=_pct(r["menor_preco"], r["ref_preco"]) if tem_ref else None,
            variacao_desde=r["ref_dia"] if tem_ref else None,
        )
    return out


def _na_ordem(ids: list[int], achados: dict[int, m.Card]) -> list[m.Card]:
    return [achados[i] for i in ids if i in achados]


_DURO = re.compile(r"^(?:ps[345]|ns[12]|n3ds|\d+(?:gb|tb))$")


def _buscar(conn, q: str) -> list[int]:
    # Quem busca escreve no plural ("jogos ps5"); no título, "jogos" é de "para jogos".
    q = re.sub(r"\bjogos\b", "jogo", sem_acento(q))
    termos = (termos_busca(q) or q).split()
    duros = [t for t in termos if _DURO.match(t)]
    resto = [t for t in termos if t not in duros]
    p = {"q": " ".join(termos), "resto": " ".join(resto), "duros": [f"%{t}%" for t in duros],
         "padroes": [f"%{t}%" for t in resto]}
    tipo = normalizar(q).tipo
    for aproximar in (False, True):
        achados = conn.execute(Q["buscar"], {**p, "aproximar": aproximar and bool(resto)}).fetchall()
        if achados:
            break
    # Quem diz o tipo ("controle ps5") quer o tipo: "+ 1 Controle" no título do
    # console não faz dele um controle. Sem nenhum do tipo, não filtra. "Jogo"
    # só reordena: muito título de jogo não diz "jogo" ("Dixit", "Star Fox").
    if tipo != "outro":
        do_tipo = [r for r in achados if tipo in {normalizar(t).tipo for t in r["titulos"]}]
        if tipo == "jogo":
            achados = do_tipo + [r for r in achados if r not in do_tipo]
        else:
            achados = do_tipo or achados
    return [r["id"] for r in achados]


# ---------- perfis ----------

def _gravar_escolhas(conn, pid: UUID, p: m.PerfilEntrada) -> None:
    for nome, slugs in (("categoria", p.categorias), ("loja", p.lojas)):
        achados = {r["slug"] for r in conn.execute(Q[f"slugs_{nome}"], {"slugs": slugs})} if slugs else set()
        faltam = [s for s in slugs if s not in achados]
        if faltam:
            raise HTTPException(422, f"{nome} desconhecida: {', '.join(faltam)}")
    for q in ("limpar_categorias", "limpar_lojas", "limpar_interesses"):
        conn.execute(Q[q], {"id": pid})
    conn.execute(Q["inserir_categorias"], {"id": pid, "slugs": p.categorias})
    conn.execute(Q["inserir_lojas"], {"id": pid, "slugs": p.lojas})
    for termo in p.interesses:
        conn.execute(Q["inserir_interesse"], {"id": pid, "termo": termo})


def _perfil(conn, pid: UUID) -> m.Perfil:
    r = conn.execute(Q["perfil"], {"id": pid}).fetchone()
    if not r:
        raise HTTPException(404, "perfil não encontrado")
    return m.Perfil(**r)


def _exigir(conn, consulta: str, valor, oque: str) -> None:
    if not conn.execute(Q[consulta], {"id": valor}).fetchone()["exists"]:
        raise HTTPException(404, f"{oque} não encontrado")


# ---------- histórico ----------

def menor_geral(pontos: list[dict]) -> list[m.Ponto]:
    """Degrau do menor preço entre anúncios: a cada instante, o mínimo dos
    preços vigentes. `pontos` em ordem de tempo."""
    vigente: dict[int, Decimal] = {}
    out: list[m.Ponto] = []
    i = 0
    while i < len(pontos):
        em = pontos[i]["em"]
        while i < len(pontos) and pontos[i]["em"] == em:
            vigente[pontos[i]["anuncio_id"]] = pontos[i]["preco"]
            i += 1
        menor = min(vigente.values())
        if not out or out[-1].preco != menor:
            out.append(m.Ponto(em=em, preco=menor))
    return out


# ---------- app ----------

def criar_app(url_banco: str | None = None, dir_dados: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def ciclo(app: FastAPI):
        from config import ConfigColeta, database_url

        app.state.dir_dados = dir_dados or ConfigColeta.carregar().dir_dados
        app.state.pool = ConnectionPool(url_banco or database_url(), min_size=1, max_size=4, open=True,
                                        kwargs={"row_factory": dict_row}, timeout=5)
        yield
        app.state.pool.close()

    app = FastAPI(title="Sossego", version="0.4.0", lifespan=ciclo,
                  description="Comparador de preços de uso pessoal. Rotas estáveis em /api/v1: "
                              "mudança incompatível só numa /api/v2.")
    v1 = "/api/v1"

    @app.exception_handler(psycopg.errors.CheckViolation)
    async def _check(_, e):  # o banco também barra o 4º item (trigger), se a validação falhar
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": str(e.diag.message_primary)}, status_code=422)

    @app.get(f"{v1}/lojas", response_model=list[m.Loja], tags=["catálogo"])
    def lojas(conn=Conn):
        return conn.execute(Q["lojas"]).fetchall()

    @app.get(f"{v1}/categorias", response_model=list[m.Categoria], tags=["catálogo"])
    def categorias(conn=Conn):
        return conn.execute(Q["categorias"]).fetchall()

    @app.post(f"{v1}/perfis", response_model=m.Perfil, status_code=201, tags=["perfil"])
    def criar_perfil(p: m.PerfilEntrada, conn=Conn):
        pid = uuid4()
        with conn.transaction():
            conn.execute(Q["criar_perfil"], {"id": pid, "faixa_etaria": p.faixa_etaria, "genero": p.genero})
            _gravar_escolhas(conn, pid, p)
        return _perfil(conn, pid)

    @app.get(f"{v1}/perfis/{{pid}}", response_model=m.Perfil, tags=["perfil"])
    def ler_perfil(pid: UUID, conn=Conn):
        return _perfil(conn, pid)

    @app.put(f"{v1}/perfis/{{pid}}", response_model=m.Perfil, tags=["perfil"])
    def atualizar_perfil(pid: UUID, p: m.PerfilEntrada, conn=Conn):
        with conn.transaction():
            _exigir(conn, "existe_perfil", pid, "perfil")
            conn.execute(Q["atualizar_perfil"], {"id": pid, "faixa_etaria": p.faixa_etaria, "genero": p.genero})
            _gravar_escolhas(conn, pid, p)
        return _perfil(conn, pid)

    @app.get(f"{v1}/busca", response_model=m.ResultadoBusca, tags=["busca"])
    def busca(q: str | None = Query(None, min_length=2, max_length=100),
              categoria: str | None = Query(None, description="slug; sem q, lista a categoria (chips da home)"),
              perfil: UUID | None = None,
              ordem: Literal["relevancia", "preco", "pix", "queda"] = "relevancia",
              loja: list[str] | None = Query(None, description="só ofertas destas lojas (slug)"),
              preco_min: m.Dinheiro | None = None, preco_max: m.Dinheiro | None = None,
              conn=Conn):
        if not q and not categoria:
            raise HTTPException(422, "informe q ou categoria")
        if categoria and not conn.execute(Q["existe_categoria"], {"slug": categoria}).fetchone():
            raise HTTPException(422, f"categoria desconhecida: {categoria}")
        ids = _buscar(conn, q) if q else [r["id"] for r in conn.execute(Q["por_categoria"], {"slug": categoria})]
        res = _na_ordem(ids, cards(conn, ids, loja))
        if categoria:
            res = [c for c in res if c.categoria == categoria]
        res = [c for c in res if (preco_min is None or c.menor_preco >= preco_min)
               and (preco_max is None or c.menor_preco <= preco_max)]
        if ordem == "preco":
            res.sort(key=lambda c: c.menor_preco)
        elif ordem == "pix":
            res.sort(key=lambda c: c.menor_pix if c.menor_pix is not None else c.menor_preco)
        elif ordem == "queda":
            res.sort(key=lambda c: c.variacao_pct if c.variacao_pct is not None else Decimal(0))
        if q:  # navegar por categoria não é busca: não entra no histórico de buscas
            conn.execute(Q["registrar_busca"], {"perfil": perfil, "termo": q.strip(), "resultados": len(res)})
        return m.ResultadoBusca(q=q or "", categoria=categoria, ordem=ordem, total=len(res), resultados=res)

    @app.get(f"{v1}/produtos/{{produto_id}}", response_model=m.Produto, tags=["produto"])
    def produto(produto_id: int, conn=Conn):
        p = conn.execute(Q["produto"], {"id": produto_id}).fetchone()
        if not p:
            raise HTTPException(404, "produto não encontrado")
        return m.Produto(**p, ofertas=conn.execute(Q["ofertas"], {"id": produto_id}).fetchall(),
                         menor_visto=conn.execute(Q["menor_visto"], {"id": produto_id}).fetchone())

    @app.get(f"{v1}/produtos/{{produto_id}}/historico", response_model=m.Historico, tags=["produto"])
    def historico(produto_id: int, periodo: Literal["24h", "7d", "30d", "tudo"] = "30d", conn=Conn):
        _exigir(conn, "existe_produto", produto_id, "produto")
        janela = PERIODOS[periodo]
        desde = datetime.now(timezone.utc) - janela if janela else None
        pontos = conn.execute(Q["historico"], {"id": produto_id, "desde": desde}).fetchall()
        series: dict[int, m.Serie] = {}
        for p in pontos:
            s = series.setdefault(p["anuncio_id"], m.Serie(anuncio_id=p["anuncio_id"], loja=p["loja"],
                                                           titulo=p["titulo_original"], pontos=[]))
            s.pontos.append(m.Ponto(em=p["em"], preco=p["preco"], preco_pix=p["preco_pix"]))
        return m.Historico(produto_id=produto_id, periodo=periodo, desde=desde, series=list(series.values()),
                           menor_geral=menor_geral(pontos),
                           menor_visto=conn.execute(Q["menor_visto"], {"id": produto_id}).fetchone())

    @app.get(f"{v1}/produtos/{{produto_id}}/parecidos", response_model=list[m.Card], tags=["produto"])
    def parecidos(produto_id: int, conn=Conn):
        base = cards(conn, [produto_id]).get(produto_id)
        if base is None:
            _exigir(conn, "existe_produto", produto_id, "produto")
            return []
        ids = [r["id"] for r in conn.execute(Q["parecidos"], {"id": produto_id})]
        # Faixa de preço próxima: ±40% do melhor preço do produto.
        lo, hi = base.menor_preco * Decimal("0.6"), base.menor_preco * Decimal("1.4")
        return [c for c in _na_ordem(ids, cards(conn, ids)) if lo <= c.menor_preco <= hi][:8]

    @app.post(f"{v1}/perfis/{{pid}}/vigias/{{produto_id}}", status_code=204, tags=["vigia"])
    def vigiar(pid: UUID, produto_id: int, corpo: m.VigiaEntrada | None = None, conn=Conn):
        _exigir(conn, "existe_perfil", pid, "perfil")
        _exigir(conn, "existe_produto", produto_id, "produto")
        conn.execute(Q["vigiar"], {"perfil": pid, "produto": produto_id,
                                   "preco_alvo": corpo.preco_alvo if corpo else None})
        return Response(status_code=204)

    @app.delete(f"{v1}/perfis/{{pid}}/vigias/{{produto_id}}", status_code=204, tags=["vigia"])
    def desvigiar(pid: UUID, produto_id: int, conn=Conn):
        conn.execute(Q["desvigiar"], {"perfil": pid, "produto": produto_id})
        return Response(status_code=204)

    @app.get(f"{v1}/vigias/quedas", response_model=list[m.Queda], tags=["vigia"])
    def quedas(desde: datetime | None = Query(None, description="padrão: 24 h atrás"), conn=Conn):
        desde = desde or datetime.now(timezone.utc) - timedelta(hours=24)
        linhas = conn.execute(Q["quedas"], {"desde": desde}).fetchall()
        agora = cards(conn, sorted({r["produto_id"] for r in linhas}))
        out = []
        for r in linhas:
            c = agora.get(r["produto_id"])
            if c is None:
                continue
            caiu = r["preco_antes"] is not None and c.menor_preco < r["preco_antes"]
            alvo = r["preco_alvo"] is not None and c.menor_preco <= r["preco_alvo"]
            if not (caiu or alvo):
                continue
            motivo = " e ".join(x for x in (
                f"caiu de R$ {r['preco_antes']} para R$ {c.menor_preco}" if caiu else "",
                f"chegou ao preço-alvo de R$ {r['preco_alvo']}" if alvo else "") if x)
            out.append(m.Queda(perfil_id=r["perfil_id"], produto_id=c.id, titulo=c.titulo,
                               preco_antes=r["preco_antes"], preco_agora=c.menor_preco,
                               queda_pct=_pct(c.menor_preco, r["preco_antes"]) if caiu else None,
                               preco_alvo=r["preco_alvo"], alvo_atingido=alvo, motivo=motivo,
                               loja=c.loja, loja_nome=c.loja_nome, url=c.url))
        return out

    @app.get(f"{v1}/inicio", response_model=m.Inicio, tags=["início"])
    def inicio(perfil: UUID | None = None, conn=Conn):
        todas = [m.Categoria(**c) for c in conn.execute(Q["categorias"])]
        if perfil is None:
            ids = [r["id"] for r in conn.execute(Q["produtos_da_categoria"], {"cats": None})]
            return m.Inicio(de_olho=[], pra_voce=[], caiu_de_preco=_caiu(cards(conn, ids)), categorias=todas)
        _exigir(conn, "existe_perfil", perfil, "perfil")
        p = {"perfil": perfil}
        vigiados = [r["produto_id"] for r in conn.execute(Q["vigiados"], p)]
        cats = [r["slug"] for r in conn.execute(Q["categorias_do_perfil"], p)]
        preferidas = {r["slug"] for r in conn.execute(Q["lojas_do_perfil"], p)}

        cand = conn.execute(Q["candidatos_pra_voce"], p).fetchall()
        cs = cards(conn, [r["id"] for r in cand])
        recs = []
        for r in cand:
            c = cs.get(r["id"])
            if c is None:
                continue
            sim = float(r["sim"])
            queda = c.variacao_pct is not None and c.variacao_pct < 0
            # Pontuação explicável: categoria + parecido com o que procurou + queda real.
            nota = (1.0 if r["da_categoria"] else 0) + 2 * sim + (0.5 if queda else 0)
            porque = (f"porque você procurou {r['termo']}" if sim >= 0.5
                      else f"porque você escolheu {r['categoria_nome']}")
            recs.append((nota, c.loja in preferidas, -c.menor_preco, m.Recomendacao(**c.model_dump(), porque=porque)))
        recs.sort(key=lambda x: x[:3], reverse=True)

        ids_cat = [r["id"] for r in conn.execute(Q["produtos_da_categoria"], {"cats": cats or None})]
        ordem_cat = {s: i for i, s in enumerate(cats)}
        return m.Inicio(
            de_olho=_na_ordem(vigiados, cards(conn, vigiados)),
            pra_voce=[r[3] for r in recs[:12]],
            caiu_de_preco=_caiu(cards(conn, ids_cat)),
            categorias=sorted(todas, key=lambda c: (ordem_cat.get(c.slug, len(cats)), c.nome)),
        )

    @app.post(f"{v1}/pagamento/simular", response_model=m.Simulacao, tags=["pagamento"])
    def simular_pagamento(e: m.SimulacaoEntrada, conn=Conn):
        return _simular(conn, e)

    @app.get(f"{v1}/saude", response_model=m.Saude, tags=["operação"])
    def saude(request: Request):
        return _saude(request.app)

    return app


def _pct_ou_none(x):
    return None if x is None else (x * 100).quantize(Decimal("0.01"), ROUND_HALF_UP)


def _simular(conn, e: m.SimulacaoEntrada) -> m.Simulacao:
    from pagamento.calculo import simular

    cdi = data = None
    if e.rendimento_mensal_pct is None:
        taxa = conn.execute(Q["ultima_taxa"]).fetchone()
        if taxa is None:
            raise HTTPException(503, "sem taxa do Banco Central salva; informe rendimento_mensal_pct")
        cdi, data = taxa["cdi_anual"], taxa["data"]
    try:
        s = simular(preco_avista=e.preco_avista, preco_cartao=e.preco_cartao, parcelas=e.parcelas,
                    valor_parcela=e.valor_parcela,
                    taxa_mensal=None if e.rendimento_mensal_pct is None else e.rendimento_mensal_pct / 100,
                    cdi_anual=None if cdi is None else cdi / 100, pct_cdi=e.pct_cdi / 100,
                    cashback=e.cashback_pct / 100, no_ato=e.primeira_parcela == "ato")
    except ValueError as erro:
        raise HTTPException(422, str(erro))

    def opcao(o):
        return m.OpcaoPagamento(
            tipo=o.tipo, parcelas=o.parcelas, valor_parcela=o.valor_parcela, total=o.total,
            valor_presente=o.valor_presente, cashback=o.cashback, custo_efetivo=o.custo_efetivo,
            rendimento_mensal_pct=_pct_ou_none(o.taxa_mensal), ir_pct=_pct_ou_none(o.ir),
            desconto_equilibrio_pct=_pct_ou_none(o.desconto_equilibrio), juros_mensal_pct=_pct_ou_none(o.juros_mensal))

    return m.Simulacao(recomendacao=s.recomendacao, melhor=opcao(s.melhor), opcoes=[opcao(o) for o in s.opcoes],
                       desconto_pix_pct=_pct_ou_none(s.desconto_pix), economia=s.economia,
                       rendimento_fonte="informado" if cdi is None else "cdi_bcb", cdi_anual_pct=cdi, cdi_data=data)


def _caiu(cs: dict[int, m.Card]) -> list[m.Card]:
    caidos = [c for c in cs.values() if c.variacao_pct is not None and c.variacao_pct < 0]
    return sorted(caidos, key=lambda c: (c.variacao_pct, c.id))[:12]


def _saude(app: FastAPI) -> m.Saude:
    from coleta.admin import situacao_loja
    from coleta.estado import Estado
    from coleta.lojas_mvp import LOJAS

    dados: Path = app.state.dir_dados
    agora = time.time()
    execucoes, banco = {}, "ok"
    try:
        with app.state.pool.connection() as c:
            execucoes = {r["slug"]: r["em"] for r in c.execute(Q["ultima_execucao_ok"])}
    except Exception:  # banco fora do ar: a saúde diz isso, não cai junto
        banco = "erro"
    w = dados / "worker.json"
    batimento = json.loads(w.read_text(encoding="utf-8"))["batimento_em"] if w.exists() else None
    sqlite = dados / "coleta.sqlite3"
    estado = Estado(sqlite) if sqlite.exists() else None

    def dt(t):
        return datetime.fromtimestamp(t, timezone.utc) if t else None

    lojas = []
    for slug, loja in LOJAS.items():
        if estado is None:
            sit, texto, ok = "sem_estado", "sem estado da coleta (dados/coleta.sqlite3)", None
        else:
            sit, texto, _ = situacao_loja(slug, estado, agora)
            ok = estado.ultima_por_classe(slug, "ok")
        lojas.append(m.SaudeLoja(slug=slug, nome=loja.nome, situacao=sit, texto=texto, ultima_ok=dt(ok),
                                 ultima_execucao_ok=execucoes.get(slug)))
    return m.Saude(banco=banco, worker_vivo=batimento is not None and agora - batimento < 180,
                   worker_batimento_em=dt(batimento), lojas=lojas)


app = criar_app()
