# 002 — Matching por regras explicáveis, com ligação completa

Data: 27/11/2026

**Decisão.** Um anúncio só entra num produto se `decidir()` disser "mesmo"
contra **todos** os anúncios que já estão nele. A decisão vem em camadas:

1. GTIN igual nos dois lados → mesmo, a não ser que o título contradiga.
2. GTIN diferente nos dois lados → diferente.
3. Conflito duro → diferente: tipo (jogo, console, controle, acessório, kit),
   plataforma (Switch × Switch 2 × PS5), capacidade, usado × novo, com console ×
   sem console, digital × disco, pro × slim × fat.
4. Sem conflito e com os mesmos tokens identificadores → mesmo. Antes da
   comparação saem a vitrine ("Jogo", "Edição Standard", "Físico Nacional"), a
   cor, que é variação e não produto, e o código da loja no fim do título.
5. Sobrou palavra de um lado, mas o título é parecido (`token_set_ratio` ≥ 75)
   → parecido, que nunca é agrupado.

Os grupos `[[produto]]` da `vigia.toml` vencem o algoritmo.

**Por quê.** Precisão importa mais que recall: juntar dois produtos diferentes
mostra preço errado, separar só deixa de comparar. Uma regra explicável diz
por que juntou ("GTIN igual", "plataforma ns1 × ns2"), e isso fica em
`anuncio.match_motivo`. Exigir todos os membros evita o efeito corrente:
A≈B e B≈C não junta A com C.

**Evidência (27/11).**
- Conjunto rotulado `tests/fixtures/matching.csv`: 110 pares de títulos reais
  coletados (46 mesmo, 61 diferente, 3 a confirmar). Precisão 1,000, recall
  0,891.
- A validação nos 459 anúncios reais achou dois falsos positivos que viraram
  regressão: bundle com console junto com o jogo avulso, e título sem
  capacidade junto com qualquer capacidade.
- O EAN não é certeza absoluta: a Ri Happy repete 3558387010695 no kit e no
  avulso.

**Consequências.**
- `match_metodo` pode ser `gtin`, `titulo`, `manual` ou `novo`.
- Quando a regra mudar, rodar `.\sossego.ps1 matching --refazer`. Ele apaga
  só os produtos automáticos.
- Quando existir a tabela `vigia (produto_id)` (Fase 4), o `--refazer` vai
  precisar preservar os produtos vigiados.

**Alternativas descartadas.**
- **Só fuzzy com limiar:** juntava "PS5 Digital" com "PS5 com disco" e "FC 27
  Switch" com "FC 27 Switch 2", porque o score fica acima de 90.
- **Ligação simples, pelo membro mais parecido:** é o que cria as correntes.
- **Embeddings ou LLM:** fora de escopo (backlog). Também não seriam
  explicáveis, e o volume não precisa disso.
