# universe_editor_tab.py
import os
import zipfile
import shutil
import tempfile
from xml.etree import ElementTree as ET

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QProgressBar, QFileDialog, QTextEdit, QCheckBox
)

# Папки й коефіцієнти
CREATURE_FOLDERS = [
    "Academy", "Dungeon", "Dwarf", "Haven", "Inferno",
    "Necropolis", "Neutrals", "Orcs", "Preserve"
]
PERCENT_FACTORS = {
    "50%": 0.50,
    "75%": 0.75,
    "100%": 1.00,
    "125%": 1.25,
    "150%": 1.50,
    "175%": 1.75,
    "200%": 2.00,
    "225%": 2.25,
    "250%": 2.50
}


class InplacePatchWorker(QThread):
    """
    Потік, що редагує WeeklyGrowth у .xdb файлах (Universe_mod.pak).
    """
    progressChanged = Signal(int)
    logMessage = Signal(str)
    finishedSignal = Signal(str)

    def __init__(self, pakPath, factor, doBackup, creatureFilter, dryRun, parent=None):
        super().__init__(parent)
        self.pakPath = pakPath
        self.factor = factor
        self.doBackup = doBackup
        self.creatureFilter = creatureFilter.lower().strip()
        self.dryRun = dryRun

    def run(self):
        try:
            if not os.path.isfile(self.pakPath):
                self.finishedSignal.emit("Помилка: Universe_mod.pak не знайдено.")
                return

            # Перевірка прав
            if not os.access(self.pakPath, os.R_OK):
                self.finishedSignal.emit("Помилка: немає прав на читання .pak")
                return
            if not os.access(os.path.dirname(self.pakPath), os.W_OK):
                self.finishedSignal.emit("Помилка: немає прав на запис у теку .pak")
                return

            self.logMessage.emit("Читаємо оригінальний .pak...")
            with zipfile.ZipFile(self.pakPath, 'r') as z_in:
                file_names = z_in.namelist()
                total = len(file_names)

            tmp_dir = tempfile.mkdtemp(prefix="universe_inplace_")

            # Розпаковуємо
            extracted_count = 0
            with zipfile.ZipFile(self.pakPath, 'r') as z_in:
                for f_name in file_names:
                    info = z_in.getinfo(f_name)
                    if info.is_dir():
                        dest_dir = os.path.join(tmp_dir, f_name)
                        os.makedirs(dest_dir, exist_ok=True)
                        extracted_count += 1
                        prog = int(50 * extracted_count / total)
                        self.progressChanged.emit(prog)
                        continue

                    dest_path = os.path.join(tmp_dir, f_name)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    with z_in.open(info) as fin, open(dest_path, 'wb') as fout:
                        shutil.copyfileobj(fin, fout)

                    extracted_count += 1
                    prog = int(50 * extracted_count / total)
                    self.progressChanged.emit(prog)

            self.logMessage.emit("Аналізуємо .xdb та змінюємо WeeklyGrowth...")
            creatures_root = os.path.join(tmp_dir, "GameMechanics", "Creature", "Creatures")
            xdb_files = self._collect_xdb(creatures_root)

            changed_count = 0
            sample_info = None
            changed_files_list = []

            if not self.dryRun:
                changed_count, sample_info = self._process_xdb_files(xdb_files, changed_files_list)
            else:
                # Лише dry-run
                for xdb_path in xdb_files:
                    c, info = self._dry_check_xdb(xdb_path)
                    if c:
                        changed_count += 1
                        changed_files_list.append(os.path.basename(xdb_path))
                        if sample_info is None and info:
                            sample_info = info

            # backup
            if not self.dryRun and self.doBackup:
                backup_path = self.pakPath + ".backup"
                if not os.path.exists(backup_path):
                    shutil.copy2(self.pakPath, backup_path)
                    self.logMessage.emit(f"Створено резервну копію: {backup_path}")

            if self.dryRun:
                shutil.rmtree(tmp_dir)
                msg = f"[РЕЖИМ ПЕРЕГЛЯДУ] Зміни: {changed_count} файлів"
                if sample_info:
                    cr_name, oldv, newv = sample_info
                    msg += f" (Приклад: {cr_name} {oldv}→{newv})"
                self.finishedSignal.emit(msg)
                return

            # Перезапаковуємо
            new_pak = self.pakPath + ".new"
            self.logMessage.emit("Запаковуємо оновлений архів...")
            updated_files = []
            for root, dirs, files in os.walk(tmp_dir):
                for f in files:
                    updated_files.append(os.path.join(root, f))
            total_updated = len(updated_files)

            packed_count = 0
            with zipfile.ZipFile(new_pak, 'w', compression=zipfile.ZIP_DEFLATED) as z_out:
                for fpath in updated_files:
                    rel_path = os.path.relpath(fpath, tmp_dir)
                    z_out.write(fpath, rel_path)
                    packed_count += 1
                    prog = 50 + int(50 * packed_count / total_updated)
                    self.progressChanged.emit(prog)

            # Заміна
            os.remove(self.pakPath)
            os.rename(new_pak, self.pakPath)
            shutil.rmtree(tmp_dir)

            # Лог
            if changed_files_list:
                self.logMessage.emit("Змінено файли:")
                for f in changed_files_list:
                    self.logMessage.emit(f" - {f}")

            if changed_count > 0:
                if sample_info:
                    cr_name, oldv, newv = sample_info
                    msg = f"Готово! Змінено {changed_count} .xdb. Приклад: {cr_name} {oldv}→{newv}"
                else:
                    msg = f"Готово! Змінено {changed_count} .xdb"
            else:
                msg = "Готово! Не знайдено змін."
            self.finishedSignal.emit(msg)

        except Exception as e:
            self.finishedSignal.emit(f"Помилка: {e}")

    def _collect_xdb(self, creatures_root):
        xdb_files = []
        if not os.path.isdir(creatures_root):
            return xdb_files

        for root, dirs, files in os.walk(creatures_root):
            for f in files:
                if not f.lower().endswith(".xdb"):
                    continue
                rel_path = os.path.relpath(os.path.join(root, f), creatures_root)
                folder_top = rel_path.split(os.sep, 1)[0]
                if folder_top not in CREATURE_FOLDERS:
                    continue

                if self.creatureFilter and self.creatureFilter not in f.lower():
                    continue
                xdb_files.append(os.path.join(root, f))
        return xdb_files

    def _process_xdb_files(self, xdb_files, changed_files_list):
        changed_count = 0
        sample_info = None
        total_files = len(xdb_files)
        for i, p in enumerate(xdb_files, start=1):
            changed, info = self._patch_xdb(p, self.factor)
            if changed:
                changed_count += 1
                changed_files_list.append(os.path.basename(p))
                if sample_info is None and info:
                    sample_info = info
            prog = 50 + int(40 * i / total_files)
            self.progressChanged.emit(prog)
        return changed_count, sample_info

    def _dry_check_xdb(self, path):
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except ET.ParseError:
            return False, None

        changed = False
        sample = None
        for elem in root.iter("WeeklyGrowth"):
            val_str = (elem.text or "").strip()
            if val_str.isdigit():
                old_val = int(val_str)
                new_val = int(round(old_val * self.factor))
                if old_val != new_val:
                    changed = True
                    if not sample:
                        c_name = os.path.splitext(os.path.basename(path))[0]
                        sample = (c_name, old_val, new_val)
        return changed, sample

    def _patch_xdb(self, path, factor):
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except ET.ParseError:
            return False, None

        changed = False
        sample = None
        for elem in root.iter("WeeklyGrowth"):
            val_str = (elem.text or "").strip()
            if val_str.isdigit():
                old_val = int(val_str)
                new_val = int(round(old_val * factor))
                if new_val != old_val:
                    elem.text = str(new_val)
                    changed = True
                    if not sample:
                        c_name = os.path.splitext(os.path.basename(path))[0]
                        sample = (c_name, old_val, new_val)

        if changed:
            tree.write(path, encoding="utf-8", xml_declaration=True)
            return True, sample
        return False, None


class UniverseEditorTab(QWidget):
    """
    Вкладка зі всім функціоналом Universe Editor:
    поле для Universe_mod.pak, dry-run, backup тощо.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())

        # 1) Поле Universe_mod
        rowPak = QHBoxLayout()
        self.layout().addLayout(rowPak)
        lblPak = QLabel("Universe_mod.pak:")
        rowPak.addWidget(lblPak)
        self.edtPakPath = QLineEdit(r"C:\Games\HeroesV\data\Universe_mod.pak")
        rowPak.addWidget(self.edtPakPath)
        btnBrowse = QPushButton("Огляд")
        rowPak.addWidget(btnBrowse)
        btnBrowse.clicked.connect(self.onBrowse)

        # 2) % коеф
        rowFactor = QHBoxLayout()
        self.layout().addLayout(rowFactor)
        lblFactor = QLabel("Множник WeeklyGrowth:")
        rowFactor.addWidget(lblFactor)
        self.cmbFactor = QComboBox()
        for k in PERCENT_FACTORS:
            self.cmbFactor.addItem(k)
        self.cmbFactor.setCurrentText("150%")
        rowFactor.addWidget(self.cmbFactor)

        # 3) Фільтр
        fltRow = QHBoxLayout()
        self.layout().addLayout(fltRow)
        fltRow.addWidget(QLabel("Фільтр назви:"))
        self.edtFilter = QLineEdit()
        fltRow.addWidget(self.edtFilter)

        # 4) Прапорці
        self.chkBackup = QCheckBox("Створити .backup")
        self.chkBackup.setChecked(True)
        self.layout().addWidget(self.chkBackup)

        self.chkDryRun = QCheckBox("Режим перегляду (dry-run)")
        self.layout().addWidget(self.chkDryRun)

        # 5) Кнопки
        btnRow = QHBoxLayout()
        self.layout().addLayout(btnRow)
        self.btnRun = QPushButton("Почати")
        btnRow.addWidget(self.btnRun)
        self.btnRun.clicked.connect(self.onRun)
        self.btnCheck = QPushButton("Перевірити права")
        btnRow.addWidget(self.btnCheck)
        self.btnCheck.clicked.connect(self.onCheck)
        self.btnRestore = QPushButton("Відновити з .backup")
        btnRow.addWidget(self.btnRestore)
        self.btnRestore.clicked.connect(self.onRestore)

        # 6) Прогрес
        self.prgBar = QProgressBar()
        self.layout().addWidget(self.prgBar)

        # 7) Логи
        self.txtLog = QTextEdit()
        self.txtLog.setReadOnly(True)
        self.layout().addWidget(self.txtLog, stretch=1)

        self.worker = None

    def onBrowse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Universe_mod.pak", "",
                                              "PAK Files (*.pak);;All Files (*.*)")
        if path:
            self.edtPakPath.setText(path)

    def onRun(self):
        pak_path = self.edtPakPath.text().strip()
        factor_str = self.cmbFactor.currentText()
        factor = PERCENT_FACTORS[factor_str]
        do_backup = self.chkBackup.isChecked()
        dry_run = self.chkDryRun.isChecked()
        creature_filter = self.edtFilter.text().strip()

        if not pak_path or not os.path.isfile(pak_path):
            self.logMsg("Помилка: невірний шлях")
            return

        self.btnRun.setEnabled(False)
        self.prgBar.setValue(0)
        self.logMsg(f"Починаємо... {factor_str}, filter='{creature_filter}'\n")

        self.worker = InplacePatchWorker(pak_path, factor, do_backup, creature_filter, dry_run)
        self.worker.progressChanged.connect(self.onProgress)
        self.worker.logMessage.connect(self.logMsg)
        self.worker.finishedSignal.connect(self.onFinished)
        self.worker.start()

    def onCheck(self):
        p = self.edtPakPath.text().strip()
        if not p:
            self.logMsg("Не вказано Universe_mod.pak.")
            return
        can_read = os.access(p, os.R_OK)
        can_write_dir = os.access(os.path.dirname(p), os.W_OK)
        self.logMsg(f"Перевірка:\n  read={can_read}, write_dir={can_write_dir}")

    def onRestore(self):
        p = self.edtPakPath.text().strip()
        backup = p + ".backup"
        if not os.path.exists(backup):
            self.logMsg("backup-файл не знайдено.")
            return
        if os.path.exists(p):
            os.remove(p)
        os.rename(backup, p)
        self.logMsg("Відновлено з .backup.")

    def onProgress(self, val):
        self.prgBar.setValue(val)

    def onFinished(self, msg):
        self.logMsg(msg)
        self.btnRun.setEnabled(True)
        self.prgBar.setValue(100)

        # beep
        from PySide6.QtWidgets import QApplication
        QApplication.beep()

    def logMsg(self, text: str):
        self.txtLog.append(text)