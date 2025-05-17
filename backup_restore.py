#!/usr/bin/env python3
import os
import sys
import time
import datetime
import hashlib
import tarfile
import shutil
import threading
import json
import logging
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLineEdit, QFileDialog, QCheckBox, QSlider, QComboBox,
                             QSpinBox, QListWidget, QTextEdit, QProgressBar, QLabel, QFrame, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

class BackupWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    completed = pyqtSignal(str)

    def __init__(self, app, backup_name, dest, folders, compression_level, calculate_checksums):
        super().__init__()
        self.app = app
        self.backup_name = backup_name
        self.dest = dest
        self.folders = folders
        self.compression_level = compression_level
        self.calculate_checksums = calculate_checksums

    def run(self):
        try:
            backup_file = os.path.join(self.dest, f"{self.backup_name}.tar.gz")
            self.status.emit(f"Starting backup to {backup_file}...")
            self.progress.emit(0)

            manifest = {
                "created": datetime.datetime.now().isoformat(),
                "folders": self.folders,
                "files": {}
            }

            total_files = 0
            for folder in self.folders:
                for root, _, files in os.walk(folder):
                    total_files += len(files)

            processed_files = 0

            with tarfile.open(backup_file, f"w:gz", compresslevel=self.compression_level) as tar:
                for folder in self.folders:
                    folder_path = Path(folder)
                    base_name = folder_path.name
                    for root, _, files in os.walk(folder):
                        for file in files:
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, folder_path.parent)
                            short_path = os.path.join(base_name, os.path.relpath(file_path, folder))
                            self.status.emit(f"Adding: {short_path}")
                            tar.add(file_path, arcname=rel_path)

                            if self.calculate_checksums:
                                checksum = self.app.calculate_checksum(file_path)
                                manifest["files"][rel_path] = {
                                    "checksum": checksum,
                                    "size": os.path.getsize(file_path),
                                    "modified": datetime.datetime.fromtimestamp(
                                        os.path.getmtime(file_path)).isoformat()
                                }

                            processed_files += 1
                            progress = int(processed_files / total_files * 100)
                            self.progress.emit(progress)

                manifest_content = json.dumps(manifest, indent=2)
                manifest_file = os.path.join(self.dest, "manifest.json")
                with open(manifest_file, 'w') as f:
                    f.write(manifest_content)
                tar.add(manifest_file, arcname="manifest.json")
                os.unlink(manifest_file)

            self.app.manage_retention()
            self.progress.emit(100)
            self.completed.emit(f"Backup completed: {backup_file}")
        except Exception as e:
            error_msg = f"Backup failed: {str(e)}"
            self.error.emit(error_msg)

class RestoreWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    completed = pyqtSignal(str)

    def __init__(self, app, backup_file, restore_dest, verify_checksums, overwrite):
        super().__init__()
        self.app = app
        self.backup_file = backup_file
        self.restore_dest = restore_dest
        self.verify_checksums = verify_checksums
        self.overwrite = overwrite

    def run(self):
        try:
            self.status.emit(f"Starting restore from {self.backup_file}...")
            self.progress.emit(0)

            manifest = None
            with tarfile.open(self.backup_file, "r:gz") as tar:
                try:
                    manifest_file = tar.extractfile("manifest.json")
                    manifest = json.loads(manifest_file.read().decode())
                except KeyError:
                    self.app.logger.warning("No manifest found in backup archive")

            total_files = 0
            with tarfile.open(self.backup_file, "r:gz") as tar:
                total_files = sum(1 for member in tar.getmembers() if member.isfile())

            processed_files = 0

            with tarfile.open(self.backup_file, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name == "manifest.json":
                        continue
                    if not member.isfile():
                        continue

                    dest_path = os.path.join(self.restore_dest, member.name)
                    dest_dir = os.path.dirname(dest_path)
                    os.makedirs(dest_dir, exist_ok=True)

                    if os.path.exists(dest_path) and not self.overwrite:
                        self.app.logger.info(f"Skipping existing file: {dest_path}")
                        processed_files += 1
                        progress = int(processed_files / total_files * 100)
                        self.progress.emit(progress)
                        continue

                    self.status.emit(f"Restoring: {member.name}")
                    tar.extract(member, path=self.restore_dest)

                    if self.verify_checksums and manifest and member.name in manifest["files"]:
                        restored_checksum = self.app.calculate_checksum(dest_path)
                        original_checksum = manifest["files"][member.name]["checksum"]
                        if restored_checksum != original_checksum:
                            raise Exception(f"Checksum verification failed for {member.name}")

                    processed_files += 1
                    progress = int(processed_files / total_files * 100)
                    self.progress.emit(progress)

            self.progress.emit(100)
            self.completed.emit(f"Restore completed to {self.restore_dest}")
        except Exception as e:
            error_msg = f"Restore failed: {str(e)}"
            self.error.emit(error_msg)

class BackupRestoreApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Backup & Restore Utility")
        self.setMinimumSize(800, 600)
        self.config_file = os.path.join(os.path.expanduser("~"), ".backup_restore_config.json")
        self.config = self.load_config()

        log_dir = os.path.join(os.path.expanduser("~"), "backup_logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "backup_restore.log")
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
        )
        self.logger = logging
        self.folder_paths = self.config.get("folders", [])
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        self.create_backup_tab()
        self.create_restore_tab()
        self.create_settings_tab()
        self.create_logs_tab()

        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        main_layout.addWidget(self.progress_bar)

    def create_backup_tab(self):
        backup_tab = QWidget()
        layout = QVBoxLayout(backup_tab)

        folder_frame = QFrame()
        folder_layout = QVBoxLayout(folder_frame)
        folder_layout.addWidget(QLabel("Folders to Backup"))
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Folder")
        add_btn.clicked.connect(self.add_folder)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.remove_folder)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        folder_layout.addLayout(btn_layout)
        self.folder_list = QListWidget()
        self.refresh_folder_list()
        folder_layout.addWidget(self.folder_list)
        layout.addWidget(folder_frame)

        dest_frame = QFrame()
        dest_layout = QHBoxLayout(dest_frame)
        dest_layout.addWidget(QLabel("Destination Folder:"))
        self.dest_edit = QLineEdit(self.config.get("last_backup_destination", ""))
        dest_layout.addWidget(self.dest_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.select_destination)
        dest_layout.addWidget(browse_btn)
        layout.addWidget(dest_frame)

        options_frame = QFrame()
        options_layout = QVBoxLayout(options_frame)
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Backup Name:"))
        current_date = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_name_edit = QLineEdit(f"backup_{current_date}")
        name_layout.addWidget(self.backup_name_edit)
        options_layout.addLayout(name_layout)
        comp_layout = QHBoxLayout()
        comp_layout.addWidget(QLabel("Compression Level:"))
        self.compression_slider = QSlider(Qt.Horizontal)
        self.compression_slider.setRange(1, 9)
        self.compression_slider.setValue(self.config.get("compression_level", 6))
        comp_layout.addWidget(self.compression_slider)
        options_layout.addLayout(comp_layout)
        self.checksum_check = QCheckBox("Calculate Checksums")
        self.checksum_check.setChecked(self.config.get("calculate_checksums", True))
        options_layout.addWidget(self.checksum_check)
        layout.addWidget(options_frame)

        start_btn = QPushButton("Start Backup")
        start_btn.clicked.connect(self.start_backup)
        layout.addWidget(start_btn)
        self.tabs.addTab(backup_tab, "Backup")

    def create_restore_tab(self):
        restore_tab = QWidget()
        layout = QVBoxLayout(restore_tab)

        select_frame = QFrame()
        select_layout = QHBoxLayout(select_frame)
        select_layout.addWidget(QLabel("Backup File:"))
        self.restore_path_edit = QLineEdit()
        select_layout.addWidget(self.restore_path_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.select_backup_file)
        select_layout.addWidget(browse_btn)
        layout.addWidget(select_frame)

        dest_frame = QFrame()
        dest_layout = QHBoxLayout(dest_frame)
        dest_layout.addWidget(QLabel("Destination:"))
        self.restore_dest_edit = QLineEdit()
        dest_layout.addWidget(self.restore_dest_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.select_restore_destination)
        dest_layout.addWidget(browse_btn)
        layout.addWidget(dest_frame)

        options_frame = QFrame()
        options_layout = QVBoxLayout(options_frame)
        self.verify_check = QCheckBox("Verify Checksums")
        self.verify_check.setChecked(True)
        self.overwrite_check = QCheckBox("Overwrite Existing Files")
        options_layout.addWidget(self.verify_check)
        options_layout.addWidget(self.overwrite_check)
        layout.addWidget(options_frame)

        info_frame = QFrame()
        info_layout = QVBoxLayout(info_frame)
        info_layout.addWidget(QLabel("Backup Information"))
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        info_layout.addWidget(self.info_text)
        layout.addWidget(info_frame)

        start_btn = QPushButton("Start Restore")
        start_btn.clicked.connect(self.start_restore)
        layout.addWidget(start_btn)
        self.tabs.addTab(restore_tab, "Restore")

    def create_settings_tab(self):
        settings_tab = QWidget()
        layout = QVBoxLayout(settings_tab)

        schedule_frame = QFrame()
        schedule_layout = QVBoxLayout(schedule_frame)
        self.schedule_check = QCheckBox("Enable Scheduled Backups")
        self.schedule_check.setChecked(self.config.get("scheduled_backups", False))
        self.schedule_check.stateChanged.connect(self.toggle_schedule_options)
        schedule_layout.addWidget(self.schedule_check)
        self.schedule_options = QFrame()
        options_layout = QHBoxLayout(self.schedule_options)
        options_layout.addWidget(QLabel("Frequency:"))
        self.frequency_combo = QComboBox()
        self.frequency_combo.addItems(["hourly", "daily", "weekly", "monthly"])
        self.frequency_combo.setCurrentText(self.config.get("backup_frequency", "daily"))
        options_layout.addWidget(self.frequency_combo)
        schedule_layout.addWidget(self.schedule_options)
        layout.addWidget(schedule_frame)

        retention_frame = QFrame()
        retention_layout = QHBoxLayout(retention_frame)
        retention_layout.addWidget(QLabel("Keep backups for:"))
        self.retention_spin = QSpinBox()
        self.retention_spin.setRange(1, 100)
        self.retention_spin.setValue(self.config.get("retention_count", 5))
        retention_layout.addWidget(self.retention_spin)
        self.retention_unit_combo = QComboBox()
        self.retention_unit_combo.addItems(["backups", "days", "weeks", "months"])
        self.retention_unit_combo.setCurrentText(self.config.get("retention_unit", "backups"))
        retention_layout.addWidget(self.retention_unit_combo)
        layout.addWidget(retention_frame)

        notify_frame = QFrame()
        notify_layout = QVBoxLayout(notify_frame)
        self.notify_success_check = QCheckBox("Notify on successful backup")
        self.notify_success_check.setChecked(self.config.get("notify_success", True))
        self.notify_failure_check = QCheckBox("Notify on backup failure")
        self.notify_failure_check.setChecked(self.config.get("notify_failure", True))
        notify_layout.addWidget(self.notify_success_check)
        notify_layout.addWidget(self.notify_failure_check)
        layout.addWidget(notify_frame)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        self.tabs.addTab(settings_tab, "Settings")
        self.toggle_schedule_options()

    def create_logs_tab(self):
        logs_tab = QWidget()
        layout = QVBoxLayout(logs_tab)

        log_frame = QFrame()
        log_layout = QVBoxLayout(log_frame)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_frame)

        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Logs")
        refresh_btn.clicked.connect(self.refresh_logs)
        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_logs)
        export_btn = QPushButton("Export Logs")
        export_btn.clicked.connect(self.export_logs)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(export_btn)
        layout.addLayout(btn_layout)
        self.tabs.addTab(logs_tab, "Logs")
        self.refresh_logs()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "last_backup_destination": os.path.expanduser("~/Backups"),
            "compression_level": 6,
            "calculate_checksums": True,
            "scheduled_backups": False,
            "backup_frequency": "daily",
            "retention_count": 5,
            "retention_unit": "backups",
            "notify_success": True,
            "notify_failure": True,
            "folders": []
        }

    def save_config(self):
        self.config["last_backup_destination"] = self.dest_edit.text()
        self.config["compression_level"] = self.compression_slider.value()
        self.config["calculate_checksums"] = self.checksum_check.isChecked()
        self.config["scheduled_backups"] = self.schedule_check.isChecked()
        self.config["backup_frequency"] = self.frequency_combo.currentText()
        self.config["retention_count"] = self.retention_spin.value()
        self.config["retention_unit"] = self.retention_unit_combo.currentText()
        self.config["notify_success"] = self.notify_success_check.isChecked()
        self.config["notify_failure"] = self.notify_failure_check.isChecked()
        self.config["folders"] = self.folder_paths
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")
            self.logger.error(f"Failed to save configuration: {str(e)}")

    def refresh_folder_list(self):
        self.folder_list.clear()
        for folder in self.folder_paths:
            self.folder_list.addItem(folder)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Backup")
        if folder and folder not in self.folder_paths:
            self.folder_paths.append(folder)
            self.folder_list.addItem(folder)
            self.save_config()

    def remove_folder(self):
        selected_items = self.folder_list.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.folder_paths.remove(item.text())
            self.folder_list.takeItem(self.folder_list.row(item))
        self.save_config()

    def select_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Destination")
        if folder:
            self.dest_edit.setText(folder)

    def select_backup_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Select Backup File", "", "Backup Files (*.tar.gz);;All Files (*.*)"
        )
        if file:
            self.restore_path_edit.setText(file)
            self.show_backup_info(file)

    def select_restore_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Restore Destination")
        if folder:
            self.restore_dest_edit.setText(folder)

    def show_backup_info(self, backup_file):
        self.info_text.clear()
        try:
            if not os.path.exists(backup_file):
                self.info_text.append("File not found.")
                return
            file_size = os.path.getsize(backup_file)
            file_size_mb = file_size / (1024 * 1024)
            file_date = datetime.datetime.fromtimestamp(os.path.getmtime(backup_file))
            info_text = f"File: {os.path.basename(backup_file)}\n"
            info_text += f"Size: {file_size_mb:.2f} MB\n"
            info_text += f"Date: {file_date}\n\n"
            info_text += "Contents:\n"
            with tarfile.open(backup_file, "r:gz") as tar:
                top_dirs = set()
                for member in tar.getmembers():
                    if '/' in member.name:
                        top_dir = member.name.split('/')[0]
                        top_dirs.add(top_dir)
                    else:
                        top_dirs.add(member.name)
                for dir_name in sorted(top_dirs):
                    info_text += f"- {dir_name}\n"
            self.info_text.append(info_text)
        except Exception as e:
            self.info_text.append(f"Error reading backup file: {str(e)}")

    def toggle_schedule_options(self):
        enabled = self.schedule_check.isChecked()
        self.schedule_options.setEnabled(enabled)
        if enabled:
            self.start_scheduler()
        else:
            self.stop_scheduler()

    def save_settings(self):
        self.save_config()
        QMessageBox.information(self, "Settings", "Settings saved successfully")

    def refresh_logs(self):
        log_file = os.path.join(os.path.expanduser("~"), "backup_logs", "backup_restore.log")
        self.log_text.clear()
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()[-1000:]
                    self.log_text.append(''.join(lines))
            else:
                self.log_text.append("No log file found.")
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum())
        except Exception as e:
            self.log_text.append(f"Error reading log file: {str(e)}")

    def clear_logs(self):
        if QMessageBox.question(self, "Clear Logs", "Are you sure you want to clear all logs?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            log_file = os.path.join(os.path.expanduser("~"), "backup_logs", "backup_restore.log")
            try:
                with open(log_file, 'w') as f:
                    f.write(f"Logs cleared on {datetime.datetime.now()}\n")
                self.refresh_logs()
                QMessageBox.information(self, "Logs", "Logs have been cleared")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear logs: {str(e)}")

    def export_logs(self):
        file, _ = QFileDialog.getSaveFileName(
            self, "Export Logs", "", "Log Files (*.log);;Text Files (*.txt);;All Files (*.*)"
        )
        if file:
            log_file = os.path.join(os.path.expanduser("~"), "backup_logs", "backup_restore.log")
            try:
                if os.path.exists(log_file):
                    shutil.copy2(log_file, file)
                    QMessageBox.information(self, "Export", "Logs exported successfully")
                else:
                    QMessageBox.warning(self, "Export", "No log file found to export")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export logs: {str(e)}")

    def calculate_checksum(self, file_path):
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    def start_backup(self):
        if not self.folder_paths:
            QMessageBox.critical(self, "Error", "No folders selected for backup")
            return
        backup_dest = self.dest_edit.text()
        if not backup_dest:
            QMessageBox.critical(self, "Error", "No backup destination selected")
            return
        if not os.path.exists(backup_dest):
            try:
                os.makedirs(backup_dest)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create destination directory: {str(e)}")
                return
        self.backup_worker = BackupWorker(
            self, self.backup_name_edit.text(), backup_dest, self.folder_paths,
            self.compression_slider.value(), self.checksum_check.isChecked()
        )
        self.backup_worker.progress.connect(self.progress_bar.setValue)
        self.backup_worker.status.connect(self.status_label.setText)
        self.backup_worker.error.connect(
            lambda msg: QMessageBox.critical(self, "Backup Failed", msg) if self.notify_failure_check.isChecked() else None)
        self.backup_worker.completed.connect(
            lambda msg: QMessageBox.information(self, "Backup Complete", msg) if self.notify_success_check.isChecked() else None)
        self.backup_worker.start()

    def start_restore(self):
        backup_file = self.restore_path_edit.text()
        if not backup_file or not os.path.exists(backup_file):
            QMessageBox.critical(self, "Error", "Backup file not found")
            return
        restore_dest = self.restore_dest_edit.text()
        if not restore_dest:
            QMessageBox.critical(self, "Error", "No restore destination selected")
            return
        if not os.path.exists(restore_dest):
            try:
                os.makedirs(restore_dest)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create destination directory: {str(e)}")
                return
        if QMessageBox.question(self, "Confirm Restore",
                                f"Are you sure you want to restore from {backup_file} to {restore_dest}?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self.restore_worker = RestoreWorker(
            self, backup_file, restore_dest, self.verify_check.isChecked(), self.overwrite_check.isChecked()
        )
        self.restore_worker.progress.connect(self.progress_bar.setValue)
        self.restore_worker.status.connect(self.status_label.setText)
        self.restore_worker.error.connect(
            lambda msg: QMessageBox.critical(self, "Restore Failed", msg) if self.notify_failure_check.isChecked() else None)
        self.restore_worker.completed.connect(
            lambda msg: QMessageBox.information(self, "Restore Complete", msg) if self.notify_success_check.isChecked() else None)
        self.restore_worker.start()

    def start_scheduler(self):
        if not self.schedule_check.isChecked():
            return
        self.stop_scheduler()
        frequency = self.frequency_combo.currentText()
        intervals = {"hourly": 3600, "daily": 86400, "weekly": 604800, "monthly": 2592000}
        interval = intervals.get(frequency, 86400)
        self.schedule_next_backup(interval)

    def stop_scheduler(self):
        if hasattr(self, 'scheduler_thread') and self.scheduler_thread.is_alive():
            self.scheduler_event.set()
            self.scheduler_thread.join()
        self.scheduler_event = threading.Event()

    def schedule_next_backup(self, interval):
        def run_scheduled_backup():
            while not self.scheduler_event.is_set():
                self.perform_backup()
                self.scheduler_event.wait(interval)
        self.scheduler_event = threading.Event()
        self.scheduler_thread = threading.Thread(target=run_scheduled_backup, daemon=True)
        self.scheduler_thread.start()

    def perform_backup(self):
        worker = BackupWorker(
            self, self.backup_name_edit.text(), self.dest_edit.text(), self.folder_paths,
            self.compression_slider.value(), self.checksum_check.isChecked()
        )
        worker.run()

    def manage_retention(self):
        backup_dest = self.dest_edit.text()
        retention_count = self.retention_spin.value()
        retention_unit = self.retention_unit_combo.currentText()
        if not os.path.exists(backup_dest):
            return
        backup_files = [f for f in os.listdir(backup_dest) if f.endswith('.tar.gz')]
        if not backup_files:
            return
        backup_files.sort(
            key=lambda x: os.path.getmtime(os.path.join(backup_dest, x)), reverse=True
        )
        if retention_unit == "backups":
            for old_backup in backup_files[retention_count:]:
                try:
                    os.remove(os.path.join(backup_dest, old_backup))
                    self.logger.info(f"Removed old backup: {old_backup}")
                except Exception as e:
                    self.logger.error(f"Failed to remove old backup {old_backup}: {str(e)}")
        else:
            now = datetime.datetime.now()
            time_units = {"days": 1, "weeks": 7, "months": 30}
            cutoff_days = retention_count * time_units[retention_unit]
            cutoff_time = now - datetime.timedelta(days=cutoff_days)
            for backup_file in backup_files:
                file_path = os.path.join(backup_dest, backup_file)
                file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_mtime < cutoff_time:
                    try:
                        os.remove(file_path)
                        self.logger.info(f"Removed old backup: {backup_file}")
                    except Exception as e:
                        self.logger.error(f"Failed to remove old backup {backup_file}: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BackupRestoreApp()
    window.show()
    sys.exit(app.exec_())
