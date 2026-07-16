import json
import os
import sys
import time
import shutil
import threading
import urllib.request
import tkinter as tk
from tkinter import messagebox, ttk, filedialog, simpledialog

# === 軟體版本與更新設定 ===
APP_VERSION = "4.2.3" 
UPDATE_URL = "https://raw.githubusercontent.com/cvk82519-boop/GTA-Garage-App/refs/heads/main/version.json"
DATA_FILE = "gta5_garage_data.json"

ACQUIRE_OPTIONS = ["購買獲得", "任務獲得", "生涯成就", "賭場轉盤", "搶劫獲得", "車友會", "其他備註"]
V_TYPE_OPTIONS = ["個人載具", "非個人載具"]

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
            p_data["garages"] = ["未分類", "日蝕大樓 1 號", "辦公室車庫", "名鑽賭場空中別墅", "設施"]
        if "garage_limits" not in p_data:
            p_data["garage_limits"] = {"未分類": 999}
            for g in p_data["garages"]:
                if g != "未分類": p_data["garage_limits"][g] = 10
        for sv in p_data.get("special_vehicles", []):
            if "inner_vehicle" not in sv: sv["inner_vehicle"] = ""
            if "can_store" not in sv: sv["can_store"] = True if sv["name"] in SUB_CARRIER_RULES else False

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)

class GTAGarageApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"洛聖都資產管理系統 V{APP_VERSION}")
        self.root.configure(bg=COLOR_MAIN_BG)
        
        window_width = 1250
        window_height = 780
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        center_x = (screen_width - window_width) // 2
        center_y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        self.root.resizable(False, False)
        
        self.root.option_add("*Entry.background", COLOR_CARD_BG)
        self.root.option_add("*Entry.foreground", COLOR_TEXT_WHITE)
        self.root.option_add("*Entry.insertBackground", COLOR_TEXT_WHITE)

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background=COLOR_MAIN_BG, foreground=COLOR_TEXT_WHITE, font=FONT_NORMAL)
        self.style.configure("TNotebook", background=COLOR_MAIN_BG, borderwidth=0, padding=2)
        self.style.configure("TNotebook.Tab", background=COLOR_CARD_BG, foreground=COLOR_TEXT_GRAY, font=FONT_BOLD, padding=[15, 6])
        self.style.map("TNotebook.Tab", background=[("selected", COLOR_MAIN_BG)], foreground=[("selected", "#4CAF50")])
        self.style.configure("Treeview", background=COLOR_CARD_BG, fieldbackground=COLOR_CARD_BG, foreground=COLOR_TEXT_WHITE, font=FONT_NORMAL, rowheight=28)
        self.style.configure("Treeview.Heading", background="#151515", foreground=COLOR_TEXT_WHITE, font=FONT_BOLD, borderwidth=1)
        self.style.map("Treeview", background=[("selected", "#2c7a43")])

        self.style.map('TCombobox', fieldbackground=[('readonly', COLOR_CARD_BG)], foreground=[('readonly', COLOR_TEXT_WHITE)])
        self.style.configure('TCombobox', fieldbackground=COLOR_CARD_BG, background=COLOR_CARD_BG, foreground=COLOR_TEXT_WHITE)
        self.root.option_add("*TCombobox*Listbox.background", COLOR_CARD_BG)
        self.root.option_add("*TCombobox*Listbox.foreground", COLOR_TEXT_WHITE)
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#4CAF50")
        self.root.option_add("*TCombobox*Listbox.selectForeground", "white")

        self.all_data = load_data()
        self.current_id = ""
        self.data = None
        
        # 碼錶相關變數
        self.is_running = False
        self.start_time = 0.0
        self.elapsed_time = 0.0
        self.stopwatch_window = None

        # 🌟 UI 佈局
        self.setup_menu_bar()
        self.setup_status_bar()
        self.setup_profile_bar()
        
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=5)
        
        self.tab_vehicles = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.notebook.add(self.tab_vehicles, text=" 🚗 車輛管理 ")
        self.tab_non_personal = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.notebook.add(self.tab_non_personal, text=" 🚜 非個人載具 ")
        self.tab_special = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.notebook.add(self.tab_special, text=" 🚁 特殊載具 ")
        self.tab_garages = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.notebook.add(self.tab_garages, text=" 🏠 車庫管理 ")

        self.setup_vehicles_tab()
        self.setup_non_personal_tab()
        self.setup_special_tab()
        self.setup_garages_tab()

        self.root.bind_all("<Pause>", self.handle_pause_key)
        self.check_login_status()

    # ==========================================
    #   🌟 頂端功能列 (Menu Bar)
    # ==========================================
    def setup_menu_bar(self):
        menubar = tk.Menu(self.root)
        
        # 檔案 (File)
        file_menu = tk.Menu(menubar, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        file_menu.add_command(label="💾 手動備份資料 (Backup)", command=self.backup_data)
        file_menu.add_separator()
        file_menu.add_command(label="🚪 結束系統 (Exit)", command=self.root.quit)
        menubar.add_cascade(label="檔案 (F)", menu=file_menu)

        # 系統工具 (Tools)
        tools_menu = tk.Menu(menubar, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        tools_menu.add_command(label="⏱️ 呼叫任務碼錶 (或按 Pause 鍵)", command=self.toggle_stopwatch)
        tools_menu.add_command(label="📦 批量貼上匯入", command=self.open_batch_import_window)
        menubar.add_cascade(label="系統工具 (T)", menu=tools_menu)
        
        # 視窗導覽 (Navigation)
        nav_menu = tk.Menu(menubar, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        nav_menu.add_command(label="🚗 前往 車輛管理", command=lambda: self.notebook.select(self.tab_vehicles))
        nav_menu.add_command(label="🚜 前往 非個人載具", command=lambda: self.notebook.select(self.tab_non_personal))
        nav_menu.add_command(label="🚁 前往 特殊載具", command=lambda: self.notebook.select(self.tab_special))
        nav_menu.add_command(label="🏠 前往 車庫管理", command=lambda: self.notebook.select(self.tab_garages))
        menubar.add_cascade(label="視窗導覽 (V)", menu=nav_menu)

        # 關於 (About)
        about_menu = tk.Menu(menubar, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        about_menu.add_command(label="ℹ️ 關於本系統", command=self.show_about)
        menubar.add_cascade(label="關於 (A)", menu=about_menu)

        self.root.config(menu=menubar)

    def backup_data(self):
        if not os.path.exists(DATA_FILE): return messagebox.showinfo("備份", "目前沒有資料檔案可備份。")
        backup_name = f"backup_gta_data_{int(time.time())}.json"
        try:
            shutil.copy(DATA_FILE, backup_name)
            self.set_status(f"✅ 資料已成功安全備份至：{backup_name}", color="#4CAF50")
            messagebox.showinfo("備份成功", f"資料已成功備份為：\n{backup_name}")
        except Exception as e:
            messagebox.showerror("備份錯誤", f"備份失敗：\n{e}")

    def show_about(self):
        messagebox.showinfo("關於", f"🚗 洛聖都資產管理系統\n當前版本：{APP_VERSION}\n\n為 GTA5 玩家打造的專業載具與車庫資產追蹤工具。")

    # ==========================================
    #   ⏱️ 碼錶功能區塊 (V4.2.3 修復補回)
    # ==========================================
    def handle_pause_key(self, event=None):
        self.toggle_stopwatch()

    def toggle_stopwatch(self):
        if not self.stopwatch_window or not self.stopwatch_window.winfo_exists():
            self.stopwatch_window = tk.Toplevel(self.root)
            self.stopwatch_window.title("⏱️ 任務碼錶")
            self.stopwatch_window.geometry("260x120")
            self.stopwatch_window.configure(bg=COLOR_CARD_BG)
            self.stopwatch_window.attributes("-topmost", True)
            self.stopwatch_window.resizable(False, False)
            
            self.lbl_sw = tk.Label(self.stopwatch_window, text="00:00.0", font=("Consolas", 32, "bold"), bg=COLOR_CARD_BG, fg="white")
            self.lbl_sw.pack(pady=10)
            
            btn_f = tk.Frame(self.stopwatch_window, bg=COLOR_CARD_BG)
            btn_f.pack()
            self.btn_sw_action = tk.Button(btn_f, text="開始/暫停", command=self.action_stopwatch, bg="#FF9800" if self.is_running else "#4CAF50", fg="white", font=FONT_BOLD, relief="flat")
            self.btn_sw_action.pack(side="left", padx=5)
            tk.Button(btn_f, text="歸零", command=self.reset_stopwatch, bg="#e74c3c", fg="white", font=FONT_BOLD, relief="flat").pack(side="left", padx=5)
            
            if self.is_running:
                self.update_stopwatch_ui()
        else:
            self.stopwatch_window.destroy()

    def action_stopwatch(self):
        if not self.is_running:
            self.is_running = True
            self.start_time = time.time() - self.elapsed_time
            self.update_stopwatch_loop()
            self.btn_sw_action.config(bg="#FF9800")
        else:
            self.is_running = False
            self.btn_sw_action.config(bg="#4CAF50")

    def reset_stopwatch(self):
        self.is_running = False
        self.elapsed_time = 0.0
        if hasattr(self, 'lbl_sw') and self.lbl_sw.winfo_exists():
            self.lbl_sw.config(text="00:00.0")
            self.btn_sw_action.config(bg="#4CAF50")

    def update_stopwatch_loop(self):
        if self.is_running:
            self.elapsed_time = time.time() - self.start_time
            self.update_stopwatch_ui()
            self.root.after(50, self.update_stopwatch_loop)

    def update_stopwatch_ui(self):
        if hasattr(self, 'lbl_sw') and self.lbl_sw.winfo_exists():
            mins = int(self.elapsed_time // 60)
            secs = int(self.elapsed_time % 60)
            ms = int((self.elapsed_time * 10) % 10)
            self.lbl_sw.config(text=f"{mins:02d}:{secs:02d}.{ms}")

    # ==========================================
    #   🌟 底部全域狀態列 (Status Bar)
    # ==========================================
    def setup_status_bar(self):
        self.status_bar = tk.Label(self.root, text="💡 系統就緒。輸入完畢按下 Enter 即可連續新增；非個人載具會自動過濾至專屬頁面。", bg="#111111", fg="#FF9800", font=FONT_BOLD, anchor="w", padx=15, pady=6)
        self.status_bar.pack(side="bottom", fill="x")

    def set_status(self, msg, color="#FF9800"):
        if hasattr(self, 'status_bar') and self.status_bar.winfo_exists():
            self.status_bar.config(text=msg, fg=color)

    # ==========================================
    #   核心工具與邏輯區塊
    # ==========================================
    def center_toplevel_window(self, win, width, height):
        win.configure(bg=COLOR_MAIN_BG)
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.resizable(False, False)

    def sort_treeview(self, tv, col, reverse):
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        try: l.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError: l.sort(key=lambda t: t[0].replace("📌 ", "").replace("🔒 ", ""), reverse=reverse)
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
                if sv["name"] == g:
                    sv["inner_vehicle"] += f", {car['name']}" if sv["inner_vehicle"] else car["name"]

    def sync_vehicles_from_special(self):
        if not self.data: return
        for sv in self.data.get("special_vehicles", []):
            sv_name = sv["name"]; inner_car = sv.get("inner_vehicle", "")
            if inner_car and sv.get("can_store", False) and "," not in inner_car:
                found = any(car["name"] == inner_car and car.update({"garage": sv_name}) or True for car in self.data.get("vehicles", []) if car["name"] == inner_car)
                if not found:
                    self.data["vehicles"].append({"name": inner_car, "garage": sv_name, "v_type": "個人載具", "acquire": "購買獲得", "upgraded": "未改滿", "count": 1, "notes": f"自【{sv_name}】同步", "locked": False, "pinned": False})

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
        
        self.lbl_clock = tk.Label(top_frame, text="", bg="#1a1a1a", fg="#4CAF50", font=("Consolas", 13, "bold"))
        self.lbl_clock.pack(side="right", padx=20)
        self.update_clock() 
        
        self.update_profile_combo()

    def update_clock(self):
        current_time = time.strftime('%Y-%m-%d  %H:%M:%S')
        self.lbl_clock.config(text=f"🕒 {current_time}")
        self.root.after(1000, self.update_clock)

    def delete_profile(self):
        sel = self.combo_profile.get()
        if not sel: return messagebox.showwarning("操作提示", "請先在下拉選單中選取您想刪除的 ID！")
        if messagebox.askyesno("⚠️ 極度危險操作", f"確定要徹底刪除 ID：【 {sel} 】嗎？") and messagebox.askyesno("❗ 最後確認", "資料刪除後無法還原，確定抹除嗎？"):
            del self.all_data["profiles"][sel]; save_data(self.all_data); self.show_toast_progress(f"🗑️ 已抹除 ID：{sel}")
            self.set_status(f"🗑️ 角色檔案 {sel} 已永久移除。", "#c62828")
            if self.current_id == sel: self.current_id = ""
            self.update_profile_combo(); self.combo_profile.set(""); self.check_login_status()

    def update_profile_combo(self):
        self.combo_profile["values"] = list(self.all_data.get("profiles", {}).keys())
        if self.current_id: self.combo_profile.set(self.current_id)

    def check_login_status(self):
        is_logged_in = bool(self.current_id and self.current_id in self.all_data["profiles"])
        state_str = "normal" if is_logged_in else "disabled"
        
        self.btn_logout.config(state="normal" if is_logged_in else "disabled"); self.btn_login.config(state="disabled" if is_logged_in else "normal")
        self.btn_delete_profile.config(state="disabled" if is_logged_in else "normal"); self.combo_profile.config(state="disabled" if is_logged_in else "readonly")
        
        if is_logged_in:
            self.data = self.all_data["profiles"][self.current_id]
            for key, default in [("vehicles", []), ("special_vehicles", []), ("garages", ["未分類", "日蝕大樓 1 號"])]:
                if key not in self.data: self.data[key] = default
            if "garage_limits" not in self.data:
                self.data["garage_limits"] = {"未分類": 999}
                for g in self.data["garages"]: 
                    if g != "未分類": self.data["garage_limits"][g] = 10
        else: self.current_id = ""; self.data = None

        for tab in [self.tab_vehicles, self.tab_non_personal, self.tab_special, self.tab_garages]:
            self.notebook.tab(tab, state=state_str)
            
        self.update_garage_comboboxes(); self.refresh_vehicle_tables(); self.refresh_special_table(); self.refresh_garage_table()

    def login_profile(self):
        sel = self.combo_profile.get()
        if sel and sel in self.all_data["profiles"]: 
            self.current_id = sel; self.check_login_status()
            self.show_toast_progress(f"🔑 登入成功：{sel}")
            self.set_status(f"🔑 成功登入角色：{sel}", "#4CAF50")

    def logout_profile(self): 
        self.current_id = ""; self.check_login_status(); self.combo_profile.set("")
        self.show_toast_progress("🚪 已登出")
        self.set_status("🚪 已登出，請選擇 ID 登入。", "#FF9800")

    def create_profile(self):
        name = simpledialog.askstring("新建 ID", "請輸入新的遊戲 ID / 角色名稱:")
        if not name: return
        if name in self.all_data["profiles"]: return messagebox.showwarning("重複", "ID 已經存在！")
        self.all_data["profiles"][name] = {"vehicles": [], "special_vehicles": [], "garages": ["未分類", "日蝕大樓 1 號"], "garage_limits": {"未分類": 999, "日蝕大樓 1 號": 10}}
        save_data(self.all_data); self.update_profile_combo(); self.combo_profile.set(name); messagebox.showinfo("建立成功", f"成功建立：{name}")

    def show_toast_progress(self, message="✅ 操作成功"):
        toast = tk.Toplevel(self.root); toast.overrideredirect(True); toast.attributes("-topmost", True)
        toast.configure(bg=COLOR_CARD_BG)
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
        if event and hasattr(event, 'widget') and isinstance(event.widget, ttk.Treeview):
            return event.widget
        current_tab_id = self.notebook.select()
        if "非個人載具" in self.notebook.tab(current_tab_id, "text"):
            return self.tree_non_personal
        return self.tree_vehicles

    # ==========================================
    #     🚗 1. 車輛管理頁面 (包含輸入區)
    # ==========================================
    def setup_vehicles_tab(self):
        input_frame = tk.LabelFrame(self.tab_vehicles, text=" 📝 登記新載具資產 ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#4CAF50", padx=12, pady=12, bd=2)
        input_frame.pack(fill="x", padx=15, pady=10)

        tk.Label(input_frame, text="名稱:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=0, sticky="e", pady=5)
        self.entry_name = tk.Entry(input_frame, width=15, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid")
        self.entry_name.grid(row=0, column=1, padx=4, pady=5); self.entry_name.bind("<Return>", lambda e: self.combo_garage.focus())

        tk.Label(input_frame, text="位置/特殊載具:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=2, sticky="e", pady=5)
        self.combo_garage = ttk.Combobox(input_frame, width=16, state="readonly", font=FONT_NORMAL)
        self.combo_garage.grid(row=0, column=3, padx=4, pady=5); self.combo_garage.bind("<Return>", lambda e: self.combo_vtype.focus())

        tk.Label(input_frame, text="類型:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=4, sticky="e", pady=5)
        self.combo_vtype = ttk.Combobox(input_frame, width=10, state="readonly", values=V_TYPE_OPTIONS, font=FONT_NORMAL)
        self.combo_vtype.set("個人載具"); self.combo_vtype.grid(row=0, column=5, padx=4, pady=5)
        self.combo_vtype.bind("<Return>", lambda e: self.combo_acquire.focus())

        tk.Label(input_frame, text="取得:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=1, column=0, sticky="e", pady=5)
        self.combo_acquire = ttk.Combobox(input_frame, width=10, state="readonly", values=ACQUIRE_OPTIONS, font=FONT_NORMAL)
        self.combo_acquire.set("購買獲得"); self.combo_acquire.grid(row=1, column=1, padx=4, pady=5)
        self.combo_acquire.bind("<Return>", lambda e: self.combo_upgrade.focus())

        tk.Label(input_frame, text="改裝:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=1, column=2, sticky="e", pady=5)
        self.combo_upgrade = ttk.Combobox(input_frame, width=8, state="readonly", values=["未改滿", "已改滿"], font=FONT_NORMAL)
        self.combo_upgrade.set("未改滿"); self.combo_upgrade.grid(row=1, column=3, padx=4, pady=5)
        self.combo_upgrade.bind("<Return>", lambda e: self.add_vehicle())

        btn_f = tk.Frame(input_frame, bg=COLOR_CARD_BG); btn_f.grid(row=1, column=4, columnspan=2, sticky="w", padx=10)
        tk.Button(btn_f, text="➕ 新增登記", command=self.add_vehicle, bg="#4CAF50", fg="white", font=FONT_BOLD, relief="flat", padx=10).pack(side="left", padx=5)
        tk.Button(btn_f, text="📦 批量貼上", command=self.open_batch_import_window, bg="#2196F3", fg="white", font=FONT_BOLD, relief="flat", padx=8).pack(side="left", padx=5)

        action_frame = tk.Frame(self.tab_vehicles, bg=COLOR_MAIN_BG); action_frame.pack(fill="x", padx=15, pady=5)
        tk.Label(action_frame, text="🔍 全域搜尋:", bg=COLOR_MAIN_BG, fg="white", font=FONT_NORMAL).pack(side="left")
        self.entry_search = tk.Entry(action_frame, width=18, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid")
        self.entry_search.pack(side="left", padx=5); self.entry_search.bind("<KeyRelease>", lambda e: self.apply_filters())
        
        tk.Label(action_frame, text="  |  篩選車庫位置:", bg=COLOR_MAIN_BG, fg="white", font=FONT_NORMAL).pack(side="left", padx=5)
        self.combo_garage_filter = ttk.Combobox(action_frame, width=18, state="readonly", font=FONT_NORMAL); self.combo_garage_filter.pack(side="left", padx=5)
        self.combo_garage_filter.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())
        tk.Button(action_frame, text="重置條件", command=self.reset_filters, bg="#555555", fg="white", font=FONT_BOLD, relief="flat", padx=6).pack(side="left", padx=10)

        tree_frame = tk.Frame(self.tab_vehicles, bg=COLOR_MAIN_BG); tree_frame.pack(fill="both", expand=True, padx=15, pady=10)
        self.tree_vehicles = ttk.Treeview(tree_frame, columns=("name", "garage", "vtype", "acquire", "upgrade", "count", "notes"), show="headings", selectmode="extended")
        
        columns_config = {"name": "車輛名稱", "garage": "存放位置", "vtype": "類型", "acquire": "取得方式", "upgrade": "改裝", "count": "數量", "notes": "備註"}
        for col, text in columns_config.items(): self.tree_vehicles.heading(col, text=text, command=lambda c=col: self.sort_treeview(self.tree_vehicles, c, False))
        self.tree_vehicles.column("vtype", width=90, anchor="center"); self.tree_vehicles.column("acquire", width=100, anchor="center")
        self.tree_vehicles.column("upgrade", width=80, anchor="center"); self.tree_vehicles.column("count", width=60, anchor="center")
        
        self.tree_vehicles.bind("<Double-1>", self.open_edit_window); self.tree_vehicles.bind("<Return>", self.open_edit_window)
        self.tree_vehicles.bind("<Delete>", self.delete_vehicle)
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_vehicles.yview)
        self.tree_vehicles.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y"); self.tree_vehicles.pack(side="left", fill="both", expand=True)
        
        self.vehicle_popup_menu = tk.Menu(self.root, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        self.tree_vehicles.bind("<Button-3>", self.show_vehicle_context_menu)

    # ==========================================
    #     🚜 1.5 非個人載具頁面 (自動分類區)
    # ==========================================
    def setup_non_personal_tab(self):
        header_frame = tk.Frame(self.tab_non_personal, bg=COLOR_MAIN_BG)
        header_frame.pack(fill="x", padx=15, pady=15)
        tk.Label(header_frame, text="🚜 非個人載具列表", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#FF9800").pack(side="left")
        tk.Label(header_frame, text=" (請統一在「車輛管理」面板新增，系統會自動將非個人載具過濾並分類至此區)", font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg=COLOR_TEXT_GRAY).pack(side="left")

        tree_frame = tk.Frame(self.tab_non_personal, bg=COLOR_MAIN_BG); tree_frame.pack(fill="both", expand=True, padx=15, pady=5)
        self.tree_non_personal = ttk.Treeview(tree_frame, columns=("name", "garage", "vtype", "acquire", "upgrade", "count", "notes"), show="headings", selectmode="extended")
        
        columns_config = {"name": "車輛名稱", "garage": "存放位置", "vtype": "類型", "acquire": "取得方式", "upgrade": "改裝", "count": "數量", "notes": "備註"}
        for col, text in columns_config.items(): self.tree_non_personal.heading(col, text=text, command=lambda c=col: self.sort_treeview(self.tree_non_personal, c, False))
        self.tree_non_personal.column("vtype", width=90, anchor="center"); self.tree_non_personal.column("acquire", width=100, anchor="center")
        self.tree_non_personal.column("upgrade", width=80, anchor="center"); self.tree_non_personal.column("count", width=60, anchor="center")
        
        self.tree_non_personal.bind("<Double-1>", self.open_edit_window); self.tree_non_personal.bind("<Return>", self.open_edit_window)
        self.tree_non_personal.bind("<Delete>", self.delete_vehicle)
        self.tree_non_personal.bind("<Button-3>", self.show_vehicle_context_menu)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_non_personal.yview)
        self.tree_non_personal.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y"); self.tree_non_personal.pack(side="left", fill="both", expand=True)

    def update_garage_comboboxes(self):
        if not self.data: return
        spec_carriers = [sv["name"] for sv in self.data.get("special_vehicles", []) if sv.get("can_store", False)]
        actual_garages = [g for g in self.data["garages"] if g != "未分類"]
        combined_list = actual_garages + spec_carriers
        
        self.combo_garage["values"] = combined_list
        if self.combo_garage["values"] and not self.combo_garage.get(): self.combo_garage.set(self.combo_garage["values"][0])
        self.combo_garage_filter["values"] = ["全部", "未分類"] + combined_list
        if self.combo_garage_filter.get() == "": self.combo_garage_filter.set("全部")

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
            values = (display_name, car["garage"], car.get("v_type", ""), car.get("acquire", ""), car.get("upgraded", ""), car.get("count", 1), car.get("notes", ""))
            
            if car.get("v_type", "個人載具") == "非個人載具":
                if hasattr(self, 'tree_non_personal'): self.tree_non_personal.insert("", "end", iid=str(idx), values=values)
            else:
                self.tree_vehicles.insert("", "end", iid=str(idx), values=values)

    def add_vehicle(self):
        if not self.data: return
        name = self.entry_name.get().strip()
        if not name: return
        garage = self.combo_garage.get().strip() or "未分類"
        vtype = self.combo_vtype.get()
        if garage != "未分類":
            if not self.validate_tab1_vehicle_to_garage(name, garage): return
            spec_carriers = [sv["name"] for sv in self.data.get("special_vehicles", [])]
            limit = self.data["garage_limits"].get(garage, 1 if garage in spec_carriers else 10)
            if self.count_cars_in_garage(garage) >= limit: return messagebox.showerror("位置已滿", f"【{garage}】容量已滿！")

        self.data["vehicles"].append({
            "name": name, "garage": garage, "v_type": vtype, "acquire": self.combo_acquire.get(), 
            "upgraded": self.combo_upgrade.get(), "count": 1, "notes": "無", "locked": False, "pinned": False 
        })
        self.sync_special_from_vehicles(); save_data(self.all_data)
        self.entry_search.delete(0, tk.END); self.combo_garage_filter.set("全部")
        
        self.refresh_vehicle_tables(); self.refresh_special_table(); self.refresh_garage_table()
        self.entry_name.delete(0, tk.END)
        self.show_toast_progress("🚗 登記成功！")
        self.set_status(f"✅ 新增成功：【{name}】已登記入庫至 {garage}。游標已就緒，請繼續輸入！", "#4CAF50")
        
        new_iid = str(len(self.data["vehicles"]) - 1)
        target_tree = self.tree_non_personal if vtype == "非個人載具" else self.tree_vehicles
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
            for item in sorted([int(s) for s in selected], reverse=True): del self.data["vehicles"][item]
            self.sync_special_from_vehicles(); save_data(self.all_data); self.apply_filters()
            self.refresh_special_table(); self.refresh_garage_table()
            self.set_status(f"🗑️ 成功刪除 {len(selected)} 筆載具資料。", "#FF9800")

    def toggle_pin_vehicle(self, event=None):
        if not self.data: return
        target_tree = self.get_active_tree(event)
        selected = target_tree.selection()
        if not selected: return
        new_state = not self.data["vehicles"][int(selected[0])].get("pinned", False)
        for item in selected: self.data["vehicles"][int(item)]["pinned"] = new_state
        save_data(self.all_data); self.apply_filters(); self.show_toast_progress("📌 置頂狀態已更新")
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
        self.entry_search.delete(0, tk.END); self.combo_garage_filter.set("全部"); self.refresh_vehicle_tables()

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
        win = tk.Toplevel(self.root); win.title("批量貼上匯入")
        self.center_toplevel_window(win, 540, 480); win.bind("<Escape>", lambda e: win.destroy())
        tk.Label(win, text="請在此貼上車輛資料（一行一筆）", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#2196F3").pack(pady=8)
        text_area = tk.Text(win, height=13, width=52, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); text_area.pack(pady=10, padx=15)
        
        def process_import():
            content = text_area.get("1.0", tk.END).strip(); added = 0
            spec_carriers = [sv["name"] for sv in self.data.get("special_vehicles", []) if sv.get("can_store", False)]
            for line in content.split('\n'):
                if not line.strip(): continue
                parts = line.split(',')
                name = parts[0].strip(); garage = parts[1].strip() if len(parts) > 1 else "未分類"
                if garage in SUB_CARRIER_RULES and not self.validate_tab1_vehicle_to_garage(name, garage, show_error=False): garage = "未分類"
                idx_existing = next((i for i, c in enumerate(self.data["vehicles"]) if c['name'] == name), None)
                if idx_existing is not None:
                    self.data["vehicles"][idx_existing]["count"] = int(self.data["vehicles"][idx_existing].get("count") or 1) + 1
                else:
                    if garage not in self.data["garages"] and garage not in spec_carriers: garage = "未分類"
                    self.data["vehicles"].append({"name": name, "garage": garage, "v_type": "個人載具", "acquire": "購買獲得", "upgraded": "未改滿", "count": 1, "notes": "無", "locked": False, "pinned": False})
                    added += 1
                    
            self.sync_special_from_vehicles(); save_data(self.all_data)
            self.refresh_vehicle_tables(); self.refresh_special_table(); win.destroy(); self.refresh_garage_table()
            self.show_toast_progress(f"📦 批量匯入完成 ({added} 筆)")
            self.set_status(f"📦 批量操作完成，共新增了 {added} 筆資料。", "#2196F3")
            if added > 0:
                new_iid = str(len(self.data["vehicles"]) - 1)
                if self.tree_vehicles.exists(new_iid):
                    self.tree_vehicles.selection_set(new_iid); self.tree_vehicles.focus(new_iid); self.tree_vehicles.see(new_iid)
        tk.Button(win, text="確認執行批量匯入", command=process_import, bg="#2196F3", fg="white", font=FONT_BOLD, relief="flat", height=2).pack(fill="x", padx=15, pady=10)

    def open_edit_window(self, event=None):
        if not self.data: return
        target_tree = self.get_active_tree(event)
        selected = target_tree.selection()
        if not selected: return
        for item in selected:
            if self.data["vehicles"][int(item)].get("locked", False): return messagebox.showwarning("鎖定限制", "⚠️ 資料已鎖定，請解鎖後再編輯！")
        
        spec_carriers = [sv["name"] for sv in self.data.get("special_vehicles", []) if sv.get("can_store", False)]
        combined_locations = self.data["garages"] + spec_carriers
        
        if len(selected) == 1:
            idx = int(selected[0]); car = self.data["vehicles"][idx]
            win = tk.Toplevel(self.root); win.title("編輯載具資產")
            self.center_toplevel_window(win, 340, 480)
            
            tk.Label(win, text="載具資產名稱:", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(12,2))
            ent_name = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=22); ent_name.insert(0, car['name']); ent_name.pack(); ent_name.focus()
            
            combo_edit_garage = ttk.Combobox(win, state="readonly", values=combined_locations, font=FONT_NORMAL); combo_edit_vtype = ttk.Combobox(win, state="readonly", values=V_TYPE_OPTIONS, font=FONT_NORMAL)
            combo_edit_acquire = ttk.Combobox(win, state="readonly", values=ACQUIRE_OPTIONS, font=FONT_NORMAL); combo_edit_upgrade = ttk.Combobox(win, state="readonly", values=["未改滿", "已改滿"], font=FONT_NORMAL)
            ent_count = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", relief="solid", width=22); ent_notes = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", relief="solid", width=22)
            
            tk.Label(win, text="存放位置 (車庫/特殊載具):", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(6,2)); combo_edit_garage.set(car.get('garage', '未分類')); combo_edit_garage.pack()
            tk.Label(win, text="載具類型:", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(6,2)); combo_edit_vtype.set(car.get('v_type', '個人載具')); combo_edit_vtype.pack()
            tk.Label(win, text="取得方式:", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(6,2)); combo_edit_acquire.set(car.get('acquire', '購買獲得')); combo_edit_acquire.pack()
            tk.Label(win, text="改裝狀態:", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(6,2)); combo_edit_upgrade.set(car.get('upgraded', '未改滿')); combo_edit_upgrade.pack()
            tk.Label(win, text="資產數量:", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(6,2)); ent_count.insert(0, str(car.get('count', 1))); ent_count.pack()
            tk.Label(win, text="自訂備註:", bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE, font=FONT_BOLD).pack(pady=(6,2)); ent_notes.insert(0, car.get('notes', '無')); ent_notes.pack()
            
            def save_single(e=None):
                new_car_name = ent_name.get(); new_g = combo_edit_garage.get()
                if new_g != car['garage'] and new_g != "未分類":
                    if not self.validate_tab1_vehicle_to_garage(new_car_name, new_g): return
                    lim = self.data["garage_limits"].get(new_g, 1 if new_g in spec_carriers else 10)
                    if self.count_cars_in_garage(new_g) >= lim: return messagebox.showerror("容量已滿", f"【{new_g}】空間不足！上限為 {lim} 台。")
                
                car.update({'name': new_car_name, 'garage': new_g, 'v_type': combo_edit_vtype.get(), 'acquire': combo_edit_acquire.get(), 'upgraded': combo_edit_upgrade.get(), 'notes': ent_notes.get()})
                try: car['count'] = int(ent_count.get())
                except: car['count'] = 1 
                
                self.sync_special_from_vehicles(); save_data(self.all_data); self.refresh_vehicle_tables(); self.refresh_garage_table(); self.refresh_special_table(); win.destroy(); self.show_toast_progress("✅ 資產修改成功！")
                self.set_status(f"✏️ 資料庫已更新：【{new_car_name}】屬性修改成功。", "#4CAF50")
                
                idx_str = str(idx)
                final_tree = self.tree_non_personal if car['v_type'] == "非個人載具" else self.tree_vehicles
                if final_tree.exists(idx_str):
                    final_tree.selection_set(idx_str); final_tree.focus(idx_str); final_tree.see(idx_str)
            
            tk.Button(win, text="儲存修改變更 (Enter)", command=save_single, bg="#4CAF50", fg="white", font=FONT_BOLD, relief="flat").pack(pady=15)
            
            ent_name.bind("<Return>", lambda e: combo_edit_garage.focus()); combo_edit_garage.bind("<Return>", lambda e: combo_edit_vtype.focus())
            combo_edit_vtype.bind("<Return>", lambda e: combo_edit_acquire.focus()); combo_edit_acquire.bind("<Return>", lambda e: combo_edit_upgrade.focus())
            combo_edit_upgrade.bind("<Return>", lambda e: ent_count.focus()); ent_count.bind("<Return>", lambda e: ent_notes.focus()); ent_notes.bind("<Return>", save_single)

        else:
            win = tk.Toplevel(self.root); win.title("批量修改車輛資產")
            self.center_toplevel_window(win, 350, 440)
            tk.Label(win, text=f"⚠️ 您正在批量調整 {len(selected)} 筆載具", fg="#e91e63", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG).pack(pady=10)
            
            tk.Label(win, text="1. 批量移動存放位置:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack()
            combo_batch_garage = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]"] + combined_locations); combo_batch_garage.set("[不修改]"); combo_batch_garage.pack(pady=3)
            tk.Label(win, text="2. 批量更改載具類型:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack()
            combo_batch_vtype = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]"] + V_TYPE_OPTIONS); combo_batch_vtype.set("[不修改]"); combo_batch_vtype.pack(pady=3)
            tk.Label(win, text="3. 批量更改取得方式:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack()
            combo_batch_acq = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]"] + ACQUIRE_OPTIONS); combo_batch_acq.set("[不修改]"); combo_batch_acq.pack(pady=3)
            tk.Label(win, text="4. 批量更改改裝狀態:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack()
            combo_batch_upg = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]", "未改滿", "已改滿"]); combo_batch_upg.set("[不修改]"); combo_batch_upg.pack(pady=3)
            var_update_notes = tk.BooleanVar(value=False); tk.Checkbutton(win, text="5. 覆蓋自訂備註", variable=var_update_notes, bg=COLOR_MAIN_BG, fg="white", selectcolor=COLOR_MAIN_BG, font=FONT_BOLD).pack(pady=3)
            ent_batch_notes = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", relief="solid", width=22); ent_batch_notes.pack()
            
            def save_batch(e=None):
                new_g = combo_batch_garage.get(); up_g = (new_g != "[不修改]")
                for item in selected:
                    idx = int(item); car_name = self.data["vehicles"][idx]['name']
                    if up_g and new_g in SUB_CARRIER_RULES and not self.validate_tab1_vehicle_to_garage(car_name, new_g): return
                    if up_g: self.data["vehicles"][idx]['garage'] = new_g
                    if combo_batch_vtype.get() != "[不修改]": self.data["vehicles"][idx]['v_type'] = combo_batch_vtype.get()
                    if combo_batch_acq.get() != "[不修改]": self.data["vehicles"][idx]['acquire'] = combo_batch_acq.get()
                    if combo_batch_upg.get() != "[不修改]": self.data["vehicles"][idx]['upgraded'] = combo_batch_upg.get()
                    if var_update_notes.get(): self.data["vehicles"][idx]['notes'] = ent_batch_notes.get()
                self.sync_special_from_vehicles(); save_data(self.all_data); self.refresh_vehicle_tables(); self.refresh_garage_table(); self.refresh_special_table(); win.destroy(); self.show_toast_progress("✅ 批量更新完畢")
                self.set_status(f"✏️ 批量操作執行完畢：已變更 {len(selected)} 筆載具屬性。", "#2196F3")
                for item in selected:
                    final_t = self.tree_non_personal if self.data["vehicles"][int(item)].get("v_type") == "非個人載具" else self.tree_vehicles
                    if final_t.exists(item): final_t.selection_add(item)
                    if item == selected[0]: final_t.see(item)
            
            tk.Button(win, text="執行批量變更 (Enter)", command=save_batch, bg="#2196F3", fg="white", font=FONT_BOLD, relief="flat").pack(pady=15)
            ent_batch_notes.bind("<Return>", save_batch)

    # ==========================================
    #     🚁 2. 特殊載具分頁
    # ==========================================
    def setup_special_tab(self):
        input_frame = tk.LabelFrame(self.tab_special, text=" 🚁 登記大型特種特殊載具 (可自由指定車庫功能) ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#e91e63", padx=12, pady=12, bd=2)
        input_frame.pack(fill="x", padx=15, pady=10)
        
        tk.Label(input_frame, text="載具名稱:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).pack(side="left", padx=5)
        self.combo_spec_name = ttk.Combobox(input_frame, width=16, state="normal", font=FONT_NORMAL, values=list(SUB_CARRIER_RULES.keys()) + ["機動作戰中心", "復仇者"]); self.combo_spec_name.pack(side="left", padx=5)
        self.combo_spec_name.bind("<KeyRelease>", self.on_main_spec_carrier_changed); self.combo_spec_name.bind("<<ComboboxSelected>>", self.on_main_spec_carrier_changed)
        self.combo_spec_name.bind("<Return>", lambda e: self.combo_inner_car.focus() if str(self.combo_inner_car.cget("state")) != "disabled" else self.add_special())

        self.var_can_store = tk.BooleanVar(value=False)
        self.chk_can_store = tk.Checkbutton(input_frame, text="啟用車庫(可放車)", variable=self.var_can_store, bg=COLOR_CARD_BG, fg="white", selectcolor=COLOR_CARD_BG, font=FONT_BOLD, activebackground=COLOR_CARD_BG, activeforeground="white"); self.chk_can_store.pack(side="left", padx=5)
        
        tk.Label(input_frame, text="內部專屬車輛:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).pack(side="left", padx=5)
        self.combo_inner_car = ttk.Combobox(input_frame, width=14, state="disabled", font=FONT_NORMAL, values=["無"]); self.combo_inner_car.set("無"); self.combo_inner_car.pack(side="left", padx=2)
        self.combo_inner_car.bind("<Return>", lambda e: self.add_special())

        tk.Button(input_frame, text="➕ 建立特殊載具", command=self.add_special, bg="#e91e63", fg="white", font=FONT_BOLD, relief="flat", padx=10).pack(side="left", padx=15)

        tree_frame = tk.Frame(self.tab_special, bg=COLOR_MAIN_BG); tree_frame.pack(fill="both", expand=True, padx=15, pady=10)
        self.tree_special = ttk.Treeview(tree_frame, columns=("name", "inner"), show="headings", selectmode="extended")
        
        columns_config_sp = {"name": "特殊載具名稱", "inner": "內部停放/綁定車輛"}
        for col, text in columns_config_sp.items(): self.tree_special.heading(col, text=text, command=lambda c=col: self.sort_treeview(self.tree_special, c, False))
        self.tree_special.column("name", width=350); self.tree_special.column("inner", width=350)
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
            self.combo_inner_car["values"] = ["無"] + SUB_CARRIER_RULES[carrier]
            if self.combo_inner_car.get() not in self.combo_inner_car["values"]: self.combo_inner_car.set(SUB_CARRIER_RULES[carrier][0])
        else:
            self.chk_can_store.config(state="normal"); self.combo_inner_car.set("無"); self.combo_inner_car.config(state="disabled")

    def add_special(self):
        if not self.data: return
        name = self.combo_spec_name.get().strip(); inner_car = self.combo_inner_car.get().strip(); can_store = self.var_can_store.get()
        if inner_car == "無": inner_car = ""
        if not name: return
        if any(sv['name'].lower() == name.lower() for sv in self.data.get("special_vehicles", [])): return messagebox.showwarning("重複", "⚠️ 此特殊載具已在資產清單中！")

        self.data["special_vehicles"].append({"name": name, "inner_vehicle": inner_car, "can_store": can_store, "locked": False, "pinned": False})
        self.sync_vehicles_from_special(); save_data(self.all_data)
        
        self.refresh_special_table(); self.update_garage_comboboxes(); self.refresh_vehicle_tables() 
        self.combo_spec_name.set(""); self.combo_inner_car.set("無"); self.var_can_store.set(False); self.on_main_spec_carrier_changed()
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
            self.tree_special.insert("", "end", iid=str(idx), values=(display_name, item.get("inner_vehicle", "無") or "無"))

    def toggle_pin_special(self):
        if not self.data: return
        selected = self.tree_special.selection()
        if not selected: return
        new_state = not self.data["special_vehicles"][int(selected[0])].get("pinned", False)
        for item in selected: self.data["special_vehicles"][int(item)]["pinned"] = new_state
        save_data(self.all_data); self.refresh_special_table()
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
            for item in sorted([int(s) for s in selected], reverse=True): 
                old_name = self.data["special_vehicles"][item]["name"]; del self.data["special_vehicles"][item]
                for v in self.data["vehicles"]:
                    if v.get("garage") == old_name: v["garage"] = "未分類"
            save_data(self.all_data); self.refresh_special_table(); self.update_garage_comboboxes(); self.apply_filters()
            self.set_status(f"🗑️ 成功拆解/變賣特殊載具。", "#FF9800")

    def open_special_edit_window(self, event=None):
        if not self.data: return
        selected = self.tree_special.selection()
        if not selected or len(selected) > 1: return 
        idx = int(selected[0])
        if self.data["special_vehicles"][idx].get("locked", False): return messagebox.showwarning("權限限制", "⚠️ 特殊載具鎖定中！")
            
        old_name = self.data["special_vehicles"][idx]["name"]; old_inner = self.data["special_vehicles"][idx].get("inner_vehicle", "") or "無"
        old_can_store = self.data["special_vehicles"][idx].get("can_store", False)
        
        win = tk.Toplevel(self.root); win.title("修改特種載具屬性")
        self.center_toplevel_window(win, 340, 240)
        
        tk.Label(win, text="特種載具資產名稱:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(12,2))
        combo_name = ttk.Combobox(win, state="normal", font=FONT_NORMAL, values=list(SUB_CARRIER_RULES.keys()) + ["機動作戰中心", "復仇者"])
        if old_name not in combo_name["values"]: combo_name["values"] = list(combo_name["values"]) + [old_name]
        combo_name.set(old_name); combo_name.pack()
        
        edit_var_can_store = tk.BooleanVar(value=old_can_store)
        chk_edit_store = tk.Checkbutton(win, text="設為車庫(車輛管理可直接存入)", variable=edit_var_can_store, bg=COLOR_MAIN_BG, fg="white", selectcolor=COLOR_MAIN_BG, font=FONT_BOLD); chk_edit_store.pack(pady=4)
        
        tk.Label(win, text="內部限制綁定車輛:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(5,2))
        combo_inner = ttk.Combobox(win, state="disabled", font=FONT_NORMAL); combo_inner.pack()
        
        def update_edit_inner(event=None):
            c = combo_name.get().strip()
            if c in SUB_CARRIER_RULES:
                edit_var_can_store.set(True); chk_edit_store.config(state="disabled"); combo_inner.config(state="readonly"); combo_inner["values"] = ["無"] + SUB_CARRIER_RULES[c]
                if combo_inner.get() not in combo_inner["values"]: combo_inner.set("無")
            else:
                chk_edit_store.config(state="normal"); combo_inner["values"] = ["無"]; combo_inner.set("無"); combo_inner.config(state="disabled")
                
        combo_name.bind("<KeyRelease>", update_edit_inner); combo_name.bind("<<ComboboxSelected>>", update_edit_inner)
        if old_name in SUB_CARRIER_RULES: combo_inner.config(state="readonly"); combo_inner["values"] = ["無"] + SUB_CARRIER_RULES[old_name]; chk_edit_store.config(state="disabled")
        combo_inner.set(old_inner)
        
        def save(e=None):
            new_name = combo_name.get().strip(); new_inner = combo_inner.get().strip(); new_store = edit_var_can_store.get()
            if new_inner == "無": new_inner = ""
            if not new_name: return
            if new_name != old_name:
                for v in self.data["vehicles"]:
                    if v.get("garage") == old_name: v["garage"] = new_name
            self.data["special_vehicles"][idx].update({"name": new_name, "inner_vehicle": new_inner, "can_store": new_store})
            
            self.sync_vehicles_from_special(); save_data(self.all_data); self.refresh_vehicle_tables(); self.update_garage_comboboxes(); self.refresh_special_table(); win.destroy(); self.show_toast_progress("✅ 特種資產修正完畢")
            self.set_status("✏️ 資料庫已更新：特種載具屬性修改成功。", "#e91e63")
            
            idx_str = str(idx)
            if self.tree_special.exists(idx_str): self.tree_special.see(idx_str); self.tree_special.selection_set(idx_str); self.tree_special.focus(idx_str)
        
        tk.Button(win, text="保存設定變更 (Enter)", command=save, bg="#4CAF50", fg="white", font=FONT_BOLD, relief="flat").pack(pady=12)
        combo_name.bind("<Return>", lambda e: combo_inner.focus() if str(combo_inner.cget("state")) != "disabled" else save(e)); combo_inner.bind("<Return>", save)

    # ==========================================
    #     🏠 3. 車庫管理頁面
    # ==========================================
    def setup_garages_tab(self):
        left_frame = tk.Frame(self.tab_garages, bg=COLOR_MAIN_BG); left_frame.pack(side="left", fill="y", padx=15, pady=10)
        
        tk.Label(left_frame, text="🏠 新增全新房產車庫", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#4CAF50").pack(pady=10)
        tk.Label(left_frame, text="新車庫/物業名稱:", font=FONT_BOLD, bg=COLOR_MAIN_BG, fg="white").pack(anchor="w", pady=2)
        self.entry_new_garage = tk.Entry(left_frame, width=22, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); self.entry_new_garage.pack(pady=5); self.entry_new_garage.bind("<Return>", lambda e: self.add_garage_simple())
        
        self.btn_add_garage = tk.Button(left_frame, text="➕ 登記置產新車庫", command=self.add_garage_simple, bg="#4CAF50", fg="white", font=FONT_BOLD, relief="flat"); self.btn_add_garage.pack(fill="x", pady=15)
        
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

    def add_garage_simple(self):
        if not self.data: return
        name = self.entry_new_garage.get().strip()
        if not name: return
        if name in self.data["garages"]: return messagebox.showerror("錯誤", "物業名稱重複！")
        
        limit = simpledialog.askinteger("設定上限", f"請輸入「{name}」的可停車位容量上限\n(預設 10 車位):", initialvalue=10, minvalue=1, maxvalue=100)
        if not limit: return 
        
        self.data["garages"].append(name); self.data["garage_limits"][name] = limit
        save_data(self.all_data); self.refresh_garage_table(); self.update_garage_comboboxes(); self.entry_new_garage.delete(0, tk.END); self.show_toast_progress(f"🏠 成功購入新車庫：{name}"); self.entry_new_garage.focus()
        self.set_status(f"🏠 房地產中心：成功登記物業【{name}】。", "#4CAF50")

    def refresh_garage_table(self):
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        if not self.data: return
        actual_garages = [g for g in self.data["garages"] if g != "未分類"]
        self.btn_add_garage.config(state="normal", text=f"➕ 購入新物業車庫 ({len(actual_garages)})")
            
        for g in actual_garages:
            limit = self.data["garage_limits"].get(g, 10); usage = self.count_cars_in_garage(g)
            row = tk.Frame(self.scrollable_frame, pady=6, bg=COLOR_MAIN_BG); row.pack(fill="x", expand=True, pady=3)
            tk.Label(row, text=f"▪️ {g}  ({usage} / {limit} 輛)", width=32, anchor="w", font=FONT_BOLD, bg=COLOR_MAIN_BG, fg=COLOR_TEXT_WHITE).pack(side="left")
            pb = ttk.Progressbar(row, length=240, mode="determinate"); pb["maximum"] = limit; pb["value"] = usage; pb.pack(side="left", padx=15)
            if usage >= limit: tk.Label(row, text="⚠️ 爆滿危險", fg="#ff1744", font=FONT_BOLD, bg=COLOR_MAIN_BG).pack(side="left")
            btn_f = tk.Frame(row, bg=COLOR_MAIN_BG); btn_f.pack(side="right", padx=10)
            tk.Button(btn_f, text="修改物業", command=lambda name=g: self.open_garage_edit_window_by_name(name), bg="#3498db", fg="white", font=FONT_NORMAL, relief="flat", padx=5).pack(side="left", padx=3)
            tk.Button(btn_f, text="拆除物業", command=lambda name=g: self.delete_garage_by_name(name), bg="#e74c3c", fg="white", font=FONT_NORMAL, relief="flat", padx=5).pack(side="left", padx=3)

    def delete_garage_by_name(self, g_name):
        if messagebox.askyesno("安全確認", f"您確定要拆除變賣車庫「{g_name}」嗎？\n(車庫內的車輛將自動撤回「未分類」車庫)"):
            if g_name in self.data["garages"]: self.data["garages"].remove(g_name)
            if g_name in self.data["garage_limits"]: del self.data["garage_limits"][g_name]
            for v in self.data["vehicles"]:
                if v.get("garage") == g_name: v["garage"] = "未分類"
            save_data(self.all_data); self.refresh_garage_table(); self.apply_filters(); self.update_garage_comboboxes()
            self.set_status(f"🏠 房地產中心：已成功出售變賣物業【{g_name}】。", "#FF9800")

    def open_garage_edit_window_by_name(self, old_name):
        old_limit = self.data["garage_limits"].get(old_name, 10)
        win = tk.Toplevel(self.root); win.title("編輯車庫房產屬性")
        self.center_toplevel_window(win, 320, 220); win.bind("<Escape>", lambda e: win.destroy()) 
        
        tk.Label(win, text="修改車庫物業名稱:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(15,2))
        ent_name = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=24); ent_name.insert(0, old_name); ent_name.pack(); ent_name.focus()
        tk.Label(win, text="修改車位總量上限:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(10,2))
        ent_limit = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=12); ent_limit.insert(0, str(old_limit)); ent_limit.pack()
        
        def save(e=None):
            new_name = ent_name.get().strip()
            try: new_limit = int(ent_limit.get().strip() or 10)
            except: new_limit = 10
            if new_name != old_name and new_name in self.data["garages"]: return messagebox.showerror("錯誤", "物業名稱已存在！")
            if new_limit < self.count_cars_in_garage(old_name): return messagebox.showerror("錯誤", "車位不可小於目前停放車數！")
            
            idx = self.data["garages"].index(old_name)
            self.data["garages"][idx] = new_name; self.data["garage_limits"][new_name] = new_limit
            if new_name != old_name:
                del self.data["garage_limits"][old_name]
                for v in self.data["vehicles"]:
                    if v.get("garage") == old_name: v["garage"] = new_name
            save_data(self.all_data); self.refresh_garage_table(); self.refresh_vehicle_tables(); self.update_garage_comboboxes(); win.destroy()
            self.set_status(f"✏️ 房地產中心：已更新物業【{new_name}】的屬性。", "#3498db")
            
        tk.Button(win, text="確認保存修改 (Enter)", command=save, bg="#4CAF50", fg="white", font=FONT_BOLD, relief="flat").pack(pady=15)
        ent_name.bind("<Return>", lambda e: ent_limit.focus()); ent_limit.bind("<Return>", save)

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
