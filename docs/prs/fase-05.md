# PR — `fase/05-pagamento` → `fase/04-api`

A base é a Fase 4, porque as branches são empilhadas. Depois do merge da 04,
a base passa a ser a `main`. No merge, tag `v0.5.0`.

**Título:** Fase 5: calculadora Pix × parcelado, taxas do Banco Central e /pagamento/simular

## O que foi feito
- `pagamento/calculo.py`: funções puras, só com Decimal.
  - Calcula a taxa líquida mensal a partir do CDI, com %CDI e IR, e o VP das
    parcelas, no ato ou em 30 dias.
  - Calcula o custo efetivo (VP − cashback), o desconto de equilíbrio e a TIR
    do parcelado com juros.
  - O IR regressivo segue o prazo de cada opção.
  - Gera as opções (Pix e 1x..Nx sem juros, ou Pix × plano com juros), ordena
    pelo custo efetivo e dá a recomendação em uma frase.
- `pagamento/taxas.py`: CDI (SGS 4389) e Selic (432) pelo `ClienteEducado`,
  gravados em `taxa_referencia` (migration 005).
  - O worker confere a cada hora e só vai à rede com mais de 20 h desde a
    última atualização.
  - Pausado ou desligado, não pede nada.
  - Falha não derruba o worker: fica a última taxa, e a API mostra a data dela.
- `POST /api/v1/pagamento/simular`: os percentuais vão em %. Sem rendimento
  informado, usa o último CDI salvo; sem nenhum salvo, responde 503.
- `docs/fontes/bcb.md`: a conferência das séries.

## Testado
- 207 testes verdes.
- Os 4 casos de aceitação do prompt:
  - equilíbrio de 4,63% com a 1ª parcela no ato;
  - equilíbrio de 5,64% com a 1ª parcela em 30 dias;
  - Pix sem desconto → parcelar;
  - juros de 3% a.m. contra rendimento de 1% → Pix.
- As frases do exemplo do prompt, número por número ("~R$ 44").
- BCB real (27/11), 4 requisições no total:
  - robots.txt: 404;
  - 4389: 13,65%, de 26/11;
  - 432: 304 sem corpo, duas vezes.
- O código 4389 foi conferido pelo dado: CDI 13,65 contra a meta Selic de 13,75.

## Bug achado e corrigido
- O `ClienteEducado` devolvia corpo vazio quando a loja respondia 304 sem
  termos cópia em cache. Agora isso é falha transitória, sem retry e sem
  breaker. O teste de regressão foi escrito antes da correção.
- A atualização de taxas salva o CDI mesmo se a Selic falhar (regressão).

## Não testado / limites
- Por que a 432 responde 304 (backlog). A Selic não entra na conta.
- As ofertas da rota de produto ainda não são ordenadas pelo custo efetivo
  (fica para a Fase 8, com a tela).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
