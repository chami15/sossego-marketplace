# Produto e fases — registro vivo

Atualizado em 26/11/2026 (véspera da Black Friday).

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
  - Reprocessamento do bruto → anúncios e snapshots com dedupe.

## Falta (depois da BF)

- API, web, adminer, CI (Fase 1 completa).
- Rodar `historico` periodicamente (hoje é manual: o bruto é a fonte da verdade).
- Matching (Fase 3), calculadora (Fase 5), telas.
- Ver `docs/backlog.md`.
