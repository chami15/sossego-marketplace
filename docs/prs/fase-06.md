# PR — `fase/06-design-system-onboarding` → `fase/05-pagamento`

Base empilhada; depois do merge da 05, a base vira a `main`. No merge, tag `v0.6.0`.

**Título:** Fase 6: design system e onboarding em 3 passos

## O que foi feito
- `frontend/` (Vite + React + TypeScript), proxy `/api` para a API local.
- Design system: tokens do prompt (azul royal, papel, tinta, queda/alta),
  Fraunces nos destaques e Literata no corpo com algarismos tabulares, fontes
  self-hosted. Cantos de 2px; sem pílula, vidro, blur, gradiente ou sombra.
- Componentes: Botao, Escolha (opção única que preenche, sem caixa; caixa só
  na escolha múltipla), BarraProgresso, Aviso, CampoTags, IconeCategoria
  (Lucide) e IconeLoja (monograma; arquivo local se um dia houver).
- Refino do visual: tela dividida 40/60 (painel azul com a pergunta, índice
  de passos e resumo ao vivo com nomes de exibição); categorias em 5 colunas e
  lojas em 4; barra de ações fixa com o aviso "Máximo 3" e tremor no item
  recusado (desligado com `prefers-reduced-motion`); busca de loja; no celular,
  cabeçalho compacto e grade de 2 colunas. Só ícones SVG Lucide (regra 11).
- Onboarding: faixa etária (obrigatória) e gênero (opcional) com a linha da
  LGPD; até 3 categorias e termos em tags; até 3 lojas ou "Não tenho
  preferência". Na 4ª escolha, aviso "Máximo 3" e nada sai sozinho. Erro ao
  salvar mantém as escolhas. "Refazer preferências" atualiza o mesmo perfil.
- Os termos ficam no perfil e não disparam coleta (decisão do dono, 27/11).
- `backend/db/recriar.py`: recria `*_test`/`*_e2e` do zero; o conftest usa.

## Testado
- 6 testes e2e com a API real (`sossego_e2e`): fluxo completo com os limites e
  o perfil conferido no banco; refazer no mesmo perfil; falha ao salvar e nova
  tentativa; erro ao carregar desabilita o Avançar; regressão do estouro de
  largura no celular; navegação por teclado.
- 211 testes do backend (inclui a trava do `recriar` contra o banco principal
  e os testes do baixador de ícones).
- 22 prints em `docs/prints/fase-06/` (1440 e 390 px), conferidos um a um.

## Não testado / limites
- Ícones das lojas: monogramas. O baixador pelo serviço de favicons do Google
  está pronto, mas o robots.txt do Google proíbe `/s2`: parou na 1ª requisição
  (o robots) e nada foi baixado. Fonte alternativa = decisão do dono.
- Leitor de tela real (NVDA) não foi usado; só papéis ARIA conferidos no e2e.
- Nos prints de página inteira, barra e rodapé fixos entram no fluxo só durante
  a captura; na tela eles ficam fixos.
- Ao concluir, vai para a página inicial (Fase 7).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
