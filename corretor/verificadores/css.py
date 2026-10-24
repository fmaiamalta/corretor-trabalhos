"""Verificações automáticas a ficheiros CSS."""

from __future__ import annotations

import re

from corretor.modelos import Verificacao

# Propriedades comuns no ensino. Uma propriedade fora da lista é sinal de erro de escrita
# (ex: "colour", "font-colour", "text-size"), mas a IA confirma.
PROPRIEDADES = set("""
align-content align-items align-self animation animation-delay animation-direction animation-duration
animation-iteration-count animation-name animation-timing-function aspect-ratio background background-attachment
background-color background-image background-position background-repeat background-size border border-bottom
border-collapse border-color border-left border-radius border-right border-spacing border-style border-top
border-width bottom box-shadow box-sizing clear color column-gap columns content cursor display filter flex
flex-basis flex-direction flex-flow flex-grow flex-shrink flex-wrap float font font-family font-size font-style
font-variant font-weight gap grid grid-area grid-column grid-row grid-template grid-template-areas
grid-template-columns grid-template-rows height inset justify-content justify-items justify-self left
letter-spacing line-height list-style list-style-image list-style-position list-style-type margin margin-bottom
margin-left margin-right margin-top max-height max-width min-height min-width object-fit opacity order outline
overflow overflow-x overflow-y padding padding-bottom padding-left padding-right padding-top place-items
position right row-gap scroll-behavior text-align text-decoration text-indent text-overflow text-shadow
text-transform top transform transition transition-delay transition-duration transition-property
transition-timing-function vertical-align visibility white-space width word-break word-spacing z-index
""".split())


def _sem_comentarios(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def verificar_css(css: str) -> list[Verificacao]:
    limpo = _sem_comentarios(css)
    res: list[Verificacao] = []

    abre, fecha = limpo.count("{"), limpo.count("}")
    res.append(Verificacao(abre == fecha, "Chavetas equilibradas." if abre == fecha else f"Chavetas desequilibradas: {abre} '{{' e {fecha} '}}'."))

    regras = re.findall(r"([^{}]+)\{([^{}]*)\}", limpo)
    seletores: dict[str, int] = {}
    vazias = 0
    desconhecidas: set[str] = set()
    for seletor, corpo in regras:
        seletor = " ".join(seletor.split())
        if seletor.startswith("@") or re.fullmatch(r"(from|to|\d+%)(\s*,\s*(from|to|\d+%))*", seletor):
            continue
        seletores[seletor] = seletores.get(seletor, 0) + 1
        declaracoes = [d for d in corpo.split(";") if d.strip()]
        if not declaracoes:
            vazias += 1
        for d in declaracoes:
            if ":" not in d:
                res.append(Verificacao(False, f"Declaração sem ':' em '{seletor}': {d.strip()[:40]}"))
                continue
            prop = d.split(":", 1)[0].strip().lower()
            if prop.startswith("--") or prop.startswith("-webkit-") or prop.startswith("-moz-"):
                continue
            if prop not in PROPRIEDADES:
                desconhecidas.add(prop)

    res.append(Verificacao(True, f"{len(regras)} regra(s) CSS encontradas."))
    if desconhecidas:
        res.append(Verificacao(False, f"Propriedades desconhecidas ou mal escritas: {', '.join(sorted(desconhecidas))}."))
    repetidos = [s for s, n in seletores.items() if n > 1]
    if repetidos:
        res.append(Verificacao(False, f"Seletores repetidos: {', '.join(repetidos[:5])}."))
    if vazias:
        res.append(Verificacao(False, f"{vazias} regra(s) vazia(s)."))
    importants = limpo.count("!important")
    if importants > 2:
        res.append(Verificacao(False, f"Usa !important {importants} vezes."))
    tem_media = "@media" in limpo
    res.append(Verificacao(tem_media, "Tem media queries (responsivo)." if tem_media else "Não tem media queries (@media)."))
    return res
