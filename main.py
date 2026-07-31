import json
import os
import sys
import time
import shutil
import threading
import urllib.request
import webbrowser
import tkinter as tk
import re
from tkinter import messagebox, ttk, filedialog, simpledialog
from collections import defaultdict

# 嘗試載入全域鍵盤監聽模組
try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

# 嘗試載入影像辨識 (OCR) 模組與影像處理模組
try:
    from PIL import Image, ImageEnhance, ImageTk, ImageGrab, ImageOps
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

# === 軟體版本與更新設定 ===
APP_VERSION = "4.45.0" 
UPDATE_URL = "https://raw.githubusercontent.com/cvk82519-boop/GTA-Garage-App/refs/heads/main/version.json"
DATA_FILE = "gta5_garage_data.json"

# 預設的取得方式 (供新帳號初始化使用)
ACQUIRE_OPTIONS = ["購買獲得", "任務獲得", "生涯成就", "賭場轉盤", "搶劫獲得", "車友會", "其他備註"]
V_TYPE_OPTIONS = ["個人載具", "非個人載具", "帕格薩斯"]

# 🛸 子母載具白名單設定
SUB_CARRIER_RULES = {
    "驚駭位元": ["暴君MKII", "暴君 Mk II", "Oppressor Mk II"],
    "科薩卡": ["鬥牛勇士", "斯特龍伯格", "Toreador", "Stromberg"]
}

# 🎨 統一視覺色彩與字體設定
COLOR_MAIN_BG = "#212121"       # 主背景：曜石黑
COLOR_CARD_BG = "#2d2d2d"       # 元件背景：鈦金灰
COLOR_TEXT_WHITE = "#ffffff"    # 主要文字：純白
COLOR_TEXT_GRAY = "#cccccc"     # 次要文字：亮灰
COLOR_FOCUS_BG = "#1565C0"      # 當前輸入高亮：科技藍

FONT_NORMAL = ("Microsoft JhengHei", 12)           
FONT_BOLD = ("Microsoft JhengHei", 13, "bold")     
FONT_LARGE_BOLD = ("Microsoft JhengHei", 14, "bold") 

# ✨ 全域輸入框高亮追蹤引擎
def apply_focus_highlight(widget):
    if isinstance(widget, tk.Entry):
        widget.bind("<FocusIn>", lambda e: widget.config(bg=COLOR_FOCUS_BG), add="+")
        widget.bind("<FocusOut>", lambda e: widget.config(bg=COLOR_CARD_BG), add="+")

# --- 浮動註解 (Tooltip) ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<Destroy>", self.leave) 

    def enter(self, event=None): self.schedule()
    def leave(self, event=None):
        self.unschedule(); self.hidetip()
    def schedule(self):
        self.unschedule()
        if self.widget.winfo_exists(): self.id = self.widget.after(400, self.showtip)
    def unschedule(self):
        if self.id: self.widget.after_cancel(self.id); self.id = None
    def showtip(self, event=None):
        if not self.widget.winfo_exists() or not self.text: return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify=tk.LEFT, background="#111111", foreground="white", relief=tk.SOLID, borderwidth=0, font=FONT_NORMAL, padx=8, pady=4).pack(ipadx=1)
    def hidetip(self):
        if self.tipwindow and self.tipwindow.winfo_exists(): self.tipwindow.destroy()
        self.tipwindow = None

def add_tooltip(widget, text): ToolTip(widget, text)

# --- 資料處理核心 ---
def load_data():
    default_structure = {"profiles": {}}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "vehicles" in data and "profiles" not in data:
                        return {"profiles": {"已移轉帳號": data}}
                    if "profiles" in data: return data
                return default_structure
        except: return default_structure
    return default_structure

def save_data(all_data):
    for p_name, p_data in all_data.get("profiles", {}).items():
        if "garages" not in p_data: 
            p_data["garages"] = ["未分類", "帕格薩斯", "日蝕大樓 1 號", "辦公室車庫", "名鑽賭場空中別墅", "設施"]
        else:
            if "帕格薩斯" not in p_data["garages"]:
                if "未分類" in p_data["garages"]: p_data["garages"].insert(p_data["garages"].index("未分類") + 1, "帕格薩斯")
                else: p_data["garages"].insert(0, "帕格薩斯")
                
        # 移除舊版誤建在特殊載具中的帕格薩斯
        if "special_vehicles" in p_data:
            p_data["special_vehicles"] = [sv for sv in p_data["special_vehicles"] if sv["name"] != "帕格薩斯"]
            
        if "garage_limits" not in p_data:
            p_data["garage_limits"] = {"未分類": 999, "帕格薩斯": 999}
            for g in p_data["garages"]:
                if g not in ["未分類", "帕格薩斯"]: p_data["garage_limits"][g] = 10
        else:
            p_data["garage_limits"]["帕格薩斯"] = 999
            
        if "garage_categories" not in p_data:
            p_data["garage_categories"] = {}
        p_data["garage_categories"]["帕格薩斯"] = "虛擬服務"
            
        for g in p_data["garages"]:
            if g not in p_data["garage_categories"]:
                if g in ["通瓦別墅", "利金漫莊園", "好麥塢宅第"]: p_data["garage_categories"][g] = "豪宅"
                elif g == "日蝕大樓 1 號": p_data["garage_categories"][g] = "高階公寓"
                elif g == "辦公室車庫": p_data["garage_categories"][g] = "商辦企業"
                elif g == "名鑽賭場空中別墅": p_data["garage_categories"][g] = "豪華賭場"
                elif g == "設施": p_data["garage_categories"][g] = "地下設施"
                elif g == "未分類": p_data["garage_categories"][g] = "系統預設"
                else: p_data["garage_categories"][g] = "一般車庫"

        if "action_logs" not in p_data:
            p_data["action_logs"] = []
            
        if "app_settings" not in p_data:
            p_data["app_settings"] = {}
            
        defaults = {
            "tab_bulletin": True, "tab_vehicles": True, "tab_non_personal": True,
            "tab_special": True, "tab_garages": True, "tab_statistics": True, "tab_logs": True,
            "tool_stopwatch": True, "disable_all_limits": False,
            "default_garage_limit": 10, "default_special_limit": 2,
            "default_countdown_sec": 300.0 
        }
        for k, v in defaults.items():
            if k not in p_data["app_settings"]:
                p_data["app_settings"][k] = v

        if "acquire_options" not in p_data:
            p_data["acquire_options"] = ACQUIRE_OPTIONS.copy()

        for sv in p_data.get("special_vehicles", []):
            if "location" not in sv: sv["location"] = "未分類"
            if "inner_vehicle" not in sv: sv["inner_vehicle"] = ""
            if "can_store" not in sv: sv["can_store"] = True if sv["name"] in SUB_CARRIER_RULES else False

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)

class GTAGarageApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"洛聖都資產管理系統 V{APP_VERSION}")
        self.root.configure(bg=COLOR_MAIN_BG)
        
        self.root.resizable(True, True)
        self.root.minsize(1200, 700)
        
        self.all_data = load_data()
        
        app_config = self.all_data.get("app_config", {})
        saved_geom = app_config.get("geometry", "")
        saved_state = app_config.get("state", "normal")
        
        if saved_geom:
            self.root.geometry(saved_geom)
        else:
            window_width = 1350 
            window_height = 780
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            center_x = (screen_width - window_width) // 2
            center_y = (screen_height - window_height) // 2
            self.root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
            
        if saved_state == "zoomed":
            self.root.state('zoomed')
            
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_closing)
        
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background=COLOR_MAIN_BG, foreground=COLOR_TEXT_WHITE, font=FONT_NORMAL)
        self.style.configure("TNotebook", background=COLOR_MAIN_BG, borderwidth=0, padding=2)
        self.style.configure("TNotebook.Tab", background=COLOR_CARD_BG, foreground=COLOR_TEXT_GRAY, font=FONT_BOLD, padding=[15, 6])
        self.style.map("TNotebook.Tab", background=[("selected", COLOR_MAIN_BG)], foreground=[("selected", "#4CAF50")])
        self.style.configure("Treeview", background=COLOR_CARD_BG, fieldbackground=COLOR_CARD_BG, foreground=COLOR_TEXT_WHITE, font=FONT_NORMAL, rowheight=28)
        self.style.configure("Treeview.Heading", background="#151515", foreground=COLOR_TEXT_WHITE, font=FONT_BOLD, borderwidth=1)
        self.style.map("Treeview", background=[("selected", "#2c7a43")])

        self.style.configure('TCombobox', fieldbackground=COLOR_CARD_BG, background=COLOR_CARD_BG, foreground=COLOR_TEXT_WHITE)
        self.style.map('TCombobox', 
                       fieldbackground=[('focus', COLOR_FOCUS_BG), ('readonly', COLOR_CARD_BG)], 
                       foreground=[('focus', 'white'), ('readonly', COLOR_TEXT_WHITE)])
        
        save_data(self.all_data) 
        
        self.current_id = ""
        self.data = None
        self.checked_indices = set()
        self.last_hovered_iid = None
        
        self.sw_mode = "STOPWATCH" 
        self.sw_state = "IDLE"      
        self.cd_target_sec = 300.0  
        self.last_pause_time = 0.0
        self.is_running = False
        self.start_time = 0.0
        self.elapsed_time = 0.0
        self.stopwatch_window = None
        self.keyboard_warned = False
        
        self.root.after(50, self.master_stopwatch_loop)

        self.setup_menu_bar()
        self.setup_status_bar()
        self.setup_profile_bar()
        
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=5)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        self.tab_bulletin = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.notebook.add(self.tab_bulletin, text=" 📢 系統公告 ")
        self.tab_vehicles = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.notebook.add(self.tab_vehicles, text=" 🚗 車輛管理 ")
        self.tab_non_personal = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.notebook.add(self.tab_non_personal, text=" 🚜 非個人與帕格薩斯 ")
        self.tab_special = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.notebook.add(self.tab_special, text=" 🚁 特殊載具 ")
        self.tab_garages = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.notebook.add(self.tab_garages, text=" 🏠 車庫管理 ")
        self.tab_statistics = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.notebook.add(self.tab_statistics, text=" 📊 統計資料 ")
        self.tab_logs = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.notebook.add(self.tab_logs, text=" 📜 操作日誌 ")

        self.setup_bulletin_tab()
        self.setup_vehicles_tab()
        self.setup_non_personal_tab()
        self.setup_special_tab()
        self.setup_garages_tab()
        self.setup_statistics_tab() 
        self.setup_logs_tab()

        self.apply_settings()
        self.check_login_status()

    def on_app_closing(self):
        if "app_config" not in self.all_data:
            self.all_data["app_config"] = {}
            
        current_state = self.root.state()
        self.all_data["app_config"]["state"] = current_state
        
        if current_state == "normal":
            self.all_data["app_config"]["geometry"] = self.root.geometry()
            
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.all_data, f, ensure_ascii=False, indent=4)
            
        self.root.destroy()
        sys.exit(0)

    # ==========================================
    #   🌟 頂端功能列 (Menu Bar)
    # ==========================================
    def setup_menu_bar(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        file_menu.add_command(label="💾 手動備份資料 (Backup)", command=self.backup_data)
        file_menu.add_command(label="📂 載入備份還原 (Restore)", command=self.restore_data) 
        file_menu.add_separator()
        file_menu.add_command(label="🚪 結束系統 (Exit)", command=self.on_app_closing)
        menubar.add_cascade(label="檔案 (F)", menu=file_menu)

        self.tools_menu = tk.Menu(menubar, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        self.tools_menu.add_command(label="⏱️ 呼叫賽車與任務碼錶 (Pause準備/W計時/倒數)", command=self.toggle_stopwatch_window)
        self.tools_menu.add_command(label="📦 批量登入", command=self.open_batch_import_window) 
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label="⚙️ 系統全域與版面設定 (版面/容量/選單)", command=self.open_settings_window)
        menubar.add_cascade(label="系統工具 (T)", menu=self.tools_menu)
        
        self.nav_menu = tk.Menu(menubar, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        self.nav_menu.add_command(label="📢 前往 系統公告", command=lambda: self.safe_select_tab(self.tab_bulletin))
        self.nav_menu.add_command(label="🚗 前往 車輛管理", command=lambda: self.safe_select_tab(self.tab_vehicles))
        self.nav_menu.add_command(label="🚜 前往 非個人與帕格薩斯", command=lambda: self.safe_select_tab(self.tab_non_personal))
        self.nav_menu.add_command(label="🚁 前往 特殊載具", command=lambda: self.safe_select_tab(self.tab_special))
        self.nav_menu.add_command(label="🏠 前往 車庫管理", command=lambda: self.safe_select_tab(self.tab_garages))
        self.nav_menu.add_command(label="📊 前往 統計資料", command=lambda: self.safe_select_tab(self.tab_statistics)) 
        self.nav_menu.add_command(label="📜 前往 操作日誌", command=lambda: self.safe_select_tab(self.tab_logs))
        menubar.add_cascade(label="視窗導覽 (V)", menu=self.nav_menu)

        about_menu = tk.Menu(menubar, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        about_menu.add_command(label="🔄 手動檢查更新", command=self.check_for_updates)
        about_menu.add_separator()
        about_menu.add_command(label="ℹ️ 關於本系統", command=self.show_about)
        menubar.add_cascade(label="關於 (A)", menu=about_menu)

        self.root.config(menu=menubar)

    # === 🏁 全新賽車碼錶與倒數計時雙引擎 ===
    def master_stopwatch_loop(self):
        if getattr(self, 'is_running', False):
            now = time.time()
            mode = getattr(self, 'sw_mode', 'STOPWATCH')
            if mode == "STOPWATCH":
                self.elapsed_time = now - self.start_time
            else: 
                passed = now - self.start_time
                rem = getattr(self, 'cd_target_sec', 300.0) - passed
                if rem <= 0.0:
                    self.elapsed_time = 0.0
                    self.is_running = False
                    self.sw_state = "IDLE"
                    self.update_stopwatch_ui_state()
                    self.update_stopwatch_ui()
                    self.show_toast_progress("⏰ 倒數計時時間到！")
                    self.set_status("⏰ 倒數計時時間到！", "#e74c3c")
                    if hasattr(self, 'stopwatch_window') and self.stopwatch_window and self.stopwatch_window.winfo_exists():
                        self.stopwatch_window.deiconify()
                        self.stopwatch_window.attributes("-topmost", True)
                else:
                    self.elapsed_time = rem
            self.update_stopwatch_ui()
        self.root.after(50, self.master_stopwatch_loop)

    def handle_pause_key(self, event=None):
        now = time.time()
        if now - getattr(self, 'last_pause_time', 0.0) < 0.4:
            self.last_pause_time = 0.0
            self.root.after(0, self.action_reset)
        else:
            self.last_pause_time = now
            self.root.after(0, self.action_pause_single)

    def handle_w_key(self, event=None):
        if getattr(self, 'sw_state', 'IDLE') == "READY":
            self.root.after(0, self.action_start)

    def action_pause_single(self):
        state = getattr(self, 'sw_state', 'IDLE')
        mode = getattr(self, 'sw_mode', 'STOPWATCH')
        if state == "RUNNING":
            self.sw_state = "IDLE"
            self.is_running = False
        elif state == "IDLE":
            if mode == "COUNTDOWN" and getattr(self, 'elapsed_time', 0.0) <= 0.0:
                self.elapsed_time = getattr(self, 'cd_target_sec', 300.0)
            self.sw_state = "READY"
            self.is_running = False
        elif state == "READY":
            self.sw_state = "IDLE"
            self.is_running = False
        self.update_stopwatch_ui_state()

    def action_start(self):
        self.sw_state = "RUNNING"
        self.is_running = True
        mode = getattr(self, 'sw_mode', 'STOPWATCH')
        now = time.time()
        if mode == "STOPWATCH":
            self.start_time = now - getattr(self, 'elapsed_time', 0.0)
        else: 
            current_rem = getattr(self, 'elapsed_time', self.cd_target_sec)
            if current_rem <= 0.0:
                current_rem = self.cd_target_sec
            self.start_time = now - (self.cd_target_sec - current_rem)
        self.update_stopwatch_ui_state()

    def action_reset(self):
        self.sw_state = "IDLE"
        self.is_running = False
        if getattr(self, 'sw_mode', 'STOPWATCH') == "STOPWATCH":
            self.elapsed_time = 0.0
        else:
            self.elapsed_time = getattr(self, 'cd_target_sec', 300.0)
        self.update_stopwatch_ui_state()
        self.update_stopwatch_ui()

    def set_countdown_target(self, seconds, close_window=False):
        self.cd_target_sec = float(seconds)
        if self.data:
            if "app_settings" not in self.data: self.data["app_settings"] = {}
            self.data["app_settings"]["default_countdown_sec"] = self.cd_target_sec
            save_data(self.all_data)
        self.action_reset()
        self.show_toast_progress(f"⏳ 已記憶倒數: {int(seconds//60)}分{int(seconds%60)}秒")
        if close_window and hasattr(self, 'stopwatch_window') and self.stopwatch_window and self.stopwatch_window.winfo_exists():
            self.stopwatch_window.withdraw()

    def set_sw_mode(self, mode):
        self.sw_mode = mode
        if hasattr(self, 'btn_mode_sw') and hasattr(self, 'btn_mode_cd'):
            if mode == "STOPWATCH":
                self.btn_mode_sw.config(bg="#1565C0", fg="white")
                self.btn_mode_cd.config(bg="#333333", fg="#cccccc")
                if hasattr(self, 'frame_cd_opts') and self.frame_cd_opts.winfo_exists():
                    self.frame_cd_opts.pack_forget()
            else:
                self.btn_mode_sw.config(bg="#333333", fg="#cccccc")
                self.btn_mode_cd.config(bg="#1565C0", fg="white")
                if hasattr(self, 'frame_cd_opts') and self.frame_cd_opts.winfo_exists():
                    self.frame_cd_opts.pack(after=self.frame_mode_btn, pady=4)
        self.action_reset()

    def update_stopwatch_ui_state(self):
        if hasattr(self, 'btn_sw_action') and self.btn_sw_action.winfo_exists():
            state = getattr(self, 'sw_state', 'IDLE')
            if state == "READY":
                self.btn_sw_action.config(text="等待 W 鍵起跑", bg="#F39C12") 
                if hasattr(self, 'lbl_sw'): self.lbl_sw.config(fg="#F39C12")
            elif state == "RUNNING":
                self.btn_sw_action.config(text="計時中 (Pause停)", bg="#e74c3c") 
                if hasattr(self, 'lbl_sw'): self.lbl_sw.config(fg="#4CAF50") 
            else:
                self.btn_sw_action.config(text="Pause 準備", bg="#4CAF50") 
                if hasattr(self, 'lbl_sw'): self.lbl_sw.config(fg="white")

    def toggle_stopwatch_window(self):
        if not self.stopwatch_window or not self.stopwatch_window.winfo_exists():
            self.stopwatch_window = tk.Toplevel(self.root)
            self.stopwatch_window.title("⏱️ 任務與賽車計時器")
            self.stopwatch_window.geometry("360x240") 
            self.stopwatch_window.configure(bg=COLOR_CARD_BG)
            self.stopwatch_window.attributes("-topmost", True)
            self.stopwatch_window.resizable(False, False)
            
            self.stopwatch_window.protocol("WM_DELETE_WINDOW", lambda: self.stopwatch_window.withdraw())
            
            self.frame_mode_btn = tk.Frame(self.stopwatch_window, bg=COLOR_CARD_BG)
            self.frame_mode_btn.pack(pady=(8, 2))
            
            self.btn_mode_sw = tk.Button(self.frame_mode_btn, text="⏱️ 正向計時", command=lambda: self.set_sw_mode("STOPWATCH"), 
                                        bg="#1565C0" if self.sw_mode == "STOPWATCH" else "#333333", 
                                        fg="white" if self.sw_mode == "STOPWATCH" else "#cccccc", 
                                        font=FONT_BOLD, relief="flat", padx=8)
            self.btn_mode_sw.pack(side="left", padx=4)
            
            self.btn_mode_cd = tk.Button(self.frame_mode_btn, text="⏳ 倒數計時", command=lambda: self.set_sw_mode("COUNTDOWN"), 
                                        bg="#1565C0" if self.sw_mode == "COUNTDOWN" else "#333333", 
                                        fg="white" if self.sw_mode == "COUNTDOWN" else "#cccccc", 
                                        font=FONT_BOLD, relief="flat", padx=8)
            self.btn_mode_cd.pack(side="left", padx=4)

            self.frame_cd_opts = tk.Frame(self.stopwatch_window, bg=COLOR_CARD_BG)
            if self.sw_mode == "COUNTDOWN":
                self.frame_cd_opts.pack(pady=4)

            f_preset = tk.Frame(self.frame_cd_opts, bg=COLOR_CARD_BG)
            f_preset.pack()
            for label_t, sec_v in [("1分", 60), ("5分", 300), ("10分", 600), ("20分", 1200), ("48分", 2880)]:
                tk.Button(f_preset, text=label_t, command=lambda s=sec_v: self.set_countdown_target(s), 
                          bg="#424242", fg="white", font=("Microsoft JhengHei", 9, "bold"), relief="flat", padx=3).pack(side="left", padx=2)

            f_custom = tk.Frame(self.frame_cd_opts, bg=COLOR_CARD_BG)
            f_custom.pack(pady=(4, 0))
            tk.Label(f_custom, text="自訂:", bg=COLOR_CARD_BG, fg="white", font=("Microsoft JhengHei", 9)).pack(side="left")
            
            ent_custom_m = tk.Entry(f_custom, width=3, font=("Microsoft JhengHei", 10), bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid")
            ent_custom_m.insert(0, str(int(self.cd_target_sec // 60)))
            ent_custom_m.pack(side="left", padx=1)
            apply_focus_highlight(ent_custom_m)
            tk.Label(f_custom, text="分", bg=COLOR_CARD_BG, fg="white", font=("Microsoft JhengHei", 9)).pack(side="left")
            
            ent_custom_s = tk.Entry(f_custom, width=3, font=("Microsoft JhengHei", 10), bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid")
            ent_custom_s.insert(0, str(int(self.cd_target_sec % 60)))
            ent_custom_s.pack(side="left", padx=1)
            apply_focus_highlight(ent_custom_s)
            tk.Label(f_custom, text="秒", bg=COLOR_CARD_BG, fg="white", font=("Microsoft JhengHei", 9)).pack(side="left", padx=(0,3))
            
            def apply_custom_cd(e=None):
                try:
                    m_str = ent_custom_m.get().strip()
                    s_str = ent_custom_s.get().strip()
                    m = float(m_str) if m_str else 0.0
                    s = float(s_str) if s_str else 0.0
                    total = m * 60 + s
                    if total > 0: 
                        self.set_countdown_target(total, close_window=True)
                except: pass

            tk.Button(f_custom, text="儲存並隱藏", command=apply_custom_cd, bg="#2196F3", fg="white", font=("Microsoft JhengHei", 9, "bold"), relief="flat", padx=3).pack(side="left", padx=2)
            ent_custom_m.bind("<Return>", lambda e: ent_custom_s.focus())
            ent_custom_s.bind("<Return>", apply_custom_cd)

            self.lbl_sw = tk.Label(self.stopwatch_window, text="00:00.0", font=("Consolas", 30, "bold"), bg=COLOR_CARD_BG, fg="white")
            self.lbl_sw.pack(pady=(4, 4))
            
            btn_f = tk.Frame(self.stopwatch_window, bg=COLOR_CARD_BG)
            btn_f.pack(pady=(0, 5))
            
            self.btn_sw_action = tk.Button(btn_f, text="Pause 準備", command=self.action_pause_single, bg="#4CAF50", fg="white", font=FONT_BOLD, relief="flat", width=14)
            self.btn_sw_action.pack(side="left", padx=5)
            tk.Button(btn_f, text="歸零", command=self.action_reset, bg="#e74c3c", fg="white", font=FONT_BOLD, relief="flat", width=6).pack(side="left", padx=5)
            
            self.update_stopwatch_ui_state()
            self.update_stopwatch_ui()
        else:
            if self.stopwatch_window.state() == "normal":
                self.stopwatch_window.withdraw()
            else:
                self.stopwatch_window.deiconify()

    def update_stopwatch_ui(self):
        if self.stopwatch_window and self.stopwatch_window.winfo_exists() and hasattr(self, 'lbl_sw'):
            mins = int(self.elapsed_time // 60)
            secs = int(self.elapsed_time % 60)
            ms = int((self.elapsed_time * 10) % 10)
            self.lbl_sw.config(text=f"{mins:02d}:{secs:02d}.{ms}")

    def on_tab_changed(self, event):
        sel_id = self.notebook.select()
        if not sel_id: return
        current_tab = self.notebook.tab(sel_id, "text")
        if "統計資料" in current_tab:
            self.refresh_statistics()

    def check_for_updates(self):
        self.set_status("🔄 正在連線檢查最新版本...", "#2196F3")
        def _check():
            try:
                req = urllib.request.Request(UPDATE_URL, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    latest_version = data.get("version", APP_VERSION)
                    
                    def parse_v(v_str):
                        return [int(x) for x in str(v_str).replace("V", "").replace("v", "").split(".") if x.isdigit()]
                    
                    current_v = parse_v(APP_VERSION)
                    latest_v = parse_v(latest_version)
                    
                    if latest_v > current_v:
                        notes = data.get("notes", "無更新說明")
                        url = data.get("url", "https://github.com/cvk82519-boop/GTA-Garage-App")
                        msg = f"✨ 發現新版本：V{latest_version}\n\n目前版本：V{APP_VERSION}\n\n📝 更新內容：\n{notes}\n\n是否要開啟瀏覽器前往下載？"
                        def show_update_dialog():
                            if messagebox.askyesno("更新通知", msg):
                                webbrowser.open(url)
                            self.set_status(f"✨ 發現新版本：V{latest_version}，建議盡快前往更新！", "#4CAF50")
                        self.root.after(0, show_update_dialog)
                    else:
                        self.root.after(0, lambda: messagebox.showinfo("檢查更新", f"太棒了！您目前使用的 V{APP_VERSION} 已經是最新的雲端版本！"))
                        self.root.after(0, lambda: self.set_status("✅ 系統已是最新版本。", "#4CAF50"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("更新錯誤", f"無法連接至更新伺服器，請確認網路連線。\n\n詳細錯誤訊息：{e}"))
                self.root.after(0, lambda: self.set_status("❌ 檢查更新失敗，請稍後再試。", "#e74c3c"))
                
        threading.Thread(target=_check, daemon=True).start()

    def safe_select_tab(self, tab_widget):
        state = self.notebook.tab(tab_widget, "state")
        if state == "hidden": messagebox.showinfo("功能已隱藏", "此功能已被隱藏，請先至「系統工具 -> ⚙️ 系統全域與版面設定」中開啟。")
        elif state == "disabled": messagebox.showinfo("未登入權限", "請先登入您的角色 ID 以解鎖此功能分頁。")
        else: self.notebook.select(tab_widget)

    def backup_data(self):
        if not os.path.exists(DATA_FILE): return messagebox.showinfo("備份", "目前沒有資料檔案可備份。")
        default_name = f"backup_gta_data_{int(time.time())}.json"
        file_path = filedialog.asksaveasfilename(title="選擇備份儲存位置", initialfile=default_name, defaultextension=".json", filetypes=[("JSON 資料檔", "*.json"), ("所有檔案", "*.*")])
        if not file_path: return 
        try:
            shutil.copy(DATA_FILE, file_path)
            self.set_status(f"✅ 資料已成功安全備份至：{file_path}", color="#4CAF50")
            messagebox.showinfo("備份成功", f"資料已成功備份至：\n{file_path}")
        except Exception as e: 
            messagebox.showerror("備份錯誤", f"備份失敗：\n{e}")

    def restore_data(self):
        if not messagebox.askyesno("⚠️ 還原資料警告", "還原備份將會【徹底覆蓋】您目前的所有的資料與進度！\n\n強烈建議您在還原前，先點擊一次「手動備份資料」以防萬一。\n\n確定要繼續選擇備份檔案並還原嗎？"): return
        file_path = filedialog.askopenfilename(title="選擇要還原的 JSON 備份檔案", filetypes=[("JSON 資料檔", "*.json"), ("所有檔案", "*.*")])
        if not file_path: return 
        try:
            with open(file_path, "r", encoding="utf-8") as f: new_data = json.load(f)
            if not isinstance(new_data, dict): raise ValueError("檔案格式無法辨識，必須為 JSON 字典結構")
            shutil.copy(file_path, DATA_FILE); self.all_data = load_data()
            if self.current_id and self.current_id not in self.all_data.get("profiles", {}): self.current_id = ""
            self.update_profile_combo(); self.check_login_status(); self.show_toast_progress("📂 備份還原成功！")
            self.set_status(f"✅ 已成功從 {os.path.basename(file_path)} 還原所有狀態。", "#4CAF50")
            messagebox.showinfo("還原成功", "資料已成功從備份檔還原！\n系統已自動刷新所有畫面。")
        except Exception as e: messagebox.showerror("還原失敗", f"讀取或還原備份檔案時發生錯誤：\n\n{e}\n\n請確認該檔案是本系統產生之備份檔。")

    def show_about(self):
        messagebox.showinfo("關於", f"🚗 洛聖都資產管理系統\n當前版本：{APP_VERSION}\n\n為 GTA5 玩家打造的專業載具與車庫資產追蹤工具。")

    def open_settings_window(self):
        if not self.data:
            messagebox.showwarning("操作提示", "請先選擇並登入一個角色 ID，才能設定專屬參數！")
            return
            
        win = tk.Toplevel(self.root)
        win.title("⚙️ 角色全域與版面設定")
        self.center_toplevel_window(win, 520, 680)
        win.configure(bg=COLOR_CARD_BG)
        
        canvas = tk.Canvas(win, borderwidth=0, bg=COLOR_CARD_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLOR_CARD_BG)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=500)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
            
        win.bind("<Enter>", _bind_mousewheel)
        win.bind("<Leave>", _unbind_mousewheel)
        
        tk.Label(scrollable_frame, text="👁️ 版面顯示設定 (勾選顯示 / 取消隱藏)", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#4CAF50").pack(pady=(15, 5))
        
        settings = self.data.get("app_settings", {})
        vars_dict = {}
        win.vars_dict = vars_dict
        
        features = [
            ("tab_bulletin", "📢 系統公告分頁 (預設主頁)"), ("tab_vehicles", "🚗 車輛管理分頁"),
            ("tab_non_personal", "🚜 非個人與帕格薩斯分頁"), ("tab_special", "🚁 特殊載具分頁"),
            ("tab_garages", "🏠 車庫管理分頁"), ("tab_statistics", "📊 統計資料分頁"), 
            ("tab_logs", "📜 操作日誌分頁"), ("tool_stopwatch", "⏱️ 任務碼錶 (Pause準備/W起跑/雙擊歸零)") 
        ]
        
        frame_checks = tk.Frame(scrollable_frame, bg=COLOR_CARD_BG); frame_checks.pack(fill="x", padx=40)
        for key, text in features:
            var = tk.BooleanVar(win, value=settings.get(key, True)); vars_dict[key] = var
            tk.Checkbutton(frame_checks, text=text, variable=var, bg=COLOR_CARD_BG, fg="white", selectcolor="#757575", font=FONT_BOLD, activebackground=COLOR_CARD_BG, activeforeground="white", justify="left").pack(anchor="w", pady=3)
            
        ttk.Separator(scrollable_frame, orient="horizontal").pack(fill="x", pady=15, padx=20)
        
        tk.Label(scrollable_frame, text="🛠️ 全域容量與限制設定", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#e74c3c").pack(pady=(5, 5))
        
        disable_limits = settings.get("disable_all_limits", False)
        def_g_limit = settings.get("default_garage_limit", 10)
        def_s_limit = settings.get("default_special_limit", 2)
        
        frame_inputs = tk.Frame(scrollable_frame, bg=COLOR_CARD_BG)
        frame_inputs.pack(fill="x", padx=40, pady=5)
        
        tk.Label(frame_inputs, text="🏠 一般車庫預設上限:", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).grid(row=0, column=0, sticky="e", pady=8)
        ent_g_limit = tk.Entry(frame_inputs, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=10)
        ent_g_limit.insert(0, str(def_g_limit))
        ent_g_limit.grid(row=0, column=1, padx=10, pady=8)
        apply_focus_highlight(ent_g_limit)
        
        tk.Label(frame_inputs, text="🚁 特殊載具預設上限:", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).grid(row=1, column=0, sticky="e", pady=8)
        ent_s_limit = tk.Entry(frame_inputs, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=10)
        ent_s_limit.insert(0, str(def_s_limit))
        ent_s_limit.grid(row=1, column=1, padx=10, pady=8)
        apply_focus_highlight(ent_s_limit)
        
        var_limits = tk.BooleanVar(win, value=disable_limits)
        chk_limits = tk.Checkbutton(scrollable_frame, text="♾️ 解除所有車庫與特殊載具容量上限", variable=var_limits, bg=COLOR_CARD_BG, fg="white", selectcolor="#757575", font=FONT_BOLD, activebackground=COLOR_CARD_BG, activeforeground="white")
        chk_limits.pack(pady=5)
        
        var_overwrite = tk.BooleanVar(win, value=False)
        chk_overwrite = tk.Checkbutton(scrollable_frame, text="⚠️ 強制套用預設上限至所有「現有車庫/載具」", variable=var_overwrite, bg=COLOR_CARD_BG, fg="#F39C12", selectcolor="#757575", font=FONT_BOLD, activebackground=COLOR_CARD_BG, activeforeground="white")
        chk_overwrite.pack(pady=5)

        ttk.Separator(scrollable_frame, orient="horizontal").pack(fill="x", pady=15, padx=20)
        
        tk.Label(scrollable_frame, text="🏷️ 自訂「取得方式」選單管理", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#F39C12").pack(pady=(5, 5))
        
        frame_acq = tk.Frame(scrollable_frame, bg=COLOR_CARD_BG)
        frame_acq.pack(fill="x", padx=50, pady=5)
        
        scrollbar_acq = ttk.Scrollbar(frame_acq)
        scrollbar_acq.pack(side="right", fill="y")
        
        list_acq = tk.Listbox(frame_acq, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", selectbackground="#4CAF50", height=5, relief="solid", yscrollcommand=scrollbar_acq.set)
        list_acq.pack(side="left", fill="both", expand=True)
        scrollbar_acq.config(command=list_acq.yview)
        
        temp_acq_list = self.data.get("acquire_options", ACQUIRE_OPTIONS).copy()
        for opt in temp_acq_list:
            list_acq.insert(tk.END, opt)
            
        btn_f_acq = tk.Frame(scrollable_frame, bg=COLOR_CARD_BG)
        btn_f_acq.pack(fill="x", padx=50, pady=5)
        
        ent_new_acq = tk.Entry(btn_f_acq, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=14)
        ent_new_acq.pack(side="left", padx=(0, 10), fill="x", expand=True, ipady=3)
        apply_focus_highlight(ent_new_acq)
        
        def add_acq(e=None):
            new_opt = ent_new_acq.get().strip()
            if new_opt and new_opt not in temp_acq_list:
                temp_acq_list.append(new_opt)
                list_acq.insert(tk.END, new_opt)
                ent_new_acq.delete(0, tk.END)
                list_acq.see(tk.END)
                
        def del_acq():
            sel = list_acq.curselection()
            if sel:
                idx = sel[0]
                temp_acq_list.pop(idx)
                list_acq.delete(idx)
                
        ent_new_acq.bind("<Return>", add_acq)
        tk.Button(btn_f_acq, text="➕ 新增", command=add_acq, bg="#4CAF50", fg="white", font=FONT_BOLD, relief="flat").pack(side="left", padx=2, ipady=1)
        tk.Button(btn_f_acq, text="🗑️ 刪除", command=del_acq, bg="#e74c3c", fg="white", font=FONT_BOLD, relief="flat").pack(side="left", padx=2, ipady=1)
            
        def save_settings():
            for key, var in vars_dict.items(): self.data["app_settings"][key] = var.get()
            
            try: new_g = int(ent_g_limit.get().strip())
            except: new_g = 10
            try: new_s = int(ent_s_limit.get().strip())
            except: new_s = 2
            
            self.data["app_settings"]["disable_all_limits"] = var_limits.get()
            self.data["app_settings"]["default_garage_limit"] = new_g
            self.data["app_settings"]["default_special_limit"] = new_s
            
            if var_overwrite.get():
                spec_carriers = [sv["name"] for sv in self.data.get("special_vehicles", [])]
                for g in self.data.get("garages", []):
                    if g != "未分類" and g != "帕格薩斯":
                        self.data["garage_limits"][g] = new_s if g in spec_carriers else new_g
                        
            self.data["acquire_options"] = temp_acq_list
            
            save_data(self.all_data); self.apply_settings(); self.check_login_status(); self.refresh_garage_table()
            messagebox.showinfo("設定儲存成功", "⚙️ 全域設定已成功儲存並套用！\n相關版面與容量規則已重新載入。", parent=win)
            
            win.destroy()
            self.show_toast_progress("⚙️ 設定已儲存套用")
            self.set_status("⚙️ 全域設定已更新，版面、容量規則與自訂選單已重新載入。", "#2196F3")
            
        tk.Button(scrollable_frame, text="💾 儲存並套用設定", command=save_settings, bg="#2196F3", fg="white", font=FONT_BOLD, relief="flat").pack(fill="x", padx=40, pady=(20, 20), ipady=4)

    def apply_settings(self):
        settings = self.data.get("app_settings", {}) if self.data else {"tool_stopwatch": True}
        if settings.get("tool_stopwatch", True):
            self.tools_menu.entryconfig("⏱️ 呼叫賽車與任務碼錶 (Pause準備/W計時/倒數)", state="normal")
            if HAS_KEYBOARD:
                try: keyboard.unhook_all()
                except: pass
                try:
                    keyboard.add_hotkey('pause', self.handle_pause_key)
                    keyboard.add_hotkey('w', self.handle_w_key)
                except Exception as e:
                    if not getattr(self, "keyboard_admin_warned", False):
                        messagebox.showwarning("權限不足", "全域快捷鍵綁定失敗！\n請關閉程式後，【以系統管理員身分】重新執行 (或以系統管理員開啟 VSCode / CMD)。\n\n否則碼錶在遊戲背景時無法使用。")
                        self.keyboard_admin_warned = True
            else:
                self.root.bind_all("<Pause>", self.handle_pause_key)
                self.root.bind_all("<w>", self.handle_w_key)
                self.root.bind_all("<W>", self.handle_w_key)
                if not getattr(self, "keyboard_warned", False):
                    messagebox.showinfo("💡 升級提示", "系統偵測到您尚未安裝全域快捷鍵模組。\n\n若您希望在 GTA5 遊戲全螢幕時，\n也能在背景按 Pause 鍵控制碼錶，\n請開啟 CMD 執行以下指令：\n\npip install keyboard")
                    self.keyboard_warned = True
        else:
            self.tools_menu.entryconfig("⏱️ 呼叫賽車與任務碼錶 (Pause準備/W計時/倒數)", state="disabled")
            if HAS_KEYBOARD:
                try: keyboard.unhook_all()
                except: pass
            self.root.unbind_all("<Pause>")
            self.root.unbind_all("<w>")
            self.root.unbind_all("<W>")
            if self.stopwatch_window and self.stopwatch_window.winfo_exists():
                self.stopwatch_window.destroy()
                self.is_running = False
                self.sw_state = "IDLE"

    def setup_status_bar(self):
        self.status_bar = tk.Label(self.root, text="💡 系統就緒。", bg="#111111", fg="#FF9800", font=FONT_BOLD, anchor="w", padx=15, pady=6); self.status_bar.pack(side="bottom", fill="x")

    def set_status(self, msg, color="#FF9800"):
        if hasattr(self, 'status_bar') and self.status_bar.winfo_exists(): self.status_bar.config(text=msg, fg=color)

    def log_action(self, msg):
        if not self.data: return
        full_msg = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]  {msg}"
        if "action_logs" not in self.data: self.data["action_logs"] = []
        self.data["action_logs"].append(full_msg); self.data["action_logs"] = self.data["action_logs"][-200:]
        save_data(self.all_data); self.refresh_logs_display()

    def center_toplevel_window(self, win, width, height):
        win.configure(bg=COLOR_MAIN_BG); self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - width) // 2; y = self.root.winfo_y() + (self.root.winfo_height() - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")

    def sort_treeview(self, tv, col, reverse):
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        try: l.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError: l.sort(key=lambda t: t[0].replace("📌 ", "").replace("🔒 ", "").replace("☑ ", "").replace("☐ ", ""), reverse=reverse)
        for index, (val, k) in enumerate(l): tv.move(k, '', index)
        for c in tv["columns"]:
            clean_text = tv.heading(c)["text"].replace(" ▲", "").replace(" ▼", "")
            tv.heading(c, text=f"{clean_text} {'▼' if reverse else '▲'}" if c == col else clean_text, command=lambda _c=c: self.sort_treeview(tv, _c, not reverse))

    def sync_special_from_vehicles(self):
        if not self.data: return
        for sv in self.data.get("special_vehicles", []): sv["inner_vehicle"] = ""
        for car in self.data.get("vehicles", []):
            g = car.get("garage", "")
            for sv in self.data.get("special_vehicles", []):
                if sv["name"] == g: sv["inner_vehicle"] += f", {car['name']}" if sv["inner_vehicle"] else car["name"]

    def sync_vehicles_from_special(self):
        if not self.data: return
        current_time = time.strftime('%Y-%m-%d %H:%M')
        for sv in self.data.get("special_vehicles", []):
            sv_name = sv["name"]; inner_car = sv.get("inner_vehicle", "")
            if inner_car and sv.get("can_store", False) and "," not in inner_car:
                found = any(car["name"] == inner_car and car.update({"garage": sv_name, "updated_at": current_time}) or True for car in self.data.get("vehicles", []) if car["name"] == inner_car)
                if not found:
                    self.data["vehicles"].append({
                        "name": inner_car, "garage": sv_name, "v_type": "", "acquire": "", "upgraded": "", 
                        "count": 1, "notes": f"自【{sv_name}】同步", "locked": False, "pinned": False,
                        "created_at": current_time, "updated_at": current_time
                    })

    def validate_tab1_vehicle_to_garage(self, car_name, target_garage, show_error=True):
        if target_garage in SUB_CARRIER_RULES:
            allowed = SUB_CARRIER_RULES[target_garage]
            if not any(a.lower() in car_name.lower() or car_name.lower() in a.lower() for a in allowed):
                if show_error: messagebox.showerror("違規停放", f"❌ 【{target_garage}】只能停放：\n{', '.join(allowed)}\n\n請修正車輛名稱或更換停放位置！")
                return False
        return True

    def setup_profile_bar(self):
        top_frame = tk.Frame(self.root, bg="#1a1a1a", pady=10); top_frame.pack(fill="x", side="top")
        tk.Label(top_frame, text="👤 選擇角色 ID:", bg="#1a1a1a", fg="white", font=FONT_BOLD).pack(side="left", padx=(15, 5))
        self.combo_profile = ttk.Combobox(top_frame, state="readonly", width=15, font=FONT_NORMAL); self.combo_profile.pack(side="left", padx=5)
        self.btn_login = tk.Button(top_frame, text="🔑 登入系統", command=self.login_profile, bg="#2e7d32", fg="white", font=FONT_BOLD, relief="flat", padx=8); self.btn_login.pack(side="left", padx=3)
        self.btn_logout = tk.Button(top_frame, text="🚪 安全登出", command=self.logout_profile, bg="#ef6c00", fg="white", font=FONT_BOLD, relief="flat", padx=8); self.btn_logout.pack(side="left", padx=3)
        self.btn_delete_profile = tk.Button(top_frame, text="🗑️ 刪除角色", command=self.delete_profile, bg="#c62828", fg="white", font=FONT_BOLD, relief="flat", padx=8); self.btn_delete_profile.pack(side="left", padx=15)
        add_tooltip(self.btn_delete_profile, "刪除選取之角色ID，其資料庫將被永久抹除且無法復原！")
        self.btn_create_profile = tk.Button(top_frame, text="➕ 新建 ID", command=self.create_profile, bg="#1565c0", fg="white", font=FONT_BOLD, relief="flat", padx=8); self.btn_create_profile.pack(side="right", padx=15)
        
        self.lbl_clock = tk.Label(top_frame, text="", bg="#1a1a1a", fg="#4CAF50", font=("Consolas", 13, "bold")); self.lbl_clock.pack(side="right", padx=20); self.update_clock() 
        self.update_profile_combo()

    def update_clock(self):
        self.lbl_clock.config(text=f"🕒 {time.strftime('%Y-%m-%d  %H:%M:%S')}"); self.root.after(1000, self.update_clock)

    def delete_profile(self):
        sel = self.combo_profile.get()
        if not sel: return messagebox.showwarning("操作提示", "請先在下拉選單中選取您想刪除的 ID！")
        if messagebox.askyesno("⚠️ 極度危險操作", f"確定要徹底刪除 ID：【 {sel} 】嗎？") and messagebox.askyesno("❗ 最後確認", "資料刪除後無法還原，確定抹除嗎？"):
            del self.all_data["profiles"][sel]; save_data(self.all_data); self.show_toast_progress(f"🗑️ 已抹除 ID：{sel}"); self.set_status(f"🗑️ 角色檔案 {sel} 已永久移除。", "#c62828")
            if self.current_id == sel: self.current_id = ""
            self.update_profile_combo(); self.combo_profile.set(""); self.check_login_status()

    def update_profile_combo(self):
        if self.current_id:
            self.combo_profile["values"] = [self.current_id]
            self.combo_profile.set(self.current_id)
        else:
            self.combo_profile["values"] = list(self.all_data.get("profiles", {}).keys())

    def check_login_status(self):
        is_logged_in = bool(self.current_id and self.current_id in self.all_data["profiles"])
        state_str = "normal" if is_logged_in else "disabled"
        
        self.btn_logout.config(state="normal" if is_logged_in else "disabled"); self.btn_login.config(state="disabled" if is_logged_in else "normal")
        self.btn_delete_profile.config(state="disabled" if is_logged_in else "normal") 
        
        if is_logged_in:
            self.data = self.all_data["profiles"][self.current_id]
            for key, default in [("vehicles", []), ("special_vehicles", []), ("garages", ["未分類", "日蝕大樓 1 號"]), ("action_logs", []), ("garage_categories", {}), ("acquire_options", ACQUIRE_OPTIONS.copy())]:
                if key not in self.data: self.data[key] = default
            if "garage_limits" not in self.data:
                self.data["garage_limits"] = {"未分類": 999}; 
                for g in self.data["garages"]: 
                    if g != "未分類": self.data["garage_limits"][g] = 10
            
            if "app_settings" not in self.data: self.data["app_settings"] = {}
            defaults = {
                "tab_bulletin": True, "tab_vehicles": True, "tab_non_personal": True, 
                "tab_special": True, "tab_garages": True, "tab_statistics": True, "tab_logs": True, 
                "tool_stopwatch": True, "disable_all_limits": False,
                "default_garage_limit": 10, "default_special_limit": 2,
                "default_countdown_sec": 300.0 
            }
            for k, v in defaults.items():
                if k not in self.data["app_settings"]: self.data["app_settings"][k] = v
            
            # ✨ 登入時自動修復帕格薩斯舊資料
            for v in self.data["vehicles"]:
                if v.get("garage") == "帕格薩斯" or v.get("v_type") == "帕格薩斯":
                    v["garage"] = "帕格薩斯"
                    v["v_type"] = "帕格薩斯"
                    v["count"] = 1
                    v["upgraded"] = "不可改裝"
            
            for g in self.data["garages"]:
                if g not in self.data["garage_categories"]:
                    if g in ["通瓦別墅", "利金漫莊園", "好麥塢宅第"]: self.data["garage_categories"][g] = "豪宅"
                    elif g == "日蝕大樓 1 號": self.data["garage_categories"][g] = "高階公寓"
                    elif g == "辦公室車庫": self.data["garage_categories"][g] = "商辦企業"
                    elif g == "名鑽賭場空中別墅": self.data["garage_categories"][g] = "豪華賭場"
                    elif g == "設施": self.data["garage_categories"][g] = "地下設施"
                    elif g == "未分類": self.data["garage_categories"][g] = "系統預設"
                    elif g == "帕格薩斯": self.data["garage_categories"][g] = "虛擬服務"
                    else: self.data["garage_categories"][g] = "一般車庫"
            
            self.checked_indices.clear() 
            
            self.cd_target_sec = self.data["app_settings"].get("default_countdown_sec", 300.0)
            if not getattr(self, 'is_running', False) and getattr(self, 'sw_mode', 'STOPWATCH') == "COUNTDOWN":
                self.elapsed_time = self.cd_target_sec
                self.update_stopwatch_ui()
        else: 
            self.current_id = ""; self.data = None
            if hasattr(self, 'text_logs'): self.text_logs.config(state="normal"); self.text_logs.delete("1.0", tk.END); self.text_logs.config(state="disabled")

        settings = self.data.get("app_settings", {}) if self.data else {"tab_bulletin": True, "tab_vehicles": True, "tab_non_personal": True, "tab_special": True, "tab_garages": True, "tab_statistics": True, "tab_logs": True}

        if not settings.get("tab_bulletin", True): self.notebook.tab(self.tab_bulletin, state="hidden")
        else: self.notebook.tab(self.tab_bulletin, state="normal")

        for key, tab in [("tab_vehicles", self.tab_vehicles), ("tab_non_personal", self.tab_non_personal), ("tab_special", self.tab_special), ("tab_garages", self.tab_garages), ("tab_statistics", self.tab_statistics), ("tab_logs", self.tab_logs)]:
            if not settings.get(key, True): self.notebook.tab(tab, state="hidden")
            else: self.notebook.tab(tab, state=state_str)
            
        self.update_garage_comboboxes(); self.update_acquire_comboboxes(); self.refresh_vehicle_tables(); self.refresh_special_table(); self.refresh_garage_table(); self.apply_settings()
        if is_logged_in: 
            self.refresh_logs_display()
            self.update_checked_button_text()
            
            sel_id = self.notebook.select()
            if sel_id:
                current_tab = self.notebook.tab(sel_id, "text")
                if "統計資料" in current_tab: self.refresh_statistics()

    def update_acquire_comboboxes(self):
        if not self.data: return
        acq_opts = self.data.get("acquire_options", ACQUIRE_OPTIONS)
        if hasattr(self, 'combo_acquire'):
            self.combo_acquire["values"] = acq_opts

    def login_profile(self):
        sel = self.combo_profile.get()
        if sel and sel in self.all_data["profiles"]: 
            self.current_id = sel
            self.update_profile_combo() 
            self.check_login_status()
            self.show_toast_progress(f"🔑 登入成功：{sel}"); self.set_status(f"🔑 成功登入角色：{sel}", "#4CAF50"); self.log_action("🔑 登入系統")

    def logout_profile(self): 
        if self.data: self.log_action("🚪 登出系統")
        self.current_id = ""
        self.update_profile_combo() 
        self.check_login_status()
        self.combo_profile.set("") 
        self.show_toast_progress("🚪 已登出"); self.set_status("🚪 已登出，請選擇 ID 登入。", "#FF9800")

    def create_profile(self):
        name = simpledialog.askstring("新建 ID", "請輸入新的遊戲 ID / 角色名稱:")
        if not name: return
        if name in self.all_data["profiles"]: return messagebox.showwarning("重複", "ID 已經存在！")
        init_log = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]  🌟 建立角色 ID 檔案"
        
        default_garages = ["未分類", "帕格薩斯", "日蝕大樓 1 號", "辦公室車庫", "名鑽賭場空中別墅", "設施", "通瓦別墅", "利金漫莊園", "好麥塢宅第"]
        default_limits = {"未分類": 999, "帕格薩斯": 999}
        for g in default_garages:
            if g not in ["未分類", "帕格薩斯"]: default_limits[g] = 10
            
        default_categories = {
            "未分類": "系統預設", "帕格薩斯": "虛擬服務", "日蝕大樓 1 號": "高階公寓", "辦公室車庫": "商辦企業", 
            "名鑽賭場空中別墅": "豪華賭場", "設施": "地下設施",
            "通瓦別墅": "豪宅", "利金漫莊園": "豪宅", "好麥塢宅第": "豪宅"
        }
        
        self.all_data["profiles"][name] = {
            "vehicles": [], "special_vehicles": [], "garages": default_garages, 
            "garage_limits": default_limits, "garage_categories": default_categories, "action_logs": [init_log],
            "acquire_options": ACQUIRE_OPTIONS.copy(),
            "app_settings": {
                "tab_bulletin": True, "tab_vehicles": True, "tab_non_personal": True, 
                "tab_special": True, "tab_garages": True, "tab_statistics": True, "tab_logs": True, 
                "tool_stopwatch": True, "disable_all_limits": False,
                "default_garage_limit": 10, "default_special_limit": 2
            }
        }
        save_data(self.all_data); self.update_profile_combo(); self.combo_profile.set(name); messagebox.showinfo("建立成功", f"成功建立：{name}")

    def show_toast_progress(self, message="✅ 操作成功"):
        toast = tk.Toplevel(self.root); toast.overrideredirect(True); toast.attributes("-topmost", True); toast.configure(bg=COLOR_CARD_BG)
        self.root.update_idletasks()
        toast.geometry(f"320x70+{self.root.winfo_rootx() + self.root.winfo_width() - 320 - 20}+{self.root.winfo_rooty() + self.root.winfo_height() - 70 - 20}")
        frame = tk.Frame(toast, bg=COLOR_CARD_BG, highlightbackground="#4CAF50", highlightthickness=2); frame.pack(fill="both", expand=True)
        tk.Label(frame, text=message, bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).pack(expand=True, pady=5)
        def step(v):
            if not toast.winfo_exists(): return 
            if v <= 100: toast.after(20, step, v + 5)
            else: toast.after(800, lambda: toast.destroy() if toast.winfo_exists() else None)
        step(0)

    def get_active_tree(self, event=None):
        if event and hasattr(event, 'widget') and isinstance(event.widget, ttk.Treeview): return event.widget
        current_tab_id = self.notebook.select()
        if "非個人" in self.notebook.tab(current_tab_id, "text"): return self.tree_non_personal
        return self.tree_vehicles

    # 🌟 滑鼠懸停雷達：自動顯示時間
    def on_vehicle_hover(self, event):
        if not self.data: return
        tree = event.widget
        iid = tree.identify_row(event.y)
        if iid:
            if getattr(self, "last_hovered_iid", None) != iid:
                self.last_hovered_iid = iid
                try:
                    idx = int(iid)
                    car = self.data["vehicles"][idx]
                    created = car.get("created_at", "-")
                    updated = car.get("updated_at", "-")
                    self.set_status(f"🕒 【{car['name']}】 登記日期：{created}   |   最後修改：{updated}", "#3498db")
                except: pass
        else:
            if getattr(self, "last_hovered_iid", None) is not None:
                self.last_hovered_iid = None
                self.set_status("💡 系統就緒。", "#FF9800")

    # ==========================================
    #     📢 0. 系統公告分頁
    # ==========================================
    def setup_bulletin_tab(self):
        title_lbl = tk.Label(self.tab_bulletin, text="📢 洛聖都資產管理系統 - 系統公告與完整更新日誌", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#4CAF50")
        title_lbl.pack(pady=(30, 15))
        
        text_frame = tk.Frame(self.tab_bulletin, bg=COLOR_MAIN_BG)
        text_frame.pack(fill="both", expand=True, padx=40, pady=(0, 40))
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        
        text_area = tk.Text(text_frame, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, relief="solid", padx=20, pady=20, wrap="word", yscrollcommand=scrollbar.set)
        text_area.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text_area.yview)
        
        content = f"""【系統更新公告】

🌟 最新版本：V{APP_VERSION} 帕格薩斯絕對規則版
📅 更新日期：2026-07-31

📝 本次版本修改與新增項目：
1. [新增] 🚁 帕格薩斯全面支援與防呆限制：完美解決玩家管理帕格薩斯武裝載具的需求！現在只要將載具設為帕格薩斯，系統將嚴格套用三大規則：【數量強制鎖定1台】、【改裝狀態強制鎖為「不可改裝」】、【車庫與載具類型雙向綁定】，杜絕任何錯誤設定。
2. [優化] 🧹 舊有資料自動清洗修復：登入角色時，系統會自動幫您檢查以前手動新增的帕格薩斯載具，並將舊的錯誤數量或改裝狀態全部自動修正為正確格式。

--------------------------------------------------
【歷史完整更新回顧】

🔸 版本：V4.43.0 介面記憶儲存版
- [新增] 💾 介面配置記憶引擎：系統會自動在關閉時記憶您當下的版面配置大小與全螢幕狀態，下次開啟直接完美還原！

🔸 版本：V4.42.0 狀態列雷達版
- [優化] 🌟 狀態列雷達顯示：將時間移出表格，保持畫面清爽。只要將滑鼠停在車輛上，下方狀態列就會浮現該車的「登記日期」與「最後修改時間」。

🔸 版本：V4.41.0 完美響應式與雙時區版
- [優化] 📐 彈性排版與 RWD：全面導入自適應網格 (Grid) 系統！視窗最大化時，所有的輸入框與表格都會完美地等比拉伸。
- [新增] 🕒 登記日期與最後修改：不僅記錄修改時間，還額外新增了「登記日期」欄位。

🔸 版本：V4.39.0 系統純淨優化版
- [優化] 🗑️ 徹底拔除 OCR 模組：果斷移除不穩定的 OCR 辨識引擎與龐大依賴庫，讓系統啟動極速、記憶體佔用極低！

🔸 版本：V4.38.1 權限除錯版
- [修復] ⏱️ 碼錶快捷鍵警告機制：如果系統攔截了背景快捷鍵的權限，現在會彈出明確的錯誤警告，不再默默失效！

🔸 版本：V4.29.0 重複清理大師版
- [新增] 🔍 車輛檢查按鈕與一鍵智能合併。

🔸 版本：V4.28.2 智慧防重版
- [新增] 攔截手動新增時的重複車輛。

🔸 版本：V4.28.1 倒數精準記憶版
- [新增] 儲存記憶與隱藏倒數計時設定。

🔸 版本：V4.28.0 倒數計時功能版
- [新增] ⏱️ 倒數計時器模式：支援「正向計時」與「倒數計時」雙模式切換！
"""
        text_area.insert("1.0", content)
        text_area.config(state="disabled")

    # ==========================================
    #     📊 0.4. 統計資料分頁 (Statistics)
    # ==========================================
    def setup_statistics_tab(self):
        title_lbl = tk.Label(self.tab_statistics, text="📊 洛聖都資產統計儀表板", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#F39C12")
        title_lbl.pack(pady=(20, 10))
        
        self.canvas_stats = tk.Canvas(self.tab_statistics, borderwidth=0, bg=COLOR_MAIN_BG, highlightthickness=0)
        self.scrollbar_stats = ttk.Scrollbar(self.tab_statistics, orient="vertical", command=self.canvas_stats.yview)
        self.stats_frame = tk.Frame(self.canvas_stats, bg=COLOR_MAIN_BG)

        self.stats_frame.bind("<Configure>", lambda e: self.canvas_stats.configure(scrollregion=self.canvas_stats.bbox("all")))
        self.canvas_stats.create_window((0, 0), window=self.stats_frame, anchor="nw", width=1200) 
        self.canvas_stats.configure(yscrollcommand=self.scrollbar_stats.set)
        
        self.canvas_stats.pack(side="left", fill="both", expand=True, padx=15, pady=10)
        self.scrollbar_stats.pack(side="right", fill="y")
        
        def _on_stats_scroll(event):
            if hasattr(self, 'canvas_stats') and self.canvas_stats.winfo_exists():
                if event.delta: self.canvas_stats.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.tab_statistics.bind("<Enter>", lambda e: self.canvas_stats.bind_all("<MouseWheel>", _on_stats_scroll))
        self.tab_statistics.bind("<Leave>", lambda e: self.canvas_stats.unbind_all("<MouseWheel>"))

    def refresh_statistics(self):
        for widget in self.stats_frame.winfo_children(): widget.destroy()
        if not self.data: return
        
        vehicles = self.data.get("vehicles", [])
        garages = self.data.get("garages", [])
        specials = self.data.get("special_vehicles", [])
        limits = self.data.get("garage_limits", {})
        disable_limits = self.data.get("app_settings", {}).get("disable_all_limits", False)
        
        total_cars = sum(v.get("count", 1) for v in vehicles)
        actual_garages = [g for g in garages if g not in ["未分類", "帕格薩斯"]]
        total_garages = len(actual_garages)
        total_specials = len(specials)
        
        type_counts = {"個人載具": 0, "非個人載具": 0, "帕格薩斯": 0, "未設定": 0}
        upg_counts = {"已改滿": 0, "未改滿": 0, "不可改裝": 0, "未設定": 0}
        acq_counts = {}

        for v in vehicles:
            c = v.get("count", 1)
            vt = v.get("v_type", "")
            if not vt: vt = "未設定"
            if vt in type_counts: type_counts[vt] += c
            else: type_counts["未設定"] += c

            upg = v.get("upgraded", "")
            if not upg: upg = "未設定"
            if upg in upg_counts: upg_counts[upg] += c
            else: upg_counts["未設定"] += c

            acq = v.get("acquire", "")
            if not acq: acq = "未設定"
            acq_counts[acq] = acq_counts.get(acq, 0) + c

        total_capacity = 0
        total_used_in_capacity = 0
        
        for g in actual_garages:
            lim = limits.get(g, 10)
            total_capacity += lim
            total_used_in_capacity += self.count_cars_in_garage(g)
            
        for sv in specials:
            if sv.get("can_store", False):
                sv_name = sv.get("name")
                lim = limits.get(sv_name, 2)
                total_capacity += lim
                total_used_in_capacity += self.count_cars_in_garage(sv_name)

        usage_pct = (total_used_in_capacity / total_capacity * 100) if total_capacity > 0 else 0
        
        row1 = tk.Frame(self.stats_frame, bg=COLOR_MAIN_BG)
        row1.pack(fill="x", pady=10)
        
        def create_stat_card(parent, title, value, color):
            f = tk.Frame(parent, bg=COLOR_CARD_BG, highlightbackground=color, highlightthickness=2, padx=15, pady=15)
            f.pack(side="left", fill="both", expand=True, padx=10)
            tk.Label(f, text=title, font=FONT_BOLD, bg=COLOR_CARD_BG, fg=COLOR_TEXT_GRAY).pack()
            tk.Label(f, text=str(value), font=("Consolas", 24, "bold"), bg=COLOR_CARD_BG, fg=color).pack(pady=(10, 0))
        
        create_stat_card(row1, "🚗 總擁有載具數量", total_cars, "#3498db")
        create_stat_card(row1, "🏠 總持有車庫物業", total_garages, "#4CAF50")
        create_stat_card(row1, "🚁 總特種設備數量", total_specials, "#e91e63")
        
        capacity_text = f"{total_used_in_capacity} / ∞" if disable_limits else f"{total_used_in_capacity} / {total_capacity}"
        create_stat_card(row1, "🅿️ 總車位使用率", capacity_text, "#F39C12")

        row2 = tk.Frame(self.stats_frame, bg=COLOR_MAIN_BG)
        row2.pack(fill="x", pady=15)
        
        # 📐 重寫為支援動態數量的長條圖表函數
        def create_bar_stat(parent, title, items):
            f = tk.LabelFrame(parent, text=f" {title} ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="white", bd=2, padx=20, pady=20)
            f.pack(side="left", fill="both", expand=True, padx=10)
            
            total = sum(val for val, lbl, color in items)
            if total == 0: total = 1 
            
            for idx, (val, lbl, color) in enumerate(items):
                pct = val / total * 100
                tk.Label(f, text=f"{lbl} ({val}) - {pct:.1f}%", font=FONT_BOLD, bg=COLOR_CARD_BG, fg=color).pack(anchor="w")
                pady_bottom = 10 if idx < len(items) - 1 else 0
                ttk.Progressbar(f, length=400, mode="determinate", value=pct).pack(fill="x", pady=(2, pady_bottom))

        create_bar_stat(row2, "🔧 改裝狀態分布", [
            (upg_counts["已改滿"], "✅ 已改滿", "#4CAF50"),
            (upg_counts["未改滿"], "⚠️ 未改滿", "#e74c3c"),
            (upg_counts["不可改裝"], "❌ 不可改裝", "#9b59b6"),
            (upg_counts["未設定"], "❓ 未設定", "#95a5a6")
        ])
                        
        create_bar_stat(row2, "🚜 載具類型分布", [
            (type_counts["個人載具"], "🚗 個人載具", "#3498db"),
            (type_counts["非個人載具"], "🚜 非個人載具", "#F39C12"),
            (type_counts["帕格薩斯"], "🚁 帕格薩斯", "#9b59b6"),
            (type_counts["未設定"], "❓ 未設定", "#95a5a6")
        ])

        row3 = tk.LabelFrame(self.stats_frame, text=" 🎁 載具取得方式排行榜 ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#9b59b6", bd=2, padx=20, pady=20)
        row3.pack(fill="x", padx=10, pady=10)
        
        sorted_acq = sorted(acq_counts.items(), key=lambda item: item[1], reverse=True)
        if not sorted_acq:
            tk.Label(row3, text="目前沒有任何車輛資料可供分析。", font=FONT_NORMAL, bg=COLOR_CARD_BG, fg=COLOR_TEXT_GRAY).pack()
        else:
            for acq, count in sorted_acq:
                pct = count / total_cars * 100 if total_cars > 0 else 0
                f = tk.Frame(row3, bg=COLOR_CARD_BG)
                f.pack(fill="x", pady=4)
                tk.Label(f, text=f"▪️ {acq}", width=20, anchor="w", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="white").pack(side="left")
                tk.Label(f, text=f"{count} 台", width=8, anchor="e", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="#9b59b6").pack(side="left")
                tk.Label(f, text=f"({pct:.1f}%)", width=8, anchor="e", font=FONT_NORMAL, bg=COLOR_CARD_BG, fg=COLOR_TEXT_GRAY).pack(side="left", padx=(0, 15))
                ttk.Progressbar(f, length=600, mode="determinate", value=pct).pack(side="left", fill="x", expand=True)

    # ==========================================
    #     📜 0.5. 操作日誌分頁 (Action Logs)
    # ==========================================
    def setup_logs_tab(self):
        header_frame = tk.Frame(self.tab_logs, bg=COLOR_MAIN_BG); header_frame.pack(fill="x", padx=15, pady=15)
        tk.Label(header_frame, text="📜 帳號操作日誌 (最多保留最近 200 筆紀錄)", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#4CAF50").pack(side="left")
        tk.Button(header_frame, text="🗑️ 清空歷史日誌", command=self.clear_logs, bg="#c62828", fg="white", font=FONT_BOLD, relief="flat", padx=8).pack(side="right")
        self.text_logs = tk.Text(self.tab_logs, font=("Consolas", 11), bg=COLOR_CARD_BG, fg="#a8e6cf", relief="solid", padx=15, pady=15)
        vsb = ttk.Scrollbar(self.tab_logs, orient="vertical", command=self.text_logs.yview); self.text_logs.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", pady=(0, 15), padx=(0, 15)); self.text_logs.pack(fill="both", expand=True, padx=(15, 0), pady=(0, 15)); self.text_logs.config(state="disabled")

    def refresh_logs_display(self):
        if not hasattr(self, 'text_logs') or not self.text_logs.winfo_exists(): return
        self.text_logs.config(state="normal"); self.text_logs.delete("1.0", tk.END)
        if self.data and "action_logs" in self.data:
            for log in reversed(self.data["action_logs"]): self.text_logs.insert(tk.END, log + "\n\n")
        self.text_logs.config(state="disabled")

    def clear_logs(self):
        if not self.data: return
        if messagebox.askyesno("危險操作", "確定要清空此角色的所有操作日誌嗎？\n清空後將無法復原。"):
            self.data["action_logs"] = []; save_data(self.all_data); self.refresh_logs_display(); self.show_toast_progress("🗑️ 日誌已清空"); self.log_action("🗑️ 執行清空歷史操作日誌")

    # ==========================================
    #   ✨ 勾選功能核心邏輯
    # ==========================================
    def update_checked_button_text(self):
        count = len(self.checked_indices) if hasattr(self, 'checked_indices') else 0
        text = f"✏️ 修改已勾選 ({count})"
        if hasattr(self, 'btn_batch_edit_v') and self.btn_batch_edit_v.winfo_exists(): self.btn_batch_edit_v.config(text=text)
        if hasattr(self, 'btn_batch_edit_np') and self.btn_batch_edit_np.winfo_exists(): self.btn_batch_edit_np.config(text=text)

    def on_tree_click(self, event):
        if not self.data: return
        tree = event.widget
        if tree.identify_region(event.x, event.y) != "cell": return
        if tree.identify_column(event.x) == "#1": 
            item_iid = tree.identify_row(event.y)
            if not item_iid: return
            idx = int(item_iid)
            if idx in self.checked_indices:
                self.checked_indices.remove(idx); tree.set(item_iid, "check", "☐")
            else:
                self.checked_indices.add(idx); tree.set(item_iid, "check", "☑")
            self.update_checked_button_text()

    def select_all_vehicles(self, event=None):
        if not self.data: return
        target_tree = self.get_active_tree(event)
        children = target_tree.get_children(); added = 0
        for child in children:
            idx = int(child)
            if idx not in self.checked_indices:
                self.checked_indices.add(idx); target_tree.set(child, "check", "☑"); added += 1
        self.update_checked_button_text()
        self.set_status(f"☑️ 成功全選目前畫面上的 {added} 筆載具！", "#9b59b6")

    def edit_checked_vehicles(self):
        if not self.data: return
        if not self.checked_indices:
            messagebox.showwarning("提示", "您還沒有勾選任何載具！\n請點擊列表最左側的方塊來跨次搜尋勾選。")
            return
        selected = [str(i) for i in self.checked_indices]
        self.open_edit_window(pre_selected=selected)

    # === 🔍 重複車輛智能檢查引擎 ===
    def check_duplicate_vehicles(self):
        if not self.data: return
        
        name_map = defaultdict(list)
        for idx, v in enumerate(self.data.get("vehicles", [])):
            name_map[v["name"].strip().lower()].append(idx)
            
        duplicates = {name: indices for name, indices in name_map.items() if len(indices) > 1}
        
        if not duplicates:
            messagebox.showinfo("檢查結果", "✅ 太棒了！您的車庫清單中目前沒有任何重複的車輛。")
            self.set_status("✅ 檢查完畢：目前車庫清單中無任何重複車輛。", "#4CAF50")
            return
            
        win = tk.Toplevel(self.root)
        win.title("🔍 發現重複車輛")
        self.center_toplevel_window(win, 450, 500)
        win.configure(bg=COLOR_CARD_BG)
        
        tk.Label(win, text=f"⚠️ 系統偵測到 {len(duplicates)} 組重複的車輛紀錄：", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#F39C12").pack(pady=(15, 5))
        tk.Label(win, text="(選擇「一鍵智能合併」將自動保留第一筆位置，並將其餘數量累加)", font=FONT_NORMAL, bg=COLOR_CARD_BG, fg=COLOR_TEXT_GRAY).pack(pady=(0, 10))
        
        frame_list = tk.Frame(win, bg=COLOR_MAIN_BG)
        frame_list.pack(fill="both", expand=True, padx=25, pady=5)
        
        scrollbar = ttk.Scrollbar(frame_list)
        scrollbar.pack(side="right", fill="y")
        
        listbox = tk.Listbox(frame_list, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", yscrollcommand=scrollbar.set, relief="solid", selectbackground="#4CAF50")
        
        for name, indices in duplicates.items():
            real_name = self.data["vehicles"][indices[0]]["name"]
            garages = [self.data["vehicles"][i]["garage"] for i in indices]
            garage_str = ", ".join(garages)
            if len(garage_str) > 30: garage_str = garage_str[:27] + "..."
            listbox.insert(tk.END, f"▪ {real_name} (共 {len(indices)} 筆)")
            listbox.insert(tk.END, f"  📍 分佈: {garage_str}")
            listbox.insert(tk.END, "") 
            
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)
        
        def do_auto_merge():
            if not messagebox.askyesno("最後確認", "確定要將這些重複紀錄合併嗎？\n\n(此操作會把數量全部加總到第一筆紀錄，並刪除多餘的紀錄，建議操作前已備份)", parent=win):
                return
                
            indices_to_delete = []
            merged_count = 0
            current_time = time.strftime('%Y-%m-%d %H:%M')
            
            for name, indices in duplicates.items():
                first_idx = indices[0]
                total_extra = 0
                is_pegasus = self.data["vehicles"][first_idx].get("garage") == "帕格薩斯" or self.data["vehicles"][first_idx].get("v_type") == "帕格薩斯"
                
                for other_idx in indices[1:]:
                    if not is_pegasus:
                        try: c = int(self.data["vehicles"][other_idx].get("count", 1))
                        except: c = 1
                        total_extra += c
                    indices_to_delete.append(other_idx)
                    merged_count += 1
                    
                if is_pegasus:
                    self.data["vehicles"][first_idx]["count"] = 1
                    self.data["vehicles"][first_idx]["upgraded"] = "不可改裝"
                else:
                    try: first_c = int(self.data["vehicles"][first_idx].get("count", 1))
                    except: first_c = 1
                    self.data["vehicles"][first_idx]["count"] = first_c + total_extra
                    
                self.data["vehicles"][first_idx]["updated_at"] = current_time
                
            for idx in sorted(indices_to_delete, reverse=True):
                del self.data["vehicles"][idx]
                
            self.checked_indices.clear()
            self.update_checked_button_text()
            self.sync_special_from_vehicles()
            save_data(self.all_data)
            
            self.log_action(f"🧹 智能清理：自動合併了 {len(duplicates)} 組重複車輛，共移除了 {merged_count} 筆多餘紀錄。")
            self.refresh_vehicle_tables()
            self.refresh_special_table()
            self.refresh_garage_table()
            
            self.show_toast_progress(f"✅ 成功合併 {merged_count} 筆重複紀錄")
            self.set_status(f"🧹 系統清理完畢，成功合併 {merged_count} 筆重複紀錄。", "#4CAF50")
            win.destroy()
            
        btn_frame = tk.Frame(win, bg=COLOR_CARD_BG)
        btn_frame.pack(fill="x", padx=25, pady=15)
        
        tk.Button(btn_frame, text="✨ 一鍵智能合併", command=do_auto_merge, bg="#2196F3", fg="white", font=FONT_BOLD, relief="flat").pack(side="left", expand=True, fill="x", padx=(0, 5), ipady=4)
        tk.Button(btn_frame, text="關閉 (手動處理)", command=win.destroy, bg="#555555", fg="white", font=FONT_BOLD, relief="flat").pack(side="right", expand=True, fill="x", padx=(5, 0), ipady=4)

    # ==========================================
    #     🚗 1. 車輛管理頁面 
    # ==========================================
    def setup_vehicles_tab(self):
        input_frame = tk.LabelFrame(self.tab_vehicles, text=" 📝 登記新載具資產 ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#4CAF50", padx=12, pady=12, bd=2)
        input_frame.pack(fill="x", padx=15, pady=10)

        for i in range(7): input_frame.columnconfigure(i, weight=0)
        input_frame.columnconfigure(1, weight=1)
        input_frame.columnconfigure(3, weight=1)
        input_frame.columnconfigure(5, weight=1)

        tk.Label(input_frame, text="載具名稱:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=0, sticky="e", pady=5, padx=5)
        self.entry_name = tk.Entry(input_frame, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid")
        self.entry_name.grid(row=0, column=1, sticky="we", padx=5, pady=5)
        apply_focus_highlight(self.entry_name); self.entry_name.bind("<Return>", lambda e: self.combo_garage.focus()); self.entry_name.bind("<FocusIn>", lambda e: self.set_status("📍 當前游標位置：【載具名稱】 (輸入完請按 Enter 跳下一格)", "#00E676"), add="+")

        tk.Label(input_frame, text="存放位置:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=2, sticky="e", pady=5, padx=5)
        self.combo_garage = ttk.Combobox(input_frame, state="readonly", font=FONT_NORMAL)
        self.combo_garage.grid(row=0, column=3, sticky="we", padx=5, pady=5)
        self.combo_garage.bind("<Return>", lambda e: self.combo_acquire.focus()); self.combo_garage.bind("<FocusIn>", lambda e: self.set_status("📍 當前游標位置：【存放位置】 (可按 ↑ ↓ 鍵快速選擇，選完請按 Enter)", "#00E676"), add="+")

        tk.Label(input_frame, text="取得方式:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=4, sticky="e", pady=5, padx=5)
        self.combo_acquire = ttk.Combobox(input_frame, state="readonly", font=FONT_NORMAL)
        self.combo_acquire.grid(row=0, column=5, sticky="we", padx=5, pady=5)
        self.combo_acquire.bind("<Return>", lambda e: self.add_vehicle()); self.combo_acquire.bind("<FocusIn>", lambda e: self.set_status("📍 當前游標位置：【取得方式】 (選完按 Enter 即可直接送出新增！)", "#00E676"), add="+")

        tk.Button(input_frame, text="➕ 新增登記", command=self.add_vehicle, bg="#4CAF50", fg="white", font=FONT_BOLD, relief="flat", padx=20).grid(row=0, column=6, sticky="e", padx=(15, 5), pady=5)

        action_frame = tk.Frame(self.tab_vehicles, bg=COLOR_MAIN_BG); action_frame.pack(fill="x", padx=15, pady=5)
        tk.Label(action_frame, text="🔍 全域搜尋:", bg=COLOR_MAIN_BG, fg="white", font=FONT_NORMAL).pack(side="left")
        self.entry_search = tk.Entry(action_frame, width=20, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); self.entry_search.pack(side="left", padx=5); self.entry_search.bind("<KeyRelease>", lambda e: self.apply_filters())
        apply_focus_highlight(self.entry_search) 
        
        tk.Label(action_frame, text="  |  篩選車庫位置:", bg=COLOR_MAIN_BG, fg="white", font=FONT_NORMAL).pack(side="left", padx=5)
        self.combo_garage_filter = ttk.Combobox(action_frame, width=20, state="readonly", font=FONT_NORMAL); self.combo_garage_filter.pack(side="left", padx=5); self.combo_garage_filter.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())
        tk.Button(action_frame, text="重置", command=self.reset_filters, bg="#555555", fg="white", font=FONT_BOLD, relief="flat", padx=8).pack(side="left", padx=6)

        btn_frame_chk = tk.Frame(action_frame, bg=COLOR_MAIN_BG); btn_frame_chk.pack(side="right")
        self.btn_check_dup = tk.Button(btn_frame_chk, text="🔍 檢查重複", command=self.check_duplicate_vehicles, bg="#9b59b6", fg="white", font=FONT_BOLD, relief="flat", padx=6)
        self.btn_check_dup.pack(side="left", padx=3)
        
        self.btn_batch_edit_v = tk.Button(btn_frame_chk, text="✏️ 修改已勾選 (0)", command=self.edit_checked_vehicles, bg="#F39C12", fg="white", font=FONT_BOLD, relief="flat", padx=6)
        self.btn_batch_edit_v.pack(side="left", padx=3)

        tree_frame = tk.Frame(self.tab_vehicles, bg=COLOR_MAIN_BG); tree_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        self.tree_vehicles = ttk.Treeview(tree_frame, columns=("check", "name", "garage", "vtype", "acquire", "upgrade", "count", "notes"), show="headings", selectmode="extended")
        
        columns_config = {"check": "☑ 選取", "name": "車輛名稱", "garage": "存放位置", "vtype": "類型", "acquire": "取得方式", "upgrade": "改裝", "count": "數量", "notes": "備註"}
        for col, text in columns_config.items(): self.tree_vehicles.heading(col, text=text, command=lambda c=col: self.sort_treeview(self.tree_vehicles, c, False))
        
        self.tree_vehicles.column("check", width=60, anchor="center", stretch=False)
        self.tree_vehicles.column("name", width=180, anchor="w", stretch=True)
        self.tree_vehicles.column("garage", width=140, anchor="center", stretch=True)
        self.tree_vehicles.column("vtype", width=90, anchor="center", stretch=False)
        self.tree_vehicles.column("acquire", width=100, anchor="center", stretch=False)
        self.tree_vehicles.column("upgrade", width=80, anchor="center", stretch=False)
        self.tree_vehicles.column("count", width=50, anchor="center", stretch=False)
        self.tree_vehicles.column("notes", width=120, anchor="w", stretch=True)
        
        self.tree_vehicles.bind("<ButtonRelease-1>", self.on_tree_click) 
        self.tree_vehicles.bind("<Control-a>", self.select_all_vehicles); self.tree_vehicles.bind("<Control-A>", self.select_all_vehicles)
        self.tree_vehicles.bind("<Double-1>", self.open_edit_window); self.tree_vehicles.bind("<Return>", self.open_edit_window); self.tree_vehicles.bind("<Delete>", self.delete_vehicle)
        self.tree_vehicles.bind("<Motion>", self.on_vehicle_hover)
        self.tree_vehicles.bind("<Leave>", lambda e: self.set_status("💡 系統就緒。", "#FF9800"))
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_vehicles.yview); self.tree_vehicles.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y"); self.tree_vehicles.pack(side="left", fill="both", expand=True)
        self.vehicle_popup_menu = tk.Menu(self.root, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL); self.tree_vehicles.bind("<Button-3>", self.show_vehicle_context_menu)

    # ==========================================
    #     🚜 1.5 非個人載具頁面
    # ==========================================
    def setup_non_personal_tab(self):
        header_frame = tk.Frame(self.tab_non_personal, bg=COLOR_MAIN_BG); header_frame.pack(fill="x", padx=15, pady=15)
        tk.Label(header_frame, text="🚜 非個人載具與帕格薩斯列表", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#FF9800").pack(side="left")
        tk.Label(header_frame, text=" (請統一在「車輛管理」面板新增，系統會自動過濾至此區)", font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg=COLOR_TEXT_GRAY).pack(side="left")

        btn_frame_np = tk.Frame(header_frame, bg=COLOR_MAIN_BG); btn_frame_np.pack(side="right")
        self.btn_check_dup_np = tk.Button(btn_frame_np, text="🔍 檢查重複", command=self.check_duplicate_vehicles, bg="#9b59b6", fg="white", font=FONT_BOLD, relief="flat", padx=6)
        self.btn_check_dup_np.pack(side="left", padx=3)
        
        self.btn_batch_edit_np = tk.Button(btn_frame_np, text="✏️ 修改已勾選 (0)", command=self.edit_checked_vehicles, bg="#F39C12", fg="white", font=FONT_BOLD, relief="flat", padx=6)
        self.btn_batch_edit_np.pack(side="left", padx=3)

        tree_frame = tk.Frame(self.tab_non_personal, bg=COLOR_MAIN_BG); tree_frame.pack(fill="both", expand=True, padx=15, pady=5)
        self.tree_non_personal = ttk.Treeview(tree_frame, columns=("check", "name", "garage", "vtype", "acquire", "upgrade", "count", "notes"), show="headings", selectmode="extended")
        
        columns_config = {"check": "☑ 選取", "name": "車輛名稱", "garage": "存放位置", "vtype": "類型", "acquire": "取得方式", "upgrade": "改裝", "count": "數量", "notes": "備註"}
        for col, text in columns_config.items(): self.tree_non_personal.heading(col, text=text, command=lambda c=col: self.sort_treeview(self.tree_non_personal, c, False))
        
        self.tree_non_personal.column("check", width=60, anchor="center", stretch=False)
        self.tree_non_personal.column("name", width=180, anchor="w", stretch=True)
        self.tree_non_personal.column("garage", width=140, anchor="center", stretch=True)
        self.tree_non_personal.column("vtype", width=90, anchor="center", stretch=False)
        self.tree_non_personal.column("acquire", width=100, anchor="center", stretch=False)
        self.tree_non_personal.column("upgrade", width=80, anchor="center", stretch=False)
        self.tree_non_personal.column("count", width=50, anchor="center", stretch=False)
        self.tree_non_personal.column("notes", width=120, anchor="w", stretch=True)
        
        self.tree_non_personal.bind("<ButtonRelease-1>", self.on_tree_click) 
        self.tree_non_personal.bind("<Control-a>", self.select_all_vehicles); self.tree_non_personal.bind("<Control-A>", self.select_all_vehicles)
        self.tree_non_personal.bind("<Double-1>", self.open_edit_window); self.tree_non_personal.bind("<Return>", self.open_edit_window); self.tree_non_personal.bind("<Delete>", self.delete_vehicle); self.tree_non_personal.bind("<Button-3>", self.show_vehicle_context_menu)
        self.tree_non_personal.bind("<Motion>", self.on_vehicle_hover)
        self.tree_non_personal.bind("<Leave>", lambda e: self.set_status("💡 系統就緒。", "#FF9800"))

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_non_personal.yview); self.tree_non_personal.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y"); self.tree_non_personal.pack(side="left", fill="both", expand=True)

    def update_garage_comboboxes(self):
        if not self.data: return
        spec_carriers = [sv["name"] for sv in self.data.get("special_vehicles", []) if sv.get("can_store", False)]
        # ✨ 將未分類和帕格薩斯永遠排最上面
        user_garages = [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]
        combined_list = ["未分類", "帕格薩斯"] + user_garages + spec_carriers
        
        self.combo_garage["values"] = combined_list
        self.combo_garage_filter["values"] = ["全部"] + combined_list
        if self.combo_garage_filter.get() == "": self.combo_garage_filter.set("全部")
        
        if hasattr(self, 'combo_spec_location'):
            self.combo_spec_location["values"] = ["未分類"] + user_garages
            if not self.combo_spec_location.get():
                self.combo_spec_location.set("未分類")

    def count_cars_in_garage(self, garage_name):
        if not self.data: return 0
        return sum(c.get("count", 1) for c in self.data["vehicles"] if c["garage"] == garage_name)

    def refresh_vehicle_tables(self, search_results=None):
        for i in self.tree_vehicles.get_children(): self.tree_vehicles.delete(i)
        if hasattr(self, 'tree_non_personal'):
            for i in self.tree_non_personal.get_children(): self.tree_non_personal.delete(i)
            
        if not self.data: return
        data_to_sort = search_results if search_results is not None else enumerate(self.data["vehicles"])
        pinned_items = []; normal_items = []
        
        for idx, car in data_to_sort:
            if car.get("pinned", False): pinned_items.append((idx, car))
            else: normal_items.append((idx, car))
            
        for idx, car in pinned_items + normal_items:
            display_name = car["name"]
            if car.get("locked", False): display_name = "🔒 " + display_name
            if car.get("pinned", False): display_name = "📌 " + display_name
            
            check_symbol = "☑" if idx in getattr(self, 'checked_indices', set()) else "☐"
            
            values = (check_symbol, display_name, car["garage"], car.get("v_type", ""), car.get("acquire", ""), car.get("upgraded", ""), car.get("count", 1), car.get("notes", ""))
            
            if car.get("v_type", "") in ["非個人載具", "帕格薩斯"]:
                if hasattr(self, 'tree_non_personal'): self.tree_non_personal.insert("", "end", iid=str(idx), values=values)
            else:
                self.tree_vehicles.insert("", "end", iid=str(idx), values=values)

    def add_vehicle(self):
        if not self.data: return
        name = self.entry_name.get().strip()
        if not name: return
        garage = self.combo_garage.get().strip() or "未分類"
        vtype = "" 
        
        app_set = self.data.get("app_settings", {})
        disable_limits = app_set.get("disable_all_limits", False)
        def_g = app_set.get("default_garage_limit", 10)
        def_s = app_set.get("default_special_limit", 2)
        
        current_time = time.strftime('%Y-%m-%d %H:%M')
        
        # ✨ 帕格薩斯強制屬性
        upgraded = ""
        count = 1
        if garage == "帕格薩斯":
            vtype = "帕格薩斯"
            upgraded = "不可改裝"
            count = 1
        
        existing_idx = next((i for i, v in enumerate(self.data["vehicles"]) if v["name"].lower() == name.lower()), None)
        if existing_idx is not None:
            existing_car = self.data["vehicles"][existing_idx]
            existing_garage = existing_car.get("garage", "未分類")
            msg = f"系統偵測到資產中已存在名為【{name}】的載具！\n(目前存放於：{existing_garage})\n\n• 按「是 (Yes)」：將該現有車輛的數量 +1 (合併)\n• 按「否 (No)」：強制新增為另一筆獨立紀錄\n• 按「取消 (Cancel)」：放棄本次新增"
            choice = messagebox.askyesnocancel("發現重複車輛", msg)
            if choice is None:
                return
            elif choice is True:
                if existing_car.get("garage") == "帕格薩斯" or existing_car.get("v_type") == "帕格薩斯":
                    messagebox.showinfo("系統提示", "帕格薩斯載具數量固定為 1，無法疊加數量！")
                    return
                try: current_c = int(existing_car.get("count", 1))
                except: current_c = 1
                existing_car["count"] = current_c + 1
                existing_car["updated_at"] = current_time 
                
                self.sync_special_from_vehicles(); save_data(self.all_data)
                self.log_action(f"✅ 合併載具數量：將現有的【{name}】數量 +1 (總數: {current_c + 1})")
                self.entry_search.delete(0, tk.END); self.combo_garage_filter.set("全部")
                self.refresh_vehicle_tables(); self.refresh_special_table(); self.refresh_garage_table()
                self.entry_name.delete(0, tk.END); self.combo_acquire.set("") 
                self.show_toast_progress("🚗 數量合併成功！")
                self.set_status(f"✅ 【{name}】已存在，系統已自動將其數量 +1！", "#4CAF50") 
                idx_str = str(existing_idx)
                target_tree = self.tree_non_personal if existing_car.get("v_type") in ["非個人載具", "帕格薩斯"] else self.tree_vehicles
                if target_tree.exists(idx_str):
                    target_tree.selection_set(idx_str); target_tree.focus(idx_str); target_tree.see(idx_str)            
                self.entry_name.focus()
                return

        if garage != "未分類" and garage != "帕格薩斯":
            if not self.validate_tab1_vehicle_to_garage(name, garage): return
            spec_carriers = [sv["name"] for sv in self.data.get("special_vehicles", [])]
            limit = self.data["garage_limits"].get(garage, def_s if garage in spec_carriers else def_g)
            
            if not disable_limits and self.count_cars_in_garage(garage) >= limit: 
                return messagebox.showerror("位置已滿", f"【{garage}】容量已滿！")

        self.data["vehicles"].append({
            "name": name, "garage": garage, "v_type": vtype, "acquire": self.combo_acquire.get(), 
            "upgraded": upgraded, "count": count, "notes": "", "locked": False, "pinned": False,
            "created_at": current_time, "updated_at": current_time
        })
        self.sync_special_from_vehicles(); save_data(self.all_data)
        
        self.log_action(f"✅ 新增載具：【{name}】 (儲存至：{garage})")
        
        self.entry_search.delete(0, tk.END); self.combo_garage_filter.set("全部")
        
        self.refresh_vehicle_tables(); self.refresh_special_table(); self.refresh_garage_table()
        self.entry_name.delete(0, tk.END)
        self.combo_acquire.set("") 
        
        self.show_toast_progress("🚗 登記成功！")
        self.set_status(f"✅ 新增成功：【{name}】已入庫。游標已自動回到【載具名稱】，可直接繼續打字！", "#4CAF50") 
        
        new_iid = str(len(self.data["vehicles"]) - 1)
        target_tree = self.tree_non_personal if vtype in ["非個人載具", "帕格薩斯"] else self.tree_vehicles
        if target_tree.exists(new_iid):
            target_tree.selection_set(new_iid); target_tree.focus(new_iid); target_tree.see(new_iid)            
        self.entry_name.focus()

    def delete_vehicle(self, event=None):
        if not self.data: return
        target_tree = self.get_active_tree(event)
        selected = target_tree.selection()
        if not selected: return
        for item in selected:
            if self.data["vehicles"][int(item)].get("locked", False): return messagebox.showwarning("安全鎖定", "⚠️ 包含鎖定車輛，拒絕刪除！")
        if messagebox.askyesno("確認刪除", f"確定要刪除選定的 【 {len(selected)} 】 筆資料嗎？"):
            names_deleted = [self.data["vehicles"][int(s)]["name"] for s in selected]
            
            for item in sorted([int(s) for s in selected], reverse=True): del self.data["vehicles"][item]
            
            self.checked_indices.clear()
            self.update_checked_button_text()
            
            self.sync_special_from_vehicles(); save_data(self.all_data); self.apply_filters()
            self.refresh_special_table(); self.refresh_garage_table()
            
            self.log_action(f"🗑️ 刪除載具：共移除了 {len(selected)} 筆載具資料 ({', '.join(names_deleted)[:50]}{'...' if len(', '.join(names_deleted)) > 50 else ''})")
            self.set_status(f"🗑️ 成功刪除 {len(selected)} 筆載具資料。", "#FF9800")

    def toggle_pin_vehicle(self, event=None):
        if not self.data: return
        target_tree = self.get_active_tree(event)
        selected = target_tree.selection()
        if not selected: return
        new_state = not self.data["vehicles"][int(selected[0])].get("pinned", False)
        for item in selected: self.data["vehicles"][int(item)]["pinned"] = new_state
        save_data(self.all_data); self.apply_filters(); self.show_toast_progress("📌 置頂狀態已更新")
        self.log_action(f"📌 更新置頂狀態：變更了 {len(selected)} 筆資料的置頂屬性")
        for item in selected:
            if target_tree.exists(item): target_tree.selection_add(item)
        if selected and target_tree.exists(selected[0]): target_tree.see(selected[0])

    def toggle_lock_vehicle(self, event=None):
        if not self.data: return
        target_tree = self.get_active_tree(event)
        selected = target_tree.selection()
        if not selected: return
        new_state = not self.data["vehicles"][int(selected[0])].get("locked", False)
        for item in selected: self.data["vehicles"][int(item)]["locked"] = new_state
        save_data(self.all_data); self.apply_filters(); self.show_toast_progress("🔒 鎖定狀態已更新")
        self.log_action(f"🔒 更新鎖定狀態：變更了 {len(selected)} 筆資料的保護鎖")
        for item in selected:
            if target_tree.exists(item): target_tree.selection_add(item)
        if selected and target_tree.exists(selected[0]): target_tree.see(selected[0])

    def apply_filters(self):
        if not self.data: return
        kw = self.entry_search.get().lower(); selected_garage = self.combo_garage_filter.get()
        filtered = [(i, c) for i, c in enumerate(self.data["vehicles"]) if (kw in c["name"].lower() or kw in c["garage"].lower()) and (selected_garage in ["全部", ""] or c["garage"] == selected_garage)]
        self.refresh_vehicle_tables(search_results=filtered)

    def reset_filters(self):
        if not self.data: return
        self.entry_search.delete(0, tk.END)
        self.combo_garage_filter.set("全部")
        self.checked_indices.clear()
        self.update_checked_button_text()
        self.refresh_vehicle_tables()
        self.set_status("🔄 條件與勾選狀態已重置。", "#555555")

    def show_vehicle_context_menu(self, event):
        if not self.data: return
        target_tree = self.get_active_tree(event)
        item = target_tree.identify_row(event.y)
        if item: 
            if item not in target_tree.selection(): target_tree.selection_set(item)
            sel_count = len(target_tree.selection())
            self.vehicle_popup_menu.delete(0, tk.END)
            self.vehicle_popup_menu.add_command(label=f"✏️ 編輯資產 ({sel_count} 筆)", command=lambda: self.open_edit_window(event))
            self.vehicle_popup_menu.add_separator()
            self.vehicle_popup_menu.add_command(label="📌 置頂/取消置頂", command=lambda: self.toggle_pin_vehicle(event))
            self.vehicle_popup_menu.add_command(label="🔒 檔案鎖定/解鎖", command=lambda: self.toggle_lock_vehicle(event))
            self.vehicle_popup_menu.add_separator()
            self.vehicle_popup_menu.add_command(label=f"🗑️ 刪除資產 ({sel_count} 筆)", command=lambda: self.delete_vehicle(event))
            self.vehicle_popup_menu.post(event.x_root, event.y_root)

    def open_batch_import_window(self):
        if not self.data: return
        win = tk.Toplevel(self.root); win.title("📦 批量登入")
        self.center_toplevel_window(win, 540, 520); win.bind("<Escape>", lambda e: win.destroy())
        tk.Label(win, text="請在此貼上車輛資料（一行一筆）", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#2196F3").pack(pady=8)
        text_area = tk.Text(win, height=13, width=52, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); text_area.pack(pady=10, padx=15)
        
        def process_import():
            content = text_area.get("1.0", tk.END).strip()
            added = 0; merged = 0
            spec_carriers = [sv["name"] for sv in self.data.get("special_vehicles", []) if sv.get("can_store", False)]
            current_time = time.strftime('%Y-%m-%d %H:%M')
            
            for line in content.split('\n'):
                if not line.strip(): continue
                parts = line.split(',')
                name = parts[0].strip(); garage = parts[1].strip() if len(parts) > 1 else "未分類"
                if garage in SUB_CARRIER_RULES and not self.validate_tab1_vehicle_to_garage(name, garage, show_error=False): garage = "未分類"
                
                # ✨ 帕格薩斯強制規則
                if garage == "帕格薩斯":
                    v_type = "帕格薩斯"
                    upgraded = "不可改裝"
                    count = 1
                else:
                    v_type = ""
                    upgraded = ""
                    count = 1
                
                idx_existing = next((i for i, c in enumerate(self.data["vehicles"]) if c['name'] == name), None)
                if idx_existing is not None:
                    choice = messagebox.askyesno("發現重複車輛", f"準備登入的車輛【{name}】已經存在！\n\n• 選擇「是 (Yes)」：覆蓋/合併該車輛數量 (+1)\n• 選擇「否 (No)」：新增一筆獨立紀錄，並在備註加上「已重複」", parent=win)
                    if choice:
                        if garage != "帕格薩斯":
                            self.data["vehicles"][idx_existing]["count"] = int(self.data["vehicles"][idx_existing].get("count") or 1) + 1
                        self.data["vehicles"][idx_existing]["updated_at"] = current_time
                        merged += 1
                    else: 
                        if garage not in self.data["garages"] and garage not in spec_carriers: garage = "未分類"
                        self.data["vehicles"].append({"name": name, "garage": garage, "v_type": v_type, "acquire": "", "upgraded": upgraded, "count": count, "notes": "已重複", "locked": False, "pinned": False, "created_at": current_time, "updated_at": current_time})
                        added += 1
                else:
                    if garage not in self.data["garages"] and garage not in spec_carriers: garage = "未分類"
                    self.data["vehicles"].append({"name": name, "garage": garage, "v_type": v_type, "acquire": "", "upgraded": upgraded, "count": count, "notes": "", "locked": False, "pinned": False, "created_at": current_time, "updated_at": current_time})
                    added += 1
                    
            self.sync_special_from_vehicles(); save_data(self.all_data)
            if added > 0 or merged > 0: self.log_action(f"📦 批量登入執行完畢：全新增 {added} 筆，合併覆蓋 {merged} 筆")
            self.refresh_vehicle_tables(); self.refresh_special_table(); win.destroy(); self.refresh_garage_table()
            self.show_toast_progress(f"📦 批量登入完成 (新增 {added} 筆, 覆蓋 {merged} 筆)")
            self.set_status(f"📦 批量操作完成，共登入了 {added} 筆資料，合併覆蓋了 {merged} 筆數量。", "#2196F3")
            if added > 0 or merged > 0:
                new_iid = str(len(self.data["vehicles"]) - 1)
                if self.tree_vehicles.exists(new_iid): self.tree_vehicles.selection_set(new_iid); self.tree_vehicles.focus(new_iid); self.tree_vehicles.see(new_iid)
                    
        tk.Button(win, text="確認執行批量登入", command=process_import, bg="#2196F3", fg="white", font=FONT_BOLD, relief="flat").pack(fill="x", padx=40, pady=15, ipady=4)

    def open_edit_window(self, event=None, pre_selected=None):
        if not self.data: return
        
        if pre_selected is not None:
            selected = pre_selected
        else:
            target_tree = self.get_active_tree(event)
            selected = target_tree.selection()
            if not selected: 
                if event is None: 
                    messagebox.showwarning("操作提示", "請先在列表中選取您要修改的載具！\n(也可透過最左側的方塊來跨區勾選多台載具)")
                return
            
        for item in selected:
            if self.data["vehicles"][int(item)].get("locked", False): return messagebox.showwarning("鎖定限制", "⚠️ 資料已鎖定，請解鎖後再編輯！")
        
        spec_carriers = [sv["name"] for sv in self.data.get("special_vehicles", []) if sv.get("can_store", False)]
        combined_locations = [g for g in self.data["garages"] if g != "未分類" and g != "帕格薩斯"]
        combined_locations = ["未分類", "帕格薩斯"] + combined_locations + spec_carriers
        
        app_set = self.data.get("app_settings", {})
        disable_limits = app_set.get("disable_all_limits", False)
        def_g = app_set.get("default_garage_limit", 10)
        def_s = app_set.get("default_special_limit", 2)
        
        acq_opts = self.data.get("acquire_options", ACQUIRE_OPTIONS)
        
        if len(selected) == 1:
            idx = int(selected[0]); car = self.data["vehicles"][idx]
            old_name_ref = car['name']
            win = tk.Toplevel(self.root); win.title("編輯載具資產")
            self.center_toplevel_window(win, 350, 520) 
            
            tk.Label(win, text="載具資產名稱:", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(12,2))
            ent_name = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=22); ent_name.insert(0, car['name']); ent_name.pack(); ent_name.focus()
            
            combo_edit_garage = ttk.Combobox(win, state="readonly", values=combined_locations, font=FONT_NORMAL)
            combo_edit_vtype = ttk.Combobox(win, state="readonly", values=V_TYPE_OPTIONS, font=FONT_NORMAL)
            combo_edit_acquire = ttk.Combobox(win, state="readonly", values=acq_opts, font=FONT_NORMAL)
            combo_edit_upgrade = ttk.Combobox(win, state="readonly", values=["未改滿", "已改滿", "不可改裝"], font=FONT_NORMAL)
            ent_count = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=22)
            ent_notes = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=22)
            
            apply_focus_highlight(ent_name); apply_focus_highlight(ent_count); apply_focus_highlight(ent_notes)

            tk.Label(win, text="存放位置 (車庫/特殊載具):", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(6,2)); combo_edit_garage.set(car.get('garage', '未分類')); combo_edit_garage.pack()
            tk.Label(win, text="載具類型:", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(6,2)); combo_edit_vtype.set(car.get('v_type', '')); combo_edit_vtype.pack()
            tk.Label(win, text="取得方式:", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(6,2)); combo_edit_acquire.set(car.get('acquire', '')); combo_edit_acquire.pack()
            tk.Label(win, text="改裝狀態:", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(6,2)); combo_edit_upgrade.set(car.get('upgraded', '')); combo_edit_upgrade.pack()
            tk.Label(win, text="資產數量:", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(6,2)); ent_count.insert(0, str(car.get('count', 1))); ent_count.pack()
            tk.Label(win, text="自訂備註:", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(6,2)); ent_notes.insert(0, car.get('notes', '')); ent_notes.pack()
            
            # ✨ 動態鎖定/解鎖機制
            def on_edit_combobox_change(e=None):
                if combo_edit_garage.get() == "帕格薩斯" or combo_edit_vtype.get() == "帕格薩斯":
                    if combo_edit_garage.get() != "帕格薩斯": combo_edit_garage.set("帕格薩斯")
                    if combo_edit_vtype.get() != "帕格薩斯": combo_edit_vtype.set("帕格薩斯")
                    combo_edit_upgrade.config(state="normal")
                    combo_edit_upgrade.set("不可改裝")
                    combo_edit_upgrade.config(state="disabled")
                    ent_count.config(state="normal")
                    ent_count.delete(0, tk.END)
                    ent_count.insert(0, "1")
                    ent_count.config(state="disabled")
                else:
                    combo_edit_upgrade.config(state="readonly")
                    ent_count.config(state="normal")

            combo_edit_garage.bind("<<ComboboxSelected>>", on_edit_combobox_change)
            combo_edit_vtype.bind("<<ComboboxSelected>>", on_edit_combobox_change)
            on_edit_combobox_change() # 初始化狀態

            def save_single(e=None):
                new_car_name = ent_name.get(); new_g = combo_edit_garage.get()
                if new_g != car['garage'] and new_g != "未分類" and new_g != "帕格薩斯":
                    if not self.validate_tab1_vehicle_to_garage(new_car_name, new_g): return
                    lim = self.data["garage_limits"].get(new_g, def_s if new_g in spec_carriers else def_g)
                    if not disable_limits and self.count_cars_in_garage(new_g) >= lim: 
                        return messagebox.showerror("容量已滿", f"【{new_g}】空間不足！上限為 {lim} 台。")
                
                car.update({'name': new_car_name, 'garage': new_g, 'v_type': combo_edit_vtype.get(), 'acquire': combo_edit_acquire.get(), 'upgraded': combo_edit_upgrade.get(), 'notes': ent_notes.get()})
                car['updated_at'] = time.strftime('%Y-%m-%d %H:%M')
                try: car['count'] = int(ent_count.get())
                except: car['count'] = 1 
                
                self.sync_special_from_vehicles(); save_data(self.all_data)
                self.log_action(f"✏️ 編輯載具屬性：修改了【{old_name_ref}】(可能已更名為 {new_car_name}) 的紀錄。")
                
                if pre_selected is not None:
                    self.checked_indices.clear(); self.update_checked_button_text()

                self.refresh_vehicle_tables(); self.refresh_garage_table(); self.refresh_special_table(); win.destroy(); self.show_toast_progress("✅ 資產修改成功！")
                self.set_status(f"✏️ 資料庫已更新：【{new_car_name}】屬性修改成功。", "#4CAF50")
                
                idx_str = str(idx)
                final_tree = self.tree_non_personal if car['v_type'] in ["非個人載具", "帕格薩斯"] else self.tree_vehicles
                if final_tree.exists(idx_str):
                    final_tree.selection_set(idx_str); final_tree.focus(idx_str); final_tree.see(idx_str)

            def delete_action():
                if messagebox.askyesno("確認刪除", f"確定要刪除選定的 【 1 】 筆資料嗎？", parent=win):
                    del self.data["vehicles"][idx]
                    self.checked_indices.discard(idx)
                    self.update_checked_button_text()
                    self.sync_special_from_vehicles()
                    save_data(self.all_data)
                    self.log_action(f"🗑️ 刪除載具：移除了 {old_name_ref}")
                    self.refresh_vehicle_tables(); self.refresh_garage_table(); self.refresh_special_table()
                    self.set_status(f"🗑️ 成功刪除 1 筆載具資料。", "#FF9800")
                    win.destroy()
            
            btn_frame = tk.Frame(win, bg=COLOR_MAIN_BG)
            btn_frame.pack(fill="x", padx=35, pady=15)
            tk.Button(btn_frame, text="儲存變更", command=save_single, bg="#4CAF50", fg="white", font=FONT_BOLD, relief="flat").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=4)
            tk.Button(btn_frame, text="🗑️ 刪除", command=delete_action, bg="#e74c3c", fg="white", font=FONT_BOLD, relief="flat").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4)
            
            ent_name.bind("<Return>", lambda e: combo_edit_garage.focus()); combo_edit_garage.bind("<Return>", lambda e: combo_edit_vtype.focus())
            combo_edit_vtype.bind("<Return>", lambda e: combo_edit_acquire.focus()); combo_edit_acquire.bind("<Return>", lambda e: combo_edit_upgrade.focus())
            combo_edit_upgrade.bind("<Return>", lambda e: ent_count.focus()); ent_count.bind("<Return>", lambda e: ent_notes.focus()); ent_notes.bind("<Return>", save_single)

        else:
            win = tk.Toplevel(self.root); win.title("批量修改與檢視已勾選資產")
            self.center_toplevel_window(win, 380, 620) 
            
            tk.Label(win, text=f"👁️ 您目前共勾選了 {len(selected)} 筆載具：", fg="#e91e63", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG).pack(pady=(10, 5))
            
            frame_preview = tk.Frame(win, bg=COLOR_MAIN_BG)
            frame_preview.pack(fill="x", padx=30, pady=5)
            
            scrollbar_prev = ttk.Scrollbar(frame_preview)
            scrollbar_prev.pack(side="right", fill="y")
            
            listbox_prev = tk.Listbox(frame_preview, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", selectbackground="#4CAF50", yscrollcommand=scrollbar_prev.set, height=5, relief="solid")
            for item in selected:
                car = self.data["vehicles"][int(item)]
                listbox_prev.insert(tk.END, f"▪ {car['name']}  ({car['garage']})")
            listbox_prev.pack(side="left", fill="both", expand=True)
            scrollbar_prev.config(command=listbox_prev.yview)
            
            ttk.Separator(win, orient="horizontal").pack(fill="x", pady=10, padx=20)
            
            tk.Label(win, text="1. 批量移動存放位置:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack()
            combo_batch_garage = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]"] + combined_locations); combo_batch_garage.set("[不修改]"); combo_batch_garage.pack(pady=3)
            tk.Label(win, text="2. 批量更改載具類型:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack()
            combo_batch_vtype = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]"] + V_TYPE_OPTIONS); combo_batch_vtype.set("[不修改]"); combo_batch_vtype.pack(pady=3)
            tk.Label(win, text="3. 批量更改取得方式:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack()
            combo_batch_acq = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]"] + acq_opts); combo_batch_acq.set("[不修改]"); combo_batch_acq.pack(pady=3)
            tk.Label(win, text="4. 批量更改改裝狀態:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack()
            combo_batch_upg = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]", "未改滿", "已改滿", "不可改裝"]); combo_batch_upg.set("[不修改]"); combo_batch_upg.pack(pady=3)
            var_update_notes = tk.BooleanVar(win, value=False)
            tk.Checkbutton(win, text="5. 覆蓋自訂備註", variable=var_update_notes, bg=COLOR_MAIN_BG, fg="white", selectcolor="#757575", font=FONT_BOLD).pack(pady=3)
            ent_batch_notes = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=22); ent_batch_notes.pack()
            apply_focus_highlight(ent_batch_notes)
            
            def save_batch(e=None):
                new_g = combo_batch_garage.get(); up_g = (new_g != "[不修改]")
                current_time = time.strftime('%Y-%m-%d %H:%M')
                for item in selected:
                    idx = int(item); car_name = self.data["vehicles"][idx]['name']
                    if up_g and new_g in SUB_CARRIER_RULES and not self.validate_tab1_vehicle_to_garage(car_name, new_g): return
                    if up_g: self.data["vehicles"][idx]['garage'] = new_g
                    if combo_batch_vtype.get() != "[不修改]": self.data["vehicles"][idx]['v_type'] = combo_batch_vtype.get()
                    if combo_batch_acq.get() != "[不修改]": self.data["vehicles"][idx]['acquire'] = combo_batch_acq.get()
                    if combo_batch_upg.get() != "[不修改]": self.data["vehicles"][idx]['upgraded'] = combo_batch_upg.get()
                    if var_update_notes.get(): self.data["vehicles"][idx]['notes'] = ent_batch_notes.get()
                    
                    # ✨ 批量處理時若觸發帕格薩斯，強制套用屬性
                    if self.data["vehicles"][idx]['garage'] == "帕格薩斯" or self.data["vehicles"][idx]['v_type'] == "帕格薩斯":
                        self.data["vehicles"][idx]['garage'] = "帕格薩斯"
                        self.data["vehicles"][idx]['v_type'] = "帕格薩斯"
                        self.data["vehicles"][idx]['upgraded'] = "不可改裝"
                        self.data["vehicles"][idx]['count'] = 1
                        
                    self.data["vehicles"][idx]['updated_at'] = current_time
                
                self.sync_special_from_vehicles(); save_data(self.all_data)
                self.log_action(f"✏️ 執行批量屬性編輯：一次性修改了 {len(selected)} 筆載具屬性。")
                
                if pre_selected is not None:
                    self.checked_indices.clear(); self.update_checked_button_text()

                self.refresh_vehicle_tables(); self.refresh_garage_table(); self.refresh_special_table(); win.destroy(); self.show_toast_progress("✅ 批量更新完畢")
                self.set_status(f"✏️ 批量操作執行完畢：已變更 {len(selected)} 筆載具屬性。", "#2196F3")
                
                for item in selected:
                    final_t = self.tree_non_personal if self.data["vehicles"][int(item)].get("v_type") in ["非個人載具", "帕格薩斯"] else self.tree_vehicles
                    if final_t.exists(item): final_t.selection_add(item)
                    if item == selected[0]: final_t.see(item)

            def delete_action():
                if messagebox.askyesno("確認刪除", f"確定要刪除您所勾選的 【 {len(selected)} 】 筆資料嗎？", parent=win):
                    names_deleted = [self.data["vehicles"][int(s)]["name"] for s in selected]
                    for item in sorted([int(s) for s in selected], reverse=True): 
                        del self.data["vehicles"][item]
                    self.checked_indices.clear()
                    self.update_checked_button_text()
                    self.sync_special_from_vehicles()
                    save_data(self.all_data)
                    self.log_action(f"🗑️ 刪除載具：共移除了 {len(selected)} 筆載具資料 ({', '.join(names_deleted)[:50]}{'...' if len(', '.join(names_deleted)) > 50 else ''})")
                    self.refresh_vehicle_tables(); self.refresh_garage_table(); self.refresh_special_table()
                    self.set_status(f"🗑️ 成功刪除 {len(selected)} 筆載具資料。", "#FF9800")
                    win.destroy()
            
            btn_frame = tk.Frame(win, bg=COLOR_MAIN_BG)
            btn_frame.pack(fill="x", padx=35, pady=15)
            tk.Button(btn_frame, text="執行批量變更", command=save_batch, bg="#2196F3", fg="white", font=FONT_BOLD, relief="flat").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=4)
            tk.Button(btn_frame, text="🗑️ 批量刪除", command=delete_action, bg="#e74c3c", fg="white", font=FONT_BOLD, relief="flat").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4)
            ent_batch_notes.bind("<Return>", save_batch)

    # ==========================================
    #     🚁 2. 特殊載具分頁
    # ==========================================
    def setup_special_tab(self):
        input_frame = tk.LabelFrame(self.tab_special, text=" 🚁 登記大型特種特殊載具 (可自由指定車庫功能與停放位置) ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#e91e63", padx=12, pady=12, bd=2)
        input_frame.pack(fill="x", padx=15, pady=10)
        
        input_frame.columnconfigure(1, weight=1)
        input_frame.columnconfigure(3, weight=1)

        tk.Label(input_frame, text="載具名稱:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=0, column=0, pady=5, padx=5, sticky="e")
        self.combo_spec_name = ttk.Combobox(input_frame, state="normal", font=FONT_NORMAL, values=list(SUB_CARRIER_RULES.keys()) + ["機動作戰中心", "復仇者"])
        self.combo_spec_name.grid(row=0, column=1, pady=5, padx=5, sticky="we")
        self.combo_spec_name.bind("<KeyRelease>", self.on_main_spec_carrier_changed)
        self.combo_spec_name.bind("<<ComboboxSelected>>", self.on_main_spec_carrier_changed)
        
        tk.Label(input_frame, text="停放位置:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=2, pady=5, padx=5, sticky="e")
        self.combo_spec_location = ttk.Combobox(input_frame, state="readonly", font=FONT_NORMAL)
        self.combo_spec_location.grid(row=0, column=3, pady=5, padx=5, sticky="we")

        tk.Button(input_frame, text="➕ 建立特殊載具", command=self.add_special, bg="#e91e63", fg="white", font=FONT_BOLD, relief="flat", padx=10).grid(row=0, column=4, rowspan=2, padx=15, pady=5, sticky="ns")

        self.var_can_store = tk.BooleanVar(value=False)
        self.chk_can_store = tk.Checkbutton(input_frame, text="啟用車庫(可放車)", variable=self.var_can_store, bg=COLOR_CARD_BG, fg="white", selectcolor="#757575", font=FONT_BOLD, activebackground=COLOR_CARD_BG, activeforeground="white")
        self.chk_can_store.grid(row=1, column=0, columnspan=2, pady=5, padx=5, sticky="w")
        
        tk.Label(input_frame, text="內部專屬車輛:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=1, column=2, pady=5, padx=5, sticky="e")
        self.combo_inner_car = ttk.Combobox(input_frame, state="disabled", font=FONT_NORMAL, values=[""])
        self.combo_inner_car.grid(row=1, column=3, pady=5, padx=5, sticky="we")
        
        self.combo_spec_name.bind("<Return>", lambda e: self.combo_spec_location.focus())
        self.combo_spec_location.bind("<Return>", lambda e: self.combo_inner_car.focus() if str(self.combo_inner_car.cget("state")) != "disabled" else self.add_special())
        self.combo_inner_car.bind("<Return>", lambda e: self.add_special())

        tree_frame = tk.Frame(self.tab_special, bg=COLOR_MAIN_BG); tree_frame.pack(fill="both", expand=True, padx=15, pady=10)
        self.tree_special = ttk.Treeview(tree_frame, columns=("name", "location", "inner"), show="headings", selectmode="extended")
        
        columns_config_sp = {"name": "特殊載具名稱", "location": "停放物業/位置", "inner": "內部停放/綁定車輛"}
        for col, text in columns_config_sp.items(): self.tree_special.heading(col, text=text, command=lambda c=col: self.sort_treeview(self.tree_special, c, False))
        self.tree_special.column("name", width=200, stretch=True); self.tree_special.column("location", width=200, stretch=True); self.tree_special.column("inner", width=300, stretch=True)
        self.tree_special.pack(side="left", fill="both", expand=True)
        
        self.tree_special.bind("<Double-1>", self.open_special_edit_window); self.tree_special.bind("<Return>", self.open_special_edit_window)
        self.tree_special.bind("<Delete>", self.delete_special)
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_special.yview)
        self.tree_special.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y")
        self.special_popup_menu = tk.Menu(self.root, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        self.tree_special.bind("<Button-3>", self.show_special_context_menu)

    def on_main_spec_carrier_changed(self, event=None):
        carrier = self.combo_spec_name.get().strip()
        if carrier in SUB_CARRIER_RULES:
            self.var_can_store.set(True); self.chk_can_store.config(state="disabled"); self.combo_inner_car.config(state="readonly")
            self.combo_inner_car["values"] = [""] + SUB_CARRIER_RULES[carrier] 
            if self.combo_inner_car.get() not in self.combo_inner_car["values"]: self.combo_inner_car.set("") 
        else:
            self.chk_can_store.config(state="normal"); self.combo_inner_car.set(""); self.combo_inner_car.config(state="disabled") 

    def add_special(self):
        if not self.data: return
        name = self.combo_spec_name.get().strip()
        location = self.combo_spec_location.get().strip() or "未分類" 
        inner_car = self.combo_inner_car.get().strip()
        can_store = self.var_can_store.get()
        if inner_car == "無": inner_car = ""
        if not name: return
        if any(sv['name'].lower() == name.lower() for sv in self.data.get("special_vehicles", [])): return messagebox.showwarning("重複", "⚠️ 此特殊載具已在資產清單中！")

        if can_store:
            def_s = self.data.get("app_settings", {}).get("default_special_limit", 2)
            limit = simpledialog.askinteger("設定上限", f"請輸入特殊載具「{name}」的可停放車輛數量上限\n(預設 {def_s} 台，無限制請輸入大數字):", initialvalue=def_s, minvalue=1)
            if not limit: return
            self.data["garage_limits"][name] = limit

        self.data["special_vehicles"].append({"name": name, "location": location, "inner_vehicle": inner_car, "can_store": can_store, "locked": False, "pinned": False}) 
        self.sync_vehicles_from_special(); save_data(self.all_data)
        
        self.log_action(f"🚁 建立特殊載具：登記了新設備【{name}】 (停放於 {location})") 
        
        self.refresh_special_table(); self.update_garage_comboboxes(); self.refresh_vehicle_tables() 
        self.combo_spec_name.set(""); self.combo_inner_car.set(""); self.var_can_store.set(False); self.on_main_spec_carrier_changed() 
        self.combo_spec_location.set("未分類") 
        self.show_toast_progress("🚁 特殊載具資產建立成功！")
        self.set_status(f"✅ 成功編編制特種載具：【{name}】", "#e91e63")
        
        new_iid = str(len(self.data["special_vehicles"]) - 1)
        if self.tree_special.exists(new_iid): self.tree_special.selection_set(new_iid); self.tree_special.focus(new_iid); self.tree_special.see(new_iid)
        self.combo_spec_name.focus()

    def refresh_special_table(self):
        for i in self.tree_special.get_children(): self.tree_special.delete(i)
        if not self.data: return
        pinned_items = []; normal_items = []
        for idx, item in enumerate(self.data.get("special_vehicles", [])):
            if item.get("pinned", False): pinned_items.append((idx, item))
            else: normal_items.append((idx, item))
        for idx, item in pinned_items + normal_items:
            display_name = item["name"]
            if item.get("locked", False): display_name = "🔒 " + display_name
            if item.get("pinned", False): display_name = "📌 " + display_name
            self.tree_special.insert("", "end", iid=str(idx), values=(display_name, item.get("location", "未分類"), item.get("inner_vehicle", "") or "")) 

    def toggle_pin_special(self):
        if not self.data: return
        selected = self.tree_special.selection()
        if not selected: return
        new_state = not self.data["special_vehicles"][int(selected[0])].get("pinned", False)
        for item in selected: self.data["special_vehicles"][int(item)]["pinned"] = new_state
        save_data(self.all_data); self.refresh_special_table()
        self.log_action(f"📌 更新置頂狀態：變更了特種載具的置頂屬性")
        for item in selected:
            if self.tree_special.exists(item): self.tree_special.selection_add(item)
        if selected and self.tree_special.exists(selected[0]): self.tree_special.see(selected[0])
        
    def toggle_lock_special(self):
        if not self.data: return
        selected = self.tree_special.selection()
        if not selected: return
        new_state = not self.data["special_vehicles"][int(selected[0])].get("locked", False)
        for item in selected: self.data["special_vehicles"][int(item)]["locked"] = new_state
        save_data(self.all_data); self.refresh_special_table()
        self.log_action(f"🔒 更新鎖定狀態：變更了特種載具的保護鎖")
        for item in selected:
            if self.tree_special.exists(item): self.tree_special.selection_add(item)
        if selected and self.tree_special.exists(selected[0]): self.tree_special.see(selected[0])

    def show_special_context_menu(self, event):
        if not self.data: return
        item = self.tree_special.identify_row(event.y)
        if item:
            if item not in self.tree_special.selection(): self.tree_special.selection_set(item)
            self.special_popup_menu.delete(0, tk.END); self.special_popup_menu.add_command(label="✏️ 編輯特種載具", command=self.open_special_edit_window)
            self.special_popup_menu.add_separator(); self.special_popup_menu.add_command(label="📌 置頂/取消置頂", command=self.toggle_pin_special)
            self.special_popup_menu.add_command(label="🔒 屬性鎖定/解鎖", command=self.toggle_lock_special)
            self.special_popup_menu.add_separator(); self.special_popup_menu.add_command(label="🗑️ 報廢刪除特種載具", command=self.delete_special)
            self.special_popup_menu.post(event.x_root, event.y_root)

    def delete_special(self, event=None):
        if not self.data: return
        selected = self.tree_special.selection()
        if not selected: return
        for item in selected:
            if self.data["special_vehicles"][int(item)].get("locked", False): return messagebox.showwarning("安全警告", "⚠️ 無法刪除鎖定載具！")
        if messagebox.askyesno("確認刪除", "確定報廢此特殊載具資產？\n(內部車輛關聯位置將重置為未分類)"):
            names_deleted = []
            for item in sorted([int(s) for s in selected], reverse=True): 
                old_name = self.data["special_vehicles"][item]["name"]; del self.data["special_vehicles"][item]
                if old_name in self.data["garage_limits"]: del self.data["garage_limits"][old_name] 
                names_deleted.append(old_name)
                for v in self.data["vehicles"]:
                    if v.get("garage") == old_name: v["garage"] = "未分類"
                    
            save_data(self.all_data); self.refresh_special_table(); self.update_garage_comboboxes(); self.apply_filters()
            self.log_action(f"🗑️ 報廢特殊載具：移除了 {old_name_del}")
            self.set_status(f"🗑️ 成功拆解/變賣特殊載具。", "#FF9800")
            win.destroy()

    def open_special_edit_window(self, event=None):
        if not self.data: return
        selected = self.tree_special.selection()
        if not selected or len(selected) > 1: return 
        idx = int(selected[0])
        if self.data["special_vehicles"][idx].get("locked", False): return messagebox.showwarning("權限限制", "⚠️ 特殊載具鎖定中！")
            
        old_name = self.data["special_vehicles"][idx]["name"]
        old_location = self.data["special_vehicles"][idx].get("location", "未分類") 
        old_inner = self.data["special_vehicles"][idx].get("inner_vehicle", "") 
        old_can_store = self.data["special_vehicles"][idx].get("can_store", False)
        
        def_s = self.data.get("app_settings", {}).get("default_special_limit", 2)
        old_limit = self.data["garage_limits"].get(old_name, def_s)
        
        win = tk.Toplevel(self.root); win.title("修改特種載具屬性")
        self.center_toplevel_window(win, 350, 420) 
        
        tk.Label(win, text="特種載具資產名稱:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(12,2))
        combo_name = ttk.Combobox(win, state="normal", font=FONT_NORMAL, values=list(SUB_CARRIER_RULES.keys()) + ["機動作戰中心", "復仇者"])
        if old_name not in combo_name["values"]: combo_name["values"] = list(combo_name["values"]) + [old_name]
        combo_name.set(old_name); combo_name.pack()
        
        actual_garages = [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]
        tk.Label(win, text="停放位置 (存放此設備的車庫):", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(5,2))
        combo_spec_loc = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["未分類"] + actual_garages)
        combo_spec_loc.set(old_location)
        combo_spec_loc.pack()

        edit_var_can_store = tk.BooleanVar(value=old_can_store)
        chk_edit_store = tk.Checkbutton(win, text="設為車庫(車輛管理可直接存入)", variable=edit_var_can_store, bg=COLOR_MAIN_BG, fg="white", selectcolor="#757575", font=FONT_BOLD); chk_edit_store.pack(pady=4)
        
        tk.Label(win, text="特殊載具車位上限:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(5,2))
        ent_limit = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=12)
        ent_limit.insert(0, str(old_limit))
        ent_limit.pack()
        apply_focus_highlight(ent_limit)
        
        tk.Label(win, text="內部限制綁定車輛:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(5,2))
        combo_inner = ttk.Combobox(win, state="disabled", font=FONT_NORMAL); combo_inner.pack()
        
        def update_edit_inner(event=None):
            c = combo_name.get().strip()
            if c in SUB_CARRIER_RULES:
                edit_var_can_store.set(True); chk_edit_store.config(state="disabled"); combo_inner.config(state="readonly"); combo_inner["values"] = [""] + SUB_CARRIER_RULES[c] 
                if combo_inner.get() not in combo_inner["values"]: combo_inner.set("") 
            else:
                chk_edit_store.config(state="normal"); combo_inner["values"] = [""]; combo_inner.set(""); combo_inner.config(state="disabled") 
                
        combo_name.bind("<KeyRelease>", update_edit_inner); combo_name.bind("<<ComboboxSelected>>", update_edit_inner)
        if old_name in SUB_CARRIER_RULES: combo_inner.config(state="readonly"); combo_inner["values"] = [""] + SUB_CARRIER_RULES[old_name]; chk_edit_store.config(state="disabled") 
        combo_inner.set(old_inner)
        
        def save(e=None):
            new_name = combo_name.get().strip()
            new_loc = combo_spec_loc.get().strip() or "未分類" 
            new_inner = combo_inner.get().strip()
            new_store = edit_var_can_store.get()
            if new_inner == "無": new_inner = ""
            if not new_name: return
            
            try: new_limit = int(ent_limit.get().strip() or def_s)
            except: new_limit = def_s
            
            if new_name != old_name:
                for v in self.data["vehicles"]:
                    if v.get("garage") == old_name: v["garage"] = new_name
                if old_name in self.data["garage_limits"]: del self.data["garage_limits"][old_name]
                
            self.data["special_vehicles"][idx].update({"name": new_name, "location": new_loc, "inner_vehicle": new_inner, "can_store": new_store}) 
            if new_store: self.data["garage_limits"][new_name] = new_limit
            
            self.sync_vehicles_from_special(); save_data(self.all_data)
            self.log_action(f"✏️ 修改特種載具屬性：編輯了【{old_name}】的紀錄 (停放: {new_loc} | 上限: {new_limit})。") 
            
            self.refresh_vehicle_tables(); self.update_garage_comboboxes(); self.refresh_special_table(); win.destroy(); self.show_toast_progress("✅ 特種資產修正完畢")
            self.set_status("✏️ 資料庫已更新：特種載具屬性修改成功。", "#e91e63")
            
            idx_str = str(idx)
            if self.tree_special.exists(idx_str): self.tree_special.see(idx_str); self.tree_special.selection_set(idx_str); self.tree_special.focus(idx_str)

        def delete_special_action():
            if messagebox.askyesno("確認刪除", "確定報廢此特殊載具資產？\n(內部車輛關聯位置將重置為未分類)", parent=win):
                old_name_del = self.data["special_vehicles"][idx]["name"]
                del self.data["special_vehicles"][idx]
                if old_name_del in self.data["garage_limits"]: del self.data["garage_limits"][old_name_del]
                for v in self.data["vehicles"]:
                    if v.get("garage") == old_name_del: v["garage"] = "未分類"
                save_data(self.all_data)
                self.refresh_special_table(); self.update_garage_comboboxes(); self.apply_filters()
                self.log_action(f"🗑️ 報廢特殊載具：移除了 {old_name_del}")
                self.set_status(f"🗑️ 成功拆解/變賣特殊載具。", "#FF9800")
                win.destroy()
        
        btn_frame = tk.Frame(win, bg=COLOR_MAIN_BG)
        btn_frame.pack(fill="x", padx=35, pady=15)
        tk.Button(btn_frame, text="保存變更", command=save, bg="#4CAF50", fg="white", font=FONT_BOLD, relief="flat").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=4)
        tk.Button(btn_frame, text="🗑️ 報廢刪除", command=delete_special_action, bg="#e74c3c", fg="white", font=FONT_BOLD, relief="flat").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4)
        
        combo_name.bind("<Return>", lambda e: combo_spec_loc.focus())
        combo_spec_loc.bind("<Return>", lambda e: ent_limit.focus())
        ent_limit.bind("<Return>", lambda e: combo_inner.focus() if str(combo_inner.cget("state")) != "disabled" else save(e))
        combo_inner.bind("<Return>", save)

    # ==========================================
    #     🏠 3. 車庫管理頁面
    # ==========================================
    def setup_garages_tab(self):
        left_frame = tk.Frame(self.tab_garages, bg=COLOR_MAIN_BG); left_frame.pack(side="left", fill="y", padx=15, pady=10)
        
        tk.Label(left_frame, text="🏠 新增全新房產車庫", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#4CAF50").pack(pady=10)
        
        tk.Label(left_frame, text="新車庫/物業名稱:", font=FONT_BOLD, bg=COLOR_MAIN_BG, fg="white").pack(anchor="w", pady=2)
        self.entry_new_garage = tk.Entry(left_frame, width=22, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); self.entry_new_garage.pack(pady=5)
        apply_focus_highlight(self.entry_new_garage)
        
        tk.Label(left_frame, text="房產分類 (可自訂或選擇):", font=FONT_BOLD, bg=COLOR_MAIN_BG, fg="white").pack(anchor="w", pady=(10, 2))
        self.combo_new_garage_cat = ttk.Combobox(left_frame, width=20, font=FONT_NORMAL, values=["一般車庫", "高階公寓", "豪宅", "商辦企業", "地下設施", "豪華賭場"])
        self.combo_new_garage_cat.set("一般車庫")
        self.combo_new_garage_cat.pack(pady=5)
        
        self.entry_new_garage.bind("<Return>", lambda e: self.combo_new_garage_cat.focus())
        self.combo_new_garage_cat.bind("<Return>", lambda e: self.add_garage_simple())
        
        self.btn_add_garage = tk.Button(left_frame, text="➕ 登記置產新車庫", command=self.add_garage_simple, bg="#4CAF50", fg="white", font=FONT_BOLD, relief="flat"); self.btn_add_garage.pack(fill="x", pady=15)
        
        ttk.Separator(left_frame, orient="horizontal").pack(fill="x", pady=15)
        
        tk.Label(left_frame, text="↕️ 進階管理", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#F39C12").pack(pady=(5, 10))
        self.btn_reorder_garage = tk.Button(left_frame, text="↕️ 自訂車庫順序", command=self.open_reorder_window, bg="#F39C12", fg="white", font=FONT_BOLD, relief="flat")
        self.btn_reorder_garage.pack(fill="x", pady=5)
        
        self.right_frame = tk.Frame(self.tab_garages, bg=COLOR_MAIN_BG); self.right_frame.pack(side="right", fill="both", expand=True, padx=15, pady=10)
        self.right_frame.bind("<Enter>", lambda e: self.canvas_garage.bind_all("<MouseWheel>", lambda ev: self.canvas_garage.yview_scroll(int(-1 * (ev.delta / 120)), "units") if hasattr(self, 'canvas_garage') and self.canvas_garage.winfo_exists() else None))
        self.right_frame.bind("<Leave>", lambda e: self.canvas_garage.unbind_all("<MouseWheel>"))
        
        tk.Label(self.right_frame, text="📊 各置產車庫容量即時安全監控儀表板", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="white").pack(pady=8)
        
        self.canvas_garage = tk.Canvas(self.right_frame, borderwidth=0, bg=COLOR_MAIN_BG, highlightthickness=0)
        self.scrollbar_garage = ttk.Scrollbar(self.right_frame, orient="vertical", command=self.canvas_garage.yview)
        self.scrollable_frame = tk.Frame(self.canvas_garage, bg=COLOR_MAIN_BG)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas_garage.configure(scrollregion=self.canvas_garage.bbox("all")))
        self.canvas_garage.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas_garage.configure(yscrollcommand=self.scrollbar_garage.set); self.canvas_garage.pack(side="left", fill="both", expand=True); self.scrollbar_garage.pack(side="right", fill="y")

    def _bind_garage_mousewheel(self):
        self.canvas_garage.bind_all("<MouseWheel>", self._on_garage_scroll)

    def _unbind_garage_mousewheel(self):
        self.canvas_garage.unbind_all("<MouseWheel>")

    def _on_garage_scroll(self, event):
        if hasattr(self, 'canvas_garage') and self.canvas_garage.winfo_exists():
            if event.delta: self.canvas_garage.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def open_reorder_window(self):
        if not self.data: return
        actual_garages = [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]
        if not actual_garages:
            messagebox.showinfo("提示", "目前沒有自訂車庫可以排序！")
            return

        win = tk.Toplevel(self.root)
        win.title("自訂車庫顯示順序")
        self.center_toplevel_window(win, 320, 400)
        win.configure(bg=COLOR_CARD_BG)
        
        tk.Label(win, text="請選擇車庫並使用上下按鈕調整順序", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="white").pack(pady=10)
        
        frame_list = tk.Frame(win, bg=COLOR_CARD_BG)
        frame_list.pack(fill="both", expand=True, padx=20, pady=5)
        
        scrollbar = ttk.Scrollbar(frame_list)
        scrollbar.pack(side="right", fill="y")
        
        listbox = tk.Listbox(frame_list, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", selectbackground="#4CAF50", yscrollcommand=scrollbar.set, relief="solid")
        for g in actual_garages:
            listbox.insert(tk.END, g)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)
        
        def move_up():
            idx = listbox.curselection()
            if not idx: return
            idx = idx[0]
            if idx > 0:
                val = listbox.get(idx)
                listbox.delete(idx)
                listbox.insert(idx - 1, val)
                listbox.selection_set(idx - 1)
                listbox.see(idx - 1)
                
        def move_down():
            idx = listbox.curselection()
            if not idx: return
            idx = idx[0]
            if idx < listbox.size() - 1:
                val = listbox.get(idx)
                listbox.delete(idx)
                listbox.insert(idx + 1, val)
                listbox.selection_set(idx + 1)
                listbox.see(idx + 1)
        
        btn_frame = tk.Frame(win, bg=COLOR_CARD_BG)
        btn_frame.pack(fill="x", padx=20, pady=10)
        tk.Button(btn_frame, text="⬆️ 上移", command=move_up, bg="#3498db", fg="white", font=FONT_BOLD, relief="flat").pack(side="left", expand=True, fill="x", padx=(0,5), ipady=4)
        tk.Button(btn_frame, text="⬇️ 下移", command=move_down, bg="#3498db", fg="white", font=FONT_BOLD, relief="flat").pack(side="right", expand=True, fill="x", padx=(5,0), ipady=4)
        
        def save_order():
            new_order = list(listbox.get(0, tk.END))
            has_unclassified = "未分類" in self.data["garages"]
            has_pegasus = "帕格薩斯" in self.data["garages"]
            final_garages = []
            if has_unclassified: final_garages.append("未分類")
            if has_pegasus: final_garages.append("帕格薩斯")
            final_garages.extend(new_order)
            
            self.data["garages"] = final_garages
            save_data(self.all_data)
            
            self.log_action("🔄 自訂車庫順序：重新排列了車庫清單")
            self.refresh_garage_table()
            self.update_garage_comboboxes()
            win.destroy()
            self.show_toast_progress("✅ 車庫排序已更新！")
            self.set_status("🔄 房地產中心：已成功套用自訂車庫排序。", "#3498db")
            
        tk.Button(win, text="💾 儲存並套用排序", command=save_order, bg="#4CAF50", fg="white", font=FONT_BOLD, relief="flat").pack(fill="x", padx=20, pady=(0, 20), ipady=4)

    def add_garage_simple(self):
        if not self.data: return
        name = self.entry_new_garage.get().strip()
        cat = self.combo_new_garage_cat.get().strip() or "一般車庫" 
        if not name: return
        if name in self.data["garages"]: return messagebox.showerror("錯誤", "物業名稱重複！")
        
        def_g = self.data.get("app_settings", {}).get("default_garage_limit", 10)
        limit = simpledialog.askinteger("設定上限", f"請輸入「{name}」的可停車位容量上限\n(預設 {def_g} 車位，無限制請輸入大數字):", initialvalue=def_g, minvalue=1)
        if not limit: return 
        
        self.data["garages"].append(name); self.data["garage_limits"][name] = limit
        self.data["garage_categories"][name] = cat 
        
        save_data(self.all_data)
        self.log_action(f"🏠 購入新車庫房產：【{name}】 (分類：{cat} | 上限：{limit})")
        
        self.refresh_garage_table(); self.update_garage_comboboxes(); self.entry_new_garage.delete(0, tk.END); self.show_toast_progress(f"🏠 成功購入新車庫：{name}"); self.entry_new_garage.focus()
        self.set_status(f"🏠 房地產中心：成功登記物業【{name}】。", "#4CAF50")

    def refresh_garage_table(self):
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        if not self.data: return
        # ✨ 隱藏不給編輯的虛擬車庫
        actual_garages = [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]
        
        if hasattr(self, 'btn_add_garage'):
            self.btn_add_garage.config(state="normal", text=f"➕ 購入新物業車庫 ({len(actual_garages)})")
            
        grouped_garages = {}
        for g in actual_garages:
            cat = self.data.get("garage_categories", {}).get(g, "未分類房產")
            if cat not in grouped_garages: grouped_garages[cat] = []
            grouped_garages[cat].append(g)
            
        disable_limits = self.data.get("app_settings", {}).get("disable_all_limits", False)
            
        for cat, g_list in grouped_garages.items():
            tk.Label(self.scrollable_frame, text=f"🏷️ 【 {cat} 】", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#F39C12").pack(anchor="w", pady=(15, 5), padx=5)
            
            for g in g_list:
                limit = self.data["garage_limits"].get(g, 10); usage = self.count_cars_in_garage(g)
                limit_display = "∞" if disable_limits else limit
                
                row = tk.Frame(self.scrollable_frame, pady=6, bg=COLOR_MAIN_BG); row.pack(fill="x", expand=True, pady=3, padx=15) 
                tk.Label(row, text=f"▪️ {g}  ({usage} / {limit_display} 輛)", width=30, anchor="w", font=FONT_BOLD, bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE).pack(side="left")
                
                pb = ttk.Progressbar(row, length=220, mode="determinate")
                pb["maximum"] = limit if not disable_limits else max(limit, usage, 1)
                pb["value"] = usage
                pb.pack(side="left", padx=15)
                
                if not disable_limits and usage >= limit: 
                    tk.Label(row, text="⚠️ 爆滿危險", fg="#ff1744", font=FONT_BOLD, bg=COLOR_MAIN_BG).pack(side="left")
                    
                btn_f = tk.Frame(row, bg=COLOR_MAIN_BG); btn_f.pack(side="right", padx=10)
                tk.Button(btn_f, text="修改物業", command=lambda name=g: self.open_garage_edit_window_by_name(name), bg="#3498db", fg="white", font=FONT_NORMAL, relief="flat", padx=5).pack(side="left", padx=3)
                tk.Button(btn_f, text="拆除物業", command=lambda name=g: self.delete_garage_by_name(name), bg="#e74c3c", fg="white", font=FONT_NORMAL, relief="flat", padx=5).pack(side="left", padx=3)

    def delete_garage_by_name(self, g_name):
        if messagebox.askyesno("安全確認", f"您確定要拆除變賣車庫「{g_name}」嗎？\n(車庫內的車輛將自動撤回「未分類」車庫)"):
            if g_name in self.data["garages"]: self.data["garages"].remove(g_name)
            if g_name in self.data["garage_limits"]: del self.data["garage_limits"][g_name]
            if g_name in self.data.get("garage_categories", {}): del self.data["garage_categories"][g_name] 
            
            for v in self.data["vehicles"]:
                if v.get("garage") == g_name: v["garage"] = "未分類"
            
            for sv in self.data.get("special_vehicles", []):
                if sv.get("location") == g_name:
                    sv["location"] = "未分類"
            
            save_data(self.all_data)
            self.log_action(f"🏠 變賣/拆除車庫：已移除物業【{g_name}】")
            
            self.refresh_garage_table(); self.apply_filters(); self.update_garage_comboboxes()
            self.refresh_special_table() 
            self.set_status(f"🏠 房地產中心：已成功出售變賣物業【{g_name}】。", "#FF9800")

    def open_garage_edit_window_by_name(self, old_name):
        old_limit = self.data["garage_limits"].get(old_name, 10)
        old_cat = self.data.get("garage_categories", {}).get(old_name, "一般車庫") 
        win = tk.Toplevel(self.root); win.title("編輯車庫房產屬性")
        self.center_toplevel_window(win, 340, 360) 
        
        tk.Label(win, text="修改車庫物業名稱:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(15,2))
        ent_name = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=24); ent_name.insert(0, old_name); ent_name.pack(); ent_name.focus()
        
        tk.Label(win, text="所屬房產分類:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(10,2))
        combo_cat = ttk.Combobox(win, font=FONT_NORMAL, width=22, values=["一般車庫", "高階公寓", "豪宅", "商辦企業", "地下設施", "豪華賭場"]); combo_cat.set(old_cat); combo_cat.pack()
        
        tk.Label(win, text="修改車位總量上限:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(10,2))
        ent_limit = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=12); ent_limit.insert(0, str(old_limit)); ent_limit.pack()
        
        apply_focus_highlight(ent_name) 
        apply_focus_highlight(ent_limit)

        def save(e=None):
            new_name = ent_name.get().strip()
            new_cat = combo_cat.get().strip() or "一般車庫" 
            try: new_limit = int(ent_limit.get().strip() or 10)
            except: new_limit = 10
            
            disable_limits = self.data.get("app_settings", {}).get("disable_all_limits", False)
            
            if new_name != old_name and new_name in self.data["garages"]: return messagebox.showerror("錯誤", "物業名稱已存在！")
            
            if not disable_limits and new_limit < self.count_cars_in_garage(old_name): 
                return messagebox.showerror("錯誤", "車位不可小於目前停放車數！")
            
            idx = self.data["garages"].index(old_name)
            self.data["garages"][idx] = new_name; self.data["garage_limits"][new_name] = new_limit
            self.data["garage_categories"][new_name] = new_cat 
            if new_name != old_name:
                del self.data["garage_limits"][old_name]
                if old_name in self.data.get("garage_categories", {}): del self.data["garage_categories"][old_name] 
                
                for v in self.data["vehicles"]:
                    if v.get("garage") == old_name: v["garage"] = new_name
                    
                for sv in self.data.get("special_vehicles", []):
                    if sv.get("location") == old_name: sv["location"] = new_name
            
            save_data(self.all_data)
            self.log_action(f"✏️ 編輯車庫屬性：修改了【{old_name}】(更名為 {new_name} | 分類: {new_cat} | 上限: {new_limit})")
            
            self.refresh_garage_table(); self.refresh_vehicle_tables(); self.update_garage_comboboxes()
            self.refresh_special_table() 
            win.destroy()
            self.set_status(f"✏️ 房地產中心：已更新物業【{new_name}】的屬性。", "#3498db")

        def delete_garage_action():
            if messagebox.askyesno("安全確認", f"您確定要拆除變賣車庫「{old_name}」嗎？\n(車庫內的車輛將自動撤回「未分類」車庫)", parent=win):
                if old_name in self.data["garages"]: self.data["garages"].remove(old_name)
                if old_name in self.data["garage_limits"]: del self.data["garage_limits"][old_name]
                if old_name in self.data.get("garage_categories", {}): del self.data["garage_categories"][old_name] 
                for v in self.data["vehicles"]:
                    if v.get("garage") == old_name: v["garage"] = "未分類"
                    
                for sv in self.data.get("special_vehicles", []):
                    if sv.get("location") == old_name: sv["location"] = "未分類"
                    
                save_data(self.all_data)
                self.log_action(f"🏠 變賣/拆除車庫：已移除物業【{old_name}】")
                self.refresh_garage_table(); self.apply_filters(); self.update_garage_comboboxes()
                self.refresh_special_table() 
                self.set_status(f"🏠 房地產中心：已成功出售變賣物業【{old_name}】。", "#FF9800")
                win.destroy()
            
        btn_frame = tk.Frame(win, bg=COLOR_MAIN_BG)
        btn_frame.pack(fill="x", padx=35, pady=15)
        tk.Button(btn_frame, text="保存修改", command=save, bg="#4CAF50", fg="white", font=FONT_BOLD, relief="flat").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=4)
        tk.Button(btn_frame, text="🗑️ 拆除物業", command=delete_garage_action, bg="#e74c3c", fg="white", font=FONT_BOLD, relief="flat").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4)
        ent_name.bind("<Return>", lambda e: combo_cat.focus()); combo_cat.bind("<Return>", lambda e: ent_limit.focus()); ent_limit.bind("<Return>", save)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = GTAGarageApp(root)
        root.mainloop()
    except Exception as e:
        import traceback
        err_root = tk.Tk()
        err_root.withdraw()
        messagebox.showerror("系統崩潰報告", f"程式啟動失敗，錯誤代碼：\n\n{traceback.format_exc()}")
        err_root.destroy()
