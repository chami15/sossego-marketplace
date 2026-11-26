# 001 — Estado da coleta educada em SQLite local

Data: 26/11/2026

**Decisão.** Log de requisições, orçamento, circuit breaker, cache HTTP e cache
de robots.txt ficam em `dados/coleta.sqlite3`, não no Postgres.

**Por quê.** A trava de segurança precisa funcionar mesmo com o Postgres fora
do ar (hoje o Docker nem está de pé) e sobreviver a reinício do worker: se o
orçamento zerasse a cada restart, ele não protegeria nada. SQLite é stdlib,
zero operação e local à máquina que faz as requisições.

**Consequências.** `coleta_execucao` no Postgres (Fase 1/2) continua sendo a
observabilidade de negócio (itens coletados por execução). `/api/v1/saude` lê
os dois. `loja.coleta_ativa` no Postgres será sincronizado com o breaker
quando o banco existir.

**Alternativa descartada.** Postgres desde já: travaria a coleta de hoje na
subida do Docker e acoplaria a segurança à disponibilidade do banco.
