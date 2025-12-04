import sys
import ctypes
import os
import json
import shutil
import time
import urllib.request
from utils import copy_to_steam, restart_steam
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QLineEdit, QFrame,
    QScrollArea, QGridLayout, QMessageBox, QFileDialog, QTextEdit,
    QToolButton, QTableWidget, QTableWidgetItem, QDialog, QDialogButtonBox, QGraphicsDropShadowEffect,
    QHeaderView, QProgressBar, QAbstractItemView
)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QIcon, QPixmap, QFont, QCursor, QDesktopServices, QColor
import warnings

myappid = u'DEGamesLauncher.degameslauncher.v1'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

warnings.filterwarnings("ignore", category=DeprecationWarning)

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
GAMES_DIR = DATA_DIR / "games"
JSON_PATH = DATA_DIR / "data-games.json"
ASSETS_DIR = BASE_DIR / "assets"

DATA_DIR.mkdir(exist_ok=True)
GAMES_DIR.mkdir(exist_ok=True)

if not JSON_PATH.exists():
    with open(JSON_PATH, 'w') as f:
        json.dump([], f)

try:
    with open(JSON_PATH, 'r') as f:
        raw = json.load(f)
        games_data = raw if isinstance(raw, list) else []
except (json.JSONDecodeError, OSError):
    games_data = []


# ==================== Edit Game Dialog ====================
class EditGameDialog(QDialog):
    def __init__(self, parent, game, row_index):
        super().__init__(parent)
        self.setWindowTitle("Edit Game")
        self.game = game
        self.row_index = row_index
        self.original_name = game["name"]
        self.original_folder = game["folder"]
        self.original_thumbnail = game.get("thumbnail", "")
        self.original_desc = game.get("description", "")
        self.new_thumb_path = ""  # hanya diisi jika user upload baru
        self.setModal(True)
        self.resize(500, 400)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                border-radius: 14px;
            }

            QLabel {
                color: #e5e7eb;
                font-weight: 600;
            }

            QLineEdit, QTextEdit {
                background: #020617;
                border: 1px solid #2563eb;
                border-radius: 8px;
                padding: 8px;
                color: white;
            }

            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #3b82f6;
            }

            QPushButton {
                background: #2563eb;
                color: white;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #1d4ed8;
            }

            QPushButton#danger {
                background: #dc2626;
            }

            QPushButton#danger:hover {
                background: #b91c1c;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ===== TITLE =====
        title = QLabel("✏️ Edit Data Game")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; color: #60a5fa;")
        layout.addWidget(title)

        # ===== NAMA GAME =====
        layout.addWidget(QLabel("Nama Game"))
        self.name_edit = QLineEdit(self.original_name)
        layout.addWidget(self.name_edit)

        # ===== FOLDER =====
        layout.addWidget(QLabel("Folder Game"))
        self.folder_label = QLabel(self.original_folder)
        self.folder_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self.folder_label)

        # ===== THUMBNAIL =====
        layout.addWidget(QLabel("Thumbnail"))

        thumb_layout = QHBoxLayout()

        self.current_thumb_label = QLabel()
        self.current_thumb_label.setFixedSize(90, 90)
        self.current_thumb_label.setAlignment(Qt.AlignCenter)
        self.current_thumb_label.setStyleSheet("""
            background: #020617;
            border-radius: 10px;
            border: 2px solid #2563eb;
        """)

        if self.original_thumbnail and os.path.exists(self.original_thumbnail):
            pixmap = QPixmap(self.original_thumbnail).scaled(
                90, 90, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            self.current_thumb_label.setPixmap(pixmap)

        self.change_thumb_btn = QPushButton("Ganti Thumbnail")
        self.change_thumb_btn.clicked.connect(self.select_new_thumbnail)

        thumb_layout.addWidget(self.current_thumb_label)
        thumb_layout.addWidget(self.change_thumb_btn)
        thumb_layout.addStretch()

        layout.addLayout(thumb_layout)

        # ===== DESKRIPSI =====
        layout.addWidget(QLabel("Deskripsi"))
        self.desc_edit = QTextEdit(self.original_desc)
        self.desc_edit.setMaximumHeight(110)
        layout.addWidget(self.desc_edit)

        # ===== TOMBOL BAWAH =====
        btn_layout = QHBoxLayout()

        cancel_btn = QPushButton("Batal")
        cancel_btn.setObjectName("danger")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Simpan")
        save_btn.clicked.connect(self.validate_and_accept)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)


    def select_new_thumbnail(self):
        file, _ = QFileDialog.getOpenFileName(self, "Pilih Thumbnail Baru", "", "Image Files (*.png *.jpg *.jpeg)")
        if file:
            self.new_thumb_path = file
            # Update preview
            pixmap = QPixmap(file).scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.current_thumb_label.setPixmap(pixmap)

    def validate_and_accept(self):
        new_name = self.name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Error", "Nama game tidak boleh kosong!")
            return

        # Deteksi perubahan
        name_changed = (new_name != self.original_name)
        desc_changed = (self.desc_edit.toPlainText() != self.original_desc)
        thumb_changed = (self.new_thumb_path != "")

        if not (name_changed or desc_changed or thumb_changed):
            # Tidak ada perubahan → tutup saja
            self.reject()
            return

        global games_data

        # 1. Rename folder jika nama berubah
        if name_changed:
            old_folder = Path(self.original_folder)
            new_folder = GAMES_DIR / new_name
            if old_folder.exists():
                try:
                    old_folder.rename(new_folder)
                    games_data[self.row_index]["folder"] = str(new_folder)
                    games_data[self.row_index]["name"] = new_name
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Gagal rename folder:\n{str(e)}")
                    return
            else:
                games_data[self.row_index]["name"] = new_name
                # Folder tidak ada → biarkan saja (mungkin sudah dihapus manual)

        # 2. Ganti thumbnail jika ada yang baru
        if thumb_changed:
            ext = Path(self.new_thumb_path).suffix
            new_thumb_name = f"thumbnail{ext}"
            new_thumb_dest = Path(games_data[self.row_index]["folder"]) / new_thumb_name
            try:
                shutil.copy2(self.new_thumb_path, new_thumb_dest)
                games_data[self.row_index]["thumbnail"] = str(new_thumb_dest)
            except Exception as e:
                QMessageBox.warning(self, "Peringatan", f"Gagal mengganti thumbnail:\n{str(e)}")

        # 3. Perbarui deskripsi
        if desc_changed:
            games_data[self.row_index]["description"] = self.desc_edit.toPlainText()

        # Simpan ke JSON
        try:
            with open(JSON_PATH, 'w') as f:
                json.dump(games_data, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal menyimpan data:\n{str(e)}")
            return

        self.accept()

    def accept(self):
        global games_data
        new_name = self.name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Error", "Nama game tidak boleh kosong!")
            return

        old_name = games_data[self.row_index]["name"]
        old_folder = Path(games_data[self.row_index]["folder"])

        if new_name != old_name:
            new_folder = GAMES_DIR / new_name
            if old_folder.exists():
                try:
                    old_folder.rename(new_folder)
                    games_data[self.row_index]["folder"] = str(new_folder)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Gagal rename folder:\n{str(e)}")
                    return
            games_data[self.row_index]["name"] = new_name

        games_data[self.row_index]["description"] = self.desc_edit.toPlainText()

        with open(JSON_PATH, 'w') as f:
            json.dump(games_data, f, indent=2)

        super().accept()


# ==================== Login Window (Modern Card Style) ====================
class LoginWindow(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.setObjectName("loginPage") 
        self.parent = parent
        self.init_ui()

    def init_ui(self):

        # ====== CARD LOGIN ======
        card = QFrame()
        card.setFixedWidth(360)
        card.setStyleSheet("""
            QFrame {
                background: #0d0d0d;
                border-radius: 16px;
               
            }
        """)

        # ====== SHADOW BIRU GLOW ======
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(45)     # besar cahaya
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(QColor(0, 170, 255))  # ✅ BIRU NEON

        card.setGraphicsEffect(shadow)

        # ====== LAYOUT ISIAN CARD ======
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(20)

        # ====== HEADER ======
        title = QLabel("LOGIN DIBUTUHKAN")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            letter-spacing: 2px;
            color: #00f2ea;
        """)

        subtitle = QLabel("ADMIN ACCESS ONLY")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            font-size: 10px;
            color: #a855f7;
            letter-spacing: 2px;
        """)

        # ====== INPUT USERNAME ======
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("USERNAME")
        self.user_edit.setFixedHeight(42)
        self.user_edit.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                border-bottom: 2px solid rgba(0, 242, 234, 0.3);
                color: white;
                padding: 8px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-bottom: 2px solid #00f2ea;
            }
        """)

        # ====== INPUT PASSWORD ======
        self.pass_edit = QLineEdit()
        self.pass_edit.setPlaceholderText("ACCESS KEY")
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.pass_edit.setFixedHeight(42)
        self.pass_edit.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                border-bottom: 2px solid rgba(0, 242, 234, 0.3);
                color: white;
                padding: 8px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-bottom: 2px solid #00f2ea;
            }
        """)

        # ====== BUTTON LOGIN ======
        login_btn = QPushButton("INITIATE CONNECTION")
        login_btn.setFixedHeight(42)
        login_btn.clicked.connect(self.check_login)
        login_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 2px solid #00f2ea;
                color: #00f2ea;
                font-weight: bold;
                letter-spacing: 2px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: #00f2ea;
                color: #000;
                box-shadow: 0 0 20px #00f2ea;
            }
            QPushButton:pressed {
                background: #00cfc8;
            }
        """)

        # ====== SUSUN KE CARD ======
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(10)
        card_layout.addWidget(self.user_edit)
        card_layout.addWidget(self.pass_edit)
        card_layout.addSpacing(10)
        card_layout.addWidget(login_btn)
        
        main_layout = QHBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # ====== WRAPPER VERTICAL (AGAR LINK DI BAWAH FORM) ======
        wrapper = QVBoxLayout()
        wrapper.setAlignment(Qt.AlignCenter)

        wrapper.addWidget(card)

        # === LINK UPDATE DI BAWAH FORM LOGIN ===
        update_label = QLabel('<a href="https://github.com/debotz-bot/apply_to_steam">🔗 New Update Check Github</a>')
        update_label.setAlignment(Qt.AlignCenter)
        update_label.setOpenExternalLinks(True)
        update_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 17px;
                margin-top: 20px;
                text-decoration: none;

            }
            QLabel:hover {
                color: #a855f7;
                text-decoration: none;

            }
        """)

        wrapper.addWidget(update_label)

        # Masukkan wrapper ke layout utama
        main_layout.addLayout(wrapper)



    # ================= LOGIN LOGIC =================
    def check_login(self):
        if self.user_edit.text() == "qq" and self.pass_edit.text() == "12":
            self.parent.show_admin()
        else:
            QMessageBox.warning(self, "ACCESS DENIED", "Username atau password salah!")



# ==================== Admin Window ====================
class AdminWindow(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.folder_path = ""
        self.thumb_path = ""
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("🛠️ Panel Admin")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #bb86fc;")
        home_btn = QPushButton("🏠 Home")
        home_btn.clicked.connect(self.go_to_home)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(home_btn)
        main_layout.addLayout(header_layout)

        # Form
        form_layout = QGridLayout()
        form_layout.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nama Game")
        self.folder_btn = QPushButton("📁 Pilih Folder Game")
        self.folder_btn.clicked.connect(self.select_folder)
        self.thumb_btn = QPushButton("🖼️ Upload Thumbnail")
        self.thumb_btn.clicked.connect(self.select_thumbnail)
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("Deskripsi game...")
        self.desc_edit.setMaximumHeight(80)
        save_btn = QPushButton("💾 Simpan Game")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.save_game)

        form_layout.addWidget(QLabel("Nama Game:"), 0, 0)
        form_layout.addWidget(self.name_edit, 0, 1)
        form_layout.addWidget(QLabel("Folder Game:"), 1, 0)
        form_layout.addWidget(self.folder_btn, 1, 1)
        form_layout.addWidget(QLabel("Thumbnail:"), 2, 0)
        form_layout.addWidget(self.thumb_btn, 2, 1)
        form_layout.addWidget(QLabel("Deskripsi:"), 3, 0)
        form_layout.addWidget(self.desc_edit, 3, 1)
        form_layout.addWidget(save_btn, 4, 1, Qt.AlignRight)

        # Table
        table_label = QLabel("📋 Daftar Game yang Tersimpan")
        table_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        table_label.setStyleSheet("color: #03dac6;")

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["No", "Nama Game", "Deskripsi", "Aksi"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(table_label)
        main_layout.addWidget(self.table)
        self.setLayout(main_layout)
        self.load_game_table()

    def go_to_home(self):
        self.parent.stack.setCurrentWidget(self.parent.home)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder Game")
        if folder:
            self.folder_path = folder
            self.folder_btn.setText(f"📁 {os.path.basename(folder)}")

    def select_thumbnail(self):
        file, _ = QFileDialog.getOpenFileName(self, "Pilih Thumbnail", "", "Image Files (*.png *.jpg *.jpeg)")
        if file:
            self.thumb_path = file
            self.thumb_btn.setText(f"🖼️ {os.path.basename(file)}")

    def save_game(self):
        name = self.name_edit.text().strip()
        if not name or not self.folder_path:
            QMessageBox.warning(self, "Error", "Nama game dan folder wajib diisi!")
            return

        game_folder = GAMES_DIR / name
        game_folder.mkdir(exist_ok=True)

        for item in Path(self.folder_path).iterdir():
            if item.is_file():
                shutil.copy2(item, game_folder / item.name)
            else:
                shutil.copytree(item, game_folder / item.name, dirs_exist_ok=True)

        thumb_dest = ""
        if self.thumb_path:
            ext = Path(self.thumb_path).suffix
            thumb_dest = str(game_folder / f"thumbnail{ext}")
            shutil.copy2(self.thumb_path, thumb_dest)

        global games_data
        games_data.append({
            "name": name,
            "folder": str(game_folder),
            "thumbnail": thumb_dest,
            "description": self.desc_edit.toPlainText() or "Tidak ada deskripsi."
        })

        with open(JSON_PATH, 'w') as f:
            json.dump(games_data, f, indent=2)

        msg = QMessageBox(self)
        msg.setWindowTitle("✅ Berhasil")
        msg.setText("🎮 Game berhasil ditambahkan!")
        msg.setInformativeText("Game sekarang sudah tersedia di halaman Home.")
        msg.setIcon(QMessageBox.Information)

        msg.setStyleSheet("""
        QMessageBox {
            background-color: #020617;
            color: #e5e7eb;
            font-size: 11pt;
        }

        QLabel {
            color: #e5e7eb;
        }

        QPushButton {
            background-color: #3b82f6;
            color: white;
            border-radius: 10px;
            padding: 8px 18px;
            font-weight: bold;
        }

        QPushButton:hover {
            background-color: #2563eb;
        }

        QPushButton:pressed {
            background-color: #1d4ed8;
        }
        """)

        msg.exec_()

        self.clear_form()
        self.load_game_table()
        self.parent.refresh_home()

    def clear_form(self):
        self.name_edit.clear()
        self.folder_path = ""
        self.thumb_path = ""
        self.folder_btn.setText("📁 Pilih Folder Game")
        self.thumb_btn.setText("🖼️ Upload Thumbnail")
        self.desc_edit.clear()

    def load_game_table(self):
        global games_data

        self.table.setRowCount(len(games_data))
        self.table.setObjectName("adminGameTable")
        self.table.setAlternatingRowColors(True)  # ✅ biar lebih rapi
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.horizontalHeader().setStretchLastSection(True)

        for row, game in enumerate(games_data):
            if not isinstance(game, dict):
                continue

            self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.table.setItem(row, 1, QTableWidgetItem(game.get("name", "")))

            desc = game.get("description", "")[:60] + "..." if len(game.get("description", "")) > 60 else game.get("description", "")
            self.table.setItem(row, 2, QTableWidgetItem(desc))

            action_widget = QWidget()
            action_layout = QHBoxLayout()
            action_layout.setContentsMargins(6, 0, 6, 10)
            action_layout.setSpacing(6)


            edit_btn = QPushButton("Edit ✏️")
            edit_btn.setFixedSize(100, 28)
            edit_btn.setStyleSheet("""
                QPushButton {
                    background: #2563eb;
                    color: white;
                    border-radius: 6px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #1d4ed8;
                }
            """)
            edit_btn.clicked.connect(lambda _, r=row: self.edit_game(r))


            delete_btn = QPushButton("Hapus 🗑️")
            delete_btn.setFixedSize(100, 28)
            delete_btn.setStyleSheet("""
                QPushButton {
                    background: #dc2626;
                    color: white;
                    border-radius: 6px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #b91c1c;
                }
            """)
            delete_btn.clicked.connect(lambda _, r=row: self.delete_game(r))


            action_layout.addWidget(edit_btn)
            action_layout.addWidget(delete_btn)
            action_layout.addStretch()
            action_widget.setLayout(action_layout)
            self.table.setCellWidget(row, 3, action_widget)

    def edit_game(self, row):
        global games_data
        game = games_data[row]
        dialog = EditGameDialog(self, game, row)
        if dialog.exec_() == QDialog.Accepted:
            self.load_game_table()
            self.parent.refresh_home()

    def delete_game(self, row):
        global games_data
        game = games_data[row]
        reply = QMessageBox.question(
            self, "Konfirmasi Hapus",
            f"Yakin ingin menghapus game '{game['name']}'?\nIni akan menghapus folder game dan data.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            folder_path = Path(game["folder"])
            if folder_path.exists():
                shutil.rmtree(folder_path)

            games_data.pop(row)
            with open(JSON_PATH, 'w') as f:
                json.dump(games_data, f, indent=2)

            QMessageBox.information(self, "Sukses", "Game berhasil dihapus!")
            self.load_game_table()
            self.parent.refresh_home()

# ==================== Download Worker ====================
class DownloadWorker(QThread):
    progress = pyqtSignal(int, int, float)  # downloaded, total, speed (KB/s)
    finished = pyqtSignal(str)  # path file hasil download
    error = pyqtSignal(str)

    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self._canceled = False

    def cancel(self):
        self._canceled = True

    def run(self):
        try:
            def reporthook(block_num, block_size, total_size):
                if self._canceled:
                    raise Exception("Download dibatalkan")
                downloaded = block_num * block_size
                if total_size > 0:
                    percent = min(100, int(downloaded * 100 / total_size))
                    speed = downloaded / (1024 * (time.time() - self.start_time + 0.001))
                    self.progress.emit(downloaded, total_size, speed)
                return not self._canceled

            import time
            self.start_time = time.time()
            urllib.request.urlretrieve(self.url, self.save_path, reporthook)
            if not self._canceled:
                self.finished.emit(self.save_path)
        except Exception as e:
            self.error.emit(str(e))

# ==================== Game Card (Tailwind Style) ====================
class GameCard(QFrame):
    def __init__(self, game_info):
        super().__init__()
        self.game = game_info
        self.setObjectName("gameCard")
        self.setFixedSize(260, 340)

        # CARD STYLE (PUTIH + SHADOW)
        self.setStyleSheet("""
        QFrame#gameCard {
            background: #ffffff;
            border-radius: 20px;
            border: none;
        }
        QFrame#gameCard:hover {
            background: #f5f7ff;
        }
        """)

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ================= THUMBNAIL PERSEGI TENGAH =================
        thumb_size = 200  # ukuran kotak persegi

        # Wrapper luar (untuk center)
        thumb_container = QWidget()
        thumb_container_layout = QHBoxLayout()
        thumb_container_layout.setContentsMargins(0, 10, 0, 0)
        thumb_container_layout.setAlignment(Qt.AlignCenter)

        thumb_wrapper = QFrame()
        thumb_wrapper.setFixedSize(thumb_size, thumb_size)
        thumb_wrapper.setStyleSheet("""
            QFrame {
                border-radius: 12px;
                background: #e5e7eb;
            }
        """)

        thumb_label = QLabel(thumb_wrapper)
        thumb_label.setFixedSize(thumb_size, thumb_size)
        thumb_label.setAlignment(Qt.AlignCenter)

        if self.game.get("thumbnail") and os.path.exists(self.game["thumbnail"]):
            pixmap = QPixmap(self.game["thumbnail"]).scaled(
                thumb_size, thumb_size,
                Qt.IgnoreAspectRatio,   # FULL TERISI
                Qt.SmoothTransformation
            )
            thumb_label.setPixmap(pixmap)
        else:
            thumb_label.setText("No Image")
            thumb_label.setStyleSheet("color: #64748b;")

        thumb_container_layout.addWidget(thumb_wrapper)
        thumb_container.setLayout(thumb_container_layout)



        # ================= BODY =================
        body = QFrame()
        body_layout = QVBoxLayout()
        body_layout.setContentsMargins(20, 20, 20, 12)
        body_layout.setSpacing(8)

        # JUDUL
        full_name = self.game["name"]
        name_label = QLabel(full_name)
        name_label.setWordWrap(True)
        name_label.setToolTip(full_name)
        name_label.setStyleSheet("""
            font-size: 19px;
            font-weight: 700;
            color: #0f172a;
            qproperty-alignment: AlignCenter;
        """)

       # ================= DESKRIPSI 1 BARIS + ICON INFO =================
        full_desc = self.game.get("description", "Tidak ada deskripsi.")

        # Deskripsi dipaksa 1 baris saja
        desc_label = QLabel(full_desc)
        desc_label.setFixedHeight(20)
        desc_label.setWordWrap(False)
        desc_label.setStyleSheet("""
            font-size: 14px;
            color: #475569;
        """)

        # Potong otomatis jika kepanjangan
        metrics = desc_label.fontMetrics()
        elided_text = metrics.elidedText(full_desc, Qt.ElideRight, 170)
        desc_label.setText(elided_text)

        # ================= ICON INFO =================
        # ================= ICON INFO PREMIUM =================
        info_btn = QToolButton()
        info_btn.setText("ⓘ")
        info_btn.setCursor(QCursor(Qt.PointingHandCursor))
        info_btn.setMouseTracking(True)
        info_btn.setFixedSize(18, 18)
        info_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                font-size: 14px;
                color: #64748b;
            }
            QToolButton:hover {
                color: #3b82f6;
            }
        """)

        from PyQt5.QtWidgets import QToolTip
        from PyQt5.QtCore import QPoint

        # ✅ TOOLTIP PREMIUM (HTML + WRAP + JUDUL)
        def show_premium_tooltip(e):
            html = f"""
            <div style="
                max-width: 300px;
                font-size: 11pt;
                line-height: 1.4;
            ">
                <div style="
                    font-weight: bold;
                    color: #60a5fa;
                    margin-bottom: 6px;
                ">
                    📄 Deskripsi Game
                </div>

                <div style="
                    color: #64748b;
                ">
                    {full_desc}
                </div>
            </div>
            """

            QToolTip.showText(
                info_btn.mapToGlobal(info_btn.rect().bottomLeft() + QPoint(0, 6)),
                html
            )

        info_btn.enterEvent = show_premium_tooltip



        # ================= WRAPPER DESKRIPSI =================
        desc_layout = QHBoxLayout()
        desc_layout.setContentsMargins(0, 0, 0, 0)
        desc_layout.setSpacing(6)
        desc_layout.addWidget(desc_label)
        desc_layout.addWidget(info_btn)
        desc_layout.addStretch()


        # ================= FOOTER BUTTON =================
        self.add_btn = QPushButton("Add to Steam")
        self.add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.add_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border-radius: 10px;
                padding: 10px;
                font-size: 15px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
            QPushButton:pressed {
                background: #1d4ed8;
            }
        """)
        self.add_btn.clicked.connect(self.add_to_steam)

        body_layout.addWidget(name_label)
        body_layout.addLayout(desc_layout)
        body_layout.addStretch()
        body_layout.addWidget(self.add_btn)

        body.setLayout(body_layout)

        # ================= FINAL COMPOSE =================
        main_layout.addSpacing(20)
        main_layout.addWidget(thumb_container)
        main_layout.addWidget(body)

        self.setLayout(main_layout)

    def add_to_steam(self):
        success = copy_to_steam(self.game["folder"])

        # ===================== POPUP KONFIRMASI PREMIUM =====================
        if success:
            confirm = QMessageBox(self)
            confirm.setWindowTitle("🔄 Restart Steam?")
            confirm.setText("✅ File berhasil ditambahkan!")
            confirm.setInformativeText("Apakah Steam ingin direstart sekarang?")
            confirm.setIcon(QMessageBox.Question)
            confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

            confirm.setStyleSheet("""
            QMessageBox {
                background-color: #020617;
                color: #e5e7eb;
                font-size: 11pt;
            }

            QLabel {
                color: #e5e7eb;
            }

            QPushButton {
                background-color: #3b82f6;
                color: white;
                border-radius: 10px;
                padding: 8px 18px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #2563eb;
            }

            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            """)

            reply = confirm.exec_()

            # ===================== JIKA USER SETUJU =====================
            if reply == QMessageBox.Yes:
                if restart_steam():

                    msg = QMessageBox(self)
                    msg.setWindowTitle("🚀 Berhasil")
                    msg.setText("Steam berhasil direstart!")
                    msg.setIcon(QMessageBox.Information)

                    msg.setStyleSheet("""
                    QMessageBox {
                        background-color: #020617;
                        color: #e5e7eb;
                        font-size: 11pt;
                    }

                    QLabel {
                        color: #00f2ea;
                    }

                    QPushButton {
                        background-color: #00f2ea;
                        color: black;
                        border-radius: 10px;
                        padding: 8px 18px;
                        font-weight: bold;
                    }
                    """)
                    msg.exec_()

                else:
                    err = QMessageBox(self)
                    err.setWindowTitle("❌ Gagal")
                    err.setText("Gagal merestart Steam.")
                    err.setIcon(QMessageBox.Critical)

                    err.setStyleSheet("""
                    QMessageBox {
                        background-color: #020617;
                        color: #e5e7eb;
                        font-size: 11pt;
                    }

                    QLabel {
                        color: #f87171;
                    }

                    QPushButton {
                        background-color: #dc2626;
                        color: white;
                        border-radius: 10px;
                        padding: 8px 18px;
                        font-weight: bold;
                    }
                    """)
                    err.exec_()

        # ===================== JIKA COPY GAGAL =====================
        else:
            fail = QMessageBox(self)
            fail.setWindowTitle("❌ Gagal")
            fail.setText("Gagal menambahkan file ke direktori Steam.")
            fail.setIcon(QMessageBox.Critical)

            fail.setStyleSheet("""
            QMessageBox {
                background-color: #020617;
                color: #e5e7eb;
                font-size: 11pt;
            }

            QLabel {
                color: #f87171;
            }

            QPushButton {
                background-color: #dc2626;
                color: white;
                border-radius: 10px;
                padding: 8px 18px;
                font-weight: bold;
            }
            """)
            fail.exec_()



# ==================== Home Window ====================
class HomeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.no_game_label = QLabel("🔍 Game tidak tersedia")
        self.no_game_label.setAlignment(Qt.AlignCenter)
        self.no_game_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.no_game_label.setStyleSheet("color: #ff6b6b; margin-top: 40px;")
        self.no_game_label.setVisible(False)

        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(25)
        self.cards_layout.setContentsMargins(20, 10, 20, 20)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        content = QWidget()
        content.setLayout(self.cards_layout)
        scroll.setWidget(content)


        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.no_game_label)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)
        self.refresh_cards(games_data)

    def refresh_cards(self, game_list):
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not game_list:
            self.no_game_label.setVisible(True)
            return
        else:
            self.no_game_label.setVisible(False)

        row, col = 0, 0
        for game in game_list:
            if not isinstance(game, dict):
                continue
            card = GameCard(game)
            self.cards_layout.addWidget(card, row, col)
            col += 1
            if col == 4:
                col = 0
                row += 1


# ==================== Main Window ====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DEGamesLauncher v1.0")

        if (ASSETS_DIR / "DEGamesLauncher.ico").exists():
            self.setWindowIcon(QIcon(str(ASSETS_DIR / "DEGamesLauncher.ico")))

        self.setGeometry(100, 100, 1100, 750)

        # ==================== TOP BAR ====================
        top_bar = QWidget()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(70)
        top_bar.setStyleSheet("""
            QWidget#topBar {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0f172a,
                    stop:1 #1e293b
                );
            }
        """)
        top_bar.setAutoFillBackground(True)


        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(30, 0, 30, 0)
        top_layout.setSpacing(20)

        # ================= LOGO + JUDUL =================
        title_layout = QHBoxLayout()
        title_layout.setSpacing(12)

        logo_path = ASSETS_DIR / "DEGamesLauncher.png"
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(logo_path)).scaled(
                42, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            logo_label.setPixmap(pixmap)
            logo_label.setFixedSize(42, 42)
        else:
            logo_label = QLabel("🎮")
            logo_label.setFont(QFont("Segoe UI", 22))
            logo_label.setFixedSize(42, 42)
            logo_label.setAlignment(Qt.AlignCenter)

        title_label = QLabel("DEGamesLauncher")
        title_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title_label.setStyleSheet("""
            color: #ffffff;
            letter-spacing: 1px;
            font-size: 26px;
        """)

        title_layout.addWidget(logo_label)
        title_layout.addWidget(title_label)

        # ================= SEARCH BAR =================
        self.main_search = QLineEdit()
        self.main_search.setPlaceholderText("🔍 Cari game...")
        self.main_search.setMinimumWidth(360)
        self.main_search.setFixedHeight(38)
        self.main_search.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.08);
                border: 1px solid #3b82f6;
                border-radius: 10px;
                padding-left: 14px;
                padding-right: 14px;
                color: white;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #60a5fa;
                background: rgba(255,255,255,0.12);
            }
        """)
        self.main_search.textChanged.connect(self.on_search)

        # ================= FINAL COMPOSE =================
        top_layout.addLayout(title_layout)
        top_layout.addStretch()
        top_layout.addWidget(self.main_search)

        top_bar.setLayout(top_layout)


        # ==================== SIDEBAR MODERN ====================
        sidebar = QWidget()
        sidebar.setFixedWidth(80)


        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        sidebar_layout.setSpacing(18)

        # ========== ICON STYLE BASE ==========
        btn_style = """
        QToolButton {
            font-size: 26px;
            color: #94a3b8;
            background: transparent;
            border: none;
            border-radius: 14px;
            padding: 12px;
        }
        QToolButton:hover {
            background: rgba(59,130,246,0.2);
            color: #ffffff;
        }
        QToolButton:checked {
            background: rgba(59,130,246,0.35);
            color: #3b82f6;
        }
        """

        # ================== HOME ==================
        home_btn = QToolButton()
        home_btn.setText("🏠")
        home_btn.setCheckable(True)
        home_btn.setChecked(True)
        home_btn.setStyleSheet(btn_style)
        home_btn.setCursor(QCursor(Qt.PointingHandCursor))
        home_btn.clicked.connect(self.go_to_home_main)

        # ================== BYPASS ==================
        bypass_btn = QToolButton()
        bypass_btn.setText("⚡")
        bypass_btn.setCheckable(True)
        bypass_btn.setStyleSheet(btn_style)
        bypass_btn.setCursor(QCursor(Qt.PointingHandCursor))
        bypass_btn.clicked.connect(self.start_bypass_download)

        # ================== DONATE ==================
        donate_btn = QToolButton()
        donate_btn.setText("💖")
        donate_btn.setCheckable(False)
        donate_btn.setToolTip("Support Developer via Saweria")
        donate_btn.setStyleSheet(btn_style)
        donate_btn.setCursor(QCursor(Qt.PointingHandCursor))
        donate_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://saweria.co/DEGamesLauncher")
            )
        )
        # ================== GITHUB ==================
        github_btn = QToolButton()
        github_btn.setText("🤖")  # ikon github
        github_btn.setCheckable(False)
        github_btn.setToolTip("Buka Repository GitHub")
        github_btn.setStyleSheet(btn_style)
        github_btn.setCursor(QCursor(Qt.PointingHandCursor))
        github_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/USERNAME/REPO")  # GANTI DENGAN URL GITHUB KAMU
            )
        )
        # ================== SETTINGS / LOGIN ==================
        settings_btn = QToolButton()
        settings_btn.setText("⚙️")
        settings_btn.setCheckable(True)
        settings_btn.setStyleSheet(btn_style)
        settings_btn.setCursor(QCursor(Qt.PointingHandCursor))
        settings_btn.clicked.connect(self.show_login)


        # ================== AUTO TOGGLE ACTIVE ==================
        def set_active(btn):
            home_btn.setChecked(False)
            bypass_btn.setChecked(False)
            settings_btn.setChecked(False)
            btn.setChecked(True)

        home_btn.clicked.connect(lambda: set_active(home_btn))
        bypass_btn.clicked.connect(lambda: set_active(bypass_btn))
        settings_btn.clicked.connect(lambda: set_active(settings_btn))

        # ================== SUSUN LAYOUT ==================
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(home_btn, alignment=Qt.AlignHCenter)
        sidebar_layout.addWidget(bypass_btn, alignment=Qt.AlignHCenter)
        sidebar_layout.addWidget(donate_btn, alignment=Qt.AlignHCenter)   # ✅ DONATE DI TENGAH
        sidebar_layout.addWidget(github_btn, alignment=Qt.AlignHCenter)
        sidebar_layout.addWidget(settings_btn, alignment=Qt.AlignHCenter)
        sidebar_layout.addStretch()

        sidebar.setLayout(sidebar_layout)


        # Stack
        self.stack = QStackedWidget()
        self.home = HomeWindow()
        self.home.setObjectName("homePage")
        self.login = LoginWindow(self)
        self.login.setObjectName("loginPage")
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.login)

        main_layout = QHBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack)

        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(top_bar)
        container_layout.addLayout(main_layout)
        container.setLayout(container_layout)

        self.setCentralWidget(container)

        # Load stylesheet
        qss_path = BASE_DIR / "styles.qss"
        if qss_path.exists():
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())

    def on_search(self, text):
        if isinstance(self.stack.currentWidget(), HomeWindow):
            filtered = [
                game for game in games_data
                if isinstance(game, dict) and text.lower() in game.get("name", "").lower()
            ]
            self.stack.currentWidget().refresh_cards(filtered)

    def show_login(self):
        self.stack.setCurrentWidget(self.login)

    def start_bypass_download(self):
        url = "https://github.com/LightnigFast/Project-Lightning/releases/download/v4.0.0.0/ProjectLightningInstaller.exe"
        
        # ✅ Minta user pilih folder tujuan
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Pilih Folder Tujuan untuk Installer", 
            str(Path.home() / "Downloads")  # default ke folder Downloads
        )
        if not folder:
            # User batalkan pemilihan folder
            return

        save_path = Path(folder) / "ProjectLightningInstaller.exe"

        # Cek jika file sudah ada
        if save_path.exists():
            reply = QMessageBox.question(
                self, 
                "File Sudah Ada", 
                f"File sudah ada di:\n{save_path}\n\nTimpa file ini?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                self.show_download_complete(str(save_path))
                return

        # Buat dialog download
        self.download_dialog = QDialog(self)
        self.download_dialog.setWindowTitle("📥 Mengunduh Project Lightning")
        self.download_dialog.setFixedSize(400, 180)
        self.download_dialog.setModal(True)

        layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.status_label = QLabel("Memulai unduhan...")
        self.speed_label = QLabel("Kecepatan: -")
        self.open_folder_btn = QPushButton("Buka Folder")
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(save_path.parent))))

        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.cancel_download)

        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.speed_label)
        layout.addWidget(self.open_folder_btn)
        layout.addWidget(cancel_btn)
        self.download_dialog.setLayout(layout)

        # Mulai download
        self.worker = DownloadWorker(url, str(save_path))
        self.worker.progress.connect(self.update_download_progress)
        self.worker.finished.connect(lambda path: self.on_download_finished(path, str(save_path.parent)))
        self.worker.error.connect(self.on_download_error)
        self.worker.start()

        self.download_dialog.exec_()

    def update_download_progress(self, downloaded, total, speed):
        percent = int(downloaded * 100 / total) if total > 0 else 0
        self.progress_bar.setValue(percent)
        self.progress_bar.setMaximum(100)
        self.status_label.setText(f"Mengunduh... {self.format_bytes(downloaded)} / {self.format_bytes(total)}")
        self.speed_label.setText(f"Kecepatan: {speed:.1f} KB/s")

    def on_download_finished(self, file_path, folder_path):
        self.worker.quit()
        self.download_dialog.accept()
        self.show_download_complete(file_path, folder_path)

    def on_download_error(self, error_msg):
        self.worker.quit()
        self.download_dialog.accept()
        QMessageBox.critical(self, "Error Download", f"Gagal mengunduh:\n{error_msg}")

    def cancel_download(self):
        if hasattr(self, 'worker'):
            self.worker.cancel()
        self.download_dialog.accept()

    def show_download_complete(self, file_path, folder_path):
        msg = QMessageBox(self)
        msg.setWindowTitle("✅ Unduhan Selesai")
        msg.setText("Project Lightning berhasil diunduh!")
        msg.setInformativeText(f"File disimpan di:\n{file_path}")
        msg.addButton("Buka Folder", QMessageBox.ActionRole)
        open_btn = msg.addButton("Jalankan Installer", QMessageBox.ActionRole)
        msg.addButton(QMessageBox.Ok)

        ret = msg.exec_()
        if msg.clickedButton() == open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        elif ret == QMessageBox.ActionRole:  # "Buka Folder"
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))

    def format_bytes(self, bytes):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} TB"
    
    def show_admin(self):
        if not hasattr(self, 'admin'):
            self.admin = AdminWindow(self)
            self.admin.setObjectName("adminPage")
        self.stack.addWidget(self.admin)
        self.stack.setCurrentWidget(self.admin)

    def go_to_home_main(self):
        """Kembali ke halaman utama dari mana saja"""
        self.stack.setCurrentWidget(self.home)

    def refresh_home(self):
        global games_data
        with open(JSON_PATH, 'r') as f:
            games_data = json.load(f)
        self.home.refresh_cards(games_data)
        self.stack.setCurrentWidget(self.home)


# ==================== Main ====================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())