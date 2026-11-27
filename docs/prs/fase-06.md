# PR — `fase/06-design-system-onboarding` → `fase/05-pagamento`

Base empilhada; depois do merge da 05, a base vira a `main`. No merge, tag `v0.6.0`.

**Título:** Fase 6: design system e onboarding em 3 passos

## O que foi feito
- `frontend/` (Vite + React + TypeScript), proxy `/api` para a API local.
- Design system: tokens do prompt (azul royal, papel, tinta, queda/alta),
  Fraunces nos destaques e Literata no corpo com algarismos tabulares, fontes
  self-hosted. Cantos de 2px; sem pílula, vidro, blur, gradiente ou sombra.
- Componentes: Botao, Chip, BarraProgresso, Aviso, CampoTags, IconeCategoria
  e IconeLoja (arquivo local em `public/lojas/`; monograma enquanto não há).
- Onboarding: faixa etária (obrigatória) e gênero (opcional) com a linha da
  LGPD; até 3 categorias e termos em tags; até 3 lojas ou "Não tenho
  preferência". Na 4ª escolha, aviso "Máximo 3" e nada sai sozinho. Erro ao
  salvar mantém as escolhas. "Refazer preferências" atualiza o mesmo perfil.
- Os termos ficam no perfil e não disparam coleta (decisão do dono, 27/11).
- `backend/db/recriar.py`: recria `*_test`/`*_e2e` do zero; o conftest usa.

## Testado
- 4 testes e2e com a API real (`sossego_e2e`): fluxo completo com os limites e
  o perfil conferido no banco; refazer no mesmo perfil; falha ao salvar e nova
  tentativa; navegação por teclado.
- 208 testes do backend (inclui a trava do `recriar` contra o banco principal).
- 20 prints em `docs/prints/fase-06/` (1440 e 390 px), conferidos um a um.

## Não testado / limites
- Ícones das lojas: monogramas. Baixar os favicons é requisição a loja e espera
  o "pode" do dono.
- Leitor de tela real (NVDA) não foi usado; só papéis ARIA conferidos no e2e.
- Nos prints de página inteira, barra e rodapé fixos entram no fluxo só durante
  a captura; na tela eles ficam fixos.
- A tela depois do onboarding é provisória; a página inicial é a Fase 7.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
