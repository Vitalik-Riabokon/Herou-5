# tabs/download_tab.py
# -*- coding: utf-8 -*-

import os
import re

import gdown
import requests
import zipfile
import shutil
import tempfile
from time import time

from PySide6.QtCore import (QThread, Signal, QSettings, QTimer,
                            Qt, QEvent, QUrl)
from PySide6.QtGui import QDesktopServices, QRegion
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QProgressBar, QTextEdit, QComboBox, QMessageBox, QDialog,
    QPlainTextEdit, QGridLayout, QDialogButtonBox
)

import dotenv
dotenv.load_dotenv()

# ------------------------------------------------------
# 1) Мапа встановлення
# ------------------------------------------------------
INSTALL_MAP = {
    "Universe_mod": {
        "bin":  ["H5_Universe.exe"],
        "data": ["Universe_mod.pak"]
    },
    "H5AI_31": {
        "bin":  ["H5_AIadv_31j.exe", "H5_AIProcess_31j.exe"],
        "data": ["EE_options.pak", "EE_options_text.pak"]
    },
    "Maps": {
        "Maps": ["*"]
    }
}

# ------------------------------------------------------
# 2) Джерела завантаження
# ------------------------------------------------------
DOWNLOAD_SOURCES = {
    "Universe_mod": {
        "type": "git",
        "repo": "Vitalik-Riabokon/Herou-5",
        "file": "Universe_mod 1.3.zip"
    },
    "H5AI_31": {
        "type": "gdrive",
        "id": "1F2s-Ebm80JBj7OOsce3E-cqLJGyzpu2d"
    },
    "Tribes of the East": {
        "type": "gdrive",
        "id": "1UMXa_c6k5AGReDUNXDh3p5toxHsWnizG"
    },
    "CheatEngine": {
        "type": "gdrive",
        "id": "1b-stAqvS8NoqEf4wCD3EMKaYiJzLGfzm"
    },
    "Maps": {
        "type": "gdrive",
        "id": "1SaXQI64JkTp_6_gqqc0Lk95ZnJODuy0h"
    }
}

# ------------------------------------------------------
# 3) Функція для GitHub (приватне/публічне репо)
# ------------------------------------------------------
def github_download(repo: str, filepath: str, dest: str):
    """Завантаження одного файлу з приватного (або публічного) репо GitHub через API."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Set GITHUB_TOKEN environment variable")

    url_api = f"https://api.github.com/repos/{repo}/contents/{filepath}"
    headers = {"Authorization": f"token {token}"}
    r = requests.get(url_api, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"GitHub API {r.status_code}: {r.text}")

    download_url = r.json().get("download_url")
    if not download_url:
        raise RuntimeError("No download_url in API response")

    resp = requests.get(download_url, headers=headers, stream=True)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(32768):
            if chunk:
                f.write(chunk)

# ------------------------------------------------------
# 4) Воркери завантаження (Git / GDrive / Прямий)
# ------------------------------------------------------
class DownloadWorker(QThread):
    """Універсальний потік для прямого URL (але не GDrive великих файлів)."""
    progressChanged = Signal(int)
    statusMessage   = Signal(str)
    finishedSignal  = Signal(str)

    def __init__(self, url: str, out_path: str):
        super().__init__()
        self.url = url
        self.out_path = out_path

    def run(self):
        t0 = time()
        self.statusMessage.emit(f"⚡ Завантаження: {self.url}")
        r = requests.get(self.url, stream=True)
        if r.status_code != 200:
            self.finishedSignal.emit(f"❌ HTTP {r.status_code}")
            return

        total = int(r.headers.get("Content-Length", 0))
        done = 0
        with open(self.out_path, "wb") as f:
            for chunk in r.iter_content(32768):
                if not chunk:
                    continue
                f.write(chunk)
                done += len(chunk)
                if total:
                    prog = int(done*100/total)
                    self.progressChanged.emit(prog)

        dt = time() - t0
        mb = done/1024/1024
        self.finishedSignal.emit(f"✅ Завантажено {mb:.2f}MB за {dt:.1f}с")


class GitDownloadWorker(QThread):
    """Воркeр для скачування файлу з GitHub (приватного/публічного репо)."""
    progressChanged = Signal(int)
    statusMessage   = Signal(str)
    finishedSignal  = Signal(str)

    def __init__(self, repo: str, filepath: str, out_path: str):
        super().__init__()
        self.repo = repo
        self.filepath = filepath
        self.out_path = out_path

    def run(self):
        try:
            self.statusMessage.emit(f"⚡ GitHub: {self.repo}/{self.filepath}")
            github_download(self.repo, self.filepath, self.out_path)
            self.finishedSignal.emit("✅ GitHub файл отримано")
        except Exception as ex:
            self.finishedSignal.emit(f"❌ GitHub download failed: {ex}")


import subprocess
import re

class GDriveDownloadWorker(QThread):
    """Воркeр для скачування Google Drive через gdown з відображенням прогресу."""
    progressChanged = Signal(int)
    statusMessage  = Signal(str)
    finishedSignal = Signal(str)

    def __init__(self, file_id: str, out_path: str):
        super().__init__()
        self.file_id = file_id
        self.out_path = out_path

    def run(self):
        url = f"https://drive.google.com/uc?id={self.file_id}"
        self.statusMessage.emit("⚡ Запуск gdown…")
        # Формуємо команду
        cmd = ["gdown", url, "-O", self.out_path]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
        except FileNotFoundError:
            return self.finishedSignal.emit("❌ Не знайдено gdown. Встановіть його через pip install gdown")

        pattern = re.compile(r"\s*(\d+)%\s+([\d\.]+[KMG]?B/s)")

        # Читаємо stdout рядок за рядком
        for line in proc.stdout:
            line = line.strip()
            # Емімо будь‑які статусні повідомлення
            self.statusMessage.emit(line)
            # Шукаємо прогрес
            m = pattern.search(line)
            if m:
                pct = int(m.group(1))
                speed = m.group(2)
                self.progressChanged.emit(pct)
                # Додатково показуємо швидкість
                self.statusMessage.emit(f"🚀 {speed}")
        proc.wait()

        if proc.returncode == 0:
            self.progressChanged.emit(100)
            self.finishedSignal.emit(f"✅ Завантажено {self.out_path}")
        else:
            self.finishedSignal.emit(f"❌ gdown завершився з кодом {proc.returncode}")



# ------------------------------------------------------
# 5) Клас вкладки DownloadTab, інтегрованої в main.py
# ------------------------------------------------------
class DownloadTab(QWidget):
    """
    Вкладка «Download» для головного вікна:
    - Завантаження обраного ZIP (Google Drive, GitHub) в обрану теку
    - Вибір кореня гри та встановлення (за INSTALL_MAP)
    - Кіберпанк-стиль, підказки, лог, збереження шляхів
    - Кнопка «Відкрити папку з ZIP» + кнопка «Показати повний лог».
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        # QSettings для збереження/відновлення шляхів
        self.settings = QSettings("download_tab_settings.ini", QSettings.IniFormat)

        # ----------- UI -----------
        self.initUi()
        self.applyCyberpunkStyle()
        self.initHoverHighlight()

        # Відновлюємо збережені теку ZIP і теку гри
        self.loadPathsFromSettings()

    # -----------------------
    # Створення UI
    # -----------------------
    def initUi(self):
        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)

        # 1) Комбобокс із пунктами (DOWNLOAD_SOURCES)
        self.comboTargets = QComboBox()
        self.comboTargets.addItems(DOWNLOAD_SOURCES.keys())
        self.comboTargets.setToolTip("Оберіть, що завантажити (Google Drive чи GitHub)")

        # 2) Тека для збереження ZIP
        row_save = QHBoxLayout()
        lbl_save = QLabel("Тека для збереження ZIP:")
        self.edtSave = QLineEdit()
        self.edtSave.setToolTip("Оберіть теку, куди зберігатиметься архів .zip")
        btn_browse_save = QPushButton("Огляд")
        btn_browse_save.setToolTip("Відкрити вікно вибору теки для збереження.")
        btn_browse_save.clicked.connect(self.chooseSaveDir)
        row_save.addWidget(lbl_save)
        row_save.addWidget(self.edtSave)
        row_save.addWidget(btn_browse_save)

        # 3) Кнопка «Завантажити»
        self.btnDownload = QPushButton("🔄 Завантажити")
        self.btnDownload.setToolTip("Почати завантаження обраного ZIP")
        self.btnDownload.clicked.connect(self.onDownload)

        # 4) Прогресбар + текстовий лог
        self.prg = QProgressBar()
        self.txtLog = QTextEdit()
        self.txtLog.setReadOnly(True)

        # 5) Тека гри + кнопка
        row_hero = QHBoxLayout()
        lbl_hero = QLabel("🗺 Папка гри:")
        self.edtHeroRoot = QLineEdit()
        self.edtHeroRoot.setToolTip("Вкажіть кореневу папку Heroes V (bin, data, Maps).")
        btn_hero = QPushButton("Огляд")
        btn_hero.setToolTip("Оберіть кореневу папку гри.")
        btn_hero.clicked.connect(lambda: self.chooseFolder(self.edtHeroRoot))
        row_hero.addWidget(lbl_hero)
        row_hero.addWidget(self.edtHeroRoot)
        row_hero.addWidget(btn_hero)

        # 6) Комбобокс для вибору ZIP (Universe_mod / H5AI_31 / Maps), щоб встановити
        self.comboInstall = QComboBox()
        self.comboInstall.addItems(INSTALL_MAP.keys())
        self.comboInstall.setToolTip("Виберіть архів для встановлення (повинні вже завантажити відповідний ZIP).")

        # 7) Кнопка «Install ZIP»
        btnInstall = QPushButton("✅ Встановити ZIP")
        btnInstall.setToolTip("Розпакувати вибраний ZIP у кореневу папку гри.")
        btnInstall.clicked.connect(self.onInstall)

        # 8) Кнопка «Відкрити папку з ZIP»
        self.btnOpenFolder = QPushButton("📂 Відкрити папку з ZIP")
        self.btnOpenFolder.setToolTip("Відкрити теку, де лежить останній завантажений ZIP.")
        self.btnOpenFolder.setVisible(False)  # стане видимою після успішного завантаження
        self.btnOpenFolder.clicked.connect(self.openZipFolder)

        # 9) Кнопка «Показати повний лог»
        self.btnShowFullLog = QPushButton("📝 Повний лог")
        self.btnShowFullLog.setToolTip("Відкрити окреме вікно із усіма повідомленнями логу.")
        self.btnShowFullLog.clicked.connect(self.showFullLogDialog)

        # Розміщення
        main_layout.addWidget(self.comboTargets)
        main_layout.addLayout(row_save)
        main_layout.addWidget(self.btnDownload)
        main_layout.addWidget(self.prg)
        main_layout.addWidget(self.txtLog, stretch=1)
        main_layout.addLayout(row_hero)
        main_layout.addWidget(self.comboInstall)
        main_layout.addWidget(btnInstall)

        row_extras = QHBoxLayout()
        row_extras.addWidget(self.btnOpenFolder)
        row_extras.addWidget(self.btnShowFullLog)
        row_extras.addStretch(1)
        main_layout.addLayout(row_extras)

    # -----------------------
    # Стиль кіберпанк
    # -----------------------
    def applyCyberpunkStyle(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #242424;
                color: #A8FFC4;
                font-family: Consolas, Segoe UI, Arial;
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
                padding: 5px 10px;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: #4A4A4A;
            }
            QProgressBar {
                text-align: center;
                background-color: #2A2A2A;
                border: 1px solid #444;
            }
            QProgressBar::chunk {
                background-color: #00FFC8;
            }
            QToolTip {
                background-color: #2A2A2A;
                color: #A8FFC4;
                border: 1px solid #00FFC8;
            }
        """)

    # -----------------------
    # Ховер-хайлайт
    # -----------------------
    def initHoverHighlight(self):
        """Якщо 5с тримати курсор на одному елементі — затемнюємо інтерфейс, підсвічуємо цей елемент."""
        self.overlay = QWidget(self)
        self.overlay.hide()
        self.overlay.setStyleSheet("background-color: rgba(0,0,0,150);")
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.hoverTimer = QTimer(self)
        self.hoverTimer.setSingleShot(True)
        self.hoverTimer.timeout.connect(self.onHoverTimeout)
        self.hoverTarget = None

        # Встановимо фільтр подій на всі суттєві елементи
        for w in self.findChildren(QWidget):
            if w is not self.overlay and w is not self:
                w.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            self.hoverTarget = obj
            self.hoverTimer.start(5000)
        elif event.type() == QEvent.Leave:
            self.hoverTimer.stop()
            self.overlay.hide()
            self.hoverTarget = None
        return super().eventFilter(obj, event)

    def onHoverTimeout(self):
        if not self.hoverTarget:
            return
        # Створюємо дірку у накладці, де елемент
        rect = self.hoverTarget.geometry()
        # Переходимо в координати DownloadTab
        topLeft = self.hoverTarget.mapTo(self, rect.topLeft())
        myRect = rect.translated(topLeft)
        region = QRegion(self.rect())
        region_hole = QRegion(myRect)
        final_mask = region.subtracted(region_hole)
        self.overlay.setGeometry(self.rect())
        self.overlay.setMask(final_mask)
        self.overlay.raise_()
        self.overlay.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.overlay.isVisible():
            # При зміні розміру оновлюємо положення overlay
            self.overlay.setGeometry(self.rect())

    # -----------------------
    # Збереження/відновлення шляхів
    # -----------------------
    def loadPathsFromSettings(self):
        save_dir = self.settings.value("save_dir", "")
        game_dir = self.settings.value("game_dir", "")
        if save_dir:
            self.edtSave.setText(save_dir)
        if game_dir:
            self.edtHeroRoot.setText(game_dir)

    def savePathsToSettings(self):
        self.settings.setValue("save_dir", self.edtSave.text())
        self.settings.setValue("game_dir", self.edtHeroRoot.text())

    # -----------------------
    # Допоміжні методи UI
    # -----------------------
    def chooseSaveDir(self):
        path = QFileDialog.getExistingDirectory(self, "Оберіть теку для збереження ZIP")
        if path:
            self.edtSave.setText(path)
            self.savePathsToSettings()

    def chooseFolder(self, edt: QLineEdit):
        d = QFileDialog.getExistingDirectory(self, "Оберіть кореневу папку Heroes V")
        if d:
            edt.setText(d)
            self.savePathsToSettings()

    # -----------------------
    # Завантаження ZIP
    # -----------------------
    def onDownload(self):
        """Користувач тисне «Завантажити»: визначити джерело, створити воркер."""
        self.txtLog.clear()
        self.prg.setValue(0)
        self.btnOpenFolder.setVisible(False)

        item_name = self.comboTargets.currentText()
        info = DOWNLOAD_SOURCES.get(item_name, {})
        if not info:
            self.log("❌ Нема джерела завантаження для: " + item_name)
            return

        save_dir = self.edtSave.text().strip()
        if not save_dir or not os.path.isdir(save_dir):
            self.log("❌ Некоректна текa для збереження ZIP.")
            return

        zip_path = os.path.join(save_dir, f"{item_name}.zip")
        self.log(f"🔄 Завантаження {item_name} → {zip_path}")
        src_type = info.get("type")

        # Вибір воркера за типом
        if src_type == "git":
            repo = info["repo"]
            file_in_repo = info["file"]
            self.worker = GitDownloadWorker(repo, file_in_repo, zip_path)
        elif src_type == "gdrive":
            file_id = info["id"]
            self.worker = GDriveDownloadWorker(file_id, zip_path)
        else:
            file_id = info.get("id")
            if file_id:
                url = f"https://drive.google.com/uc?export=download&id={file_id}"
                self.worker = DownloadWorker(url, zip_path)
            else:
                # fallback
                self.log("❌ Не змогли визначити тип джерела.")
                return

        # Підписуємося на сигнали воркера
        self.worker.progressChanged.connect(self.prg.setValue)
        self.worker.statusMessage.connect(self.txtLog.append)
        self.worker.finishedSignal.connect(self.onDownloadFinished)

        # Заблокувати кнопку поки йде завантаження
        self.btnDownload.setEnabled(False)
        self.prg.setValue(0)
        self.worker.start()

        # Зберегти теку
        self.savePathsToSettings()

    def onDownloadFinished(self, msg: str):
        """Обробка завершення завантаження."""
        self.txtLog.append(msg)
        self.btnDownload.setEnabled(True)
        self.prg.setValue(100)
        # Робимо кнопку «Відкрити папку з ZIP» видимою
        self.btnOpenFolder.setVisible(True)

    # -----------------------
    # Встановити ZIP
    # -----------------------
    def onInstall(self):
        """Копіює потрібні файли з ZIP (за INSTALL_MAP) у папку гри."""
        choice = self.comboInstall.currentText()  # Universe_mod / H5AI_31 / Maps
        save_dir = self.edtSave.text().strip()
        zip_path = os.path.join(save_dir, f"{choice}.zip")

        if not os.path.isfile(zip_path):
            self.txtLog.append(f"❌ ZIP-файл не знайдено: {zip_path}")
            return

        hero_root = self.edtHeroRoot.text().strip()
        if not hero_root or not os.path.isdir(hero_root):
            self.txtLog.append("❌ Некоректна коренева папка гри")
            return

        mapping = INSTALL_MAP.get(choice, {})
        self.txtLog.append(f"⚙️ Інсталяція «{choice}» у {hero_root}")

        with zipfile.ZipFile(zip_path, "r") as archive:
            for subfolder, files in mapping.items():
                dest = os.path.join(hero_root, subfolder)
                os.makedirs(dest, exist_ok=True)

                for member in archive.namelist():
                    base = os.path.basename(member)
                    # Якщо ["*"] → переносимо всі файли
                    if files == ["*"] or base.lower() in [f.lower() for f in files]:
                        tmp = tempfile.mkdtemp()
                        archive.extract(member, tmp)
                        dest_file = os.path.join(dest, base)

                        # Перезапитати, якщо існує
                        if os.path.exists(dest_file):
                            reply = QMessageBox.question(
                                self, "Перезаписати файл?",
                                f"Файл «{base}» вже існує у {dest}. Перезаписати?",
                                QMessageBox.Yes | QMessageBox.No
                            )
                            if reply == QMessageBox.No:
                                shutil.rmtree(tmp)
                                continue
                            os.remove(dest_file)

                        shutil.move(os.path.join(tmp, member), dest)
                        shutil.rmtree(tmp)
                        self.txtLog.append(f"✔ {base} → {dest}")

        self.txtLog.append(f"✅ «{choice}» успішно встановлено")

    # -----------------------
    # Додаткові кнопки
    # -----------------------
    def openZipFolder(self):
        """Відкрити теку, де зберігаються ZIP-файли."""
        path = self.edtSave.text().strip()
        if os.path.isdir(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            self.txtLog.append("❌ Тека з ZIP не існує.")

    def showFullLogDialog(self):
        """Показати повний лог у новому вікні (копія тексту)."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Повний лог")
        dlg.resize(600, 400)

        layout = QVBoxLayout(dlg)
        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(self.txtLog.toPlainText())
        layout.addWidget(txt)

        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(dlg.accept)
        layout.addWidget(btns)

        dlg.exec()

    # -----------------------
    # Допоміжне логування
    # -----------------------
    def log(self, message: str):
        self.txtLog.append(message)
        print(message)
