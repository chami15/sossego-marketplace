# AGENTS.md — Sossego

Comparador de preços de uso pessoal: uma busca, todas as lojas, histórico de
preço e a melhor forma de pagar. Monolito modular em Python (FastAPI + worker)
com Postgres; frontend React depois.

## Princípios (valem para qualquer agente)

1. **Debate antes de construir.** Decisão de design não fechada: proponha,
   explique alternativas e espere o "pode". Correção pontual: faça direto.
2. **Fases pequenas e testadas.** Branch `fase/NN-<nome>`, commits por módulo
   (Conventional Commits em português), `make test` verde antes do PR.
3. **Pesquise antes de afirmar.** Sites mudam. Nada de "a loja X usa Y" de
   memória: verifique e registre a data em `docs/fontes/<loja>.md`.
4. **Honestidade.** Diga o que testou e o que não testou. "Compilou" ≠ testado.
5. **Bug achado = teste de regressão antes da correção:** `test_regressao_<o_que_quebrava>`.
6. **Nunca** pule, desabilite ou afrouxe teste para ficar verde.
7. **Segredo nunca no git:** `.env` (ignorado) + `.env.example` comentado.
8. **Migration aplicada não se edita:** crie a próxima, numerada.
9. Docs, nomes de domínio e commits em **português**. Comentário explica o porquê.
10. Dinheiro é `Decimal`/`NUMERIC(12,2)`. Nunca `float`.

## Coleta segura e educada (INEGOCIÁVEL)

O coletor roda na máquina do dono, com o IP residencial dele. Prefira ficar sem
o dado de uma loja a arriscar banimento ou sobrecarga.

- Toda requisição sai **só** por `backend/coleta/http.py` (`ClienteEducado`).
  Nada de `requests`/`httpx`/`curl_cffi` direto em adaptador.
- 1 requisição por vez por loja; ≥ 5 s + jitter 0–3 s; orçamento 60/h e 500/dia.
- 403/429/captcha/conteúdo inesperado = breaker (30 min → 2 h → 6 h; 3 seguidos
  = desligada até religar na mão). **Sem retry** nesses casos.
- Retry só em 5xx/timeout (máx. 2: 30 s, 2 min). Respeitar `Retry-After`.
- robots.txt (Disallow e Crawl-delay) respeitado; cache 30 min (busca) / 50 min (produto).
- **Proibido:** proxy/rotação, resolver captcha, trocar fingerprint para fugir
  de bloqueio, login/carrinho/qualquer coisa com sessão, método não-GET.
- Antes de rodar coleta nova contra lojas reais: mostrar o `--dry-run` ao dono
  e esperar o "pode".

## Comandos

Windows sem make: `.\sossego.ps1 <alvo>` faz o mesmo que `make <alvo>`.

| Comando | O que faz |
|---|---|
| `make test` | pytest do backend (sem rede) |
| `make dry-run` | plano de coleta da `vigia.toml`: URLs e totais por loja, sem rede |
| `make coletar` | uma rodada de coleta |
| `make worker` | coleta contínua, espalhada ao longo do período de cada loja |
| `make orcamento` | requisições por loja (1 h / 24 h) e estado do breaker |
| `make parar` / `make retomar` | kill switch (cria/remove `dados/PARAR`) |
| `.\sossego.ps1 religar <loja>` | religa loja desligada pelo breaker |

## Mapa de leitura

- `docs/produto-e-fases.md` — o que foi feito, o que falta (registro vivo).
- `docs/fontes/` — reconhecimento de cada loja (fonte, campos, data).
- `docs/decisoes/` — ADRs curtos.
- `vigia.toml` — o que está sendo vigiado.
- `backend/coleta/http.py` — cliente educado (ler antes de mexer em coleta).
- `backend/coleta/estado.py` — estado da coleta em SQLite (`dados/coleta.sqlite3`).
- `backend/coleta/lojas_mvp.py` — lojas, moldes de URL de busca, frequência.
- `backend/coleta/vigiar.py` — CLI/worker; `admin.py` — operação.
- `dados/bruto/<loja>/<dia>/*.json.gz` — resposta crua (landing zone, fora do git).
