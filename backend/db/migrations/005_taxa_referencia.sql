-- 005: taxas do Banco Central (SGS) para a calculadora de pagamento.
-- Uma linha por data de referência do CDI; valores em % ao ano, como o SGS publica.
CREATE TABLE taxa_referencia (
    data           DATE PRIMARY KEY,
    cdi_anual      NUMERIC(8,4) NOT NULL,   -- SGS 4389, % a.a. base 252
    selic_meta     NUMERIC(8,4),            -- SGS 432, % a.a.
    selic_data     DATE,
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);
