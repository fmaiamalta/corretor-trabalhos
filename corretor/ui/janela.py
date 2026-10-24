"""Janela principal: separador da tarefa (enunciado e rubrica) e separador dos trabalhos."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from corretor.exportar import exportar_csv, exportar_feedback
from corretor.modelos import TIPOS, AvaliacaoCriterio, Criterio, Tarefa, TestePython, Trabalho
from corretor.verificadores import ler_ficheiro, verificar

FILTRO_FICHEIROS = "Trabalhos (*.html *.htm *.css *.py *.js *.txt *.md *.pdf *.docx *.xlsx *.xlsm);;Todos (*)"
FILTRO_ENUNCIADO = "Enunciados (*.pdf *.docx *.txt *.md *.xlsx);;Todos (*)"


def _item(texto: str, editavel: bool = True) -> QTableWidgetItem:
    it = QTableWidgetItem(texto)
    if not editavel:
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


class Corretor(QThread):
    """Corrige os trabalhos indicados fora da thread da interface."""

    progresso = Signal(int, str)  # índice do trabalho, estado

    def __init__(self, tarefa: Tarefa, indices: list[int], chave_api: str, usar_ia: bool):
        super().__init__()
        self.tarefa, self.indices, self.chave_api, self.usar_ia = tarefa, indices, chave_api, usar_ia

    def run(self) -> None:
        for i in self.indices:
            t = self.tarefa.trabalhos[i]
            self.progresso.emit(i, "A corrigir...")
            try:
                t.verificacoes, conteudos = verificar(self.tarefa, t)
                if self.usar_ia:
                    from corretor.ia import corrigir_com_ia

                    corrigir_com_ia(self.tarefa, t, f"A{i + 1:02d}", t.verificacoes, conteudos, self.chave_api)
                    t.nota_final = self.tarefa.calcular_nota(t)
                t.revisto = False
                t.estado = "Corrigido (por rever)" if self.usar_ia else "Verificado"
            except Exception as e:  # erro de rede, chave inválida, ficheiro ilegível
                t.estado = f"Erro: {e}"
            self.progresso.emit(i, t.estado)


class Janela(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Corretor de Trabalhos")
        self.resize(1200, 760)
        self.definicoes = QSettings("CorretorTrabalhos", "Corretor")
        self.tarefa = Tarefa(criterios=[Criterio("Cumprimento do enunciado", 50), Criterio("Qualidade do código", 50)])
        self.caminho: str | None = None
        self.corretor: Corretor | None = None
        self.atual: int | None = None

        self._menu()
        self.tabs = QTabWidget()
        self.tabs.addTab(self._separador_tarefa(), "1. Tarefa")
        self.tabs.addTab(self._separador_trabalhos(), "2. Trabalhos")
        self.setCentralWidget(self.tabs)
        self._carregar_tarefa()

    # ---------- menu ----------
    def _menu(self) -> None:
        barra = self.addToolBar("Principal")
        barra.setMovable(False)
        for texto, func in [
            ("Nova tarefa", self.nova),
            ("Abrir...", self.abrir),
            ("Gravar", self.gravar),
            ("Exportar notas (CSV)", self.exportar_notas),
            ("Exportar feedback", self.exportar_feedback),
            ("Chave da API", self.pedir_chave),
        ]:
            a = QAction(texto, self)
            a.triggered.connect(func)
            barra.addAction(a)

    # ---------- separador 1: tarefa ----------
    def _separador_tarefa(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.ed_titulo = QLineEdit()
        self.cb_tipo = QComboBox()
        for chave, nome in TIPOS.items():
            self.cb_tipo.addItem(nome, chave)
        self.cb_tipo.currentIndexChanged.connect(self._tipo_mudou)
        self.ed_nivel = QLineEdit()
        self.ed_nivel.setPlaceholderText("ex: 10.º ano, Curso Profissional de Informática")
        self.sp_escala = QDoubleSpinBox()
        self.sp_escala.setRange(1, 100)
        self.ed_enunciado = QPlainTextEdit()
        self.ed_enunciado.setPlaceholderText("Cola aqui o enunciado que deste aos alunos, ou carrega-o de um ficheiro.")
        bt_enunciado = QPushButton("Carregar enunciado de ficheiro...")
        bt_enunciado.clicked.connect(self.carregar_enunciado)
        caixa_enunciado = QWidget()
        le = QVBoxLayout(caixa_enunciado)
        le.setContentsMargins(0, 0, 0, 0)
        le.addWidget(self.ed_enunciado)
        le.addWidget(bt_enunciado, alignment=Qt.AlignLeft)

        self.tb_criterios = QTableWidget(0, 3)
        self.tb_criterios.setHorizontalHeaderLabels(["Critério", "Peso (%)", "O que se espera"])
        self.tb_criterios.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.lb_pesos = QLabel()
        self.tb_criterios.itemChanged.connect(self._atualizar_soma_pesos)
        crit = QWidget()
        lc = QVBoxLayout(crit)
        lc.setContentsMargins(0, 0, 0, 0)
        lc.addWidget(self.tb_criterios)
        bc = QHBoxLayout()
        for texto, func in [("Adicionar critério", self._add_criterio), ("Remover", lambda: self._remover_linha(self.tb_criterios))]:
            b = QPushButton(texto)
            b.clicked.connect(func)
            bc.addWidget(b)
        bc.addStretch()
        bc.addWidget(self.lb_pesos)
        lc.addLayout(bc)

        self.tb_testes = QTableWidget(0, 2)
        self.tb_testes.setHorizontalHeaderLabels(["Entrada (o que o aluno escreve no input)", "Saída esperada"])
        self.tb_testes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.box_testes = QWidget()
        lt = QVBoxLayout(self.box_testes)
        lt.setContentsMargins(0, 0, 0, 0)
        lt.addWidget(QLabel("Cada linha da entrada é uma resposta a um input(). A saída esperada tem de aparecer no que o programa escreve."))
        lt.addWidget(self.tb_testes)
        bt = QHBoxLayout()
        for texto, func in [("Adicionar teste", lambda: self.tb_testes.insertRow(self.tb_testes.rowCount())),
                            ("Remover", lambda: self._remover_linha(self.tb_testes))]:
            b = QPushButton(texto)
            b.clicked.connect(func)
            bt.addWidget(b)
        bt.addStretch()
        lt.addLayout(bt)

        form.addRow("Título", self.ed_titulo)
        form.addRow("Tipo de trabalho", self.cb_tipo)
        form.addRow("Nível", self.ed_nivel)
        form.addRow("Nota máxima", self.sp_escala)
        form.addRow("Enunciado", caixa_enunciado)
        form.addRow("Rubrica", crit)
        form.addRow("Testes", self.box_testes)
        return w

    def carregar_enunciado(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Enunciado", "", FILTRO_ENUNCIADO)
        if not caminho:
            return
        try:
            texto = ler_ficheiro(caminho)
        except Exception as e:
            QMessageBox.critical(self, "Enunciado", f"Não foi possível ler o ficheiro:\n{e}")
            return
        if not texto.strip():
            QMessageBox.warning(self, "Enunciado", "O ficheiro não tem texto que se consiga ler (é uma imagem digitalizada?).")
            return
        if self.ed_enunciado.toPlainText().strip() and QMessageBox.question(
            self, "Enunciado", "Substituir o enunciado que já está escrito?"
        ) != QMessageBox.Yes:
            return
        self.ed_enunciado.setPlainText(texto)

    def _add_criterio(self) -> None:
        r = self.tb_criterios.rowCount()
        self.tb_criterios.insertRow(r)
        self.tb_criterios.setItem(r, 0, _item("Novo critério"))
        self.tb_criterios.setItem(r, 1, _item("0"))
        self.tb_criterios.setItem(r, 2, _item(""))

    @staticmethod
    def _remover_linha(tabela: QTableWidget) -> None:
        if tabela.currentRow() >= 0:
            tabela.removeRow(tabela.currentRow())

    def _tipo_mudou(self) -> None:
        self.box_testes.setVisible(self.cb_tipo.currentData() == "python")

    def _atualizar_soma_pesos(self) -> None:
        soma = 0.0
        for r in range(self.tb_criterios.rowCount()):
            it = self.tb_criterios.item(r, 1)
            try:
                soma += float((it.text() if it else "0").replace(",", "."))
            except ValueError:
                pass
        cor = "green" if abs(soma - 100) < 0.01 else "red"
        self.lb_pesos.setText(f"<span style='color:{cor}'>Soma dos pesos: {soma:g}%</span>")

    def _ler_tarefa(self) -> bool:
        """Passa o formulário para self.tarefa. Devolve False se a rubrica tiver erros."""
        t = self.tarefa
        t.titulo = self.ed_titulo.text().strip() or "Sem título"
        t.tipo = self.cb_tipo.currentData()
        t.nivel = self.ed_nivel.text().strip()
        t.escala = self.sp_escala.value()
        t.enunciado = self.ed_enunciado.toPlainText()
        criterios = []
        for r in range(self.tb_criterios.rowCount()):
            nome = (self.tb_criterios.item(r, 0).text() if self.tb_criterios.item(r, 0) else "").strip()
            peso_txt = self.tb_criterios.item(r, 1).text() if self.tb_criterios.item(r, 1) else "0"
            desc = self.tb_criterios.item(r, 2).text() if self.tb_criterios.item(r, 2) else ""
            if not nome:
                continue
            try:
                peso = float(peso_txt.replace(",", "."))
            except ValueError:
                QMessageBox.warning(self, "Rubrica", f"O peso de '{nome}' não é um número.")
                return False
            criterios.append(Criterio(nome, peso, desc))
        t.criterios = criterios
        t.testes = []
        for r in range(self.tb_testes.rowCount()):
            ent = self.tb_testes.item(r, 0).text() if self.tb_testes.item(r, 0) else ""
            sai = self.tb_testes.item(r, 1).text() if self.tb_testes.item(r, 1) else ""
            if sai.strip():
                # Na tabela escreve-se "\n" ou " | " para separar várias respostas.
                t.testes.append(TestePython(ent.replace(" | ", "\n").replace("\\n", "\n"), sai))
        return True

    def _carregar_tarefa(self) -> None:
        t = self.tarefa
        self.ed_titulo.setText(t.titulo)
        self.cb_tipo.setCurrentIndex(max(0, self.cb_tipo.findData(t.tipo)))
        self.ed_nivel.setText(t.nivel)
        self.sp_escala.setValue(t.escala)
        self.ed_enunciado.setPlainText(t.enunciado)
        self.tb_criterios.blockSignals(True)
        self.tb_criterios.setRowCount(0)
        for c in t.criterios:
            r = self.tb_criterios.rowCount()
            self.tb_criterios.insertRow(r)
            self.tb_criterios.setItem(r, 0, _item(c.nome))
            self.tb_criterios.setItem(r, 1, _item(f"{c.peso:g}"))
            self.tb_criterios.setItem(r, 2, _item(c.descricao))
        self.tb_criterios.blockSignals(False)
        self._atualizar_soma_pesos()
        self.tb_testes.setRowCount(0)
        for teste in t.testes:
            r = self.tb_testes.rowCount()
            self.tb_testes.insertRow(r)
            self.tb_testes.setItem(r, 0, _item(teste.entrada.replace("\n", " | ")))
            self.tb_testes.setItem(r, 1, _item(teste.saida))
        self._tipo_mudou()
        self._preencher_trabalhos()
        self._mostrar_detalhe(None)

    # ---------- separador 2: trabalhos ----------
    def _separador_trabalhos(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        botoes = QHBoxLayout()
        for texto, func in [
            ("Adicionar trabalho...", self.adicionar_trabalho),
            ("Remover", self.remover_trabalho),
            ("Corrigir selecionado", lambda: self.corrigir(apenas_selecionado=True)),
            ("Corrigir todos", lambda: self.corrigir(apenas_selecionado=False)),
        ]:
            b = QPushButton(texto)
            b.clicked.connect(func)
            botoes.addWidget(b)
        self.ck_ia = QCheckBox("Usar IA para nota e feedback")
        self.ck_ia.setChecked(True)
        botoes.addWidget(self.ck_ia)
        botoes.addStretch()
        lay.addLayout(botoes)

        div = QSplitter()
        self.tb_trabalhos = QTableWidget(0, 4)
        self.tb_trabalhos.setHorizontalHeaderLabels(["Aluno", "Ficheiros", "Estado", "Nota"])
        self.tb_trabalhos.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tb_trabalhos.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tb_trabalhos.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tb_trabalhos.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb_trabalhos.currentCellChanged.connect(lambda r, *_: self._mostrar_detalhe(r if r >= 0 else None))
        div.addWidget(self.tb_trabalhos)

        det = QWidget()
        ld = QVBoxLayout(det)
        self.lb_aluno = QLabel()
        self.lb_aluno.setStyleSheet("font-size: 16px; font-weight: bold")
        ld.addWidget(self.lb_aluno)
        ld.addWidget(QLabel("Verificações automáticas"))
        self.ls_verif = QListWidget()
        self.ls_verif.setWordWrap(True)
        ld.addWidget(self.ls_verif, 2)
        ld.addWidget(QLabel("As tuas observações (a IA segue-as na nota e no feedback)"))
        self.ed_obs = QPlainTextEdit()
        self.ed_obs.setPlaceholderText("ex: O gráfico não é adequado aos dados. Usou valores fixos nos totais. A nota não deve passar de 14.")
        self.ed_obs.textChanged.connect(self._obs_mudou)
        ld.addWidget(self.ed_obs, 1)
        self.bt_obs = QPushButton("Gerar correção com as minhas observações")
        self.bt_obs.clicked.connect(lambda: self.corrigir(apenas_selecionado=True))
        ld.addWidget(self.bt_obs, alignment=Qt.AlignRight)
        ld.addWidget(QLabel("Notas por critério (podes editar a nota e o comentário)"))
        self.tb_aval = QTableWidget(0, 3)
        self.tb_aval.setHorizontalHeaderLabels(["Critério", "Nota", "Comentário"])
        self.tb_aval.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tb_aval.setWordWrap(True)
        ld.addWidget(self.tb_aval, 3)
        ld.addWidget(QLabel("Resumo para o aluno"))
        self.ed_resumo = QPlainTextEdit()
        ld.addWidget(self.ed_resumo, 1)
        ld.addWidget(QLabel("Pontos fortes (um por linha)"))
        self.ed_fortes = QPlainTextEdit()
        ld.addWidget(self.ed_fortes, 1)
        ld.addWidget(QLabel("Sugestões de melhoria (uma por linha)"))
        self.ed_sugestoes = QPlainTextEdit()
        ld.addWidget(self.ed_sugestoes, 1)
        linha = QHBoxLayout()
        self.lb_nota = QLabel()
        self.lb_nota.setStyleSheet("font-size: 16px")
        linha.addWidget(self.lb_nota)
        linha.addStretch()
        self.bt_rever = QPushButton("Guardar revisão")
        self.bt_rever.clicked.connect(self.guardar_revisao)
        linha.addWidget(self.bt_rever)
        ld.addLayout(linha)
        div.addWidget(det)
        div.setSizes([450, 750])
        lay.addWidget(div)
        return w

    def _preencher_trabalhos(self) -> None:
        self.tb_trabalhos.setRowCount(0)
        for i, t in enumerate(self.tarefa.trabalhos):
            self.tb_trabalhos.insertRow(i)
            self._atualizar_linha(i)

    def _atualizar_linha(self, i: int) -> None:
        t = self.tarefa.trabalhos[i]
        nota = f"{t.nota_final:g}" if t.nota_final is not None else ""
        estado = "Revisto" if t.revisto else t.estado
        for col, texto in enumerate([t.aluno, ", ".join(Path(f).name for f in t.ficheiros), estado, nota]):
            it = _item(texto, editavel=False)
            if col == 2 and estado.startswith("Erro"):
                it.setForeground(QColor("red"))
            self.tb_trabalhos.setItem(i, col, it)

    def adicionar_trabalho(self) -> None:
        ficheiros, _ = QFileDialog.getOpenFileNames(self, "Ficheiros do trabalho de um aluno", "", FILTRO_FICHEIROS)
        if not ficheiros:
            return
        sugestao = Path(ficheiros[0]).stem if len(ficheiros) == 1 else Path(ficheiros[0]).parent.name
        nome, ok = QInputDialog.getText(self, "Aluno", "Nome do aluno:", text=sugestao)
        if not ok or not nome.strip():
            return
        self.tarefa.trabalhos.append(Trabalho(aluno=nome.strip(), ficheiros=ficheiros))
        self._preencher_trabalhos()
        self.tb_trabalhos.selectRow(len(self.tarefa.trabalhos) - 1)

    def remover_trabalho(self) -> None:
        r = self.tb_trabalhos.currentRow()
        if r < 0 or self._a_corrigir():
            return
        if QMessageBox.question(self, "Remover", f"Remover o trabalho de {self.tarefa.trabalhos[r].aluno}?") == QMessageBox.Yes:
            del self.tarefa.trabalhos[r]
            self._preencher_trabalhos()
            self._mostrar_detalhe(None)

    def _a_corrigir(self) -> bool:
        if self.corretor and self.corretor.isRunning():
            QMessageBox.information(self, "Aguarda", "Ainda há trabalhos a ser corrigidos.")
            return True
        return False

    def corrigir(self, apenas_selecionado: bool) -> None:
        if self._a_corrigir() or not self._ler_tarefa():
            return
        if not self.tarefa.trabalhos:
            QMessageBox.information(self, "Corrigir", "Adiciona primeiro os trabalhos dos alunos.")
            return
        if abs(self.tarefa.soma_pesos() - 100) > 0.01:
            QMessageBox.warning(self, "Rubrica", "A soma dos pesos dos critérios tem de dar 100%.")
            self.tabs.setCurrentIndex(0)
            return
        chave = self._chave()
        if self.ck_ia.isChecked() and not chave:
            self.pedir_chave()
            chave = self._chave()
            if not chave:
                return
        if apenas_selecionado:
            r = self.tb_trabalhos.currentRow()
            if r < 0:
                QMessageBox.information(self, "Corrigir", "Seleciona um trabalho na tabela.")
                return
            indices = [r]
        else:
            indices = list(range(len(self.tarefa.trabalhos)))
        self.corretor = Corretor(self.tarefa, indices, chave, self.ck_ia.isChecked())
        self.corretor.progresso.connect(self._progresso)
        self.corretor.start()

    def _progresso(self, i: int, _estado: str) -> None:
        self._atualizar_linha(i)
        if i == self.atual:
            self._mostrar_detalhe(i)

    def _mostrar_detalhe(self, i: int | None) -> None:
        self.atual = i
        ativo = i is not None and i < len(self.tarefa.trabalhos)
        for w in (self.ed_obs, self.bt_obs, self.tb_aval, self.ed_resumo, self.ed_fortes, self.ed_sugestoes, self.bt_rever):
            w.setEnabled(ativo)
        self.ls_verif.clear()
        self.tb_aval.setRowCount(0)
        if not ativo:
            self.lb_aluno.setText("Seleciona um trabalho")
            self.lb_nota.setText("")
            for ed in (self.ed_obs, self.ed_resumo, self.ed_fortes, self.ed_sugestoes):
                ed.setPlainText("")
            return
        t = self.tarefa.trabalhos[i]
        self.lb_aluno.setText(t.aluno)
        if self.ed_obs.toPlainText() != t.observacoes:
            self.ed_obs.setPlainText(t.observacoes)
        for v in t.verificacoes:
            it = QListWidgetItem(("✔ " if v.ok else "✘ ") + v.mensagem)
            it.setForeground(QColor("#1a7f37" if v.ok else "#cf222e"))
            self.ls_verif.addItem(it)
        notas = {a.criterio: a for a in t.avaliacoes}
        for c in self.tarefa.criterios:
            r = self.tb_aval.rowCount()
            self.tb_aval.insertRow(r)
            a = notas.get(c.nome)
            self.tb_aval.setItem(r, 0, _item(f"{c.nome} ({c.peso:g}%)", editavel=False))
            self.tb_aval.setItem(r, 1, _item(f"{a.nota:g}" if a else ""))
            self.tb_aval.setItem(r, 2, _item(a.comentario if a else ""))
        self.tb_aval.resizeRowsToContents()
        self.ed_resumo.setPlainText(t.resumo)
        self.ed_fortes.setPlainText("\n".join(t.pontos_fortes))
        self.ed_sugestoes.setPlainText("\n".join(t.sugestoes))
        nota = f"{t.nota_final:g} / {self.tarefa.escala:g}" if t.nota_final is not None else "sem nota"
        self.lb_nota.setText(f"Nota final: <b>{nota}</b>" + (" (revisto)" if t.revisto else ""))

    def _obs_mudou(self) -> None:
        if self.atual is not None and self.atual < len(self.tarefa.trabalhos):
            self.tarefa.trabalhos[self.atual].observacoes = self.ed_obs.toPlainText()

    def guardar_revisao(self) -> None:
        if self.atual is None:
            return
        t = self.tarefa.trabalhos[self.atual]
        avaliacoes = []
        for r, c in enumerate(self.tarefa.criterios):
            txt = self.tb_aval.item(r, 1).text().strip().replace(",", ".") if self.tb_aval.item(r, 1) else ""
            if not txt:
                continue
            try:
                nota = float(txt)
            except ValueError:
                QMessageBox.warning(self, "Nota", f"A nota de '{c.nome}' não é um número.")
                return
            if not 0 <= nota <= self.tarefa.escala:
                QMessageBox.warning(self, "Nota", f"A nota de '{c.nome}' tem de estar entre 0 e {self.tarefa.escala:g}.")
                return
            com = self.tb_aval.item(r, 2).text() if self.tb_aval.item(r, 2) else ""
            avaliacoes.append(AvaliacaoCriterio(c.nome, nota, com))
        t.avaliacoes = avaliacoes
        t.resumo = self.ed_resumo.toPlainText().strip()
        t.pontos_fortes = [l.strip() for l in self.ed_fortes.toPlainText().splitlines() if l.strip()]
        t.sugestoes = [l.strip() for l in self.ed_sugestoes.toPlainText().splitlines() if l.strip()]
        t.nota_final = self.tarefa.calcular_nota(t)
        t.revisto = True
        self._atualizar_linha(self.atual)
        self._mostrar_detalhe(self.atual)

    # ---------- ficheiros ----------
    def nova(self) -> None:
        if self._a_corrigir():
            return
        if QMessageBox.question(self, "Nova tarefa", "Começar uma tarefa nova? O que não gravaste perde-se.") == QMessageBox.Yes:
            self.tarefa = Tarefa(criterios=[Criterio("Cumprimento do enunciado", 50), Criterio("Qualidade do código", 50)])
            self.caminho = None
            self._carregar_tarefa()
            self.tabs.setCurrentIndex(0)

    def abrir(self) -> None:
        if self._a_corrigir():
            return
        caminho, _ = QFileDialog.getOpenFileName(self, "Abrir tarefa", "", "Tarefas (*.tarefa.json *.json)")
        if not caminho:
            return
        try:
            self.tarefa = Tarefa.abrir(caminho)
        except Exception as e:
            QMessageBox.critical(self, "Abrir", f"Não foi possível abrir o ficheiro:\n{e}")
            return
        self.caminho = caminho
        self._carregar_tarefa()

    def gravar(self) -> None:
        if not self._ler_tarefa():
            return
        if not self.caminho:
            caminho, _ = QFileDialog.getSaveFileName(self, "Gravar tarefa", f"{self.tarefa.titulo}.tarefa.json", "Tarefas (*.tarefa.json)")
            if not caminho:
                return
            self.caminho = caminho
        self.tarefa.gravar(self.caminho)
        self.statusBar().showMessage(f"Gravado em {self.caminho}", 4000)

    def exportar_notas(self) -> None:
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar notas", f"{self.tarefa.titulo} - notas.csv", "CSV (*.csv)")
        if caminho:
            exportar_csv(self.tarefa, caminho)
            self.statusBar().showMessage(f"Notas exportadas para {caminho}", 4000)

    def exportar_feedback(self) -> None:
        pasta = QFileDialog.getExistingDirectory(self, "Pasta para o feedback dos alunos")
        if pasta:
            n = exportar_feedback(self.tarefa, pasta)
            QMessageBox.information(self, "Feedback", f"Criei {n} ficheiro(s) em {pasta}.\nAbre no browser e imprime para PDF.")

    # ---------- chave da API ----------
    def _chave(self) -> str:
        return self.definicoes.value("chave_api", "") or os.environ.get("ANTHROPIC_API_KEY", "")

    def pedir_chave(self) -> None:
        chave, ok = QInputDialog.getText(
            self, "Chave da API",
            "Cola a tua chave da API da Anthropic (começa por sk-ant-).\nFica guardada só neste computador.",
            QLineEdit.Password, self._chave(),
        )
        if ok:
            self.definicoes.setValue("chave_api", chave.strip())
