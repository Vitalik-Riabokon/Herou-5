# download_tab.py

import os
import requests
import zipfile
import shutil
import tempfile
from time import time

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QProgressBar, QTextEdit, QComboBox, QMessageBox
)

# Mapping file names to subfolders for install
INSTALL_MAP = {
    "Universe_mod": {
        "bin":  ["H5_Universe.exe"],
        "data": ["Universe_mod.pak"]
    },
    "H5AI_31": {
        "bin":  ["H5_AIadv_31j.exe", "H5_AIProcess_31j.exe"],
        "data": ["EE_options.pak", "EE_options_text.pak"]
    }
}

class DownloadWorker(QThread):
    progressChanged = Signal(int)
    statusMessage = Signal(str)
    finishedSignal = Signal(str)

    def __init__(self, url, out_path):
        super().__init__()
        self.url = url
        self.out_path = out_path

    def run(self):
        start = time()
        self.statusMessage.emit(f"Downloading → {self.url}")
        resp = requests.get(self.url, stream=True)
        if resp.status_code != 200:
            self.finishedSignal.emit(f"HTTP {resp.status_code}")
            return
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(self.out_path, "wb") as f:
            for chunk in resp.iter_content(32768):
                if not chunk:
                    continue
                f.write(chunk)
                done += len(chunk)
                if total:
                    self.progressChanged.emit(int(done * 100 / total))
        elapsed = time() - start
        mb = done / 1024 / 1024
        self.finishedSignal.emit(f"Downloaded {mb:.2f}MB in {elapsed:.1f}s")

class DownloadTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())

        # Save directory
        save_row = QHBoxLayout()
        save_row.addWidget(QLabel("Save ZIP to:"))
        self.edtSave = QLineEdit(os.path.expanduser("~"))
        save_row.addWidget(self.edtSave)
        btn_save = QPushButton("Browse")
        btn_save.clicked.connect(self.chooseSaveDir)
        save_row.addWidget(btn_save)
        self.layout().addLayout(save_row)

        # Target file selector
        self.comboTargets = QComboBox()
        self.files = {
            "Universe_mod": "https://drive.google.com/uc?export=download&id=1Tu6QMzAxc05D4d5qYOhLoqO4YEtdwom_",
            "H5AI_31": "https://drive.google.com/uc?export=download&id=1F2s-Ebm80JBj7OOsce3E-cqLJGyzpu2d",
            "Tribes of the East": "https://drive.google.com/uc?export=download&id=1UMXa_c6k5AGReDUNXDh3p5toxHsWnizG",
            "CheatEngine": "https://drive.google.com/uc?export=download&id=1b-stAqvS8NoqEf4wCD3EMKaYiJzLGfzm"
        }
        self.comboTargets.addItems(self.files.keys())
        self.layout().addWidget(self.comboTargets)

        # Download controls
        self.btnDownload = QPushButton("Download")
        self.btnDownload.clicked.connect(self.onDownload)
        self.layout().addWidget(self.btnDownload)
        self.prg = QProgressBar()
        self.layout().addWidget(self.prg)
        self.txtLog = QTextEdit(readOnly=True)
        self.layout().addWidget(self.txtLog, stretch=1)

        # Install controls: choose hero root
        install_row = QHBoxLayout()
        install_row.addWidget(QLabel("Heroes V root folder:"))
        self.edtHeroRoot = QLineEdit()
        install_row.addWidget(self.edtHeroRoot)
        btn_hero = QPushButton("Browse")
        btn_hero.clicked.connect(lambda: self.chooseFolder(self.edtHeroRoot))
        install_row.addWidget(btn_hero)
        self.layout().addLayout(install_row)

        self.comboInstall = QComboBox()
        self.comboInstall.addItems(INSTALL_MAP.keys())
        self.layout().addWidget(self.comboInstall)
        btnInstall = QPushButton("Install ZIP")
        btnInstall.clicked.connect(self.onInstall)
        self.layout().addWidget(btnInstall)

        self.worker = None

    def chooseSaveDir(self):
        d = QFileDialog.getExistingDirectory(self, "Choose folder for ZIP")
        if d:
            self.edtSave.setText(d)

    def chooseFolder(self, edt):
        d = QFileDialog.getExistingDirectory(self, "Choose Heroes V root folder")
        if d:
            edt.setText(d)

    def onDownload(self):
        name = self.comboTargets.currentText()
        url = self.files[name]
        save_dir = self.edtSave.text().strip()
        os.makedirs(save_dir, exist_ok=True)
        out = os.path.join(save_dir, f"{name}.zip")
        self.txtLog.append(f"Downloading {name} → {out}")
        self.btnDownload.setEnabled(False)
        self.worker = DownloadWorker(url, out)
        self.worker.progressChanged.connect(self.prg.setValue)
        self.worker.statusMessage.connect(self.txtLog.append)
        self.worker.finishedSignal.connect(lambda msg: (self.txtLog.append(msg), self.btnDownload.setEnabled(True)))
        self.worker.start()

    def onInstall(self):
        choice = self.comboInstall.currentText()
        save_dir = self.edtSave.text().strip()
        zip_path = os.path.join(save_dir, f"{choice}.zip")
        if not os.path.isfile(zip_path):
            self.txtLog.append(f"❌ ZIP not found: {zip_path}")
            return

        hero_root = self.edtHeroRoot.text().strip()
        if not hero_root or not os.path.isdir(hero_root):
            self.txtLog.append("❌ Invalid Heroes V root folder")
            return

        mapping = INSTALL_MAP.get(choice, {})
        self.txtLog.append(f"Installing '{choice}' into {hero_root}")
        with zipfile.ZipFile(zip_path, "r") as archive:
            for subfolder, filenames in mapping.items():
                dest_dir = os.path.join(hero_root, subfolder)
                os.makedirs(dest_dir, exist_ok=True)
                for member in archive.namelist():
                    if os.path.basename(member).lower() in [f.lower() for f in filenames]:
                        tmp = tempfile.mkdtemp()
                        archive.extract(member, tmp)
                        shutil.move(os.path.join(tmp, member), dest_dir)
                        shutil.rmtree(tmp)
                        self.txtLog.append(f"✔ {os.path.basename(member)} → {dest_dir}")
        self.txtLog.append(f"✅ Installation of '{choice}' completed")
