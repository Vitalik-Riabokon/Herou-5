# main.py
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QMenuBar, QMenu

# Підключаємо наші вкладки:
from tabs.universe_editor_tab import UniverseEditorTab
from tabs.wheel_tab import WheelTab
from tabs.download_tab import DownloadTab
from PySide6.QtCore import Signal
import keyboard


class MainWindow(QMainWindow):
    hotkeySignal = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heroes V Extended")

        # Тулбар вкладок
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # 1) Universe Editor
        self.universe_tab = UniverseEditorTab(parent=self)
        self.tabs.addTab(self.universe_tab, "Universe Editor")

        # 2) Колесо вмінь
        self.wheel_tab = WheelTab(parent=self)
        self.tabs.addTab(self.wheel_tab, "Колесо вмінь")

        # 3) Download
        self.download_tab = DownloadTab(parent=self)
        self.tabs.addTab(self.download_tab, "Download")

        # Меню
        menubar = QMenuBar()
        self.setMenuBar(menubar)
        menuFile = QMenu("Файл", self)
        menubar.addMenu(menuFile)
        actExit = menuFile.addAction("Вихід")
        actExit.triggered.connect(self.close)

        # Додайте меню “Про програму” за потреби
        menuHelp = QMenu("Довідка", self)
        menubar.addMenu(menuHelp)
        aboutAct = menuHelp.addAction("Про програму")
        aboutAct.triggered.connect(self.onAbout)

        self.tabs.currentChanged.connect(self.onTabChanged)
        self.applyNeonStyle()
        self.resize(1000, 700)

        self.hotkeySignal.connect(self._show_wheel)

        import keyboard
        keyboard.add_hotkey('Tab', self.hotkeySignal.emit)

    def _show_wheel(self):
        from ctypes import windll

        hwnd = int(self.winId())
        # Якщо зараз мінімізовано → відновлюємо і показуємо колесо
        if self.isMinimized() or not self.isVisible():      
            self.tabs.blockSignals(True)            
            self.tabs.setCurrentIndex(1 )
            self.tabs.blockSignals(False)

            windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            windll.user32.SetForegroundWindow(hwnd)
            self.showMaximized()
        else:
            # Інакше — мінімізуємо
            windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE

    def onTabChanged(self, index):
        # Якщо вкладка «Колесо вмінь» (індекс 1), розгортаємо на весь екран
        if index == 1:
            self.showMaximized()
        else:
            self.showNormal()
            self.resize(1000, 700)

    def onAbout(self):
        """Просте вікно з інформацією."""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Про програму",
                                "Heroes V Extended\n\n"
                                " - Universe Editor\n"
                                " - Колесо вмінь\n"
                                " - Завантаження ZIP та ін.\n\n"
                                "Автор: ChatGPT Extended")

    def applyNeonStyle(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #242424;
                color: #A8FFC4;
                font-family: Segoe UI, Consolas;
                font-size: 10pt;
            }
            QLineEdit, QComboBox, QTextEdit {
                background-color: #2E2E2E;
                border: 1px solid #444;
                color: #C4FFE4;
            }
            QPushButton {
                background-color: #3A3A3A;
                border: 1px solid #5EECCB;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #4A4A4A;
            }
            QCheckBox {
                spacing: 6px;
            }
            QProgressBar {
                text-align: center;
                background-color: #2A2A2A;
                border: 1px solid #444;
            }
            QProgressBar::chunk {
                background-color: #00FFC8;
            }
            QMenuBar {
                background-color: #2A2A2A;
            }
            QMenuBar::item {
                background-color: #2A2A2A;
                color: #A8FFC4;
            }
            QMenuBar::item:selected {
                background-color: #3A3A3A;
            }
            QMenu {
                background-color: #2A2A2A;
                color: #A8FFC4;
            }
            QMenu::item:selected {
                background-color: #3A3A3A;
            }

            QTabBar::tab {
                background-color: #2E2E2E;
                color: #C4FFE4;
                border: 1px solid #5EECCB;
                padding: 5px 10px;
                margin: 2px;
            }
            QTabBar::tab:selected {
                background-color: #3A3A3A;
                border-color: #00FFC8;
            }
        """)


def main():
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
