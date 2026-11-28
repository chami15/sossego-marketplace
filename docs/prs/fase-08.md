# PR — `fase/08-pagina-produto` → `fase/07-inicio-e-busca`

Base empilhada; depois do merge da 07, a base vira a `main`. No merge, tag `v0.8.0`.

**Título:** Fase 8: página de produto, card de vitrine e imagens locais

## O que foi feito
- Correções da Fase 7: formatador único de dinheiro (`Intl.NumberFormat`
  pt-BR; "R$ 4.289,00", nunca "4.289.00") com teste; Fraunces só em título de
  página e preço, títulos de card em Literata.
- Card de vitrine: grade 6/4/2 colunas; imagem 1:1 em fundo `#F2F3F5`, produto
  inteiro (`contain`); selo de variação sobre o nosso histórico; preço com
  centavos sobrescritos (texto acessível com vírgula); Pix em verde quando
  menor; título em 2 linhas; loja e "+N lojas a partir de"; botão vigiar
  quadrado (olho) no canto, que não abre o produto. Sem imagem: ícone da categoria.
- Imagens: `backend/coleta/imagens.py` baixa pelo `ClienteEducado` (chave de
  breaker e orçamento próprios por CDN, 30/h e 150/dia, robots.txt do CDN),
  só as de card e de `[[produto]]`, uma vez por URL, em WebP de até 400 px.
  O worker roda a cada 30 min, depois da coleta. API serve em `/api/v1/imagens/`.
  Migration 006 (`imagem_baixada`).
- Logos das lojas do `simple-icons` (CC0, local); exceção registrada na regra 11.
- Página de produto: galeria, título e marca, seletor de variação, melhor
  oferta com "Comprar na X por R$ Y", tabela de ofertas por custo efetivo com
  "Ir para a loja" (nova aba, `noopener`), sobre o produto; lateral com o
  gráfico de preço (degrau por loja + faixa do menor geral, período, mira com
  tooltip, tabela), "Menor preço que vimos", "Ficar de olho" com preço-alvo e
  a calculadora Pix × parcelado; "Você também pode gostar".
- API: `GET /perfis/{id}/vigias`; `imagem_local` em card e oferta.

## Testado
- 231 testes do backend (novos: orçamento por chave, imagem fora do bruto e do
  cache, HTML no lugar de imagem = molde quebrado, 13 de imagens com a
  regressão do dry-run com CDN desligado, rota de imagem, vigias do perfil, regressão do status com CDN desligado).
- 21 testes Playwright (9 novos: produto → Ir para a loja, frete no custo,
  variação, gráfico, um ponto só, ficar de olho, vigiar no card, calculadora,
  parecidos) + regressão de largura no celular também na página de produto.
- 5 testes unitários do formatador (`npm run test:unit`).
- Prints em `docs/prints/fase-08/` (1440 e 390 px), conferidos.

## Não testado / limites
- Kabum sem imagens: o robots.txt do CDN respondeu 403; desligado (backlog).
- Capas da Ludopedia pequenas (só existe o `_s` na busca).
- "De" riscado fora: o dado não é confiável ainda.
- Descrição e especificações só aparecem quando o parser gravar.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
