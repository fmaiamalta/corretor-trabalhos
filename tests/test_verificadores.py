from corretor.ia import anonimizar
from corretor.modelos import AvaliacaoCriterio, Criterio, Tarefa, TestePython, Trabalho
from corretor.verificadores.css import verificar_css
from corretor.verificadores.html import verificar_html
from corretor.verificadores.python_codigo import verificar_python


def _falhas(res):
    return [v.mensagem for v in res if not v.ok]


def test_html_correto():
    codigo = """<!DOCTYPE html><html lang="pt"><head><title>Olá</title></head>
<body><header>x</header><main><p>texto<img src="a.png" alt="a"></main><footer></footer></body></html>"""
    assert _falhas(verificar_html(codigo)) == []


def test_html_com_erros():
    codigo = """<html><body><div><span>sem fecho</div><img src="a.png"><center>x</center></body></html>"""
    falhas = " ".join(_falhas(verificar_html(codigo)))
    assert "DOCTYPE" in falhas
    assert "lang" in falhas
    assert "<span> não foi fechada" in falhas
    assert "sem alt" in falhas
    assert "obsoletas: center" in falhas


def test_css():
    css = "h1 { colour: red; }\nh1 { color: blue }\np {}\n@media (max-width: 600px) { p { font-size: 12px; } }"
    falhas = " ".join(_falhas(verificar_css(css)))
    assert "colour" in falhas
    assert "Seletores repetidos: h1" in falhas
    assert "vazia" in falhas
    assert "media queries" not in falhas


def test_css_chavetas():
    assert "desequilibradas" in " ".join(_falhas(verificar_css("p { color: red;")))


def test_python_testes():
    codigo = "a = int(input())\nb = int(input())\nprint('Soma:', a + b)\n"
    testes = [TestePython("2\n3", "Soma: 5"), TestePython("1\n1", "Soma: 3")]
    res = verificar_python(codigo, testes)
    assert any("Passou 1 de 2" in v.mensagem for v in res)


def test_python_sintaxe_e_ciclo_infinito():
    assert "sintaxe" in _falhas(verificar_python("print('a'", []))[0]
    res = verificar_python("while True:\n    pass\n", [TestePython("", "x")])
    assert any("demorou" in m for m in _falhas(res))


def test_anonimizar():
    texto = "Site da Maria Silva. Autora: maria. Mariana não muda."
    assert anonimizar(texto, "Maria Silva", "A01") == "Site da A01. Autora: A01. Mariana não muda."


def test_nota_ponderada_e_gravacao(tmp_path):
    t = Tarefa(criterios=[Criterio("A", 30), Criterio("B", 70)])
    tr = Trabalho("Rui", ["x.html"], avaliacoes=[AvaliacaoCriterio("A", 10, ""), AvaliacaoCriterio("B", 20, "")])
    t.trabalhos.append(tr)
    assert t.calcular_nota(tr) == 17.0
    t.gravar(tmp_path / "t.json")
    assert Tarefa.abrir(tmp_path / "t.json") == t
