# Kabum

Verificado em **26/11/2026, 19h25 (BRT)**: 1 busca (`/busca/ps5`), 200, 439 KB,
sem bloqueio. robots.txt proíbe `/busca/*?`; `/busca/<termo-com-hifens>` é permitido.

## Fonte

`<script id="__NEXT_DATA__">` → `props.pageProps.data` (string JSON) →
`catalogServer.data` (36 produtos). Também há JSON-LD `ItemList`/`Product`
com `price` = campo `price` da raiz.

Os preços visíveis dos cards **não** estão no HTML do servidor (são
renderizados por JavaScript). Por isso a comparação abaixo é entre campos do
JSON, não contra a tela.

## Campos (exemplo: PS5 código 989702)

| Campo | Valor | Significado | Status |
|---|---|---|---|
| `code` | 989702 | id do produto | confirmado |
| `name`, `friendlyName` | ... | título e slug da URL `/produto/<code>/<friendlyName>` | confirmado |
| `available`, `quantity` | true, 314 | em estoque | confirmado |
| `sellerName` | KaBuM! | vendedor | confirmado |
| `maxInstallment` | "10x de R$ 459,90" | parcelamento máximo exibido | confirmado (texto literal) |
| `offer.price` | 4599 | preço vigente no cartão quando há oferta ativa | **forte**: 10 × 459,90 = 4.599,00 exato |
| `offer.priceWithDiscount` | 4369.05 | preço à vista (= 4599 × 0,95) | **hipótese**: Pix? boleto? não confirmado |
| `price`, `oldPrice` | 4893.76 | preço fora da oferta / "de" | **hipótese** |
| `priceWithDiscount` | 4649.07 | à vista fora da oferta (= 4893,76 × 0,95) | **hipótese** |
| `offer.startsAt`/`endsAt` | epoch | janela da oferta | confirmado (formato) |
| sem juros? | — | não aparece no JSON | **desconhecido** |

## O que o parser grava hoje (versão 1)

- `preco` = total parcelado (`n × valor` de `maxInstallment`), **só se** bater
  (±R$ 0,05) com o preço vigente (`offer.price` com oferta ativa, senão `price`).
  Se não bater, o produto não vira oferta e o log registra.
- `parcelas_max`, `parcela_valor`, `em_estoque`, `vendedor`.
- `preco_pix`, `preco_de`, `parcelas_sem_juros`: **None** até confirmar.

## Para confirmar (sem requisição nossa)

Abrir no seu navegador um produto que o worker acabou de coletar e comparar
o "à vista no Pix" e o "de" da tela com os campos do bruto daquela hora.
Confirmado, sobe `PARSER_VERSAO["kabum"]` e `--tudo` reprocessa o bruto.
