import os
import io
import subprocess
import requests
import zipfile
import json
import shutil
import logging
import sys
import time
import threading
import pyautogui

from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QInputDialog, QLabel, QVBoxLayout, QPushButton, QWidget, QFileDialog, QGridLayout
from PyQt5.QtGui import QPixmap, QPalette, QBrush, QFont
from PyQt5.QtCore import Qt

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

class HeaderWidget(QWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.initUI()

    def initUI(self):
        self.setFixedHeight(200)  # Set the height of the header
        palette = QPalette()
        pixmap = QPixmap(self.image_path)
        scaled_pixmap = pixmap.scaled(self.width(), self.height(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        palette.setBrush(QPalette.Window, QBrush(scaled_pixmap))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

    def resizeEvent(self, event):
        # Handle resizing of the header to keep the image properly scaled
        palette = QPalette()
        pixmap = QPixmap(self.image_path)
        scaled_pixmap = pixmap.scaled(self.width(), self.height(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        palette.setBrush(QPalette.Window, QBrush(scaled_pixmap))
        self.setPalette(palette)

class GameItemWidget(QWidget):
    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        launch_button = QPushButton("Launch", self)
        launch_button.clicked.connect(self.launch_game)
        layout.addWidget(launch_button)

        edit_button = QPushButton("Edit Config", self)
        edit_button.clicked.connect(self.edit_config)
        layout.addWidget(edit_button)

        remove_button = QPushButton("Remove", self)
        remove_button.clicked.connect(self.remove_game)
        layout.addWidget(remove_button)

        open_folder_button = QPushButton("Open Folder", self)
        open_folder_button.clicked.connect(self.open_folder)
        layout.addWidget(open_folder_button)

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
        
        # Create the main layout
        main_layout = QVBoxLayout()

        # Add the header widget with the background image
        header = HeaderWidget(resource_path(os.path.join('images', MAIN_MENU_IMAGE)), self)
        main_layout.addWidget(header)

        # Create the central widget layout
        layout = QGridLayout()
        layout.setContentsMargins(20, 20, 20, 20)  # Add margins
        layout.setSpacing(15)  # Add spacing between elements

        # Define a font for buttons and labels
        font = QFont("Arial", 12)

        self.label = QLabel("What would you like to do?", self)
        self.label.setFont(font)
        layout.addWidget(self.label, 0, 0, 1, 2)

        buttons = [
            ("Games", self.games_menu),
            ("Launch Xenia Canary With Default Settings", lambda: self.launch_game("Xenia")),
            ("Edit Config", lambda: self.edit_config("Xenia")),
            ("Launch Xenia Canary With 4k Settings", lambda: self.launch_game("4k\\Xenia")),
            ("Edit Config", lambda: self.edit_config("4k\\Xenia")),
            ("Help", self.help_menu),
            ("Extra Options", self.extra_options),
            ("Toggle Auto Launch", self.toggle_auto_launch),
            ("Add New Game", self.add_new_game),
            ("Open Games Config", self.open_games_config),
            ("Open SaveData Folder", self.open_save_data_folder)
        ]

        for i, (text, func) in enumerate(buttons, start=1):
            button = QPushButton(text, self)
            button.setFont(font)
            button.clicked.connect(func)
            layout.addWidget(button, i, 0, 1, 2)

        container = QWidget()
        container.setLayout(layout)
        main_layout.addWidget(container)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def open_save_data_folder(self):
        if not os.path.isdir(SAVE_DATA_DIR):
            os.makedirs(SAVE_DATA_DIR)
            QMessageBox.information(self, "Info", f"The folder {SAVE_DATA_DIR} has been created.")
        os.startfile(SAVE_DATA_DIR)
    
    def open_games_config(self):
        if os.path.isfile(CONFIG_FILE):
            os.startfile(CONFIG_FILE)
            QMessageBox.information(self, "Info", f"Opening configuration file: {CONFIG_FILE}")
        else:
            QMessageBox.warning(self, "Error", "Games config file not found!")

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
        config = self.load_config()
        config["auto_launch"] = not config.get("auto_launch", False)
        self.save_config(config)
        QMessageBox.information(self, "Info", f"Auto Launch is now {'enabled' if config['auto_launch'] else 'disabled'}.")

    def set_auto_launch_delay(self):
        config = self.load_config()
        delay, ok = QInputDialog.getInt(self, "Input", "Enter the auto-launch delay in seconds:", value=config.get("auto_launch_delay", 5))
        if ok:
            config["auto_launch_delay"] = delay
            self.save_config(config)
            QMessageBox.information(self, "Info", f"Auto Launch Delay set to {delay} seconds.")

    def set_auto_launch_key(self):
        config = self.load_config()
        key, ok = QInputDialog.getText(self, "Input", "Enter the key for auto-launch:", text=config.get("auto_launch_key", "f9"))
        if ok:
            config["auto_launch_key"] = key
            self.save_config(config)
            QMessageBox.information(self, "Info", f"Auto Launch Key set to '{key}'.")

    def load_config(self):
        if not os.path.isfile(CONFIG_FILE):
            config = {
                "prompt_shown": False,
                "auto_launch": False,
                "auto_launch_delay": 2,
                "auto_launch_key": "f9",
                "games": []
            }
            self.save_config(config)
        with open(CONFIG_FILE, 'r') as file:
            return json.load(file)

    def save_config(self, config):
        with open(CONFIG_FILE, 'w') as file:
            json.dump(config, file, indent=4)

    def run_xcopy(self, src, dst):
        command = ["xcopy", src, dst, "/E", "/I", "/Y"]
        subprocess.run(command, shell=True)

    def clear_directory(self, directory):
        command = ["rmdir", "/s", "/q", directory]
        subprocess.run(command, shell=True)

    def launch_xenia(self, game_folder, progress_label):
        def update_progress(message):
            progress_label.setText(message)
            progress_label.repaint()

        def auto_press_key():
            config = self.load_config()
            if config.get("auto_launch", True):
                time.sleep(config.get("auto_launch_delay", 10))
                pyautogui.press(config.get("auto_launch_key", "f9"))

        update_progress("Copying save data to game folder...")
        game_path = resource_path(os.path.join('Core', game_folder))
        xenia_exe = resource_path(os.path.join('Core', game_folder, 'xenia_canary.exe'))

        logging.info(f"Game path: {game_path}")
        logging.info(f"Xenia executable path: {xenia_exe}")

        if not os.path.isfile(xenia_exe):
            logging.error(f"Xenia executable not found: {xenia_exe}")
            update_progress(f"Error: Xenia executable not found: {xenia_exe}")
            return

        self.run_xcopy(SAVE_DATA_DIR, game_path)
        update_progress("Launching Xenia...")

        threading.Thread(target=auto_press_key).start()

        try:
            subprocess.run([xenia_exe], cwd=game_path, check=True)
        except FileNotFoundError as e:
            logging.error(f"Error launching Xenia: {e}")
            update_progress(f"Error launching Xenia: {e}")

        update_progress("Copying save data back...")
        self.run_xcopy(os.path.join(game_path, 'cache'), os.path.join(SAVE_DATA_DIR, 'cache'))
        self.run_xcopy(os.path.join(game_path, 'content'), os.path.join(SAVE_DATA_DIR, 'content'))
        self.clear_directory(os.path.join(game_path, 'cache'))
        self.clear_directory(os.path.join(game_path, 'content'))
        update_progress("Done.")

    def clear_layout(self):
        # Remove all widgets from the layout
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
        layout.setContentsMargins(20, 20, 20, 20)  # Add margins
        layout.setSpacing(15)  # Add spacing between elements
        font = QFont("Arial", 12)

        self.label = QLabel("Games", self)
        self.label.setFont(font)
        layout.addWidget(self.label, 0, 0, 1, 2)

        config = self.load_config()
        games = config.get('games', [])

        if not games:
            no_games_label = QLabel("No games found. Please add a new game.", self)
            no_games_label.setFont(font)
            layout.addWidget(no_games_label, 1, 0, 1, 2)
        else:
            for i, game in enumerate(games, start=1):
                game_button = QPushButton(game['name'], self)
                game_button.setFont(font)
                game_button.clicked.connect(lambda _, g=game: self.show_game_options(g))
                layout.addWidget(game_button, i, 0, 1, 2)

        back_button = QPushButton("Back", self)
        back_button.setFont(font)
        back_button.clicked.connect(self.initUI)
        layout.addWidget(back_button, len(games) + 1, 0, 1, 2)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def show_game_options(self, game):
        self.clear_layout()

        layout = QGridLayout()
        layout.setContentsMargins(20, 20, 20, 20)  # Add margins
        layout.setSpacing(15)  # Add spacing between elements
        font = QFont("Arial", 12)

        self.label = QLabel(game['name'], self)
        self.label.setFont(font)
        layout.addWidget(self.label, 0, 0, 1, 2)

        buttons = [
            ("Launch", lambda: self.launch_game(game['path'])),
            ("Edit Config", lambda: self.edit_config(game['path'])),
            ("Remove", lambda: self.remove_game(game)),
            ("Open Folder", lambda: self.open_folder(game['path'])),
            ("Back", self.games_menu)
        ]

        for i, (text, func) in enumerate(buttons, start=1):
            button = QPushButton(text, self)
            button.setFont(font)
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
                                    "You can now use F9 to launch the game from now on after selecting your choice on the games menu\n\n"
                                    "Only 1 Backup is kept at a time\n\n"
                                    "You should copy your cache and content folders into SaveData & the app will manage your save data across games.\n\n"
                                    "Auto launch will only work once you have played a game at least once using the app.\n\n" 
                                    "(Auto launch attempts to press F9 after starting Xenia - Configurable via games_config.json)\n\n"
                                    "App is still WIP")

    def extra_options(self):
        self.clear_layout()

        layout = QGridLayout()
        layout.setContentsMargins(20, 20, 20, 20)  # Add margins
        layout.setSpacing(15)  # Add spacing between elements
        font = QFont("Arial", 12)

        self.label = QLabel("Extra Options", self)
        self.label.setFont(font)
        layout.addWidget(self.label, 0, 0, 1, 2)

        buttons = [
            ("Backup Save Data", self.confirm_backup_save_data),
            ("Restore Save Data", self.confirm_restore_save_data),
            ("Update Xenia", self.update_xenia),
            ("Update Patches", self.update_patches),
            ("Delete Save Data Backup", self.confirm_delete_save_backups),
            ("Back", self.initUI)
        ]

        for i, (text, func) in enumerate(buttons, start=1):
            button = QPushButton(text, self)
            button.setFont(font)
            button.clicked.connect(func)
            layout.addWidget(button, i, 0, 1, 2)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def confirm_backup_save_data(self):
        reply = QMessageBox.question(self, "Confirm", "Are you sure you want to backup save data?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.backup_save_data()

    def confirm_restore_save_data(self):
        reply = QMessageBox.question(self, "Confirm", "Are you sure you want to restore save data?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.restore_save_data()

    def confirm_delete_save_backups(self):
        reply = QMessageBox.question(self, "Confirm", "Are you sure you want to delete save data backups?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.delete_save_backups()

    def backup_save_data(self):
        self.run_xcopy(os.path.join(SAVE_DATA_DIR, 'cache'), os.path.join(BASE_DIR, 'Backups', 'cache'))
        self.run_xcopy(os.path.join(SAVE_DATA_DIR, 'content'), os.path.join(BASE_DIR, 'Backups', 'content'))
        QMessageBox.information(self, "Info", "Backup completed!")

    def restore_save_data(self):
        self.run_xcopy(os.path.join(BASE_DIR, 'Backups', 'cache'), os.path.join(SAVE_DATA_DIR, 'cache'))
        self.run_xcopy(os.path.join(BASE_DIR, 'Backups', 'content'), os.path.join(SAVE_DATA_DIR, 'content'))
        QMessageBox.information(self, "Info", "Restore completed!")

    def update_xenia(self):
        message = ("This will download and update Xenia to the latest version from the repository.\n"
                   "Do you want to continue?\n\n"
                   "Details:\n"
                   "- The latest version will be fetched from https://github.com/xenia-canary/xenia-canary.\n"
                   "- Existing Xenia files will be replaced with the new ones.\n"
                   "- Your game data will not be affected.")
        reply = QMessageBox.question(self, "Update Xenia", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
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

    def update_patches(self):
        patches_dir = resource_path('Patches')
        temp_extract_dir = resource_path('TempPatches')

        message = ("This will remove all current patches and download new ones from the repository.\n"
                   "Do you want to continue?\n\n"
                   "Details:\n"
                   "- Existing patches will be deleted.\n"
                   "- New patches will be downloaded from https://github.com/xenia-canary/game-patches.\n"
                   "- The process might take a few minutes depending on your internet connection.")
        reply = QMessageBox.question(self, "Update Patches", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

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
        image_path, ok3 = QInputDialog.getText(self, "Input", "Enter the a image name\n\n(Your image should be placed in images folder, enter none for no image):")

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
        if os.path.isfile(toml_path):
            os.startfile(toml_path)  # This works on Windows. Use an appropriate method for other OS.
            QMessageBox.information(self, "Info", f"Opening configuration file: {toml_path}")
        else:
            QMessageBox.warning(self, "Error", "You must launch Xenia at least once to have a config file!")

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
