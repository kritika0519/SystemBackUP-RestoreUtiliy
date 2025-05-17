# 🛡️ System Backup and Restore Utility

A user-friendly Python application with a **PyQt5 GUI** for backing up and restoring files and folders on Linux systems (tested on **Kali Linux**). The utility supports **scheduled backups**, **retention policies**, **checksum verification**, and **detailed logging**—ideal for personal and system-level file management.

---

## ✨ Features

### 🔁 Backup

- Create compressed `.tar.gz` archives of selected folders.
- Customize compression level (1–9).
- Enable **SHA-256 checksums** for file integrity.
- Generate a `manifest.json` file with metadata (file paths, sizes, checksums).
- Real-time **progress bar** and **status updates**.

### 🔄 Restore

- Restore files from `.tar.gz` backups to a specified location.
- Optional checksum verification.
- Option to **overwrite existing files**.
- Display **backup details**: size, date, and contents.

### 🕒 Scheduling

- Schedule backups: **hourly, daily, weekly, or monthly**.
- Run backups in the **background using threading**.

### 📦 Retention Policies

- Keep a specified number of backups or set **retention duration** (days/weeks/months).
- Auto-delete old backups to save disk space.

### 🧾 Logging

- Logs all actions and errors to `~/backup_logs/backup_restore.log`.
- View, refresh, clear, or export logs via the GUI.

### ⚙️ Configuration

- Save settings in `~/.backup_restore_config.json`.
- Loads settings on startup with **sensible defaults**.

### 🖼️ User Interface

- **Modern PyQt5 GUI** with tabs for:
  - **Backup**
  - **Restore**
  - **Settings**
  - **Logs**
- Responsive design with progress bars, native dialogs, and real-time updates.

---

## 📋 Requirements

- **OS**: Linux (Kali), macOS, or Windows
- **Python**: 3.6+
- **Python Libraries**:
  - PyQt5
  - `os`, `sys`, `time`, `datetime`, `hashlib`, `tarfile`, `shutil`, `threading`, `json`, `logging`, `pathlib`

- **System Tools**: `tar`, `gzip` (pre-installed on most Linux systems)

---

## 🛠️ Installation on Kali Linux

### ✅ Option 1: Install with APT (Recommended)

```bash
sudo apt update
sudo apt install python3 python3-pyqt5
python3 -c "import PyQt5; print(PyQt5.__version__)"
````

### 🧪 Option 2: Install in a Virtual Environment

```bash
sudo apt install python3-venv python3-pip
mkdir ~/backup_restore
cd ~/backup_restore
python3 -m venv venv
source venv/bin/activate
pip install PyQt5
deactivate
```

---

## 💾 Download the Code

```bash
nano backup_restore.py
# Paste the source code into this file
# Save and exit: Ctrl+O, Enter, Ctrl+X
chmod +x backup_restore.py  # (optional)
```

---

## 🚀 Usage

### 🖥️ Run the Application

**If using APT:**

```bash
python3 backup_restore.py
```

**If using Virtual Environment:**

```bash
cd ~/backup_restore
source venv/bin/activate
python backup_restore.py
```

---

## 🧩 GUI Overview

### 📂 Backup Tab

* Click `Add Folder` to select folders.
* Set destination and backup name.
* Choose compression level and enable checksums (optional).
* Click `Start Backup`.

### 🧰 Restore Tab

* Select a `.tar.gz` file via `Browse`.
* View file details.
* Set destination.
* Enable checksum verification and overwrite option (if needed).
* Click `Start Restore`.

### ⚙️ Settings Tab

* Enable **Scheduled Backups** and select frequency.
* Set **Backup Retention** options.
* Enable or disable **Notifications**.
* Click `Save Settings`.

### 📜 Logs Tab

* View logs.
* Refresh, clear, or export logs.

---

## 🗃️ Configuration & Logs

* **Config File**: `~/.backup_restore_config.json`

  ```bash
  chmod u+w ~/.backup_restore_config.json
  ```

* **Log File**: `~/backup_logs/backup_restore.log`

  ```bash
  mkdir -p ~/backup_logs
  chmod u+w ~/backup_logs
  ```

---

## 🧯 Troubleshooting

### PyQt5 Not Found

```bash
sudo apt install python3-pyqt5
```

### GUI Not Displaying

* Use a graphical session (XFCE, GNOME, etc.).
* For SSH: `ssh -X user@kali`
* Missing xorg: `sudo apt install xorg`

### Permission Issues

* Ensure backup/log directories are writable.
* Avoid running GUI as root unless absolutely necessary.

### Backup/Restore Fails

* Check `~/backup_logs/backup_restore.log` for errors.
* Confirm backup file integrity.

### Scheduling Problems

* Test with **hourly** frequency.
* Check logs for schedule execution.

---

## 🔐 Security Notes (Kali Linux)

* Avoid backing up sensitive files (e.g., `/etc/shadow`) unless needed.
* Verify backups before restoring.
* Prefer using a **non-root user** for GUI sessions.

---

## 🙌 Contributing

1. **Fork** the repo.
2. Create a new branch:

   ```bash
   git checkout -b feature-name
   ```
3. Commit changes:

   ```bash
   git commit -m "Add feature"
   ```
4. Push changes:

   ```bash
   git push origin feature-name
   ```
5. Submit a **pull request**.

### 💡 Suggested Improvements

* Incremental backup support.
* Password-protected, encrypted backups.
* File/folder exclude filters.
* Dark theme for better visual experience.
* Cancel button for in-progress backups.

---

## 📜 License

Licensed under the **MIT License**. See the `LICENSE` file for more details.

---

## 📬 Contact

For issues, suggestions, or contributions, open an issue or contact the project maintainer.

> Built with ❤️ for Kali Linux users and beyond.

```

---

### ✅ Instructions

- Save this as `README.md` in your project folder.
- Push it to your GitHub repository.
- It will be rendered with proper sections, code blocks, and formatting in the preview.

Let me know if you want this as a downloadable file or want the matching LICENSE template too.
```
