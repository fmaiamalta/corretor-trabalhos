"""Lê os ficheiros de um trabalho e corre as verificações adequadas ao tipo da tarefa."""

from __future__ import annotations

import re
import zipfile
from html import unescape  # o nome "html" fica para o submódulo de verificações
from pathlib import Path

from corretor.modelos import Tarefa, Trabalho, Verificacao
from corretor.verificadores.css import verificar_css
from corretor.verificadores.excel import ler_excel, verificar_excel
from corretor.verificadores.html import verificar_html
from corretor.verificadores.python_codigo import verificar_python


def _ler_docx(caminho: Path) -> str:
    """Só o texto, parágrafo a parágrafo. Imagens e formatação ficam de fora."""
    with zipfile.ZipFile(caminho) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    paragrafos = re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S)
    textos = ("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)) for p in paragrafos)
    return "\n".join(unescape(t) for t in textos if t.strip())


def ler_ficheiro(caminho: str) -> str:
    p = Path(caminho)
    ext = p.suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader

        return "\n".join(pag.extract_text() or "" for pag in PdfReader(p).pages)
    if ext == ".docx":
        return _ler_docx(p)
    if ext in (".xlsx", ".xlsm", ".xls"):
        return ler_excel(caminho)
    return p.read_text(encoding="utf-8", errors="replace")


def verificar(tarefa: Tarefa, trabalho: Trabalho) -> tuple[list[Verificacao], dict[str, str]]:
    """Devolve as verificações e o conteúdo de cada ficheiro (para enviar à IA)."""
    conteudos: dict[str, str] = {}
    res: list[Verificacao] = []
    for caminho in trabalho.ficheiros:
        nome = Path(caminho).name
        try:
            conteudos[nome] = ler_ficheiro(caminho)
        except Exception as e:  # ficheiro apagado, PDF danificado, etc.
            res.append(Verificacao(False, f"{nome}: não foi possível ler ({e})."))

    for nome, texto in conteudos.items():
        ext = Path(nome).suffix.lower()
        if ext in (".html", ".htm") and tarefa.tipo in ("html", "web"):
            res += [Verificacao(v.ok, f"[{nome}] {v.mensagem}") for v in verificar_html(texto)]
        elif ext == ".css" and tarefa.tipo in ("css", "web"):
            res += [Verificacao(v.ok, f"[{nome}] {v.mensagem}") for v in verificar_css(texto)]
        elif ext == ".py" and tarefa.tipo == "python":
            res += [Verificacao(v.ok, f"[{nome}] {v.mensagem}") for v in verificar_python(texto, tarefa.testes)]

    if tarefa.tipo == "excel":
        for caminho in trabalho.ficheiros:
            nome = Path(caminho).name
            if nome in conteudos and Path(caminho).suffix.lower() in (".xlsx", ".xlsm"):
                res += [Verificacao(v.ok, f"[{nome}] {v.mensagem}") for v in verificar_excel(caminho)]

    if tarefa.tipo == "web" and not any(n.lower().endswith(".css") for n in conteudos):
        res.append(Verificacao(False, "Não foi entregue nenhum ficheiro .css."))
    return res, conteudos
