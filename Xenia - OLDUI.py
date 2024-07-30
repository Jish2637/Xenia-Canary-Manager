import os
import io
import subprocess
import requests
import zipfile
import json
import shutil
import tkinter as tk
from tkinter import messagebox, simpledialog, Text, ttk
import logging
import sys
import time
import pyautogui
import threading

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

def initialize_directories():
    xenia_path = resource_path(os.path.join('Core', 'Xenia'))
    xenia_4k_path = resource_path(os.path.join('Core', '4k\\Xenia'))
    resources_path = resource_path('Resources')

    # Create directories if they don't exist
    os.makedirs(xenia_path, exist_ok=True)
    os.makedirs(xenia_4k_path, exist_ok=True)

    # Copy resources to Xenia directory
    if not os.path.isfile(os.path.join(xenia_path, 'xenia_canary.exe')):
        run_xcopy(resources_path, xenia_path)

    # Copy resources to 4k Xenia directory
    if not os.path.isfile(os.path.join(xenia_4k_path, 'xenia_canary.exe')):
        run_xcopy(resources_path, xenia_4k_path)
    
    # Handle the 4k config file separately
    config_file_src = resource_path('4kconfig.toml')
    config_file_dst = os.path.join(xenia_4k_path, 'xenia-canary.config.toml')
    if os.path.isfile(config_file_src):
        shutil.copy2(config_file_src, config_file_dst)

def show_initial_prompt():
    config = load_config()
    if not config.get("prompt_shown", False):
        message = ("Would you like to update Xenia and download patches?\n\n"
                   "Details:\n"
                   "- Update Xenia to the latest version from https://github.com/xenia-canary/xenia-canary.\n"
                   "- Download new game patches from https://github.com/xenia-canary/game-patches.\n"
                   "- This process might take a few minutes depending on your internet connection.")
        if messagebox.askyesno("Initial Setup", message):
            update_xenia()
            update_patches()
        config["prompt_shown"] = True
        save_config(config)

def toggle_auto_launch():
    config = load_config()
    config["auto_launch"] = not config.get("auto_launch", False)
    save_config(config)
    messagebox.showinfo("Info", f"Auto Launch is now {'enabled' if config['auto_launch'] else 'disabled'}.")

def set_auto_launch_delay():
    config = load_config()
    delay = simpledialog.askinteger("Input", "Enter the auto-launch delay in seconds:", initialvalue=config.get("auto_launch_delay", 5))
    if delay is not None:
        config["auto_launch_delay"] = delay
        save_config(config)
        messagebox.showinfo("Info", f"Auto Launch Delay set to {delay} seconds.")

def set_auto_launch_key():
    config = load_config()
    key = simpledialog.askstring("Input", "Enter the key for auto-launch:", initialvalue=config.get("auto_launch_key", "f9"))
    if key:
        config["auto_launch_key"] = key
        save_config(config)
        messagebox.showinfo("Info", f"Auto Launch Key set to '{key}'.")
        
def load_config():
    if not os.path.isfile(CONFIG_FILE):
        # Create default config if it doesn't exist
        config = {
            "prompt_shown": False,
            "auto_launch": False,
            "auto_launch_delay": 10,
            "auto_launch_key": "f9",
            "games": []
        }
        save_config(config)
    with open(CONFIG_FILE, 'r') as file:
        return json.load(file)

def save_config(config):
    with open(CONFIG_FILE, 'w') as file:
        json.dump(config, file, indent=4)

def load_toml_config(game_folder):
    toml_path = os.path.join(CORE_DIR, game_folder, TOML_CONFIG_FILE)
    with open(toml_path, 'r') as file:
        return toml.load(file)

def save_toml_config(game_folder, config):
    toml_path = os.path.join(CORE_DIR, game_folder, TOML_CONFIG_FILE)
    with open(toml_path, 'w') as file:
        toml.dump(config, file)

def run_xcopy(src, dst):
    command = ["xcopy", src, dst, "/E", "/I", "/Y"]
    subprocess.run(command, shell=True)

def clear_directory(directory):
    command = ["rmdir", "/s", "/q", directory]
    subprocess.run(command, shell=True)

def launch_xenia(game_folder, progress_label):
    def update_progress(message):
        progress_label.config(text=message)
        progress_label.update_idletasks()

    def auto_press_key():
        # Auto-launch feature
        config = load_config()
        if config.get("auto_launch", True):
            time.sleep(config.get("auto_launch_delay", 10))  # Wait for the configured delay
            pyautogui.press(config.get("auto_launch_key", "f9"))  # Press the configured key

    # Clear the progress label at the beginning
    progress_label.config(text="")
    progress_label.update_idletasks()

    update_progress("Copying save data to game folder...")
    progress_label.after(5000, lambda: progress_label.config(text=""))

    game_path = resource_path(os.path.join('Core', game_folder))
    xenia_exe = resource_path(os.path.join('Core', game_folder, 'xenia_canary.exe'))

    logging.info(f"Game path: {game_path}")
    logging.info(f"Xenia executable path: {xenia_exe}")

    if not os.path.isfile(xenia_exe):
        logging.error(f"Xenia executable not found: {xenia_exe}")
        update_progress(f"Error: Xenia executable not found: {xenia_exe}")
        return

    run_xcopy(SAVE_DATA_DIR, game_path)

    update_progress("Launching Xenia...")
    progress_label.after(5000, lambda: progress_label.config(text=""))

    # Start the thread to auto-press the key
    threading.Thread(target=auto_press_key).start()

    try:
        subprocess.run([xenia_exe], cwd=game_path, check=True)
    except FileNotFoundError as e:
        logging.error(f"Error launching Xenia: {e}")
        update_progress(f"Error launching Xenia: {e}")

    update_progress("Copying save data back...")
    progress_label.after(5000, lambda: progress_label.config(text=""))
    run_xcopy(os.path.join(game_path, 'cache'), os.path.join(SAVE_DATA_DIR, 'cache'))
    run_xcopy(os.path.join(game_path, 'content'), os.path.join(SAVE_DATA_DIR, 'content'))
    clear_directory(os.path.join(game_path, 'cache'))
    clear_directory(os.path.join(game_path, 'content'))
    progress_label.after(5000, lambda: progress_label.config(text=""))
    update_progress("Done.")
    # Reset the progress label after completion
    progress_label.after(500, lambda: progress_label.config(text=""))

def main_menu():
    show_initial_prompt()  # Show initial prompt if needed

    initialize_directories()  # Initialize directories on first launch

    for widget in root.winfo_children():
        widget.destroy()

    root.title("Xenia Manager")

    ttk.Label(root, text="What would you like to do?").pack(pady=10)

    ttk.Button(root, text="Games", command=games_menu).pack(fill='x', padx=20, pady=5)
    
    # Default Settings Launch and Edit Config
    default_frame = ttk.Frame(root)
    default_frame.pack(fill='x', padx=20, pady=5)
    ttk.Button(default_frame, text="Launch Xenia Canary With Default Settings", command=lambda: launch_game("Xenia")).pack(side='left', fill='x', expand=True)
    ttk.Button(default_frame, text="Edit Config", command=lambda: edit_config("Xenia")).pack(side='left')

    # 4k Settings Launch and Edit Config
    k4_frame = ttk.Frame(root)
    k4_frame.pack(fill='x', padx=20, pady=5)
    ttk.Button(k4_frame, text="Launch Xenia Canary With 4k Settings", command=lambda: launch_game("4k\\Xenia")).pack(side='left', fill='x', expand=True)
    ttk.Button(k4_frame, text="Edit Config", command=lambda: edit_config("4k\\Xenia")).pack(side='left')

    ttk.Button(root, text="Help", command=help_menu).pack(fill='x', padx=20, pady=5)
    ttk.Button(root, text="Extra Options", command=extra_options).pack(fill='x', padx=20, pady=5)

    ttk.Button(root, text="Toggle Auto Launch", command=toggle_auto_launch).pack(fill='x', padx=20, pady=5)
    
    ttk.Button(root, text="Add New Game", command=add_new_game).pack(fill='x', padx=20, pady=5)



def games_menu():
    for widget in root.winfo_children():
        widget.destroy()

    root.title("Games")

    ttk.Label(root, text="Games").pack(pady=10)

    config = load_config()

    for game in config['games']:
        frame = ttk.Frame(root)
        frame.pack(fill='x', padx=20, pady=5)

        ttk.Button(frame, text=game['name'], command=lambda g=game: launch_game(g['path'])).pack(side='left', fill='x', expand=True)
        ttk.Button(frame, text="Edit Config", command=lambda g=game: edit_config(g['path'])).pack(side='left')
        ttk.Button(frame, text="Remove", command=lambda g=game: remove_game(g)).pack(side='left')
        ttk.Button(frame, text="Open Folder", command=lambda g=game: open_folder(g['path'])).pack(side='left')

    ttk.Button(root, text="Back", command=main_menu).pack(pady=20)
    
def open_folder(game_path):
    folder_path = os.path.join(CORE_DIR, game_path)
    if os.path.isdir(folder_path):
        os.startfile(folder_path)
    else:
        messagebox.showerror("Error", f"The folder {folder_path} does not exist.")
    
def launch_game(path):
    progress_label = tk.Label(root, text="")
    progress_label.pack(pady=10)
    launch_xenia(path, progress_label)

def help_menu():
    messagebox.showinfo("Help", "Black Screen after you select a game?\n\n"
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

def extra_options():
    for widget in root.winfo_children():
        widget.destroy()

    root.title("Extra Options")

    ttk.Label(root, text="Extra Options").pack(pady=10)

    ttk.Button(root, text="Backup Save Data", command=backup_save_data).pack(fill='x', padx=20, pady=5)
    ttk.Button(root, text="Restore Save Data", command=restore_save_data).pack(fill='x', padx=20, pady=5)
    
    ttk.Button(root, text="Update Xenia", command=update_xenia).pack(fill='x', padx=20, pady=5)
    ttk.Button(root, text="Update Patches", command=update_patches).pack(fill='x', padx=20, pady=5)

    ttk.Button(root, text="Delete Save Data Backup", command=delete_save_backups).pack(fill='x', padx=20, pady=5)
    ttk.Button(root, text="Delete Update Backups", command=delete_update_backups).pack(fill='x', padx=20, pady=5)

    ttk.Button(root, text="Back", command=main_menu).pack(pady=20)

def backup_save_data():
    run_xcopy(os.path.join(SAVE_DATA_DIR, 'cache'), os.path.join(BASE_DIR, 'Backups', 'cache'))
    run_xcopy(os.path.join(SAVE_DATA_DIR, 'content'), os.path.join(BASE_DIR, 'Backups', 'content'))
    messagebox.showinfo("Info", "Backup completed!")

def restore_save_data():
    run_xcopy(os.path.join(BASE_DIR, 'Backups', 'cache'), os.path.join(SAVE_DATA_DIR, 'cache'))
    run_xcopy(os.path.join(BASE_DIR, 'Backups', 'content'), os.path.join(SAVE_DATA_DIR, 'content'))
    messagebox.showinfo("Info", "Restore completed!")

def update_xenia():
    # Show confirmation dialog with additional information
    message = ("This will download and update Xenia to the latest version from the repository.\n"
               "Do you want to continue?\n\n"
               "Details:\n"
               "- The latest version will be fetched from https://github.com/xenia-canary/xenia-canary.\n"
               "- Existing Xenia files will be replaced with the new ones.\n"
               "- Your game data will not be affected.")
    if not messagebox.askyesno("Update Xenia", message):
        return

    # Fetch the latest release information from GitHub
    repo_url = "https://api.github.com/repos/xenia-canary/xenia-canary/releases/latest"
    response = requests.get(repo_url)
    response.raise_for_status()  # Check for request errors
    release_info = response.json()

    # Get the download URL for the latest release zip file
    asset = next((asset for asset in release_info['assets'] if asset['name'].endswith('.zip')), None)
    if not asset:
        messagebox.showerror("Error", "No zip file found in the latest release assets.")
        return

    zip_url = asset['browser_download_url']

    # Download the latest release zip file
    response = requests.get(zip_url)
    response.raise_for_status()  # Check for request errors

    # Extract the zip file to the update directory
    update_dir = os.path.join(BASE_DIR, 'Update', 'Depo')
    if os.path.exists(update_dir):
        clear_directory(update_dir)
    os.makedirs(update_dir, exist_ok=True)
    
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        z.extractall(update_dir)

    # Update the existing Xenia files with the new ones
    run_xcopy(update_dir, os.path.join(CORE_DIR, 'Xenia'))
    run_xcopy(update_dir, os.path.join(CORE_DIR, '4k\\Xenia'))
    run_xcopy(update_dir, os.path.join(BASE_DIR, 'Resources'))

    messagebox.showinfo("Info", "Update completed! - Core & Resources Only - Your games have not been updated!")

def update_patches():
    patches_dir = resource_path('Patches')
    temp_extract_dir = resource_path('TempPatches')

    # Show confirmation dialog with additional information
    message = ("This will remove all current patches and download new ones from the repository.\n"
               "Do you want to continue?\n\n"
               "Details:\n"
               "- Existing patches will be deleted.\n"
               "- New patches will be downloaded from https://github.com/xenia-canary/game-patches.\n"
               "- The process might take a few minutes depending on your internet connection.")
    if not messagebox.askyesno("Update Patches", message):
        return

    # Clear existing patches directory
    if os.path.exists(patches_dir):
        clear_directory(patches_dir)
    os.makedirs(patches_dir, exist_ok=True)

    # Clear temporary extraction directory
    if os.path.exists(temp_extract_dir):
        clear_directory(temp_extract_dir)
    os.makedirs(temp_extract_dir, exist_ok=True)

    # URL for the game patches
    patches_url = "https://github.com/xenia-canary/game-patches/archive/refs/heads/main.zip"
    
    try:
        response = requests.get(patches_url)
        response.raise_for_status()  # Check for request errors
        
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extractall(temp_extract_dir)
        
        # Move the patches folder from extracted content to the patches_dir
        extracted_patches_dir = os.path.join(temp_extract_dir, "game-patches-main", "patches")
        if os.path.exists(extracted_patches_dir):
            for item in os.listdir(extracted_patches_dir):
                shutil.move(os.path.join(extracted_patches_dir, item), os.path.join(patches_dir, item))
        
        # Clean up temporary extraction directory
        shutil.rmtree(temp_extract_dir)

        messagebox.showinfo("Info", "Patches updated successfully!")
    except requests.RequestException as e:
        logging.error(f"Error downloading patches: {e}")
        messagebox.showerror("Error", f"Error downloading patches: {e}")
    except zipfile.BadZipFile as e:
        logging.error(f"Error extracting patches: {e}")
        messagebox.showerror("Error", f"Error extracting patches: {e}")



def delete_save_backups():
    clear_directory(os.path.join(SAVE_DATA_DIR, 'Backups', 'cache'))
    clear_directory(os.path.join(SAVE_DATA_DIR, 'Backups', 'content'))
    messagebox.showinfo("Info", "Backups removed!")

def delete_update_backups():
    clear_directory(os.path.join(BASE_DIR, 'Update', 'Backup'))
    os.makedirs(os.path.join(BASE_DIR, 'Update', 'Backup'))
    messagebox.showinfo("Info", "Backups removed!")

def add_new_game():
    config = load_config()
    new_id = str(len(config['games']) + 1)
    name = simpledialog.askstring("Input", "Enter the game name:")
    path = simpledialog.askstring("Input", "Enter the game path:")

    if name and path:
        game_path = os.path.join(CORE_DIR, path)
        if not os.path.exists(game_path):
            os.makedirs(game_path)
        run_xcopy(EXAMPLE_FOLDER, game_path)
               # Handle the config file
        config_file_src = resource_path('defaultconfig.toml')
        config_file_dst = os.path.join(game_path, 'xenia-canary.config.toml')
        if os.path.isfile(config_file_src):
            shutil.copy2(config_file_src, config_file_dst)
        config['games'].append({"id": new_id, "name": name, "path": path})
        save_config(config)
        messagebox.showinfo("Success", "Game added successfully!")
    else:
        messagebox.showerror("Error", "Invalid input!")

def remove_game(game):
    config = load_config()
    game_name = game['name']
    game_path = os.path.join(CORE_DIR, game['path'])
    
    if messagebox.askyesno("Confirm", f"Do you want to remove the game '{game_name}'?"):
        config['games'] = [g for g in config['games'] if g['name'] != game_name]
        save_config(config)
        if messagebox.askyesno("Delete Data", f"Do you want to delete the data for '{game_name}' located at '{game_path}'?"):
            if os.path.exists(game_path):
                clear_directory(game_path)
                messagebox.showinfo("Info", f"Data for '{game_name}' has been deleted.")
            else:
                messagebox.showwarning("Warning", f"Data path '{game_path}' does not exist.")
        messagebox.showinfo("Info", f"'{game_name}' has been removed from the configuration.")
        games_menu()

def edit_config(game_folder):
    toml_path = os.path.join(CORE_DIR, game_folder, TOML_CONFIG_FILE)
    os.startfile(toml_path)
    messagebox.showinfo("Info", f"Opening configuration file: {toml_path}")



if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    style.configure("TButton", padding=6, relief="flat", background="#ccc")
    style.configure("TLabel", padding=6, background="#eee")
    style.configure("TFrame", padding=6, background="#ddd")
    main_menu()
    root.mainloop()
