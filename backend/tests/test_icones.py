import struct

from coleta.icones import avaliar, baixar, url_do_icone
from coleta.http import Resposta
from tests.test_http import RelogioFalso, TransporteFalso, cliente


def png(lado: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", lado, lado) + b"\x08\x06\x00\x00\x00"


def test_avaliar_aceita_so_png_grande_e_200():
    assert avaliar(200, png(128)) == (True, "128x128")
    assert avaliar(200, png(16))[0] is False
    assert avaliar(404, png(128)) == (False, "HTTP 404 (ícone genérico)")
    assert avaliar(200, b"<html>")[1] == "não é PNG"


def test_url_vai_para_o_google_e_nao_para_a_loja():
    assert url_do_icone("www.kabum.com.br") == "https://www.google.com/s2/favicons?domain=www.kabum.com.br&sz=128"


async def test_baixar_salva_o_bom_e_deixa_o_ruim_no_monograma(tmp_path):
    relogio = RelogioFalso()
    t = TransporteFalso(relogio)
    t.em(url_do_icone("a.com"), Resposta(200, {}, png(128), url_do_icone("a.com")))
    t.em(url_do_icone("b.com"), Resposta(404, {}, png(16), url_do_icone("b.com")))
    feitos = await baixar(cliente(relogio, t, dir_dados=tmp_path), [("a", "a.com"), ("b", "b.com")], tmp_path / "lojas")
    assert [(s, ok) for s, ok, _ in feitos] == [("a", True), ("b", False)]
    assert (tmp_path / "lojas" / "a.png").exists() and not (tmp_path / "lojas" / "b.png").exists()
    assert all("google.com" in u for u in t.urls())
