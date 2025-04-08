# download_tab.py (UPDATED)

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
import dotenv
dotenv.load_dotenv()

INSTALL_MAP = {
    "Universe_mod": {"bin": ["H5_Universe.exe"], "data": ["Universe_mod.pak"]},
    "H5AI_31":    {"bin": ["H5_AIadv_31j.exe", "H5_AIProcess_31j.exe"], "data": ["EE_options.pak", "EE_options_text.pak"]},
    "Maps":       {"Maps": ["*"]}
}

DOWNLOAD_SOURCES = {
    "Universe_mod": {"type": "git", "repo": "Vitalik-Riabokon/Herou-5", "file": "Universe_mod 1.3.zip"},
    "H5AI_31":      {"type": "gdrive", "id": "1F2s-Ebm80JBj7OOsce3E-cqLJGyzpu2d"},
    "Tribes of the East": {"type": "gdrive", "id": "1UMXa_c6k5AGReDUNXDh3p5toxHsWnizG"},
    "CheatEngine":  {"type": "gdrive", "id": "1b-stAqvS8NoqEf4wCD3EMKaYiJzLGfzm"},
    "Maps":         {"type": "gdrive", "id": "1SaXQI64JkTp_6_gqqc0Lk95ZnJODuy0h"}
}


def github_download(repo: str, filepath: str, dest: str):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Set GITHUB_TOKEN environment variable")
    api_url = f"https://api.github.com/repos/{repo}/contents/{filepath}"
    headers = {"Authorization": f"token {token}"}
    r = requests.get(api_url, headers=headers)
    r.raise_for_status()
    download_url = r.json().get("download_url")
    if not download_url:
        raise RuntimeError("No download_url in API response")
    resp = requests.get(download_url, stream=True)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(32768):
            if chunk:
                f.write(chunk)

class DownloadWorker(QThread):
    progressChanged = Signal(int)
    statusMessage   = Signal(str)
    finishedSignal  = Signal(str)
    def __init__(self, url, out_path):
        super().__init__()
        self.url = url
        self.out_path = out_path
    def run(self):
        start = time()
        self.statusMessage.emit(f"⚡ Завантаження → {self.url}")
        resp = requests.get(self.url, stream=True)
        if resp.status_code != 200:
            self.finishedSignal.emit(f"❌ HTTP {resp.status_code}")
            return
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(self.out_path, "wb") as f:
            for chunk in resp.iter_content(32768):
                if not chunk:
                    continue
                f.write(chunk); done += len(chunk)
                if total:
                    self.progressChanged.emit(int(done * 100 / total))
        elapsed = time() - start
        self.finishedSignal.emit(f"✅ Завантажено {done/1024/1024:.2f} MB за {elapsed:.1f}s")

class DownloadTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        # Save ZIP folder
        save_row = QHBoxLayout()
        save_row.addWidget(QLabel("📁 Папка для ZIP:"))
        self.edtSave = QLineEdit(os.path.expanduser("~"))
        save_row.addWidget(self.edtSave)
        btn_save = QPushButton("Огляд")
        btn_save.clicked.connect(lambda: self.chooseFolder(self.edtSave))
        save_row.addWidget(btn_save)
        self.layout().addLayout(save_row)
        # Targets
        self.comboTargets = QComboBox(); self.comboTargets.addItems(DOWNLOAD_SOURCES.keys())
        self.layout().addWidget(self.comboTargets)
        self.btnDownload = QPushButton("🔄 Завантажити"); self.btnDownload.clicked.connect(self.onDownload)
        self.layout().addWidget(self.btnDownload)
        self.prg = QProgressBar(); self.layout().addWidget(self.prg)
        self.txtLog = QTextEdit(readOnly=True); self.layout().addWidget(self.txtLog, stretch=1)
        # Hero root
        hero_row = QHBoxLayout(); hero_row.addWidget(QLabel("🗺 Коренева папка гри:"))
        self.edtHeroRoot = QLineEdit(); hero_row.addWidget(self.edtHeroRoot)
        btn_hero = QPushButton("Огляд"); btn_hero.clicked.connect(lambda: self.chooseFolder(self.edtHeroRoot))
        hero_row.addWidget(btn_hero)
        self.layout().addLayout(hero_row)
        # Install
        self.comboInstall = QComboBox(); self.comboInstall.addItems(INSTALL_MAP.keys())
        self.layout().addWidget(self.comboInstall)
        btnInstall = QPushButton("✅ Встановити ZIP"); btnInstall.clicked.connect(self.onInstall)
        self.layout().addWidget(btnInstall)
        self.worker = None

    def chooseFolder(self, edt):
        d = QFileDialog.getExistingDirectory(self, "Оберіть теку")
        if d: edt.setText(d)

    def onDownload(self):
        name = self.comboTargets.currentText(); info = DOWNLOAD_SOURCES[name]
        save_dir = self.edtSave.text().strip(); os.makedirs(save_dir, exist_ok=True)
        dest = os.path.join(save_dir, f"{name}.zip")
        self.txtLog.append(f"🔄 Завантаження {name} → {dest}")
        self.btnDownload.setEnabled(False); self.prg.setValue(0)
        url = f"https://drive.google.com/uc?export=download&id={info['id']}"
        self.worker = DownloadWorker(url, dest)
        self.worker.progressChanged.connect(self.prg.setValue)
        self.worker.statusMessage.connect(self.txtLog.append)
        self.worker.finishedSignal.connect(lambda m: (self.txtLog.append(m), self.btnDownload.setEnabled(True)))
        self.worker.start()

    def onInstall(self):
        choice = self.comboInstall.currentText()
        save_dir = self.edtSave.text().strip()
        zip_path = os.path.join(save_dir, f"{choice}.zip")
        hero_root = self.edtHeroRoot.text().strip()
        if not os.path.isfile(zip_path): return self.txtLog.append(f"❌ ZIP not found: {zip_path}")
        if not os.path.isdir(hero_root): return self.txtLog.append("❌ Invalid root folder")
        mapping = INSTALL_MAP.get(choice, {})
        self.txtLog.append(f"⚙️ Installing '{choice}' into {hero_root}")
        with zipfile.ZipFile(zip_path) as archive:
            for sub, files in mapping.items():
                dest = os.path.join(hero_root, sub); os.makedirs(dest, exist_ok=True)
                for member in archive.namelist():
                    base = os.path.basename(member)
                    if files == ["*"] or base.lower() in [f.lower() for f in files]:
                        tmp = tempfile.mkdtemp(); archive.extract(member, tmp)
                        dest_file = os.path.join(dest, base)
                        if os.path.exists(dest_file):
                            reply = QMessageBox.question(self, "Overwrite?", f"{dest_file} exists. Overwrite?", QMessageBox.Yes|QMessageBox.No)
                            if reply == QMessageBox.No:
                                shutil.rmtree(tmp); continue
                            os.remove(dest_file)
                        shutil.move(os.path.join(tmp, member), dest); shutil.rmtree(tmp)
                        self.txtLog.append(f"✔ {base} → {dest}")
        self.txtLog.append(f"✅ '{choice}' installed")
