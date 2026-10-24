"""Verificações automáticas a ficheiros HTML."""

from __future__ import annotations

from html.parser import HTMLParser

from corretor.modelos import Verificacao

VAZIAS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# Tags que o HTML permite deixar por fechar sem erro.
FECHO_OPCIONAL = {"li", "p", "td", "th", "tr", "option", "dt", "dd", "thead", "tbody", "tfoot"}
SEMANTICAS = ["header", "nav", "main", "section", "article", "footer"]
OBSOLETAS = {"font", "center", "marquee", "big", "strike", "frame", "frameset"}


class _Analisador(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pilha: list[tuple[str, int]] = []
        self.erros_fecho: list[str] = []
        self.tags: dict[str, int] = {}
        self.imgs_sem_alt: list[int] = []
        self.html_lang = False
        self.doctype = False
        self.titulo = ""
        self._no_titulo = False
        self.estilos_inline = 0

    def handle_decl(self, decl: str) -> None:
        if decl.lower().startswith("doctype html"):
            self.doctype = True

    def handle_starttag(self, tag, attrs):
        linha = self.getpos()[0]
        a = dict(attrs)
        self.tags[tag] = self.tags.get(tag, 0) + 1
        if tag == "html" and a.get("lang"):
            self.html_lang = True
        if tag == "img" and not a.get("alt"):
            self.imgs_sem_alt.append(linha)
        if "style" in a:
            self.estilos_inline += 1
        if tag == "title":
            self._no_titulo = True
        if tag not in VAZIAS:
            self.pilha.append((tag, linha))

    def handle_startendtag(self, tag, attrs):
        # <img ... /> conta como abertura sem precisar de fecho.
        self.handle_starttag(tag, attrs)
        if tag not in VAZIAS and self.pilha and self.pilha[-1][0] == tag:
            self.pilha.pop()

    def handle_endtag(self, tag):
        linha = self.getpos()[0]
        if tag == "title":
            self._no_titulo = False
        if tag in VAZIAS:
            return
        if not any(t == tag for t, _ in self.pilha):
            self.erros_fecho.append(f"Linha {linha}: </{tag}> fecha uma tag que não foi aberta.")
            return
        while self.pilha:
            aberta, l_aberta = self.pilha.pop()
            if aberta == tag:
                break
            if aberta not in FECHO_OPCIONAL:
                self.erros_fecho.append(f"Linha {l_aberta}: <{aberta}> não foi fechada antes de </{tag}>.")

    def handle_data(self, data):
        if self._no_titulo:
            self.titulo += data


def verificar_html(codigo: str) -> list[Verificacao]:
    p = _Analisador()
    p.feed(codigo)
    p.close()
    for tag, linha in p.pilha:
        if tag not in FECHO_OPCIONAL:
            p.erros_fecho.append(f"Linha {linha}: <{tag}> nunca foi fechada.")

    res = [
        Verificacao(p.doctype, "Tem <!DOCTYPE html>." if p.doctype else "Falta <!DOCTYPE html> no início."),
        Verificacao(p.html_lang, "<html> tem o atributo lang." if p.html_lang else "Falta lang em <html> (ex: lang=\"pt\")."),
        Verificacao(bool(p.titulo.strip()), "Tem <title>." if p.titulo.strip() else "Falta <title> ou está vazio."),
    ]
    if p.erros_fecho:
        res += [Verificacao(False, e) for e in p.erros_fecho[:10]]
        if len(p.erros_fecho) > 10:
            res.append(Verificacao(False, f"... e mais {len(p.erros_fecho) - 10} problemas de fecho de tags."))
    else:
        res.append(Verificacao(True, "Todas as tags estão bem fechadas."))

    if p.imgs_sem_alt:
        linhas = ", ".join(str(l) for l in p.imgs_sem_alt)
        res.append(Verificacao(False, f"{len(p.imgs_sem_alt)} imagem(ns) sem alt (linhas {linhas})."))
    elif p.tags.get("img"):
        res.append(Verificacao(True, "Todas as imagens têm alt."))

    usadas = [t for t in SEMANTICAS if p.tags.get(t)]
    res.append(Verificacao(
        len(usadas) >= 2,
        f"Tags semânticas usadas: {', '.join(usadas)}." if usadas else "Não usa tags semânticas (header, nav, main, footer...).",
    ))
    obsoletas = sorted(t for t in OBSOLETAS if p.tags.get(t))
    if obsoletas:
        res.append(Verificacao(False, f"Usa tags obsoletas: {', '.join(obsoletas)}."))
    if p.estilos_inline:
        res.append(Verificacao(False, f"{p.estilos_inline} elemento(s) com style=\"...\" no HTML. O CSS deve ir para um ficheiro à parte."))
    return res
