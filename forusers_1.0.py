import sys
import subprocess
import os
import io

# ==========================================
#   AUTOMATIC DEPENDENCY INSTALLER
# ==========================================
def check_and_install_dependencies():
    required_libraries = {
        "customtkinter": "customtkinter",
        "pynput": "pynput",
        "PIL": "pillow",
        "cv2": "opencv-python",
        "numpy": "numpy"
    }
    missing = []
    for module_name, pip_name in required_libraries.items():
        try:
            if module_name == "cv2": __import__("cv2")
            else: __import__(module_name)
        except ImportError:
            missing.append(pip_name)
            
    if missing:
        print(f"\n[SYSTEM] Missing libraries detected, installing automatically: {missing}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        print("[SYSTEM] All libraries installed successfully!\n")

check_and_install_dependencies()

# ==========================================
#         REQUIRED LIBRARIES
# ==========================================
import customtkinter as ctk
import threading
import time
import sqlite3
import json
import re
import math
import zipfile
import cv2
import numpy as np
import xml.etree.ElementTree as ET
from tkinter import filedialog, messagebox
from datetime import datetime
from pynput.keyboard import Listener, Key
from PIL import Image

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# --- HELPER DATA ACCESS FUNCTIONS (JSON MAPPING) ---
def parts_to_dict(parts, idx):
    action_type = parts[0]
    step_obj = {
        "step_name": f"Step {idx}", "action": "Tap", "xpath": "", "val": "",
        "count": 1, "direction": "Down", "x": 0, "y": 0, "sys_key": "",
        "exact_match": False, "ref": ""
    }
    def safe_get(index, default): return parts[index] if len(parts) > index else default
    
    if action_type == "C":
        step_obj["action"] = "Case"
        step_obj["val"] = safe_get(1, f"Case_{idx}")
    elif action_type == "T":
        step_obj["action"] = "Tap"
        step_obj["xpath"], step_obj["x"], step_obj["y"], step_obj["ref"] = safe_get(1, ""), int(safe_get(2, 0)), int(safe_get(3, 0)), safe_get(4, "")
        step_obj["step_name"] = safe_get(5, f"Tap: {step_obj['xpath'].split('/')[-1][:15]}" if step_obj['xpath'] else f"Step {idx}")
        step_obj["exact_match"] = str(safe_get(6, "False")) == "True"
    elif action_type == "M":
        step_obj["action"] = "Type Text"
        step_obj["xpath"], step_obj["x"], step_obj["y"], step_obj["val"], step_obj["ref"] = safe_get(1, ""), int(safe_get(2, 0)), int(safe_get(3, 0)), safe_get(4, ""), safe_get(5, "")
        step_obj["step_name"] = safe_get(6, f"Type: '{step_obj['val']}'")
        step_obj["exact_match"] = str(safe_get(7, "False")) == "True"
    elif action_type == "S":
        step_obj["action"] = "Swipe"
        direction = safe_get(1, "down")
        step_obj["direction"] = {"down": "Down", "up": "Up", "right": "Right", "left": "Left"}.get(direction, direction)
        step_obj["x"], step_obj["y"] = int(safe_get(2, 0)), int(safe_get(3, 0)) 
        step_obj["ref"] = safe_get(6, "")
        step_obj["step_name"] = safe_get(7, f"Swipe: {step_obj['direction']}")
        step_obj["count"] = int(safe_get(8, 1))
    elif action_type == "K":
        step_obj["action"] = "System Key"
        step_obj["sys_key"] = "Clear Box"
        step_obj["xpath"], step_obj["x"], step_obj["y"], step_obj["ref"] = safe_get(1, ""), int(safe_get(2, 0)), int(safe_get(3, 0)), safe_get(4, "")
        step_obj["step_name"] = safe_get(5, "Clear Content")
        step_obj["exact_match"] = str(safe_get(6, "False")) == "True"
    elif action_type == "SM":
        step_obj["action"] = "Secure Type (Physical)"
        step_obj["xpath"], step_obj["x"], step_obj["y"], step_obj["val"], step_obj["count"], step_obj["ref"] = safe_get(1, ""), int(safe_get(2, 0)), int(safe_get(3, 0)), safe_get(4, ""), int(safe_get(5, 10)), safe_get(6, "")
        step_obj["step_name"] = safe_get(7, f"Secure Type: '{step_obj['val']}'")
        step_obj["exact_match"] = str(safe_get(8, "False")) == "True"
    elif action_type == "SYS":
        step_obj["action"] = "System Key"
        step_obj["sys_key"], step_obj["xpath"], step_obj["x"], step_obj["y"], step_obj["count"], step_obj["ref"] = safe_get(1, "Back"), safe_get(2, ""), int(safe_get(3, 0)), int(safe_get(4, 0)), int(safe_get(5, 1)), safe_get(6, "")
        step_obj["step_name"] = safe_get(7, f"Key: {step_obj['sys_key']}")
        step_obj["exact_match"] = str(safe_get(8, "False")) == "True"
    elif action_type == "W":
        step_obj["action"] = "Sleep"
        step_obj["val"] = safe_get(1, "1")
        step_obj["step_name"] = safe_get(2, f"Sleep: {step_obj['val']} sec")
    elif action_type == "B":
        step_obj["action"] = "Title / Comment"
        step_obj["val"] = safe_get(1, "")
        step_obj["step_name"] = safe_get(2, f"--- {step_obj['val']} ---")
        
    return step_obj

def dict_to_parts(step_obj):
    act = step_obj["action"]
    sn = str(step_obj.get("step_name", "")).replace(";", "").replace("|", "")
    xp = str(step_obj.get("xpath", "")).replace(";", "").replace("|", "")
    x, y = str(step_obj.get("x", 0)), str(step_obj.get("y", 0))
    val = str(step_obj.get("val", "")).replace(";", "").replace("|", "")
    ref = str(step_obj.get("ref", ""))
    em = str(step_obj.get("exact_match", False))
    count = str(step_obj.get("count", 1))
    sysk = str(step_obj.get("sys_key", ""))
    
    if act == "Case": return ["C", val]
    elif act == "Tap": return ["T", xp, x, y, ref, sn, em]
    elif act == "Type Text": return ["M", xp, x, y, val, ref, sn, em]
    elif act == "Swipe":
        direction = {"Down": "down", "Up": "up", "Right": "right", "Left": "left"}.get(step_obj.get("direction"), "down")
        return ["S", direction, x, y, x, y, ref, sn, count]
    elif act == "System Key":
        if sysk == "Clear Box": return ["K", xp, x, y, ref, sn, em]
        else: return ["SYS", sysk, xp, x, y, count, ref, sn, em]
    elif act == "Secure Type (Physical)": return ["SM", xp, x, y, val, count, ref, sn, em]
    elif act == "Sleep": return ["W", val, sn]
    elif act == "Title / Comment": return ["B", val, sn]
    return ["T", xp, x, y, ref, sn, em]

class AppicTestStudio(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Appic - Test Automation Studio")
        self.geometry("1150x750")
        
        if getattr(sys, 'frozen', False): self.main_dir = os.path.dirname(sys.executable)
        else: self.main_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.db_path = os.path.join(self.main_dir, "appic_test_center.db")
        self.adb_path = "adb" 
        
        self.error_folder = os.path.join(self.main_dir, "error_images")
        os.makedirs(self.error_folder, exist_ok=True) 

        self.log_folder = os.path.join(self.main_dir, "test_logs")
        os.makedirs(self.log_folder, exist_ok=True)
        
        self.reference_folder = os.path.join(self.main_dir, "reference_images")
        os.makedirs(self.reference_folder, exist_ok=True)

        self.is_recording = False
        self.is_playing = False
        self.temp_touches = []
        self.keyboard_listener = None
        
        self.ui_w = 360
        self.ui_h = 640
        
        self.active_screen_xml = ""
        self.screen_width = 1080
        self.screen_height = 1920
        
        self.ide_active_steps = []
        self.ide_selected_test_id = None
        self.ide_selected_test_name = ""

        self.get_device_resolution()
        self.prepare_database()

        # --- UI SETUP ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="APPIC", font=ctk.CTkFont(size=24, weight="bold"), text_color="#3498db")
        self.logo_label.pack(pady=20, padx=10)

        self.btn_record_screen = ctk.CTkButton(self.sidebar_frame, text="📸 New Visual Record", command=self.show_record)
        self.btn_record_screen.pack(pady=10, padx=20)
        
        self.btn_ide_screen = ctk.CTkButton(self.sidebar_frame, text="🧩 Visual IDE (Edit)", fg_color="#8e44ad", hover_color="#732d91", command=self.show_ide)
        self.btn_ide_screen.pack(pady=10, padx=20)

        self.btn_list_screen = ctk.CTkButton(self.sidebar_frame, text="📂 Manage Tests", command=self.show_list)
        self.btn_list_screen.pack(pady=10, padx=20)

        self.btn_report_screen = ctk.CTkButton(self.sidebar_frame, text="📊 Test Reports", fg_color="#F4A460", text_color="black", hover_color="#d68b49", command=self.show_reports)
        self.btn_report_screen.pack(pady=10, padx=20)

        self.btn_about = ctk.CTkButton(self.sidebar_frame, text="ℹ️ About", fg_color="#2c3e50", hover_color="#34495e", command=self.show_about)
        self.btn_about.pack(side="bottom", pady=20, padx=20)

        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.start_screen()

    def get_device_resolution(self):
        try:
            c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            result = subprocess.run([self.adb_path, "shell", "wm", "size"], capture_output=True, text=True, creationflags=c_flags)
            match = re.search(r"size:\s*(\d+)x(\d+)", result.stdout)
            if match:
                self.screen_width = int(match.group(1))
                self.screen_height = int(match.group(2))
        except Exception: pass

    def prepare_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS case_bazli_testler (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ana_test_adi TEXT, yetkili TEXT, uygulama TEXT, 
            versiyon TEXT, tarih TEXT, telefon_modeli TEXT, aksiyonlar TEXT)""")
        
        try: cursor.execute("ALTER TABLE case_bazli_testler ADD COLUMN versiyon TEXT")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE case_bazli_testler ADD COLUMN tarih TEXT")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE case_bazli_testler ADD COLUMN telefon_modeli TEXT")
        except sqlite3.OperationalError: pass
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS test_sonuclari (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ana_test_adi TEXT, tarih TEXT,
            toplam_adim INTEGER, basarili_adim INTEGER, genel_durum TEXT, detaylar TEXT)""")
            
        conn.commit()
        conn.close()

    def find_active_app_and_version(self):
        pkg, ver = "", ""
        try:
            c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            res = subprocess.run([self.adb_path, "shell", "dumpsys", "window"], capture_output=True, text=True, creationflags=c_flags)
            match = re.search(r'mCurrentFocus=Window\{.*\s+([\w\.]+)/', res.stdout)
            if match:
                pkg = match.group(1)
                if pkg and pkg not in ["com.android.systemui", "com.android.launcher"]:
                    res2 = subprocess.run([self.adb_path, "shell", "dumpsys", "package", pkg], capture_output=True, text=True, creationflags=c_flags)
                    v_match = re.search(r'versionName=(.*)', res2.stdout)
                    if v_match: ver = v_match.group(1).strip()
        except: pass
        return pkg, ver

    def clear_main_frame(self):
        self.is_recording = False
        self.is_playing = False
        for widget in self.main_frame.winfo_children(): widget.destroy()

    def start_screen(self):
        self.clear_main_frame()
        lbl = ctk.CTkLabel(self.main_frame, text="Welcome to Appic!\n\n1. Use 'New Visual Record' to create a test.\n2. Use 'Visual IDE' to edit your tests.\n3. Compare on device and export script via 'Manage Tests'.", font=("Arial", 16))
        lbl.pack(expand=True)

    def show_about(self):
        self.clear_main_frame()
        ctk.CTkLabel(self.main_frame, text="ℹ️ About", font=("Arial", 22, "bold")).pack(pady=(40, 10))
        info_frame = ctk.CTkFrame(self.main_frame, fg_color="#2c3e50", corner_radius=15)
        info_frame.pack(pady=20, padx=50, fill="x")
        ctk.CTkLabel(info_frame, text="Appic Test Automation Studio", font=("Arial", 18, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(info_frame, text="Version 1.0", font=("Arial", 12)).pack(pady=0)
        person_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        person_frame.pack(pady=(20, 20))
        ctk.CTkLabel(person_frame, text="Developer Contact", font=("Arial", 16, "bold"), text_color="#f1c40f").pack(pady=5)
        ctk.CTkLabel(person_frame, text="For technical issues, bug reports, and app development\nplease contact the development team directly.", font=("Arial", 14), justify="center").pack(pady=5)

    # ==========================================
    #   1. LIVE INSPECTOR AND RECORDING
    # ==========================================
    def show_record(self):
        self.clear_main_frame()
        info_frame = ctk.CTkFrame(self.main_frame, fg_color="#2c3e50")
        info_frame.pack(fill="x", padx=10, pady=(5,10))
        info_text = ("📌 HOW TO USE?\n"
                     "• Left Click: Taps and automatically saves the object's XPath.\n"
                     "• Drag & Drop: Swipes the screen.\n"
                     "• Right Click: Opens the text input or content clear menu for that area.")
        ctk.CTkLabel(info_frame, text=info_text, justify="left", font=("Arial", 13, "bold"), text_color="#f1c40f").pack(pady=10, padx=15, anchor="w")

        form_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        form_frame.pack(fill="x", padx=10, pady=5)
        
        pkg, ver = self.find_active_app_and_version()
        active_user = os.getlogin().capitalize() if hasattr(os, 'getlogin') else "Tester"
        
        self.entry_name = ctk.CTkEntry(form_frame, placeholder_text="Scenario Name", width=180)
        self.entry_name.grid(row=0, column=0, padx=5, pady=2)
        
        self.entry_author = ctk.CTkEntry(form_frame, width=120)
        self.entry_author.insert(0, active_user)
        self.entry_author.grid(row=0, column=1, padx=5, pady=2)
        
        self.entry_app = ctk.CTkEntry(form_frame, width=180)
        self.entry_app.insert(0, pkg if pkg else "App Package")
        self.entry_app.grid(row=0, column=2, padx=5, pady=2)
        
        self.entry_version = ctk.CTkEntry(form_frame, width=100)
        self.entry_version.insert(0, ver if ver else "Version")
        self.entry_version.grid(row=0, column=3, padx=5, pady=2)

        self.entry_device = ctk.CTkEntry(form_frame, placeholder_text="Device Model", width=120)
        self.entry_device.grid(row=0, column=4, padx=5, pady=2)
        
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.pack(pady=5)
        
        self.btn_start = ctk.CTkButton(self.button_frame, text="▶️ START APPIC INSPECTOR", fg_color="green", hover_color="darkgreen", command=self.trigger_record)
        self.btn_start.grid(row=0, column=0, padx=5)
        self.btn_stop = ctk.CTkButton(self.button_frame, text="🛑 Stop Record (ESC)", fg_color="red", state="disabled", command=self.stop_record_process)
        self.btn_stop.grid(row=0, column=1, padx=5)

        content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.screen_frame = ctk.CTkFrame(content_frame, width=self.ui_w+20, fg_color="#1e1e1e")
        self.screen_frame.pack(side="left", fill="y", padx=10, pady=5)
        
        self.lbl_screen = ctk.CTkLabel(self.screen_frame, text="Connecting...", width=self.ui_w, height=self.ui_h, fg_color="#000000")
        self.lbl_screen.pack(pady=10, padx=10)
        
        self.lbl_screen.bind("<Button-1>", self.left_click_pressed)
        self.lbl_screen.bind("<ButtonRelease-1>", self.left_click_released)
        self.lbl_screen.bind("<Button-2>", self.right_click_menu)
        self.lbl_screen.bind("<Button-3>", self.right_click_menu)
        
        self.log_box = ctk.CTkTextbox(content_frame, height=560)
        self.log_box.pack(side="right", fill="both", expand=True, pady=10, padx=10)
        self.log_box.insert("0.0", "Appic is ready. Your actions will be saved as XML XPaths.\n")

    def screen_stream_loop(self):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        temp_img_path = os.path.join(self.error_folder, "temp_live_screen.png")
        while self.is_recording:
            try:
                subprocess.run([self.adb_path, "shell", "screencap", "-p", "/sdcard/temp_live.png"], capture_output=True, creationflags=c_flags)
                subprocess.run([self.adb_path, "pull", "/sdcard/temp_live.png", temp_img_path], capture_output=True, creationflags=c_flags)
                if os.path.exists(temp_img_path):
                    with open(temp_img_path, "rb") as f:
                        img_data = f.read()
                    if img_data:
                        img = Image.open(io.BytesIO(img_data))
                        img_resized = img.resize((self.ui_w, self.ui_h))
                        ctk_img = ctk.CTkImage(light_image=img_resized, dark_image=img_resized, size=(self.ui_w, self.ui_h))
                        self.after(0, lambda resim=ctk_img: self.lbl_screen.configure(image=resim, text=""))
            except Exception as e:
                self.after(0, lambda err=e: self.write_log(f"⚠️ Screen stream error: {err}"))
            time.sleep(0.3)

    def fetch_current_xml_once(self):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            subprocess.run([self.adb_path, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], capture_output=True, creationflags=c_flags)
            xml_data = subprocess.check_output([self.adb_path, "shell", "cat", "/sdcard/window_dump.xml"], creationflags=c_flags).decode('utf-8', errors='ignore')
            self.active_screen_xml = xml_data
        except Exception: pass

    def find_xpath_target(self, real_x, real_y):
        self.fetch_current_xml_once()
        if not self.active_screen_xml: return "//android.view.View"
        try:
            root = ET.fromstring(self.active_screen_xml)
            min_area = float('inf')
            final_target = None
            TOLERANCE = 30
            for elem in root.iter():
                bounds = elem.attrib.get('bounds')
                if bounds:
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        if (x1 - TOLERANCE) <= real_x <= (x2 + TOLERANCE) and (y1 - TOLERANCE) <= real_y <= (y2 + TOLERANCE):
                            area = (x2 - x1) * (y2 - y1)
                            if 0 < area < min_area:
                                min_area = area
                                final_target = elem.attrib
            if final_target:
                if final_target.get('resource-id'): return f"//*[@resource-id='{final_target.get('resource-id')}']"
                elif final_target.get('text'): return f"//*[@text='{final_target.get('text')}']"
                elif final_target.get('content-desc'): return f"//*[@content-desc='{final_target.get('content-desc')}']"
                else: 
                    cls = final_target.get('class', 'android.view.View')
                    bnd = final_target.get('bounds')
                    return f"//{cls}[@bounds='{bnd}']"
        except Exception: pass
        return "//android.view.View"

    def take_reference_screen(self):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        time_ms = int(time.time() * 1000)
        ref_name = f"ref_{time_ms}.png"
        ref_path = os.path.join(self.reference_folder, ref_name)
        subprocess.run([self.adb_path, "shell", "screencap", "-p", "/sdcard/temp_ref.png"], capture_output=True, creationflags=c_flags)
        subprocess.run([self.adb_path, "pull", "/sdcard/temp_ref.png", ref_path], capture_output=True, creationflags=c_flags)
        return ref_name

    def left_click_pressed(self, event):
        if not self.is_recording: return
        self.press_x = event.x
        self.press_y = event.y

    def left_click_released(self, event):
        if not self.is_recording: return
        end_x = event.x
        end_y = event.y
        distance = math.hypot(end_x - getattr(self, 'press_x', 0), end_y - getattr(self, 'press_y', 0))
        
        real_x = int((end_x / self.ui_w) * self.screen_width)
        real_y = int((end_y / self.ui_h) * self.screen_height)
        real_press_x = int((getattr(self, 'press_x', 0) / self.ui_w) * self.screen_width)
        real_press_y = int((getattr(self, 'press_y', 0) / self.ui_h) * self.screen_height)
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        if distance < 30:
            self.after(0, lambda: self.write_log("🔍 Scanning object..."))
            def perform_action():
                xpath = self.find_xpath_target(real_x, real_y)
                subprocess.run([self.adb_path, "shell", "input", "tap", str(real_x), str(real_y)], creationflags=c_flags)
                time.sleep(1.5)
                ref_name = self.take_reference_screen()
                # T;;;xpath;;;x;;;y;;;ref;;;step_name;;;exact_match
                sn = f"Tap: {xpath.split('/')[-1][:15]}" if xpath else "Step"
                em = "True" if xpath.startswith("//") else "False"
                self.temp_touches.append(f"T;;;{xpath};;;{real_x};;;{real_y};;;{ref_name};;;{sn};;;{em}") 
                self.after(0, lambda: self.write_log(f"🎯 Tap (XPath): {xpath}"))
            threading.Thread(target=perform_action).start()
        else:
            diff_x = end_x - getattr(self, 'press_x', 0)
            diff_y = end_y - getattr(self, 'press_y', 0)
            direction = "down" if diff_y > 0 else "up"
            if abs(diff_x) > abs(diff_y): direction = "right" if diff_x > 0 else "left"
            def perform_swipe():
                subprocess.run([self.adb_path, "shell", "input", "swipe", str(real_press_x), str(real_press_y), str(real_x), str(real_y), "400"], creationflags=c_flags)
                time.sleep(1.5)
                ref_name = self.take_reference_screen()
                direction_en = {"down": "Down", "up": "Up", "right": "Right", "left": "Left"}.get(direction, "Down")
                # S;;;direction;;;x;;;y;;;x;;;y;;;ref;;;step_name;;;count
                self.temp_touches.append(f"S;;;{direction};;;{real_press_x};;;{real_press_y};;;{real_x};;;{real_y};;;{ref_name};;;Swipe: {direction_en};;;1")
                self.after(0, lambda: self.write_log(f"👆 Swipe Added: {direction_en}"))
            threading.Thread(target=perform_swipe).start()

    def right_click_menu(self, event):
        if not self.is_recording: return
        real_x = int((event.x / self.ui_w) * self.screen_width)
        real_y = int((event.y / self.ui_h) * self.screen_height)
        self.after(0, lambda: self.write_log("🔍 Scanning text box..."))
        def prepare_menu():
            xpath = self.find_xpath_target(real_x, real_y)
            self.after(0, lambda: self._open_popup(real_x, real_y, xpath))
        threading.Thread(target=prepare_menu).start()

    def _open_popup(self, real_x, real_y, xpath):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        popup = ctk.CTkToplevel(self)
        popup.title("Box Actions")
        popup.geometry("300x200")
        popup.attributes("-topmost", True)
        data_entry = ctk.CTkEntry(popup, placeholder_text="Text to type...", width=200)
        data_entry.pack(pady=20)
        
        def type_text():
            val = data_entry.get().replace(";", "").replace("|", "")
            if not val: return
            popup.destroy()
            def write_to_device():
                subprocess.run([self.adb_path, "shell", "input", "tap", str(real_x), str(real_y)], creationflags=c_flags)
                time.sleep(0.5)
                subprocess.run([self.adb_path, "shell", "input", "text", str(val)], creationflags=c_flags)
                time.sleep(1.5)
                ref_name = self.take_reference_screen()
                em = "True" if xpath.startswith("//") else "False"
                # M;;;xpath;;;x;;;y;;;val;;;ref;;;step_name;;;exact_match
                self.temp_touches.append(f"M;;;{xpath};;;{real_x};;;{real_y};;;{val};;;{ref_name};;;Type: '{val}';;;{em}")
                self.after(0, lambda: self.write_log(f"✍️ Text Added: '{val}'"))
            threading.Thread(target=write_to_device).start()
            
        def clear_text():
            popup.destroy()
            def delete_from_device():
                subprocess.run([self.adb_path, "shell", "input", "tap", str(real_x), str(real_y)], creationflags=c_flags)
                time.sleep(0.5)
                subprocess.run([self.adb_path, "shell", "input", "keyevent", "123"], creationflags=c_flags)
                for _ in range(25): subprocess.run([self.adb_path, "shell", "input", "keyevent", "67"], creationflags=c_flags)
                time.sleep(1.5)
                ref_name = self.take_reference_screen()
                em = "True" if xpath.startswith("//") else "False"
                # K;;;xpath;;;x;;;y;;;ref;;;step_name;;;exact_match
                self.temp_touches.append(f"K;;;{xpath};;;{real_x};;;{real_y};;;{ref_name};;;Clear Content;;;{em}")
                self.after(0, lambda: self.write_log(f"🧹 Clear Action Added"))
            threading.Thread(target=delete_from_device).start()

        ctk.CTkButton(popup, text="✍️ Type Text", fg_color="green", command=type_text).pack(pady=5)
        ctk.CTkButton(popup, text="🧹 Clear Content", fg_color="red", command=clear_text).pack(pady=5)

    def trigger_record(self):
        self.current_test_name = self.entry_name.get()
        if not self.current_test_name:
            self.write_log("\n❌ Please enter a Scenario Name!")
            return

        self.current_author = self.entry_author.get()
        self.current_app = self.entry_app.get()
        self.current_version = self.entry_version.get()
        self.current_device = self.entry_device.get()
        self.current_date = datetime.now().strftime("%d-%m-%Y %H:%M")

        self.get_device_resolution()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        
        self.is_recording = True
        self.temp_touches = []
        
        self.write_log(f"\n🚀 '{self.current_test_name}' Appic is active!\nYou can record steps by clicking on the screen.")
        threading.Thread(target=self.screen_stream_loop, daemon=True).start()
        if self.keyboard_listener: self.keyboard_listener.stop()
        self.keyboard_listener = Listener(on_press=self.listen_keyboard)
        self.keyboard_listener.start()

    def listen_keyboard(self, key):
        if not self.is_recording: return 
        if key == Key.esc: self.after(0, self.stop_record_process)

    def stop_record_process(self):
        self.is_recording = False
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
            
        if self.temp_touches:
            copy_touches = list(self.temp_touches)
            action_str = "|".join(copy_touches)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO case_bazli_testler 
                              (ana_test_adi, yetkili, uygulama, versiyon, tarih, telefon_modeli, aksiyonlar) 
                              VALUES (?,?,?,?,?,?,?)""", 
                           (self.current_test_name, self.current_author, self.current_app, self.current_version, self.current_date, self.current_device, action_str))
            conn.commit()
            conn.close()
            
        try:
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.write_log("\n🎉 RECORDING COMPLETED! You can edit from Visual IDE or export from Manage tab.\n")
        except Exception: pass

    def write_log(self, message):
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")

    # ==========================================
    #   2. VISUAL IDE (EDITOR)
    # ==========================================
    def show_ide(self):
        self.clear_main_frame()
        ctk.CTkLabel(self.main_frame, text="🧩 Visual IDE (Test Editor)", font=("Arial", 18, "bold")).pack(pady=10)
        
        top_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        top_frame.pack(fill="x", padx=10, pady=5)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, ana_test_adi FROM case_bazli_testler ORDER BY id DESC")
        tests = cursor.fetchall()
        conn.close()
        
        self.test_dict = {f"{t[1]} (ID:{t[0]})": t[0] for t in tests}
        test_names = list(self.test_dict.keys())
        
        if not test_names:
            ctk.CTkLabel(top_frame, text="No saved tests yet. Please record a test first.").pack()
            return

        self.ide_selected_test_id = None
        self.ide_active_steps = []
            
        self.combo_test = ctk.CTkComboBox(top_frame, values=test_names, width=250, command=self.ide_load_test)
        self.combo_test.pack(side="left", padx=10)
        
        ctk.CTkButton(top_frame, text="➕ Add Case", width=120, fg_color="#8e44ad", hover_color="#732d91", command=self.ide_add_case_popup).pack(side="left", padx=5)
        ctk.CTkButton(top_frame, text="➕ Add Block", width=100, fg_color="#f39c12", text_color="black", hover_color="#d68b49", command=self.ide_add_block_popup).pack(side="left", padx=5)
        
        ctk.CTkButton(top_frame, text="📤 Save & Export", fg_color="#2980b9", hover_color="#1f618d", command=self.ide_save_and_export).pack(side="right", padx=5)
        ctk.CTkButton(top_frame, text="💾 Save Only", fg_color="green", hover_color="darkgreen", command=self.ide_save).pack(side="right", padx=5)
        
        self.ide_list_frame = ctk.CTkScrollableFrame(self.main_frame)
        self.ide_list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.ide_load_test(test_names[0])

    def ide_load_test(self, selection):
        test_id = self.test_dict[selection]
        self.ide_selected_test_id = test_id
        self.ide_selected_test_name = selection.split(" (ID:")[0]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT aksiyonlar FROM case_bazli_testler WHERE id = ?", (test_id,))
        row = cursor.fetchone()
        conn.close()
        
        self.ide_active_steps = []
        if row and row[0]:
            touches = [n for n in row[0].split("|") if n]
            for idx, d in enumerate(touches):
                parts = d.split(";;;")
                self.ide_active_steps.append(parts_to_dict(parts, idx+1))
        self.ide_draw_interface()

    def ide_add_case_popup(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Add New Case")
        popup.geometry("300x150")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text="Case Name:", font=("Arial", 12, "bold")).pack(pady=(15,5))
        entry_name = ctk.CTkEntry(popup, width=200)
        entry_name.pack(pady=5)
        
        def add():
            name = entry_name.get().replace(";", "").replace("|", "")
            if name:
                self.ide_active_steps.append({"action": "Case", "val": name})
                self.ide_draw_interface()
            popup.destroy()
            
        ctk.CTkButton(popup, text="Add", fg_color="green", command=add).pack(pady=10)

    def ide_add_block_popup(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Add New Block")
        popup.geometry("400x500")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text="Action Type:", font=("Arial", 12, "bold")).pack(pady=(10,0))
        combo_act = ctk.CTkComboBox(popup, values=["Tap", "Type Text", "Secure Type (Physical)", "Swipe", "System Key", "Sleep", "Title / Comment"], width=300)
        combo_act.pack(pady=5)
        
        ctk.CTkLabel(popup, text="Step Name:", font=("Arial", 12)).pack()
        e_name = ctk.CTkEntry(popup, width=300)
        e_name.pack(pady=5)
        
        ctk.CTkLabel(popup, text="Target XPath / Text Value:", font=("Arial", 12)).pack()
        e_xp = ctk.CTkEntry(popup, width=300)
        e_xp.pack(pady=5)
        
        ctk.CTkLabel(popup, text="Value / Direction / Seconds / Key:", font=("Arial", 12)).pack()
        e_val = ctk.CTkEntry(popup, width=300)
        e_val.pack(pady=5)
        
        ctk.CTkLabel(popup, text="Repeat (Count):", font=("Arial", 12)).pack()
        e_count = ctk.CTkEntry(popup, width=100)
        e_count.insert(0, "1")
        e_count.pack(pady=5)
        
        chk_exact = ctk.CTkCheckBox(popup, text="Exact Match")
        chk_exact.pack(pady=10)
        
        def add():
            act = combo_act.get()
            step_obj = {
                "step_name": e_name.get().replace(";", ""),
                "action": act,
                "xpath": e_xp.get().replace(";", ""),
                "val": e_val.get().replace(";", ""),
                "count": int(e_count.get()) if e_count.get().isdigit() else 1,
                "direction": e_val.get() if act == "Swipe" else "Down",
                "sys_key": e_val.get() if act == "System Key" else "",
                "x": 0, "y": 0, "ref": "",
                "exact_match": chk_exact.get() == 1
            }
            if not step_obj["step_name"]: step_obj["step_name"] = act
            self.ide_active_steps.append(step_obj)
            self.ide_draw_interface()
            popup.destroy()
            
        ctk.CTkButton(popup, text="Add", fg_color="green", command=add).pack(pady=15)

    def ide_draw_interface(self):
        for widget in self.ide_list_frame.winfo_children(): widget.destroy()
        if not self.ide_active_steps: return

        for idx, step in enumerate(self.ide_active_steps):
            act = step["action"]
            s_name = step.get("step_name", f"Step {idx}")
            
            color, icon, detail = "#8A9BAC", "⚙️", ""
            
            if act == "Case":
                color, icon = "#FF6680", "⚙️ CASE:"
                s_name = f"{icon} {step.get('val', '')}"
                
                row_frame = ctk.CTkFrame(self.ide_list_frame, fg_color=color, corner_radius=10)
                row_frame.pack(fill="x", pady=(15, 2), padx=5)
                ctk.CTkLabel(row_frame, text=s_name, font=("Arial", 16, "bold"), text_color="white").pack(side="left", padx=15, pady=10)
                ctk.CTkButton(row_frame, text="🗑️", width=40, fg_color="#c0392b", hover_color="#962d22", command=lambda i=idx: self.ide_delete_step(i)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(row_frame, text="✏️", width=40, fg_color="#f39c12", text_color="black", hover_color="#d68b49", command=lambda i=idx: self.ide_edit_step(i)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(row_frame, text="⬇️", width=40, fg_color="#34495e", command=lambda i=idx: self.ide_move_step(i, 1), state="disabled" if idx == len(self.ide_active_steps)-1 else "normal").pack(side="right", padx=2, pady=10)
                ctk.CTkButton(row_frame, text="⬆️", width=40, fg_color="#34495e", command=lambda i=idx: self.ide_move_step(i, -1), state="disabled" if idx == 0 else "normal").pack(side="right", padx=2, pady=10)
                continue
                
            elif act == "Tap": 
                color, icon = "#4C97FF", "👆"
                detail = f"[{step.get('xpath')[:20]}]" if step.get('xpath') else f"Coord({step.get('x')},{step.get('y')})"
            elif act == "Type Text": 
                color, icon = "#59C059", "⌨️"
                detail = f"Type: '{step.get('val')}'"
            elif act == "Secure Type (Physical)": 
                color, icon = "#D35400", "🤖"
                detail = f"Sec. Type: '{step.get('val')}'"
            elif act == "Swipe": 
                color, icon = "#FFBF00", "↔️"
                detail = f"Dir: {step.get('direction')}"
            elif act == "Sleep": 
                color, icon = "#9966FF", "⏳"
                detail = f"Duration: {step.get('val')}s"
            elif act == "Title / Comment": 
                color, icon = "#34495E", "📝"
                detail = step.get("val")
            elif act == "System Key": 
                if step.get("sys_key") == "Clear Box": color, icon, detail = "#E74C3C", "🧹", "Clear Content"
                elif step.get("sys_key") == "Physical Delete (Backspace)": color, icon, detail = "#E74C3C", "🔙", "Physical Delete"
                else: color, icon, detail = "#8A9BAC", "📱", f"Key: {step.get('sys_key')}"

            if step.get("exact_match"): detail += " 🔒 Exact"

            row_frame = ctk.CTkFrame(self.ide_list_frame, fg_color=color, corner_radius=8)
            row_frame.pack(fill="x", pady=2, padx=20)
            
            ctk.CTkLabel(row_frame, text=f"{icon} {s_name} | {detail}", font=("Arial", 14, "bold"), text_color="white").pack(side="left", padx=15, pady=10)
            ctk.CTkButton(row_frame, text="🗑️", width=40, fg_color="#c0392b", hover_color="#962d22", command=lambda i=idx: self.ide_delete_step(i)).pack(side="right", padx=5, pady=10)
            ctk.CTkButton(row_frame, text="✏️ Edit", width=100, fg_color="#f39c12", text_color="black", hover_color="#d68b49", command=lambda i=idx: self.ide_edit_step(i)).pack(side="right", padx=5, pady=10)
            ctk.CTkButton(row_frame, text="⬇️", width=40, fg_color="#34495e", command=lambda i=idx: self.ide_move_step(i, 1), state="disabled" if idx == len(self.ide_active_steps)-1 else "normal").pack(side="right", padx=2, pady=10)
            ctk.CTkButton(row_frame, text="⬆️", width=40, fg_color="#34495e", command=lambda i=idx: self.ide_move_step(i, -1), state="disabled" if idx == 0 else "normal").pack(side="right", padx=2, pady=10)

    def ide_move_step(self, idx, direction):
        new_idx = idx + direction
        self.ide_active_steps[idx], self.ide_active_steps[new_idx] = self.ide_active_steps[new_idx], self.ide_active_steps[idx]
        self.ide_draw_interface()

    def ide_delete_step(self, idx):
        self.ide_active_steps.pop(idx)
        self.ide_draw_interface()

    def ide_edit_step(self, idx):
        step = self.ide_active_steps[idx]
        act = step["action"]
        
        popup = ctk.CTkToplevel(self)
        popup.title(f"Edit: {act}")
        popup.geometry("400x500")
        popup.attributes("-topmost", True)
        
        if act == "Case":
            ctk.CTkLabel(popup, text="Case Name:").pack(pady=5)
            e_name = ctk.CTkEntry(popup, width=300)
            e_name.insert(0, step.get("val", ""))
            e_name.pack(pady=5)
            def save():
                step["val"] = e_name.get()
                self.ide_active_steps[idx] = step
                popup.destroy()
                self.ide_draw_interface()
            ctk.CTkButton(popup, text="💾 Update", fg_color="green", command=save).pack(pady=20)
            return

        ctk.CTkLabel(popup, text="Step Name:").pack(pady=5)
        e_name = ctk.CTkEntry(popup, width=300)
        e_name.insert(0, step.get("step_name", ""))
        e_name.pack(pady=5)
        
        e_xp, e_val, e_count, chk_em = None, None, None, None
        
        if act in ["Tap", "Type Text", "Secure Type (Physical)", "System Key"]:
            ctk.CTkLabel(popup, text="XPath / ID:").pack(pady=5)
            e_xp = ctk.CTkEntry(popup, width=300)
            e_xp.insert(0, step.get("xpath", ""))
            e_xp.pack(pady=5)
            
            chk_em = ctk.CTkCheckBox(popup, text="Exact Match")
            if step.get("exact_match"): chk_em.select()
            chk_em.pack(pady=5)
            
        if act in ["Type Text", "Secure Type (Physical)", "Sleep", "Title / Comment", "Swipe", "System Key"]:
            l_text = "Value / Seconds:"
            if act == "Swipe": l_text = "Direction (Down, Up, Right, Left):"
            elif act == "System Key": l_text = "Key (Back, Home, Clear Box):"
            
            ctk.CTkLabel(popup, text=l_text).pack(pady=5)
            e_val = ctk.CTkEntry(popup, width=300)
            v_ins = step.get("val", "")
            if act == "Swipe": v_ins = step.get("direction", "Down")
            elif act == "System Key": v_ins = step.get("sys_key", "")
            e_val.insert(0, v_ins)
            e_val.pack(pady=5)
            
        if act in ["Secure Type (Physical)", "Swipe"] or (act == "System Key" and step.get("sys_key") == "Physical Delete (Backspace)"):
            ctk.CTkLabel(popup, text="Repeat (Count):").pack(pady=5)
            e_count = ctk.CTkEntry(popup, width=100)
            e_count.insert(0, str(step.get("count", 1)))
            e_count.pack(pady=5)
            
        def save():
            step["step_name"] = e_name.get().replace(";", "").replace("|", "")
            if e_xp: step["xpath"] = e_xp.get().replace(";", "")
            if e_val:
                v = e_val.get().replace(";", "")
                if act == "Swipe": step["direction"] = v
                elif act == "System Key": step["sys_key"] = v
                else: step["val"] = v
            if e_count: step["count"] = int(e_count.get()) if e_count.get().isdigit() else 1
            if chk_em: step["exact_match"] = chk_em.get() == 1
            
            self.ide_active_steps[idx] = step
            popup.destroy()
            self.ide_draw_interface()
            
        ctk.CTkButton(popup, text="💾 Update", fg_color="green", command=save).pack(pady=20)

    def ide_save(self, silent=False):
        if not self.ide_selected_test_id: return
        new_actions = "|".join([";;;".join(dict_to_parts(s)) for s in self.ide_active_steps])
        conn = sqlite3.connect(self.db_path)
        conn.cursor().execute("UPDATE case_bazli_testler SET aksiyonlar = ? WHERE id = ?", (new_actions, self.ide_selected_test_id))
        conn.commit()
        conn.close()
        if not silent: messagebox.showinfo("Success", "Test scenario updated successfully!")

    def ide_save_and_export(self):
        if not self.ide_selected_test_id: return
        self.ide_save(silent=True)
        self.export_test(self.ide_selected_test_id, self.ide_selected_test_name)

    # ==========================================
    #   3. MANAGEMENT AND LOCAL PLAYBACK
    # ==========================================
    def show_list(self):
        self.clear_main_frame()
        ctk.CTkLabel(self.main_frame, text="📂 Manage Saved Tests", font=("Arial", 18, "bold")).pack(pady=10)
        
        top_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        top_frame.pack(pady=5, fill="x", padx=10)
        self.search_entry = ctk.CTkEntry(top_frame, placeholder_text="Search by Test Name...", width=400)
        self.search_entry.pack(side="left", padx=10)
        self.search_entry.bind("<KeyRelease>", self.update_list)

        self.test_list = ctk.CTkScrollableFrame(self.main_frame, width=800, height=450)
        self.test_list.pack(pady=10, padx=10, fill="both", expand=True)
        self.update_list()

    def update_list(self, event=None):
        for widget in self.test_list.winfo_children(): widget.destroy()
        if not os.path.exists(self.db_path): return
        search = self.search_entry.get().strip()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, ana_test_adi, yetkili, uygulama, versiyon, tarih FROM case_bazli_testler WHERE ana_test_adi LIKE ? ORDER BY id DESC", (f'%{search}%',))
            records = cursor.fetchall()
            conn.close()

            for t_id, test_name, author, app, ver, date in records:
                row_frame = ctk.CTkFrame(self.test_list, fg_color="#2b2b2b")
                row_frame.pack(fill="x", pady=5, padx=5)
                
                info_text = f"📂 {test_name}  |  👤 {author}  |  📱 {app} (v{ver})  |  🕒 {date}"
                ctk.CTkLabel(row_frame, text=info_text, font=("Arial", 13, "bold")).pack(side="left", padx=15, pady=10)
                
                ctk.CTkButton(row_frame, text="🗑️ Delete", width=60, fg_color="#c0392b", hover_color="#962d22", command=lambda i=t_id: self.delete_test(i)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(row_frame, text="▶️ Play & Compare", width=160, fg_color="green", command=lambda i=t_id, a=test_name: self.play_test(i, a)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(row_frame, text="📤 Export Script", width=140, fg_color="#2980b9", command=lambda i=t_id, a=test_name: self.export_test(i, a)).pack(side="right", padx=5, pady=10)
        except Exception: pass

    def delete_test(self, t_id):
        answer = messagebox.askyesno("Confirm", "Are you sure you want to delete this test?")
        if answer:
            conn = sqlite3.connect(self.db_path)
            conn.cursor().execute("DELETE FROM case_bazli_testler WHERE id = ?", (t_id,))
            conn.commit()
            conn.close()
            self.update_list()

    def stop_playback(self):
        self.is_playing = False

    def compare_images(self, ref_path, check_path):
        try:
            img_ref_color = cv2.imdecode(np.fromfile(ref_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            img_check_color = cv2.imdecode(np.fromfile(check_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img_ref_color is None or img_check_color is None: return 0.0, check_path
            img1 = cv2.cvtColor(img_ref_color, cv2.COLOR_BGR2GRAY)
            img2 = cv2.cvtColor(img_check_color, cv2.COLOR_BGR2GRAY)
            if img1.shape != img2.shape:
                img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
                img_check_color = cv2.resize(img_check_color, (img1.shape[1], img1.shape[0]))
            diff = cv2.absdiff(img1, img2)
            _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                if cv2.contourArea(c) > 100: 
                    x, y, w, h = cv2.boundingRect(c)
                    cv2.rectangle(img_check_color, (x, y), (x+w, y+h), (0, 0, 255), 3) 
            diff_pixels = cv2.countNonZero(thresh)
            total_pixels = img1.shape[0] * img1.shape[1]
            similarity = 1.0 - (diff_pixels / total_pixels)
            diff_path = os.path.join(self.error_folder, "temp_diff.png")
            is_success, im_buf_arr = cv2.imencode(".png", img_check_color)
            if is_success: im_buf_arr.tofile(diff_path)
            else: cv2.imwrite(diff_path, img_check_color)
            return similarity, diff_path
        except Exception: return 0.0, check_path

    def update_ui_images(self, ref_path, check_path, score_percent):
        try:
            img_ref = Image.open(ref_path)
            img_check = Image.open(check_path)
            ratio = 480 / img_ref.height
            new_size = (int(img_ref.width * ratio), 480)
            ctk_ref = ctk.CTkImage(light_image=img_ref, size=new_size)
            ctk_check = ctk.CTkImage(light_image=img_check, size=new_size)
            self.lbl_img_ref.configure(image=ctk_ref, text="")
            self.lbl_img_check.configure(image=ctk_check, text="")
            color = "lightgreen" if score_percent >= 85 else "#ff4d4d"
            self.lbl_similarity.configure(text=f"Analyzed Similarity: {score_percent}%", text_color=color)
        except Exception: pass

    def play_test(self, t_id, test_name):
        self.is_playing = True
        self.play_window = ctk.CTkToplevel(self)
        self.play_window.title(f"Executing Test: {test_name}")
        self.play_window.geometry("1100x650")
        self.play_window.attributes("-topmost", True)
        
        log_frame = ctk.CTkFrame(self.play_window, width=350)
        log_frame.pack(side="left", fill="y", padx=10, pady=10)
        btn_stop = ctk.CTkButton(log_frame, text="🛑 EMERGENCY STOP", fg_color="red", command=self.stop_playback)
        btn_stop.pack(pady=10)
        log_box = ctk.CTkTextbox(log_frame, width=350, font=("Consolas", 12))
        log_box.pack(fill="both", expand=True, padx=5, pady=5)
        log_box.insert("end", f"🚀 {test_name} is starting...\n\n")

        img_frame = ctk.CTkFrame(self.play_window)
        img_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        title_frame = ctk.CTkFrame(img_frame, fg_color="transparent")
        title_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(title_frame, text="Expected (Reference)", font=("Arial", 14, "bold")).pack(side="left", expand=True)
        ctk.CTkLabel(title_frame, text="Current Device (Errors Marked)", font=("Arial", 14, "bold")).pack(side="right", expand=True)
        
        images_container = ctk.CTkFrame(img_frame, fg_color="transparent")
        images_container.pack(fill="both", expand=True, pady=5)
        self.lbl_img_ref = ctk.CTkLabel(images_container, text="⏳ Waiting for Test...", width=300, height=480, fg_color="#2b2b2b")
        self.lbl_img_ref.pack(side="left", expand=True, padx=10)
        self.lbl_img_check = ctk.CTkLabel(images_container, text="⏳ Waiting for Test...", width=300, height=480, fg_color="#2b2b2b")
        self.lbl_img_check.pack(side="right", expand=True, padx=10)
        self.lbl_similarity = ctk.CTkLabel(img_frame, text="Similarity: Waiting for Analysis...", font=("Arial", 18, "bold"))
        self.lbl_similarity.pack(pady=10)

        def playback_loop():
            c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT aksiyonlar FROM case_bazli_testler WHERE id = ?", (t_id,))
            action_data = cursor.fetchone()
            conn.close()
            
            if not action_data or not action_data[0]:
                self.after(0, lambda: log_box.insert("end", "⚠️ No saved steps found."))
                return

            touches = [n for n in action_data[0].split("|") if n]
            
            real_steps = [d for d in touches if not d.startswith("C;;;") and not d.startswith("B;;;")]
            success_count = 0
            total_count = len(real_steps)
            step_reports = []
            loop_cancelled = False
            
            log_file_name = f"log_{test_name.replace(' ', '_')}_{int(time.time())}.txt"
            log_path = os.path.join(self.log_folder, log_file_name)
            subprocess.run([self.adb_path, "logcat", "-c"], creationflags=c_flags)
            log_file = open(log_path, "w", encoding="utf-8")
            log_proc = subprocess.Popen([self.adb_path, "logcat", "-v", "threadtime"], stdout=log_file, creationflags=c_flags)

            action_index = 0
            for idx, point in enumerate(touches):
                if not self.is_playing:
                    self.after(0, lambda: log_box.insert("end", "\n🛑 TEST CANCELLED BY USER!"))
                    loop_cancelled = True
                    break

                parts = point.split(";;;")
                step_obj = parts_to_dict(parts, idx+1)
                act = step_obj["action"]
                
                if act == "Case":
                    self.after(0, lambda p=step_obj["val"]: log_box.insert("end", f"\n--- CASE: {p} ---\n"))
                    continue
                elif act == "Title / Comment":
                    self.after(0, lambda p=step_obj["val"]: log_box.insert("end", f"\n📝 {p}\n"))
                    continue
                    
                action_index += 1
                ref_name = step_obj.get("ref", "")
                
                if act == "Tap":
                    x, y = step_obj["x"], step_obj["y"]
                    self.after(0, lambda i=action_index, n=step_obj["step_name"]: log_box.insert("end", f"[{i}] {n}\n"))
                    subprocess.run([self.adb_path, "shell", "input", "tap", str(x), str(y)], creationflags=c_flags)
                elif act == "Type Text":
                    x, y, val = step_obj["x"], step_obj["y"], step_obj["val"]
                    self.after(0, lambda i=action_index, n=step_obj["step_name"]: log_box.insert("end", f"[{i}] {n}\n"))
                    subprocess.run([self.adb_path, "shell", "input", "tap", str(x), str(y)], creationflags=c_flags)
                    time.sleep(0.5)
                    subprocess.run([self.adb_path, "shell", "input", "text", str(val)], creationflags=c_flags)
                elif act == "Secure Type (Physical)":
                    x, y, val, count = step_obj["x"], step_obj["y"], step_obj["val"], step_obj["count"]
                    self.after(0, lambda i=action_index, n=step_obj["step_name"]: log_box.insert("end", f"[{i}] {n}\n"))
                    subprocess.run([self.adb_path, "shell", "input", "tap", str(x), str(y)], creationflags=c_flags)
                    time.sleep(0.5)
                    subprocess.run([self.adb_path, "shell", "input", "keyevent", "123"], creationflags=c_flags)
                    for _ in range(count): subprocess.run([self.adb_path, "shell", "input", "keyevent", "67"], creationflags=c_flags)
                    time.sleep(0.5)
                    subprocess.run([self.adb_path, "shell", "input", "text", str(val)], creationflags=c_flags)
                elif act == "Swipe":
                    self.after(0, lambda i=action_index, n=step_obj["step_name"]: log_box.insert("end", f"[{i}] {n}\n"))
                    for _ in range(step_obj.get("count", 1)):
                        b_x, b_y, s_x, s_y = self.screen_width//2, self.screen_height//2, self.screen_width//2, self.screen_height//2
                        off_x, off_y = self.screen_width//4, self.screen_height//4
                        direction = step_obj["direction"]
                        if direction == "Down": b_y += off_y; s_y -= off_y
                        elif direction == "Up": b_y -= off_y; s_y += off_y
                        elif direction == "Right": b_x -= off_x; s_x += off_x
                        elif direction == "Left": b_x += off_x; s_x -= off_x
                        subprocess.run([self.adb_path, "shell", "input", "swipe", str(b_x), str(b_y), str(s_x), str(s_y), "400"], creationflags=c_flags)
                        time.sleep(0.5)
                elif act == "System Key":
                    sysk = step_obj["sys_key"]
                    self.after(0, lambda i=action_index, n=step_obj["step_name"]: log_box.insert("end", f"[{i}] {n}\n"))
                    if sysk == "Back": subprocess.run([self.adb_path, "shell", "input", "keyevent", "4"], creationflags=c_flags)
                    elif sysk == "Home": subprocess.run([self.adb_path, "shell", "input", "keyevent", "3"], creationflags=c_flags)
                    elif sysk == "Background": subprocess.run([self.adb_path, "shell", "input", "keyevent", "187"], creationflags=c_flags)
                    elif sysk == "Hide Keyboard": subprocess.run([self.adb_path, "shell", "input", "keyevent", "111"], creationflags=c_flags)
                    elif sysk == "Clear Box":
                        subprocess.run([self.adb_path, "shell", "input", "tap", str(step_obj["x"]), str(step_obj["y"])], creationflags=c_flags)
                        time.sleep(0.5)
                        subprocess.run([self.adb_path, "shell", "input", "keyevent", "123"], creationflags=c_flags)
                        for _ in range(25): subprocess.run([self.adb_path, "shell", "input", "keyevent", "67"], creationflags=c_flags)
                    elif sysk == "Physical Delete (Backspace)":
                        subprocess.run([self.adb_path, "shell", "input", "tap", str(step_obj["x"]), str(step_obj["y"])], creationflags=c_flags)
                        time.sleep(0.5)
                        subprocess.run([self.adb_path, "shell", "input", "keyevent", "123"], creationflags=c_flags)
                        for _ in range(step_obj.get("count", 1)): subprocess.run([self.adb_path, "shell", "input", "keyevent", "67"], creationflags=c_flags)
                elif act == "Sleep":
                    duration = float(step_obj["val"]) if step_obj["val"].replace(".","",1).isdigit() else 1
                    self.after(0, lambda i=action_index, n=step_obj["step_name"]: log_box.insert("end", f"[{i}] {n}\n"))
                    time.sleep(duration)
                    success_count += 1
                    continue
                
                time.sleep(1.5)
                
                if not ref_name:
                    success_count += 1
                    step_reports.append(f"✅ Step {action_index} - SUCCESS (No Visual Compare)")
                    self.after(0, lambda: log_box.insert("end", f"✅ Process Completed.\n"))
                    continue

                self.after(0, lambda: log_box.insert("end", f"🔍 Comparing...\n"))
                check_path = os.path.join(self.error_folder, f"temp_check_{int(time.time())}.png")
                subprocess.run([self.adb_path, "shell", "screencap", "-p", "/sdcard/temp_check.png"], capture_output=True, creationflags=c_flags)
                subprocess.run([self.adb_path, "pull", "/sdcard/temp_check.png", check_path], capture_output=True, creationflags=c_flags)
                
                ref_path = os.path.join(self.reference_folder, ref_name)
                
                if os.path.exists(ref_path) and os.path.exists(check_path):
                    score, marked_path = self.compare_images(ref_path, check_path)
                    score_percent = int(score * 100)
                    self.after(0, lambda r=ref_path, c=marked_path, s=score_percent: self.update_ui_images(r, c, s))
                    
                    if score >= 0.85:
                        success_count += 1
                        step_reports.append(f"✅ Step {action_index} - SUCCESS (Similarity: {score_percent}%)")
                        self.after(0, lambda s=score_percent: log_box.insert("end", f"✅ Similarity: {s}%\n"))
                    else:
                        photo_name = f"error_{test_name.replace(' ', '_')}_Step{action_index}_{int(time.time())}.png"
                        photo_path = os.path.join(self.error_folder, photo_name)
                        if os.path.exists(marked_path): os.rename(marked_path, photo_path)
                        step_reports.append(f"❌ Step {action_index} - FAILED (Similarity: {score_percent}%) | IMG:{photo_path}")
                        self.after(0, lambda: log_box.insert("end", "\n🛑 ERROR DETECTED! Test stopped..."))
                        loop_cancelled = True
                        break
                else:
                    step_reports.append(f"⚠️ Step {action_index} - REFERENCE NOT FOUND")
                    self.after(0, lambda: log_box.insert("end", f"⚠️ No reference, skipping.\n"))

            log_proc.terminate()
            log_file.close()
            step_reports.append(f"📄 LOG FILE | LOG:{log_path}")
            
            general_status = "SUCCESS" if success_count == total_count and not loop_cancelled else "FAILED"
            date_time = datetime.now().strftime("%d-%m-%Y %H:%M")
            details_str = "\n".join(step_reports)
            
            record_conn = sqlite3.connect(self.db_path)
            record_cursor = record_conn.cursor()
            record_cursor.execute("INSERT INTO test_sonuclari (ana_test_adi, tarih, toplam_adim, basarili_adim, genel_durum, detaylar) VALUES (?,?,?,?,?,?)", 
                                 (test_name, date_time, total_count, success_count, general_status, details_str))
            record_conn.commit()
            record_conn.close()
                    
            if not loop_cancelled: self.after(0, lambda: log_box.insert("end", "\n🎉 TEST FINISHED! Report saved."))
            self.is_playing = False

        threading.Thread(target=playback_loop, daemon=True).start()

    # --- 4. EXPORT STANDARD APPIUM SCRIPT ---
    def export_test(self, t_id, test_name):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT aksiyonlar, uygulama, yetkili, versiyon, tarih, telefon_modeli FROM case_bazli_testler WHERE id = ?", (t_id,))
            row = cursor.fetchone()
            conn.close()
            if not row or not row[0]: return
            
            app_pkg = row[1] if row[1] else ""
            author = row[2] if row[2] else ""
            version = row[3] if row[3] else ""
            date = row[4] if row[4] else ""
            device = row[5] if row[5] else ""
            
            func_name = f"{test_name.replace(' ', '_')}"
            stream_cases = []
            current_case = None

            touches = [n for n in row[0].split("|") if n]
            for idx, point in enumerate(touches):
                parts = point.split(";;;")
                step_obj = parts_to_dict(parts, idx+1)
                
                if step_obj["action"] == "Case":
                    if current_case: stream_cases.append(current_case)
                    case_safe_name = re.sub(r'\W|^(?=\d)', '_', step_obj["val"])
                    current_case = {"name": case_safe_name, "steps": []}
                    continue
                
                if not current_case:
                    current_case = {"name": func_name, "steps": []}
                
                current_case["steps"].append(step_obj)
                
            if current_case: stream_cases.append(current_case)

            gen_code = f"""import time
import json
import re
import os
from datetime import datetime, timezone
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.common.actions import interaction

def smart_element_finder(driver, locator):
    locator = str(locator).strip()
    if not locator: raise Exception("Target data (XPath/ID) is empty!")
    
    if locator.count("/") > 3 and "android.widget" in locator:
        last_node = locator.split("/")[-1]
        if ("@" in last_node) and (last_node.startswith("android.") or last_node.startswith("android.widget.")):
            locator = "//" + last_node

    if ("[@content-desc=" in locator or "[@text=" in locator) and ("'" in locator or '"' in locator):
        try:
            attr_part = locator.split("[@")[1].split("=")[0]
            val_part = locator.split("=")[1].split("]")[0].replace('"', '').replace("'", "")
            if len(val_part) > 12 or " " in val_part:
                words = re.findall(r'[\\wİıÖöÜüŞşÇçĞğ]+', val_part)
                if words:
                    selected = sorted([w for w in words if len(w) >= 4], key=len, reverse=True)[0]
                    locator = f"//*[contains(@{{attr_part}}, '{{selected}}')]"
        except: pass
    
    if locator.startswith("//") or locator.startswith("(") or locator.startswith("hierarchy"):
        return driver.find_element(by=AppiumBy.XPATH, value=locator)
    return driver.find_element(by=AppiumBy.ID, value=locator)

def swipe_screen(driver, direction, x=0, y=0):
    size = driver.get_window_size()
    center_x = x if x > 0 else int(size['width'] * 0.05) if direction in ['down', 'up'] else int(size['width'] / 2)
    center_y = y if y > 0 else int(size['height'] / 2) if direction in ['down', 'up'] else int(size['height'] * 0.1)
    
    start_x, start_y, end_x, end_y = center_x, center_y, center_x, center_y
    x_offset, y_offset = int(size['width'] * 0.25), int(size['height'] * 0.25)
    
    if direction == 'down': start_y += y_offset; end_y -= y_offset
    elif direction == 'up': start_y -= y_offset; end_y += y_offset
    elif direction == 'right': start_x -= x_offset; end_x += x_offset
    elif direction == 'left': start_x += x_offset; end_x -= x_offset

    try:
        actions = ActionChains(driver)
        actions.w3c_actions = ActionBuilder(driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch"))
        actions.w3c_actions.pointer_action.move_to_location(start_x, start_y)
        actions.w3c_actions.pointer_action.pointer_down()
        actions.w3c_actions.pointer_action.pause(0.05) 
        actions.w3c_actions.pointer_action.move_to_location(end_x, end_y)
        actions.w3c_actions.pointer_action.pointer_up()
        actions.perform()
    except Exception as e: print(f"Swipe error: {{e}}")

"""
            gen_code += "options = UiAutomator2Options()\n"
            if app_pkg: gen_code += f"options.app_package = '{app_pkg}'\n"
            gen_code += "options.no_reset = True\n"
            gen_code += "executor = os.getenv('COMMAND_EXECUTOR', 'http://127.0.0.1:4723')\n"
            gen_code += "driver = webdriver.Remote(executor, options=options)\n"
            gen_code += "driver.implicitly_wait(10)\n\n"

            calls = []
            for case in stream_cases:
                c_name = case["name"]
                calls.append(f"    {c_name}()")
                gen_code += f"def {c_name}():\n    try:\n        print('--- {c_name.upper()} STARTED ---')\n"
                
                for s_idx, step in enumerate(case["steps"]):
                    act = step["action"]
                    s_name = step.get("step_name", f"Step {s_idx+1}").replace("'", "\\'")
                    xp = step.get('xpath', '')
                    exact = step.get('exact_match', False)
                    
                    if act == "Title / Comment":
                        gen_code += f"\n        # --- {step.get('val', '')} ---\n"
                        gen_code += f"        print('{step.get('val', '')}')\n"
                        continue
                        
                    gen_code += f"        print('Starting step: {s_name}...')\n"
                    
                    def get_finder(xpath, exact_match):
                        if exact_match: return f"driver.find_element(by=AppiumBy.XPATH, value=r'''{xpath}''')"
                        return f"smart_element_finder(driver, r'''{xpath}''')"
                    
                    if act == "Tap":
                        if step.get("x", 0) > 0 or step.get("y", 0) > 0:
                            gen_code += f"        driver.tap([({step['x']}, {step['y']})])\n        time.sleep(1)\n"
                        else:
                            gen_code += f"        {get_finder(xp, exact)}.click()\n        time.sleep(1)\n"
                    elif act == "Type Text":
                        safe_val = step.get("val", "").replace("'", "\\'")
                        gen_code += f"        box = {get_finder(xp, exact)}\n"
                        gen_code += f"        box.click(); time.sleep(0.5)\n" 
                        gen_code += f"        box.clear(); box.send_keys('{safe_val}'); time.sleep(1)\n"
                    elif act == "Secure Type (Physical)":
                        safe_val = step.get("val", "").replace("'", "\\'")
                        d_count = step.get("count", 10)
                        gen_code += f"        box = {get_finder(xp, exact)}\n"
                        gen_code += f"        box.click(); time.sleep(0.5)\n"
                        gen_code += f"        driver.press_keycode(123) # Move cursor to end\n"
                        gen_code += f"        for _ in range({d_count}): driver.press_keycode(67) # DELETE\n"
                        gen_code += f"        time.sleep(0.5)\n"
                        gen_code += f"        for digit in '{safe_val}':\n"
                        gen_code += f"            driver.press_keycode(int(digit) + 7)\n"
                        gen_code += f"            time.sleep(0.2)\n"
                        gen_code += f"        time.sleep(1)\n"
                    elif act == "System Key":
                        sk = step.get("sys_key", "")
                        if sk == "Hide Keyboard": gen_code += "        try: driver.hide_keyboard()\n        except: pass\n"
                        elif sk == "Back": gen_code += "        driver.press_keycode(4)\n"
                        elif sk == "Home": gen_code += "        driver.press_keycode(3)\n"
                        elif sk == "Clear Box":
                            gen_code += f"        box = {get_finder(xp, exact)}\n"
                            gen_code += f"        box.clear(); time.sleep(1)\n"
                        elif sk == "Physical Delete (Backspace)":
                            d_count = step.get("count", 10)
                            gen_code += f"        box = {get_finder(xp, exact)}\n"
                            gen_code += f"        box.click(); time.sleep(0.5)\n"
                            gen_code += f"        driver.press_keycode(123)\n"
                            gen_code += f"        for _ in range({d_count}): driver.press_keycode(67)\n        time.sleep(1)\n"
                    elif act == "Swipe":
                        s_dir = {"Down": "down", "Up": "up", "Right": "right", "Left": "left"}.get(step.get('direction','Down'))
                        sx, sy = step.get('x', 0), step.get('y', 0)
                        gen_code += f"        for _ in range({step.get('count',1)}):\n            swipe_screen(driver, '{s_dir}', {sx}, {sy})\n            time.sleep(0.5)\n"
                    elif act == "Sleep":
                        gen_code += f"        time.sleep({step.get('val',1)})\n"
                        
                    gen_code += f"        print('Passed: {s_name}')\n"
                    
                gen_code += f"        print('{c_name} Successfully Completed')\n"
                gen_code += "    except Exception as e:\n"
                gen_code += "        print(f'ERROR: {e}')\n"
                gen_code += "        raise Exception(f'Test Stopped! Expected element not found: {e}')\n\n"

            gen_code += "try:\n" + ("\n".join(calls) if calls else "    pass") + "\nfinally:\n    driver.quit()\n"

            metadata_dict = {"platform": "Android", "app_pkg": app_pkg, "app_act": "", "bundle_id": "", "cases": stream_cases}
            metadata_json = json.dumps(metadata_dict, ensure_ascii=False)
            gen_code += f"\n\n# --- IDE_METADATA_START ---\n# {metadata_json}\n"

            file_path = filedialog.asksaveasfilename(defaultextension=".py", initialfile=f"{func_name}_Appium.py", title="Save Standard IDE Script")
            if file_path:
                with open(file_path, "w", encoding="utf-8") as f: f.write(gen_code)
                messagebox.showinfo("Success", f"Standard Appium script generated!\nFile: {file_path}")
        except Exception as e: messagebox.showerror("Error", f"Export failed: {e}")

    # ==========================================
    #   5. REPORTING AND ZIP EXPORT
    # ==========================================
    def show_reports(self):
        self.clear_main_frame()
        ctk.CTkLabel(self.main_frame, text="📊 Past Test Results & Reports", font=("Arial", 18, "bold")).pack(pady=10)
        top_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        top_frame.pack(pady=5, fill="x", padx=10)
        self.search_report_entry = ctk.CTkEntry(top_frame, placeholder_text="Search in Reports...", width=400)
        self.search_report_entry.pack(side="left", padx=10)
        self.search_report_entry.bind("<KeyRelease>", self.update_report_list)

        self.report_list = ctk.CTkScrollableFrame(self.main_frame, width=800, height=450)
        self.report_list.pack(pady=10, padx=10, fill="both", expand=True)
        self.update_report_list()

    def update_report_list(self, event=None):
        for widget in self.report_list.winfo_children(): widget.destroy()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            search_text = self.search_report_entry.get().strip() if hasattr(self, 'search_report_entry') else ""
            cursor.execute("SELECT id, ana_test_adi, tarih, toplam_adim, basarili_adim, genel_durum, detaylar FROM test_sonuclari WHERE ana_test_adi LIKE ? ORDER BY id DESC", (f'%{search_text}%',))
            reports = cursor.fetchall()
            conn.close()

            for r_id, test_name, date, total, success, status, details in reports:
                bg_color = "darkgreen" if status == "SUCCESS" else "#962d22"
                row_frame = ctk.CTkFrame(self.report_list, fg_color=bg_color, corner_radius=5)
                row_frame.pack(fill="x", pady=5, padx=5)

                info_text = f"🕒 {date}   |   📂 {test_name}   |   Success: {success}/{total}"
                ctk.CTkLabel(row_frame, text=info_text, font=("Arial", 13, "bold")).pack(side="left", padx=15, pady=10)
                
                ctk.CTkButton(row_frame, text="🗑️ Delete", width=60, fg_color="#c0392b", hover_color="#962d22", command=lambda idx=r_id: self.delete_report(idx)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(row_frame, text="📤 Download ZIP", width=100, fg_color="#2980b9", hover_color="#1f618d", command=lambda t=test_name, dt=date, tp=total, b=success, dr=status, d=details: self.export_report_zip(t, dt, tp, b, dr, d)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(row_frame, text="🔍 Details", width=80, fg_color="#1f538d", hover_color="#14375e", command=lambda t=test_name, dt=date, d=details: self.open_detail_popup(t, dt, d)).pack(side="right", padx=5, pady=10)
        except Exception: pass

    def delete_report(self, report_id):
        answer = messagebox.askyesno("Confirm", "Are you sure you want to delete this report and its error images?")
        if not answer: return
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT detaylar FROM test_sonuclari WHERE id = ?", (report_id,))
            record = cursor.fetchone()
            if record and record[0]:
                for line in record[0].split("\n"):
                    if "| IMG:" in line:
                        path = line.split("| IMG:")[1].strip()
                        if os.path.exists(path): os.remove(path)
                    elif "| LOG:" in line:
                        path = line.split("| LOG:")[1].strip()
                        if os.path.exists(path): os.remove(path)
            cursor.execute("DELETE FROM test_sonuclari WHERE id = ?", (report_id,))
            conn.commit()
            conn.close()
            self.update_report_list()
        except Exception: pass

    def export_report_zip(self, test_name, date, total, success, status, details):
        file_date = date.replace(":", "-").replace(" ", "_")
        zip_name = f"Report_{test_name.replace(' ', '_')}_{file_date}.zip"
        zip_path = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP Files", "*.zip")], initialfile=zip_name)
        if not zip_path: return
        try:
            report_content = "="*55 + "\n           APPIC TEST RESULTS REPORT\n" + "="*55 + "\n\n"
            report_content += f"📌 Test Name       : {test_name}\n🕒 Run Date        : {date}\n📊 Success Rate    : {success} / {total} Steps Passed\n🎯 Overall Status  : {status}\n\n--- STEP DETAILS ---\n"
            files_to_add = []
            if details:
                for line in details.split("\n"):
                    if "| IMG:" in line:
                        text_part, path_part = line.split("| IMG:")
                        report_content += text_part.strip() + f" (Error Image inside Zip: {os.path.basename(path_part.strip())})\n"
                        if os.path.exists(path_part.strip()): files_to_add.append(path_part.strip())
                    elif "| LOG:" in line:
                        text_part, path_part = line.split("| LOG:")
                        report_content += text_part.strip() + f" (Log File inside Zip: {os.path.basename(path_part.strip())})\n"
                        if os.path.exists(path_part.strip()): files_to_add.append(path_part.strip())
                    else: report_content += line + "\n"
            else: report_content += "No details found.\n"
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.writestr(f"Report_Summary_{file_date}.txt", report_content)
                for file_path in set(files_to_add): zipf.write(file_path, arcname=os.path.basename(file_path))
            messagebox.showinfo("Success", f"Report and files packed as ZIP successfully!\n{zip_path}")
        except Exception as e: messagebox.showerror("Error", f"Packing error: {e}")

    def open_detail_popup(self, test_name, date, details):
        popup = ctk.CTkToplevel(self)
        popup.title("Test Step Details")
        popup.geometry("550x650") 
        popup.attributes("-topmost", True)
        ctk.CTkLabel(popup, text=f"📂 {test_name}\n🕒 {date}", font=("Arial", 16, "bold")).pack(pady=10)
        scroll_area = ctk.CTkScrollableFrame(popup, width=500, height=550)
        scroll_area.pack(padx=10, pady=10, fill="both", expand=True)
        if details:
            for line in details.split("\n"):
                if "| IMG:" in line:
                    text_part, photo_path = line.split("| IMG:")
                    ctk.CTkLabel(scroll_area, text=text_part.strip(), font=("Arial", 14, "bold"), text_color="#ff4d4d").pack(pady=(15, 5), anchor="w", padx=10)
                    if os.path.exists(photo_path.strip()):
                        try:
                            original_img = Image.open(photo_path.strip())
                            ratio = 300 / original_img.width
                            new_size = (300, int(original_img.height * ratio))
                            ctk_img = ctk.CTkImage(light_image=original_img, dark_image=original_img, size=new_size)
                            ctk.CTkLabel(scroll_area, image=ctk_img, text="").pack(pady=5, anchor="w", padx=30)
                        except Exception: pass
                elif "| LOG:" in line:
                    text_part, log_path = line.split("| LOG:")
                    if os.path.exists(log_path.strip()): 
                        ctk.CTkButton(scroll_area, text="📄 Open Device Log (Logcat)", fg_color="#8e44ad", command=lambda p=log_path.strip(): os.startfile(p)).pack(pady=(20, 10), padx=30, fill="x")
                else:
                    color = "lightgreen" if "✅" in line else "white"
                    ctk.CTkLabel(scroll_area, text=line.strip(), font=("Arial", 14, "bold"), text_color=color).pack(pady=(15, 5), anchor="w", padx=10)

if __name__ == "__main__":
    app = AppicTestStudio()
    app.mainloop()