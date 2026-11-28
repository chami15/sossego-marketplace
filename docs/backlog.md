# Backlog (fora do escopo agora)

## Coleta
- **Magalu: uma única tentativa manual depois da Black Friday.** Em 26/11/2026
  a 1ª busca HTML (`/busca/ps5/`) deu 403. Uma requisição, com o dono olhando;
  se bloquear de novo, fica fora de vez até haver fonte oficial. Nada de
  contornar.
- **Amazon: desligada até segunda 30/11; o dono decide se faz 1 tentativa manual.**
  Em 27/11/2026 15:11 (Black Friday) a busca `jogo ito` voltou 200 com o desafio
  do Akamai Bot Manager (`bm-verify`, POST `/_sec/verify`, prova de trabalho).
  O dono desligou na hora (`ativa=False` + migration 002), sem esperar o
  breaker. Se a tentativa de segunda vier com desafio, fica fora; nada de
  contornar. Antes disso, 4 buscas boas em 26/11 (bruto e snapshots ficam).
- **Fast Shop: avaliar depois da BF.** Em 26/11/2026 a API VTEX deu 503 nas
  3 tentativas (1 + 2 retries). Uma nova sondagem, com o dono olhando.
- **Carrefour: avaliar depois da BF.** Em 26/11/2026 a API VTEX deu 403
  (bloqueio). Só tentar de novo com decisão do dono; nada de contornar.
- Mercado Livre pelo HTML: não. Só pela API oficial.
- Recon do restante da lista (Casas Bahia, Americanas, Shopee...).
- Uma fonte só para "loja ativa": hoje é `lojas_mvp.py` (o worker obedece) e
  `loja.coleta_ativa` no Postgres (espelho, atualizado por migration).
- **Parser de página de produto** (depois da BF, decisão do dono em 27/11): hoje
  só a busca é lida; URL direta na `vigia.toml` não teria preço. Exige recon
  por loja + `--dry-run` + "pode".
- Kabum: de onde vem o "de" da tela (4.893,76 em 27/11 não está no JSON da
  busca; página de produto? só com recon + "pode").
- Molde quebrado pausar só a URL, não a loja inteira (debate).
- Fechar as conexões SQLite (`Estado`): ResourceWarning nos testes, inofensivo.

## Matching
- Gravar a cor (já extraída por `normalizar`) em `anuncio.variacao` quando a
  loja não manda; o seletor de variação da Fase 8 precisa disso.
- Dixit Disney: a Ri Happy tem dois EAN (3558380106944 e 3558387010077) e o
  matching juntou o Ludopedia "Dixit: Disney" com o de EAN 3558387010077 pelo
  título. Confirmar edição, como no Dixit base.
- Recall: casos que ficam separados (Sports Resort com descrição no título,
  MacBook com specs escritas de outro jeito, Acer Aspire 5 com o modelo em
  ordem diferente). Só mexer com par rotulado novo, sem perder precisão.

## Frontend
- **Imagens da Kabum: decisão do dono.** Na tentativa manual de 27/11 (21:29),
  o robots.txt de `images.kabum.com.br` deu 403 de novo e a imagem deu 200
  (`docs/fontes/imagens.md`). Para o worker baixar as ~298, a chave
  `cdn:images.kabum.com.br` precisaria tratar robots 403 como ausente (RFC 9309),
  no ritmo de sempre (30/h, 150/dia). Até lá: desligado, placeholder.
- Capas da Ludopedia pequenas (51–75 px): a busca só traz o `_s`. Tamanho maior
  exigiria a página do produto (recon + "pode").
- Preço "de" riscado no card: fora até o dado ser confiável (o "de" da Kabum
  não bate com o JSON; parser v5 grava vazio).
- Cor da loja no gráfico de preço segue a ordem alfabética das lojas DAQUELE
  produto: a mesma loja pode ter cor diferente em outro produto. Fixar uma cor
  por loja exige paleta validada maior que 3 (a skill corta em 3 nos pares todos).
- Página de produto: galeria só com a imagem de cada oferta (uma por loja);
  descrição e especificações aparecem quando o parser gravar (hoje vazias).
- Calculadora: com 1 parcela e Pix = cartão ela ainda aparece (diz "pague no
  cartão em 1x"); talvez esconder quando não há escolha real.
- Filtro "só com estoque" (Tela 2 do prompt) não entrou: o card já exige
  oferta em estoque vista nas últimas 48 h, então o filtro não mudaria nada.
- Situação das lojas na busca é a da coleta (`/saude`), não um progresso ao
  vivo: a busca lê só o histórico (ADR 003), nenhuma loja é consultada.

## Vigia
- Kabum "jogos ps5" (27/11 20:03): dos 10 primeiros, só 1 é jogo (GTA VI);
  o resto é console e controle. Trocar o termo ou a ordenação muda a
  `vigia.toml`: precisa de `--dry-run` e do "pode" do dono.

## Pagamento
- BCB série 432 (Selic) respondeu 304 sem corpo em 27/11 (`docs/fontes/bcb.md`).
  Se continuar, investigar os cabeçalhos do curl_cffi. A Selic é só referência.

## API
- Tipo de produto quando o título não diz: "Sony PlayStation 5 Edição Digital
  825GB 1 Controle" (Amazon) não aparece em "console ps5". "Drive de Disco
  para Console" e "PlayStation Portal Para Console" aparecem; "Analógico
  DualSense" (peça) aparece em "controle ps5". Só mexer em `TIPOS` com par
  rotulado, porque o matching também usa.
- `starlette.testclient` avisa que vai trocar `httpx` por `httpx2`. É só aviso,
  sem efeito hoje.

## Produto
- Termos do onboarding **não** disparam coleta (decisão do dono, 27/11): ficam
  em `perfil_interesse`. Quando houver multiusuário, viram uma fila de
  "sugestões de vigia" que só entra no worker com aprovação do dono.
- Login e conta.
- Notificação push/e-mail/WhatsApp de queda de preço (`/vigias/quedas` prepara).
- App mobile; cupons; LLM na recomendação; integração com o hubbia.
- Histórico anterior à primeira coleta (não existe e não vamos inventar).
