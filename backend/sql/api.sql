-- name: lojas
SELECT slug, nome, dominio, icone, coleta_ativa FROM loja ORDER BY nome;

-- name: categorias
SELECT slug, nome, icone FROM categoria ORDER BY nome;

-- name: criar_perfil
INSERT INTO perfil (id, faixa_etaria, genero) VALUES (%(id)s, %(faixa_etaria)s, %(genero)s);

-- name: atualizar_perfil
UPDATE perfil SET faixa_etaria = %(faixa_etaria)s, genero = %(genero)s WHERE id = %(id)s;

-- name: limpar_categorias
DELETE FROM perfil_categoria WHERE perfil_id = %(id)s;

-- name: limpar_lojas
DELETE FROM perfil_loja WHERE perfil_id = %(id)s;

-- name: limpar_interesses
DELETE FROM perfil_interesse WHERE perfil_id = %(id)s;

-- name: inserir_categorias
INSERT INTO perfil_categoria (perfil_id, categoria_id)
SELECT %(id)s, id FROM categoria WHERE slug = ANY(%(slugs)s);

-- name: inserir_lojas
INSERT INTO perfil_loja (perfil_id, loja_id)
SELECT %(id)s, id FROM loja WHERE slug = ANY(%(slugs)s);

-- name: inserir_interesse
INSERT INTO perfil_interesse (perfil_id, termo) VALUES (%(id)s, %(termo)s) ON CONFLICT DO NOTHING;

-- name: slugs_categoria
SELECT slug FROM categoria WHERE slug = ANY(%(slugs)s);

-- name: slugs_loja
SELECT slug FROM loja WHERE slug = ANY(%(slugs)s);

-- name: perfil
SELECT p.id, p.faixa_etaria, p.genero,
       coalesce((SELECT array_agg(c.slug ORDER BY c.slug) FROM perfil_categoria pc
                 JOIN categoria c ON c.id = pc.categoria_id WHERE pc.perfil_id = p.id), '{}') AS categorias,
       coalesce((SELECT array_agg(l.slug ORDER BY l.slug) FROM perfil_loja pl
                 JOIN loja l ON l.id = pl.loja_id WHERE pl.perfil_id = p.id), '{}') AS lojas,
       coalesce((SELECT array_agg(termo ORDER BY id) FROM perfil_interesse WHERE perfil_id = p.id), '{}')
           AS interesses
FROM perfil p WHERE p.id = %(id)s;

-- name: cards
-- Card de produto: melhor oferta (vista nas últimas 48 h, com estoque), quantas
-- lojas, a 2ª loja mais barata, a variação contra o nosso histórico (menor preço
-- do dia mais antigo nos últimos 7 dias) e o menor preço que já vimos.
WITH o AS (
    SELECT * FROM oferta_atual
    WHERE produto_id = ANY(%(ids)s)
      AND ultima_coleta_em >= now() - interval '48 hours'
      AND em_estoque IS NOT FALSE
      AND (%(lojas)s::text[] IS NULL OR loja = ANY(%(lojas)s::text[]))
), melhor AS (
    SELECT DISTINCT ON (produto_id) produto_id, preco, loja, loja_nome, loja_icone, url, imagem
    FROM o ORDER BY produto_id, preco, loja
), outras AS (
    SELECT o.produto_id, count(DISTINCT o.loja) AS outras_lojas, min(o.preco) AS outras_a_partir
    FROM o JOIN melhor m ON m.produto_id = o.produto_id AND o.loja <> m.loja
    GROUP BY o.produto_id
), pix AS (
    SELECT produto_id, min(preco_pix) AS menor_pix FROM o GROUP BY produto_id
), diario AS (
    SELECT produto_id, dia, min(menor_preco) AS menor
    FROM preco_diario WHERE produto_id = ANY(%(ids)s) GROUP BY 1, 2
), ref AS (
    SELECT DISTINCT ON (produto_id) produto_id, menor AS ref_preco, dia AS ref_dia
    FROM diario WHERE dia >= (now() AT TIME ZONE 'America/Sao_Paulo')::date - 7
    ORDER BY produto_id, dia
), minimo AS (
    SELECT DISTINCT ON (produto_id) produto_id, menor AS menor_visto, dia AS menor_visto_em
    FROM diario ORDER BY produto_id, menor, dia
)
SELECT p.id, p.titulo, coalesce(p.imagem, m.imagem) AS imagem, c.slug AS categoria,
       m.preco AS menor_preco, m.loja, m.loja_nome, m.loja_icone, m.url,
       px.menor_pix, coalesce(ou.outras_lojas, 0) AS outras_lojas, ou.outras_a_partir,
       r.ref_preco, r.ref_dia, mi.menor_visto, mi.menor_visto_em
FROM produto p
JOIN melhor m ON m.produto_id = p.id
JOIN pix px ON px.produto_id = p.id
LEFT JOIN outras ou ON ou.produto_id = p.id
LEFT JOIN categoria c ON c.id = p.categoria_id
LEFT JOIN ref r ON r.produto_id = p.id
LEFT JOIN minimo mi ON mi.produto_id = p.id;

-- name: buscar
-- Plataforma e capacidade sempre exatas; o resto com todas as palavras presentes,
-- ou (segunda passada, só se a primeira não achou nada) parecido pelo pg_trgm.
SELECT p.id, greatest(word_similarity(%(q)s, p.termos), similarity(p.termos, %(q)s)) AS relevancia,
       p.titulo || (SELECT coalesce(array_agg(titulo_original), '{}') FROM anuncio WHERE produto_id = p.id)
           AS titulos
FROM produto p
WHERE p.termos ILIKE ALL(%(duros)s)
  AND (p.termos ILIKE ALL(%(padroes)s) OR (%(aproximar)s AND %(resto)s <%% p.termos))
ORDER BY relevancia DESC, p.id
LIMIT 200;

-- name: registrar_busca
INSERT INTO busca_log (perfil_id, termo, resultados)
VALUES ((SELECT id FROM perfil WHERE id = %(perfil)s), %(termo)s, %(resultados)s);

-- name: produto
SELECT p.id, p.titulo, p.marca, p.modelo, p.gtin, p.imagem, p.descricao, p.especificacoes,
       p.a_confirmar, c.slug AS categoria
FROM produto p LEFT JOIN categoria c ON c.id = p.categoria_id
WHERE p.id = %(id)s;

-- name: ofertas
-- Ordem provisória: à vista (Pix quando houver). Custo efetivo com a calculadora vem na Fase 5.
SELECT anuncio_id, loja, loja_nome, loja_icone, url, titulo_original, vendedor, variacao, imagem,
       preco_de, preco, preco_pix, parcelas_max, parcela_valor, parcelas_sem_juros, frete, em_estoque,
       coletado_em, ultima_coleta_em,
       ultima_coleta_em < now() - interval '48 hours' AS desatualizada
FROM oferta_atual
WHERE produto_id = %(id)s
ORDER BY em_estoque IS FALSE, ultima_coleta_em < now() - interval '48 hours',
         coalesce(preco_pix, preco), preco, loja;

-- name: historico
-- Pontos do período mais o preço vigente no início dele: o degrau começa certo.
WITH a AS (
    SELECT a.id, l.slug AS loja, a.titulo_original FROM anuncio a JOIN loja l ON l.id = a.loja_id
    WHERE a.produto_id = %(id)s
)
SELECT a.id AS anuncio_id, a.loja, a.titulo_original, s.coletado_em AS em, s.preco, s.preco_pix
FROM a JOIN preco_snapshot s ON s.anuncio_id = a.id
WHERE %(desde)s::timestamptz IS NULL OR s.coletado_em >= %(desde)s::timestamptz
UNION ALL
SELECT * FROM (
    SELECT DISTINCT ON (a.id) a.id, a.loja, a.titulo_original, %(desde)s::timestamptz, s.preco, s.preco_pix
    FROM a JOIN preco_snapshot s ON s.anuncio_id = a.id
    WHERE %(desde)s::timestamptz IS NOT NULL AND s.coletado_em < %(desde)s::timestamptz
    ORDER BY a.id, s.coletado_em DESC
) vigente
ORDER BY em, anuncio_id;

-- name: menor_visto
SELECT s.preco, s.coletado_em AS em, l.slug AS loja
FROM preco_snapshot s JOIN anuncio a ON a.id = s.anuncio_id JOIN loja l ON l.id = a.loja_id
WHERE a.produto_id = %(id)s
ORDER BY s.preco, s.coletado_em
LIMIT 1;

-- name: parecidos
-- Mesma categoria, do mais parecido no título para o menos; a faixa de preço é filtrada na API.
SELECT p2.id
FROM produto p JOIN produto p2 ON p2.categoria_id = p.categoria_id AND p2.id <> p.id
WHERE p.id = %(id)s
ORDER BY similarity(p2.termos, p.termos) DESC, p2.id
LIMIT 60;

-- name: existe_produto
SELECT EXISTS (SELECT 1 FROM produto WHERE id = %(id)s);

-- name: existe_perfil
SELECT EXISTS (SELECT 1 FROM perfil WHERE id = %(id)s);

-- name: vigiar
INSERT INTO vigia (perfil_id, produto_id, preco_alvo) VALUES (%(perfil)s, %(produto)s, %(preco_alvo)s)
ON CONFLICT (perfil_id, produto_id) DO UPDATE SET preco_alvo = EXCLUDED.preco_alvo;

-- name: desvigiar
DELETE FROM vigia WHERE perfil_id = %(perfil)s AND produto_id = %(produto)s;

-- name: vigiados
SELECT produto_id FROM vigia WHERE perfil_id = %(perfil)s ORDER BY criado_em DESC;

-- name: candidatos_pra_voce
-- Produtos da categoria do perfil ou parecidos com o que ele disse/buscou.
WITH termos AS (
    SELECT termo FROM perfil_interesse WHERE perfil_id = %(perfil)s
    UNION
    SELECT termo FROM (SELECT termo FROM busca_log WHERE perfil_id = %(perfil)s
                       ORDER BY criado_em DESC LIMIT 20) recentes
), cats AS (
    SELECT categoria_id FROM perfil_categoria WHERE perfil_id = %(perfil)s
)
SELECT p.id, c.nome AS categoria_nome, (p.categoria_id IN (SELECT categoria_id FROM cats)) AS da_categoria,
       t.termo, coalesce(t.sim, 0) AS sim
FROM produto p
LEFT JOIN categoria c ON c.id = p.categoria_id
LEFT JOIN LATERAL (
    SELECT termo, word_similarity(termo, p.termos) AS sim FROM termos
    ORDER BY word_similarity(termo, p.termos) DESC LIMIT 1
) t ON true
WHERE p.id NOT IN (SELECT produto_id FROM vigia WHERE perfil_id = %(perfil)s)
  AND (p.categoria_id IN (SELECT categoria_id FROM cats) OR coalesce(t.sim, 0) >= 0.5)
LIMIT 300;

-- name: lojas_do_perfil
SELECT l.slug FROM perfil_loja pl JOIN loja l ON l.id = pl.loja_id WHERE pl.perfil_id = %(perfil)s;

-- name: produtos_da_categoria
SELECT p.id FROM produto p
WHERE %(cats)s::text[] IS NULL
   OR p.categoria_id IN (SELECT id FROM categoria WHERE slug = ANY(%(cats)s::text[]));

-- name: categorias_do_perfil
SELECT c.slug FROM perfil_categoria pc JOIN categoria c ON c.id = pc.categoria_id
WHERE pc.perfil_id = %(perfil)s;

-- name: quedas
-- Menor preço vigente em `desde` entre os anúncios de cada produto vigiado.
WITH v AS (SELECT perfil_id, produto_id, preco_alvo FROM vigia),
antes AS (
    SELECT a.produto_id, min(x.preco) AS preco
    FROM anuncio a
    JOIN LATERAL (SELECT preco FROM preco_snapshot s
                  WHERE s.anuncio_id = a.id AND s.coletado_em <= %(desde)s
                  ORDER BY s.coletado_em DESC LIMIT 1) x ON true
    WHERE a.produto_id IN (SELECT produto_id FROM v)
    GROUP BY a.produto_id
)
SELECT v.perfil_id, v.produto_id, v.preco_alvo, antes.preco AS preco_antes
FROM v LEFT JOIN antes USING (produto_id)
ORDER BY v.produto_id, v.perfil_id;

-- name: ultima_execucao_ok
SELECT l.slug, max(e.fim) AS em
FROM coleta_execucao e JOIN loja l ON l.id = e.loja_id
WHERE e.status = 'ok' GROUP BY l.slug;
