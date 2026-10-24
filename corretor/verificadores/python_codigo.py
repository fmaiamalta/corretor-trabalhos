"""Verificações a programas Python: sintaxe e testes de entrada/saída."""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from corretor.modelos import TestePython, Verificacao

TEMPO_MAXIMO = 5  # segundos por teste


def _interpretador() -> str:
    # Numa app empacotada, sys.executable é a própria app e não o Python.
    if getattr(sys, "frozen", False):
        return shutil.which("python3") or shutil.which("python") or "python"
    return sys.executable


def _normalizar(texto: str) -> str:
    return "\n".join(l.rstrip() for l in texto.strip().splitlines())


def verificar_python(codigo: str, testes: list[TestePython]) -> list[Verificacao]:
    try:
        arvore = ast.parse(codigo)
    except SyntaxError as e:
        return [Verificacao(False, f"Erro de sintaxe na linha {e.lineno}: {e.msg}.")]

    res = [Verificacao(True, "O código não tem erros de sintaxe.")]
    funcoes = [n.name for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef)]
    if funcoes:
        res.append(Verificacao(True, f"Define {len(funcoes)} função(ões): {', '.join(funcoes[:6])}."))

    if not testes:
        return res

    passou = 0
    with tempfile.TemporaryDirectory() as pasta:
        programa = Path(pasta) / "programa.py"
        programa.write_text(codigo, encoding="utf-8")
        for i, t in enumerate(testes, 1):
            try:
                r = subprocess.run(
                    [_interpretador(), "-I", str(programa)],
                    input=t.entrada,
                    capture_output=True,
                    text=True,
                    timeout=TEMPO_MAXIMO,
                    cwd=pasta,
                )
            except subprocess.TimeoutExpired:
                res.append(Verificacao(False, f"Teste {i}: demorou mais de {TEMPO_MAXIMO}s (ciclo infinito?)."))
                continue
            if r.returncode != 0:
                erro = (r.stderr.strip().splitlines() or ["erro desconhecido"])[-1]
                res.append(Verificacao(False, f"Teste {i}: o programa deu erro: {erro}"))
            elif _normalizar(t.saida) in _normalizar(r.stdout):
                passou += 1
                res.append(Verificacao(True, f"Teste {i}: passou."))
            else:
                obtido = _normalizar(r.stdout)[-120:] or "(nada)"
                res.append(Verificacao(False, f"Teste {i}: esperava '{_normalizar(t.saida)}', obteve '{obtido}'."))
    res.insert(1, Verificacao(passou == len(testes), f"Passou {passou} de {len(testes)} testes."))
    return res
