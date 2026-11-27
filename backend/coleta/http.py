"""Cliente HTTP educado: a única porta de saída da coleta para a internet.

Regra inegociável: prefiro ficar sem o dado de uma loja a ter o IP banido ou
sobrecarregar alguém. Por isso, toda requisição passa, nesta ordem, por:

    kill switch → URL permitida → breaker → cache → robots.txt →
    orçamento → intervalo (+jitter, Crawl-delay) → envio → classificação

Bloqueou (403, 429, captcha, conteúdo inesperado) = parou. Não há retry
nesses casos, nem troca de fingerprint, nem proxy. Retry só em 5xx/timeout.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Literal, Protocol
from urllib.parse import urlsplit

from config import ConfigColeta, coleta_pausada
from coleta import robots as robots_mod
from coleta.estado import EntradaCache, Estado

log = logging.getLogger("sossego.coleta")

Tipo = Literal["busca", "produto", "robots", "recon"]


# --- erros: cada um diz por que a requisição NÃO saiu (ou parou) ----------
class ColetaRecusada(Exception):
    """Base: a requisição não foi feita ou foi interrompida de propósito."""


class ColetaPausada(ColetaRecusada):
    """Kill switch ligado."""


class UrlProibida(ColetaRecusada):
    """URL fora do que coletamos (login, carrinho, método não-GET...)."""


class LojaDesligada(ColetaRecusada):
    """Breaker no último nível: só religa na mão."""


class LojaEmPausa(ColetaRecusada):
    def __init__(self, loja: str, ate: float):
        super().__init__(f"{loja} em pausa até {time.strftime('%d/%m %H:%M', time.localtime(ate))}")
        self.ate = ate


class BloqueadaPorRobots(ColetaRecusada):
    pass


class OrcamentoEsgotado(ColetaRecusada):
    def __init__(self, loja: str, janela: str, libera_em: float | None):
        super().__init__(f"orçamento de {loja} esgotado ({janela})")
        self.libera_em = libera_em


class SinalDeBloqueio(ColetaRecusada):
    """A loja deu sinal de que não quer a gente ali (403/429/captcha). Breaker aberto."""


class MoldeQuebrado(ColetaRecusada):
    """A página veio, mas sem os dados esperados: o problema é nosso (URL ou
    layout mudou), não um bloqueio. A loja pausa mesmo assim: melhor parar
    que insistir. O bruto é salvo antes, para reprocessar depois."""


class FalhaTransitoria(Exception):
    """5xx/timeout mesmo após os retries."""


# --- dependências injetáveis (relógio e transporte) ------------------------
class Relogio(Protocol):
    def agora(self) -> float: ...
    async def dormir(self, segundos: float) -> None: ...


class RelogioReal:
    def agora(self) -> float:
        return time.time()

    async def dormir(self, segundos: float) -> None:
        if segundos > 0:
            await asyncio.sleep(segundos)


@dataclass
class Resposta:
    status: int
    cabecalhos: dict[str, str]
    corpo: bytes
    url_final: str
    id_req: int | None = None  # linha em `requisicao`, para classificar depois

    def texto(self) -> str:
        return self.corpo.decode("utf-8", errors="replace")


class Transporte(Protocol):
    async def get(self, url: str, cabecalhos: dict[str, str], timeout: float) -> Resposta: ...
    async def post(self, url: str, cabecalhos: dict[str, str], dados: dict[str, str], timeout: float) -> Resposta: ...


# POST só para obter token de aplicação de API oficial. Nada mais.
TOKENS_PERMITIDOS = frozenset({"https://api.mercadolibre.com/oauth/token"})


class TransporteCurlCffi:
    """curl_cffi imitando o Chrome. O User-Agent vem do próprio perfil de
    impersonate, coerente com o fingerprint TLS; não sobrescrevemos."""

    def __init__(self):
        from curl_cffi.requests import AsyncSession

        self._sessao = AsyncSession(impersonate="chrome")

    async def get(self, url, cabecalhos, timeout) -> Resposta:
        from curl_cffi.requests.exceptions import Timeout as CurlTimeout

        try:
            r = await self._sessao.get(url, headers=cabecalhos, timeout=timeout, allow_redirects=True)
        except CurlTimeout as e:
            raise TimeoutError(str(e)) from e
        return Resposta(r.status_code, {k.lower(): v for k, v in r.headers.items()}, r.content, str(r.url))

    async def post(self, url, cabecalhos, dados, timeout) -> Resposta:
        r = await self._sessao.post(url, headers=cabecalhos, data=dados, timeout=timeout)
        return Resposta(r.status_code, {k.lower(): v for k, v in r.headers.items()}, r.content, str(r.url))

    async def fechar(self):
        await self._sessao.close()


# --- detecção de bloqueio ---------------------------------------------------
# Marcadores específicos de página de desafio. Evitamos "recaptcha" puro:
# muita página normal carrega o script e isso desligaria a loja à toa.
MARCADORES_DESAFIO = [
    "validatecaptcha",              # Amazon
    "robot check",                  # Amazon (en)
    "digite os caracteres que você vê",  # Amazon (pt)
    "captcha-delivery.com",         # DataDome
    "px-captcha",                   # PerimeterX
    "pardon our interruption",      # Imperva/Distil
    "cf-chl-",                      # Cloudflare challenge
    "/cdn-cgi/challenge-platform/h/",
    "access denied</title>",        # Akamai
    # Akamai Bot Manager, desafio com prova de trabalho (Amazon, 27/11/2026 na BF):
    # 200, 2 KB, meta refresh com bm-verify e POST para /_sec/verify. Não resolvemos.
    "bm-verify=",
    "/_sec/verify?provider=interstitial",
    "suspeitamos que você seja um robô",
    # Interstício anti-robô do Mercado Livre (visto em 26/11/2026): 17 KB, botão
    # "Continuar" e exige JS. Não é página de dados: é a loja dizendo "não".
    "micro-landing-container",
    "this page requires javascript to work",
]


def parece_desafio(r: Resposta) -> str | None:
    if "captcha" in r.url_final.lower():
        return "redirecionou para captcha"
    trecho = r.corpo[:300_000].decode("utf-8", errors="ignore").lower()
    for m in MARCADORES_DESAFIO:
        if m in trecho:
            return f"marcador de desafio: {m!r}"
    return None


# Nunca coletamos áreas que exigem sessão de usuário.
CAMINHOS_PROIBIDOS = re.compile(
    r"/(carrinho|cart|checkout|login|entrar|conta|minha-conta|account|my-account|"
    r"signin|ap/signin|gp/cart|wishlist|lista-de-desejos|pedidos|orders)(/|$|\?)",
    re.IGNORECASE,
)


def loja_padrao(host: str) -> str:
    return host.removeprefix("www.")


@dataclass
class Resultado:
    url: str
    loja: str
    status: int
    corpo: bytes
    cabecalhos: dict[str, str]
    do_cache: bool
    obtido_em: float

    def texto(self) -> str:
        return self.corpo.decode("utf-8", errors="replace")


Validador = Callable[[Resposta], bool]


@dataclass
class ClienteEducado:
    estado: Estado
    transporte: Transporte
    cfg: ConfigColeta = field(default_factory=ConfigColeta)
    relogio: Relogio = field(default_factory=RelogioReal)
    rng: random.Random = field(default_factory=random.Random)
    loja_de: Callable[[str], str] = loja_padrao
    pausada: Callable[[], bool] | None = None
    dir_bruto: Path | None = None  # se definido, grava toda resposta nova em .json.gz
    # Lojas em que o 1º bloqueio já desliga (ex.: API oficial com token: 403
    # ali é recusa explícita, e o dono quer ser avisado, não que insistamos).
    estritas: frozenset[str] = frozenset()

    def __post_init__(self):
        self._travas: dict[str, asyncio.Lock] = {}
        if self.pausada is None:
            arquivo_parar = self.cfg.dir_dados / "PARAR"
            self.pausada = lambda: coleta_pausada() or arquivo_parar.exists()

    # --- API pública ------------------------------------------------------
    async def obter_token(self, url: str, dados: dict[str, str]) -> dict:
        """Única exceção ao "só GET": o POST do token de APLICAÇÃO de uma API
        oficial (client credentials, sem usuário). Só para URLs da lista
        TOKENS_PERMITIDOS; passa por kill switch, breaker, orçamento e
        intervalo; nunca vai para cache, bruto ou log com corpo."""
        self._checar_pausa()
        if url not in TOKENS_PERMITIDOS:
            raise UrlProibida(f"POST não permitido: {url}")
        loja = self.loja_de(urlsplit(url).hostname)
        async with self._travas.setdefault(loja, asyncio.Lock()):
            self._checar_breaker(loja)
            self._checar_orcamento(loja)
            await self._esperar_vez(loja, None)
            self._checar_pausa()
            inicio = self.relogio.agora()
            r = await self.transporte.post(url, {"Accept": "application/json"}, dados, self.cfg.timeout_s)
            r.id_req = self._registrar(loja, url, "token", inicio, r.status, 0, len(r.corpo), "enviada")
            if r.status in (401, 403, 429):
                self._classificar(r, "bloqueio")
                self._sinal(loja, f"token: HTTP {r.status}", _retry_after(r.cabecalhos, inicio))
                raise SinalDeBloqueio(f"{loja}: token recusado (HTTP {r.status})")
            if r.status != 200:
                self._classificar(r, "outro")
                raise FalhaTransitoria(f"{loja}: token HTTP {r.status}")
            self._classificar(r, "ok")
            return json.loads(r.corpo)

    async def obter(self, url: str, *, tipo: Tipo, validar: Validador | None = None,
                    cabecalhos: dict[str, str] | None = None) -> Resultado:
        self._checar_pausa()
        partes = urlsplit(url)
        if partes.scheme not in ("http", "https") or not partes.hostname:
            raise UrlProibida(url)
        if CAMINHOS_PROIBIDOS.search(partes.path):
            self._log_local(url, tipo, "url_proibida")
            raise UrlProibida(f"caminho exige sessão de usuário: {url}")
        loja = self.loja_de(partes.hostname)

        # Concorrência 1 por loja: tudo daqui pra baixo é serializado.
        async with self._travas.setdefault(loja, asyncio.Lock()):
            self._checar_breaker(loja)

            ttl = self.cfg.ttl_busca_s if tipo == "busca" else self.cfg.ttl_produto_s
            em_cache = self.estado.cache(url)
            if em_cache and self.relogio.agora() - em_cache.obtido_em < ttl:
                self._registrar(loja, url, tipo, self.relogio.agora(), em_cache.status, 0, 0, "cache")
                return self._resultado(url, loja, em_cache, do_cache=True)

            rb = await self._robots(loja, partes.scheme, partes.hostname)
            if not rb.permite(url):
                self._registrar(loja, url, tipo, self.relogio.agora(), None, 0, 0, "bloqueada_local")
                raise BloqueadaPorRobots(url)

            cond = dict(cabecalhos or {})
            if em_cache and em_cache.etag:
                cond["If-None-Match"] = em_cache.etag
            if em_cache and em_cache.last_modified:
                cond["If-Modified-Since"] = em_cache.last_modified

            r = await self._enviar_com_retry(loja, url, tipo, cond, rb.crawl_delay)

            if r.status == 304 and em_cache:
                em_cache.obtido_em = self.relogio.agora()
                self.estado.guardar_cache(em_cache)
                self._classificar(r, "ok")
                self._sucesso(loja)
                return self._resultado(url, loja, em_cache, do_cache=True)

            bloqueio = self._motivo_bloqueio(r)
            if bloqueio:
                self._classificar(r, "bloqueio")
                self._sinal(loja, bloqueio, _retry_after(r.cabecalhos, self.relogio.agora()))
                raise SinalDeBloqueio(f"{loja}: {bloqueio}")

            # Bruto antes de validar: se o layout mudou (Black Friday), a
            # resposta crua fica salva e o parser reprocessa depois.
            if _sucesso_http(r.status):
                self._gravar_bruto(loja, url, tipo, r)

            molde = self._motivo_molde(r, validar)
            if molde:
                self._classificar(r, "molde_quebrado")
                self._sinal_molde(loja, molde)
                raise MoldeQuebrado(f"{loja}: {molde}")

            self._classificar(r, "ok" if _sucesso_http(r.status) else "outro")
            self._sucesso(loja)
            entrada = EntradaCache(
                url, self.relogio.agora(), r.status, r.cabecalhos, r.corpo,
                r.cabecalhos.get("etag"), r.cabecalhos.get("last-modified"),
            )
            if _sucesso_http(r.status):
                self.estado.guardar_cache(entrada)
            return self._resultado(url, loja, entrada, do_cache=False)

    # --- etapas -----------------------------------------------------------
    def _checar_pausa(self):
        if self.pausada():
            raise ColetaPausada("SOSSEGO_COLETA_PAUSADA ligado (ou dados/PARAR existe)")

    def _checar_breaker(self, loja: str):
        b = self.estado.breaker(loja)
        if b.desligada:
            raise LojaDesligada(f"{loja} desligada pelo breaker ({b.motivo}); religue na mão")
        if b.pausada_ate > self.relogio.agora():
            raise LojaEmPausa(loja, b.pausada_ate)

    def _checar_orcamento(self, loja: str):
        agora = self.relogio.agora()
        for janela, segundos, limite in (("hora", 3600, self.cfg.orcamento_hora), ("dia", 86400, self.cfg.orcamento_dia)):
            if self.estado.enviadas_desde(loja, agora - segundos) >= limite:
                antiga = self.estado.mais_antiga_enviada_desde(loja, agora - segundos)
                libera = antiga + segundos if antiga else None
                log.warning(json.dumps({"evento": "orcamento_esgotado", "loja": loja, "janela": janela}))
                raise OrcamentoEsgotado(loja, janela, libera)

    async def _esperar_vez(self, loja: str, crawl_delay: float | None):
        ultima = self.estado.ultima_enviada(loja)
        if ultima is None:
            return
        intervalo = max(self.cfg.intervalo_min_s, crawl_delay or 0)
        alvo = ultima + intervalo + self.rng.uniform(0, self.cfg.jitter_max_s)
        espera = alvo - self.relogio.agora()
        if espera > 0:
            await self.relogio.dormir(espera)

    async def _enviar(self, loja, url, tipo, cabecalhos, crawl_delay) -> Resposta | None:
        """Uma ida à rede. Devolve None em timeout."""
        self._checar_orcamento(loja)
        await self._esperar_vez(loja, crawl_delay)
        self._checar_pausa()  # o kill switch pode ter sido ligado durante a espera
        inicio = self.relogio.agora()
        t0 = time.perf_counter()
        base = {"Accept-Language": "pt-BR,pt;q=0.9"}
        try:
            r = await self.transporte.get(url, {**base, **cabecalhos}, self.cfg.timeout_s)
        except (TimeoutError, asyncio.TimeoutError):
            self._registrar(loja, url, tipo, inicio, None, int((time.perf_counter() - t0) * 1000), 0, "timeout")
            return None
        dur = int((time.perf_counter() - t0) * 1000)
        r.id_req = self._registrar(loja, url, tipo, inicio, r.status, dur, len(r.corpo), "enviada",
                                   "transitoria" if r.status >= 500 else None)
        return r

    async def _enviar_com_retry(self, loja, url, tipo, cabecalhos, crawl_delay) -> Resposta:
        tentativas = len(self.cfg.backoff_retry_s)
        for i in range(tentativas + 1):
            r = await self._enviar(loja, url, tipo, cabecalhos, crawl_delay)
            transitoria = r is None or r.status >= 500
            if not transitoria:
                return r
            if i == tentativas:
                break
            espera = self.cfg.backoff_retry_s[i]
            ra = _retry_after(r.cabecalhos, self.relogio.agora()) if r else None
            if ra is not None:
                if ra > self.cfg.max_espera_retry_s:
                    # A loja pediu um tempo longo: vira pausa, não espera ativa.
                    self._pausar(loja, ra, f"Retry-After {int(ra)}s em {r.status}")
                    raise FalhaTransitoria(f"{loja}: Retry-After longo ({int(ra)}s)")
                espera = max(espera, ra)
            log.info(json.dumps({"evento": "retry", "loja": loja, "url": url, "espera_s": espera,
                                 "status": r.status if r else "timeout"}))
            await self.relogio.dormir(espera)
            self._checar_pausa()
        raise FalhaTransitoria(f"{loja}: {'timeout' if r is None else r.status} após {tentativas} retries")

    def _motivo_bloqueio(self, r: Resposta) -> str | None:
        if r.status in (401, 403):
            return f"HTTP {r.status}"
        if r.status == 429:
            return "HTTP 429"
        return parece_desafio(r)

    def _motivo_molde(self, r: Resposta, validar: Validador | None) -> str | None:
        if validar is None:
            return None
        if _sucesso_http(r.status) and not validar(r):
            return "página válida, mas sem os dados esperados"
        if r.status in (404, 410):
            # Com validador = busca: URL inexistente é molde de URL errado.
            return f"HTTP {r.status}: molde de URL errado?"
        return None

    def _classificar(self, r: Resposta, classe: str):
        if r.id_req is not None:
            self.estado.classificar(r.id_req, classe)

    async def _robots(self, loja: str, esquema: str, host: str) -> robots_mod.Robots:
        agora = self.relogio.agora()
        salvo = self.estado.robots(host)
        if salvo and agora - salvo[0] < self.cfg.ttl_robots_s:
            return _robots_de(salvo[1], salvo[2])
        url = f"{esquema}://{host}/robots.txt"
        r = await self._enviar_com_retry(loja, url, "robots", {}, None)
        if r.status in (401, 403, 429) or parece_desafio(r):
            # Barrado já no robots.txt: é sinal de bloqueio, e não coletamos nada.
            self._sinal(loja, f"robots.txt respondeu {r.status}", _retry_after(r.cabecalhos, agora))
            raise SinalDeBloqueio(f"{loja}: robots.txt respondeu {r.status}")
        conteudo = r.texto() if r.status == 200 else ""
        self.estado.guardar_robots(host, self.relogio.agora(), r.status, conteudo)
        return _robots_de(r.status, conteudo)

    # --- breaker ----------------------------------------------------------
    def _sinal(self, loja: str, motivo: str, retry_after: float | None):
        """1º sinal: 30 min; reincidência: 2 h, depois 6 h. 3 sinais SEGUIDOS
        (sem uma resposta boa no meio): loja desligada até religar na mão."""
        agora = self.relogio.agora()
        b = self.estado.breaker(loja)
        if b.ultimo_sinal_em is not None and agora - b.ultimo_sinal_em > self.cfg.esquecer_reincidencia_s:
            b.nivel = 0
        b.sinais_seguidos += 1
        b.nivel += 1
        b.ultimo_sinal_em = agora
        b.motivo = motivo
        b.tipo_motivo = "bloqueio"
        if b.sinais_seguidos >= self.cfg.sinais_seguidos_para_desligar or loja in self.estritas:
            b.desligada = True
            log.error(json.dumps({"evento": "LOJA_DESLIGADA", "loja": loja, "motivo": motivo,
                                  "acao": f"python -m coleta.admin religar {loja}"}))
        else:
            pausa = self.cfg.pausas_breaker_s[min(b.nivel, len(self.cfg.pausas_breaker_s)) - 1]
            b.pausada_ate = agora + max(pausa, retry_after or 0)
            log.warning(json.dumps({"evento": "breaker_aberto", "loja": loja, "motivo": motivo,
                                    "pausa_s": b.pausada_ate - agora, "sinais_seguidos": b.sinais_seguidos}))
        self.estado.salvar_breaker(b)

    def _sinal_molde(self, loja: str, motivo: str):
        """Molde quebrado pausa com a mesma escada (30 min → 2 h → 6 h), mas
        NUNCA desliga a loja: não é risco de banimento, e desligar perderia o
        bruto da Black Friday. Também não conta como sinal de bloqueio."""
        agora = self.relogio.agora()
        b = self.estado.breaker(loja)
        b.molde_seguidos += 1
        pausa = self.cfg.pausas_breaker_s[min(b.molde_seguidos, len(self.cfg.pausas_breaker_s)) - 1]
        b.pausada_ate = max(b.pausada_ate, agora + pausa)
        b.motivo = motivo
        b.tipo_motivo = "molde_quebrado"
        log.error(json.dumps({"evento": "MOLDE_QUEBRADO", "loja": loja, "motivo": motivo,
                              "pausa_s": pausa, "molde_seguidos": b.molde_seguidos}))
        self.estado.salvar_breaker(b)

    def _pausar(self, loja: str, segundos: float, motivo: str):
        b = self.estado.breaker(loja)
        b.pausada_ate = max(b.pausada_ate, self.relogio.agora() + segundos)
        b.motivo = motivo
        self.estado.salvar_breaker(b)

    def _sucesso(self, loja: str):
        b = self.estado.breaker(loja)
        if b.sinais_seguidos or b.molde_seguidos:
            b.sinais_seguidos = 0
            b.molde_seguidos = 0
            self.estado.salvar_breaker(b)

    # --- registro ---------------------------------------------------------
    def _registrar(self, loja, url, tipo, inicio, status, dur, bytes_, resultado, classe=None) -> int:
        id_ = self.estado.registrar(loja=loja, url=url, tipo=tipo, inicio=inicio, status=status,
                                    duracao_ms=dur, bytes_=bytes_, resultado=resultado, classe=classe)
        log.info(json.dumps({"evento": "requisicao", "loja": loja, "url": url, "tipo": tipo,
                             "status": status, "duracao_ms": dur, "bytes": bytes_, "resultado": resultado}))
        return id_

    def _log_local(self, url, tipo, resultado):
        log.warning(json.dumps({"evento": resultado, "url": url, "tipo": tipo}))

    def _resultado(self, url, loja, e: EntradaCache, do_cache: bool) -> Resultado:
        return Resultado(url, loja, e.status, e.corpo, e.cabecalhos, do_cache, e.obtido_em)

    def _gravar_bruto(self, loja: str, url: str, tipo: str, r: Resposta):
        """Landing zone: a resposta crua, para os parsers reprocessarem depois."""
        if self.dir_bruto is None:
            return
        agora = self.relogio.agora()
        carimbo = time.strftime("%Y%m%dT%H%M%S", time.gmtime(agora))
        pasta = self.dir_bruto / loja / time.strftime("%Y-%m-%d", time.gmtime(agora))
        pasta.mkdir(parents=True, exist_ok=True)
        import hashlib

        h = hashlib.sha1(url.encode()).hexdigest()[:10]
        registro = {
            "loja": loja, "url": url, "url_final": r.url_final, "tipo": tipo, "status": r.status,
            "coletado_em": agora, "cabecalhos": r.cabecalhos,
            "corpo": r.corpo.decode("utf-8", errors="replace"),
        }
        with gzip.open(pasta / f"{carimbo}Z_{tipo}_{h}.json.gz", "wt", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False)


def _sucesso_http(status: int) -> bool:
    # 206: a VTEX responde assim a busca paginada, com o corpo completo.
    return status in (200, 203, 206)


def _robots_de(status: int | None, conteudo: str) -> robots_mod.Robots:
    # RFC 9309: 4xx (exceto 401/403, tratados antes) = sem restrição;
    # 5xx/indisponível = assume tudo proibido.
    if status == 200:
        return robots_mod.analisar(conteudo)
    if status is not None and 400 <= status < 500:
        return robots_mod.Robots()
    return robots_mod.Robots(bloqueia_tudo=True)


def _retry_after(cabecalhos: dict[str, str], agora: float) -> float | None:
    v = cabecalhos.get("retry-after")
    if not v:
        return None
    if v.strip().isdigit():
        return float(v)
    from email.utils import parsedate_to_datetime

    try:
        return max(0.0, parsedate_to_datetime(v).timestamp() - agora)
    except (TypeError, ValueError):
        return None
