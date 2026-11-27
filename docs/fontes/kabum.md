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
| `offer.priceWithDiscount` | 4369.05 | **Pix** com oferta ativa (= `offer.price` × 0,95) | **confirmado** na tela em 27/11 |
| `oldPrice` (= `price`) | 4893.76 | **"de"** riscado | **confirmado** na tela em 27/11 |
| `priceWithDiscount` | 4649.07 | Pix fora de oferta (= `price` × 0,95) | por analogia (não visto na tela) |
| `offer.startsAt`/`endsAt` | epoch | janela da oferta | confirmado (formato) |
| sem juros? | — | não aparece no JSON | **desconhecido** |

## Conferência na tela (27/11/2026, Black Friday, pelo dono)

PS5 989702: **Pix R$ 4.274,05**, **"de" R$ 4.893,76**, **10x de R$ 449,90** (= 4.499,00).
4.274,05 = 4.499,00 × 0,95 exato: o mesmo padrão do JSON de 26/11
(`offer.priceWithDiscount` 4.369,05 = `offer.price` 4.599 × 0,95). A oferta
mudou de um dia para o outro; a estrutura, não.

## Conferência automática (27/11 16:15): NÃO BATEU

A oferta mudou às ~16:00 (`offer.startsAt`). No bruto das 16:15 o 989702 veio com
`offer.price` 4.499 = `offer.priceWithDiscount` 4.499 (sem desconto no JSON),
`oldPrice` 4.649,07 e `discountPercentage` 0. A tela de antes das 16h mostrava
Pix 4.274,05 e "de" 4.893,76. Ou a oferta nova não tem desconto no Pix, ou o
desconto é calculado na página. **Pendente: o dono conferir a tela depois das 16h.**

## O que o parser grava (versão 4, desde 27/11)

- `preco` = preço vigente no cartão (`offer.price` com oferta ativa, senão
  `price`), **só se** o parcelado de `maxInstallment` bater com ele (até
  R$ 0,01 por parcela: a parcela vem arredondada para baixo, ex. MacBook
  20.097,41 em 10x de 2.009,74). Se não bater, não vira oferta e o log registra.
- `preco_pix` = `offer.priceWithDiscount` (oferta ativa) ou `priceWithDiscount`,
  **só quando é menor que o preço no cartão**. Igual ao cartão = None (não confirmado).
- `preco_de` = `oldPrice`, só se for maior que `preco`.
- `parcelas_max`, `parcela_valor`, `em_estoque`, `vendedor`.
- `parcelas_sem_juros`: **None** (a tela conferida não disse).

Versão 1 (26/11): Pix e "de" = None. Versão 2: `preco` = parcelado arredondado,
1-3 centavos abaixo do real (14 ofertas viraram alerta "Pix > preço"). Versão 3
corrige. Versão 4: Pix só com desconto visível no JSON. `historico --tudo` refez tudo.
