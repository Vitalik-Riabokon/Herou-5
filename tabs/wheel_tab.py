

# wheel_tab.py
import os
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QComboBox, QFileDialog, QMessageBox
from PySide6.QtWebEngineWidgets import QWebEngineView


SAVE_BASE = r"C:\Programs\Games\Heroes of Might and Magic V\ТАКТИКИ"


class WheelTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        # WebView
        self.wheelView = QWebEngineView()
        self.wheelView.load(QUrl("https://h5lobby.com/wheel"))
        layout.addWidget(self.wheelView, stretch=1)

        # Controls row
        ctrls = QHBoxLayout()
        layout.addLayout(ctrls)

        self.btnScreenshot = QPushButton("Зробити скрін")
        ctrls.addWidget(self.btnScreenshot)
        self.btnScreenshot.clicked.connect(self.onScreenshot)

        self.edtFileName = QLineEdit()
        self.edtFileName.setPlaceholderText("Ім'я файлу (без розширення)")
        ctrls.addWidget(self.edtFileName)

        self.cmbFolder = QComboBox()
        ctrls.addWidget(self.cmbFolder)

        self.btnFolder = QPushButton("Створити папку")
        ctrls.addWidget(self.btnFolder)
        self.btnFolder.clicked.connect(self.onCreateFolder)

        self.updateFolderList()

    def updateFolderList(self):
        os.makedirs(SAVE_BASE, exist_ok=True)
        dirs = [d for d in os.listdir(SAVE_BASE)
                if os.path.isdir(os.path.join(SAVE_BASE, d))]
        self.cmbFolder.clear()
        self.cmbFolder.addItems(dirs)

    def onCreateFolder(self):
        # У прикладі: просто діалог для введення назви
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        name, ok = QInputDialog.getText(self, "Ім'я папки", "Введіть назву:")
        if not ok or not name.strip():
            return
        new_dir = os.path.join(SAVE_BASE, name.strip())
        if os.path.exists(new_dir):
            QMessageBox.warning(self, "Помилка", "Така папка вже існує.")
            return
        os.makedirs(new_dir, exist_ok=True)
        self.updateFolderList()

    def onScreenshot(self):
        fname = self.edtFileName.text().strip()
        if not fname:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Помилка", "Вкажіть ім'я файлу")
            return

        folder = self.cmbFolder.currentText()
        if not folder:
            QMessageBox.warning(self, "Помилка", "Оберіть папку або створіть нову")
            return

        save_dir = os.path.join(SAVE_BASE, folder)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"{fname}.png")

        pixmap = self.wheelView.grab()
        if pixmap.save(save_path):
            QMessageBox.information(self, "OK", f"Збережено: {save_path}")
        else:
            QMessageBox.critical(self, "Помилка", "Не вдалося зберегти скріншот")
