-- 003: matching (Fase 3).
-- Como cada anúncio caiu no produto, para auditar e refazer quando a regra mudar.
ALTER TABLE anuncio ADD COLUMN match_metodo TEXT;   -- gtin | titulo | manual | novo
ALTER TABLE anuncio ADD COLUMN match_motivo TEXT;

-- Grupos [[produto]] da vigia.toml: o dono agrupou à mão, vence o algoritmo.
ALTER TABLE produto ADD COLUMN grupo_manual TEXT UNIQUE;
-- "Edição a confirmar" (Dixit 606 × Ri Happy, 27/11): agrupado, mas sem certeza.
ALTER TABLE produto ADD COLUMN a_confirmar BOOLEAN NOT NULL DEFAULT false;
