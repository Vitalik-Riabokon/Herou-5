# download_tab.py
import os
import subprocess
import requests
import zipfile
import shutil
import tempfile
from time import time
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QProgressBar, QTextEdit, QComboBox
)

# Установка файлів: де копіювати всередині кореня гри
INSTALL_MAP = {
    "Universe_mod": {"bin": ["H5_Universe.exe"], "data": ["Universe_mod.pak"]},
    "H5AI_31":    {"bin": ["H5_AIadv_31j.exe", "H5_AIProcess_31j.exe"], "data": ["EE_options.pak", "EE_options_text.pak"]},
    # Maps — всі файли у підпапку Maps
    "Maps":       {"Maps": ["*"]}
}

# Джерела завантаження
DOWNLOAD_SOURCES = {
    "Universe_mod": {"type": "git", "repo": "https://github.com/Vitalik-Riabokon/Herou-5.git", "file": "Universe_mod 1.3.zip"},
    "H5AI_31":     {"type": "gdrive", "id": "1F2s-Ebm80JBj7OOsce3E-cqLJGyzpu2d"},
    "Tribes of the East": {"type": "gdrive", "id": "1UMXa_c6k5AGReDUNXDh3p5toxHsWnizG"},
    "CheatEngine": {"type": "gdrive", "id": "1b-stAqvS8NoqEf4wCD3EMKaYiJzLGfzm"},
    "Maps":        {"type": "gdrive", "id": "1SaXQI64JkTp_6_gqqc0Lk95ZnJODuy0h"}
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
        resp = requests.get(self.url, stream=True)
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(self.out_path, 'wb') as f:
            for chunk in resp.iter_content(32768):
                f.write(chunk); done += len(chunk)
                if total: self.progressChanged.emit(int(done*100/total))
        self.finishedSignal.emit(f"Downloaded {done/1024/1024:.2f} MB")

class DownloadTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.edtSave = QLineEdit(os.path.expanduser('~'))
        btnSave = QPushButton('Browse'); btnSave.clicked.connect(self.chooseSaveDir)
        self.layout().addLayout(self._row('Save ZIP to:', self.edtSave, btnSave))

        self.comboTargets = QComboBox(); self.comboTargets.addItems(DOWNLOAD_SOURCES.keys())
        self.layout().addWidget(self.comboTargets)
        self.btnDownload = QPushButton('Download'); self.btnDownload.clicked.connect(self.onDownload)
        self.layout().addWidget(self.btnDownload)
        self.prg = QProgressBar(); self.layout().addWidget(self.prg)
        self.txtLog = QTextEdit(readOnly=True); self.layout().addWidget(self.txtLog, stretch=1)

        self.edtHeroRoot = QLineEdit(); btnHero = QPushButton('Browse'); btnHero.clicked.connect(lambda: self.chooseFolder(self.edtHeroRoot))
        self.layout().addLayout(self._row('Heroes V root folder:', self.edtHeroRoot, btnHero))

        self.comboInstall = QComboBox(); self.comboInstall.addItems(INSTALL_MAP.keys())
        btnInstall = QPushButton('Install ZIP'); btnInstall.clicked.connect(self.onInstall)
        self.layout().addWidget(self.comboInstall); self.layout().addWidget(btnInstall)
        self.worker = None

    def _row(self, label, widget, btn):
        row = QHBoxLayout(); row.addWidget(QLabel(label)); row.addWidget(widget); row.addWidget(btn); return row

    def chooseSaveDir(self): path = QFileDialog.getExistingDirectory(self, 'Choose folder'); self.edtSave.setText(path)
    def chooseFolder(self, edt): d = QFileDialog.getExistingDirectory(self, 'Choose Heroes V root folder'); edt.setText(d)

    def onDownload(self):
        name = self.comboTargets.currentText()
        info = DOWNLOAD_SOURCES[name]
        out = os.path.join(self.edtSave.text(), f"{name}.zip")

        self.txtLog.append(f"Downloading {name} → {out}")
        os.makedirs(os.path.dirname(out), exist_ok=True)

        if info["type"] == "git":
            repo = "Vitalik-Riabokon/Herou-5"
            filepath = "Universe_mod 1.3.zip"
            try:
                self.github_download(repo, filepath, out)
                self.txtLog.append("✅ GitHub download complete")
            except Exception as e:
                self.txtLog.append(f"❌ GitHub download failed: {e}")
        else:
            url = f"https://drive.google.com/uc?export=download&id={info['id']}"
            self.worker = DownloadWorker(url, out)
            self.worker.progressChanged.connect(self.prg.setValue)
            self.worker.statusMessage.connect(self.txtLog.append)
            self.worker.finishedSignal.connect(lambda msg: (self.txtLog.append(msg), self.btnDownload.setEnabled(True)))
            self.worker.start()
    @staticmethod
    def github_download(repo: str, filepath: str, dest: str):
        """
        repo — у форматі 'owner/repo'
        filepath — шлях до файлу всередині репо
        dest — куди зберегти .zip
        """
        import dotenv
        dotenv.load_dotenv()

        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("Set GITHUB_TOKEN env var")

        api = f"https://api.github.com/repos/{repo}/contents/{filepath}"
        headers = {"Authorization": f"token {token}"}
        r = requests.get(api, headers=headers)
        if r.status_code != 200:
            raise RuntimeError(f"GitHub API {r.status_code}: {r.text}")

        download_url = r.json().get("download_url")
        if not download_url:
            raise RuntimeError("No download_url in GitHub response")

        # Скачуємо файл
        with requests.get(download_url, headers=headers, stream=True) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(32768):
                    if chunk:
                        f.write(chunk)

    def onInstall(self):
        choice = self.comboInstall.currentText(); save_dir = self.edtSave.text().strip()
        zip_path = os.path.join(save_dir, f"{choice}.zip")
        hero_root = self.edtHeroRoot.text().strip()
        if not os.path.isfile(zip_path) or not os.path.isdir(hero_root): return self.txtLog.append('Invalid path')
        mapping = INSTALL_MAP[choice]
        with zipfile.ZipFile(zip_path) as archive:
            for subfolder, files in mapping.items():
                dest = os.path.join(hero_root, subfolder)
                os.makedirs(dest, exist_ok=True)
                for member in archive.namelist():
                    if files==['*'] or os.path.basename(member).lower() in [f.lower() for f in files]:
                        tmp = tempfile.mkdtemp(); archive.extract(member, tmp)
                        shutil.move(os.path.join(tmp, member), dest); shutil.rmtree(tmp)
                        self.txtLog.append(f"Installed {member} → {dest}")
        self.txtLog.append(f"Installation of {choice} complete")
