-- name: loja_id
SELECT id FROM loja WHERE slug = %(slug)s;

-- name: upsert_anuncio
-- Idempotente por (loja, id_externo). Não regride ultima_coleta_em ao
-- reprocessar arquivo antigo depois de um novo.
INSERT INTO anuncio (loja_id, id_externo, url, titulo_original, gtin, vendedor, variacao, imagem,
                     primeira_vez_em, ultima_coleta_em)
VALUES (%(loja_id)s, %(id_externo)s, %(url)s, %(titulo)s, %(gtin)s, %(vendedor)s, %(variacao)s,
        %(imagem)s, %(coletado_em)s, %(coletado_em)s)
ON CONFLICT (loja_id, id_externo) DO UPDATE SET
    url              = EXCLUDED.url,
    titulo_original  = EXCLUDED.titulo_original,
    gtin             = COALESCE(EXCLUDED.gtin, anuncio.gtin),
    vendedor         = COALESCE(EXCLUDED.vendedor, anuncio.vendedor),
    imagem           = COALESCE(EXCLUDED.imagem, anuncio.imagem),
    primeira_vez_em  = LEAST(anuncio.primeira_vez_em, EXCLUDED.primeira_vez_em),
    ultima_coleta_em = GREATEST(anuncio.ultima_coleta_em, EXCLUDED.ultima_coleta_em)
RETURNING id;

-- name: snapshot_anterior
-- O estado vigente no instante desta coleta (gráfico em degrau).
SELECT preco, preco_pix, parcelas_max, parcela_valor, parcelas_sem_juros, em_estoque
FROM preco_snapshot
WHERE anuncio_id = %(anuncio_id)s AND coletado_em <= %(coletado_em)s
ORDER BY coletado_em DESC
LIMIT 1;

-- name: inserir_snapshot
INSERT INTO preco_snapshot (anuncio_id, coletado_em, preco_de, preco, preco_pix, parcelas_max,
                            parcela_valor, parcelas_sem_juros, frete, em_estoque, origem)
VALUES (%(anuncio_id)s, %(coletado_em)s, %(preco_de)s, %(preco)s, %(preco_pix)s, %(parcelas_max)s,
        %(parcela_valor)s, %(parcelas_sem_juros)s, %(frete)s, %(em_estoque)s, %(origem)s)
ON CONFLICT (anuncio_id, coletado_em) DO NOTHING;

-- name: ja_processado
SELECT parser_versao FROM bruto_processado WHERE arquivo = %(arquivo)s;

-- name: marcar_processado
INSERT INTO bruto_processado (arquivo, ofertas, parser_versao)
VALUES (%(arquivo)s, %(ofertas)s, %(parser_versao)s)
ON CONFLICT (arquivo) DO UPDATE SET
    processado_em = now(), ofertas = EXCLUDED.ofertas, parser_versao = EXCLUDED.parser_versao;

-- name: registrar_execucao
INSERT INTO coleta_execucao (loja_id, tipo, inicio, fim, status, itens, erro)
VALUES (%(loja_id)s, 'reprocesso', %(inicio)s, now(), %(status)s, %(itens)s, %(erro)s);
