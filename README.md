# Corretor de Trabalhos

App de computador (Windows, macOS, Linux) para corrigir trabalhos de informática com verificações automáticas e feedback da IA (Claude, da Anthropic).

## O que faz

1. No separador **Tarefa** defines o título, o tipo, o nível, a nota máxima e a rubrica (critérios com pesos que somam 100%). O enunciado podes colá-lo ou carregá-lo de um ficheiro (`.pdf`, `.docx`, `.txt`, `.xlsx`).
2. No separador **Trabalhos** carregas os ficheiros de cada aluno (`.html`, `.css`, `.py`, `.xlsx`, `.txt`, `.pdf`, `.docx`).
3. Se quiseres, escreves as tuas observações sobre o trabalho. A IA segue-as na nota e no feedback.
4. **Corrigir** corre as verificações automáticas e, se quiseres, pede à IA uma nota por critério e feedback.
5. Revês tudo, alteras o que for preciso e carregas em **Guardar revisão**.
6. Exportas as notas para CSV (abre no Excel) e o feedback em HTML, um ficheiro por aluno, pronto a imprimir em PDF.

| Tipo | Verificações automáticas |
|---|---|
| HTML | DOCTYPE, `lang`, `<title>`, tags por fechar, `<img>` sem `alt`, tags semânticas, tags obsoletas, `style` inline |
| CSS | Chavetas, propriedades mal escritas (ex: `colour`), seletores repetidos, regras vazias, `!important`, `@media` |
| Python | Sintaxe e testes de entrada/saída com limite de 5 segundos |
| Excel | Número de fórmulas, funções usadas, referências absolutas, valores escritos à mão em linhas ou colunas de totais e médias, células com erro (`#DIV/0!`), gráficos, formatação condicional |
| Texto / PDF | Só a IA, com base na rubrica |

O nome do aluno é trocado por um código (A01, A02...) antes de qualquer envio para a IA e só volta a aparecer no teu computador.

## Instalar e correr

Precisas do Python 3.10 ou mais recente.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m corretor
```

## Chave da API

Na barra de cima, **Chave da API**, cola a chave que começa por `sk-ant-`. Fica guardada só neste computador. Também podes definir a variável de ambiente `ANTHROPIC_API_KEY`.

Sem chave, desliga a opção **Usar IA** e a app faz só as verificações automáticas.

## Testes

```bash
pip install pytest
python -m pytest
```

## Limites conhecidos

- O código Python dos alunos corre no teu computador com um limite de tempo, mas sem isolamento total. Abre só trabalhos dos teus alunos.
- Dos `.docx` só se lê o texto. Imagens e formatação ficam de fora.
- Ficheiros `.xls` antigos não são lidos. Guarda-os como `.xlsx`.
- No Excel, a app lê os valores que o Excel calculou da última vez que o ficheiro foi gravado. Um ficheiro criado fora do Excel pode não ter esses valores.
- Scratch e criação de apresentações ficam para as próximas fases.
