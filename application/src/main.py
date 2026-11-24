import sys

from PySide6.QtWidgets import QApplication

from application.src.gui import MainWindow


def main():
    app = QApplication(sys.argv)

    app.setApplicationName(
        "CNC Intelligent Control System"
    )

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()