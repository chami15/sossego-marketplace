# Fontes — reconhecimento mínimo (Fase 0 enxuta)

Verificado em **26/11/2026, ~18h45 (BRT)**, do IP residencial do dono, via
`ClienteEducado` (curl_cffi, impersonate chrome). Total: **12 requisições**
(5 robots.txt + 7 buscas). Sem Playwright nesta rodada.

| Loja | Fonte | Resultado | Campos vistos | Dificuldade | No worker? |
|---|---|---|---|---|---|
| Amazon | HTML da busca (`/s?k=`) | 200, 1,6 MB, 60 resultados | ASIN, título, preço ("a-offscreen"), patrocinado | médio (risco de captcha) | sim, 120 min |
| Ludopedia | HTML da busca (`/search?search=`) | 200, 137 KB | jogo, ano, nota, menor preço Ludostore (boleto) | fácil | sim, 60 min |
| Ri Happy | API VTEX `api/catalog_system/pub/products/search?ft=` | **206**, JSON 529 KB | id, nome, Price, ListPrice, estoque, **EAN** | fácil | sim, 60 min |
| Mercado Livre | HTML `lista.mercadolivre.com.br` | 200, mas **interstício anti-robô** (17 KB, "requires JavaScript") | nenhum | — | **não**: aguarda API oficial |
| Magalu | HTML `/busca/<termo>/` | **403** na 1ª busca | nenhum | difícil | **não**: bloqueou = parou |

## Observações

- **Ri Happy:** o robots.txt proíbe `/*?_q=` (busca HTML). O `ClienteEducado`
  barrou a URL antes de sair. A API pública VTEX não está proibida e é bem mais
  leve. Plataforma VTEX confirmada, então o adaptador genérico `plataformas/vtex.py` é viável.
  O mesmo EAN aparece em anúncios com preços diferentes (vendedores/edições),
  bom caso para o matching.
- **Mercado Livre:** a página de busca HTML devolve um interstício "Continuar /
  This page requires JavaScript". Não tentamos outro caminho (seria contornar).
  Próximo passo: app em developers.mercadolivre.com.br com token de aplicação.
- **Magalu:** 403 de cara. Pausada pelo breaker e marcada como inativa. Não volto
  a tentar sem decisão do dono.
- **Amazon:** sem JSON-LD na busca. Parser vai por seletores (`data-asin`,
  `s-search-result`, `a-offscreen`). Os primeiros resultados são "Anúncio
  patrocinado", que o parser precisa marcar.
- **Ludopedia:** sem JSON-LD. É catálogo de jogos + preço da Ludostore. As
  páginas `/jogo/<slug>` são as candidatas a URL direta.

Fixtures (respostas reais, gzip): `backend/tests/fixtures/<loja>/`.

## Recomendação de MVP

Amazon, Ri Happy (VTEX) e Ludopedia agora; Mercado Livre quando houver
credencial. Magalu só com nova estratégia aprovada (e sem contornar bloqueio).
Restante do recon (Kabum, PBKids, outras VTEX...) depois da Black Friday.
