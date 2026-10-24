import sys

from PySide6.QtWidgets import QApplication

from corretor.ui.janela import Janela


def main() -> int:
    app = QApplication(sys.argv)
    janela = Janela()
    janela.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
