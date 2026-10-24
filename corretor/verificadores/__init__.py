"""Lê os ficheiros de um trabalho e corre as verificações adequadas ao tipo da tarefa."""

from __future__ import annotations

from pathlib import Path

from corretor.modelos import Tarefa, Trabalho, Verificacao
from corretor.verificadores.css import verificar_css
from corretor.verificadores.html import verificar_html
from corretor.verificadores.python_codigo import verificar_python

EXTENSOES_TEXTO = {".html", ".htm", ".css", ".py", ".js", ".txt", ".md"}


def ler_ficheiro(caminho: str) -> str:
    p = Path(caminho)
    if p.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n".join(pag.extract_text() or "" for pag in PdfReader(p).pages)
    if p.suffix.lower() == ".docx":
        raise ValueError("Ficheiros .docx ainda não são suportados. Guarda o documento como PDF.")
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

    if tarefa.tipo == "web" and not any(n.lower().endswith(".css") for n in conteudos):
        res.append(Verificacao(False, "Não foi entregue nenhum ficheiro .css."))
    return res, conteudos
