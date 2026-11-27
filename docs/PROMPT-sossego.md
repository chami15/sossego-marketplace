# Projeto Sossego — analisador e comparador de preços

> Prompt para o Claude Code. O repositório já existe: `github.com/chami15/sossego` (vazio). Você trabalha dentro dele.

---

## 0. Contexto e a dor

Sou o Bernardo (`chami15`), engenheiro de dados. Python é a minha casa; conheço Postgres, Docker e JS/TS.

A dor: quero comprar um produto (um PS5, um jogo de tabuleiro como o Dixit) e preciso abrir 50 abas — Amazon, Mercado Livre, Magalu, Ri Happy... No fim já não lembro qual preço era de onde. Cada site ainda me empurra mais sugestões, e eu me perco.

**Sossego** resolve isso: **uma busca, todas as lojas, o histórico de preço e a melhor forma de pagar, tudo numa tela só.** O nome é a promessa: comprar em paz.

**Urgência:** a Black Friday é **amanhã (27/11/2026)**. Não existe histórico de preço antes de hoje: ele começa na primeira coleta. Por isso a **Fase 2 (coleta + snapshots) tem prioridade sobre tudo que é visual**. Quero o coletor rodando HOJE à noite para gravar a linha de base pré-Black Friday dos produtos que eu cadastrar. A interface pode vir depois. O dado perdido de hoje não volta.

---

## 1. Como você vai trabalhar (leia antes de codar)

1. **Debate antes de construir.** Em decisão de design ou arquitetura que não esteja fechada aqui: proponha, explique o porquê e as alternativas, e espere meu "pode". Correção pontual e o que já está definido aqui: faça direto.
2. **Fases pequenas, cada uma testada.** Cada fase tem branch própria, commits por módulo e testes verdes antes do merge (ver seção 9).
3. **Pesquise antes de afirmar.** Sites mudam toda semana. Nada de "a Magalu usa X" de memória: abra, inspecione, confirme e registre a data da verificação.
4. **Honestidade.** Diga o que testou e o que não testou. Se algo falhou, mostre a saída. "Compilou" não é "testado".
5. **Bug achado = teste de regressão antes da correção.** Nome: `test_regressao_<o_que_quebrava>`.
6. **Nunca** pule, desabilite ou afrouxe um teste para ficar verde.
7. **Segredo nunca no git:** `.env` + `.env.example` comentado + `.gitignore`.
8. **Migration aplicada nunca se edita**: crie a próxima, numerada.
9. Crie um `AGENTS.md` na raiz (≤120 linhas) com estes princípios, os comandos e o mapa de leitura, e um `CLAUDE.md` que só importa ele (`@AGENTS.md`). Regra nova só entra lá se um agente errou de verdade sem ela.
10. Docs, nomes de domínio e mensagens de commit em **português**. Comentários explicam o **porquê**, não o quê.

---

## 2. Arquitetura (decidida; questione se achar algo melhor)

**Monolito modular**, não microsserviços. É um usuário, um time de uma pessoa e um domínio coeso: microsserviço aqui é só custo de operação. Mas com **dois processos** saindo do mesmo código:

```
┌─────────────┐      ┌──────────────────────────────┐      ┌──────────────┐
│  frontend   │─────▶│  api  (FastAPI, /api/v1)     │─────▶│              │
│ React+Vite  │      │  busca sob demanda, produto, │      │  PostgreSQL  │
└─────────────┘      │  calculadora, perfil         │      │     16       │
                     └──────────────────────────────┘      │  (+pg_trgm)  │
                     ┌──────────────────────────────┐      │              │
                     │  worker (APScheduler)        │─────▶│              │
                     │  re-coleta periódica dos     │      └──────────────┘
                     │  produtos vigiados + taxas   │
                     └──────────────────────────────┘
```

| Camada | Escolha | Por quê |
|---|---|---|
| Backend | Python 3.13 + FastAPI + Pydantic v2 | Minha stack; async nativo para disparar N lojas em paralelo |
| Acesso a dados | **psycopg 3 + SQL em arquivos `.sql`** + pool | SQL explícito, sem ORM. Igual ao que uso no hubbia, então já sei manter |
| HTTP de coleta | `httpx` (APIs) + **`curl_cffi`** com `impersonate="chrome"` (sites com anti-bot) | `requests`/`httpx` são barrados no handshake TLS em sites com WAF. O `curl_cffi` imita a impressão digital TLS/HTTP2 do Chrome |
| Navegador headless | **Playwright**: só na Fase 0 (reconhecimento) e como último recurso por loja | Caro e lento; nunca é o caminho padrão |
| Parsing | `selectolax` (HTML), `extruct` (JSON-LD/microdata), `rapidfuzz` (matching) | Rápidos e pequenos |
| Agendador | APScheduler dentro do processo `worker` | Sem Redis/Celery: o volume não justifica |
| Banco | PostgreSQL 16 em Docker, extensão `pg_trgm` | Busca por similaridade de título direto no banco |
| Frontend | React 19 + Vite + **TypeScript** + TanStack Query + React Router | SPA simples, sem SEO a considerar |
| Gráfico | Recharts (linha em degrau, `type="stepAfter"`) | Leve e resolve o caso |
| Testes | pytest (Postgres real, rede mockada) · Vitest · Playwright e2e | Ver seção 9 |
| Infra local | `docker compose` com `db`, `api`, `worker`, `web` e `adminer` | Um comando sobe tudo |

**Portas:** o Postgres do Sossego publica na **5433** (a 5000 já é usada pelo hubbia na minha máquina e a 5432 pode ter Postgres local). API na **8001**, web na **5174**.

Estrutura sugerida:

```
sossego/
  AGENTS.md  CLAUDE.md  README.md  docker-compose.yml  .env.example  Makefile
  docs/
    fontes/<loja>.md          # resultado da Fase 0, uma por loja
    decisoes/NNN-<tema>.md    # ADRs curtos
    produto-e-fases.md        # registro vivo: o que foi feito, o que falta
  backend/
    main.py  config.py
    db/migrations/NNN_<tema>.sql
    sql/<entidade>.sql
    coleta/
      base.py                 # contrato Coletor + tipos Oferta/ResultadoBusca
      registro.py             # loja -> coletor
      lojas/<loja>.py         # um adaptador por loja
      plataformas/vtex.py     # adaptador genérico reaproveitável
      http.py                 # cliente com rate limit, retry com backoff, cache
    matching/                 # normalização e agrupamento de produto
    pagamento/                # calculadora (funções puras)
    taxas/bcb.py              # CDI/Selic do Banco Central
    recomendacao/
    resolvers/  routers/  worker.py
    tests/  tests/fixtures/<loja>/   # HTML/JSON reais salvos
  frontend/
    src/{api,components,features/{onboarding,home,produto,calculadora},styles}
```

---

## 3. Fase 0 — Reconhecimento de fontes (antes de qualquer coletor)

Não sei se o melhor é scraping ou chamar direto os endpoints que aparecem na aba Network. **Decida loja por loja, com evidência.** Para cada loja:

1. Abra uma busca e uma página de produto com **Playwright**, grave o HAR (`page.route` / `context.tracing`) e liste as requisições XHR/fetch que devolvem JSON com preço.
2. Classifique a fonte, nesta **ordem de preferência**:
   1. **API oficial** (documentada, com credencial)
   2. **Endpoint JSON interno** visto no Network (sem autenticação de usuário)
   3. **JSON embutido no HTML**: `__NEXT_DATA__`, `__PRELOADED_STATE__`, `window.__INITIAL_STATE__`
   4. **JSON-LD `schema.org/Product` + `Offer`** (muito comum e estável)
   5. **Seletores CSS no HTML**
   6. **Headless** (só se nada acima funcionar)
3. Teste se a fonte escolhida funciona **sem navegador** (`curl_cffi`), em sequência e com intervalo, e anote se aparece captcha ou 403.
4. Salve respostas reais em `tests/fixtures/<loja>/` (busca e produto). São a base dos testes.
5. Escreva `docs/fontes/<loja>.md`: fonte escolhida, campos disponíveis (preço "de", "por", Pix, parcelas, juros, frete, estoque, vendedor, GTIN/EAN, variações), dificuldade (fácil/médio/difícil), limites observados e **data da verificação**.

O que já pesquisei (confirme tudo, pode ter mudado):

- **Mercado Livre**: tem API oficial (`api.mercadolibre.com/sites/MLB/search?q=...`). A documentação manda enviar o access token em **toda** chamada, inclusive nos recursos públicos. Crie um app em `developers.mercadolivre.com.br` e use token de aplicação (client credentials). Se a busca voltar 403 mesmo com token, caia para o JSON embutido no site.
- **Amazon**: a PA-API 5 foi descontinuada e substituída pela **Creators API**, que exige 10 vendas qualificadas como afiliado nos últimos 30 dias. **Assuma que não tenho acesso.** Vá de `curl_cffi` + JSON-LD/HTML no `amazon.com.br`, com frequência baixa e cache agressivo. É a loja mais propensa a captcha: trate esse caso explicitamente (marca a coleta como `bloqueada`, não quebra o resto).
- **Lojas em VTEX**: a VTEX expõe busca pública em `/api/catalog_system/pub/products/search/{termo}` e o Intelligent Search em `/api/io/_v/api/intelligent-search/product_search/...`. Detecte a plataforma (headers `x-vtex-*`, paths `/api/catalog_system`) e, se for VTEX, use **um adaptador genérico** (`plataformas/vtex.py`) parametrizado por domínio. Uma loja nova vira uma linha de config. Candidatas a checar: Ri Happy, Centauro, Renner, Época Cosméticos e outras.
- **Magalu**: há vários scrapers comerciais para ela (Apify, Oxylabs), sinal de que dá para extrair. Cheque `__NEXT_DATA__` e as chamadas JSON da busca.
- **Dafiti, Netshoes, Zattini, Kabum, Casas Bahia, Americanas, Shopee**: investigue. Algumas usam Akamai; documente e deixe para depois se for difícil.
- **Ludopedia**: loja/marketplace especializada em jogos de tabuleiro. Prioritária para o meu caso de uso.

**Regras de coleta educada (obrigatórias):** respeitar `robots.txt`, no máximo ~1 requisição a cada 2–3 s por domínio, cache de resultado de busca (TTL de 30 min), backoff exponencial em 429/503, User-Agent coerente com o fingerprint, **nunca** contornar captcha com serviço de resolução e **nunca** coletar dado pessoal. É uso pessoal: o volume é o de uma pessoa navegando.

**Entrega da Fase 0:** uma tabela-resumo em `docs/fontes/README.md` com loja × fonte × dificuldade × campos, e a sua recomendação de quais lojas entram no MVP. **Pare aqui e me mostre antes de seguir.**

Lista de lojas para o seletor do onboarding (coletor ou não, todas aparecem com ícone): Amazon, Mercado Livre, Magalu, Americanas, Casas Bahia, Ponto, Kabum, Fast Shop, Carrefour, Shopee, AliExpress, Dafiti, Netshoes, Zattini, Centauro, Renner, Riachuelo, C&A, Shein, Ri Happy, PBKids, Ludopedia, Época Cosméticos, Sephora, Beleza na Web, Leroy Merlin. Ícones: baixe o favicon/logo de cada uma uma vez, salve em `frontend/public/lojas/<slug>.svg|png` (sem hotlink) e use apenas para identificar a loja.

---

## 4. Contrato do coletor

Toda loja implementa a mesma interface. O resto do sistema não sabe de onde o dado veio.

```python
class Coletor(Protocol):
    loja: str                                   # slug: "mercado-livre"
    async def buscar(self, termo: str, limite: int = 20) -> list[Oferta]: ...
    async def detalhar(self, url_ou_id: str) -> Oferta: ...   # re-coleta de um anúncio conhecido

class Oferta(BaseModel):
    loja: str
    id_externo: str            # MLB123..., ASIN, SKU VTEX
    url: HttpUrl
    titulo: str
    imagem: HttpUrl | None
    marca: str | None
    gtin: str | None           # EAN: a chave de ouro do matching
    vendedor: str | None
    variacao: dict[str, str]   # {"cor": "Preto", "tamanho": "M"}
    preco_de: Decimal | None   # preço "riscado"
    preco: Decimal             # preço cheio no cartão
    preco_pix: Decimal | None
    parcelas_max: int | None
    parcela_valor: Decimal | None
    parcelas_sem_juros: int | None
    frete: Decimal | None      # None = não informado; 0 = grátis
    em_estoque: bool
    descricao: str | None
    especificacoes: dict[str, str]
    coletado_em: datetime
```

- `buscar()` de todas as lojas roda com `asyncio.gather` e **timeout por loja** (~8 s). A loja que falhar ou demorar sai do resultado com status `indisponivel`; a busca nunca quebra por uma loja.
- Dinheiro sempre em `Decimal`/`NUMERIC(12,2)`. **Nunca `float`.**
- Cada adaptador tem teste contra a fixture salva (parse determinístico). Teste ao vivo só com `@pytest.mark.live`, fora do CI (`make smoke`).

---

## 5. Banco de dados (compacto, só colunas úteis)

Separe **o produto** (a coisa: "PS5 Slim 1TB") do **anúncio** (a coisa vendida em uma loja) e do **preço no tempo**. Isso permite comparar lojas e desenhar o gráfico sem duplicar nada.

```
loja            (id, slug UNIQUE, nome, dominio, icone, plataforma, tipo_fonte, coleta_ativa, criado_em)
categoria       (id, slug UNIQUE, nome, icone)
                -- eletrodomésticos, eletrônicos, games, jogos de tabuleiro, vestuário,
                -- calçados, cosméticos, casa, brinquedos, livros, esporte, informática...
produto         (id, titulo, titulo_normalizado, marca, modelo, gtin UNIQUE NULL,
                 categoria_id FK, imagem, descricao, especificacoes JSONB, criado_em)
                -- índice GIN pg_trgm em titulo_normalizado
anuncio         (id, loja_id FK, produto_id FK, id_externo, url, titulo_original, vendedor,
                 variacao JSONB, imagem, ativo, vigiado, primeira_vez_em, ultima_coleta_em,
                 UNIQUE(loja_id, id_externo))
preco_snapshot  (id BIGSERIAL, anuncio_id FK, coletado_em, preco_de, preco, preco_pix,
                 parcelas_max, parcela_valor, parcelas_sem_juros, frete, em_estoque)
                -- índice (anuncio_id, coletado_em DESC) + BRIN em coletado_em
coleta_execucao (id, loja_id FK, tipo[busca|recoleta], inicio, fim, status[ok|parcial|bloqueada|erro],
                 itens, erro)                  -- observabilidade: qual loja está quebrando
taxa_referencia (data PK, cdi_anual, selic_meta)   -- do Banco Central
perfil          (id UUID, faixa_etaria, genero NULL, criado_em)   -- anônimo, sem login
perfil_categoria(perfil_id FK, categoria_id FK, PK composta)      -- máx. 3
perfil_loja     (perfil_id FK, loja_id FK, PK composta)           -- máx. 3
perfil_interesse(id, perfil_id FK, termo, criado_em)              -- "ps5", "dixit"
vigia           (perfil_id FK, produto_id FK, preco_alvo NULL, criado_em, PK composta)
busca_log       (id, perfil_id FK NULL, termo, resultados, criado_em)
```

Regras:

- **Snapshot só quando algo muda.** Na re-coleta, se preço, Pix, parcelas e estoque forem iguais ao último snapshot, atualize só `anuncio.ultima_coleta_em`. O gráfico em degrau (`stepAfter`) torna isso sem perda e o banco não incha. Teste essa regra.
- **"Desconto real"** = comparação contra o **menor preço que nós registramos nos últimos N dias**, não contra o `preco_de` da loja, que costuma ser inflado. Na Black Friday é isso que desmascara o "metade do dobro". Mostre os dois, mas destaque o nosso.
- O máximo de 3 categorias e 3 lojas é validado na API **e** por constraint/trigger, com teste.
- `VIEW preco_diario` (ou materializada, se pesar): menor preço por produto, loja e dia, que alimenta o gráfico.
- Seeds: lojas, categorias e ícones.

**Matching (produto ↔ anúncio)**, o problema mais difícil do sistema, em camadas:

1. Mesmo **GTIN/EAN** → mesmo produto (certeza).
2. Sem GTIN: normalize o título (minúsculas, sem acento, sem palavras de marketing como "oferta", "promoção", "lançamento", "envio imediato"; extraia marca, modelo e capacidade como "1tb" ou "128gb"). Compare com `rapidfuzz.token_set_ratio` + `pg_trgm` + mesma marca. Acima de um limiar alto → mesmo produto; numa faixa cinzenta → **não agrupe** e mostre como "produto parecido".
3. Variação (cor/tamanho) **não** cria produto novo: fica em `anuncio.variacao`.
4. Guarde um conjunto de pares rotulados à mão em `tests/fixtures/matching.csv` (≥40 pares, incluindo casos difíceis como "PS5 Slim digital" × "PS5 Slim com leitor" e "Dixit" × "Dixit Odyssey" × "Dixit expansão") e meça precisão/recall no teste. **Precisão > recall**: juntar dois produtos diferentes é pior que deixar separados.

---

## 6. Calculadora de pagamento (Pix × parcelado)

Funções **puras** em `pagamento/`, 100% testadas. É a parte que mais quero que esteja certa.

**Entradas:** preço à vista (Pix/boleto), preço no cartão, nº de parcelas, se tem juros (ou o valor da parcela), rendimento do dinheiro (padrão: **100% do CDI**, buscado automaticamente do Banco Central e editável), IR sobre o rendimento (tabela regressiva: 22,5% até 180 dias), cashback/pontos do cartão em % (padrão 0) e quando cai a 1ª parcela (padrão: 1ª fatura em ~30 dias; opção "no ato").

**Lógica:**

- Taxa líquida mensal: `i = (1 + CDI_anual × %CDI × (1 − IR))^(1/12) − 1`.
- **Valor presente das parcelas:** `VP = Σ parcela / (1+i)^k`, com `k` começando em 1 (fatura futura) ou 0 (no ato).
- **Custo efetivo do cartão** = `VP − cashback`.
- **Desconto de equilíbrio** = `1 − VP / total_parcelado`: o desconto mínimo para o Pix valer a pena.
- Parcelado **com juros**: calcule a taxa efetiva mensal (TIR) e compare com `i`. Se a taxa do parcelamento for maior que o rendimento, é praticamente sempre Pix.
- Para cada anúncio, gere as opções (Pix, 1x, cada nº de parcelas sem juros disponível) e ordene pelo custo efetivo.

**Saída:** recomendação em uma frase direta + os números. Exemplo:

> **Pague no Pix.** O desconto de 10% supera o que o dinheiro renderia parcelado em 10x (equilíbrio: 5,6%). Você economiza ~R$ 44 em valor de hoje.

> **Parcele em 10x sem juros.** O desconto no Pix é só 3%, abaixo dos 5,6% que seu dinheiro rende no período. Deixe o valor aplicado.

**Testes de aceitação obrigatórios** (conferidos à mão):

- R$ 10.000 em 10x de R$ 1.000, rendimento líquido 1,07% a.m., 1ª parcela **no ato** → desconto de equilíbrio **≈ 4,63%** (bate com a calculadora de referência da Rio Claro).
- Mesmo caso com 1ª parcela **em 30 dias** → **≈ 5,64%**.
- Pix com desconto 0 → recomenda parcelar sem juros (se o rendimento > 0).
- Parcelado com juros de 3% a.m. e rendimento de 1% a.m. → recomenda Pix.

**Taxas do Banco Central** (API SGS, pública, sem chave): `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/1?formato=json`. Confira os códigos antes de usar (acredito que 4389 = CDI anualizado base 252 e 432 = Selic meta). O worker atualiza uma vez por dia e salva em `taxa_referencia`. Se a API cair, usa o último valor salvo e mostra a data dele.

Na UI, a calculadora já vem preenchida com os dados da melhor oferta e permite editar tudo. Um link "como calculamos" abre a explicação em linguagem simples.

---

## 7. Produto e telas

### Identidade

- **Nome:** Sossego. **Tagline:** "Compare em paz."
- **Cor principal: azul royal**, que acalma sem ser frio. Base de partida (ajuste para contraste AA):
  - `--azul-royal: #2340C8` (ações, links, destaques)
  - `--azul-profundo: #14246E` (títulos, cabeçalho)
  - `--azul-nevoa: #E8ECFA` (fundos de seção, estados selecionados)
  - `--papel: #FAFAF7` (fundo), `--tinta: #16181D` (texto), `--grafite: #5B6070` (secundário), `--linha: #D9DCE4`
  - `--queda: #127A4B` (preço caiu), `--alta: #B4232C` (preço subiu). Sempre com ícone/seta junto, nunca só a cor.
- **Tipografia (nada de Arial nem sans genérica):**
  - **Display: Fraunces** (eixo `opsz` alto, `SOFT` 0, `WONK` 0) para os momentos marcantes: preço em destaque, título do produto, perguntas do onboarding, a recomendação da calculadora. Grande, com peso.
  - **Texto: Literata**: serifa feita para tela, muito legível em corpo pequeno, com **algarismos tabulares** (`font-variant-numeric: tabular-nums`) para alinhar preços em tabela.
  - Self-host via `@fontsource`; nada de CDN.
  - Escala: preço do card ~28px, preço da página ~48px, pergunta do onboarding ~40px, corpo 16–17px.
- **Estilo institucional, não "app de IA":** cantos retos ou no máximo 2–4px. **Proibido:** botão pílula/arredondado, glassmorphism, fundo translúcido, blur, gradiente chamativo, sombra difusa gigante. Botões sólidos e retangulares, bordas de 1px, hierarquia por tipografia e espaço, não por enfeite. Pense em site de banco público bem-feito ou jornal de qualidade, não em landing page de startup.
- **Sem barra lateral.** Topo com logo à esquerda e busca no centro, só isso.
- Acessibilidade: contraste AA, foco visível, tudo navegável por teclado, `prefers-reduced-motion`.

### Tela 1 — Onboarding (3 passos, sem login)

Centralizado na tela, uma pergunta por vez, sem distração (nada de cabeçalho ou menu). Barra de progresso fina e reta no topo (1/3, 2/3, 3/3). Botões "Voltar" e "Avançar". Tudo salvo num `perfil` anônimo (UUID no `localStorage` + linha no banco).

1. **Sobre você.** Faixa etária (chips: até 17, 18–24, 25–34, 35–44, 45–59, 60+) e gênero (Feminino, Masculino, Outro, **Prefiro não dizer**). Avançar libera com a faixa etária preenchida; gênero é opcional.
2. **O que você procura?** Grade de categorias com ícone, **máx. 3** (ao tentar a 4ª, a mais antiga não sai sozinha: aparece um aviso discreto "máximo 3"). Abaixo, um campo **opcional**: "Tem algo específico em mente?" com exemplos no placeholder ("PS5, Dixit, air fryer..."), aceitando vários termos como tags.
3. **Lojas de confiança.** Lista com **ícone à esquerda do nome**, **máx. 3**, e opção "Não tenho preferência". Texto de apoio: "A gente compara todas; estas aparecem primeiro quando o preço empatar."

Ao concluir, os termos específicos já disparam a primeira coleta (e entram em `vigia`), para o histórico começar a contar.

Dado pessoal: faixa etária e gênero são anônimos, só servem para recomendação, e aparece uma linha dizendo isso (LGPD). Um link "refazer preferências" no rodapé.

### Tela 2 — Início

- Busca grande no topo ("O que você quer comprar hoje?") com autocomplete do histórico local.
- Seções, nesta ordem:
  1. **De olho**: os produtos vigiados, com preço atual e variação desde a primeira coleta ("−12% desde ontem").
  2. **Pra você**: recomendações a partir das categorias, dos termos e das buscas.
  3. **Caiu de preço**: maiores quedas reais (contra o nosso histórico) nas categorias do perfil.
  4. Chips de categoria para explorar.
- **Card quadrado** (grade responsiva de 2 a 5 colunas): imagem 1:1 em fundo branco, título em 2 linhas, **menor preço em Fraunces grande**, ícone e nome da loja desse preço, linha "+4 lojas a partir de R$ X", selo de variação real (seta + %), e "Pix R$ Y" quando houver. Sem botão dentro do card: o card inteiro é o link.
- Busca: mostra os resultados conforme cada loja responde (streaming via SSE, ou polling curto) com um indicador por loja ("Amazon ✓ · Magalu ✓ · Kabum…"). Ordenação: menor preço, menor preço no Pix, maior queda, relevância. Filtros simples no topo dos resultados (loja, faixa de preço, só com estoque), **nunca em barra lateral**.

### Tela 3 — Produto

Layout em 3 colunas no desktop (empilha no mobile):

- **Esquerda:** galeria de imagens.
- **Centro:** nome em Fraunces, marca; **seletor de variação** (cor/tamanho, como botões retangulares; muda as ofertas mostradas); **tabela de ofertas por loja**, ordenada pelo custo efetivo: loja (ícone + nome), vendedor, preço, Pix, parcelas ("10x sem juros"), frete, estoque, botão "Ir para a loja". A melhor oferta fica destacada no topo com o botão principal **"Comprar na [loja] por R$ X"**, que redireciona para a página do produto na loja de melhor preço (abre em nova aba). Depois: descrição, especificações, vendedor/fornecedor.
- **Direita (fixa ao rolar):** **gráfico de preço no tempo**: linha em degrau, uma série por loja com cor discreta por loja + uma linha do menor preço geral; seletor de período (24h, 7d, 30d, tudo); tooltip com data/hora, loja e preço. Abaixo: **"Menor preço que vimos: R$ X em DD/MM"** e o botão **"Ficar de olho"** (com preço-alvo opcional). Embaixo, a **calculadora de pagamento** (seção 6).
- Enquanto só houver um ponto de dado: mostre o ponto e o texto "Começamos a acompanhar hoje. Volte amanhã para ver a variação." Nada de gráfico vazio ou inventado.
- "Você também pode gostar": produtos parecidos (mesma categoria, faixa de preço próxima), cada um com o melhor preço. É exatamente a minha dor dos jogos de tabuleiro: ver alternativas **já com preço comparado**, sem abrir outra aba.

### Recomendação (v1 determinística, sem LLM)

Pontuação simples e explicável: categoria do perfil + similaridade com termos/buscas (`pg_trgm`) + queda de preço real + loja preferida como desempate. Cada recomendação tem um "porquê" curto ("porque você buscou Dixit"). LLM fica para depois, se fizer sentido.

---

## 8. API (contrato estável, `/api/v1`)

O OpenAPI do FastAPI é o contrato; outro sistema meu (o hubbia) vai consumir essa API no futuro, então **não quebre rotas sem versionar**.

```
POST /api/v1/perfis                         cria perfil anônimo (onboarding)
PUT  /api/v1/perfis/{id}                    atualiza respostas
GET  /api/v1/lojas | /categorias
GET  /api/v1/busca?q=&perfil=               resultados agregados (+ /busca/stream via SSE)
GET  /api/v1/produtos/{id}                  produto + ofertas atuais por loja/variação
GET  /api/v1/produtos/{id}/historico?periodo=30d
GET  /api/v1/produtos/{id}/parecidos
POST /api/v1/pagamento/simular              calculadora (entrada/saída Pydantic)
GET  /api/v1/inicio?perfil=                 seções da home
POST/DELETE /api/v1/perfis/{id}/vigias/{produto_id}
GET  /api/v1/vigias/quedas?desde=           produtos vigiados que caíram (feito pensando no hubbia)
GET  /api/v1/saude                          status do banco + última coleta por loja
```

**Worker:** re-coleta os anúncios `vigiado = true` a cada **2 h** (configurável; na noite e no dia da Black Friday, a cada **1 h**), escalonados para não bater em todas as lojas no mesmo minuto. Taxas do BCB, 1x/dia. Toda execução grava em `coleta_execucao`.

---

## 9. Fases, branches, commits e versão

Cada fase em **branch própria com o nome da fase**, nunca nome aleatório: `fase/<NN>-<nome>`. Commits por módulo, em **Conventional Commits** com descrição em português e escopo:

```
feat(coleta): adaptador VTEX genérico com busca e detalhe
fix(matching): não agrupar PS5 digital com PS5 com leitor
test(pagamento): casos de aceitação do desconto de equilíbrio
chore(infra): docker compose com db, api, worker e web
docs(fontes): reconhecimento da Magalu
```

Fluxo por fase: branch a partir da `main` atualizada → commits pequenos → suíte verde (`make test`) → atualizar `docs/produto-e-fases.md` → push → **PR para a `main`** com resumo do que foi feito, o que foi testado e o que não foi → espero minha aprovação para o merge (exceto se eu disser "pode mergear") → tag anotada `v0.N.0` no merge. Nunca force push na `main`.

| Fase | Branch | Entrega | Pronto quando |
|---|---|---|---|
| 0 | `fase/00-reconhecimento-fontes` | `docs/fontes/*`, fixtures reais, recomendação de MVP | Tabela-resumo revisada por mim |
| 1 | `fase/01-fundacao` | Compose (db, api, worker, adminer), migrations, seeds, `AGENTS.md`, CI, Makefile | `make up && make test` verde do zero |
| 2 | `fase/02-coleta-e-historico` ⚡ | Contrato `Coletor`, 3–4 adaptadores do MVP, cliente HTTP educado, snapshot com dedupe, worker de re-coleta, CLI `python -m coleta.vigiar "ps5 slim"` | Coletor rodando hoje à noite gravando snapshots |
| 3 | `fase/03-matching` | Normalização, GTIN, fuzzy, conjunto rotulado com métricas | Precisão ≥ 0,95 no conjunto rotulado |
| 4 | `fase/04-api` | Rotas da seção 8 com testes | OpenAPI completo, testes de rota verdes |
| 5 | `fase/05-pagamento` | Calculadora + BCB + testes de aceitação | 4 casos de aceitação passando |
| 6 | `fase/06-design-system-onboarding` | Tokens, fontes, componentes base, 3 passos do onboarding | e2e do onboarding passando |
| 7 | `fase/07-inicio-e-busca` | Home, cards, busca com streaming por loja | e2e busca → card |
| 8 | `fase/08-pagina-produto` | Variações, tabela de ofertas, gráfico, vigia, calculadora, parecidos | e2e produto → "Ir para a loja" |
| 9 | `fase/09-mais-lojas` | Adaptadores restantes, priorizando os da Fase 0 | Cada loja com teste de fixture |
| 10 | `fase/10-polimento` | Acessibilidade, estados vazios/erro/carregando, performance, README | Lighthouse ≥ 90 em acessibilidade |

**A Fase 2 roda logo depois da 1, antes de qualquer tela.** Se a 0 demorar, comece a 2 com as lojas já reconhecidas (Mercado Livre e uma VTEX são os candidatos mais fáceis) e siga reconhecendo o resto em paralelo.

### Testes

- **Backend:** pytest com **Postgres real** (banco `sossego_test` recriado por sessão); rede **sempre mockada** com as fixtures (`respx` para httpx; para `curl_cffi`, injete o cliente HTTP). Parsers testados contra fixtures; calculadora com testes de propriedade (`hypothesis`: o desconto de equilíbrio cresce com a taxa e com o nº de parcelas).
- **Ao vivo:** `@pytest.mark.live` (`make smoke`) bate de verdade em cada loja e avisa qual parser quebrou. Fora do CI. Rode antes de cada fase de coleta e quando eu pedir.
- **Frontend:** Vitest para lógica (formatação de moeda, regras de seleção máx. 3, transformação de série do gráfico) e **Playwright e2e** para os fluxos críticos, com a API mockada por fixture.
- **CI (GitHub Actions):** todo push roda `pytest` (Postgres de serviço), `npm test` e `npm run build`. Lint (ruff + oxlint/eslint) local e no pre-commit.
- Antes de dizer "pronto": rode tudo e diga o que **não** rodou.

### Qualidade de engenharia de dados

- Coleta **idempotente** (`UNIQUE(loja_id, id_externo)` + upsert).
- Toda execução registrada em `coleta_execucao`; `/api/v1/saude` mostra loja por loja quando foi a última coleta OK. Loja quebrada aparece, não some em silêncio.
- Validação na borda: Pydantic recusa preço ≤ 0, parcela × nº muito diferente do total, Pix > preço cheio (vira alerta, não snapshot).
- Logs estruturados (JSON) com `loja`, `duracao_ms`, `status`.

---

## 10. Fora do escopo agora (registre em `docs/backlog.md`)

Login e conta; notificação push/e-mail/WhatsApp de queda de preço (a rota `/vigias/quedas` já prepara isso); app mobile; cupons; histórico anterior à primeira coleta; LLM na recomendação; integração com o hubbia (seção 11).

---

## 11. Integração futura com o hubbia (não implementar agora, só não fechar a porta)

O hubbia (`github.com/chami15/hubbia`) é meu hub de agentes (FastAPI + Postgres + LangChain), com agentes de domínio que falam com sistemas externos por um cliente HTTP (é assim que o Norte fala com o GitHub) e mostram sugestões em **cards**. A ideia futura é um agente lá que consome o Sossego. Para isso, aqui:

- API versionada e estável, com o OpenAPI como contrato.
- `/api/v1/vigias/quedas` devolvendo dados estruturados e prontos para virar card, sem precisar de LLM.
- `/api/v1/pagamento/simular` puro e determinístico (o agente financeiro de lá pode usar).
- Bancos **separados**: o hubbia nunca lê o banco do Sossego direto, só pela API.

---

## Primeiro passo

1. Leia este prompt inteiro.
2. Crie a branch `fase/00-reconhecimento-fontes`.
3. Antes de codar, me devolva: (a) dúvidas reais ou discordâncias com a arquitetura, (b) o plano da Fase 0 loja por loja e (c) uma estimativa de quanto falta para o coletor estar gravando snapshots, dado que a Black Friday é amanhã.
