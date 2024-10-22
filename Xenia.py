import io
import os
import sys
import subprocess
import requests
import zipfile
import json
import shutil
import logging
import time
import threading
import pyautogui
import qtawesome as qta
from PyQt5.QtWidgets import (QApplication, QMainWindow, QMessageBox, QInputDialog,
                             QLabel, QVBoxLayout, QPushButton, QWidget, QFileDialog, QGridLayout,
                             QProgressBar, QGroupBox)
from PyQt5.QtGui import QPixmap, QPalette, QBrush, QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    return os.path.join(base_path, relative_path)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("Starting the application")

# Constants
BASE_DIR = resource_path('.')
SAVE_DATA_DIR = resource_path('SaveData')
CORE_DIR = resource_path('Core')
CONFIG_FILE = resource_path('games_config.json')
EXAMPLE_FOLDER = resource_path('Resources')
TOML_CONFIG_FILE = 'xenia-canary.config.toml'
DEFAULT_CONFIG_FILE = resource_path('defaultconfig.toml')
IMAGES_DIR = resource_path('images')
MAIN_MENU_IMAGE = "main_menu_background.jpg"

class CopyThread(QThread):
    progress = pyqtSignal(int)
    update_text = pyqtSignal(str)

    def __init__(self, src, dst, parent=None):
        super().__init__(parent)
        self.src = src
        self.dst = dst  # Properly assign self.dst

    def run(self):
        total_files = sum([len(files) for r, d, files in os.walk(self.src)])
        copied_files = 0

        for root, dirs, files in os.walk(self.src):
            for file in files:
                src_file = os.path.join(root, file)
                dst_file = os.path.join(self.dst, os.path.relpath(src_file, self.src))
                dst_dir = os.path.dirname(dst_file)
                if not os.path.exists(dst_dir):
                    os.makedirs(dst_dir)
                shutil.copy2(src_file, dst_file)
                copied_files += 1
                progress_percent = int((copied_files / total_files) * 100)
                self.progress.emit(progress_percent)
                self.update_text.emit(f"Save Data Transfer Complete: {copied_files}/{total_files} files.")

class HeaderWidget(QWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.initUI()

    def initUI(self):
        self.setFixedHeight(200)  # Set the height of the header
        self.update_palette()

    def update_palette(self):
        palette = QPalette()
        pixmap = QPixmap(self.image_path)
        scaled_pixmap = pixmap.scaled(self.width(), self.height(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        palette.setBrush(QPalette.Window, QBrush(scaled_pixmap))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

    def resizeEvent(self, event):
        self.update_palette()

class GameItemWidget(QWidget):
    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        buttons = [
            ("Launch", "fa.play", self.launch_game),
            ("Edit Config", "fa.edit", self.edit_config),
            ("Remove", "fa.trash", self.remove_game),
            ("Open Folder", "fa.folder-open-o", self.open_folder)
        ]
        for text, icon, func in buttons:
            button = QPushButton(text, self)
            button.setIcon(qta.icon(icon))
            button.clicked.connect(func)
            layout.addWidget(button)
        self.setLayout(layout)

    def launch_game(self):
        self.parent().launch_game(self.game['path'])

    def edit_config(self):
        self.parent().edit_config(self.game['path'])

    def remove_game(self):
        self.parent().remove_game(self.game)

    def open_folder(self):
        self.parent().open_folder(self.game['path'])

class XeniaManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xenia Manager V2")
        self.setGeometry(300, 300, 800, 600)  # Increase the window size for better readability
        self.initUI()

    def initUI(self):
        self.show_initial_prompt()
        main_layout = QVBoxLayout()
        header = HeaderWidget(resource_path(os.path.join('images', MAIN_MENU_IMAGE)), self)
        main_layout.addWidget(header)

        layout = QGridLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        font = QFont("Arial", 12)

        self.label = QLabel("Main Menu", self)
        self.label.setFont(font)
        layout.addWidget(self.label, 0, 0, 1, 2)

        # Simplified main menu with fewer options
        main_buttons = [
            ("Games", "fa.gamepad", self.games_menu),
            ("Launch Xenia", "fa.play", self.launch_xenia_menu),
            ("Edit Config", "fa.edit", self.edit_config_menu),
            ("Help", "fa.question-circle", self.help_menu),
            ("Extra Options", "fa.cogs", self.extra_options),
        ]

        for i, (text, icon, func) in enumerate(main_buttons, start=1):
            button = QPushButton(text, self)
            button.setFont(font)
            button.setIcon(qta.icon(icon))
            button.clicked.connect(func)
            layout.addWidget(button, i, 0, 1, 2)

        # Container and central widget setup
        container = QWidget()
        container.setLayout(layout)
        main_layout.addWidget(container)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def launch_xenia_menu(self):
        self.clear_layout()

        layout = QGridLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        font = QFont("Arial", 12)

        self.label = QLabel("Launch Xenia", self)
        self.label.setFont(font)
        layout.addWidget(self.label, 0, 0, 1, 2)

        launch_buttons = [
            ("Launch Xenia Canary", "fa.play", lambda: self.launch_game("Xenia")),
            ("Launch Xenia Canary with 4K Settings", "fa.play", lambda: self.launch_game("4k\\Xenia")),
            ("Launch Normal Xenia", "fa.play", lambda: self.launch_normal_xenia("NonCanaryXenia")),
            ("Back", "fa.arrow-left", self.initUI)
        ]

        for i, (text, icon, func) in enumerate(launch_buttons, start=1):
            button = QPushButton(text, self)
            button.setFont(font)
            button.setIcon(qta.icon(icon))
            button.clicked.connect(func)
            layout.addWidget(button, i, 0, 1, 2)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def edit_config_menu(self):
        self.clear_layout()

        layout = QGridLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        font = QFont("Arial", 12)

        self.label = QLabel("Edit Config", self)
        self.label.setFont(font)
        layout.addWidget(self.label, 0, 0, 1, 2)

        config_buttons = [
            ("Edit Xenia Config", "fa.edit", lambda: self.edit_config("Xenia")),
            ("Edit 4K Xenia Config", "fa.edit", lambda: self.edit_config("4k\\Xenia")),
            ("Edit Xenia Manager Config", "fa.edit", self.open_games_config),
            ("Back", "fa.arrow-left", self.initUI)
        ]

        for i, (text, icon, func) in enumerate(config_buttons, start=1):
            button = QPushButton(text, self)
            button.setFont(font)
            button.setIcon(qta.icon(icon))
            button.clicked.connect(func)
            layout.addWidget(button, i, 0, 1, 2)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def open_save_data_folder(self):
        self._open_folder(SAVE_DATA_DIR)

    def open_patches_folder(self):
        patches_dir = resource_path('Patches')
        self._open_folder(patches_dir)

    def _open_folder(self, directory):
        if not os.path.isdir(directory):
            os.makedirs(directory)
            QMessageBox.information(self, "Info", f"The folder {directory} has been created.")
        os.startfile(directory)
    
    def open_games_config(self):
        self._open_file(CONFIG_FILE, "Games config file not found!")

    def _open_file(self, file_path, error_message):
        if os.path.isfile(file_path):
            os.startfile(file_path)
            QMessageBox.information(self, "Info", f"Opening file: {file_path}")
        else:
            QMessageBox.warning(self, "Error", error_message)

    def show_initial_prompt(self):
        config = self.load_config()
        if not config.get("prompt_shown", False):
            message = ("Would you like to update Xenia and download patches?\n\n"
                       "Details:\n"
                       "- Update Xenia to the latest version from https://github.com/xenia-canary/xenia-canary.\n"
                       "- Download new game patches from https://github.com/xenia-canary/game-patches.\n"
                       "- This process might take a few minutes depending on your internet connection.")
            reply = QMessageBox.question(self, "Initial Setup", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.update_xenia()
                self.update_patches()
            config["prompt_shown"] = True
            self.save_config(config)

    def toggle_auto_launch(self):
        self._toggle_config_option("auto_launch", "Auto Launch")

    def _toggle_config_option(self, key, option_name):
        config = self.load_config()
        config[key] = not config.get(key, False)
        self.save_config(config)
        QMessageBox.information(self, "Info", f"{option_name} is now {'enabled' if config[key] else 'disabled'}.")

    def set_auto_launch_delay(self):
        self._set_config_value("auto_launch_delay", "Enter the auto-launch delay in seconds:", 5)

    def set_auto_launch_key(self):
        self._set_config_value("auto_launch_key", "Enter the key for auto-launch:", "f9")

    def _set_config_value(self, key, message, default_value):
        config = self.load_config()
        value, ok = QInputDialog.getText(self, "Input", message, text=str(config.get(key, default_value)))
        if ok:
            config[key] = type(default_value)(value)
            self.save_config(config)
            QMessageBox.information(self, "Info", f"{key.replace('_', ' ').title()} set to '{value}'.")

    def load_config(self):
        if not os.path.isfile(CONFIG_FILE):
            config = {
                "prompt_shown": False,
                "auto_launch": False,
                "auto_launch_delay": 2,
                "auto_launch_key": "f9",
                "auto_fullscreen": False,
                "auto_fullscreen_delay": 2,
                "auto_fullscreen_key": "f11",
                "games": []
            }
            self.save_config(config)
        with open(CONFIG_FILE, 'r') as file:
            return json.load(file)

    def save_config(self, config):
        with open(CONFIG_FILE, 'w') as file:
            json.dump(config, file, indent=4)

    def run_xcopy(self, src, dst):
        subprocess.run(["xcopy", src, dst, "/E", "/I", "/Y"], shell=True)

    def clear_directory(self, directory):
        subprocess.run(["rmdir", "/s", "/q", directory], shell=True)

    def launch_xenia(self, game_folder, progress_label):
        def update_progress(message):
            progress_label.setText(message)
            progress_label.repaint()

        def auto_press_key():
            config = self.load_config()
            if config.get("auto_launch", True):
                time.sleep(config.get("auto_launch_delay", 10))
                pyautogui.press(config.get("auto_launch_key", "f9"))
            if config.get("auto_fullscreen", True):
                time.sleep(config.get("auto_fullscreen_delay", 10))
                pyautogui.press(config.get("auto_fullscreen_key", "f11"))

        progress_bar = QProgressBar(self)
        progress_bar.setMaximum(100)

        layout = self.centralWidget().layout()
        layout.addWidget(progress_bar)
        layout.addWidget(progress_label)

        update_progress("Copying save data to game folder...")
        game_path = resource_path(os.path.join('Core', game_folder))
        xenia_exe = resource_path(os.path.join('Core', game_folder, 'xenia_canary.exe'))

        if not os.path.isfile(xenia_exe):
            logging.error(f"Xenia executable not found: {xenia_exe}")
            update_progress(f"Error: Xenia executable not found: {xenia_exe}")
            return

        copy_thread = CopyThread(SAVE_DATA_DIR, game_path)
        copy_thread.progress.connect(progress_bar.setValue)
        copy_thread.update_text.connect(update_progress)
        copy_thread.start()
        copy_thread.wait()  # Wait for the thread to finish

        update_progress("Launching Xenia...")
        threading.Thread(target=auto_press_key).start()

        try:
            subprocess.run([xenia_exe], cwd=game_path, check=True)
        except FileNotFoundError as e:
            logging.error(f"Error launching Xenia: {e}")
            update_progress(f"Error launching Xenia: {e}")

        update_progress("Copying save data back...")
        copy_thread = CopyThread(os.path.join(game_path, 'cache'), os.path.join(SAVE_DATA_DIR, 'cache'))
        copy_thread.progress.connect(progress_bar.setValue)
        copy_thread.update_text.connect(update_progress)
        copy_thread.start()
        copy_thread.wait()

        copy_thread = CopyThread(os.path.join(game_path, 'content'), os.path.join(SAVE_DATA_DIR, 'content'))
        copy_thread.progress.connect(progress_bar.setValue)
        copy_thread.update_text.connect(update_progress)
        copy_thread.start()
        copy_thread.wait()

        self.clear_directory(os.path.join(game_path, 'cache'))
        self.clear_directory(os.path.join(game_path, 'content'))
        update_progress("Done.")

    def launch_normal_xenia(self, game_folder):
        def update_progress(message):
            progress_label.setText(message)
            progress_label.repaint()

        def auto_press_key():
            config = self.load_config()
            if config.get("auto_launch", True):
                time.sleep(config.get("auto_launch_delay", 10))
                pyautogui.press(config.get("auto_launch_key", "f9"))
            if config.get("auto_fullscreen", True):
                time.sleep(config.get("auto_fullscreen_delay", 10))
                pyautogui.press(config.get("auto_fullscreen_key", "f11"))

        progress_label = QLabel("", self)
        progress_label.setAlignment(Qt.AlignCenter)
        progress_bar = QProgressBar(self)
        progress_bar.setMaximum(100)

        layout = self.centralWidget().layout()
        layout.addWidget(progress_bar)
        layout.addWidget(progress_label)

        update_progress("Preparing to launch Xenia...")
        game_path = resource_path(os.path.join('Core', game_folder))
        xenia_exe = resource_path(os.path.join('Core', game_folder, 'xenia.exe'))

        if not os.path.isfile(xenia_exe):
            logging.error(f"Xenia executable not found: {xenia_exe}")
            update_progress(f"Error: Xenia executable not found: {xenia_exe}")
            QMessageBox.critical(self, "Error", f"Xenia executable not found: {xenia_exe}")
            return

        try:
            subprocess.Popen([xenia_exe], cwd=game_path)
            threading.Thread(target=auto_press_key).start()
            update_progress("Xenia launched successfully.")
        except FileNotFoundError as e:
            logging.error(f"Error launching Xenia: {e}")
            update_progress(f"Error launching Xenia: {e}")
            QMessageBox.critical(self, "Error", f"Error launching Xenia: {e}")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            update_progress(f"Unexpected error: {e}")
            QMessageBox.critical(self, "Error", f"Unexpected error: {e}")

        update_progress("Done.")

    def clear_layout(self):
        layout = self.centralWidget().layout()
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    def games_menu(self):
        self.clear_layout()

        layout = QGridLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        font = QFont("Arial", 12)

        self.label = QLabel("Games", self)
        self.label.setFont(font)
        layout.addWidget(self.label, 0, 1, 1, 2)  # Adjusted to make space for the add button

        # Add Game button in the top-left corner
        add_game_button = QPushButton("Add Game", self)
        add_game_button.setFont(font)
        add_game_button.setIcon(qta.icon("fa.plus"))
        add_game_button.clicked.connect(self.add_new_game)
        layout.addWidget(add_game_button, 0, 0)

        config = self.load_config()
        games = config.get('games', [])

        if not games:
            no_games_label = QLabel("No games found. Please add a new game.", self)
            no_games_label.setFont(font)
            layout.addWidget(no_games_label, 1, 0, 1, 3)
        else:
            for i, game in enumerate(games, start=1):
                game_button = QPushButton(game['name'], self)
                game_button.setFont(font)
                game_button.setIcon(qta.icon("fa.gamepad"))
                game_button.clicked.connect(lambda _, g=game: self.show_game_options(g))
                layout.addWidget(game_button, i + 1, 0, 1, 3)  # Adjust the row index

        back_button = QPushButton("Back", self)
        back_button.setFont(font)
        back_button.setIcon(qta.icon("fa.arrow-left"))
        back_button.clicked.connect(self.initUI)
        layout.addWidget(back_button, len(games) + 2, 0, 1, 3)  # Adjust the row index

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def show_game_options(self, game):
        self.clear_layout()

        layout = QGridLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        font = QFont("Arial", 12)

        self.label = QLabel(game['name'], self)
        self.label.setFont(font)
        layout.addWidget(self.label, 0, 0, 1, 2)

        buttons = [
            ("Launch", "fa.play", lambda: self.launch_game(game['path'])),
            ("Edit Config", "fa.edit", lambda: self.edit_config(game['path'])),
            ("Remove", "fa.trash", lambda: self.remove_game(game)),
            ("Open Folder", "fa.folder-open-o", lambda: self.open_folder(game['path'])),
            ("Back", "fa.arrow-left", self.games_menu)
        ]

        for i, (text, icon, func) in enumerate(buttons, start=1):
            button = QPushButton(text, self)
            button.setFont(font)
            button.setIcon(qta.icon(icon))
            button.clicked.connect(func)
            layout.addWidget(button, i, 0, 1, 2)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def open_folder(self, game_path):
        folder_path = os.path.join(CORE_DIR, game_path)
        if os.path.isdir(folder_path):
            os.startfile(folder_path)
        else:
            QMessageBox.warning(self, "Error", f"The folder {folder_path} does not exist.")

    def launch_game(self, path):
        progress_label = QLabel("", self)
        progress_label.setAlignment(Qt.AlignCenter)
        layout = self.centralWidget().layout()
        layout.addWidget(progress_label)
        self.launch_xenia(path, progress_label)

    def help_menu(self):
        QMessageBox.information(self, "Help", "Black Screen after you select a game?\n\n"
                                    "Press Esc\n\n"
                                    "Click File - Open\n\n"
                                    "Select the default.xex/iso file of the game you selected to play from within your games folder\n\n"
                                    "Emulator will now update the correct path for the file\n\n"
                                    "\n\n"
                                    "Only 1 Backup is kept at a time\n\n"
                                    "You should copy your cache and content folders into SaveData & the app will manage your save data across games.\n\n"
                                    "Auto launch will only work once you have played a game at least once using the app.\n\n" 
                                    "When updating Xenia nothing is copied to your custom games folders, you must update these. \n\nYou can use the `Open folder` option to easily find your games xenia_canary.exe \n\n"
                                    "App is still WIP")

    def toggle_auto_fullscreen(self):
        self._toggle_config_option("auto_fullscreen", "Auto Fullscreen")

    def set_auto_fullscreen_key(self):
        self._set_config_value("auto_fullscreen_key", "Enter the key for auto-fullscreen:", "f11")
    
    def set_auto_fullscreen_delay(self):
        self._set_config_value("auto_fullscreen_delay", "Enter the fullscreen delay in seconds:", 2)

    def extra_options(self):
        self.clear_layout()

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        font = QFont("Arial", 12)

        self.label = QLabel("Extra Options", self)
        self.label.setFont(font)
        layout.addWidget(self.label)

        # Method to create buttons with icons
        def create_button(text, icon_name, func):
            button = QPushButton(text, self)
            button.setFont(font)
            button.setIcon(qta.icon(icon_name))
            button.clicked.connect(func)
            return button

        # Backup/Restore Section
        backup_restore_section = QGroupBox("Backup/Restore")
        backup_restore_layout = QVBoxLayout()
        backup_restore_buttons = [
            ("Backup Save Data", "fa.save", self.confirm_backup_save_data),
            ("Restore Save Data", "fa.history", self.confirm_restore_save_data),
            ("Delete Save Data Backup", "fa.trash", self.confirm_delete_save_backups),
        ]
        for text, icon, func in backup_restore_buttons:
            backup_restore_layout.addWidget(create_button(text, icon, func))
        backup_restore_section.setLayout(backup_restore_layout)
        layout.addWidget(backup_restore_section)

        # Update Section
        update_section = QGroupBox("Update")
        update_layout = QVBoxLayout()
        update_buttons = [
            ("Update Xenia", "fa.download", self.update_xenia),
            ("Update Patches", "fa.download", self.update_patches),
            ("Update Non-Canary Xenia", "fa.download", self.update_non_canary_xenia),
        ]
        for text, icon, func in update_buttons:
            update_layout.addWidget(create_button(text, icon, func))
        update_section.setLayout(update_layout)
        layout.addWidget(update_section)

        # Auto Launch Section
        auto_launch_section = QGroupBox("Auto Launch")
        auto_launch_layout = QVBoxLayout()
        auto_launch_buttons = [
            ("Toggle Auto Launch", "fa.toggle-on", self.toggle_auto_launch),
            ("Set Auto Launch Delay", "fa.clock-o", self.set_auto_launch_delay),
            ("Set Auto Launch Key", "fa.keyboard-o", self.set_auto_launch_key),
        ]
        for text, icon, func in auto_launch_buttons:
            auto_launch_layout.addWidget(create_button(text, icon, func))
        auto_launch_section.setLayout(auto_launch_layout)
        layout.addWidget(auto_launch_section)

        # Auto Fullscreen Section
        auto_fullscreen_section = QGroupBox("Auto Fullscreen")
        auto_fullscreen_layout = QVBoxLayout()
        auto_fullscreen_buttons = [
            ("Toggle Auto Fullscreen", "fa.toggle-on", self.toggle_auto_fullscreen),
            ("Set Auto Fullscreen Delay", "fa.clock-o", self.set_auto_fullscreen_delay),
            ("Set Auto Fullscreen Key", "fa.keyboard-o", self.set_auto_fullscreen_key),
        ]
        for text, icon, func in auto_fullscreen_buttons:
            auto_fullscreen_layout.addWidget(create_button(text, icon, func))
        auto_fullscreen_section.setLayout(auto_fullscreen_layout)
        layout.addWidget(auto_fullscreen_section)

        # Folder Access Section
        folder_access_section = QGroupBox("Folder Access")
        folder_access_layout = QVBoxLayout()
        folder_access_buttons = [
            ("Open SaveData Folder", "fa.folder-open-o", self.open_save_data_folder),
            ("Open Patches Folder", "fa.folder-open-o", self.open_patches_folder),
        ]
        for text, icon, func in folder_access_buttons:
            folder_access_layout.addWidget(create_button(text, icon, func))
        folder_access_section.setLayout(folder_access_layout)
        layout.addWidget(folder_access_section)

        # Back Button
        back_button = create_button("Back", "fa.arrow-left", self.initUI)
        layout.addWidget(back_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def confirm_backup_save_data(self):
        self._confirm_action("Backup Save Data", "Are you sure you want to backup save data?", self.backup_save_data)

    def confirm_restore_save_data(self):
        self._confirm_action("Restore Save Data", "Are you sure you want to restore save data?", self.restore_save_data)

    def confirm_delete_save_backups(self):
        self._confirm_action("Delete Save Data Backup", "Are you sure you want to delete save data backups?", self.delete_save_backups)

    def _confirm_action(self, title, message, action):
        reply = QMessageBox.question(self, "Confirm", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            action()

    def backup_save_data(self):
        self._backup_or_restore(SAVE_DATA_DIR, 'Backups', "Backup completed!")

    def restore_save_data(self):
        self._backup_or_restore('Backups', SAVE_DATA_DIR, "Restore completed!")

    def _backup_or_restore(self, src_dir, dst_dir, success_message):
        self.run_xcopy(os.path.join(src_dir, 'cache'), os.path.join(BASE_DIR, dst_dir, 'cache'))
        self.run_xcopy(os.path.join(src_dir, 'content'), os.path.join(BASE_DIR, dst_dir, 'content'))
        QMessageBox.information(self, "Info", success_message)

    def update_xenia(self):
        message = ("This will download and update Xenia to the latest version from the repository.\n"
                   "Do you want to continue?\n\n"
                   "Details:\n"
                   "- The latest version will be fetched from https://github.com/xenia-canary/xenia-canary.\n"
                   "- Existing Xenia files will be replaced with the new ones.\n"
                   "- Your game data and added games will not be affected.")
        self._confirm_action("Update Xenia", message, self._update_xenia_files)

    def _update_xenia_files(self):
        self.initialize_directories()
        repo_url = "https://api.github.com/repos/xenia-canary/xenia-canary/releases/latest"
        response = requests.get(repo_url)
        response.raise_for_status()
        release_info = response.json()

        asset = next((asset for asset in release_info['assets'] if asset['name'].endswith('.zip')), None)
        if not asset:
            QMessageBox.critical(self, "Error", "No zip file found in the latest release assets.")
            return

        zip_url = asset['browser_download_url']
        response = requests.get(zip_url)
        response.raise_for_status()

        update_dir = os.path.join(BASE_DIR, 'Update', 'Depo')
        if os.path.exists(update_dir):
            self.clear_directory(update_dir)
        os.makedirs(update_dir, exist_ok=True)

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extractall(update_dir)

        self.run_xcopy(update_dir, os.path.join(CORE_DIR, 'Xenia'))
        self.run_xcopy(update_dir, os.path.join(CORE_DIR, '4k\\Xenia'))
        self.run_xcopy(update_dir, os.path.join(BASE_DIR, 'Resources'))

        QMessageBox.information(self, "Info", "Update completed! - Core & Resources Only - Your games have not been updated!")
        
    def update_non_canary_xenia(self):
        message = ("This will download and update Non Canary Xenia to the latest version from the repository.\n"
                   "Do you want to continue?\n\n"
                   "Details:\n"
                   "- The latest version will be fetched from https://api.github.com/repos/xenia-project/release-builds-windows/releases/latest \n"
                   "- Existing Non Canary Xenia files will be replaced with the new ones.\n"
                   "- Your game data and added games will not be affected.")
        self._confirm_action("Update Non Canary Xenia", message, self._update_non_canary_xenia_files)
        
    def _update_non_canary_xenia_files(self):
        self.initialize_directories()
        repo_url = "https://api.github.com/repos/xenia-project/release-builds-windows/releases/latest"
        response = requests.get(repo_url)
        response.raise_for_status()
        release_info = response.json()

        # Fetch the specific asset named 'xenia_master.zip'
        asset = next((asset for asset in release_info['assets'] if asset['name'] == 'xenia_master.zip'), None)
        if not asset:
            QMessageBox.critical(self, "Error", "No 'xenia_master.zip' file found in the latest release assets.")
            return

        zip_url = asset['browser_download_url']
        response = requests.get(zip_url)
        response.raise_for_status()

        update_dir = os.path.join(BASE_DIR, 'Update', 'NonCanaryDepo')
        if os.path.exists(update_dir):
            self.clear_directory(update_dir)
        os.makedirs(update_dir, exist_ok=True)

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extractall(update_dir)

        self.run_xcopy(update_dir, os.path.join(CORE_DIR, 'NonCanaryXenia'))
        self.run_xcopy(update_dir, os.path.join(BASE_DIR, 'NonCanaryXResources'))

        QMessageBox.information(self, "Info", "Update completed! - Non Canary Core & Non Canary Resources Only - Your games have not been updated!")

    def update_patches(self):
        message = ("This will remove all current patches and download new ones from the repository.\n"
                   "Do you want to continue?\n\n"
                   "Details:\n"
                   "- Existing patches will be deleted.\n"
                   "- New patches will be downloaded from https://github.com/xenia-canary/game-patches.\n"
                   "- The process might take a few minutes depending on your internet connection.")
        self._confirm_action("Update Patches", message, self._update_patches_files)

    def _update_patches_files(self):
        patches_dir = resource_path('Patches')
        temp_extract_dir = resource_path('TempPatches')

        if os.path.exists(patches_dir):
            self.clear_directory(patches_dir)
        os.makedirs(patches_dir, exist_ok=True)

        if os.path.exists(temp_extract_dir):
            self.clear_directory(temp_extract_dir)
        os.makedirs(temp_extract_dir, exist_ok=True)

        patches_url = "https://github.com/xenia-canary/game-patches/archive/refs/heads/main.zip"

        try:
            response = requests.get(patches_url)
            response.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                z.extractall(temp_extract_dir)

            extracted_patches_dir = os.path.join(temp_extract_dir, "game-patches-main", "patches")
            if os.path.exists(extracted_patches_dir):
                for item in os.listdir(extracted_patches_dir):
                    shutil.move(os.path.join(extracted_patches_dir, item), os.path.join(patches_dir, item))

            shutil.rmtree(temp_extract_dir)
            QMessageBox.information(self, "Info", "Patches updated successfully!")
        except requests.RequestException as e:
            logging.error(f"Error downloading patches: {e}")
            QMessageBox.critical(self, "Error", f"Error downloading patches: {e}")
        except zipfile.BadZipFile as e:
            logging.error(f"Error extracting patches: {e}")
            QMessageBox.critical(self, "Error", f"Error extracting patches: {e}")

    def delete_save_backups(self):
        self.clear_directory(os.path.join(BASE_DIR, 'Backups', 'cache'))
        self.clear_directory(os.path.join(BASE_DIR, 'Backups', 'content'))
        QMessageBox.information(self, "Info", "Backups removed!")

    def add_new_game(self):
        config = self.load_config()
        new_id = str(len(config['games']) + 1)
        name, ok1 = QInputDialog.getText(self, "Input", "Enter the game name\n\n(This can be anything you want):")
        path, ok2 = QInputDialog.getText(self, "Input", "Enter a name for your game folder\n\n(One will be created if it doesnt exist):")
        image_path, ok3 = QInputDialog.getText(self, "Input", "Enter the image name with extension\n\n(Your image should be placed in images folder, enter none for no image):")

        if ok1 and ok2 and ok3 and name and path and image_path:
            game_path = os.path.join(CORE_DIR, path)
            if not os.path.exists(game_path):
                os.makedirs(game_path)
            self.run_xcopy(EXAMPLE_FOLDER, game_path)
            config_file_src = resource_path('defaultconfig.toml')
            config_file_dst = os.path.join(game_path, 'xenia-canary.config.toml')
            if os.path.isfile(config_file_src):
                shutil.copy2(config_file_src, config_file_dst)
            config['games'].append({"id": new_id, "name": name, "path": path, "image_path": image_path})
            self.save_config(config)
            QMessageBox.information(self, "Success", "Game added successfully!")
            self.games_menu()  # Refresh the games menu
        else:
            QMessageBox.critical(self, "Error", "Invalid input!")

    def remove_game(self, game):
        config = self.load_config()
        game_name = game['name']
        game_path = os.path.join(CORE_DIR, game['path'])

        reply = QMessageBox.question(self, "Confirm", f"Do you want to remove the game '{game_name}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        config['games'] = [g for g in config['games'] if g['name'] != game_name]
        self.save_config(config)

        reply = QMessageBox.question(self, "Delete Data", f"Do you want to delete the data for '{game_name}' located at '{game_path}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if os.path.exists(game_path):
                self.clear_directory(game_path)
                QMessageBox.information(self, "Info", f"Data for '{game_name}' has been deleted.")
            else:
                QMessageBox.warning(self, "Warning", f"Data path '{game_path}' does not exist.")
        QMessageBox.information(self, "Info", f"'{game_name}' has been removed from the configuration.")
        self.games_menu()

    def edit_config(self, game_folder):
        toml_path = os.path.join(CORE_DIR, game_folder, TOML_CONFIG_FILE)
        self._open_file(toml_path, "You must launch Xenia at least once to have a config file!")

    def initialize_directories(self):
        xenia_path = resource_path(os.path.join('Core', 'Xenia'))
        xenia_4k_path = resource_path(os.path.join('Core', '4k\\Xenia'))
        resources_path = resource_path('Resources')

        os.makedirs(xenia_path, exist_ok=True)
        os.makedirs(xenia_4k_path, exist_ok=True)

        if not os.path.isfile(os.path.join(xenia_path, 'xenia_canary.exe')):
            self.run_xcopy(resources_path, xenia_path)

        if not os.path.isfile(os.path.join(xenia_4k_path, 'xenia_canary.exe')):
            self.run_xcopy(resources_path, xenia_4k_path)

        config_file_src = resource_path('4kconfig.toml')
        config_file_dst = os.path.join(xenia_4k_path, 'xenia-canary.config.toml')
        if os.path.isfile(config_file_src):
            shutil.copy2(config_file_src, config_file_dst)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = XeniaManager()
    window.show()
    sys.exit(app.exec_())
