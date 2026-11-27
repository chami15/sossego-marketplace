-- 004: o que a API precisa (Fase 4): categorias, perfil anônimo, vigia,
-- log de busca e o preço diário do gráfico.

ALTER TABLE loja ADD COLUMN icone TEXT;  -- frontend/public/lojas/<slug>.<ext>, baixado uma vez

-- Lojas do seletor do onboarding: aparecem com ícone, coletadas ou não.
INSERT INTO loja (slug, nome, dominio, coleta_ativa) VALUES
    ('americanas',     'Americanas',     'www.americanas.com.br',     FALSE),
    ('casas-bahia',    'Casas Bahia',    'www.casasbahia.com.br',     FALSE),
    ('ponto',          'Ponto',          'www.pontofrio.com.br',      FALSE),
    ('fast-shop',      'Fast Shop',      'www.fastshop.com.br',       FALSE),
    ('carrefour',      'Carrefour',      'www.carrefour.com.br',      FALSE),
    ('shopee',         'Shopee',         'shopee.com.br',             FALSE),
    ('aliexpress',     'AliExpress',     'pt.aliexpress.com',         FALSE),
    ('dafiti',         'Dafiti',         'www.dafiti.com.br',         FALSE),
    ('netshoes',       'Netshoes',       'www.netshoes.com.br',       FALSE),
    ('zattini',        'Zattini',        'www.zattini.com.br',        FALSE),
    ('centauro',       'Centauro',       'www.centauro.com.br',       FALSE),
    ('renner',         'Renner',         'www.lojasrenner.com.br',    FALSE),
    ('riachuelo',      'Riachuelo',      'www.riachuelo.com.br',      FALSE),
    ('cea',            'C&A',            'www.cea.com.br',            FALSE),
    ('shein',          'Shein',          'br.shein.com',              FALSE),
    ('pbkids',         'PBKids',         'www.pbkids.com.br',         FALSE),
    ('epoca',          'Época Cosméticos', 'www.epocacosmeticos.com.br', FALSE),
    ('sephora',        'Sephora',        'www.sephora.com.br',        FALSE),
    ('beleza-na-web',  'Beleza na Web',  'www.belezanaweb.com.br',    FALSE),
    ('leroy-merlin',   'Leroy Merlin',   'www.leroymerlin.com.br',    FALSE)
ON CONFLICT (slug) DO NOTHING;
UPDATE loja SET icone = 'lojas/' || slug || '.png';

CREATE TABLE categoria (
    id     SERIAL PRIMARY KEY,
    slug   TEXT NOT NULL UNIQUE,
    nome   TEXT NOT NULL,
    icone  TEXT NOT NULL
);
INSERT INTO categoria (slug, nome, icone) VALUES
    ('eletrodomesticos',  'Eletrodomésticos',  'geladeira'),
    ('eletronicos',       'Eletrônicos',       'tv'),
    ('games',             'Games',             'controle'),
    ('jogos-tabuleiro',   'Jogos de tabuleiro', 'dado'),
    ('informatica',       'Informática',       'notebook'),
    ('vestuario',         'Vestuário',         'camiseta'),
    ('calcados',          'Calçados',          'tenis'),
    ('cosmeticos',        'Cosméticos',        'frasco'),
    ('casa',              'Casa',              'casa'),
    ('brinquedos',        'Brinquedos',        'urso'),
    ('livros',            'Livros',            'livro'),
    ('esporte',           'Esporte',           'bola');

ALTER TABLE produto ADD COLUMN categoria_id INT REFERENCES categoria(id);
-- Texto de busca: titulo_normalizado tira plataforma e capacidade (o matching
-- compara isso à parte), mas quem busca digita "ps5" e "1tb".
ALTER TABLE produto ADD COLUMN termos TEXT;
CREATE INDEX ix_produto_termos_trgm ON produto USING GIN (termos gin_trgm_ops);

-- Perfil anônimo do onboarding: sem login, sem dado pessoal além disto.
CREATE TABLE perfil (
    id            UUID PRIMARY KEY,
    faixa_etaria  TEXT NOT NULL CHECK (faixa_etaria IN ('ate-17', '18-24', '25-34', '35-44', '45-59', '60+')),
    genero        TEXT CHECK (genero IN ('feminino', 'masculino', 'outro', 'prefiro-nao-dizer')),
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE perfil_categoria (
    perfil_id     UUID NOT NULL REFERENCES perfil(id) ON DELETE CASCADE,
    categoria_id  INT NOT NULL REFERENCES categoria(id),
    PRIMARY KEY (perfil_id, categoria_id)
);
CREATE TABLE perfil_loja (
    perfil_id  UUID NOT NULL REFERENCES perfil(id) ON DELETE CASCADE,
    loja_id    INT NOT NULL REFERENCES loja(id),
    PRIMARY KEY (perfil_id, loja_id)
);

-- Máximo de 3, também no banco: a API valida, mas o banco não confia nela.
CREATE FUNCTION limite_tres() RETURNS trigger AS $$
DECLARE n INT;
BEGIN
    EXECUTE format('SELECT count(*) FROM %I WHERE perfil_id = $1', TG_TABLE_NAME) INTO n USING NEW.perfil_id;
    IF n >= 3 THEN
        RAISE EXCEPTION 'máximo de 3 em % por perfil', TG_TABLE_NAME USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER perfil_categoria_max3 BEFORE INSERT ON perfil_categoria
    FOR EACH ROW EXECUTE FUNCTION limite_tres();
CREATE TRIGGER perfil_loja_max3 BEFORE INSERT ON perfil_loja
    FOR EACH ROW EXECUTE FUNCTION limite_tres();

CREATE TABLE perfil_interesse (
    id         BIGSERIAL PRIMARY KEY,
    perfil_id  UUID NOT NULL REFERENCES perfil(id) ON DELETE CASCADE,
    termo      TEXT NOT NULL,
    criado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (perfil_id, termo)
);

CREATE TABLE vigia (
    perfil_id   UUID NOT NULL REFERENCES perfil(id) ON DELETE CASCADE,
    produto_id  BIGINT NOT NULL REFERENCES produto(id),
    preco_alvo  NUMERIC(12,2) CHECK (preco_alvo > 0),
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (perfil_id, produto_id)
);

CREATE TABLE busca_log (
    id          BIGSERIAL PRIMARY KEY,
    perfil_id   UUID REFERENCES perfil(id) ON DELETE SET NULL,
    termo       TEXT NOT NULL,
    resultados  INT NOT NULL,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Último snapshot de cada anúncio ligado a produto: a oferta "de agora".
-- ultima_coleta_em diz quando a loja ainda mostrava o anúncio; quem consome
-- decide o que é velho demais (a API marca como desatualizada após 48 h).
CREATE VIEW oferta_atual AS
SELECT DISTINCT ON (a.id)
       a.id AS anuncio_id, a.produto_id, l.slug AS loja, l.nome AS loja_nome, l.icone AS loja_icone,
       a.url, a.titulo_original, a.vendedor, a.variacao, a.imagem, a.ultima_coleta_em,
       s.coletado_em, s.preco_de, s.preco, s.preco_pix, s.parcelas_max, s.parcela_valor,
       s.parcelas_sem_juros, s.frete, s.em_estoque
FROM anuncio a
JOIN loja l ON l.id = a.loja_id
JOIN preco_snapshot s ON s.anuncio_id = a.id
WHERE a.ativo AND a.produto_id IS NOT NULL
ORDER BY a.id, s.coletado_em DESC;

-- Menor preço por produto, loja e dia (gráfico). Snapshot só existe quando
-- algo muda: um dia sem snapshot herda o preço anterior (degrau), e isso é
-- resolvido na consulta do histórico, não aqui.
CREATE VIEW preco_diario AS
SELECT a.produto_id, a.loja_id, (s.coletado_em AT TIME ZONE 'America/Sao_Paulo')::date AS dia,
       min(s.preco) AS menor_preco, min(s.preco_pix) AS menor_pix
FROM preco_snapshot s JOIN anuncio a ON a.id = s.anuncio_id
WHERE a.produto_id IS NOT NULL
GROUP BY 1, 2, 3;
