# PR — `fase/03-matching` → `fase/02-coleta-e-historico`

A base é a Fase 2, porque as branches são empilhadas. Depois do merge da 02,
a base passa a ser a `main`. No merge, tag `v0.3.0`.

**Título:** Fase 3: matching de produto (normalização, GTIN, regras, conjunto rotulado)

## O que foi feito
- `matching/normalizar.py`: transforma o título nos tokens que identificam o
  produto e separa plataforma, capacidade, tipo, condição, cor (variação) e
  com/sem console. Tira o código da loja do fim do título, a vitrine e o
  marketing.
- `matching/decidir.py`: GTIN, depois conflitos duros, depois tokens. A faixa
  cinzenta vira "parecido" e nunca é agrupada (ADR 002).
- `matching/associar.py`: liga anúncio a produto com ligação completa (o
  anúncio precisa ser "mesmo" que todos os membros). Os grupos `[[produto]]`
  vencem o algoritmo. É idempotente e tem `--refazer`. Migration 003.
- O worker roda o matching no fim de cada rodada; há também
  `.\sossego.ps1 matching`.

## Testado
- 141 testes verdes (Postgres real).
- Conjunto rotulado com 110 pares de títulos reais: precisão 1,000, recall
  0,891. A meta era precisão ≥ 0,95.
- Validação fora do gabarito: `decidir()` em todos os pares dos 459 anúncios
  reais. Os dois falsos positivos encontrados viraram regressão antes da
  correção.
- Nos dados reais: 459 anúncios viraram produtos, 31 deles em 2+ lojas.

## Não testado / limites
- Os rótulos do gabarito são meus, a partir dos títulos; o dono ainda não
  revisou.
- Ainda ambíguos: Dixit base, já marcado como a confirmar, e Dixit Disney
  (backlog).
- A cor ainda não é gravada em `anuncio.variacao` (backlog, Fase 8).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
