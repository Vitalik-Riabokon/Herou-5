import os
from PySide6.QtCore import QUrl, QStandardPaths
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QComboBox, QFileDialog, QMessageBox, QInputDialog
)
from PySide6.QtWebEngineWidgets import QWebEngineView

class WheelTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.save_base = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.wheelView = QWebEngineView()
        self.wheelView.load(QUrl("https://h5lobby.com/wheel"))
        layout.addWidget(self.wheelView, stretch=1)

        ctrls = QHBoxLayout()
        layout.addLayout(ctrls)

        self.btnChooseBase = QPushButton("Вибрати базову теку")
        ctrls.addWidget(self.btnChooseBase)
        self.btnChooseBase.clicked.connect(self.onChooseBase)

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

    def onChooseBase(self):
        directory = QFileDialog.getExistingDirectory(self, "Оберіть базову теку для збереження", self.save_base)
        if directory:
            self.save_base = directory
            self.updateFolderList()

    def updateFolderList(self):
        os.makedirs(self.save_base, exist_ok=True)
        dirs = [d for d in os.listdir(self.save_base) if os.path.isdir(os.path.join(self.save_base, d))]
        self.cmbFolder.clear()
        self.cmbFolder.addItems(dirs)

    def onCreateFolder(self):
        name, ok = QInputDialog.getText(self, "Ім'я папки", "Введіть назву:")
        if ok and name.strip():
            new_dir = os.path.join(self.save_base, name.strip())
            if os.path.exists(new_dir):
                QMessageBox.warning(self, "Помилка", "Така папка вже існує.")
            else:
                os.makedirs(new_dir, exist_ok=True)
                self.updateFolderList()

    def onScreenshot(self):
        fname = self.edtFileName.text().strip()
        if not fname:
            QMessageBox.warning(self, "Помилка", "Вкажіть ім'я файлу")
            return

        folder = self.cmbFolder.currentText()
        if not folder:
            QMessageBox.warning(self, "Помилка", "Оберіть папку або створіть нову")
            return

        save_dir = os.path.join(self.save_base, folder)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"{fname}.png")

        pixmap = self.wheelView.grab()
        if pixmap.save(save_path):
            QMessageBox.information(self, "OK", f"Збережено: {save_path}")
        else:
            QMessageBox.critical(self, "Помилка", "Не вдалося зберегти скріншот")
