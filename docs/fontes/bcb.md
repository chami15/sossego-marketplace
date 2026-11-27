# Banco Central — API SGS (taxas da calculadora)

Verificado em 27/11/2026.

- **Fonte:** `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/1?formato=json`.
  API pública, sem chave. A resposta tem este formato:
  `[{"data":"26/11/2026","valor":"13.65"}]`, em `application/json`, com
  `cache-control: public, max-age=900`.
- **Séries usadas:**
  - **4389:** CDI anualizado base 252, em % a.a. Em 27/11 veio 13,65 (data de
    26/11). A busca na web não confirmou o código por catálogo. A conferência
    foi pelo próprio dado: a meta Selic está em 13,75% desde o Copom de 4/11, e
    o CDI costuma ficar 0,10 ponto abaixo dela. Bate.
  - **432:** meta Selic, em % a.a. É só referência e não entra na conta. O
    catálogo de dados abertos do BCB descreve a 432 como "Meta Selic definida
    pelo Copom".
- **robots.txt:** `api.bcb.gov.br/robots.txt` responde 404, o que significa
  sem restrição.
- **Problema encontrado:** em 27/11, a 432 respondeu **HTTP 304 sem corpo nas
  duas tentativas**, 22:20 e 22:26 UTC. Nenhum cabeçalho condicional tinha
  sido enviado, porque não havia cópia em cache. A 4389, pedida do mesmo jeito,
  veio 200.
  - Causa desconhecida; parece coisa do CDN (`x-azure-ref`).
  - O `ClienteEducado` passou a tratar 304 sem cópia como falha transitória:
    sem retry e sem acionar o breaker.
  - A atualização salva o CDI mesmo quando a Selic falha.
- **Frequência:** o worker confere a cada hora e só vai à rede se a última
  atualização tiver mais de 20 h. Na prática, 2 séries por dia mais o robots a
  cada 24 h, sempre pelo `ClienteEducado`, com orçamento e breaker próprios
  (`api.bcb.gov.br`).
