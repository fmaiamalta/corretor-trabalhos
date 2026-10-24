"""Exportação de notas (CSV para Excel) e feedback por aluno (HTML pronto a imprimir em PDF)."""

from __future__ import annotations

import csv
import html
from pathlib import Path

from corretor.modelos import Tarefa


def exportar_csv(tarefa: Tarefa, caminho: str | Path) -> None:
    # Ponto e vírgula e BOM para o Excel em português abrir as colunas certas.
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Aluno", *[c.nome for c in tarefa.criterios], "Nota final", "Revisto"])
        for t in tarefa.trabalhos:
            notas = {a.criterio: a.nota for a in t.avaliacoes}
            w.writerow([
                t.aluno,
                *[f"{notas[c.nome]:g}".replace(".", ",") if c.nome in notas else "" for c in tarefa.criterios],
                f"{t.nota_final:g}".replace(".", ",") if t.nota_final is not None else "",
                "Sim" if t.revisto else "Não",
            ])


def exportar_feedback(tarefa: Tarefa, pasta: str | Path) -> int:
    """Cria um ficheiro HTML por aluno corrigido. Devolve quantos ficheiros criou."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    e = html.escape
    n = 0
    for t in tarefa.trabalhos:
        if t.nota_final is None:
            continue
        linhas = "".join(
            f"<tr><td>{e(a.criterio)}</td><td>{a.nota:g}</td><td>{e(a.comentario)}</td></tr>" for a in t.avaliacoes
        )
        fortes = "".join(f"<li>{e(p)}</li>" for p in t.pontos_fortes)
        sugestoes = "".join(f"<li>{e(s)}</li>" for s in t.sugestoes)
        pagina = f"""<!DOCTYPE html>
<html lang="pt"><head><meta charset="utf-8"><title>{e(tarefa.titulo)} - {e(t.aluno)}</title>
<style>body{{font-family:sans-serif;max-width:800px;margin:2em auto;line-height:1.5}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px;vertical-align:top}}
.nota{{font-size:1.6em}}</style></head><body>
<h1>{e(tarefa.titulo)}</h1>
<p><strong>Aluno:</strong> {e(t.aluno)}</p>
<p class="nota"><strong>Nota:</strong> {t.nota_final:g} / {tarefa.escala:g}</p>
<p>{e(t.resumo)}</p>
<h2>Critérios</h2><table><tr><th>Critério</th><th>Nota</th><th>Comentário</th></tr>{linhas}</table>
<h2>Pontos fortes</h2><ul>{fortes}</ul>
<h2>O que podes melhorar</h2><ul>{sugestoes}</ul>
</body></html>"""
        nome = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in t.aluno).strip() or f"aluno_{n + 1}"
        (pasta / f"{nome}.html").write_text(pagina, encoding="utf-8")
        n += 1
    return n
