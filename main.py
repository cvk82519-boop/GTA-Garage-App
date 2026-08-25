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
import csv
import random
import glob
from tkinter import messagebox, ttk, filedialog, simpledialog
from collections import defaultdict

# 嘗試載入全域鍵盤監聽模組
try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

# === 軟體版本與更新設定 ===
APP_VERSION = "1.1.20" 
DATA_FILE = "gta5_garage_data.json"

ACQUIRE_OPTIONS = ["購買獲得", "任務獲得", "生涯成就", "賭場轉盤", "搶劫獲得", "車友會", "其他備註"]
V_TYPE_OPTIONS = ["個人載具", "非個人載具", "帕格薩斯"]

SUB_CARRIER_RULES = {
    "驚駭位元": ["暴君MKII", "暴君 Mk II", "Oppressor Mk II"],
    "科薩卡": ["鬥牛勇士", "斯特龍伯格", "Toreador", "Stromberg"]
}

COLOR_MAIN_BG = "#212121"       
COLOR_CARD_BG = "#2d2d2d"       
COLOR_TEXT_WHITE = "#ffffff"    
COLOR_TEXT_GRAY = "#cccccc"     
COLOR_FOCUS_BG = "#1565C0"      

FONT_NORMAL = ("Microsoft JhengHei", 12)           
FONT_BOLD = ("Microsoft JhengHei", 13, "bold")     
FONT_LARGE_BOLD = ("Microsoft JhengHei", 14, "bold") 

def apply_focus_highlight(widget):
    if isinstance(widget, tk.Entry):
        widget.bind("<FocusIn>", lambda e: widget.config(bg=COLOR_FOCUS_BG), add="+")
        widget.bind("<FocusOut>", lambda e: widget.config(bg=COLOR_CARD_BG), add="+")

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget; self.text = text; self.tipwindow = None; self.id = None
        self.widget.bind("<Enter>", self.enter); self.widget.bind("<Leave>", self.leave); self.widget.bind("<Destroy>", self.leave) 
    def enter(self, event=None): self.schedule()
    def leave(self, event=None): self.unschedule(); self.hidetip()
    def schedule(self):
        self.unschedule()
        if self.widget.winfo_exists(): self.id = self.widget.after(400, self.showtip)
    def unschedule(self):
        if self.id: self.widget.after_cancel(self.id); self.id = None
    def showtip(self, event=None):
        if not self.widget.winfo_exists() or not self.text: return
        x = self.widget.winfo_rootx() + 20; y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget); tw.wm_overrideredirect(True); tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify=tk.LEFT, background="#111111", foreground="white", relief=tk.SOLID, borderwidth=0, font=FONT_NORMAL, padx=8, pady=4).pack(ipadx=1)
    def hidetip(self):
        if self.tipwindow and self.tipwindow.winfo_exists(): self.tipwindow.destroy()
        self.tipwindow = None

def add_tooltip(widget, text): ToolTip(widget, text)

def load_data():
    default_structure = {"profiles": {}}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "vehicles" in data and "profiles" not in data: return {"profiles": {"已移轉帳號": data}}
                    if "profiles" in data: return data
                return default_structure
        except: return default_structure
    return default_structure

def save_data(all_data):
    for p_name, p_data in all_data.get("profiles", {}).items():
        if "garages" not in p_data: p_data["garages"] = ["未分類", "帕格薩斯", "日蝕大樓", "日蝕大樓 - 車庫1"]
        else:
            if "帕格薩斯" not in p_data["garages"]:
                if "未分類" in p_data["garages"]: p_data["garages"].insert(p_data["garages"].index("未分類") + 1, "帕格薩斯")
                else: p_data["garages"].insert(0, "帕格薩斯")
                
        if "special_vehicles" in p_data: p_data["special_vehicles"] = [sv for sv in p_data["special_vehicles"] if sv["name"] != "帕格薩斯"]
            
        if "garage_limits" not in p_data:
            p_data["garage_limits"] = {"未分類": 999, "帕格薩斯": 999}
            for g in p_data["garages"]:
                if g not in ["未分類", "帕格薩斯"]: p_data["garage_limits"][g] = 10
        else: p_data["garage_limits"]["帕格薩斯"] = 999
            
        if "wishlist" not in p_data: p_data["wishlist"] = []
        if "action_logs" not in p_data: p_data["action_logs"] = []
        if "app_settings" not in p_data: p_data["app_settings"] = {}
            
        defaults = {
            "tab_bulletin": True, "tab_vehicles": True, "tab_non_personal": True,
            "tab_special": True, "tab_garages": True, "tab_statistics": True, "tab_logs": True, "tab_wishlist": True, 
            "tool_stopwatch": True, "disable_all_limits": False, "auto_backup": True, 
            "default_garage_limit": 10, "default_special_limit": 2, "default_countdown_sec": 300.0,
            "hotkey_pause": "pause", "hotkey_start": "w",
            "visible_columns": ["check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"] 
        }
        for k, v in defaults.items():
            if k not in p_data["app_settings"]: p_data["app_settings"][k] = v

        if "acquire_options" not in p_data: p_data["acquire_options"] = ACQUIRE_OPTIONS.copy()

        for sv in p_data.get("special_vehicles", []):
            if "location" not in sv: sv["location"] = "未分類"
            if "inner_vehicle" not in sv: sv["inner_vehicle"] = ""
            if "can_store" not in sv: sv["can_store"] = True if sv["name"] in SUB_CARRIER_RULES else False

    with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(all_data, f, ensure_ascii=False, indent=4)

class GTAGarageApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"GTAV資產管理系統 {APP_VERSION} (智慧連動改名版)")
        self.root.configure(bg=COLOR_MAIN_BG)
        self.root.resizable(True, True)
        self.root.minsize(1200, 700)
        
        self.all_data = load_data()
        app_config = self.all_data.setdefault("app_config", {})
        
        if app_config.get("geometry"): self.root.geometry(app_config.get("geometry"))
        else:
            w = 1350; h = 780; sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
            self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
            
        if app_config.get("state", "zoomed") == "zoomed": self.root.state('zoomed')
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
        self.style.map('TCombobox', fieldbackground=[('focus', COLOR_FOCUS_BG), ('readonly', COLOR_CARD_BG)], foreground=[('focus', 'white'), ('readonly', COLOR_TEXT_WHITE)])
        self.style.configure("TButton", font=FONT_BOLD, padding=6, relief="flat")
        
        btn_colors = {"Success": ("#4CAF50", "#45a049"), "Danger": ("#e74c3c", "#d32f2f"), "Primary": ("#3498db", "#1976D2"), "Warning": ("#F39C12", "#F57C00"), "Purple": ("#9b59b6", "#8e44ad"), "Pink": ("#e91e63", "#c2185b"), "Secondary": ("#555555", "#424242"), "Dark": ("#333333", "#111111")}
        for name, (bg, active_bg) in btn_colors.items():
            self.style.configure(f"{name}.TButton", background=bg, foreground="white", bordercolor=bg, lightcolor=bg, darkcolor=bg)
            self.style.map(f"{name}.TButton", background=[("active", active_bg), ("pressed", active_bg)], foreground=[("active", "white")])
        
        save_data(self.all_data) 
        self.current_id = ""; self.data = None; self.checked_indices = set()
        self.sw_mode = "STOPWATCH"; self.sw_state = "IDLE"; self.cd_target_sec = 300.0; self.is_running = False; self.elapsed_time = 0.0; self.stopwatch_window = None
        self.current_garage_car_indices = []
        
        self.root.after(50, self.master_stopwatch_loop)
        
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=5)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        self.tab_bulletin = tk.Frame(self.notebook, bg=COLOR_MAIN_BG)
        self.tab_account = tk.Frame(self.notebook, bg=COLOR_MAIN_BG)
        self.tab_vehicles = tk.Frame(self.notebook, bg=COLOR_MAIN_BG)
        self.tab_non_personal = tk.Frame(self.notebook, bg=COLOR_MAIN_BG)
        self.tab_special = tk.Frame(self.notebook, bg=COLOR_MAIN_BG)
        self.tab_garages = tk.Frame(self.notebook, bg=COLOR_MAIN_BG)
        self.tab_wishlist = tk.Frame(self.notebook, bg=COLOR_MAIN_BG)
        self.tab_statistics = tk.Frame(self.notebook, bg=COLOR_MAIN_BG)
        self.tab_logs = tk.Frame(self.notebook, bg=COLOR_MAIN_BG)

        self.tab_widgets = {"📢 系統公告": self.tab_bulletin, "👥 帳號管理": self.tab_account, "🚗 車輛管理": self.tab_vehicles, "🚜 非個人與帕格薩斯": self.tab_non_personal, "🚁 特殊載具": self.tab_special, "🏠 車庫管理": self.tab_garages, "🛒 購車願望清單": self.tab_wishlist, "📊 統計資料": self.tab_statistics, "📜 操作日誌": self.tab_logs}
        self.tab_order = app_config.get("tab_order", list(self.tab_widgets.keys()))
        for t_name in self.tab_order:
            if t_name in self.tab_widgets: self.notebook.add(self.tab_widgets[t_name], text=f" {t_name} ")
        
        self.setup_menu_bar(); self.setup_profile_bar(); self.setup_status_bar()
        self.setup_bulletin_tab(); self.setup_account_tab(); self.setup_vehicles_tab(); self.setup_non_personal_tab(); self.setup_special_tab(); self.setup_garages_tab(); self.setup_wishlist_tab(); self.setup_statistics_tab(); self.setup_logs_tab()

        self.apply_settings()
        self.check_login_status()

    def on_app_closing(self):
        self.all_data.setdefault("app_config", {})["state"] = self.root.state()
        if self.root.state() == "normal": self.all_data["app_config"]["geometry"] = self.root.geometry()
        with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(self.all_data, f, ensure_ascii=False, indent=4)
        if self.data and self.data.get("app_settings", {}).get("auto_backup", True):
            try:
                if not os.path.exists("backups"): os.makedirs("backups")
                shutil.copy(DATA_FILE, os.path.join("backups", f"gta_auto_backup_{self.current_id}_{time.strftime('%Y%m%d_%H%M%S')}.json"))
                files = sorted(glob.glob(os.path.join("backups", f"gta_auto_backup_{self.current_id}_*.json")))
                while len(files) > 5: os.remove(files[0]); files.pop(0)
            except: pass
        self.root.destroy(); sys.exit(0)

    def setup_menu_bar(self):
        self.menubar = tk.Menu(self.root)
        file_menu = tk.Menu(self.menubar, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        file_menu.add_command(label="💾 手動備份資料 (Backup)", command=self.backup_data); file_menu.add_command(label="📂 載入備份還原 (Restore)", command=self.restore_data); file_menu.add_command(label="📥 匯出資料為 CSV (Export)", command=self.export_csv); file_menu.add_separator(); file_menu.add_command(label="🚪 結束系統 (Exit)", command=self.on_app_closing)
        self.menubar.add_cascade(label="檔案 (F)", menu=file_menu)

        self.edit_menu = tk.Menu(self.menubar, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        self.edit_menu.add_command(label="🔍 檢查重複車輛", command=self.check_duplicate_vehicles); self.edit_menu.add_command(label="✏️ 修改已勾選 (0)", command=self.edit_checked_vehicles); self.edit_menu.add_separator(); self.edit_menu.add_command(label="🎲 今天開哪台？", command=self.random_ride)
        self.menubar.add_cascade(label="編輯 (E)", menu=self.edit_menu)

        self.tools_menu = tk.Menu(self.menubar, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        self.tools_menu.add_command(label="⏱️ 呼叫任務碼錶", command=self.toggle_stopwatch_window); self.tools_menu.add_command(label="📦 批量登入", command=self.open_batch_import_window); self.tools_menu.add_separator(); self.tools_menu.add_command(label="⚙️ 系統全域設定", command=self.open_settings_window)
        self.menubar.add_cascade(label="系統工具 (T)", menu=self.tools_menu)
        self.root.config(menu=self.menubar)

    def open_column_selector(self):
        if not self.data: return messagebox.showwarning("操作提示", "請先登入角色 ID！")
        win = tk.Toplevel(self.root); win.title("👁️ 顯示/隱藏自訂欄位"); self.center_toplevel_window(win, 300, 450); win.configure(bg=COLOR_CARD_BG)
        tk.Label(win, text="請勾選您想在表格中顯示的欄位：", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#3498db").pack(pady=(15, 10))
        all_cols = {"check": "☑ 選取方塊", "name": "車輛名稱", "garage": "存放位置", "vtype": "車輛類型", "acquire": "取得方式", "price": "購入價格估值", "upgrade": "改裝狀態", "count": "資產數量", "notes": "自訂備註"}
        current_visible = self.data.get("app_settings", {}).get("visible_columns", list(all_cols.keys()))
        frame_checks = tk.Frame(win, bg=COLOR_CARD_BG); frame_checks.pack(fill="both", expand=True, padx=40)
        vars_dict = {}
        for col_id, col_name in all_cols.items():
            var = tk.BooleanVar(value=(col_id in current_visible)); vars_dict[col_id] = var
            tk.Checkbutton(frame_checks, text=col_name, variable=var, bg=COLOR_CARD_BG, fg="white", selectcolor="#757575", font=FONT_BOLD, activebackground=COLOR_CARD_BG, activeforeground="white").pack(anchor="w", pady=4)
        def save_cols():
            new_visible = [c_id for c_id, v in vars_dict.items() if v.get()]
            if not new_visible: return messagebox.showwarning("警告", "請至少保留一個顯示欄位！", parent=win)
            self.data["app_settings"]["visible_columns"] = new_visible; save_data(self.all_data)
            if hasattr(self, 'tree_vehicles') and self.tree_vehicles.winfo_exists(): self.tree_vehicles["displaycolumns"] = new_visible
            if hasattr(self, 'tree_non_personal') and self.tree_non_personal.winfo_exists(): self.tree_non_personal["displaycolumns"] = new_visible
            self.show_toast_progress("✅ 欄位顯示設定已更新！"); win.destroy()
        ttk.Button(win, text="💾 儲存並即時套用", command=save_cols, style="Success.TButton").pack(fill="x", padx=40, pady=(10, 20), ipady=4)

    def master_stopwatch_loop(self):
        if getattr(self, 'is_running', False):
            now = time.time(); mode = getattr(self, 'sw_mode', 'STOPWATCH')
            if mode == "STOPWATCH": self.elapsed_time = now - self.start_time
            else: 
                passed = now - self.start_time; rem = getattr(self, 'cd_target_sec', 300.0) - passed
                if rem <= 0.0:
                    self.elapsed_time = 0.0; self.is_running = False; self.sw_state = "IDLE"; self.update_stopwatch_ui_state(); self.update_stopwatch_ui()
                    self.show_toast_progress("⏰ 倒數計時時間到！"); self.set_status("⏰ 倒數計時時間到！", "#e74c3c")
                    if hasattr(self, 'stopwatch_window') and self.stopwatch_window and self.stopwatch_window.winfo_exists():
                        self.stopwatch_window.deiconify(); self.stopwatch_window.attributes("-topmost", True)
                else: self.elapsed_time = rem
            self.update_stopwatch_ui()
        self.root.after(50, self.master_stopwatch_loop)

    def handle_pause_key(self, event=None):
        now = time.time()
        if now - getattr(self, 'last_pause_time', 0.0) < 0.4: self.last_pause_time = 0.0; self.root.after(0, self.action_reset)
        else: self.last_pause_time = now; self.root.after(0, self.action_pause_single)

    def handle_w_key(self, event=None):
        if getattr(self, 'sw_state', 'IDLE') == "READY": self.root.after(0, self.action_start)

    def action_pause_single(self):
        state = getattr(self, 'sw_state', 'IDLE'); mode = getattr(self, 'sw_mode', 'STOPWATCH')
        if state == "RUNNING": self.sw_state = "IDLE"; self.is_running = False
        elif state == "IDLE":
            if mode == "COUNTDOWN" and getattr(self, 'elapsed_time', 0.0) <= 0.0: self.elapsed_time = getattr(self, 'cd_target_sec', 300.0)
            self.sw_state = "READY"; self.is_running = False
        elif state == "READY": self.sw_state = "IDLE"; self.is_running = False
        self.update_stopwatch_ui_state()

    def action_start(self):
        self.sw_state = "RUNNING"; self.is_running = True; mode = getattr(self, 'sw_mode', 'STOPWATCH'); now = time.time()
        if mode == "STOPWATCH": self.start_time = now - getattr(self, 'elapsed_time', 0.0)
        else: 
            current_rem = getattr(self, 'elapsed_time', self.cd_target_sec)
            self.start_time = now - (self.cd_target_sec - (current_rem if current_rem > 0 else self.cd_target_sec))
        self.update_stopwatch_ui_state()

    def action_reset(self):
        self.sw_state = "IDLE"; self.is_running = False
        self.elapsed_time = 0.0 if getattr(self, 'sw_mode', 'STOPWATCH') == "STOPWATCH" else getattr(self, 'cd_target_sec', 300.0)
        self.update_stopwatch_ui_state(); self.update_stopwatch_ui()

    def set_countdown_target(self, seconds, close_window=False):
        self.cd_target_sec = float(seconds)
        if self.data:
            self.data.setdefault("app_settings", {})["default_countdown_sec"] = self.cd_target_sec; save_data(self.all_data)
        self.action_reset(); self.show_toast_progress(f"⏳ 已記憶倒數: {int(seconds//60)}分{int(seconds%60)}秒")
        if close_window and hasattr(self, 'stopwatch_window') and self.stopwatch_window and self.stopwatch_window.winfo_exists(): self.stopwatch_window.withdraw()

    def set_sw_mode(self, mode):
        self.sw_mode = mode
        if hasattr(self, 'btn_mode_sw') and hasattr(self, 'btn_mode_cd'):
            if mode == "STOPWATCH":
                self.btn_mode_sw.config(style="Primary.TButton"); self.btn_mode_cd.config(style="Dark.TButton")
                if hasattr(self, 'frame_cd_opts') and self.frame_cd_opts.winfo_exists(): self.frame_cd_opts.pack_forget()
            else:
                self.btn_mode_sw.config(style="Dark.TButton"); self.btn_mode_cd.config(style="Primary.TButton")
                if hasattr(self, 'frame_cd_opts') and self.frame_cd_opts.winfo_exists(): self.frame_cd_opts.pack(after=self.frame_mode_btn, pady=4)
        self.action_reset()

    def update_stopwatch_ui_state(self):
        if hasattr(self, 'btn_sw_action') and self.btn_sw_action.winfo_exists():
            state = getattr(self, 'sw_state', 'IDLE')
            if state == "READY": self.btn_sw_action.config(text="等待起跑按鍵", style="Warning.TButton") 
            elif state == "RUNNING": self.btn_sw_action.config(text="計時中 (Pause停)", style="Danger.TButton") 
            else: self.btn_sw_action.config(text="準備", style="Success.TButton") 

    def toggle_stopwatch_window(self):
        if not self.stopwatch_window or not self.stopwatch_window.winfo_exists():
            self.stopwatch_window = tk.Toplevel(self.root); self.stopwatch_window.title("⏱️ 碼錶"); self.stopwatch_window.geometry("400x320"); self.stopwatch_window.configure(bg=COLOR_CARD_BG); self.stopwatch_window.attributes("-topmost", True); self.stopwatch_window.resizable(False, False)
            self.stopwatch_window.protocol("WM_DELETE_WINDOW", lambda: self.stopwatch_window.withdraw())
            self.frame_mode_btn = tk.Frame(self.stopwatch_window, bg=COLOR_CARD_BG); self.frame_mode_btn.pack(pady=(8, 2))
            self.btn_mode_sw = ttk.Button(self.frame_mode_btn, text="⏱️ 正向計時", command=lambda: self.set_sw_mode("STOPWATCH"), style="Primary.TButton"); self.btn_mode_sw.pack(side="left", padx=4)
            self.btn_mode_cd = ttk.Button(self.frame_mode_btn, text="⏳ 倒數計時", command=lambda: self.set_sw_mode("COUNTDOWN"), style="Dark.TButton"); self.btn_mode_cd.pack(side="left", padx=4)
            self.frame_cd_opts = tk.Frame(self.stopwatch_window, bg=COLOR_CARD_BG)
            if self.sw_mode == "COUNTDOWN": self.frame_cd_opts.pack(pady=4)
            f_preset = tk.Frame(self.frame_cd_opts, bg=COLOR_CARD_BG); f_preset.pack()
            for label_t, sec_v in [("1分", 60), ("5分", 300), ("10分", 600), ("20分", 1200), ("48分", 2880)]: ttk.Button(f_preset, text=label_t, command=lambda s=sec_v: self.set_countdown_target(s), style="Secondary.TButton").pack(side="left", padx=2)
            f_custom = tk.Frame(self.frame_cd_opts, bg=COLOR_CARD_BG); f_custom.pack(pady=(4, 0))
            tk.Label(f_custom, text="自訂:", bg=COLOR_CARD_BG, fg="white", font=("Microsoft JhengHei", 9)).pack(side="left")
            ent_custom_m = tk.Entry(f_custom, width=3, font=("Microsoft JhengHei", 10), bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid"); ent_custom_m.insert(0, str(int(self.cd_target_sec // 60))); ent_custom_m.pack(side="left", padx=1)
            tk.Label(f_custom, text="分", bg=COLOR_CARD_BG, fg="white", font=("Microsoft JhengHei", 9)).pack(side="left")
            ent_custom_s = tk.Entry(f_custom, width=3, font=("Microsoft JhengHei", 10), bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid"); ent_custom_s.insert(0, str(int(self.cd_target_sec % 60))); ent_custom_s.pack(side="left", padx=1)
            tk.Label(f_custom, text="秒", bg=COLOR_CARD_BG, fg="white", font=("Microsoft JhengHei", 9)).pack(side="left", padx=(0,3))
            def apply_custom_cd(e=None):
                try: m = float(ent_custom_m.get().strip() or 0.0); s = float(ent_custom_s.get().strip() or 0.0); total = m * 60 + s
                except: total = 0
                if total > 0: self.set_countdown_target(total, close_window=True)
            ttk.Button(f_custom, text="儲存並隱藏", command=apply_custom_cd, style="Primary.TButton").pack(side="left", padx=2)
            self.lbl_sw = tk.Label(self.stopwatch_window, text="00:00.0", font=("Consolas", 30, "bold"), bg=COLOR_CARD_BG, fg="white"); self.lbl_sw.pack(pady=(4, 4))
            btn_f = tk.Frame(self.stopwatch_window, bg=COLOR_CARD_BG); btn_f.pack(pady=(0, 5))
            self.btn_sw_action = ttk.Button(btn_f, text="準備", command=self.action_pause_single, style="Success.TButton"); self.btn_sw_action.pack(side="left", padx=5)
            ttk.Button(btn_f, text="歸零", command=self.action_reset, style="Danger.TButton").pack(side="left", padx=5)
            self.update_stopwatch_ui_state(); self.update_stopwatch_ui()
        else:
            if self.stopwatch_window.state() == "normal": self.stopwatch_window.withdraw()
            else: self.stopwatch_window.deiconify()

    def update_stopwatch_ui(self):
        if self.stopwatch_window and self.stopwatch_window.winfo_exists() and hasattr(self, 'lbl_sw'):
            mins = int(self.elapsed_time // 60); secs = int(self.elapsed_time % 60); ms = int((self.elapsed_time * 10) % 10)
            self.lbl_sw.config(text=f"{mins:02d}:{secs:02d}.{ms}")

    def on_tab_changed(self, event=None):
        sel_id = self.notebook.select()
        if not sel_id: return
        current_tab = self.notebook.tab(sel_id, "text")
        if "統計資料" in current_tab: self.refresh_statistics()
        if hasattr(self, 'menubar'):
            try:
                if self.current_id and ("車輛" in current_tab or "非個人" in current_tab or "車庫" in current_tab): self.menubar.entryconfig("編輯 (E)", state="normal")
                else: self.menubar.entryconfig("編輯 (E)", state="disabled")
            except: pass

    def check_for_updates(self):
        messagebox.showinfo("檢查更新", f"太棒了！您目前使用的 V{APP_VERSION} 已經是最新的雲端版！")
        self.set_status("✅ 系統已是最新版本。", "#4CAF50")

    def safe_select_tab(self, tab_widget):
        if not getattr(self, 'current_id', None) and tab_widget not in [getattr(self, 'tab_bulletin', None), getattr(self, 'tab_account', None)]: return messagebox.showinfo("未登入權限", "請先登入您的角色 ID 以解鎖此功能分頁。")
        state = self.notebook.tab(tab_widget, "state")
        if state == "hidden": messagebox.showinfo("功能已隱藏", "此功能已被隱藏，請先至「系統設定」中開啟。")
        elif state == "disabled": messagebox.showinfo("未登入權限", "請先登入您的角色 ID 以解鎖此功能分頁。")
        else: self.notebook.select(tab_widget)

    def backup_data(self):
        if not os.path.exists(DATA_FILE): return messagebox.showinfo("備份", "目前沒有資料檔案可備份。")
        file_path = filedialog.asksaveasfilename(title="選擇備份儲存位置", initialfile="GTA_Garage_Manual_Backup.json", defaultextension=".json", filetypes=[("JSON 資料檔", "*.json"), ("所有檔案", "*.*")])
        if not file_path: return 
        try:
            shutil.copy(DATA_FILE, file_path); self.set_status(f"✅ 資料已成功安全備份", color="#4CAF50"); messagebox.showinfo("備份成功", f"資料已成功備份至：\n{file_path}")
        except Exception as e: messagebox.showerror("備份錯誤", f"備份失敗：\n{e}")

    def restore_data(self):
        if not messagebox.askyesno("⚠️ 還原資料警告", "還原備份將會【徹底覆蓋】目前的資料！確定還原嗎？"): return
        file_path = filedialog.askopenfilename(title="選擇要還原的 JSON 備份檔案", filetypes=[("JSON 資料檔", "*.json"), ("所有檔案", "*.*")])
        if not file_path: return 
        try:
            with open(file_path, "r", encoding="utf-8") as f: new_data = json.load(f)
            shutil.copy(file_path, DATA_FILE); self.all_data = load_data()
            if self.current_id and self.current_id not in self.all_data.get("profiles", {}): self.current_id = ""
            self.update_profile_combo(); self.check_login_status(); self.show_toast_progress("📂 備份還原成功！")
            self.set_status(f"✅ 已成功還原狀態。", "#4CAF50"); messagebox.showinfo("還原成功", "資料已成功從備份檔還原！")
        except Exception as e: messagebox.showerror("還原失敗", f"還原備份檔案時發生錯誤：\n\n{e}")

    def export_csv(self):
        if not self.data or not self.data.get("vehicles"): return messagebox.showinfo("匯出", "目前沒有車輛資料可供匯出。")
        file_path = filedialog.asksaveasfilename(title="匯出車輛清單為 CSV", initialfile=f"GTA_Garage_Export_{self.current_id}.csv", defaultextension=".csv", filetypes=[("CSV 檔案", "*.csv")])
        if not file_path: return 
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["車輛名稱", "存放位置", "類型", "取得方式", "購入價格(估值)", "改裝狀態", "數量", "備註", "登記日期", "最後修改"])
                for car in self.data["vehicles"]:
                    writer.writerow([car.get("name", ""), car.get("garage", ""), car.get("v_type", ""), car.get("acquire", ""), car.get("price", 0), car.get("upgraded", ""), car.get("count", 1), car.get("notes", ""), car.get("created_at", ""), car.get("updated_at", "")])
            self.set_status(f"✅ CSV 報表匯出成功", color="#4CAF50"); self.show_toast_progress("📥 CSV 匯出成功！"); messagebox.showinfo("匯出成功", f"車庫資產已匯出至：\n{file_path}")
        except Exception as e: messagebox.showerror("匯出錯誤", f"匯出失敗：\n{e}")

    def show_about(self):
        messagebox.showinfo("關於", f"🚗 洛聖都資產管理系統\n當前版本：{APP_VERSION} (完美手動排序版)")

    def open_settings_window(self):
        if not self.data: return messagebox.showwarning("操作提示", "請先登入角色 ID，才能設定專屬參數！")
        win = tk.Toplevel(self.root); win.title("⚙️ 全域與版面設定"); self.center_toplevel_window(win, 520, 650); win.configure(bg=COLOR_CARD_BG)
        canvas = tk.Canvas(win, borderwidth=0, bg=COLOR_CARD_BG, highlightthickness=0); scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLOR_CARD_BG); scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=500); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        win.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(int(-1*(ev.delta/120)), "units")))
        win.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        tk.Label(scrollable_frame, text="👁️ 版面顯示設定", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#4CAF50").pack(pady=(15, 5))
        settings = self.data.get("app_settings", {}); vars_dict = {}
        features = [("tab_bulletin", "📢 系統公告"), ("tab_vehicles", "🚗 車輛管理"), ("tab_non_personal", "🚜 非個人與帕格薩斯"), ("tab_special", "🚁 特殊載具"), ("tab_garages", "🏠 車庫管理"), ("tab_wishlist", "🛒 購車願望清單"), ("tab_statistics", "📊 統計資料"), ("tab_logs", "📜 操作日誌"), ("tool_stopwatch", "⏱️ 任務碼錶"), ("auto_backup", "🛡️ 自動備份")]
        frame_checks = tk.Frame(scrollable_frame, bg=COLOR_CARD_BG); frame_checks.pack(fill="x", padx=40)
        for key, text in features:
            var = tk.BooleanVar(win, value=settings.get(key, True)); vars_dict[key] = var
            tk.Checkbutton(frame_checks, text=text, variable=var, bg=COLOR_CARD_BG, fg="white", selectcolor="#757575", font=FONT_BOLD).pack(anchor="w", pady=3)
            
        ttk.Separator(scrollable_frame, orient="horizontal").pack(fill="x", pady=15, padx=20)
        tk.Label(scrollable_frame, text="🛠️ 全域容量與限制設定", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#e74c3c").pack(pady=(5, 5))
        frame_inputs = tk.Frame(scrollable_frame, bg=COLOR_CARD_BG); frame_inputs.pack(fill="x", padx=40, pady=5)
        
        tk.Label(frame_inputs, text="🏠 一般車庫預設上限:", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).grid(row=0, column=0, sticky="e", pady=8)
        ent_g_limit = tk.Entry(frame_inputs, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=10); ent_g_limit.insert(0, str(settings.get("default_garage_limit", 10))); ent_g_limit.grid(row=0, column=1, padx=10, pady=8)
        tk.Label(frame_inputs, text="🚁 特殊載具預設上限:", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).grid(row=1, column=0, sticky="e", pady=8)
        ent_s_limit = tk.Entry(frame_inputs, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=10); ent_s_limit.insert(0, str(settings.get("default_special_limit", 2))); ent_s_limit.grid(row=1, column=1, padx=10, pady=8)
        
        var_limits = tk.BooleanVar(win, value=settings.get("disable_all_limits", False)); tk.Checkbutton(scrollable_frame, text="♾️ 解除所有容量上限", variable=var_limits, bg=COLOR_CARD_BG, fg="white", selectcolor="#757575", font=FONT_BOLD).pack(pady=5)
        var_overwrite = tk.BooleanVar(win, value=False); tk.Checkbutton(scrollable_frame, text="⚠️ 強制套用預設上限至「現有所有車庫」", variable=var_overwrite, bg=COLOR_CARD_BG, fg="#F39C12", selectcolor="#757575", font=FONT_BOLD).pack(pady=5)

        ttk.Separator(scrollable_frame, orient="horizontal").pack(fill="x", pady=15, padx=20)
        tk.Label(scrollable_frame, text="🏷️ 自訂「取得方式」選單管理", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#F39C12").pack(pady=(5, 5))
        frame_acq = tk.Frame(scrollable_frame, bg=COLOR_CARD_BG); frame_acq.pack(fill="x", padx=50, pady=5)
        scrollbar_acq = ttk.Scrollbar(frame_acq); scrollbar_acq.pack(side="right", fill="y")
        list_acq = tk.Listbox(frame_acq, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", selectbackground="#4CAF50", height=5, relief="solid", yscrollcommand=scrollbar_acq.set); list_acq.pack(side="left", fill="both", expand=True); scrollbar_acq.config(command=list_acq.yview)
        
        temp_acq_list = self.data.get("acquire_options", ACQUIRE_OPTIONS).copy()
        for opt in temp_acq_list: list_acq.insert(tk.END, opt)
            
        btn_f_acq = tk.Frame(scrollable_frame, bg=COLOR_CARD_BG); btn_f_acq.pack(fill="x", padx=50, pady=5)
        ent_new_acq = tk.Entry(btn_f_acq, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=14); ent_new_acq.pack(side="left", padx=(0, 10), fill="x", expand=True, ipady=3)
        def add_acq(e=None):
            if ent_new_acq.get().strip() and ent_new_acq.get().strip() not in temp_acq_list: temp_acq_list.append(ent_new_acq.get().strip()); list_acq.insert(tk.END, ent_new_acq.get().strip()); ent_new_acq.delete(0, tk.END); list_acq.see(tk.END)
        def del_acq():
            sel = list_acq.curselection()
            if sel: temp_acq_list.pop(sel[0]); list_acq.delete(sel[0])
        ttk.Button(btn_f_acq, text="➕ 新增", command=add_acq, style="Success.TButton").pack(side="left", padx=2); ttk.Button(btn_f_acq, text="🗑️ 刪除", command=del_acq, style="Danger.TButton").pack(side="left", padx=2)

        ttk.Separator(scrollable_frame, orient="horizontal").pack(fill="x", pady=15, padx=20)
        tk.Label(scrollable_frame, text="⌨️ 任務碼錶快捷鍵", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#9b59b6").pack(pady=(5, 5))
        frame_hotkeys = tk.Frame(scrollable_frame, bg=COLOR_CARD_BG); frame_hotkeys.pack(fill="x", padx=40, pady=5)
        tk.Label(frame_hotkeys, text="準備/暫停:", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).grid(row=0, column=0, sticky="e", pady=8)
        ent_hk_pause = tk.Entry(frame_hotkeys, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=10); ent_hk_pause.insert(0, settings.get("hotkey_pause", "pause")); ent_hk_pause.grid(row=0, column=1, padx=10, pady=8)
        tk.Label(frame_hotkeys, text="起跑/計時:", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).grid(row=1, column=0, sticky="e", pady=8)
        ent_hk_start = tk.Entry(frame_hotkeys, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=10); ent_hk_start.insert(0, settings.get("hotkey_start", "w")); ent_hk_start.grid(row=1, column=1, padx=10, pady=8)

        def save_settings():
            for key, var in vars_dict.items(): self.data["app_settings"][key] = var.get()
            try: new_g = int(ent_g_limit.get().strip())
            except: new_g = 10
            try: new_s = int(ent_s_limit.get().strip())
            except: new_s = 2
            self.data["app_settings"]["disable_all_limits"] = var_limits.get(); self.data["app_settings"]["default_garage_limit"] = new_g; self.data["app_settings"]["default_special_limit"] = new_s
            self.data["app_settings"]["hotkey_pause"] = ent_hk_pause.get().strip().lower() or "pause"; self.data["app_settings"]["hotkey_start"] = ent_hk_start.get().strip().lower() or "w"
            if var_overwrite.get():
                spec_carriers = [sv["name"] for sv in self.data.get("special_vehicles", [])]
                for g in self.data.get("garages", []):
                    if g != "未分類" and g != "帕格薩斯": self.data["garage_limits"][g] = new_s if g in spec_carriers else new_g
            self.data["acquire_options"] = temp_acq_list
            save_data(self.all_data); self.apply_settings(); self.check_login_status(); self.refresh_garage_table(); win.destroy(); self.show_toast_progress("⚙️ 設定已儲存")
            
        ttk.Button(scrollable_frame, text="💾 儲存並套用", command=save_settings, style="Primary.TButton").pack(fill="x", padx=40, pady=(20, 20), ipady=4)

    def apply_settings(self):
        settings = self.data.get("app_settings", {}) if self.data else {"tool_stopwatch": True}
        pause_key = settings.get("hotkey_pause", "pause"); start_key = settings.get("hotkey_start", "w")
        if settings.get("tool_stopwatch", True):
            self.tools_menu.entryconfig("⏱️ 呼叫任務碼錶", state="normal")
            if HAS_KEYBOARD:
                try: keyboard.unhook_all(); keyboard.add_hotkey(pause_key, self.handle_pause_key); keyboard.add_hotkey(start_key, self.handle_w_key)
                except Exception: pass
            else: self.root.bind_all(f"<{pause_key.capitalize()}>", self.handle_pause_key); self.root.bind_all(f"<{start_key.lower()}>", self.handle_w_key)
        else:
            self.tools_menu.entryconfig("⏱️ 呼叫任務碼錶", state="disabled")
            if HAS_KEYBOARD:
                try: keyboard.unhook_all()
                except: pass
            self.root.unbind_all(f"<{pause_key.capitalize()}>"); self.root.unbind_all(f"<{start_key.lower()}>")

    def setup_status_bar(self):
        self.status_bar = tk.Label(self.root, text="💡 系統就緒。", bg="#111111", fg="#FF9800", font=FONT_BOLD, anchor="w", padx=15, pady=6); self.status_bar.pack(side="bottom", fill="x")
        self.root.after(1000, self.apply_new_tags_loop)

    def apply_new_tags_loop(self):
        if hasattr(self, 'data') and self.data:
            import datetime
            now = datetime.datetime.now()
            def is_new(t_str):
                if not t_str: return False
                try: return (now - datetime.datetime.strptime(t_str, '%Y-%m-%d %H:%M')).total_seconds() < 86400
                except: return False
            for tree in [getattr(self, 'tree_vehicles', None), getattr(self, 'tree_non_personal', None)]:
                if not tree or not tree.winfo_exists(): continue
                for child in tree.get_children():
                    try:
                        car = self.data["vehicles"][int(child)]; curr = tree.set(child, "name")
                        is_n = is_new(car.get("updated_at", car.get("created_at", "")))
                        if is_n and not curr.startswith("🆕 "): tree.set(child, "name", "🆕 " + curr.replace("🆕 ", ""))
                        elif not is_n and curr.startswith("🆕 "): tree.set(child, "name", curr.replace("🆕 ", ""))
                    except: pass
        self.root.after(3000, self.apply_new_tags_loop)

    def set_status(self, msg, color="#FF9800"):
        if hasattr(self, 'status_bar') and self.status_bar.winfo_exists(): self.status_bar.config(text=msg, fg=color)

    def log_action(self, msg):
        if not self.data: return
        self.data.setdefault("action_logs", []).append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]  {msg}")
        self.data["action_logs"] = self.data["action_logs"][-200:]; save_data(self.all_data); self.refresh_logs_display()

    def center_toplevel_window(self, win, width, height):
        width = int(width * 1.1) + 40; height = int(height * 1.15) + 120
        win.configure(bg=COLOR_MAIN_BG); self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - width) // 2; y = self.root.winfo_y() + (self.root.winfo_height() - height) // 2
        if y < 30: y = 30
        win.geometry(f"{width}x{height}+{x}+{y}"); win.minsize(width, height)

    def sort_treeview(self, tv, col, reverse):
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        try: l.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError: l.sort(key=lambda t: t[0].replace("📌 ", "").replace("🔒 ", "").replace("☑ ", "").replace("☐ ", "").replace("🆕 ", ""), reverse=reverse)
        for index, (val, k) in enumerate(l): tv.move(k, '', index)
        for c in tv["columns"]:
            clean_text = tv.heading(c)["text"].replace(" ▲", "").replace(" ▼", "")
            tv.heading(c, text=f"{clean_text} {'▼' if reverse else '▲'}" if c == col else clean_text, command=lambda _c=c: self.sort_treeview(tv, _c, not reverse))

    def sync_special_from_vehicles(self):
        if not self.data: return
        for sv in self.data.get("special_vehicles", []): sv["inner_vehicle"] = ""
        for car in self.data.get("vehicles", []):
            for sv in self.data.get("special_vehicles", []):
                if sv["name"] == car.get("garage", ""): sv["inner_vehicle"] += f", {car['name']}" if sv["inner_vehicle"] else car["name"]

    def sync_vehicles_from_special(self):
        if not self.data: return
        for sv in self.data.get("special_vehicles", []):
            if sv.get("inner_vehicle", "") and sv.get("can_store", False) and "," not in sv["inner_vehicle"]:
                if not any(car["name"] == sv["inner_vehicle"] for car in self.data.get("vehicles", [])):
                    self.data["vehicles"].append({"name": sv["inner_vehicle"], "garage": sv["name"], "v_type": "", "acquire": "", "upgraded": "", "count": 1, "notes": f"自【{sv['name']}】同步", "locked": False, "pinned": False, "created_at": time.strftime('%Y-%m-%d %H:%M'), "updated_at": time.strftime('%Y-%m-%d %H:%M')})

    def validate_tab1_vehicle_to_garage(self, car_name, target_garage, show_error=True):
        if target_garage in SUB_CARRIER_RULES:
            if not any(a.lower() in car_name.lower() or car_name.lower() in a.lower() for a in SUB_CARRIER_RULES[target_garage]):
                if show_error: messagebox.showerror("違規", f"❌ 【{target_garage}】限制停放專屬載具！")
                return False
        return True

    def setup_profile_bar(self):
        top_frame = tk.Frame(self.root, bg="#1a1a1a", pady=10); top_frame.pack(fill="x", side="top")
        tk.Label(top_frame, text="👤 選擇角色 ID:", bg="#1a1a1a", fg="white", font=FONT_BOLD).pack(side="left", padx=(15, 5))
        self.combo_profile = ttk.Combobox(top_frame, width=15, font=FONT_NORMAL); self.combo_profile.pack(side="left", padx=5)
        self.btn_login_logout = ttk.Button(top_frame, text="🔑 登入系統", command=self.login_profile, style="Success.TButton"); self.btn_login_logout.pack(side="left", padx=3)
        self.lbl_clock = tk.Label(top_frame, text="", bg="#1a1a1a", fg="#4CAF50", font=("Consolas", 13, "bold")); self.lbl_clock.pack(side="right", padx=20); self.update_clock() 
        self.update_profile_combo(); self.combo_profile.bind("<Return>", lambda e: self.login_profile())

    def random_ride(self):
        if not self.data: return
        valid_cars = [c for c in self.data["vehicles"] if c.get("v_type") == "個人載具" and c.get("garage") not in ["帕格薩斯", "未分類"]]
        if not valid_cars: return messagebox.showinfo("隨機選車", "你的車庫裡目前沒有可用的個人載具喔！")
        car = random.choice(valid_cars)
        win = tk.Toplevel(self.root); win.title("🎲 今天開哪台？"); self.center_toplevel_window(win, 350, 220); win.configure(bg=COLOR_CARD_BG)
        tk.Label(win, text="🎯 系統為您今日指定了：", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#e91e63").pack(pady=(20, 10))
        tk.Label(win, text=f"🚗 【 {car['name']} 】", font=("Microsoft JhengHei", 18, "bold"), bg=COLOR_CARD_BG, fg="white").pack()
        tk.Label(win, text=f"📍 停放於：{car['garage']}", font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="#3498db").pack(pady=10)
        ttk.Button(win, text="太棒了，今天就開這台！", command=win.destroy, style="Success.TButton").pack(pady=10)

    def update_clock(self): self.lbl_clock.config(text=f"🕒 {time.strftime('%Y-%m-%d  %H:%M:%S')}"); self.root.after(1000, self.update_clock)

    def update_profile_combo(self):
        if self.current_id: self.combo_profile["values"] = [self.current_id]; self.combo_profile.set(self.current_id)
        else: self.combo_profile["values"] = list(self.all_data.get("profiles", {}).keys())
        if hasattr(self, "refresh_account_listbox"): self.refresh_account_listbox()

    def show_toast_progress(self, message="✅ 操作成功"):
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg=COLOR_CARD_BG)
        self.root.update_idletasks()
        try:
            x = self.root.winfo_rootx() + self.root.winfo_width() - 320 - 20
            y = self.root.winfo_rooty() + self.root.winfo_height() - 70 - 20
            toast.geometry(f"320x70+{x}+{y}")
        except:
            toast.geometry("320x70")
        frame = tk.Frame(toast, bg=COLOR_CARD_BG, highlightbackground="#4CAF50", highlightthickness=2)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=message, bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).pack(expand=True, pady=5)
        def step(v):
            if not toast.winfo_exists(): return 
            if v <= 100: toast.after(20, step, v + 5)
            else: toast.after(800, lambda: toast.destroy() if toast.winfo_exists() else None)
        step(0)

    def check_login_status(self):
        is_logged_in = bool(self.current_id and self.current_id in self.all_data["profiles"])
        state_str = "normal" if is_logged_in else "disabled"
        if hasattr(self, 'btn_login_logout'): self.btn_login_logout.config(text="🚪 安全登出", command=self.logout_profile, style="Warning.TButton") if is_logged_in else self.btn_login_logout.config(text="🔑 登入系統", command=self.login_profile, style="Success.TButton")
        self.combo_profile.config(state="disabled" if is_logged_in else "normal")
        if hasattr(self, 'edit_menu'):
            for idx in [0, 1, 3]:
                try: self.edit_menu.entryconfig(idx, state=state_str)
                except: pass

        if is_logged_in:
            self.data = self.all_data["profiles"][self.current_id]
            for key, default in [("vehicles", []), ("special_vehicles", []), ("garages", ["未分類", "帕格薩斯", "日蝕大樓", "日蝕大樓 - 車庫1"]), ("action_logs", []), ("acquire_options", ACQUIRE_OPTIONS.copy()), ("wishlist", [])]:
                if key not in self.data: self.data[key] = default
            if "garage_limits" not in self.data:
                self.data["garage_limits"] = {"未分類": 999}; 
                for g in self.data["garages"]: 
                    if g != "未分類": self.data["garage_limits"][g] = 10
            
            if "app_settings" not in self.data: self.data["app_settings"] = {}
            for k, v in {"tab_bulletin": True, "tab_vehicles": True, "tab_non_personal": True, "tab_special": True, "tab_garages": True, "tab_statistics": True, "tab_logs": True, "tab_wishlist": True, "tool_stopwatch": True, "disable_all_limits": False, "auto_backup": True, "default_garage_limit": 10, "default_special_limit": 2, "visible_columns": ["check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"]}.items():
                if k not in self.data["app_settings"]: self.data["app_settings"][k] = v
            
            for v in self.data["vehicles"]:
                if v.get("garage") == "帕格薩斯" or v.get("v_type") == "帕格薩斯": v["garage"] = "帕格薩斯"; v["v_type"] = "帕格薩斯"; v["count"] = 1; v["upgraded"] = "不可改裝"
            
            self.checked_indices.clear() 
            self.cd_target_sec = self.data["app_settings"].get("default_countdown_sec", 300.0)
            if not getattr(self, 'is_running', False) and getattr(self, 'sw_mode', 'STOPWATCH') == "COUNTDOWN": self.elapsed_time = self.cd_target_sec; self.update_stopwatch_ui()
                
            vis_cols = self.data["app_settings"].get("visible_columns", ["check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"])
            if hasattr(self, 'tree_vehicles') and self.tree_vehicles.winfo_exists(): self.tree_vehicles["displaycolumns"] = vis_cols
            if hasattr(self, 'tree_non_personal') and self.tree_non_personal.winfo_exists(): self.tree_non_personal["displaycolumns"] = vis_cols
                
        else: 
            self.current_id = ""; self.data = None
            if hasattr(self, 'text_logs'): self.text_logs.config(state="normal"); self.text_logs.delete("1.0", tk.END); self.text_logs.config(state="disabled")

        settings = self.data.get("app_settings", {}) if self.data else {}
        self.notebook.tab(self.tab_bulletin, state="normal" if settings.get("tab_bulletin", True) else "hidden")
        self.notebook.tab(self.tab_account, state="normal")
        for key, tab in [("tab_vehicles", self.tab_vehicles), ("tab_non_personal", self.tab_non_personal), ("tab_special", self.tab_special), ("tab_garages", self.tab_garages), ("tab_wishlist", self.tab_wishlist), ("tab_statistics", self.tab_statistics), ("tab_logs", self.tab_logs)]:
            self.notebook.tab(tab, state="normal" if (is_logged_in and settings.get(key, True)) else "hidden")
            
        self.update_garage_comboboxes(); self.update_acquire_comboboxes(); self.refresh_vehicle_tables(); self.refresh_special_table(); self.refresh_garage_table(); self.apply_settings()
        self.on_tab_changed()
        if is_logged_in: 
            self.refresh_bulletin_display(); self.refresh_logs_display(); self.refresh_wishlist_table(); self.update_checked_button_text()
            if self.notebook.select() and "統計資料" in self.notebook.tab(self.notebook.select(), "text"): self.refresh_statistics()

    def update_acquire_comboboxes(self):
        if hasattr(self, 'combo_acquire'): self.combo_acquire["values"] = self.data.get("acquire_options", ACQUIRE_OPTIONS) if self.data else ACQUIRE_OPTIONS

    def login_profile(self):
        sel = self.combo_profile.get().strip()
        if sel and sel in self.all_data["profiles"]: 
            self.current_id = sel; self.update_profile_combo(); self.check_login_status(); self.show_toast_progress(f"🔑 登入成功：{sel}"); self.set_status(f"🔑 成功登入角色：{sel}", "#4CAF50"); self.log_action("🔑 登入系統")

    def logout_profile(self): 
        if self.data: self.log_action("🚪 登出系統")
        self.current_id = ""; self.update_profile_combo(); self.check_login_status(); self.combo_profile.set(""); self.show_toast_progress("🚪 已登出"); self.set_status("🚪 已登出，請選擇 ID 登入。", "#FF9800")

    def get_active_tree(self, event=None):
        if event and hasattr(event, 'widget') and isinstance(event.widget, ttk.Treeview): return event.widget
        if self.notebook.select() and "非個人" in self.notebook.tab(self.notebook.select(), "text"): return self.tree_non_personal
        return self.tree_vehicles

    def on_vehicle_hover(self, event):
        if not self.data: return
        tree = event.widget; iid = tree.identify_row(event.y)
        if iid:
            if getattr(self, "last_hovered_iid", None) != iid:
                self.last_hovered_iid = iid
                try: self.set_status(f"🕒 【{self.data['vehicles'][int(iid)]['name']}】 登記：{self.data['vehicles'][int(iid)].get('created_at', '-')}   |   修改：{self.data['vehicles'][int(iid)].get('updated_at', '-')}", "#3498db")
                except: pass
        else:
            if getattr(self, "last_hovered_iid", None) is not None: self.last_hovered_iid = None; self.set_status("💡 系統就緒。", "#FF9800")

    # ==========================================
    #     👥 帳號管理分頁
    # ==========================================
    def setup_account_tab(self):
        tk.Label(self.tab_account, text="👥 系統帳號與角色管理", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#3498db").pack(pady=(30, 15))
        frame_add = tk.LabelFrame(self.tab_account, text=" ➕ 註冊新帳號/角色 ID ", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="#4CAF50"); frame_add.pack(fill="x", padx=40, pady=10, ipady=5)
        tk.Label(frame_add, text="輸入新 ID 名稱:", font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white").pack(side="left", padx=(15,5), pady=15)
        self.entry_new_account = tk.Entry(frame_add, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=25); self.entry_new_account.pack(side="left", padx=5)
        apply_focus_highlight(self.entry_new_account)
        ttk.Button(frame_add, text="建立帳號", command=self.create_profile_from_tab, style="Success.TButton").pack(side="left", padx=10); self.entry_new_account.bind("<Return>", lambda e: self.create_profile_from_tab())
        
        frame_del = tk.LabelFrame(self.tab_account, text=" 🗑️ 刪除已有帳號 (需為登出狀態) ", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="#e74c3c"); frame_del.pack(fill="both", expand=True, padx=40, pady=10, ipady=5)
        scroll_acc = ttk.Scrollbar(frame_del); scroll_acc.pack(side="right", fill="y")
        self.list_accounts = tk.Listbox(frame_del, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", selectbackground="#e74c3c", yscrollcommand=scroll_acc.set, relief="solid"); self.list_accounts.pack(side="left", fill="both", expand=True, padx=(15, 0), pady=15); scroll_acc.config(command=self.list_accounts.yview)
        btn_f = tk.Frame(frame_del, bg=COLOR_CARD_BG); btn_f.pack(side="bottom", fill="x", padx=15, pady=(0, 15))
        ttk.Button(btn_f, text="🗑️ 徹底刪除所選帳號", command=self.delete_profile_from_tab, style="Danger.TButton").pack(side="right")
        self.refresh_account_listbox()

    def refresh_account_listbox(self):
        if hasattr(self, 'list_accounts') and self.list_accounts.winfo_exists():
            self.list_accounts.delete(0, tk.END)
            for acc in self.all_data.get("profiles", {}).keys(): self.list_accounts.insert(tk.END, acc)

    def create_profile_from_tab(self):
        name = self.entry_new_account.get().strip()
        if not name: return messagebox.showwarning("提示", "請輸入角色 ID 名稱！")
        if name in self.all_data["profiles"]: return messagebox.showwarning("重複", "ID 已經存在！")
        
        self.all_data["profiles"][name] = {"vehicles": [], "special_vehicles": [], "garages": ["未分類", "帕格薩斯", "日蝕大樓", "日蝕大樓 - 車庫1"], "garage_limits": {"未分類": 999, "帕格薩斯": 999, "日蝕大樓": 10, "日蝕大樓 - 車庫1": 10}, "action_logs": [f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]  🌟 建立角色 ID 檔案"], "acquire_options": ACQUIRE_OPTIONS.copy(), "wishlist": [], "app_settings": {"tab_bulletin": True, "tab_vehicles": True, "tab_non_personal": True, "tab_special": True, "tab_garages": True, "tab_statistics": True, "tab_logs": True, "tab_wishlist": True, "tool_stopwatch": True, "disable_all_limits": False, "auto_backup": True, "default_garage_limit": 10, "default_special_limit": 2, "visible_columns": ["check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"]}}
        save_data(self.all_data); self.update_profile_combo(); self.combo_profile.set(name); self.entry_new_account.delete(0, tk.END); self.show_toast_progress(f"✅ 成功建立：{name}")

    def delete_profile_from_tab(self):
        if self.current_id: return messagebox.showwarning("操作提示", "請先點擊上方「🚪 安全登出」後，才能進行刪除帳號的操作喔！")
        sel = self.list_accounts.curselection()
        if not sel: return
        acc_name = self.list_accounts.get(sel[0])
        if messagebox.askyesno("⚠️ 極度危險操作", f"確定要徹底刪除 ID：【 {acc_name} 】嗎？") and messagebox.askyesno("❗ 最後確認", "資料刪除後無法還原，確定抹除嗎？"):
            del self.all_data["profiles"][acc_name]; save_data(self.all_data); self.show_toast_progress(f"🗑️ 已抹除 ID：{acc_name}"); self.set_status(f"🗑️ 角色檔案 {acc_name} 已永久移除。", "#c62828"); self.update_profile_combo(); self.combo_profile.set(""); self.check_login_status()

    # ==========================================
    #     📢 0. 系統公告分頁
    # ==========================================
    def setup_bulletin_tab(self):
        tk.Label(self.tab_bulletin, text="📢 洛聖都資產管理系統 - 系統公告與更新日誌", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#4CAF50").pack(pady=(30, 15))
        text_frame = tk.Frame(self.tab_bulletin, bg=COLOR_MAIN_BG); text_frame.pack(fill="both", expand=True, padx=40, pady=(0, 40))
        scrollbar = ttk.Scrollbar(text_frame); scrollbar.pack(side="right", fill="y")
        self.text_bulletin = tk.Text(text_frame, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, relief="solid", padx=20, pady=20, wrap="word", yscrollcommand=scrollbar.set)
        self.text_bulletin.pack(side="left", fill="both", expand=True); scrollbar.config(command=self.text_bulletin.yview); self.refresh_bulletin_display()
        
    def refresh_bulletin_display(self):
        if not hasattr(self, 'text_bulletin') or not self.text_bulletin.winfo_exists(): return
        changelog = f"""==================================================\n【系統開發與重大更新日誌】\n🌟 最新版本：V1.1.20 (智慧連動改名修復版)\n📅 更新日期：2026-08\n\n📝 本次重大更新回顧：\n1. 🛠️ 核心修復：徹底修復「主樓層改名後會脫離原本物業，變成單一車庫」的致命邏輯錯誤。現在改名主樓層時，系統會智慧連動更改所有附屬樓層！\n2. 🏢 專屬整棟管理：在右側面板對著「主物業」點擊右鍵，現在可以直接重新命名整棟大樓或變賣整棟大樓了！\n3. 🔄 完美連續排序：修復左側清單無法連續連點「上移/下移」的問題，盡情享受流暢的手動排序吧。"""
        self.text_bulletin.config(state="normal"); self.text_bulletin.delete("1.0", tk.END); self.text_bulletin.insert("1.0", changelog.strip()); self.text_bulletin.config(state="disabled")

    # ==========================================
    #     📊 0.4. 統計資料分頁
    # ==========================================
    def setup_statistics_tab(self):
        tk.Label(self.tab_statistics, text="📊 洛聖都資產統計儀表板", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#F39C12").pack(pady=(20, 10))
        self.canvas_stats = tk.Canvas(self.tab_statistics, borderwidth=0, bg=COLOR_MAIN_BG, highlightthickness=0)
        self.scrollbar_stats = ttk.Scrollbar(self.tab_statistics, orient="vertical", command=self.canvas_stats.yview)
        self.stats_frame = tk.Frame(self.canvas_stats, bg=COLOR_MAIN_BG); self.stats_frame.bind("<Configure>", lambda e: self.canvas_stats.configure(scrollregion=self.canvas_stats.bbox("all")))
        self.canvas_stats.create_window((0, 0), window=self.stats_frame, anchor="nw", width=1200); self.canvas_stats.configure(yscrollcommand=self.scrollbar_stats.set)
        self.canvas_stats.pack(side="left", fill="both", expand=True, padx=15, pady=10); self.scrollbar_stats.pack(side="right", fill="y")
        self.tab_statistics.bind("<Enter>", lambda e: self.canvas_stats.bind_all("<MouseWheel>", lambda ev: self.canvas_stats.yview_scroll(int(-1 * (ev.delta / 120)), "units") if hasattr(self, 'canvas_stats') and self.canvas_stats.winfo_exists() else None))
        self.tab_statistics.bind("<Leave>", lambda e: self.canvas_stats.unbind_all("<MouseWheel>"))

    def refresh_statistics(self):
        for widget in self.stats_frame.winfo_children(): widget.destroy()
        if not self.data: return
        vehicles = self.data.get("vehicles", []); garages = self.data.get("garages", []); specials = self.data.get("special_vehicles", []); limits = self.data.get("garage_limits", {})
        disable_limits = self.data.get("app_settings", {}).get("disable_all_limits", False)
        total_cars = sum(v.get("count", 1) for v in vehicles); actual_garages = [g for g in garages if g not in ["未分類", "帕格薩斯"]]; total_garages = len(actual_garages)
        type_counts = {"個人載具": 0, "非個人載具": 0, "帕格薩斯": 0, "未設定": 0}; upg_counts = {"已改滿": 0, "未改滿": 0, "不可改裝": 0, "未設定": 0}; acq_counts = {}; total_value = 0 
        for v in vehicles:
            c = v.get("count", 1)
            try: p = int(v.get("price", 0))
            except: p = 0
            total_value += (p * c)
            vt = v.get("v_type", "") or "未設定"; type_counts[vt] = type_counts.get(vt, 0) + c
            upg = v.get("upgraded", "") or "未設定"; upg_counts[upg] = upg_counts.get(upg, 0) + c
            acq = v.get("acquire", "") or "未設定"; acq_counts[acq] = acq_counts.get(acq, 0) + c

        total_capacity = sum(limits.get(g, 10) for g in actual_garages) + sum(limits.get(sv.get("name"), 2) for sv in specials if sv.get("can_store", False))
        total_used_in_capacity = sum(self.count_cars_in_garage(g) for g in actual_garages) + sum(self.count_cars_in_garage(sv.get("name")) for sv in specials if sv.get("can_store", False))
        
        row1 = tk.Frame(self.stats_frame, bg=COLOR_MAIN_BG); row1.pack(fill="x", pady=10)
        def create_stat_card(parent, title, value, color):
            f = tk.Frame(parent, bg=COLOR_CARD_BG, highlightbackground=color, highlightthickness=2, padx=15, pady=15); f.pack(side="left", fill="both", expand=True, padx=10)
            tk.Label(f, text=title, font=FONT_BOLD, bg=COLOR_CARD_BG, fg=COLOR_TEXT_GRAY).pack(); tk.Label(f, text=str(value), font=("Consolas", 24, "bold"), bg=COLOR_CARD_BG, fg=color).pack(pady=(10, 0))
        create_stat_card(row1, "🚗 總擁有載具數量", total_cars, "#3498db"); create_stat_card(row1, "💎 車庫總資產估值", f"$ {total_value:,}", "#9b59b6"); create_stat_card(row1, "🏠 總車庫/樓層數", total_garages, "#4CAF50"); create_stat_card(row1, "🅿️ 總車位使用率", f"{total_used_in_capacity} / ∞" if disable_limits else f"{total_used_in_capacity} / {total_capacity}", "#F39C12")

        row2 = tk.Frame(self.stats_frame, bg=COLOR_MAIN_BG); row2.pack(fill="x", pady=15)
        def create_bar_stat(parent, title, items):
            f = tk.LabelFrame(parent, text=f" {title} ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="white", bd=2, padx=20, pady=20); f.pack(side="left", fill="both", expand=True, padx=10)
            total = sum(val for val, lbl, color in items) or 1 
            for idx, (val, lbl, color) in enumerate(items):
                pct = val / total * 100
                tk.Label(f, text=f"{lbl} ({val}) - {pct:.1f}%", font=FONT_BOLD, bg=COLOR_CARD_BG, fg=color).pack(anchor="w")
                ttk.Progressbar(f, length=400, mode="determinate", value=pct).pack(fill="x", pady=(2, 10 if idx < len(items) - 1 else 0))
        create_bar_stat(row2, "🔧 改裝狀態分布", [(upg_counts["已改滿"], "✅ 已改滿", "#4CAF50"), (upg_counts["未改滿"], "⚠️ 未改滿", "#e74c3c"), (upg_counts["不可改裝"], "❌ 不可改裝", "#9b59b6"), (upg_counts["未設定"], "❓ 未設定", "#95a5a6")])
        create_bar_stat(row2, "🚜 載具類型分布", [(type_counts["個人載具"], "🚗 個人載具", "#3498db"), (type_counts["非個人載具"], "🚜 非個人載具", "#F39C12"), (type_counts["帕格薩斯"], "🚁 帕格薩斯", "#9b59b6"), (type_counts["未設定"], "❓ 未設定", "#95a5a6")])

        row3 = tk.LabelFrame(self.stats_frame, text=" 🎁 載具取得方式排行榜 ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#9b59b6", bd=2, padx=20, pady=20); row3.pack(fill="x", padx=10, pady=10)
        sorted_acq = sorted(acq_counts.items(), key=lambda item: item[1], reverse=True)
        if not sorted_acq: tk.Label(row3, text="目前沒有任何車輛資料可供分析。", font=FONT_NORMAL, bg=COLOR_CARD_BG, fg=COLOR_TEXT_GRAY).pack()
        else:
            for acq, count in sorted_acq:
                pct = count / total_cars * 100 if total_cars > 0 else 0
                f = tk.Frame(row3, bg=COLOR_CARD_BG); f.pack(fill="x", pady=4)
                tk.Label(f, text=f"▪️ {acq}", width=20, anchor="w", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="white").pack(side="left"); tk.Label(f, text=f"{count} 台", width=8, anchor="e", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="#9b59b6").pack(side="left"); tk.Label(f, text=f"({pct:.1f}%)", width=8, anchor="e", font=FONT_NORMAL, bg=COLOR_CARD_BG, fg=COLOR_TEXT_GRAY).pack(side="left", padx=(0, 15)); ttk.Progressbar(f, length=600, mode="determinate", value=pct).pack(side="left", fill="x", expand=True)

    # ==========================================
    #     📜 0.5. 操作日誌與願望清單
    # ==========================================
    def setup_logs_tab(self):
        header_frame = tk.Frame(self.tab_logs, bg=COLOR_MAIN_BG); header_frame.pack(fill="x", padx=15, pady=15)
        tk.Label(header_frame, text="📜 帳號操作日誌 (最多保留最近 200 筆紀錄)", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#4CAF50").pack(side="left"); ttk.Button(header_frame, text="🗑️ 清空歷史日誌", command=self.clear_logs, style="Danger.TButton").pack(side="right")
        self.text_logs = tk.Text(self.tab_logs, font=("Consolas", 11), bg=COLOR_CARD_BG, fg="#a8e6cf", relief="solid", padx=15, pady=15)
        vsb = ttk.Scrollbar(self.tab_logs, orient="vertical", command=self.text_logs.yview); self.text_logs.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y", pady=(0, 15), padx=(0, 15)); self.text_logs.pack(fill="both", expand=True, padx=(15, 0), pady=(0, 15)); self.text_logs.config(state="disabled")

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

    def setup_wishlist_tab(self):
        input_frame = tk.LabelFrame(self.tab_wishlist, text=" 🛒 新增想購買的載具 ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#3498db", padx=12, pady=12, bd=2); input_frame.pack(fill="x", padx=15, pady=10)
        for i in range(5): input_frame.columnconfigure(i, weight=0)
        input_frame.columnconfigure(1, weight=1); input_frame.columnconfigure(3, weight=1)
        tk.Label(input_frame, text="目標車輛名稱:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=0, column=0, sticky="e", pady=5, padx=5)
        self.ent_wish_name = tk.Entry(input_frame, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); self.ent_wish_name.grid(row=0, column=1, sticky="we", padx=5, pady=5); apply_focus_highlight(self.ent_wish_name)
        tk.Label(input_frame, text="目標價格(GTA$):", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=0, column=2, sticky="e", pady=5, padx=5)
        self.ent_wish_price = tk.Entry(input_frame, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); self.ent_wish_price.grid(row=0, column=3, sticky="we", padx=5, pady=5); apply_focus_highlight(self.ent_wish_price)
        tk.Label(input_frame, text="備註(改裝想法):", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=1, column=0, sticky="e", pady=5, padx=5)
        self.ent_wish_note = tk.Entry(input_frame, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); self.ent_wish_note.grid(row=1, column=1, columnspan=3, sticky="we", padx=5, pady=5); apply_focus_highlight(self.ent_wish_note)
        ttk.Button(input_frame, text="➕ 加入願望清單", command=self.add_wishlist, style="Primary.TButton", padding=(20, 4)).grid(row=0, column=4, rowspan=2, sticky="ns", padx=(15, 5), pady=5)
        self.ent_wish_name.bind("<Return>", lambda e: self.ent_wish_price.focus()); self.ent_wish_price.bind("<Return>", lambda e: self.ent_wish_note.focus()); self.ent_wish_note.bind("<Return>", lambda e: self.add_wishlist())

        action_frame = tk.Frame(self.tab_wishlist, bg=COLOR_MAIN_BG); action_frame.pack(fill="x", padx=15, pady=5)
        ttk.Button(action_frame, text="🎉 買到了！一鍵轉入正式車庫", command=self.buy_wishlist_item, style="Success.TButton").pack(side="left", padx=3); ttk.Button(action_frame, text="🗑️ 放棄購買", command=self.delete_wishlist_item, style="Danger.TButton").pack(side="right", padx=3)

        tree_frame = tk.Frame(self.tab_wishlist, bg=COLOR_MAIN_BG); tree_frame.pack(fill="both", expand=True, padx=15, pady=10)
        self.tree_wishlist = ttk.Treeview(tree_frame, columns=("name", "price", "notes"), show="headings", selectmode="extended")
        self.tree_wishlist.heading("name", text="目標車輛名稱"); self.tree_wishlist.heading("price", text="預計花費(GTA$)"); self.tree_wishlist.heading("notes", text="願望備註")
        self.tree_wishlist.column("name", width=250, anchor="w", stretch=True); self.tree_wishlist.column("price", width=150, anchor="center", stretch=False); self.tree_wishlist.column("notes", width=350, anchor="w", stretch=True)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_wishlist.yview); self.tree_wishlist.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y"); self.tree_wishlist.pack(side="left", fill="both", expand=True)

    def refresh_wishlist_table(self):
        if not hasattr(self, 'tree_wishlist'): return
        for i in self.tree_wishlist.get_children(): self.tree_wishlist.delete(i)
        if not self.data or "wishlist" not in self.data: return
        for idx, w in enumerate(self.data["wishlist"]): self.tree_wishlist.insert("", "end", iid=str(idx), values=(w.get("name", ""), f"$ {int(w.get('price', 0)):,}" if w.get('price') else "$ 0", w.get("notes", "")))

    def add_wishlist(self):
        if not self.data: return
        name = self.ent_wish_name.get().strip()
        if not name: return
        try: price = int(self.ent_wish_price.get().strip() or 0)
        except: price = 0
        self.data.setdefault("wishlist", []).append({"name": name, "price": price, "notes": self.ent_wish_note.get()}); save_data(self.all_data)
        self.log_action(f"🛒 加入願望清單：【{name}】"); self.ent_wish_name.delete(0, tk.END); self.ent_wish_price.delete(0, tk.END); self.ent_wish_note.delete(0, tk.END); self.refresh_wishlist_table(); self.show_toast_progress("🛒 願望已加入清單！")

    def delete_wishlist_item(self):
        if not self.data or "wishlist" not in self.data: return
        selected = self.tree_wishlist.selection()
        if not selected: return
        if messagebox.askyesno("確認刪除", "確定要放棄購買並移除這些項目嗎？"):
            for item in sorted([int(s) for s in selected], reverse=True): del self.data["wishlist"][item]
            save_data(self.all_data); self.refresh_wishlist_table(); self.show_toast_progress("🗑️ 已從願望清單移除")

    def buy_wishlist_item(self):
        if not self.data or "wishlist" not in self.data: return
        selected = self.tree_wishlist.selection()
        if not selected: return messagebox.showwarning("提示", "請先點選您已經買到的願望車輛！")
        added_count = 0
        for item in sorted([int(s) for s in selected], reverse=True): 
            w = self.data["wishlist"][item]
            self.data["vehicles"].append({"name": w["name"], "garage": "未分類", "v_type": "", "acquire": "購買獲得", "price": w["price"], "upgraded": "未改滿", "count": 1, "notes": w["notes"], "locked": False, "pinned": False, "created_at": time.strftime('%Y-%m-%d %H:%M'), "updated_at": time.strftime('%Y-%m-%d %H:%M')})
            del self.data["wishlist"][item]; added_count += 1
        save_data(self.all_data); self.log_action(f"🎉 願望達成：將 {added_count} 台夢想載具成功牽入未分類車庫！"); self.refresh_wishlist_table(); self.refresh_vehicle_tables(); self.refresh_statistics()
        messagebox.showinfo("🎉 恭喜牽新車！", f"成功將 {added_count} 輛車移入正式資產清單。\n它們目前停放在【未分類】車庫！"); self.notebook.select(self.tab_vehicles)

    # ==========================================
    #   ✨ 勾選與防呆功能核心邏輯
    # ==========================================
    def update_checked_button_text(self):
        count = len(self.checked_indices) if hasattr(self, 'checked_indices') else 0
        if hasattr(self, 'btn_batch_edit_v') and self.btn_batch_edit_v.winfo_exists(): self.btn_batch_edit_v.config(text=f"✏️ 修改已勾選 ({count})")
        if hasattr(self, 'edit_menu'):
            try: self.edit_menu.entryconfig(1, label=f"✏️ 修改已勾選 ({count})")
            except: pass

    def on_tree_click(self, event):
        if not self.data: return
        tree = event.widget
        if tree.identify_region(event.x, event.y) != "cell": return
        col_str = tree.identify_column(event.x)
        if not col_str: return
        col_idx = int(col_str.replace("#", "")) - 1
        display_cols = tree.cget("displaycolumns")
        actual_col = tree.cget("columns")[col_idx] if not display_cols or display_cols == "#all" else display_cols[col_idx]
        if actual_col == "check": 
            item_iid = tree.identify_row(event.y)
            if not item_iid: return
            idx = int(item_iid)
            if idx in self.checked_indices: self.checked_indices.remove(idx); tree.set(item_iid, "check", "☐")
            else: self.checked_indices.add(idx); tree.set(item_iid, "check", "☑")
            self.update_checked_button_text()

    def select_all_vehicles(self, event=None):
        if not self.data: return
        target_tree = self.get_active_tree(event); added = 0
        for child in target_tree.get_children():
            idx = int(child)
            if idx not in self.checked_indices: self.checked_indices.add(idx); target_tree.set(child, "check", "☑"); added += 1
        self.update_checked_button_text(); self.set_status(f"☑️ 成功全選目前畫面上的 {added} 筆載具！", "#9b59b6")

    def edit_checked_vehicles(self):
        if not self.data: return
        if not self.checked_indices: return messagebox.showwarning("提示", "您還沒有勾選任何載具！")
        self.open_edit_window(pre_selected=[str(i) for i in self.checked_indices])

    def check_duplicate_vehicles(self):
        if not self.data: return
        name_map = defaultdict(list)
        for idx, v in enumerate(self.data.get("vehicles", [])): name_map[v["name"].strip().lower()].append(idx)
        duplicates = {name: indices for name, indices in name_map.items() if len(indices) > 1}
        if not duplicates:
            messagebox.showinfo("檢查結果", "✅ 太棒了！您的車庫清單中目前沒有任何重複的車輛。"); self.set_status("✅ 檢查完畢：目前車庫清單中無任何重複車輛。", "#4CAF50"); return
        win = tk.Toplevel(self.root); win.title("🔍 發現重複車輛"); self.center_toplevel_window(win, 450, 500); win.configure(bg=COLOR_CARD_BG)
        tk.Label(win, text=f"⚠️ 系統偵測到 {len(duplicates)} 組重複的車輛紀錄：", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#F39C12").pack(pady=(15, 5))
        frame_list = tk.Frame(win, bg=COLOR_MAIN_BG); frame_list.pack(fill="both", expand=True, padx=25, pady=5)
        scrollbar = ttk.Scrollbar(frame_list); scrollbar.pack(side="right", fill="y")
        listbox = tk.Listbox(frame_list, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", yscrollcommand=scrollbar.set, relief="solid", selectbackground="#4CAF50")
        for name, indices in duplicates.items():
            listbox.insert(tk.END, f"▪ {self.data['vehicles'][indices[0]]['name']} (共 {len(indices)} 筆)")
            listbox.insert(tk.END, f"  📍 分佈: {', '.join([self.data['vehicles'][i]['garage'] for i in indices])[:27] + '...'}")
            listbox.insert(tk.END, "") 
        listbox.pack(side="left", fill="both", expand=True); scrollbar.config(command=listbox.yview)
        def do_auto_merge():
            if not messagebox.askyesno("最後確認", "確定要將這些重複紀錄合併嗎？", parent=win): return
            indices_to_delete = []; merged_count = 0
            for name, indices in duplicates.items():
                first_idx = indices[0]; total_extra = 0
                is_pegasus = self.data["vehicles"][first_idx].get("garage") == "帕格薩斯" or self.data["vehicles"][first_idx].get("v_type") == "帕格薩斯"
                for other_idx in indices[1:]:
                    if not is_pegasus: total_extra += int(self.data["vehicles"][other_idx].get("count", 1) or 1)
                    indices_to_delete.append(other_idx); merged_count += 1
                if is_pegasus: self.data["vehicles"][first_idx]["count"] = 1; self.data["vehicles"][first_idx]["upgraded"] = "不可改裝"
                else: self.data["vehicles"][first_idx]["count"] = int(self.data["vehicles"][first_idx].get("count", 1) or 1) + total_extra
                self.data["vehicles"][first_idx]["updated_at"] = time.strftime('%Y-%m-%d %H:%M')
            for idx in sorted(indices_to_delete, reverse=True): del self.data["vehicles"][idx]
            self.checked_indices.clear(); self.update_checked_button_text(); self.sync_special_from_vehicles(); save_data(self.all_data)
            self.refresh_vehicle_tables(); self.refresh_special_table(); self.refresh_garage_table(); self.show_toast_progress(f"✅ 成功合併 {merged_count} 筆重複紀錄"); win.destroy()
        btn_frame = tk.Frame(win, bg=COLOR_CARD_BG); btn_frame.pack(fill="x", padx=25, pady=15)
        ttk.Button(btn_frame, text="✨ 一鍵智能合併", command=do_auto_merge, style="Primary.TButton").pack(side="left", expand=True, fill="x", padx=(0, 5), ipady=4); ttk.Button(btn_frame, text="關閉 (手動處理)", command=win.destroy, style="Secondary.TButton").pack(side="right", expand=True, fill="x", padx=(5, 0), ipady=4)

    # ==========================================
    #     🚗 1. 車輛管理頁面 
    # ==========================================
    def setup_vehicles_tab(self):
        input_frame = tk.LabelFrame(self.tab_vehicles, text=" 📝 登記新載具資產 ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#4CAF50", padx=12, pady=12, bd=2); input_frame.pack(fill="x", padx=15, pady=(5, 10))
        for i in range(7): input_frame.columnconfigure(i, weight=0)
        input_frame.columnconfigure(1, weight=1); input_frame.columnconfigure(3, weight=1); input_frame.columnconfigure(5, weight=1)

        tk.Label(input_frame, text="載具名稱:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=0, sticky="e", pady=5, padx=5)
        self.entry_name = tk.Entry(input_frame, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); self.entry_name.grid(row=0, column=1, sticky="we", padx=5, pady=5); apply_focus_highlight(self.entry_name)

        tk.Label(input_frame, text="存放位置:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=2, sticky="e", pady=5, padx=5)
        self.combo_garage = ttk.Combobox(input_frame, state="readonly", font=FONT_NORMAL); self.combo_garage.grid(row=0, column=3, sticky="we", padx=5, pady=5)

        tk.Label(input_frame, text="取得方式:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=4, sticky="e", pady=5, padx=5)
        self.combo_acquire = ttk.Combobox(input_frame, state="readonly", font=FONT_NORMAL); self.combo_acquire.grid(row=0, column=5, sticky="we", padx=5, pady=5)
        
        tk.Label(input_frame, text="購入價格(GTA$):", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=1, column=0, sticky="e", pady=5, padx=5)
        self.entry_price = tk.Entry(input_frame, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); self.entry_price.grid(row=1, column=1, sticky="we", padx=5, pady=5); apply_focus_highlight(self.entry_price)

        ttk.Button(input_frame, text="➕ 新增登記", command=self.add_vehicle, style="Success.TButton", padding=(20, 4)).grid(row=0, column=6, rowspan=2, sticky="ns", padx=(15, 5), pady=5)

        self.entry_name.bind("<Return>", lambda e: self.combo_garage.focus()); self.combo_garage.bind("<Return>", lambda e: self.combo_acquire.focus()); self.combo_acquire.bind("<Return>", lambda e: self.entry_price.focus()); self.entry_price.bind("<Return>", lambda e: self.add_vehicle())

        action_frame = tk.Frame(self.tab_vehicles, bg=COLOR_MAIN_BG); action_frame.pack(fill="x", padx=15, pady=5)
        tk.Label(action_frame, text="🔍 全域搜尋:", bg=COLOR_MAIN_BG, fg="white", font=FONT_NORMAL).pack(side="left")
        self.entry_search = tk.Entry(action_frame, width=20, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); self.entry_search.pack(side="left", padx=5); self.entry_search.bind("<KeyRelease>", lambda e: self.apply_filters()); apply_focus_highlight(self.entry_search) 
        
        tk.Label(action_frame, text="  |  篩選車庫位置:", bg=COLOR_MAIN_BG, fg="white", font=FONT_NORMAL).pack(side="left", padx=5)
        self.combo_garage_filter = ttk.Combobox(action_frame, width=20, state="readonly", font=FONT_NORMAL); self.combo_garage_filter.pack(side="left", padx=5); self.combo_garage_filter.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())
        ttk.Button(action_frame, text="重置", command=self.reset_filters, style="Secondary.TButton").pack(side="left", padx=6); ttk.Button(action_frame, text="👁️ 欄位設定", command=self.open_column_selector, style="Dark.TButton").pack(side="left", padx=6)

        tree_frame = tk.Frame(self.tab_vehicles, bg=COLOR_MAIN_BG); tree_frame.pack(fill="both", expand=True, padx=15, pady=10)
        self.tree_vehicles = ttk.Treeview(tree_frame, columns=("check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"), show="headings", selectmode="extended")
        
        for col, text in {"check": "☑", "name": "車輛名稱", "garage": "存放位置", "vtype": "類型", "acquire": "取得方式", "price":"價值(GTA$)", "upgrade": "改裝", "count": "數量", "notes": "備註"}.items(): self.tree_vehicles.heading(col, text=text, command=lambda c=col: self.sort_treeview(self.tree_vehicles, c, False))
        
        self.tree_vehicles.column("check", width=60, anchor="center", stretch=False); self.tree_vehicles.column("name", width=180, anchor="w", stretch=True); self.tree_vehicles.column("garage", width=140, anchor="center", stretch=True); self.tree_vehicles.column("vtype", width=90, anchor="center", stretch=False); self.tree_vehicles.column("acquire", width=100, anchor="center", stretch=False); self.tree_vehicles.column("price", width=110, anchor="center", stretch=False); self.tree_vehicles.column("upgrade", width=80, anchor="center", stretch=False); self.tree_vehicles.column("count", width=50, anchor="center", stretch=False); self.tree_vehicles.column("notes", width=120, anchor="w", stretch=True)
        
        self.tree_vehicles.bind("<ButtonRelease-1>", self.on_tree_click); self.tree_vehicles.bind("<Control-a>", self.select_all_vehicles); self.tree_vehicles.bind("<Control-A>", self.select_all_vehicles)
        self.tree_vehicles.bind("<Double-1>", self.open_edit_window); self.tree_vehicles.bind("<Return>", self.open_edit_window); self.tree_vehicles.bind("<Delete>", self.delete_vehicle); self.tree_vehicles.bind("<Motion>", self.on_vehicle_hover); self.tree_vehicles.bind("<Leave>", lambda e: self.set_status("💡 系統就緒。", "#FF9800"))
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_vehicles.yview); self.tree_vehicles.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y"); self.tree_vehicles.pack(side="left", fill="both", expand=True)
        self.vehicle_popup_menu = tk.Menu(self.root, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL); self.tree_vehicles.bind("<Button-3>", self.show_vehicle_context_menu)

    # ==========================================
    #     🚜 1.5 非個人載具頁面
    # ==========================================
    def setup_non_personal_tab(self):
        header_frame = tk.Frame(self.tab_non_personal, bg=COLOR_MAIN_BG); header_frame.pack(fill="x", padx=15, pady=15)
        tk.Label(header_frame, text="🚜 非個人載具與帕格薩斯列表", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#FF9800").pack(side="left"); tk.Label(header_frame, text=" (請統一在「車輛管理」面板新增)", font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg=COLOR_TEXT_GRAY).pack(side="left")
        ttk.Button(header_frame, text="👁️ 欄位設定", command=self.open_column_selector, style="Dark.TButton").pack(side="right", padx=3)
        tree_frame = tk.Frame(self.tab_non_personal, bg=COLOR_MAIN_BG); tree_frame.pack(fill="both", expand=True, padx=15, pady=5)
        self.tree_non_personal = ttk.Treeview(tree_frame, columns=("check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"), show="headings", selectmode="extended")
        for col, text in {"check": "☑", "name": "車輛名稱", "garage": "存放位置", "vtype": "類型", "acquire": "取得方式", "price":"價值(GTA$)", "upgrade": "改裝", "count": "數量", "notes": "備註"}.items(): self.tree_non_personal.heading(col, text=text, command=lambda c=col: self.sort_treeview(self.tree_non_personal, c, False))
        self.tree_non_personal.column("check", width=60, anchor="center", stretch=False); self.tree_non_personal.column("name", width=180, anchor="w", stretch=True); self.tree_non_personal.column("garage", width=140, anchor="center", stretch=True); self.tree_non_personal.column("vtype", width=90, anchor="center", stretch=False); self.tree_non_personal.column("acquire", width=100, anchor="center", stretch=False); self.tree_non_personal.column("price", width=110, anchor="center", stretch=False); self.tree_non_personal.column("upgrade", width=80, anchor="center", stretch=False); self.tree_non_personal.column("count", width=50, anchor="center", stretch=False); self.tree_non_personal.column("notes", width=120, anchor="w", stretch=True)
        self.tree_non_personal.bind("<ButtonRelease-1>", self.on_tree_click); self.tree_non_personal.bind("<Control-a>", self.select_all_vehicles); self.tree_non_personal.bind("<Double-1>", self.open_edit_window); self.tree_non_personal.bind("<Return>", self.open_edit_window); self.tree_non_personal.bind("<Delete>", self.delete_vehicle); self.tree_non_personal.bind("<Button-3>", self.show_vehicle_context_menu); self.tree_non_personal.bind("<Motion>", self.on_vehicle_hover); self.tree_non_personal.bind("<Leave>", lambda e: self.set_status("💡 系統就緒。", "#FF9800"))
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_non_personal.yview); self.tree_non_personal.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y"); self.tree_non_personal.pack(side="left", fill="both", expand=True)

    def update_garage_comboboxes(self):
        if not self.data: return
        spec_carriers = [sv["name"] for sv in self.data.get("special_vehicles", []) if sv.get("can_store", False)]
        user_garages = [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]
        combined_list = ["未分類", "帕格薩斯"] + user_garages + spec_carriers
        self.combo_garage["values"] = combined_list; self.combo_garage_filter["values"] = ["全部"] + combined_list
        if self.combo_garage_filter.get() == "": self.combo_garage_filter.set("全部")
        if hasattr(self, 'combo_spec_location'):
            self.combo_spec_location["values"] = ["未分類"] + user_garages
            if not self.combo_spec_location.get(): self.combo_spec_location.set("未分類")

    def count_cars_in_garage(self, garage_name):
        return sum(c.get("count", 1) for c in self.data["vehicles"] if c["garage"] == garage_name) if self.data else 0

    def refresh_vehicle_tables(self, search_results=None):
        if not self.data: return
        data_to_sort = search_results if search_results is not None else enumerate(self.data["vehicles"])
        pinned_items = []; normal_items = []
        for idx, car in data_to_sort:
            if car.get("pinned", False): pinned_items.append((idx, car))
            else: normal_items.append((idx, car))
        existing_main = set(self.tree_vehicles.get_children()); existing_np = set(self.tree_non_personal.get_children()) if hasattr(self, 'tree_non_personal') else set()
        new_main = set(); new_np = set()
        today_str = time.strftime('%Y-%m-%d')
        for idx, car in pinned_items + normal_items:
            iid = str(idx); display_name = ("🆕 " if car.get("created_at", "").startswith(today_str) else "") + car["name"]
            if car.get("locked", False): display_name = "🔒 " + display_name
            if car.get("pinned", False): display_name = "📌 " + display_name
            values = ("☑" if idx in getattr(self, 'checked_indices', set()) else "☐", display_name, car["garage"], car.get("v_type", ""), car.get("acquire", ""), f"$ {int(car.get('price', 0)):,}" if car.get("price") else "$ 0", car.get("upgraded", ""), car.get("count", 1), car.get("notes", ""))
            is_np = car.get("v_type", "") in ["非個人載具", "帕格薩斯"]
            target_tree = self.tree_non_personal if is_np and hasattr(self, 'tree_non_personal') else self.tree_vehicles
            target_set = new_np if is_np else new_main; target_set.add(iid)
            if iid in (existing_np if is_np else existing_main): target_tree.item(iid, values=values)
            else: target_tree.insert("", "end", iid=iid, values=values)
        for iid in existing_main - new_main: self.tree_vehicles.delete(iid)
        if hasattr(self, 'tree_non_personal'):
            for iid in existing_np - new_np: self.tree_non_personal.delete(iid)

    def add_vehicle(self):
        if not self.data: return
        name = self.entry_name.get().strip(); garage = self.combo_garage.get().strip() or "未分類"
        if not name: return
        vtype = ""; upgraded = ""; count = 1
        try: price = int(self.entry_price.get().strip() or 0)
        except: price = 0
        disable_limits = self.data.get("app_settings", {}).get("disable_all_limits", False)
        
        if garage == "帕格薩斯": vtype = "帕格薩斯"; upgraded = "不可改裝"; count = 1
        
        existing_idx = next((i for i, v in enumerate(self.data["vehicles"]) if v["name"].lower() == name.lower()), None)
        if existing_idx is not None:
            choice = messagebox.askyesnocancel("發現重複車輛", f"系統偵測到資產中已存在名為【{name}】的載具！\n\n• 按「是 (Yes)」：將該現有車輛的數量 +1\n• 按「否 (No)」：強制新增為另一筆獨立紀錄\n• 按「取消 (Cancel)」：放棄本次新增")
            if choice is None: return
            elif choice is True:
                if self.data["vehicles"][existing_idx].get("garage") == "帕格薩斯": return messagebox.showinfo("系統提示", "帕格薩斯載具無法疊加數量！")
                self.data["vehicles"][existing_idx]["count"] = int(self.data["vehicles"][existing_idx].get("count", 1) or 1) + 1
                self.data["vehicles"][existing_idx]["updated_at"] = time.strftime('%Y-%m-%d %H:%M')
                if price > 0 and self.data["vehicles"][existing_idx].get("price", 0) == 0: self.data["vehicles"][existing_idx]["price"] = price 
                self.sync_special_from_vehicles(); save_data(self.all_data); self.refresh_vehicle_tables(); self.refresh_special_table(); self.refresh_garage_table(); self.entry_name.delete(0, tk.END); self.combo_acquire.set(""); self.entry_price.delete(0, tk.END); self.show_toast_progress("🚗 數量合併成功！"); self.entry_name.focus()
                return

        if garage != "未分類" and garage != "帕格薩斯":
            if not self.validate_tab1_vehicle_to_garage(name, garage): return
            lim = self.data["garage_limits"].get(garage, self.data.get("app_settings", {}).get("default_garage_limit", 10))
            if not disable_limits and self.count_cars_in_garage(garage) >= lim: return messagebox.showerror("位置已滿", f"【{garage}】容量已滿！")

        self.data["vehicles"].append({"name": name, "garage": garage, "v_type": vtype, "acquire": self.combo_acquire.get(), "price": price, "upgraded": upgraded, "count": count, "notes": "", "locked": False, "pinned": False, "created_at": time.strftime('%Y-%m-%d %H:%M'), "updated_at": time.strftime('%Y-%m-%d %H:%M')})
        self.sync_special_from_vehicles(); save_data(self.all_data); self.log_action(f"✅ 新增載具：【{name}】 (儲存至：{garage})")
        self.refresh_vehicle_tables(); self.refresh_special_table(); self.refresh_garage_table(); self.refresh_statistics()
        self.entry_name.delete(0, tk.END); self.combo_acquire.set(""); self.entry_price.delete(0, tk.END); self.show_toast_progress("🚗 登記成功！"); self.entry_name.focus()

    def delete_vehicle(self, event=None):
        if not self.data: return
        selected = self.get_active_tree(event).selection()
        if not selected: return
        for item in selected:
            if self.data["vehicles"][int(item)].get("locked", False): return messagebox.showwarning("安全鎖定", "⚠️ 包含鎖定車輛，拒絕刪除！")
        if messagebox.askyesno("確認刪除", f"確定要刪除選定的 【 {len(selected)} 】 筆資料嗎？"):
            for item in sorted([int(s) for s in selected], reverse=True): del self.data["vehicles"][item]
            self.checked_indices.clear(); self.update_checked_button_text(); self.sync_special_from_vehicles(); save_data(self.all_data); self.apply_filters(); self.refresh_special_table(); self.refresh_garage_table(); self.refresh_statistics(); self.set_status(f"🗑️ 成功刪除 {len(selected)} 筆載具。", "#FF9800")

    def toggle_pin_vehicle(self, event=None):
        if not self.data: return
        target_tree = self.get_active_tree(event); selected = target_tree.selection()
        if not selected: return
        new_state = not self.data["vehicles"][int(selected[0])].get("pinned", False)
        for item in selected: self.data["vehicles"][int(item)]["pinned"] = new_state
        save_data(self.all_data); self.apply_filters()

    def toggle_lock_vehicle(self, event=None):
        if not self.data: return
        target_tree = self.get_active_tree(event); selected = target_tree.selection()
        if not selected: return
        new_state = not self.data["vehicles"][int(selected[0])].get("locked", False)
        for item in selected: self.data["vehicles"][int(item)]["locked"] = new_state
        save_data(self.all_data); self.apply_filters()

    def apply_filters(self):
        if not self.data: return
        kw = self.entry_search.get().lower(); selected_garage = self.combo_garage_filter.get()
        filtered = [(i, c) for i, c in enumerate(self.data["vehicles"]) if (kw in c["name"].lower() or kw in c["garage"].lower()) and (selected_garage in ["全部", ""] or c["garage"] == selected_garage)]
        self.refresh_vehicle_tables(search_results=filtered)

    def reset_filters(self):
        if not self.data: return
        self.entry_search.delete(0, tk.END); self.combo_garage_filter.set("全部"); self.checked_indices.clear(); self.update_checked_button_text(); self.refresh_vehicle_tables()

    def show_vehicle_context_menu(self, event):
        if not self.data: return
        target_tree = self.get_active_tree(event); item = target_tree.identify_row(event.y)
        if item: 
            if item not in target_tree.selection(): target_tree.selection_set(item)
            self.vehicle_popup_menu.delete(0, tk.END); self.vehicle_popup_menu.add_command(label=f"✏️ 編輯資產", command=lambda: self.open_edit_window(event)); self.vehicle_popup_menu.add_separator(); self.vehicle_popup_menu.add_command(label="📌 置頂/取消置頂", command=lambda: self.toggle_pin_vehicle(event)); self.vehicle_popup_menu.add_command(label="🔒 檔案鎖定/解鎖", command=lambda: self.toggle_lock_vehicle(event)); self.vehicle_popup_menu.add_separator(); self.vehicle_popup_menu.add_command(label=f"🗑️ 刪除資產", command=lambda: self.delete_vehicle(event)); self.vehicle_popup_menu.post(event.x_root, event.y_root)

    def open_batch_import_window(self):
        if not self.data: return
        win = tk.Toplevel(self.root); win.title("📦 批量登入"); self.center_toplevel_window(win, 540, 520)
        tk.Label(win, text="請在此貼上車輛資料（一行一筆，逗號分隔）", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#2196F3").pack(pady=8)
        text_area = tk.Text(win, height=13, width=52, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", relief="solid"); text_area.pack(pady=10, padx=15)
        def process_import():
            content = text_area.get("1.0", tk.END).strip(); added = 0
            for line in content.split('\n'):
                if not line.strip(): continue
                parts = line.split(','); name = parts[0].strip(); garage = parts[1].strip() if len(parts) > 1 else "未分類"
                self.data["vehicles"].append({"name": name, "garage": garage, "v_type": "", "acquire": "", "price": 0, "upgraded": "", "count": 1, "notes": "", "locked": False, "pinned": False, "created_at": time.strftime('%Y-%m-%d %H:%M'), "updated_at": time.strftime('%Y-%m-%d %H:%M')}); added += 1
            self.sync_special_from_vehicles(); save_data(self.all_data); self.refresh_vehicle_tables(); win.destroy(); self.refresh_garage_table(); self.refresh_statistics(); self.show_toast_progress(f"📦 批量登入完成")
        ttk.Button(win, text="確認執行批量登入", command=process_import, style="Primary.TButton").pack(fill="x", padx=40, pady=15, ipady=4)

    def open_edit_window(self, event=None, pre_selected=None):
        if not self.data: return
        selected = pre_selected if pre_selected is not None else self.get_active_tree(event).selection()
        if not selected: return messagebox.showwarning("操作提示", "請先選取您要修改的載具！")
        for item in selected:
            if self.data["vehicles"][int(item)].get("locked", False): return messagebox.showwarning("鎖定限制", "⚠️ 資料已鎖定！")
        
        combined_locations = ["未分類", "帕格薩斯"] + [g for g in self.data["garages"] if g != "未分類" and g != "帕格薩斯"] + [sv["name"] for sv in self.data.get("special_vehicles", []) if sv.get("can_store", False)]
        
        if len(selected) == 1:
            idx = int(selected[0]); car = self.data["vehicles"][idx]
            win = tk.Toplevel(self.root); win.title("編輯載具資產"); self.center_toplevel_window(win, 350, 580) 
            
            tk.Label(win, text="載具資產名稱:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(12,2))
            ent_name = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=22); ent_name.insert(0, car['name']); ent_name.pack(); ent_name.focus()
            
            combo_edit_garage = ttk.Combobox(win, state="readonly", values=combined_locations, font=FONT_NORMAL)
            combo_edit_vtype = ttk.Combobox(win, state="readonly", values=V_TYPE_OPTIONS, font=FONT_NORMAL)
            combo_edit_acquire = ttk.Combobox(win, state="readonly", values=self.data.get("acquire_options", ACQUIRE_OPTIONS), font=FONT_NORMAL)
            combo_edit_upgrade = ttk.Combobox(win, state="readonly", values=["未改滿", "已改滿", "不可改裝"], font=FONT_NORMAL)
            ent_price = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=22)
            ent_count = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=22)
            ent_notes = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=22)
            
            tk.Label(win, text="存放位置:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(6,2)); combo_edit_garage.set(car.get('garage', '未分類')); combo_edit_garage.pack()
            tk.Label(win, text="載具類型:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(6,2)); combo_edit_vtype.set(car.get('v_type', '')); combo_edit_vtype.pack()
            tk.Label(win, text="取得方式:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(6,2)); combo_edit_acquire.set(car.get('acquire', '')); combo_edit_acquire.pack()
            tk.Label(win, text="購入價格(GTA$):", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(6,2)); ent_price.insert(0, str(car.get('price', 0))); ent_price.pack()
            tk.Label(win, text="改裝狀態:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(6,2)); combo_edit_upgrade.set(car.get('upgraded', '')); combo_edit_upgrade.pack()
            tk.Label(win, text="資產數量:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(6,2)); ent_count.insert(0, str(car.get('count', 1))); ent_count.pack()
            tk.Label(win, text="自訂備註:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(6,2)); ent_notes.insert(0, car.get('notes', '')); ent_notes.pack()

            def save_single(e=None):
                try: p_val = int(ent_price.get() or 0)
                except: p_val = 0
                try: c_val = int(ent_count.get() or 1)
                except: c_val = 1
                car.update({'name': ent_name.get(), 'garage': combo_edit_garage.get(), 'v_type': combo_edit_vtype.get(), 'acquire': combo_edit_acquire.get(), 'price': p_val, 'upgraded': combo_edit_upgrade.get(), 'count': c_val, 'notes': ent_notes.get(), 'updated_at': time.strftime('%Y-%m-%d %H:%M')})
                self.sync_special_from_vehicles(); save_data(self.all_data)
                if pre_selected is not None: self.checked_indices.clear(); self.update_checked_button_text()
                self.refresh_vehicle_tables(); self.refresh_garage_table(); self.refresh_special_table(); self.refresh_statistics(); win.destroy(); self.show_toast_progress("✅ 修改成功！")
            
            def delete_action():
                if messagebox.askyesno("確認刪除", f"確定要刪除選定的 【 1 】 筆資料嗎？", parent=win):
                    del self.data["vehicles"][idx]; self.checked_indices.discard(idx); self.update_checked_button_text(); self.sync_special_from_vehicles(); save_data(self.all_data)
                    self.refresh_vehicle_tables(); self.refresh_garage_table(); self.refresh_special_table(); win.destroy()
            
            btn_frame = tk.Frame(win, bg=COLOR_MAIN_BG); btn_frame.pack(fill="x", padx=35, pady=15)
            ttk.Button(btn_frame, text="儲存變更", command=save_single, style="Success.TButton").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=4); ttk.Button(btn_frame, text="🗑️ 刪除", command=delete_action, style="Danger.TButton").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4)
        else:
            win = tk.Toplevel(self.root); win.title("批量修改已勾選資產"); self.center_toplevel_window(win, 380, 620) 
            tk.Label(win, text=f"👁️ 您目前共勾選了 {len(selected)} 筆載具：", fg="#e91e63", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG).pack(pady=(10, 5))
            tk.Label(win, text="1. 批量移動存放位置:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack()
            combo_batch_garage = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]"] + combined_locations); combo_batch_garage.set("[不修改]"); combo_batch_garage.pack(pady=3)
            tk.Label(win, text="2. 批量更改載具類型:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack()
            combo_batch_vtype = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]"] + V_TYPE_OPTIONS); combo_batch_vtype.set("[不修改]"); combo_batch_vtype.pack(pady=3)
            tk.Label(win, text="3. 批量更改改裝狀態:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack()
            combo_batch_upg = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]", "未改滿", "已改滿", "不可改裝"]); combo_batch_upg.set("[不修改]"); combo_batch_upg.pack(pady=3)
            def save_batch():
                current_time = time.strftime('%Y-%m-%d %H:%M')
                for item in selected:
                    idx = int(item)
                    if combo_batch_garage.get() != "[不修改]": self.data["vehicles"][idx]['garage'] = combo_batch_garage.get()
                    if combo_batch_vtype.get() != "[不修改]": self.data["vehicles"][idx]['v_type'] = combo_batch_vtype.get()
                    if combo_batch_upg.get() != "[不修改]": self.data["vehicles"][idx]['upgraded'] = combo_batch_upg.get()
                    self.data["vehicles"][idx]['updated_at'] = current_time
                self.sync_special_from_vehicles(); save_data(self.all_data)
                if pre_selected is not None: self.checked_indices.clear(); self.update_checked_button_text()
                self.refresh_vehicle_tables(); self.refresh_garage_table(); self.refresh_special_table(); win.destroy(); self.show_toast_progress("✅ 批量更新完畢")
            ttk.Button(win, text="執行批量變更", command=save_batch, style="Primary.TButton").pack(fill="x", padx=35, pady=25, ipady=4)

    # ==========================================
    #     🚁 2. 特殊載具分頁
    # ==========================================
    def setup_special_tab(self):
        input_frame = tk.LabelFrame(self.tab_special, text=" 🚁 登記大型特種特殊載具 ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#e91e63", padx=12, pady=12, bd=2); input_frame.pack(fill="x", padx=15, pady=10)
        tk.Label(input_frame, text="載具名稱:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=0, column=0, pady=5, padx=5, sticky="e")
        self.combo_spec_name = ttk.Combobox(input_frame, state="normal", font=FONT_NORMAL, values=list(SUB_CARRIER_RULES.keys()) + ["機動作戰中心", "復仇者"]); self.combo_spec_name.grid(row=0, column=1, pady=5, padx=5, sticky="we"); self.combo_spec_name.bind("<KeyRelease>", self.on_main_spec_carrier_changed); self.combo_spec_name.bind("<<ComboboxSelected>>", self.on_main_spec_carrier_changed)
        tk.Label(input_frame, text="停放位置:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=0, column=2, pady=5, padx=5, sticky="e")
        self.combo_spec_location = ttk.Combobox(input_frame, state="readonly", font=FONT_NORMAL); self.combo_spec_location.grid(row=0, column=3, pady=5, padx=5, sticky="we")
        ttk.Button(input_frame, text="➕ 建立特殊載具", command=self.add_special, style="Pink.TButton", padding=(10, 4)).grid(row=0, column=4, rowspan=2, padx=15, pady=5, sticky="ns")
        self.var_can_store = tk.BooleanVar(value=False)
        self.chk_can_store = tk.Checkbutton(input_frame, text="啟用車庫(可放車)", variable=self.var_can_store, bg=COLOR_CARD_BG, fg="white", selectcolor="#757575", font=FONT_BOLD); self.chk_can_store.grid(row=1, column=0, columnspan=2, pady=5, padx=5, sticky="w")
        tk.Label(input_frame, text="內部專屬車輛:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=1, column=2, pady=5, padx=5, sticky="e")
        self.combo_inner_car = ttk.Combobox(input_frame, state="disabled", font=FONT_NORMAL, values=[""]); self.combo_inner_car.grid(row=1, column=3, pady=5, padx=5, sticky="we")
        
        tree_frame = tk.Frame(self.tab_special, bg=COLOR_MAIN_BG); tree_frame.pack(fill="both", expand=True, padx=15, pady=10)
        self.tree_special = ttk.Treeview(tree_frame, columns=("name", "location", "inner"), show="headings", selectmode="extended")
        for col, text in {"name": "特殊載具名稱", "location": "停放物業/位置", "inner": "內部停放/綁定車輛"}.items(): self.tree_special.heading(col, text=text, command=lambda c=col: self.sort_treeview(self.tree_special, c, False))
        self.tree_special.column("name", width=200, stretch=True); self.tree_special.column("location", width=200, stretch=True); self.tree_special.column("inner", width=300, stretch=True); self.tree_special.pack(side="left", fill="both", expand=True)
        self.tree_special.bind("<Double-1>", self.open_special_edit_window); self.tree_special.bind("<Delete>", self.delete_special)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_special.yview); self.tree_special.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y")
        self.special_popup_menu = tk.Menu(self.root, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL); self.tree_special.bind("<Button-3>", self.show_special_context_menu)

    def on_main_spec_carrier_changed(self, event=None):
        carrier = self.combo_spec_name.get().strip()
        if carrier in SUB_CARRIER_RULES:
            self.var_can_store.set(True); self.chk_can_store.config(state="disabled"); self.combo_inner_car.config(state="readonly"); self.combo_inner_car["values"] = [""] + SUB_CARRIER_RULES[carrier] 
        else: self.chk_can_store.config(state="normal"); self.combo_inner_car.set(""); self.combo_inner_car.config(state="disabled") 

    def add_special(self):
        if not self.data: return
        name = self.combo_spec_name.get().strip(); location = self.combo_spec_location.get().strip() or "未分類" ; inner_car = self.combo_inner_car.get().strip()
        if not name: return
        self.data["special_vehicles"].append({"name": name, "location": location, "inner_vehicle": inner_car if inner_car != "無" else "", "can_store": self.var_can_store.get(), "locked": False, "pinned": False, "updated_at": time.strftime("%Y-%m-%d %H:%M")}) 
        self.sync_vehicles_from_special(); save_data(self.all_data); self.refresh_special_table(); self.update_garage_comboboxes(); self.refresh_vehicle_tables() 
        self.combo_spec_name.set(""); self.combo_inner_car.set(""); self.var_can_store.set(False); self.on_main_spec_carrier_changed(); self.combo_spec_location.set("未分類"); self.show_toast_progress("🚁 特殊載具建立成功！")

    def refresh_special_table(self):
        for i in self.tree_special.get_children(): self.tree_special.delete(i)
        if not self.data: return
        for idx, item in enumerate(self.data.get("special_vehicles", [])):
            display_name = ("🔒 " if item.get("locked") else "") + ("📌 " if item.get("pinned") else "") + item["name"]
            self.tree_special.insert("", "end", iid=str(idx), values=(display_name, item.get("location", "未分類"), item.get("inner_vehicle", "") or "")) 

    def toggle_pin_special(self):
        if not self.data or not self.tree_special.selection(): return
        new_state = not self.data["special_vehicles"][int(self.tree_special.selection()[0])].get("pinned", False)
        for item in self.tree_special.selection(): self.data["special_vehicles"][int(item)]["pinned"] = new_state
        save_data(self.all_data); self.refresh_special_table()

    def toggle_lock_special(self):
        if not self.data or not self.tree_special.selection(): return
        new_state = not self.data["special_vehicles"][int(self.tree_special.selection()[0])].get("locked", False)
        for item in self.tree_special.selection(): self.data["special_vehicles"][int(item)]["locked"] = new_state
        save_data(self.all_data); self.refresh_special_table()

    def show_special_context_menu(self, event):
        item = self.tree_special.identify_row(event.y)
        if item:
            if item not in self.tree_special.selection(): self.tree_special.selection_set(item)
            self.special_popup_menu.delete(0, tk.END); self.special_popup_menu.add_command(label="✏️ 編輯特種載具", command=self.open_special_edit_window); self.special_popup_menu.add_separator(); self.special_popup_menu.add_command(label="📌 置頂/取消置頂", command=self.toggle_pin_special); self.special_popup_menu.add_command(label="🔒 屬性鎖定/解鎖", command=self.toggle_lock_special); self.special_popup_menu.add_separator(); self.special_popup_menu.add_command(label="🗑️ 報廢刪除", command=self.delete_special)
            self.special_popup_menu.post(event.x_root, event.y_root)

    def delete_special(self, event=None):
        selected = self.tree_special.selection()
        if not selected: return
        if messagebox.askyesno("確認刪除", "確定報廢此特殊載具？"):
            for item in sorted([int(s) for s in selected], reverse=True): 
                old_name = self.data["special_vehicles"][item]["name"]; del self.data["special_vehicles"][item]
                if old_name in self.data["garage_limits"]: del self.data["garage_limits"][old_name] 
                for v in self.data["vehicles"]:
                    if v.get("garage") == old_name: v["garage"] = "未分類"
            save_data(self.all_data); self.refresh_special_table(); self.update_garage_comboboxes(); self.apply_filters()

    def open_special_edit_window(self, event=None):
        selected = self.tree_special.selection()
        if not selected or len(selected) > 1: return 
        idx = int(selected[0]); sv = self.data["special_vehicles"][idx]
        win = tk.Toplevel(self.root); win.title("修改特種載具"); self.center_toplevel_window(win, 350, 420) 
        tk.Label(win, text="特種載具名稱:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(12,2))
        combo_name = ttk.Combobox(win, state="normal", font=FONT_NORMAL, values=list(SUB_CARRIER_RULES.keys()) + ["機動作戰中心", "復仇者"]); combo_name.set(sv["name"]); combo_name.pack()
        tk.Label(win, text="停放位置:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(5,2))
        combo_spec_loc = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["未分類"] + [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]); combo_spec_loc.set(sv.get("location", "未分類")); combo_spec_loc.pack()
        edit_var_can_store = tk.BooleanVar(value=sv.get("can_store", False)); tk.Checkbutton(win, text="設為車庫", variable=edit_var_can_store, bg=COLOR_MAIN_BG, fg="white", selectcolor="#757575", font=FONT_BOLD).pack(pady=4)
        def save(e=None):
            new_name = combo_name.get().strip()
            if new_name != sv["name"]:
                for v in self.data["vehicles"]:
                    if v.get("garage") == sv["name"]: v["garage"] = new_name
            self.data["special_vehicles"][idx].update({"name": new_name, "location": combo_spec_loc.get().strip() or "未分類", "can_store": edit_var_can_store.get(), "updated_at": time.strftime("%Y-%m-%d %H:%M")}) 
            self.sync_vehicles_from_special(); save_data(self.all_data); self.refresh_vehicle_tables(); self.update_garage_comboboxes(); self.refresh_special_table(); win.destroy()
        ttk.Button(win, text="保存變更", command=save, style="Success.TButton").pack(fill="x", padx=35, pady=15, ipady=4)

    # ==========================================
    #     🏠 3. 車庫管理頁面 (終極遊戲化互動選單版)
    # ==========================================
    def setup_garages_tab(self):
        self.expanded_bases = set()  
        self.garage_paned = tk.PanedWindow(self.tab_garages, orient="horizontal", bg=COLOR_MAIN_BG, bd=0, sashwidth=4)
        self.garage_paned.pack(fill="both", expand=True, padx=15, pady=10)

        # === 左側：GTAV 風格互動選單 ===
        self.gta_menu_frame = tk.Frame(self.garage_paned, bg="#000000", width=380)
        self.gta_menu_frame.pack_propagate(False)
        self.garage_paned.add(self.gta_menu_frame, minsize=380)

        header = tk.Frame(self.gta_menu_frame, bg="#000000", pady=12, padx=15)
        header.pack(fill="x")
        tk.Label(header, text="選擇車庫", bg="#000000", fg="white", font=("Microsoft JhengHei", 16, "bold")).pack(side="left")
        self.lbl_menu_count = tk.Label(header, text="1 / 1", bg="#000000", fg="white", font=("Microsoft JhengHei", 14, "bold"))
        self.lbl_menu_count.pack(side="right")

        self.menu_listbox = tk.Listbox(self.gta_menu_frame, bg="#1a1a1a", fg="white", 
                                       selectmode="extended",
                                       selectbackground="#ffffff", selectforeground="#000000",
                                       font=("Microsoft JhengHei", 13, "bold"), borderwidth=0, highlightthickness=0, activestyle='none')
        self.menu_listbox.pack(fill="both", expand=True, pady=(0, 2))
        
        self.menu_listbox.bind("<<ListboxSelect>>", self.on_garage_menu_select)
        self.menu_listbox.bind("<Double-1>", self.on_garage_menu_double_click)
        self.menu_listbox.bind("<Return>", self.on_garage_menu_double_click)
        self.menu_listbox.bind("<Button-3>", self.show_garage_menu_context)

        # 底部排序按鈕區
        footer = tk.Frame(self.gta_menu_frame, bg="#000000", pady=8)
        footer.pack(fill="x", side="bottom")
        ttk.Button(footer, text="⬆️ 上移", command=self.move_left_menu_up, style="Dark.TButton").pack(side="left", fill="x", expand=True, padx=(15, 5))
        ttk.Button(footer, text="⬇️ 下移", command=self.move_left_menu_down, style="Dark.TButton").pack(side="right", fill="x", expand=True, padx=(5, 15))
        
        footer_desc = tk.Frame(self.gta_menu_frame, bg="#111111", pady=8, padx=15)
        footer_desc.pack(fill="x", side="bottom")
        tk.Label(footer_desc, text="點選查看內容，【右鍵】可管理/刪除，支援 Ctrl 多選。", bg="#111111", fg="white", font=("Microsoft JhengHei", 10)).pack(side="left")

        # === 右側：車庫詳細資訊與管理面板 ===
        self.garage_details_frame = tk.Frame(self.garage_paned, bg=COLOR_MAIN_BG)
        self.garage_paned.add(self.garage_details_frame)

    def refresh_garage_table(self):
        if not hasattr(self, 'menu_listbox'): return
        
        old_sel = self.menu_listbox.curselection()
        sel_idx = old_sel[0] if old_sel else 0
        
        self.menu_listbox.delete(0, tk.END)
        self.menu_items_data = []

        if not self.data: return

        actual_garages = [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]
        
        self.menu_items_data.append({"type": "add", "name": "➕ 購買新物業 (進階管理)", "display": "➕ 購買新物業 (進階管理)"})
        self.menu_listbox.insert(tk.END, "  ➕ 購買新物業 (進階管理)")

        groups = defaultdict(list)
        ordered_bases = []
        for g in actual_garages:
            base_name = g.split(" - ", 1)[0]
            groups[base_name].append(g)
            if base_name not in ordered_bases: ordered_bases.append(base_name)

        for base in ordered_bases:
            g_list = groups[base]
            
            if len(g_list) == 1 and g_list[0] == base:
                self.menu_items_data.append({"type": "single", "name": base, "display": base})
                self.menu_listbox.insert(tk.END, f"  {base}")
            else:
                is_expanded = base in self.expanded_bases
                icon = "▼" if is_expanded else "▶"
                display_text = f"{icon} {base}"
                self.menu_items_data.append({"type": "base", "name": base, "display": display_text})
                self.menu_listbox.insert(tk.END, f"  {display_text}")

                if is_expanded:
                    for g in g_list:
                        sub_name = g.split(" - ", 1)[1] if " - " in g else "主物業樓層"
                        display_sub = f"      {sub_name}"
                        self.menu_items_data.append({"type": "sub", "name": g, "base": base, "display": display_sub})
                        self.menu_listbox.insert(tk.END, display_sub)

        total_items = len(self.menu_items_data)
        if sel_idx >= total_items: sel_idx = max(0, total_items - 1)
        
        if total_items > 0:
            if getattr(self, "skip_refresh_select", False):
                return
            self.menu_listbox.selection_clear(0, tk.END)
            self.menu_listbox.selection_set(sel_idx)
            self.menu_listbox.see(sel_idx)
            self.lbl_menu_count.config(text=f"{sel_idx + 1} / {total_items}")
            self.render_garage_details(self.menu_items_data[sel_idx])

    def on_garage_menu_select(self, event=None):
        sel = self.menu_listbox.curselection()
        if not sel: return
        
        if len(sel) > 1:
            self.lbl_menu_count.config(text=f"多選 ({len(sel)})")
            self.render_multi_garage_details(sel)
        else:
            idx = sel[0]
            total_items = len(self.menu_items_data)
            self.lbl_menu_count.config(text=f"{idx + 1} / {total_items}")
            self.render_garage_details(self.menu_items_data[idx])

    def on_garage_menu_double_click(self, event=None):
        sel = self.menu_listbox.curselection()
        if not sel or len(sel) > 1: return
        idx = sel[0]
        item = self.menu_items_data[idx]
        
        if item["type"] == "base":
            base_name = item["name"]
            if base_name in self.expanded_bases:
                self.expanded_bases.remove(base_name)
            else:
                self.expanded_bases.add(base_name)
            self.refresh_garage_table()
            
            for i, d in enumerate(self.menu_items_data):
                if d["name"] == base_name and d["type"] == "base":
                    self.menu_listbox.selection_set(i)
                    self.menu_listbox.see(i)
                    self.render_garage_details(d)
                    break

    def render_multi_garage_details(self, sel_indices):
        for widget in self.garage_details_frame.winfo_children(): widget.destroy()
        
        items = [self.menu_items_data[i] for i in sel_indices if self.menu_items_data[i]["type"] != "add"]
        if not items: return
        
        panel = tk.Frame(self.garage_details_frame, bg=COLOR_MAIN_BG, padx=30, pady=20)
        panel.pack(fill="both", expand=True)
        
        tk.Label(panel, text="📦 批量管理", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#9b59b6").pack(anchor="w", pady=(0, 20))
        
        header = tk.Frame(panel, bg=COLOR_CARD_BG, pady=20, padx=25, bd=1, relief="solid")
        header.pack(fill="x", pady=10)
        tk.Label(header, text=f"已選取 {len(items)} 個車庫項目", font=("Microsoft JhengHei", 18, "bold"), bg=COLOR_CARD_BG, fg="white").pack(side="left")
        
        list_frame = tk.Frame(panel, bg=COLOR_MAIN_BG)
        list_frame.pack(fill="both", expand=True, pady=10)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        display_listbox = tk.Listbox(list_frame, font=("Microsoft JhengHei", 12), bg="#1e1e1e", fg="white", yscrollcommand=scrollbar.set, relief="solid", bd=1)
        display_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=display_listbox.yview)
        
        for item in items:
            display_listbox.insert(tk.END, f" ▪️ {item['display'].strip().replace('▼ ', '').replace('▶ ', '')}")
            
        btn_frame = tk.Frame(panel, bg=COLOR_MAIN_BG)
        btn_frame.pack(fill="x", pady=(15, 0))
        
        ttk.Button(btn_frame, text="🗑️ 批量刪除選取車庫", command=lambda: self.delete_multiple_garages_from_menu(items), style="Danger.TButton").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4)

    def render_garage_details(self, item_data):
        for widget in self.garage_details_frame.winfo_children(): widget.destroy()
        
        if item_data["type"] == "add":
            panel = tk.Frame(self.garage_details_frame, bg=COLOR_MAIN_BG, padx=30, pady=20)
            panel.pack(fill="both", expand=True)
            tk.Label(panel, text="🏠 購買新物業/車庫", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#4CAF50").pack(anchor="w", pady=(0, 20))
            form_frame = tk.Frame(panel, bg=COLOR_CARD_BG, padx=20, pady=20, bd=1, relief="solid")
            form_frame.pack(fill="x", pady=10)
            tk.Label(form_frame, text="主物業名稱 (如: 辦公室、日蝕大樓):", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="white").pack(anchor="w", pady=5)
            self.entry_new_garage = tk.Entry(form_frame, width=28, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid")
            self.entry_new_garage.pack(anchor="w", pady=5); apply_focus_highlight(self.entry_new_garage)
            tk.Label(form_frame, text="附加額外樓層數 (單一車庫請留 1):", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="white").pack(anchor="w", pady=(15, 5))
            floor_row = tk.Frame(form_frame, bg=COLOR_CARD_BG); floor_row.pack(anchor="w", pady=5)
            self.entry_new_garage_floors = tk.Entry(floor_row, width=8, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", justify="center")
            self.entry_new_garage_floors.insert(0, "1"); self.entry_new_garage_floors.pack(side="left"); apply_focus_highlight(self.entry_new_garage_floors)
            self.combo_floor_type = ttk.Combobox(floor_row, width=18, font=FONT_NORMAL, state="readonly", values=["地上 (車庫1, 車庫2...)", "地下 (B1, B2...)"])
            self.combo_floor_type.set("地上 (車庫1, 車庫2...)"); self.combo_floor_type.pack(side="left", padx=10)
            self.entry_new_garage.bind("<Return>", lambda e: self.entry_new_garage_floors.focus())
            self.entry_new_garage_floors.bind("<Return>", lambda e: self.add_garage_simple())
            ttk.Button(form_frame, text="➕ 登記置產新車庫", command=self.add_garage_simple, style="Success.TButton").pack(anchor="w", pady=20, ipadx=10)
            
            ttk.Separator(panel, orient="horizontal").pack(fill="x", pady=25)
            
            tk.Label(panel, text="⚙️ 批量管理工具", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#F39C12").pack(anchor="w", pady=10)
            tools_frame = tk.Frame(panel, bg=COLOR_MAIN_BG)
            tools_frame.pack(fill="x", pady=5)
            ttk.Button(tools_frame, text="📦 批量匯入新增車庫", command=self.open_batch_garage_window, style="Purple.TButton").pack(side="left")

        elif item_data["type"] == "base":
            base_name = item_data["name"]
            g_list = [g for g in self.data["garages"] if g == base_name or g.startswith(base_name + " - ")]
            total_limit = sum(self.data["garage_limits"].get(g, 10) for g in g_list)
            total_usage = sum(self.count_cars_in_garage(g) for g in g_list)
            disable_limits = self.data.get("app_settings", {}).get("disable_all_limits", False)
            limit_display = "∞" if disable_limits else total_limit
            
            panel = tk.Frame(self.garage_details_frame, bg=COLOR_MAIN_BG, padx=30, pady=20)
            panel.pack(fill="both", expand=True)
            tk.Label(panel, text="🏢 物業總覽", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#F39C12").pack(anchor="w", pady=(0, 10))
            header = tk.Frame(panel, bg=COLOR_CARD_BG, pady=25, padx=25, bd=1, relief="solid")
            header.pack(fill="x", pady=10)
            tk.Label(header, text=f"{base_name}", font=("Microsoft JhengHei", 20, "bold"), bg=COLOR_CARD_BG, fg="white").pack(side="left")
            tk.Label(header, text=f"{total_usage} / {limit_display} 輛", font=("Consolas", 20, "bold"), bg=COLOR_CARD_BG, fg="#F39C12").pack(side="right")
            
            btn_frame = tk.Frame(panel, bg=COLOR_MAIN_BG); btn_frame.pack(fill="x", pady=25)
            ttk.Button(btn_frame, text="➕ 擴建新附屬樓層", command=lambda: self.add_sub_floor(base_name), style="Primary.TButton").pack(side="left", padx=(0, 10), ipady=4)
            ttk.Button(btn_frame, text="✏️ 重新命名整棟物業", command=lambda: self.rename_entire_property(base_name), style="Warning.TButton").pack(side="left", padx=10, ipady=4)
            ttk.Button(btn_frame, text="🗑️ 拆除變賣整棟物業", command=lambda: self.delete_entire_property(base_name), style="Danger.TButton").pack(side="right", ipady=4)

        else:
            g_name = item_data["name"]
            limit = self.data["garage_limits"].get(g_name, 10)
            usage = self.count_cars_in_garage(g_name)
            disable_limits = self.data.get("app_settings", {}).get("disable_all_limits", False)
            limit_display = "∞" if disable_limits else limit
            
            panel = tk.Frame(self.garage_details_frame, bg=COLOR_MAIN_BG, padx=20, pady=20)
            panel.pack(fill="both", expand=True)
            
            header = tk.Frame(panel, bg=COLOR_CARD_BG, pady=20, padx=25, bd=1, relief="solid")
            header.pack(fill="x", pady=(0, 15))
            tk.Label(header, text=f"📍 {g_name}", font=("Microsoft JhengHei", 18, "bold"), bg=COLOR_CARD_BG, fg="white").pack(side="left")
            count_fg = "#ff1744" if (not disable_limits and usage >= limit) else "#3498db"
            tk.Label(header, text=f"{usage} / {limit_display} 輛", font=("Consolas", 18, "bold"), bg=COLOR_CARD_BG, fg=count_fg).pack(side="right")
            
            list_frame = tk.Frame(panel, bg=COLOR_MAIN_BG)
            list_frame.pack(fill="both", expand=True, pady=5)
            tk.Label(list_frame, text="💡 提示：按住 Ctrl 鍵可多選，在載具上點擊「右鍵」可移動至其他車庫", font=("Microsoft JhengHei", 10), bg=COLOR_MAIN_BG, fg="#a8e6cf").pack(anchor="w", pady=(0, 5))
            
            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side="right", fill="y")
            car_listbox = tk.Listbox(list_frame, font=("Microsoft JhengHei", 12), bg="#1e1e1e", fg="white", selectmode="extended", selectbackground="#3498db", yscrollcommand=scrollbar.set, relief="solid", bd=1)
            car_listbox.pack(side="left", fill="both", expand=True)
            scrollbar.config(command=car_listbox.yview)
            
            cars_in_garage = [(idx, c) for idx, c in enumerate(self.data.get("vehicles", [])) if c.get("garage") == g_name]
            self.current_garage_car_indices = []
            if not cars_in_garage: 
                car_listbox.insert(tk.END, "  (此車庫目前沒有停放任何載具)")
                car_listbox.config(fg="#888888")
            else:
                for idx, c in cars_in_garage: 
                    vtype_str = f"  [{c.get('v_type', '')}]" if c.get('v_type') else ""
                    car_listbox.insert(tk.END, f"  🚗 {c['name']}{vtype_str}")
                    self.current_garage_car_indices.append(idx)
                    
            def show_car_context_menu(event):
                if not cars_in_garage: return
                idx = car_listbox.nearest(event.y)
                if idx >= 0:
                    if idx not in car_listbox.curselection():
                        car_listbox.selection_clear(0, tk.END); car_listbox.selection_set(idx); car_listbox.activate(idx)
                    sel = car_listbox.curselection()
                    if sel:
                        if not hasattr(self, 'car_popup_menu'): self.car_popup_menu = tk.Menu(self.root, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
                        self.car_popup_menu.delete(0, tk.END)
                        self.car_popup_menu.add_command(label=f"🚚 移動選取的 {len(sel)} 輛載具至...", command=lambda: self.open_move_vehicle_window(g_name, car_listbox))
                        self.car_popup_menu.post(event.x_root, event.y_root)

            car_listbox.bind("<Button-3>", show_car_context_menu)

    # === 左側選單：手動排序邏輯 ===
    def move_left_menu_up(self):
        sel = self.menu_listbox.curselection()
        if not sel or len(sel) > 1: return messagebox.showwarning("提示", "請單選一個項目進行排序！\n(若是主物業，會連同所有附屬樓層一起移動)")
        idx = sel[0]
        item = self.menu_items_data[idx]
        if item["type"] == "add": return

        actual_garages = [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]
        
        if item["type"] == "base":
            base_name = item["name"]
            group_garages = [g for g in actual_garages if g.split(" - ", 1)[0] == base_name]
            first_idx = actual_garages.index(group_garages[0])
            if first_idx == 0: return 
            
            prev_garage = actual_garages[first_idx - 1]
            prev_base = prev_garage.split(" - ", 1)[0]
            prev_group = [g for g in actual_garages if g.split(" - ", 1)[0] == prev_base]
            
            for g in group_garages: actual_garages.remove(g)
            insert_idx = actual_garages.index(prev_group[0])
            for g in reversed(group_garages): actual_garages.insert(insert_idx, g)
            
        elif item["type"] in ["single", "sub"]:
            g_name = item["name"]
            base_name = item.get("base", g_name)
            idx_in_actual = actual_garages.index(g_name)
            if idx_in_actual == 0: return
            
            if item["type"] == "sub":
                prev_g = actual_garages[idx_in_actual - 1]
                if prev_g.split(" - ", 1)[0] != base_name: return 
                
            actual_garages.remove(g_name)
            actual_garages.insert(idx_in_actual - 1, g_name)

        self.data["garages"] = ["未分類", "帕格薩斯"] + actual_garages
        save_data(self.all_data)
        
        self.skip_refresh_select = True
        self.refresh_garage_table()
        self.skip_refresh_select = False
        
        self.menu_listbox.selection_clear(0, tk.END)
        for i, d in enumerate(self.menu_items_data):
            if d.get("name") == item["name"] and d.get("type") == item["type"]:
                self.menu_listbox.selection_set(i); self.menu_listbox.see(i)
                self.on_garage_menu_select()
                break
        self.menu_listbox.focus_set()

    def move_left_menu_down(self):
        sel = self.menu_listbox.curselection()
        if not sel or len(sel) > 1: return messagebox.showwarning("提示", "請單選一個項目進行排序！\n(若是主物業，會連同所有附屬樓層一起移動)")
        idx = sel[0]
        item = self.menu_items_data[idx]
        if item["type"] == "add": return

        actual_garages = [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]
        
        if item["type"] == "base":
            base_name = item["name"]
            group_garages = [g for g in actual_garages if g.split(" - ", 1)[0] == base_name]
            last_idx = actual_garages.index(group_garages[-1])
            if last_idx == len(actual_garages) - 1: return 
            
            next_garage = actual_garages[last_idx + 1]
            next_base = next_garage.split(" - ", 1)[0]
            next_group = [g for g in actual_garages if g.split(" - ", 1)[0] == next_base]
            
            for g in group_garages: actual_garages.remove(g)
            insert_idx = actual_garages.index(next_group[-1]) + 1
            for g in reversed(group_garages): actual_garages.insert(insert_idx, g)
            
        elif item["type"] in ["single", "sub"]:
            g_name = item["name"]
            base_name = item.get("base", g_name)
            idx_in_actual = actual_garages.index(g_name)
            if idx_in_actual == len(actual_garages) - 1: return
            
            if item["type"] == "sub":
                next_g = actual_garages[idx_in_actual + 1]
                if next_g.split(" - ", 1)[0] != base_name: return 
                
            actual_garages.remove(g_name)
            actual_garages.insert(idx_in_actual + 1, g_name)

        self.data["garages"] = ["未分類", "帕格薩斯"] + actual_garages
        save_data(self.all_data)
        
        self.skip_refresh_select = True
        self.refresh_garage_table()
        self.skip_refresh_select = False
        
        self.menu_listbox.selection_clear(0, tk.END)
        for i, d in enumerate(self.menu_items_data):
            if d.get("name") == item["name"] and d.get("type") == item["type"]:
                self.menu_listbox.selection_set(i); self.menu_listbox.see(i)
                self.on_garage_menu_select()
                break
        self.menu_listbox.focus_set()

    # === 左側選單：右鍵管理與多選刪除功能 ===
    def show_garage_menu_context(self, event):
        if not self.data: return
        idx = self.menu_listbox.nearest(event.y)
        if idx < 0 or idx >= self.menu_listbox.size(): return
        
        if idx not in self.menu_listbox.curselection():
            self.menu_listbox.selection_clear(0, tk.END); self.menu_listbox.selection_set(idx); self.menu_listbox.activate(idx)
            self.on_garage_menu_select()

        sel_indices = self.menu_listbox.curselection()
        items_to_action = [self.menu_items_data[i] for i in sel_indices if i < len(self.menu_items_data) and self.menu_items_data[i]["type"] != "add"]

        if not items_to_action: return

        if not hasattr(self, 'left_menu_popup'): self.left_menu_popup = tk.Menu(self.root, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        self.left_menu_popup.delete(0, tk.END)

        if len(items_to_action) == 1:
            item = items_to_action[0]
            g_name = item["name"]
            if item["type"] == "base":
                self.left_menu_popup.add_command(label=f"➕ 擴建新附屬樓層 (至 {g_name})", command=lambda: self.add_sub_floor(g_name))
                self.left_menu_popup.add_command(label=f"✏️ 重新命名整棟物業", command=lambda: self.rename_entire_property(g_name))
                self.left_menu_popup.add_separator()
                self.left_menu_popup.add_command(label=f"🗑️ 移除此車庫 (含整棟子樓層)", command=lambda: self.delete_entire_property(g_name))
            elif item["type"] in ["single", "sub"]:
                self.left_menu_popup.add_command(label=f"✏️ 修改車庫屬性", command=lambda: self.open_garage_edit_window_by_name(g_name))
                self.left_menu_popup.add_separator()
                self.left_menu_popup.add_command(label=f"🗑️ 移除此車庫", command=lambda: self.delete_garage_by_name(g_name))
        else:
            self.left_menu_popup.add_command(label=f"🗑️ 批量刪除選取的 {len(items_to_action)} 個車庫項目", command=lambda: self.delete_multiple_garages_from_menu(items_to_action))

        self.left_menu_popup.post(event.x_root, event.y_root)

    def delete_multiple_garages_from_menu(self, items):
        garages_to_del = set()
        for item in items:
            if item["type"] == "base":
                base_name = item["name"]
                for g in self.data["garages"]:
                    if g == base_name or g.startswith(base_name + " - "): garages_to_del.add(g)
            elif item["type"] in ["single", "sub"]: garages_to_del.add(item["name"])
        
        if not garages_to_del: return
        
        g_list_str = "\n".join(list(garages_to_del)[:10])
        if len(garages_to_del) > 10: g_list_str += f"\n...等共 {len(garages_to_del)} 個車庫"
        
        if messagebox.askyesno("多選刪除確認", f"⚠️ 警告：您即將批量拆除以下車庫！\n\n{g_list_str}\n\n(這些車庫內的所有車輛將被自動移至「未分類」)\n\n確定要繼續嗎？"):
            for g_name in garages_to_del:
                if g_name in self.data["garages"]: self.data["garages"].remove(g_name)
                if g_name in self.data["garage_limits"]: del self.data["garage_limits"][g_name]
                for v in self.data["vehicles"]:
                    if v.get("garage") == g_name: v["garage"] = "未分類"
                for sv in self.data.get("special_vehicles", []):
                    if sv.get("location") == g_name: sv["location"] = "未分類"
            
            for base in list(self.expanded_bases):
                if base in garages_to_del or not any(g == base or g.startswith(base + " - ") for g in self.data["garages"]):
                    self.expanded_bases.discard(base)
            
            save_data(self.all_data); self.log_action(f"🏠 批量變賣物業：已移除 {len(garages_to_del)} 個車庫")
            self.refresh_garage_table(); self.apply_filters(); self.update_garage_comboboxes(); self.refresh_special_table()
            self.set_status(f"🏠 房地產中心：已成功批量出售 {len(garages_to_del)} 個車庫。", "#FF9800")

    # === 🚚 車輛無縫移動核心功能 ===
    def open_move_vehicle_window(self, g_name, listbox):
        sel = listbox.curselection()
        if not sel: return messagebox.showwarning("提示", "請先點選要移動的載具！\n(可按住 Ctrl 或 Shift 鍵進行多選)")
        if not hasattr(self, 'current_garage_car_indices') or not self.current_garage_car_indices: return
        
        selected_actual_indices = [self.current_garage_car_indices[i] for i in sel]
        
        win = tk.Toplevel(self.root); win.title("🚚 移動載具"); self.center_toplevel_window(win, 400, 220); win.configure(bg=COLOR_CARD_BG)
        tk.Label(win, text=f"將選取的 {len(selected_actual_indices)} 輛載具移至：", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="white").pack(pady=(20, 10))
        combined_locations = ["未分類"] + [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]] + [sv["name"] for sv in self.data.get("special_vehicles", []) if sv.get("can_store", False)]
        
        combo_dest = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=combined_locations, width=28); combo_dest.pack(pady=5); combo_dest.set("未分類")
        
        def confirm_move():
            dest = combo_dest.get()
            if dest == g_name: return messagebox.showinfo("提示", "目標車庫與目前車庫相同！", parent=win)
            disable_limits = self.data.get("app_settings", {}).get("disable_all_limits", False)
            if dest != "未分類" and not disable_limits:
                limit = self.data["garage_limits"].get(dest, 10); usage = self.count_cars_in_garage(dest)
                if usage + len(selected_actual_indices) > limit: return messagebox.showerror("錯誤", f"【{dest}】容量不足！\n剩餘空間: {max(0, limit - usage)} 輛", parent=win)
            for idx in selected_actual_indices:
                self.data["vehicles"][idx]["garage"] = dest; self.data["vehicles"][idx]["updated_at"] = time.strftime('%Y-%m-%d %H:%M')
            self.sync_special_from_vehicles(); save_data(self.all_data); self.show_toast_progress(f"🚚 成功將 {len(selected_actual_indices)} 輛載具移動至 {dest}")
            self.refresh_garage_table(); self.refresh_vehicle_tables(); self.refresh_statistics(); win.destroy()
            
        btn_frame = tk.Frame(win, bg=COLOR_CARD_BG); btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="確認移動", command=confirm_move, style="Primary.TButton").pack(side="left", padx=10, ipady=4); ttk.Button(btn_frame, text="取消", command=win.destroy, style="Secondary.TButton").pack(side="right", padx=10, ipady=4)

    # === 車庫資料操作方法 ===
    def add_garage_simple(self):
        if not self.data: return
        name = self.entry_new_garage.get().strip()
        if not name: return
        try: floors = int(self.entry_new_garage_floors.get().strip() or 1)
        except: floors = 1
        floor_type = self.combo_floor_type.get()
        def_g = self.data.get("app_settings", {}).get("default_garage_limit", 10)
        prompt_txt = f"請輸入「{name}」的可停車位容量上限\n(預設 {def_g} 車位):" if floors == 1 else f"請輸入「{name}」【單層/主樓層】的車位上限\n(預設 {def_g} 車位，系統會自動套用到所有樓層):"
        limit = simpledialog.askinteger("設定上限", prompt_txt, initialvalue=def_g, minvalue=1)
        if not limit: return 
        
        added_names = []
        if name not in self.data["garages"]:
            self.data["garages"].append(name); self.data["garage_limits"][name] = limit; added_names.append(name)
        elif floors == 1: return messagebox.showerror("錯誤", "物業名稱重複！")

        if floors > 1:
            for i in range(1, floors + 1):
                suffix = f" - B{i}" if "地下" in floor_type else f" - 車庫{i}"
                floor_name = f"{name}{suffix}"
                if floor_name not in self.data["garages"]:
                    self.data["garages"].append(floor_name); self.data["garage_limits"][floor_name] = limit; added_names.append(floor_name)
                    
        if "garage_timestamps" not in self.data: self.data["garage_timestamps"] = {}
        for fn in added_names: self.data["garage_timestamps"][fn] = time.strftime("%Y-%m-%d %H:%M")
        save_data(self.all_data); self.show_toast_progress(f"🏠 成功購入物業！")
        self.refresh_garage_table(); self.update_garage_comboboxes()
        self.entry_new_garage.delete(0, tk.END); self.entry_new_garage_floors.delete(0, tk.END); self.entry_new_garage_floors.insert(0, "1"); self.entry_new_garage.focus()

    def add_sub_floor(self, base_name):
        floor_name = simpledialog.askstring("擴建附屬樓層", f"請輸入【{base_name}】的新樓層名稱\n(例如輸入「車庫3」或「B2」):")
        if not floor_name: return
        full_name = f"{base_name} - {floor_name}"
        if full_name in self.data["garages"]: return messagebox.showerror("錯誤", "此樓層名稱已存在！")
        def_g = self.data.get("app_settings", {}).get("default_garage_limit", 10)
        limit = simpledialog.askinteger("設定上限", f"請輸入「{full_name}」的車位上限:", initialvalue=def_g, minvalue=1)
        if not limit: return
        
        insert_idx = len(self.data["garages"])
        for i, g in enumerate(self.data["garages"]):
            if g == base_name or g.startswith(base_name + " - "): insert_idx = i + 1
                
        self.data["garages"].insert(insert_idx, full_name); self.data["garage_limits"][full_name] = limit; self.data.setdefault("garage_timestamps", {})[full_name] = time.strftime("%Y-%m-%d %H:%M")
        save_data(self.all_data); self.show_toast_progress(f"🏠 成功擴建樓層：{floor_name}"); self.expanded_bases.add(base_name)
        self.refresh_garage_table(); self.update_garage_comboboxes()

    def rename_entire_property(self, old_base):
        new_base = simpledialog.askstring("修改整棟物業名稱", f"請輸入新的物業名稱\n(原名稱：{old_base})\n⚠️ 警告：這將會同步修改所有附屬樓層的前綴！", initialvalue=old_base)
        if not new_base or new_base == old_base: return
        if any(g == new_base or g.startswith(new_base + " - ") for g in self.data["garages"]): return messagebox.showerror("錯誤", "新名稱與現有資料衝突！")
        related_garages = [g for g in self.data["garages"] if g == old_base or g.startswith(old_base + " - ")]
        for old_g in related_garages:
            new_g = old_g.replace(old_base, new_base, 1); idx = self.data["garages"].index(old_g)
            self.data["garages"][idx] = new_g; self.data["garage_limits"][new_g] = self.data["garage_limits"].pop(old_g)
            for v in self.data["vehicles"]:
                if v.get("garage") == old_g: v["garage"] = new_g
            for sv in self.data.get("special_vehicles", []):
                if sv.get("location") == old_g: sv["location"] = new_g
        if old_base in self.expanded_bases: self.expanded_bases.remove(old_base); self.expanded_bases.add(new_base)
        save_data(self.all_data); self.refresh_garage_table(); self.refresh_vehicle_tables(); self.update_garage_comboboxes(); self.refresh_special_table(); self.show_toast_progress(f"✅ 整棟物業已更名為：{new_base}")

    def delete_entire_property(self, base_name):
        related_garages = [g for g in self.data["garages"] if g == base_name or g.startswith(base_name + " - ")]
        if messagebox.askyesno("安全確認", f"⚠️ 警告：您即將拆除整棟【{base_name}】！\n\n包含以下樓層：\n{', '.join(related_garages)}\n\n(這些車庫內的所有車輛將被自動移至「未分類」)\n\n確定要繼續嗎？"):
            for g_name in related_garages:
                self.data["garages"].remove(g_name); del self.data["garage_limits"][g_name]
                for v in self.data["vehicles"]:
                    if v.get("garage") == g_name: v["garage"] = "未分類"
                for sv in self.data.get("special_vehicles", []):
                    if sv.get("location") == g_name: sv["location"] = "未分類"
            if base_name in self.expanded_bases: self.expanded_bases.remove(base_name)
            save_data(self.all_data); self.log_action(f"🏠 變賣整棟物業：已移除【{base_name}】及其所有樓層"); self.refresh_garage_table(); self.apply_filters(); self.update_garage_comboboxes(); self.refresh_special_table(); self.set_status(f"🏠 房地產中心：已成功出售整棟物業【{base_name}】。", "#FF9800")

    def open_garage_edit_window_by_name(self, old_name):
        old_limit = self.data["garage_limits"].get(old_name, 10)
        win = tk.Toplevel(self.root); win.title("編輯此樓層屬性"); self.center_toplevel_window(win, 340, 260) 
        tk.Label(win, text="修改此樓層/車庫名稱:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(15,2))
        ent_name = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=24); ent_name.insert(0, old_name); ent_name.pack(); ent_name.focus()
        tk.Label(win, text="修改車位總量上限:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(10,2))
        ent_limit = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=12); ent_limit.insert(0, str(old_limit)); ent_limit.pack()
        apply_focus_highlight(ent_name); apply_focus_highlight(ent_limit)
        def save(e=None):
            new_name = ent_name.get().strip()
            try: new_limit = int(ent_limit.get().strip() or 10)
            except: new_limit = 10
            disable_limits = self.data.get("app_settings", {}).get("disable_all_limits", False)
            if new_name != old_name and new_name in self.data["garages"]: return messagebox.showerror("錯誤", "物業名稱已存在！")
            if not disable_limits and new_limit < self.count_cars_in_garage(old_name): return messagebox.showerror("錯誤", "車位不可小於目前停放車數！")
            
            idx = self.data["garages"].index(old_name)
            self.data["garages"][idx] = new_name; self.data["garage_limits"][new_name] = new_limit
            
            if new_name != old_name:
                del self.data["garage_limits"][old_name]
                for v in self.data["vehicles"]:
                    if v.get("garage") == old_name: v["garage"] = new_name
                for sv in self.data.get("special_vehicles", []):
                    if sv.get("location") == old_name: sv["location"] = new_name
                    
                has_children = any(g != old_name and g.startswith(old_name + " - ") for g in self.data["garages"])
                if has_children:
                    if messagebox.askyesno("同步重新命名", f"系統偵測到【{old_name}】是一棟包含多個樓層的主物業。\n\n是否要同步將底下所有樓層的前綴名稱改為【{new_name}】？\n\n(若選「否」，該樓層將會脫離整棟大樓，變成獨立的車庫)", parent=win):
                        children = [g for g in self.data["garages"] if g != new_name and g.startswith(old_name + " - ")]
                        for child in children:
                            new_child = child.replace(old_name, new_name, 1)
                            c_idx = self.data["garages"].index(child)
                            self.data["garages"][c_idx] = new_child
                            self.data["garage_limits"][new_child] = self.data["garage_limits"].pop(child)
                            for v in self.data["vehicles"]:
                                if v.get("garage") == child: v["garage"] = new_child
                            for sv in self.data.get("special_vehicles", []):
                                if sv.get("location") == child: sv["location"] = new_child

                base = old_name.split(" - ", 1)[0]
                if old_name == base and new_name != base and base in self.expanded_bases:
                    self.expanded_bases.remove(base)
                    self.expanded_bases.add(new_name)
                    
            save_data(self.all_data); self.refresh_garage_table(); self.refresh_vehicle_tables(); self.update_garage_comboboxes(); self.refresh_special_table(); win.destroy(); self.set_status(f"✏️ 已更新物業【{new_name}】的屬性。", "#3498db")
        def delete_garage_action():
            self.delete_garage_by_name(old_name); win.destroy()
        btn_frame = tk.Frame(win, bg=COLOR_MAIN_BG); btn_frame.pack(fill="x", padx=35, pady=15)
        ttk.Button(btn_frame, text="保存修改", command=save, style="Success.TButton").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=4); ttk.Button(btn_frame, text="🗑️ 拆除物業", command=delete_garage_action, style="Danger.TButton").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4)
        ent_name.bind("<Return>", lambda e: ent_limit.focus()); ent_limit.bind("<Return>", save)

    def delete_garage_by_name(self, g_name):
        if messagebox.askyesno("安全確認", f"您確定要拆除單一樓層「{g_name}」嗎？\n(車庫內的車輛將自動撤回「未分類」車庫)"):
            if g_name in self.data["garages"]: self.data["garages"].remove(g_name)
            if g_name in self.data["garage_limits"]: del self.data["garage_limits"][g_name]
            for v in self.data["vehicles"]:
                if v.get("garage") == g_name: v["garage"] = "未分類"
            for sv in self.data.get("special_vehicles", []):
                if sv.get("location") == g_name: sv["location"] = "未分類"
            save_data(self.all_data); self.refresh_garage_table(); self.apply_filters(); self.update_garage_comboboxes(); self.refresh_special_table(); self.set_status(f"🏠 房地產中心：已成功出售樓層【{g_name}】。", "#FF9800")

    def open_batch_garage_window(self):
        if not self.data: return
        win = tk.Toplevel(self.root); win.title("📦 批量新增車庫"); self.center_toplevel_window(win, 550, 280); win.configure(bg=COLOR_CARD_BG)

        frame_add = tk.LabelFrame(win, text=" ➕ 批量新增車庫 (一行輸入一個名稱) ", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="#4CAF50"); frame_add.pack(fill="x", padx=15, pady=10, ipady=5)
        txt_add = tk.Text(frame_add, height=6, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", relief="solid"); txt_add.pack(fill="x", padx=10, pady=5)
        
        def do_batch_add():
            lines = txt_add.get("1.0", tk.END).strip().split('\n')
            added = 0; def_g = self.data.get("app_settings", {}).get("default_garage_limit", 10)
            for line in lines:
                name = line.strip()
                if not name or name in self.data["garages"]: continue
                self.data["garages"].append(name); self.data["garage_limits"][name] = def_g; added += 1
            if added > 0:
                if "garage_timestamps" not in self.data: self.data["garage_timestamps"] = {}
                for line in lines:
                    n = line.strip()
                    if n and n in self.data["garages"]: self.data["garage_timestamps"][n] = time.strftime("%Y-%m-%d %H:%M")
                save_data(self.all_data); self.refresh_garage_table(); self.update_garage_comboboxes(); txt_add.delete("1.0", tk.END); self.show_toast_progress(f"✅ 成功批量新增 {added} 個車庫")
            else: messagebox.showinfo("提示", "沒有讀取到有效的新車庫名稱，或名稱已經存在！", parent=win)
                
        ttk.Button(frame_add, text="執行批量新增", command=do_batch_add, style="Success.TButton").pack(side="right", padx=10, pady=5)

if __name__ == "__main__":
    try:
        import ctypes
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "GTA_Garage_App_Single_Instance_Mutex")
        if ctypes.windll.kernel32.GetLastError() == 183:
            err_root = tk.Tk(); err_root.withdraw(); messagebox.showerror("啟動失敗", "⚠️ 程式已經在執行中！"); err_root.destroy(); sys.exit(0)
    except Exception: pass

    try:
        root = tk.Tk()
        app = GTAGarageApp(root)
        root.mainloop()
    except Exception as e:
        import traceback
        err_root = tk.Tk(); err_root.withdraw(); messagebox.showerror("系統崩潰報告", f"程式啟動失敗，錯誤代碼：\n\n{traceback.format_exc()}"); err_root.destroy()
