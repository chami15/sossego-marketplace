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
SELECT a.id, a.titulo_original, a.gtin, l.slug FROM anuncio a JOIN loja l ON l.id = a.loja_id
WHERE a.produto_id IS NULL
ORDER BY a.primeira_vez_em, a.id;

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
INSERT INTO produto (titulo, titulo_normalizado, gtin, termos, categoria_id)
VALUES (%(titulo)s, %(normalizado)s, %(gtin)s, %(termos)s, (SELECT id FROM categoria WHERE slug = %(categoria)s))
RETURNING id;

-- name: todos_os_titulos
-- Termos de busca = união dos títulos do produto: um anúncio diz "PS5", outro não.
SELECT p.id, p.termos, p.categoria_id IS NOT NULL AS tem_categoria,
       p.titulo || coalesce(array_agg(a.titulo_original ORDER BY a.id) FILTER (WHERE a.id IS NOT NULL), '{}')
           AS titulos,
       (array_agg(l.slug ORDER BY a.id))[1] AS loja
FROM produto p LEFT JOIN anuncio a ON a.produto_id = p.id LEFT JOIN loja l ON l.id = a.loja_id
GROUP BY p.id;

-- name: preencher_termos
UPDATE produto SET termos = %(termos)s,
       categoria_id = coalesce(categoria_id, (SELECT id FROM categoria WHERE slug = %(categoria)s))
WHERE id = %(id)s;

-- name: ligar
UPDATE anuncio SET produto_id = %(produto_id)s, match_metodo = %(metodo)s, match_motivo = %(motivo)s
WHERE id = %(anuncio_id)s;

-- name: desligar_todos
-- Refazer o matching: desfaz só o automático; grupo manual é religado em seguida.
-- Produto vigiado fica como está: a vigia do perfil não pode apontar para o vazio.
UPDATE anuncio SET produto_id = NULL, match_metodo = NULL, match_motivo = NULL
WHERE produto_id IS NULL OR produto_id NOT IN (SELECT produto_id FROM vigia);

-- name: apagar_produtos_automaticos
DELETE FROM produto p
WHERE p.grupo_manual IS NULL
  AND NOT EXISTS (SELECT 1 FROM anuncio a WHERE a.produto_id = p.id)
  AND NOT EXISTS (SELECT 1 FROM vigia v WHERE v.produto_id = p.id);
