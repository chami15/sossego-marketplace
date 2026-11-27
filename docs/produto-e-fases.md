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
- **Fase 2 (parcial)** — `fase/02-coleta-e-historico`
  - Contrato `Oferta` (Pydantic, Decimal), parsers Amazon/Ludopedia/VTEX.
  - Reprocessamento do bruto → anúncios e snapshots com dedupe, automático no
    fim de cada rodada do worker (falha de banco só loga; o bruto segue).
  - Kabum no worker (eletrônicos, 120 min). Parser v4: preço vigente no
    cartão, "de" e Pix conferidos na tela em 27/11; Pix só quando o JSON mostra
    desconto (`docs/fontes/kabum.md`).
  - Worker em worktree fixo (`..\sossego-worker`), atualizado só por
    `atualizar-worker`; tarefa sem admin (logon + 15 min) via
    `conhost --headless`, sem janela. `pausar`/`retomar`, `desligar`/`ligar`.
  - `status` marca ATRASADA a loja ativa sem coleta ok há mais de 2 períodos.

### Ocorrências da Black Friday (27/11)

- Sem coleta de 26/11 20:00 a 27/11 15:01: PC desligado. Não recuperável.
- 15:11: Amazon respondeu com desafio Akamai (`bm-verify`). Virou marcador de
  bloqueio; o dono desligou a Amazon até segunda 30/11 (migration 002).
- Ri Happy: busca com espaço (`jogo ito`) dá HTTP 400; termo com espaço fora
  da Ri Happy até confirmar a codificação. 400 em busca = molde quebrado.
- Kabum: a oferta do PS5 989702 mudou às ~16:00; o JSON novo não mostra desconto
  no Pix. Pendente: conferir a tela.

## Falta (depois da BF)

- API, web, adminer, CI (Fase 1 completa).
- Kabum: conferir o Pix da oferta nova (Pix = cartão no JSON) e decidir o parser.
- Ri Happy: codificação de termo com espaço (`%20`, 1 requisição de teste) ou só `ito`.
- Molde quebrado pausar só a URL, não a loja (debate).
- Fechar as conexões SQLite (`Estado`): ResourceWarning nos testes, inofensivo.
- Matching (Fase 3), calculadora (Fase 5), telas.
- Ver `docs/backlog.md`.
