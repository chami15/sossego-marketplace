-- 001: núcleo mínimo para gravar o histórico de preço antes da Black Friday.
-- Produto (a coisa), anúncio (a coisa numa loja) e snapshot (preço no tempo).
-- Perfil, categoria, vigia etc. vêm em migrations posteriores.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE loja (
    id            SERIAL PRIMARY KEY,
    slug          TEXT NOT NULL UNIQUE,
    nome          TEXT NOT NULL,
    dominio       TEXT NOT NULL,
    plataforma    TEXT,                 -- vtex, propria...
    tipo_fonte    TEXT,                 -- html_busca, api_vtex, api_oficial...
    coleta_ativa  BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE produto (
    id                  BIGSERIAL PRIMARY KEY,
    titulo              TEXT NOT NULL,
    titulo_normalizado  TEXT NOT NULL,
    marca               TEXT,
    modelo              TEXT,
    gtin                TEXT UNIQUE,
    imagem              TEXT,
    descricao           TEXT,
    especificacoes      JSONB NOT NULL DEFAULT '{}',
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_produto_titulo_trgm ON produto USING GIN (titulo_normalizado gin_trgm_ops);

CREATE TABLE anuncio (
    id                BIGSERIAL PRIMARY KEY,
    loja_id           INT NOT NULL REFERENCES loja(id),
    -- Nullable de propósito: o matching (Fase 3) associa depois, sem travar a coleta.
    produto_id        BIGINT REFERENCES produto(id),
    id_externo        TEXT NOT NULL,      -- ASIN, productId VTEX, slug Ludopedia
    url               TEXT NOT NULL,
    titulo_original   TEXT NOT NULL,
    gtin              TEXT,               -- guardado aqui até o matching subir para produto
    vendedor          TEXT,
    variacao          JSONB NOT NULL DEFAULT '{}',
    imagem            TEXT,
    ativo             BOOLEAN NOT NULL DEFAULT TRUE,
    vigiado           BOOLEAN NOT NULL DEFAULT FALSE,
    primeira_vez_em   TIMESTAMPTZ NOT NULL,
    ultima_coleta_em  TIMESTAMPTZ NOT NULL,
    UNIQUE (loja_id, id_externo)
);
CREATE INDEX ix_anuncio_produto ON anuncio (produto_id);

CREATE TABLE preco_snapshot (
    id                  BIGSERIAL PRIMARY KEY,
    anuncio_id          BIGINT NOT NULL REFERENCES anuncio(id),
    coletado_em         TIMESTAMPTZ NOT NULL,
    preco_de            NUMERIC(12,2),
    preco               NUMERIC(12,2) NOT NULL CHECK (preco > 0),
    preco_pix           NUMERIC(12,2),
    parcelas_max        INT,
    parcela_valor       NUMERIC(12,2),
    parcelas_sem_juros  INT,
    frete               NUMERIC(12,2),
    em_estoque          BOOLEAN,
    -- de qual arquivo bruto saiu (reprocessar não duplica; rastreabilidade)
    origem              TEXT NOT NULL,
    UNIQUE (anuncio_id, coletado_em)
);
CREATE INDEX ix_snapshot_anuncio_tempo ON preco_snapshot (anuncio_id, coletado_em DESC);
CREATE INDEX ix_snapshot_tempo_brin ON preco_snapshot USING BRIN (coletado_em);

CREATE TABLE coleta_execucao (
    id        BIGSERIAL PRIMARY KEY,
    loja_id   INT NOT NULL REFERENCES loja(id),
    tipo      TEXT NOT NULL CHECK (tipo IN ('busca', 'recoleta', 'reprocesso')),
    inicio    TIMESTAMPTZ NOT NULL,
    fim       TIMESTAMPTZ,
    status    TEXT NOT NULL CHECK (status IN ('ok', 'parcial', 'bloqueada', 'erro')),
    itens     INT NOT NULL DEFAULT 0,
    erro      TEXT
);

-- Arquivos brutos já processados: reprocessar o bruto é idempotente.
CREATE TABLE bruto_processado (
    arquivo        TEXT PRIMARY KEY,
    processado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ofertas        INT NOT NULL,
    parser_versao  TEXT NOT NULL
);

INSERT INTO loja (slug, nome, dominio, plataforma, tipo_fonte, coleta_ativa) VALUES
    ('amazon',        'Amazon',        'www.amazon.com.br',          'propria', 'html_busca',  TRUE),
    ('ludopedia',     'Ludopedia',     'www.ludopedia.com.br',       'propria', 'html_busca',  TRUE),
    ('ri-happy',      'Ri Happy',      'www.rihappy.com.br',         'vtex',    'api_vtex',    TRUE),
    ('mercado-livre', 'Mercado Livre', 'api.mercadolibre.com',       'propria', 'api_oficial', FALSE),
    ('magalu',        'Magalu',        'www.magazineluiza.com.br',   'propria', 'html_busca',  FALSE),
    ('kabum',         'Kabum',         'www.kabum.com.br',           'propria', 'html_busca',  FALSE);
