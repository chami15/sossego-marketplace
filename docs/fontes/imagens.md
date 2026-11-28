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
| `images.kabum.com.br` | sufixo `_g` (o `_original` vira `_g`) | **robots.txt responde 403**, mas a imagem responde 200 (ver abaixo). Desligado (`cdn:images.kabum.com.br`) até o dono decidir. 1 imagem baixada. |
| `rihappy.vteximg.com.br` | `/ids/<id>-400-400/` (VTEX redimensiona) | 26 ok, 386–400 px |
| `storage.googleapis.com` (Ludopedia) | o que vem no bruto (`_s`) | 5 ok, só 51–75 px: a busca só traz a capa pequena |

Requisições na primeira passada: robots.txt dos 3 hosts + 31 imagens.

## Kabum: tentativa manual (27/11, 21:29, autorizada pelo dono)

`python -m coleta.imagens --tentativa-manual images.kabum.com.br`: 1 robots.txt
+ 1 imagem, sem retry, com chave de breaker própria (`manual:<host>`), então a
chave do worker ficou desligada o tempo todo.

| Requisição | Resposta |
|---|---|
| `GET /robots.txt` | 403 (de novo; a 1ª foi às 20:46) |
| `GET /produtos/fotos/1002659/...cp000037nsw_1771524546_g.jpg` | 200, JPEG, 395×395 |

Leitura: a CDN serve as imagens e só não serve o robots.txt (RFC 9309: 4xx no
robots = "indisponível", que libera). Mesmo assim o CDN continua desligado: o
worker trata robots 401/403 como bloqueio, e mudar isso para esse host é
decisão do dono (backlog).