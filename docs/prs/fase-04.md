# PR — `fase/04-api` → `fase/03-matching`

A base é a Fase 3, porque as branches são empilhadas. Depois do merge da 03,
a base passa a ser a `main`. No merge, tag `v0.4.0`.

**Título:** Fase 4: API /api/v1 (catálogo, perfil, busca, produto, histórico, vigias, início, saúde)

## O que foi feito
- `api/app.py` e `api/modelos.py`: FastAPI com o contrato em Pydantic. O
  OpenAPI fica em `/docs`. Dinheiro sai como string decimal ("4289.00").
- Rotas: `GET /lojas`, `GET /categorias`, `POST/GET/PUT /perfis`, `GET /busca`,
  `GET /produtos/{id}`, `/historico?periodo=24h|7d|30d|tudo`, `/parecidos`,
  `POST/DELETE /perfis/{id}/vigias/{produto_id}`, `GET /vigias/quedas?desde=`,
  `GET /inicio?perfil=` e `GET /saude`.
- Ficaram para fases seguintes: `/pagamento/simular` (Fase 5, calculadora) e
  `/busca/stream` (Fase 7, só se houver busca ao vivo).
- **Nenhuma rota faz requisição a loja.** A busca lê o histórico (ADR 003).
- Migration 004:
  - perfil anônimo, categorias e as 26 lojas do onboarding com ícone;
  - máximo de 3 categorias e 3 lojas também por trigger;
  - vigia e `busca_log`;
  - as views `oferta_atual` e `preco_diario`;
  - `produto.termos` e `produto.categoria_id`.
- Matching:
  - preenche termos de busca (união dos títulos do produto) e categoria por
    regras;
  - o `--refazer` preserva produto vigiado.
- `situacao_loja()` virou uma função só, usada pelo `status` e pela `/saude`.
- Adminer com profile `ferramentas`, e CI no GitHub Actions (pytest com
  Postgres 16). As duas eram pendências da Fase 1.

## Testado
- 176 testes verdes, entre eles 22 de rota com Postgres real.
- O banco recusa a 4ª categoria e a 4ª loja (trigger), não só a API.
- Três regressões de busca encontradas nos dados reais. Cada uma ganhou um
  teste antes da correção:
  - "controle ps5" trazia carregador de Switch 2;
  - "controle ps5" trazia console e não trazia o DualSense da Amazon;
  - "jogos ps5" trazia "fone para jogos".
- Smoke com uvicorn no banco real: `/saude` e `/openapi.json` (12 rotas).

## Não testado / limites
- O CI só roda depois do push. O primeiro verde dele vai estar no PR.
- Tipo de produto quando o título não diz o tipo (backlog API).
- A ordem das ofertas é provisória; o custo efetivo vem com a calculadora.
- Sem autenticação: a API escuta só em 127.0.0.1.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
