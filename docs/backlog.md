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

## Produto
- Login e conta.
- Notificação push/e-mail/WhatsApp de queda de preço (`/vigias/quedas` prepara).
- App mobile; cupons; LLM na recomendação; integração com o hubbia.
- Histórico anterior à primeira coleta (não existe e não vamos inventar).
