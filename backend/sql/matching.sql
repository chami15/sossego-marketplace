-- name: produto_manual
-- Grupo [[produto]] da vigia.toml: um produto por nome de grupo.
INSERT INTO produto (titulo, titulo_normalizado, grupo_manual, a_confirmar)
VALUES (%(nome)s, %(normalizado)s, %(nome)s, %(a_confirmar)s)
ON CONFLICT (grupo_manual) DO UPDATE SET a_confirmar = EXCLUDED.a_confirmar
RETURNING id;

-- name: ligar_manual
UPDATE anuncio a SET produto_id = %(produto_id)s, match_metodo = 'manual', match_motivo = %(motivo)s
FROM loja l
WHERE l.id = a.loja_id AND l.slug = %(loja)s AND a.id_externo = %(id_externo)s;

-- name: sem_produto
SELECT id, titulo_original, gtin FROM anuncio
WHERE produto_id IS NULL
ORDER BY primeira_vez_em, id;

-- name: candidatos
-- Mesmo GTIN, ou título parecido pelo pg_trgm. A decisão final é do decidir().
SELECT id FROM produto
WHERE (%(gtin)s::text IS NOT NULL AND gtin = %(gtin)s)
   OR similarity(titulo_normalizado, %(normalizado)s) > 0.3
ORDER BY (gtin IS NOT DISTINCT FROM %(gtin)s::text) DESC,
         similarity(titulo_normalizado, %(normalizado)s) DESC
LIMIT 20;

-- name: membros
SELECT titulo_original, gtin FROM anuncio WHERE produto_id = %(produto_id)s;

-- name: gtin_livre
SELECT NOT EXISTS (SELECT 1 FROM produto WHERE gtin = %(gtin)s);

-- name: novo_produto
INSERT INTO produto (titulo, titulo_normalizado, gtin)
VALUES (%(titulo)s, %(normalizado)s, %(gtin)s)
RETURNING id;

-- name: ligar
UPDATE anuncio SET produto_id = %(produto_id)s, match_metodo = %(metodo)s, match_motivo = %(motivo)s
WHERE id = %(anuncio_id)s;

-- name: desligar_todos
-- Refazer o matching: desfaz só o automático; grupo manual é religado em seguida.
UPDATE anuncio SET produto_id = NULL, match_metodo = NULL, match_motivo = NULL;

-- name: apagar_produtos_automaticos
DELETE FROM produto p
WHERE p.grupo_manual IS NULL
  AND NOT EXISTS (SELECT 1 FROM anuncio a WHERE a.produto_id = p.id);
