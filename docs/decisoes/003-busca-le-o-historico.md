# 003 — A busca da API lê o histórico; não dispara coleta

Data: 27/11/2026

**Decisão.** `GET /api/v1/busca` e as outras rotas só leem e gravam o
Postgres. Nenhuma rota faz requisição a loja. O que é coletado continua
definido pela `vigia.toml` e pelo worker, com o `ClienteEducado`.

**Por quê.** Coleta que nasce de uma busca na tela tira do dono o controle do
volume. Cada tecla viraria requisições em várias lojas, fora do orçamento
planejado e sem o `--dry-run` que a regra de coleta segura exige. O IP é
residencial: o risco de banimento não compensa. A resposta também fica rápida
e previsível, sem esperar nenhuma loja.

**Consequências.**
- A resposta diz `"fonte": "historico"`. Produto que o coletor nunca viu não
  aparece.
- `/busca/stream` (SSE por loja, Fase 7) só faz sentido se a busca ao vivo for
  aprovada.
- O prompt diz que "os termos do onboarding já disparam a primeira coleta (e
  entram em vigia)". Eles ficam só em `perfil_interesse` (decisão do dono,
  27/11). Com multiusuário, viram sugestões de vigia que só entram no worker
  com aprovação.

**Alternativa descartada.** Busca ao vivo na API com o cliente educado: o
orçamento por loja (60/h) acabaria em poucas buscas, e a tela ficaria
esperando a loja mais lenta.
