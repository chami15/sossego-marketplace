import csv
from pathlib import Path

import pytest

from matching.decidir import decidir
from matching.normalizar import normalizar

ROTULADOS = Path(__file__).parent / "fixtures" / "matching.csv"


def pares():
    with ROTULADOS.open(encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";", quoting=csv.QUOTE_NONE))


def test_normaliza_acento_caixa_marketing_e_codigo_da_loja():
    n = normalizar("Jogo Pokémon Legends Z-A, Nintendo Switch 2 - NT000056NSW Promoção")
    assert n.texto == "pokemon legends za"
    assert n.plataformas == {"ns2"}


def test_switch_2_nao_vira_switch():
    assert normalizar("EA Sports FC 27 - Nintendo Switch").plataformas == {"ns1"}
    assert normalizar("EA Sports FC 27 para Nintendo Switch 2").plataformas == {"ns2"}
    assert normalizar("Jogo Splatoon Raiders para NS2").plataformas == {"ns2"}
    assert normalizar("PlayStation®5 Pro").plataformas == {"ps5"}


def test_capacidade_em_gb():
    assert normalizar("Notebook 16gb Ram 1TB SSD").capacidades == {16, 1024}
    assert normalizar("Cartão microSD Express 256 GB").capacidades == {256}


def test_cor_e_variacao_nao_produto():
    n = normalizar("Controle Sem Fio Sony DualSense, PlayStation 5, Bluetooth, Midnight Black")
    assert "black" not in n.tokens and n.cores == {"midnight", "black"}


def test_mesmo_gtin_e_certeza():
    d = decidir("Jogo De Tabuleiro - Dixit - Galápagos", "3558387010060", "Jogo Dixit Novo - Asmodee", "3558387010060")
    assert d.rotulo == "mesmo" and d.metodo == "gtin"


def test_gtin_diferente_nunca_e_mesmo():
    d = decidir("Dixit Odyssey", "3558380127079", "Dixit Odyssey", "3558380127080")
    assert d.rotulo != "mesmo"


def test_regressao_ean_repetido_juntava_kit_com_avulso():
    """27/11: a Ri Happy usa o mesmo EAN para o kit Vilões + Aventura e para o
    Aventura avulso. GTIN igual com conflito no título não pode virar 'mesmo'."""
    d = decidir("Kit Dixit Expansão Signature Disney Vilões + Aventura", "3558387010695",
                "Dixit Signature Aventura & Mistério Expansão Disney Pixar", "3558387010695")
    assert d.rotulo != "mesmo"


def test_faixa_cinzenta_vira_parecido_nao_mesmo():
    d = decidir("Dixit", None, "Dixit: Odyssey", None)
    assert d.rotulo == "parecido"


def test_conjunto_rotulado_tem_40_pares_com_casos_dificeis():
    ps = [p for p in pares() if p["rotulo"] in ("mesmo", "diferente")]
    assert len(ps) >= 40
    titulos = " ".join(p["titulo_a"] + p["titulo_b"] for p in ps)
    for caso in ("Slim Edição Digital", "Dixit: Odyssey", "Expansão", "Switch 2", "Usado"):
        assert caso in titulos


def test_precisao_no_conjunto_rotulado(capsys):
    """Precisão > recall: juntar produtos diferentes é pior que deixar separados."""
    vp = fp = fn = 0
    erros = []
    for p in pares():
        if p["rotulo"] not in ("mesmo", "diferente"):
            continue
        d = decidir(p["titulo_a"], p["gtin_a"] or None, p["titulo_b"], p["gtin_b"] or None)
        previsto = d.rotulo == "mesmo"
        real = p["rotulo"] == "mesmo"
        vp += previsto and real
        fp += previsto and not real
        fn += real and not previsto
        if previsto != real:
            erros.append(f"{'FP' if previsto else 'FN'} {d.rotulo}/{d.motivo}: {p['titulo_a']} | {p['titulo_b']}")
    precisao = vp / (vp + fp)
    recall = vp / (vp + fn)
    with capsys.disabled():
        print(f"\nmatching: precisão {precisao:.3f}, recall {recall:.3f} (vp {vp}, fp {fp}, fn {fn})")
        for e in erros:
            print("  " + e)
    assert precisao >= 0.95
    # Piso de recall: um matcher que nunca agrupa teria "precisão" vazia.
    assert recall >= 0.5


@pytest.mark.parametrize("a,b", [
    ("Jogo Mario Kart 8 Deluxe, Nintendo Switch - HBCPAABPA", "Mario Kart 8 Deluxe - Nintendo Switch"),
    ("Bolsa de Transporte com Alça para Nintendo Switch 2, Cinza", "Bolsa De Transporte Para Nintendo Switch 2 Com Alça (Cinza)"),
])
def test_decisao_e_simetrica(a, b):
    assert decidir(a, None, b, None).rotulo == decidir(b, None, a, None).rotulo


def test_regressao_bundle_com_console_juntava_com_jogo_avulso():
    """27/11, validação nos 459 anúncios reais: 'Bundle Switch 2 + EA FC 27' virava
    o mesmo produto que o jogo 'EA FC 27 para Switch 2' ("bundle" era só vitrine)."""
    assert decidir("Bundle Nintendo Switch 2 + EA Sports FC 27", None,
                   "EA Sports FC 27 para Nintendo Switch 2", None).rotulo != "mesmo"


def test_regressao_titulo_sem_capacidade_juntava_com_qualquer_capacidade():
    """27/11: 'Console Ps3 Slim' virava o mesmo que o PS3 Slim de 120, 250 e 320 GB."""
    for gb in (120, 250, 320):
        assert decidir("Console Ps3 Slim", None, f"Sony Playstation 3 Slim {gb}gb Standard", None).rotulo != "mesmo"
