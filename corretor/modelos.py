"""Dados de uma tarefa e dos trabalhos dos alunos, com gravação em JSON."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

TIPOS = {
    "html": "HTML",
    "css": "CSS",
    "web": "HTML + CSS",
    "python": "Python",
    "texto": "Texto / PDF (respostas escritas)",
}


@dataclass
class Criterio:
    nome: str
    peso: float  # percentagem, a soma dos pesos deve dar 100
    descricao: str = ""


@dataclass
class TestePython:
    """Um teste de entrada/saída: o programa recebe `entrada` e deve escrever `saida`."""

    __test__ = False  # o nome começa por "Teste" mas não é um teste do pytest

    entrada: str
    saida: str


@dataclass
class Verificacao:
    ok: bool
    mensagem: str


@dataclass
class AvaliacaoCriterio:
    criterio: str
    nota: float  # na escala da tarefa
    comentario: str


@dataclass
class Trabalho:
    aluno: str
    ficheiros: list[str]
    estado: str = "Por corrigir"
    verificacoes: list[Verificacao] = field(default_factory=list)
    avaliacoes: list[AvaliacaoCriterio] = field(default_factory=list)
    pontos_fortes: list[str] = field(default_factory=list)
    sugestoes: list[str] = field(default_factory=list)
    resumo: str = ""
    nota_final: float | None = None
    revisto: bool = False


@dataclass
class Tarefa:
    titulo: str = "Nova tarefa"
    tipo: str = "html"
    nivel: str = ""
    enunciado: str = ""
    escala: float = 20.0
    criterios: list[Criterio] = field(default_factory=list)
    testes: list[TestePython] = field(default_factory=list)
    trabalhos: list[Trabalho] = field(default_factory=list)

    def soma_pesos(self) -> float:
        return sum(c.peso for c in self.criterios)

    def calcular_nota(self, trabalho: Trabalho) -> float | None:
        """Média ponderada das notas por critério, arredondada a uma casa decimal."""
        pesos = {c.nome: c.peso for c in self.criterios}
        total = self.soma_pesos()
        if not trabalho.avaliacoes or total <= 0:
            return None
        soma = sum(a.nota * pesos.get(a.criterio, 0) for a in trabalho.avaliacoes)
        return round(soma / total, 1)

    def gravar(self, caminho: str | Path) -> None:
        Path(caminho).write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def abrir(cls, caminho: str | Path) -> "Tarefa":
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        trabalhos = []
        for t in dados.pop("trabalhos", []):
            t["verificacoes"] = [Verificacao(**v) for v in t.get("verificacoes", [])]
            t["avaliacoes"] = [AvaliacaoCriterio(**a) for a in t.get("avaliacoes", [])]
            trabalhos.append(Trabalho(**t))
        return cls(
            criterios=[Criterio(**c) for c in dados.pop("criterios", [])],
            testes=[TestePython(**t) for t in dados.pop("testes", [])],
            trabalhos=trabalhos,
            **dados,
        )
