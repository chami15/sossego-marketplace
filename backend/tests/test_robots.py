from coleta.robots import analisar


def test_regra_mais_longa_vence():
    rb = analisar("User-agent: *\nDisallow: /\nAllow: /produtos/\n")
    assert rb.permite("https://x.com/produtos/123")
    assert not rb.permite("https://x.com/carrinho")


def test_curinga_e_ancora():
    rb = analisar("User-agent: *\nDisallow: /*?filtro=\nDisallow: /*.pdf$\n")
    assert not rb.permite("https://x.com/busca?filtro=a")
    assert rb.permite("https://x.com/busca?q=a")
    assert not rb.permite("https://x.com/a/manual.pdf")
    assert rb.permite("https://x.com/a/manual.pdf?v=1")


def test_so_vale_grupo_asterisco():
    rb = analisar("User-agent: Googlebot\nDisallow: /\n\nUser-agent: *\nDisallow: /privado\n")
    assert rb.permite("https://x.com/qualquer")
    assert not rb.permite("https://x.com/privado/1")


def test_grupo_com_varios_agentes_e_crawl_delay():
    rb = analisar("User-agent: bingbot\nUser-agent: *\nCrawl-delay: 10\nDisallow: /a\n")
    assert rb.crawl_delay == 10
    assert not rb.permite("https://x.com/a")


def test_disallow_vazio_libera_tudo():
    rb = analisar("User-agent: *\nDisallow:\n")
    assert rb.permite("https://x.com/qualquer")
