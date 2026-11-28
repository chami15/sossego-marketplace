-- 006: imagens de produto baixadas uma vez e servidas localmente (Fase 8).
-- Chave = URL original do anúncio: se a loja trocar a imagem, a URL muda e baixa
-- de novo; com a mesma URL, nunca mais.
CREATE TABLE imagem_baixada (
    url         TEXT PRIMARY KEY,
    situacao    TEXT NOT NULL CHECK (situacao IN ('ok', 'falhou')),
    arquivo     TEXT,                 -- nome em dados/imagens/ (só com 'ok')
    largura     INT,
    altura      INT,
    motivo      TEXT,                 -- por que falhou
    tentada_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((situacao = 'ok') = (arquivo IS NOT NULL))
);
