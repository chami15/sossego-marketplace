# Produto e fases — registro vivo

Atualizado em 27/11/2026 (Black Friday).

## Feito

- **Fase 0 (enxuta)** — `fase/00-reconhecimento-fontes`
  - Cliente HTTP educado (`coleta/http.py`): orçamento, intervalo + jitter,
    robots.txt, cache, ETag, breaker (bloqueio × molde quebrado), kill switch.
  - Recon: Amazon, Ludopedia, Ri Happy (API VTEX) ok; ML e Magalu bloqueados;
    detecção VTEX em 15 lojas (só Época passou, fora por decisão do dono).
  - Worker em processo próprio + tarefa agendada; captura bruta desde 18:46.
  - ML pela API oficial pronto, aguardando credenciais.
- **Fase 1 (mínima)** — `fase/01-fundacao`
  - Postgres 16 em Docker (porta 5434), migration 001, aplicador com hash.
- **Fase 2 (fechada em 27/11, PR para a main)** — `fase/02-coleta-e-historico`
  - Contrato `Oferta` (Pydantic, Decimal), parsers Amazon/Ludopedia/VTEX.
  - Reprocessamento do bruto → anúncios e snapshots com dedupe, automático no
    fim de cada rodada do worker (falha de banco só loga; o bruto segue).
  - Kabum no worker (eletrônicos, 120 min). Parser v5: preço vigente no
    cartão, Pix de `priceWithDiscount` (conferido na tela 2x em 27/11), sem
    juros pelo parcelado; "de" vazio, porque o da tela não está no JSON
    (`docs/fontes/kabum.md`).
  - Worker em worktree fixo (`..\sossego-worker`), atualizado só por
    `atualizar-worker`; tarefa sem admin (logon + 15 min) via
    `conhost --headless`, sem janela. `pausar`/`retomar`, `desligar`/`ligar`.
  - `status` marca ATRASADA a loja ativa sem coleta ok há mais de 2 períodos.
  - `vigia.toml`: alvo com `lojas = [...]`; grupos `[[produto]]` (anúncios da
    busca agrupados à mão, semente do matching); o `status` mostra a última
    aparição de cada anúncio e destaca o que passou de 2 rodadas fora da busca.
  - Vigiados: ps5, controle ps5, jogos ps5, nintendo switch 2, jogo nintendo
    switch, notebook 16gb ram, macbook (Kabum); dixit (Ludopedia, Ri Happy);
    ito (Ludopedia). ~10 req/h no total.
- **Fase 3 (27/11, PR para revisão)** — `fase/03-matching`
  - `matching/normalizar.py`: título → tokens identificadores, plataforma,
    capacidade, tipo, condição, cor (variação) e com/sem console.
  - `matching/decidir.py`: GTIN → conflitos duros → tokens → "parecido"
    (nunca agrupado). ADR 002.
  - `matching/associar.py`: anúncio → produto com ligação completa; grupos
    `[[produto]]` vencem; roda no fim de cada rodada do worker e por
    `.\sossego.ps1 matching [--refazer]`. Migration 003 (`match_metodo`,
    `match_motivo`, `grupo_manual`, `a_confirmar`).
  - Conjunto rotulado (110 pares reais): precisão 1,000, recall 0,891.
  - Nos dados de 27/11: 459 anúncios → 31 produtos em 2+ lojas.
- **Fase 4 (27/11, PR para revisão)** — `fase/04-api`
  - `api/`: FastAPI em `/api/v1` com as rotas da seção 8, exceto
    `/pagamento/simular` (Fase 5) e `/busca/stream` (Fase 7). Também tem
    `GET /perfis/{id}`. OpenAPI em `/docs`. `.\sossego.ps1 api` sobe em 127.0.0.1:8000.
  - Nenhuma rota faz requisição a loja: a busca lê o histórico (ADR 003).
  - Migration 004: perfil anônimo, categorias, 26 lojas do onboarding com ícone,
    máximo de 3 categorias e 3 lojas também por trigger, vigia, `busca_log`, as
    views `oferta_atual` e `preco_diario`, e `produto.termos`/`categoria_id`,
    que o matching preenche.
  - Card: melhor oferta vista nas últimas 48 h e com estoque; variação contra o
    nosso menor preço de 7 dias atrás, nunca contra o "de" da loja.
  - Adminer (`docker compose --profile ferramentas up -d adminer`) e CI no
    GitHub Actions, as duas pendências da Fase 1.

### Ocorrências da Black Friday (27/11)

- Sem coleta de 26/11 20:00 a 27/11 15:01: PC desligado. Não recuperável.
- 15:11: Amazon respondeu com desafio Akamai (`bm-verify`). Virou marcador de
  bloqueio; o dono desligou a Amazon até segunda 30/11 (migration 002).
- Ri Happy: busca com espaço como `+` (`jogo+ito`) dá HTTP 400; com `%20` dá
  206 (1 requisição de teste, 16:48). Molde passou a usar `%20`. 400 em busca =
  molde quebrado. A Ri Happy não tem o Ito: os 20 resultados são outros jogos.
- Kabum: a oferta do PS5 989702 mudou às ~16:00 (4.599 → 4.499); a tela das
  16:44 confirmou Pix = cartão = 4.499 e 10x sem juros. O "de" da tela (4.893,76)
  não bate com `oldPrice` (4.649,07): parser v5 grava "de" vazio.

## Falta

- Fase 5 (pagamento): calculadora, taxas do BCB e `/pagamento/simular`.
- Fases 6 a 10 (telas, mais lojas, polimento).
- Ajustes pequenos e pendências de loja: `docs/backlog.md`.
