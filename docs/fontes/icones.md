# Ícones das lojas (onboarding)

Verificado em 27/11/2026.

- **Plano do dono:** baixar uma vez pelo serviço de favicons do Google
  (`https://www.google.com/s2/favicons?domain=<dominio>&sz=128`), pelo
  `ClienteEducado`, sem nenhuma requisição às lojas (`backend/coleta/icones.py`).
- **Resultado:** bloqueado pelo robots.txt. O `robots.txt` de `www.google.com`
  (HTTP 200) tem, em `User-agent: *`, a regra `Disallow: /s2`. Os `Allow`
  dessa área cobrem só `/s2/profiles`, `/s2/oz`, `/s2/photos`,
  `/s2/search/social` e `/s2/static`; `/s2/favicons` não está entre eles.
- **Requisições feitas:** 1, só o `robots.txt`. O cliente recusou o primeiro
  ícone (`BloqueadaPorRobots`) e o script parou ali, sem tentar os outros.
- **Hoje:** a tela mostra monogramas (iniciais da loja) para as 26 lojas.
- **Pendente:** decisão do dono sobre outra fonte (backlog).
