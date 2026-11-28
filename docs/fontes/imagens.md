# Imagens de produto (CDN das lojas)

Verificado em 27/11/2026.

Baixadas uma vez pelo `ClienteEducado` (`backend/coleta/imagens.py`), no worker,
depois da coleta; a tela lê de `GET /api/v1/imagens/<sha1>.webp`, nunca da loja.

- **Quais:** a imagem da melhor oferta de cada produto (a do card) e as dos
  anúncios dos grupos `[[produto]]`. Só de loja com coleta ativa.
- **Ritmo:** chave própria por CDN no breaker (`cdn:<host>`), 30/h e 150/dia,
  mesmos 5 s + jitter, mesmo breaker; robots.txt do CDN respeitado.
- **De novo só se a URL mudar.** Falhou (404, não é imagem): placeholder e nova
  tentativa só depois de 7 dias.
- **Formato:** WebP q80, até 400 px no maior lado.

| CDN | Tamanho pedido | Situação em 27/11 |
|---|---|---|
| `images.kabum.com.br` | sufixo `_g` (o `_original` vira `_g`) | **robots.txt respondeu 403**: breaker abriu; desligado na mão (`cdn:images.kabum.com.br`). Nenhuma imagem. Religar só com decisão do dono. |
| `rihappy.vteximg.com.br` | `/ids/<id>-400-400/` (VTEX redimensiona) | 26 ok, 386–400 px |
| `storage.googleapis.com` (Ludopedia) | o que vem no bruto (`_s`) | 5 ok, só 51–75 px: a busca só traz a capa pequena |

Requisições na primeira passada: robots.txt dos 3 hosts + 31 imagens.
