# PR — `fase/07-inicio-e-busca` → `fase/06-design-system-onboarding`

Base empilhada; depois do merge da 06, a base vira a `main`. No merge, tag `v0.7.0`.

**Título:** Fase 7: página inicial, card de produto e busca

## O que foi feito
- Home: capa azul com "O que você quer comprar hoje?" e busca com
  autocomplete das buscas recentes (localStorage, `datalist` nativo); seções
  De olho, Pra você e Caiu de preço (sem repetir produto); chips de categoria.
- Card: imagem 1:1, título em 2 linhas, menor preço em Fraunces, Pix quando
  menor, ícone e nome da loja, "+N lojas a partir de R$ X", selo de variação
  com seta e % contra o nosso histórico. O card inteiro é o link.
- Busca `/busca`: ordenação e filtros (loja, faixa de preço) no topo, guardados
  na URL; situação de cada loja coletada; estado vazio e de erro.
- API: `GET /api/v1/busca?categoria=` lista a categoria sem termo (chips).
- Tela de produto provisória (ofertas + "Ver na loja"); a página é a Fase 8.
- `backend/db/semente_e2e.py`: banco do e2e com anúncios fictícios.

## Testado
- 212 testes do backend (novo: busca por categoria, termo + categoria, 422).
- 20 testes Playwright: os 6 do onboarding + 6 da busca (busca → card →
  produto, ordenar/filtrar, home e categoria, vazio, autocomplete, regressão
  de largura no celular) + os prints.
- 14 prints em `docs/prints/fase-07/` (1440 e 390 px), conferidos.

## Não testado / limites
- Imagens dos produtos desligadas (seriam pedidas ao CDN da loja); no lugar,
  o ícone da categoria. Decisão do dono (backlog).
- "Só com estoque" não entrou: o card já exige estoque nas últimas 48 h.
- A situação das lojas é a da coleta, não progresso ao vivo (ADR 003).
- "De olho" fica vazio até existir o botão de vigiar (Fase 8).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
