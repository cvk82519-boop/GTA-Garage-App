import json
import os
import time
import shutil
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

DATA_FILE = "gta5_garage_data.json"
ACQUIRE_OPTIONS = ["購買獲得", "任務獲得", "生涯成就", "賭場轉盤", "搶劫獲得", "車友會", "其他備註"]
V_TYPE_OPTIONS = ["個人載具", "非個人載具"]

# --- 浮動註解 (Tooltip) 核心 ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<Destroy>", self.leave) 

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        if self.widget.winfo_exists():
            self.id = self.widget.after(400, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id: self.widget.after_cancel(id)

    def showtip(self, event=None):
        if not self.widget.winfo_exists() or not self.text: return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#2b2b2b", foreground="white", relief=tk.SOLID, borderwidth=0,
                         font=("Microsoft JhengHei", 9, "normal"), padx=8, pady=4)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw and tw.winfo_exists(): tw.destroy()

def add_tooltip(widget, text):
    ToolTip(widget, text)

# --- 資料處理核心 ---
def load_data():
    default_structure = {"profiles": {}}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "vehicles" in data and "profiles" not in data:
                    if "special_vehicles" not in data: data["special_vehicles"] = []
                    return {"profiles": {"已移轉帳號": data}}
                if isinstance(data, dict) and "profiles" in data:
                    return data
        except: 
            return default_structure
    return default_structure

def save_data(all_data):
    for p_name, p_data in all_data.get("profiles", {}).items():
        if "garages" not in p_data: 
            p_data["garages"] = ["未分類", "日蝕大樓 1 號", "辦公室車庫", "名鑽賭場空中別墅", "設施"]
        if "未分類" not in p_data["garages"]: 
            p_data["garages"].insert(0, "未分類")
            
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)

class GTAGarageApp:
    def __init__(self, root):
        self.root = root
        self.root.title("洛聖都資產管理系統 (置頂與安全鎖定旗艦版)")
        self.root.geometry("1200x750") # 加寬以完美容納新欄位
        self.root.resizable(False, False)
        
        self.all_data = load_data()
        self.current_id = ""
        self.data = None

        self.is_running = False
        self.start_time = 0.0
        self.elapsed_time = 0.0
        self.stopwatch_job = None

        self.setup_profile_bar()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.tab_vehicles = ttk.Frame(self.notebook)
        self.tab_special = ttk.Frame(self.notebook)
        self.tab_elite = ttk.Frame(self.notebook) 
        self.tab_garages = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_vehicles, text=" 🚗 車輛管理 ")
        self.notebook.add(self.tab_special, text=" 🚁 特殊載具 ")
        self.notebook.add(self.tab_elite, text=" 🌟 菁英專區 ")
        self.notebook.add(self.tab_garages, text=" 🏠 車庫管理 ")

        self.setup_vehicles_tab()
        self.setup_special_tab()
        self.setup_elite_tab()
        self.setup_garages_tab()

        self.root.bind("<Pause>", self.toggle_stopwatch)
        self.check_login_status()

    def center_toplevel_window(self, win, width, height):
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.resizable(False, False)

    # ==========================================
    #   🔒 核心權限鎖定與登入/登出管理系統
    # ==========================================
    def setup_profile_bar(self):
        top_frame = tk.Frame(self.root, bg="#3b3b3b", pady=8)
        top_frame.pack(fill="x", side="top")
        
        tk.Label(top_frame, text="👤 ID:", bg="#3b3b3b", fg="white", font=("Arial", 11, "bold")).pack(side="left", padx=(10, 5))
        
        self.combo_profile = ttk.Combobox(top_frame, state="readonly", width=18, font=("Arial", 10))
        self.combo_profile.pack(side="left", padx=5)
        add_tooltip(self.combo_profile, "點擊選擇要操作的遊戲 ID")
        
        self.btn_login = tk.Button(top_frame, text="🔑 登入", command=self.login_profile, bg="#4CAF50", fg="white", font=("Arial", 9, "bold"))
        self.btn_login.pack(side="left", padx=3)
        add_tooltip(self.btn_login, "登入以解鎖該 ID 的資料庫操作權限")
        
        self.btn_logout = tk.Button(top_frame, text="🚪 登出", command=self.logout_profile, bg="#FF9800", fg="white", font=("Arial", 9, "bold"))
        self.btn_logout.pack(side="left", padx=3)
        add_tooltip(self.btn_logout, "安全登出，關閉並鎖定所有資料庫")
        
        self.btn_transfer = tk.Button(top_frame, text="🔄 轉移", command=self.transfer_data, bg="#9C27B0", fg="white", font=("Arial", 9, "bold"))
        self.btn_transfer.pack(side="left", padx=10)
        add_tooltip(self.btn_transfer, "將當前帳號的車輛轉移給其他帳號")
        
        self.btn_delete_profile = tk.Button(top_frame, text="🗑 刪除ID", command=self.delete_profile, bg="#f44336", fg="white", font=("Arial", 9, "bold"))
        self.btn_delete_profile.pack(side="right", padx=10)
        add_tooltip(self.btn_delete_profile, "永久刪除當前登入的 ID 與所有資料 (危險操作)")
        
        self.btn_create_profile = tk.Button(top_frame, text="➕ 新建ID", command=self.create_profile, bg="#2196F3", fg="white", font=("Arial", 9, "bold"))
        self.btn_create_profile.pack(side="right", padx=5)
        add_tooltip(self.btn_create_profile, "建立一個全新的空白帳號")

        self.btn_restore = tk.Button(top_frame, text="📂 還原", command=self.restore_data, bg="#607D8B", fg="white", font=("Arial", 9, "bold"))
        self.btn_restore.pack(side="right", padx=5)
        add_tooltip(self.btn_restore, "讀取備份檔，並覆蓋還原至當前登入的 ID")
        
        self.btn_backup = tk.Button(top_frame, text="💾 備份", command=self.backup_data, bg="#607D8B", fg="white", font=("Arial", 9, "bold"))
        self.btn_backup.pack(side="right", padx=5)
        add_tooltip(self.btn_backup, "匯出當前 ID 的資料為備份檔 (.json)")
        
        self.update_profile_combo()

    def update_profile_combo(self):
        profiles = list(self.all_data.get("profiles", {}).keys())
        self.combo_profile["values"] = profiles
        if self.current_id: self.combo_profile.set(self.current_id)
        else: self.combo_profile.set("")

    def check_login_status(self):
        is_logged_in = bool(self.current_id and self.current_id in self.all_data["profiles"])
        state_str = "normal" if is_logged_in else "disabled"
        
        if is_logged_in:
            self.data = self.all_data["profiles"][self.current_id]
            self.btn_login.config(state="disabled") 
            self.combo_profile.config(state="disabled") 
        else:
            self.current_id = ""
            self.data = None
            self.btn_login.config(state="normal")
            self.combo_profile.config(state="readonly") 

        for tab in [self.tab_vehicles, self.tab_special, self.tab_elite, self.tab_garages]:
            self.notebook.tab(tab, state=state_str)
            
        for btn in [self.btn_delete_profile, self.btn_logout, self.btn_transfer, self.btn_backup, self.btn_restore]:
            btn.config(state=state_str)
            
        self.update_garage_comboboxes()
        self.refresh_vehicle_table()
        self.refresh_special_table()
        self.refresh_garage_table()

    def login_profile(self):
        selected = self.combo_profile.get()
        if not selected:
            messagebox.showwarning("提示", "請先選擇一個遊戲 ID！")
            return
        if selected in self.all_data["profiles"]:
            self.current_id = selected
            self.check_login_status()
            self.show_toast_progress(f"🔑 登入成功：{self.current_id}")

    def logout_profile(self):
        if not self.current_id: return
        self.current_id = ""
        self.check_login_status()
        self.combo_profile.set("") 
        self.show_toast_progress("🚪 帳號已登出，系統已上鎖")

    def create_profile(self):
        win = tk.Toplevel(self.root)
        win.title("建立新遊戲 ID")
        self.center_toplevel_window(win, 320, 150)
        
        tk.Label(win, text="請輸入新的遊戲 ID / 角色名稱:", font=("Arial", 10, "bold")).pack(pady=15)
        ent = tk.Entry(win, width=25, font=("Arial", 10))
        ent.pack(pady=5); ent.focus()
        
        def save_new(e=None):
            name = ent.get().strip()
            if not name: return
            if name in self.all_data["profiles"]:
                messagebox.showwarning("名稱重複", "此 ID 已經存在！")
                return
            self.all_data["profiles"][name] = {
                "vehicles": [], "special_vehicles": [],
                "garages": ["未分類", "日蝕大樓 1 號", "辦公室車庫", "名鑽賭場空中別墅", "設施"]
            }
            save_data(self.all_data)
            self.update_profile_combo()
            self.combo_profile.set(name)
            win.destroy()
            messagebox.showinfo("建立成功", f"🆕 成功建立 ID：{name}\n\n👉 請點擊「🔑 登入」按鈕解鎖！")
            
        btn_confirm = tk.Button(win, text="確認建立 (Enter)", command=save_new, bg="#4CAF50", fg="white", width=15)
        btn_confirm.pack(pady=10)
        win.bind("<Return>", save_new)

    def delete_profile(self):
        if not self.current_id: return
        if messagebox.askyesno("🚨 危險刪除確認", f"您確定要刪除當前登入的 ID【{self.current_id}】嗎？"):
            del self.all_data["profiles"][self.current_id]
            self.current_id = ""
            save_data(self.all_data)
            self.update_profile_combo()
            self.check_login_status()
            self.show_toast_progress("🗑️ 帳號已永久刪除")

    def backup_data(self):
        if not self.current_id: return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile=f"{self.current_id}_備份檔.json", 
            title="儲存設定檔 (僅備份當前 ID)", filetypes=[("JSON Files", "*.json")]
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=4)
                self.show_toast_progress(f"💾 {self.current_id} 備份成功！")
            except Exception as e: messagebox.showerror("錯誤", f"備份失敗：{e}")

    def restore_data(self):
        if not self.current_id: return
        file_path = filedialog.askopenfilename(title="選擇還原設定檔", filetypes=[("JSON Files", "*.json")])
        if file_path:
            if messagebox.askyesno("⚠️ 危險操作", f"將【完全覆蓋】當前 ID「{self.current_id}」的所有資料，繼續嗎？"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f: imported_data = json.load(f)
                    if "vehicles" not in imported_data or "garages" not in imported_data:
                        messagebox.showerror("錯誤", "檔案格式不正確，無法還原！")
                        return
                    self.all_data["profiles"][self.current_id] = imported_data
                    self.data = self.all_data["profiles"][self.current_id]
                    save_data(self.all_data)
                    self.check_login_status()
                    self.show_toast_progress(f"📂 {self.current_id} 還原成功！")
                except Exception as e: messagebox.showerror("錯誤", f"還原失敗：{e}")

    def transfer_data(self):
        if not self.current_id: return
        other_ids = [pid for pid in self.all_data["profiles"] if pid != self.current_id]
        if not other_ids:
            messagebox.showwarning("提示", "目前沒有其他可供接收的遊戲 ID。")
            return
            
        win = tk.Toplevel(self.root); win.title("資料轉移作業")
        self.center_toplevel_window(win, 380, 200)
        tk.Label(win, text=f"將【{self.current_id}】的車輛轉移至：", font=("Arial", 11, "bold")).pack(pady=15)
        combo_target = ttk.Combobox(win, state="readonly", values=other_ids, width=25, font=("Arial", 10))
        combo_target.pack(pady=5)
        
        def execute_transfer():
            target = combo_target.get()
            if not target: return
            if messagebox.askyesno("確認轉移", f"確定要將資料轉移到【{target}】嗎？\n(當前 ID 清單將會清空)"):
                self.all_data["profiles"][target]["vehicles"].extend(self.data["vehicles"])
                self.data["vehicles"] = []
                if "special_vehicles" not in self.all_data["profiles"][target]:
                    self.all_data["profiles"][target]["special_vehicles"] = []
                self.all_data["profiles"][target]["special_vehicles"].extend(self.data.get("special_vehicles", []))
                self.data["special_vehicles"] = []
                
                save_data(self.all_data)
                self.refresh_vehicle_table()
                self.refresh_special_table()
                win.destroy()
                self.show_toast_progress(f"🔄 成功轉移至：{target}")
        
        tk.Button(win, text="確認執行轉移", command=execute_transfer, bg="#9C27B0", fg="white", font=("Arial", 10, "bold"), width=15).pack(pady=15)

    # ==========================================
    #     🌟 菁英專區 (任務碼錶功能)
    # ==========================================
    def setup_elite_tab(self):
        title_frame = tk.Frame(self.tab_elite)
        title_frame.pack(pady=(20, 10))
        tk.Label(title_frame, text="🌟 菁英專區 - 任務碼錶", font=("Microsoft JhengHei", 24, "bold"), fg="#FF9800").pack()
        tk.Label(title_frame, text="在遊戲中隨時按下鍵盤的【Pause】鍵即可開始/暫停計時！", font=("Microsoft JhengHei", 12), fg="gray").pack(pady=5)

        timer_frame = tk.Frame(self.tab_elite, bg="#1e1e1e", bd=5, relief="ridge")
        timer_frame.pack(pady=20, padx=50, fill="x")
        self.lbl_stopwatch = tk.Label(timer_frame, text="00:00.00", font=("Consolas", 65, "bold"), bg="#1e1e1e", fg="#4CAF50")
        self.lbl_stopwatch.pack(pady=30)
        
        btn_frame = tk.Frame(self.tab_elite)
        btn_frame.pack(pady=10)
        btn_sw = tk.Button(btn_frame, text="▶ 開始 / 暫停 (Pause)", command=self.toggle_stopwatch, font=("Arial", 12, "bold"), bg="#2196F3", fg="white", width=20)
        btn_sw.pack(side="left", padx=10)
        add_tooltip(btn_sw, "可以按下鍵盤上的 Pause 鍵來遙控碼錶")
        
        btn_rst = tk.Button(btn_frame, text="🔄 重置歸零", command=self.reset_stopwatch, font=("Arial", 12, "bold"), bg="#f44336", fg="white", width=15)
        btn_rst.pack(side="left", padx=10)
        add_tooltip(btn_rst, "將碼錶時間歸零")

    def toggle_stopwatch(self, event=None):
        if not self.current_id: return 
        if self.is_running:
            self.is_running = False
            self.elapsed_time += time.time() - self.start_time
            if self.stopwatch_job:
                self.root.after_cancel(self.stopwatch_job)
                self.stopwatch_job = None
            self.lbl_stopwatch.config(fg="#FF9800")
        else:
            self.is_running = True
            self.start_time = time.time()
            self.lbl_stopwatch.config(fg="#4CAF50")
            self.update_stopwatch()

    def update_stopwatch(self):
        if self.is_running:
            current_elapsed = self.elapsed_time + (time.time() - self.start_time)
            mins = int(current_elapsed // 60); secs = int(current_elapsed % 60); millis = int((current_elapsed * 100) % 100)
            self.lbl_stopwatch.config(text=f"{mins:02d}:{secs:02d}.{millis:02d}")
            self.stopwatch_job = self.root.after(50, self.update_stopwatch)

    def reset_stopwatch(self):
        self.is_running = False
        self.elapsed_time = 0.0
        if self.stopwatch_job:
            self.root.after_cancel(self.stopwatch_job)
            self.stopwatch_job = None
        self.lbl_stopwatch.config(text="00:00.00", fg="#4CAF50")

    def show_toast_progress(self, message="✅ 操作成功"):
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + self.root.winfo_width() - 260 - 20
        y = self.root.winfo_rooty() + self.root.winfo_height() - 65 - 20
        toast.geometry(f"260x65+{x}+{y}")
        frame = tk.Frame(toast, bg="#2b2b2b", highlightbackground="#4CAF50", highlightthickness=2)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=message, bg="#2b2b2b", fg="white", font=("Microsoft JhengHei", 10, "bold")).pack(pady=(6, 2))
        progress = ttk.Progressbar(frame, orient="horizontal", length=220, mode="determinate")
        progress.pack(pady=(0, 6))
        def step(val):
            if val <= 100:
                progress["value"] = val
                toast.after(15, step, val + 5)
            else:
                toast.after(600, toast.destroy)
        step(0)

    # ==========================================
    #     🚗 1. 車輛管理 (防呆鎖定、置頂、類型)
    # ==========================================
    def setup_vehicles_tab(self):
        input_frame = tk.LabelFrame(self.tab_vehicles, text=" 📝 登記新車輛 ", padx=10, pady=10)
        input_frame.pack(fill="x", padx=15, pady=10)

        tk.Label(input_frame, text="名稱:").grid(row=0, column=0, sticky="e")
        self.entry_name = tk.Entry(input_frame, width=12)
        self.entry_name.grid(row=0, column=1, padx=2)
        self.entry_name.bind("<Return>", lambda e: self.add_vehicle())
        add_tooltip(self.entry_name, "輸入車輛名稱 (按 Enter 可直接新增)")

        tk.Label(input_frame, text="車庫:").grid(row=0, column=2, sticky="e")
        self.combo_garage = ttk.Combobox(input_frame, width=12, state="readonly")
        self.combo_garage.grid(row=0, column=3, padx=2)
        add_tooltip(self.combo_garage, "選擇車輛停放的車庫")

        tk.Label(input_frame, text="類型:").grid(row=0, column=4, sticky="e")
        self.combo_vtype = ttk.Combobox(input_frame, width=8, state="readonly", values=V_TYPE_OPTIONS)
        self.combo_vtype.set("個人載具")
        self.combo_vtype.grid(row=0, column=5, padx=2)
        add_tooltip(self.combo_vtype, "標記是否為可呼叫的個人載具")

        tk.Label(input_frame, text="取得:").grid(row=0, column=6, sticky="e")
        self.combo_acquire = ttk.Combobox(input_frame, width=9, state="readonly", values=ACQUIRE_OPTIONS)
        self.combo_acquire.set("購買獲得")
        self.combo_acquire.grid(row=0, column=7, padx=2)
        add_tooltip(self.combo_acquire, "車輛的來源方式")

        tk.Label(input_frame, text="改裝:").grid(row=0, column=8, sticky="e")
        self.combo_upgrade = ttk.Combobox(input_frame, width=6, state="readonly", values=["未改滿", "已改滿"])
        self.combo_upgrade.set("未改滿")
        self.combo_upgrade.grid(row=0, column=9, padx=2)
        add_tooltip(self.combo_upgrade, "標記是否已經進行全套改裝")

        btn_add = tk.Button(input_frame, text="➕新增", command=self.add_vehicle, bg="#4CAF50", fg="white")
        btn_add.grid(row=0, column=10, padx=8)
        
        btn_batch = tk.Button(input_frame, text="📦批量", command=self.open_batch_import_window, bg="#2196F3", fg="white")
        btn_batch.grid(row=0, column=11, padx=2)

        action_frame = tk.Frame(self.tab_vehicles)
        action_frame.pack(fill="x", padx=15, pady=5)
        tk.Label(action_frame, text="🔍 搜尋:").pack(side="left")
        self.entry_search = tk.Entry(action_frame, width=15)
        self.entry_search.pack(side="left", padx=5)
        self.entry_search.bind("<KeyRelease>", lambda e: self.apply_filters())
        
        tk.Label(action_frame, text=" | 篩選車庫:").pack(side="left", padx=5)
        self.combo_garage_filter = ttk.Combobox(action_frame, width=15, state="readonly")
        self.combo_garage_filter.pack(side="left", padx=5)
        self.combo_garage_filter.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())
        
        btn_reset = tk.Button(action_frame, text="重置", command=self.reset_filters)
        btn_reset.pack(side="left", padx=5)

        tree_frame = tk.Frame(self.tab_vehicles)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        self.tree_vehicles = ttk.Treeview(tree_frame, columns=("name", "garage", "vtype", "acquire", "upgrade", "count", "notes"), show="headings", selectmode="extended")
        self.tree_vehicles.heading("name", text="車輛名稱"); self.tree_vehicles.heading("garage", text="存放車庫")
        self.tree_vehicles.heading("vtype", text="類型"); self.tree_vehicles.heading("acquire", text="取得方式")
        self.tree_vehicles.heading("upgrade", text="改裝"); self.tree_vehicles.heading("count", text="數量"); self.tree_vehicles.heading("notes", text="備註")
        
        self.tree_vehicles.column("vtype", width=80, anchor="center")
        self.tree_vehicles.column("acquire", width=80, anchor="center")
        self.tree_vehicles.column("upgrade", width=60, anchor="center")
        self.tree_vehicles.column("count", width=40, anchor="center")
        
        self.tree_vehicles.bind("<Double-1>", lambda e: self.open_edit_window())
        self.tree_vehicles.bind("<Delete>", self.delete_vehicle)
        add_tooltip(self.tree_vehicles, "左鍵雙擊可編輯；右鍵可解鎖/鎖定/置頂")
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_vehicles.yview)
        self.tree_vehicles.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y"); self.tree_vehicles.pack(side="left", fill="both", expand=True)
        
        self.vehicle_popup_menu = tk.Menu(self.root, tearoff=0)
        self.tree_vehicles.bind("<Button-3>", self.show_vehicle_context_menu)

    def update_garage_comboboxes(self):
        if not self.data:
            self.combo_garage["values"] = []
            self.combo_garage_filter["values"] = ["全部"]
            self.combo_garage_filter.set("全部")
            return
        garages = ["全部"] + self.data["garages"]
        self.combo_garage["values"] = [g for g in self.data["garages"] if g != "未分類"]
        self.combo_garage_filter["values"] = garages
        if self.combo_garage_filter.get() == "": self.combo_garage_filter.set("全部")

    def refresh_vehicle_table(self, search_results=None):
        for i in self.tree_vehicles.get_children(): self.tree_vehicles.delete(i)
        if not self.data: return
        
        data_to_sort = search_results if search_results is not None else enumerate(self.data["vehicles"])
        
        # 📌 分離出置頂與未置頂的資料 (保持原有 idx 作為 iid 以防錯位)
        pinned_items = []
        normal_items = []
        for idx, car in data_to_sort:
            if car.get("pinned", False): pinned_items.append((idx, car))
            else: normal_items.append((idx, car))
            
        # 先顯示置頂，再顯示一般
        for idx, car in pinned_items + normal_items:
            display_name = car["name"]
            if car.get("locked", False): display_name = "🔒 " + display_name
            if car.get("pinned", False): display_name = "📌 " + display_name
            
            vt = car.get("v_type", "個人載具")
            acq = car.get("acquire", "購買獲得")
            upg = car.get("upgraded", "未改滿")
            self.tree_vehicles.insert("", "end", iid=str(idx), values=(display_name, car["garage"], vt, acq, upg, car.get("count", 1), car["notes"]))

    def add_vehicle(self):
        if not self.data: return
        name = self.entry_name.get().strip()
        garage = self.combo_garage.get() or "未分類"
        if not name: return
        
        self.data["vehicles"].append({
            "name": name, "garage": garage, 
            "v_type": self.combo_vtype.get(),
            "acquire": self.combo_acquire.get(), 
            "upgraded": self.combo_upgrade.get(),
            "count": 1, "notes": "無",
            "locked": False, "pinned": False # 預設狀態
        })
        save_data(self.all_data)
        
        self.entry_search.delete(0, tk.END); self.combo_garage_filter.set("全部")
        self.refresh_vehicle_table()
        
        new_iid = str(len(self.data["vehicles"]) - 1)
        if self.tree_vehicles.exists(new_iid):
            self.tree_vehicles.selection_set(new_iid); self.tree_vehicles.see(new_iid)           
            
        self.entry_name.delete(0, tk.END)
        self.show_toast_progress("🚗 車輛新增成功！")

    def delete_vehicle(self, event=None):
        if not self.data: return
        selected = self.tree_vehicles.selection()
        if not selected: return
        
        # 🛡️ 防刪除鎖定檢查
        for item in selected:
            if self.data["vehicles"][int(item)].get("locked", False):
                messagebox.showwarning("安全鎖定限制", "⚠️ 您選取的資料中包含【已鎖定】的車輛，系統拒絕刪除！\n請先按右鍵解除鎖定再操作。")
                return
                
        if messagebox.askyesno("確認刪除", f"確定要刪除選定的 【 {len(selected)} 】 筆車輛嗎？"):
            for item in sorted([int(s) for s in selected], reverse=True): del self.data["vehicles"][item]
            save_data(self.all_data); self.apply_filters()

    def toggle_pin_vehicle(self):
        if not self.data: return
        selected = self.tree_vehicles.selection()
        if not selected: return
        new_state = not self.data["vehicles"][int(selected[0])].get("pinned", False)
        for item in selected: self.data["vehicles"][int(item)]["pinned"] = new_state
        save_data(self.all_data); self.apply_filters()
        self.show_toast_progress(f"📌 已{'置頂' if new_state else '取消置頂'} {len(selected)} 筆車輛")

    def toggle_lock_vehicle(self):
        if not self.data: return
        selected = self.tree_vehicles.selection()
        if not selected: return
        new_state = not self.data["vehicles"][int(selected[0])].get("locked", False)
        for item in selected: self.data["vehicles"][int(item)]["locked"] = new_state
        save_data(self.all_data); self.apply_filters()
        self.show_toast_progress(f"🔒 已{'鎖定' if new_state else '解鎖'} {len(selected)} 筆車輛")

    def apply_filters(self):
        if not self.data: return
        kw = self.entry_search.get().lower()
        selected_garage = self.combo_garage_filter.get()
        filtered = [(i, c) for i, c in enumerate(self.data["vehicles"]) 
                    if (kw in c["name"].lower() or kw in c["garage"].lower()) 
                    and (selected_garage in ["全部", ""] or c["garage"] == selected_garage)]
        self.refresh_vehicle_table(search_results=filtered)

    def reset_filters(self):
        if not self.data: return
        self.entry_search.delete(0, tk.END); self.combo_garage_filter.set("全部"); self.refresh_vehicle_table()

    def show_vehicle_context_menu(self, event):
        if not self.data: return
        item = self.tree_vehicles.identify_row(event.y)
        if item: 
            if item not in self.tree_vehicles.selection(): self.tree_vehicles.selection_set(item)
            sel_count = len(self.tree_vehicles.selection())
            
            # 動態重建右鍵選單
            self.vehicle_popup_menu.delete(0, tk.END)
            self.vehicle_popup_menu.add_command(label=f"✏️編輯 ({sel_count} 筆)", command=self.open_edit_window)
            self.vehicle_popup_menu.add_separator()
            self.vehicle_popup_menu.add_command(label="📌 置頂 / 取消置頂", command=self.toggle_pin_vehicle)
            self.vehicle_popup_menu.add_command(label="🔒 鎖定 / 解鎖", command=self.toggle_lock_vehicle)
            self.vehicle_popup_menu.add_separator()
            self.vehicle_popup_menu.add_command(label=f"🗑刪除 ({sel_count} 筆)", command=self.delete_vehicle)
            
            self.vehicle_popup_menu.post(event.x_root, event.y_root)

    # --- 2. 🚁 特殊載具分頁 (防呆與置頂支援) ---
    def setup_special_tab(self):
        input_frame = tk.LabelFrame(self.tab_special, text=" 🚁 登記特殊載具 (無法進車庫) ", padx=10, pady=10)
        input_frame.pack(fill="x", padx=15, pady=10)
        
        tk.Label(input_frame, text="載具名稱:").pack(side="left", padx=5)
        self.ent_spec_name = tk.Entry(input_frame, width=25)
        self.ent_spec_name.pack(side="left", padx=5)
        self.ent_spec_name.bind("<Return>", lambda e: self.add_special())
        
        btn_add = tk.Button(input_frame, text="➕ 新增 (Enter)", command=self.add_special, bg="#E91E63", fg="white")
        btn_add.pack(side="left", padx=10)

        tree_frame = tk.Frame(self.tab_special)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        self.tree_special = ttk.Treeview(tree_frame, columns=("name",), show="headings", selectmode="extended")
        self.tree_special.heading("name", text="特殊載具名稱")
        self.tree_special.pack(side="left", fill="both", expand=True)
        self.tree_special.bind("<Double-1>", self.open_special_edit_window)
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_special.yview)
        self.tree_special.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        
        self.special_popup_menu = tk.Menu(self.root, tearoff=0)
        self.tree_special.bind("<Button-3>", self.show_special_context_menu)
        self.tree_special.bind("<Delete>", self.delete_special)

    def add_special(self):
        if not self.data: return
        name = self.ent_spec_name.get().strip()
        if not name: return
        if any(sv['name'].lower() == name.lower() for sv in self.data.get("special_vehicles", [])):
            messagebox.showwarning("重複", "⚠️ 特殊載具已存在清單中！")
            return
            
        self.data["special_vehicles"].append({"name": name, "locked": False, "pinned": False})
        save_data(self.all_data)
        self.refresh_special_table()
        self.ent_spec_name.delete(0, tk.END)
        self.show_toast_progress("🚁 特殊載具新增成功！")

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
            self.tree_special.insert("", "end", iid=str(idx), values=(display_name,))

    def toggle_pin_special(self):
        if not self.data: return
        selected = self.tree_special.selection()
        if not selected: return
        new_state = not self.data["special_vehicles"][int(selected[0])].get("pinned", False)
        for item in selected: self.data["special_vehicles"][int(item)]["pinned"] = new_state
        save_data(self.all_data); self.refresh_special_table()
        
    def toggle_lock_special(self):
        if not self.data: return
        selected = self.tree_special.selection()
        if not selected: return
        new_state = not self.data["special_vehicles"][int(selected[0])].get("locked", False)
        for item in selected: self.data["special_vehicles"][int(item)]["locked"] = new_state
        save_data(self.all_data); self.refresh_special_table()

    def show_special_context_menu(self, event):
        if not self.data: return
        item = self.tree_special.identify_row(event.y)
        if item:
            if item not in self.tree_special.selection(): self.tree_special.selection_set(item)
            self.special_popup_menu.delete(0, tk.END)
            self.special_popup_menu.add_command(label="✏️編輯", command=self.open_special_edit_window)
            self.special_popup_menu.add_separator()
            self.special_popup_menu.add_command(label="📌 置頂 / 取消置頂", command=self.toggle_pin_special)
            self.special_popup_menu.add_command(label="🔒 鎖定 / 解鎖", command=self.toggle_lock_special)
            self.special_popup_menu.add_separator()
            self.special_popup_menu.add_command(label="🗑刪除", command=self.delete_special)
            self.special_popup_menu.post(event.x_root, event.y_root)

    def delete_special(self, event=None):
        if not self.data: return
        selected = self.tree_special.selection()
        if not selected: return
        
        for item in selected:
            if self.data["special_vehicles"][int(item)].get("locked", False):
                messagebox.showwarning("鎖定警告", "⚠️ 無法刪除【已鎖定】的載具！")
                return
                
        if messagebox.askyesno("確認刪除", f"確定要刪除選定的特殊載具嗎？"):
            for item in sorted([int(s) for s in selected], reverse=True): del self.data["special_vehicles"][item]
            save_data(self.all_data); self.refresh_special_table()

    def open_special_edit_window(self, event=None):
        if not self.data: return
        selected = self.tree_special.selection()
        if not selected or len(selected) > 1: return 
        
        idx = int(selected[0])
        if self.data["special_vehicles"][idx].get("locked", False):
            messagebox.showwarning("鎖定警告", "⚠️ 此載具已被鎖定，無法修改名稱！\n請先解鎖。")
            return
            
        old_name = self.data["special_vehicles"][idx]["name"]
        win = tk.Toplevel(self.root); win.title("修改特殊載具"); self.center_toplevel_window(win, 300, 120)
        
        tk.Label(win, text="載具名稱:").pack(pady=(10,2))
        ent = tk.Entry(win, width=25); ent.insert(0, old_name); ent.pack(); ent.focus()
        
        def save(e=None):
            new_name = ent.get().strip()
            if not new_name or new_name == old_name: win.destroy(); return
            self.data["special_vehicles"][idx]["name"] = new_name
            save_data(self.all_data); self.refresh_special_table(); win.destroy()
            self.show_toast_progress("✅ 修改成功！")
            
        tk.Button(win, text="儲存 (Enter)", command=save, bg="#4CAF50", fg="white").pack(pady=10)
        win.bind("<Return>", save)

    # --- 3. 車庫管理頁面 ---
    def setup_garages_tab(self):
        btn_frame = tk.Frame(self.tab_garages); btn_frame.pack(fill="x", padx=10, pady=10)
        
        self.entry_new_garage = tk.Entry(btn_frame, width=20)
        self.entry_new_garage.pack(side="left", padx=5)
        self.entry_new_garage.bind("<Return>", lambda e: self.add_garage_simple())
        
        btn_add = tk.Button(btn_frame, text="➕新增車庫", command=self.add_garage_simple)
        btn_add.pack(side="left", padx=5)
        
        self.tree_garages = ttk.Treeview(self.tab_garages, columns=("name",), show="headings")
        self.tree_garages.pack(fill="both", expand=True, padx=10)
        self.tree_garages.heading("name", text="已登記車庫")
        
        self.tree_garages.bind("<Double-1>", self.open_garage_edit_window)
        self.tree_garages.bind("<Button-3>", self.show_garage_context_menu)
        self.garage_popup_menu = tk.Menu(self.root, tearoff=0)
        self.garage_popup_menu.add_command(label="✏️重新命名", command=self.open_garage_edit_window)
        self.garage_popup_menu.add_command(label="🗑 刪除", command=self.delete_garage)

    def add_garage_simple(self):
        if not self.data: return
        name = self.entry_new_garage.get().strip()
        if name and name not in self.data["garages"]:
            self.data["garages"].append(name); save_data(self.all_data); self.refresh_garage_table(); self.update_garage_comboboxes(); self.entry_new_garage.delete(0, tk.END)
            self.show_toast_progress("🏠 車庫新增成功！")

    def delete_garage(self):
        if not self.data: return
        selected = self.tree_garages.selection()
        if selected and messagebox.askyesno("確認", f"確定刪除選定的 {len(selected)} 筆車庫？"):
            for item in selected:
                g_name = self.tree_garages.item(item, "values")[0]
                if g_name in self.data["garages"]: self.data["garages"].remove(g_name)
            save_data(self.all_data); self.refresh_garage_table(); self.apply_filters(); self.update_garage_comboboxes()

    def show_garage_context_menu(self, event):
        if not self.data: return
        item = self.tree_garages.identify_row(event.y)
        if item: 
            if item not in self.tree_garages.selection(): self.tree_garages.selection_set(item)
            self.garage_popup_menu.post(event.x_root, event.y_root)

    def refresh_garage_table(self):
        for i in self.tree_garages.get_children(): self.tree_garages.delete(i)
        if not self.data: return
        for g in self.data.get("garages", []):
            if g != "未分類": self.tree_garages.insert("", "end", values=(g,))

    def open_garage_edit_window(self, event=None):
        if not self.data: return
        selected = self.tree_garages.selection()
        if not selected or len(selected) > 1: return
        old_name = self.tree_garages.item(selected[0], "values")[0]
        
        win = tk.Toplevel(self.root); win.title("重新命名車庫"); self.center_toplevel_window(win, 300, 150)
        
        tk.Label(win, text="修改車庫名稱 (將自動同步所有關聯車輛):").pack(pady=(15,5))
        ent = tk.Entry(win, width=25); ent.insert(0, old_name); ent.pack(); ent.focus()
        
        def save(e=None):
            new_name = ent.get().strip()
            if not new_name or new_name == old_name: win.destroy(); return
            if new_name in self.data["garages"]:
                messagebox.showerror("錯誤", "車庫名稱已存在！"); return
            
            idx = self.data["garages"].index(old_name)
            self.data["garages"][idx] = new_name
            for v in self.data["vehicles"]:
                if v.get("garage") == old_name: v["garage"] = new_name
                
            save_data(self.all_data); self.refresh_garage_table(); self.refresh_vehicle_table(); self.update_garage_comboboxes(); win.destroy()
            self.show_toast_progress("🏠 車庫重新命名成功！")
            
        tk.Button(win, text="確認修改 (Enter)", command=save, bg="#4CAF50", fg="white").pack(pady=10)
        win.bind("<Return>", save)

    # --- 批量匯入與雙擊編輯視窗 (結合安全鎖定) ---
    def open_batch_import_window(self):
        if not self.data: return
        win = tk.Toplevel(self.root); win.title("批量貼上匯入"); self.center_toplevel_window(win, 500, 450)
        tk.Label(win, text="請在此貼上車輛資料（一行一筆）", font=('Arial', 10, 'bold')).pack(pady=5)
        tk.Label(win, text="格式：車輛名稱,車庫名", fg="gray").pack()
        text_area = tk.Text(win, height=15, width=50); text_area.pack(pady=10, padx=10)
        
        def process_import():
            content = text_area.get("1.0", tk.END).strip()
            added = 0; duplicates = []
            target_index = -1 
            for line in content.split('\n'):
                if not line.strip(): continue
                parts = line.split(',')
                name = parts[0].strip(); garage = parts[1].strip() if len(parts) > 1 else "未分類"
                
                idx_existing = next((i for i, c in enumerate(self.data["vehicles"]) if c['name'] == name), None)
                if idx_existing is not None:
                    duplicates.append(name)
                    self.data["vehicles"][idx_existing]["count"] = self.data["vehicles"][idx_existing].get("count", 1) + 1
                    target_index = idx_existing 
                else:
                    if garage not in self.data["garages"]: garage = "未分類"
                    self.data["vehicles"].append({
                        "name": name, "garage": garage, "v_type": "個人載具", "acquire": "購買獲得", "upgraded": "未改滿", 
                        "count": 1, "notes": "無", "locked": False, "pinned": False
                    })
                    added += 1; target_index = len(self.data["vehicles"]) - 1 
                    
            save_data(self.all_data)
            self.entry_search.delete(0, tk.END); self.combo_garage_filter.set("全部"); self.refresh_vehicle_table()
            if target_index != -1 and self.tree_vehicles.exists(str(target_index)):
                self.tree_vehicles.selection_set(str(target_index)); self.tree_vehicles.see(str(target_index))
            
            win.destroy()
            self.show_toast_progress(f"📦 批量匯入完成 ({added} 筆)")
            if duplicates: messagebox.showinfo("匯入結果", f"新增 {added} 筆\n自動累加重複車輛：{len(duplicates)} 筆")
            
        tk.Button(win, text="確認執行匯入", command=process_import, bg="#4CAF50", fg="white", height=2).pack(fill="x", padx=10, pady=10)

    def open_edit_window(self):
        if not self.data: return
        selected = self.tree_vehicles.selection()
        if not selected: return
        
        # 🛡️ 編輯防呆檢查
        for item in selected:
            if self.data["vehicles"][int(item)].get("locked", False):
                messagebox.showwarning("鎖定限制", "⚠️ 您選取的資料包含【已鎖定】的車輛，無法編輯修改！\n請先解鎖再試。")
                return
        
        if len(selected) == 1:
            idx = int(selected[0]); car = self.data["vehicles"][idx]
            win = tk.Toplevel(self.root); win.title("編輯車輛"); self.center_toplevel_window(win, 320, 420)
            
            tk.Label(win, text="車輛名稱:").pack(pady=(10,2))
            ent_name = tk.Entry(win); ent_name.insert(0, car['name']); ent_name.pack(); ent_name.focus()
            
            tk.Label(win, text="存放車庫:").pack(pady=(5,2))
            combo_edit_garage = ttk.Combobox(win, state="readonly", values=self.data["garages"])
            combo_edit_garage.set(car.get('garage', '未分類')); combo_edit_garage.pack()
            
            tk.Label(win, text="載具類型:").pack(pady=(5,2))
            combo_edit_vtype = ttk.Combobox(win, state="readonly", values=V_TYPE_OPTIONS)
            combo_edit_vtype.set(car.get('v_type', '個人載具')); combo_edit_vtype.pack()
            
            tk.Label(win, text="取得方式:").pack(pady=(5,2))
            combo_edit_acquire = ttk.Combobox(win, state="readonly", values=ACQUIRE_OPTIONS)
            combo_edit_acquire.set(car.get('acquire', '購買獲得')); combo_edit_acquire.pack()
            
            tk.Label(win, text="改裝狀態:").pack(pady=(5,2))
            combo_edit_upgrade = ttk.Combobox(win, state="readonly", values=["未改滿", "已改滿"])
            combo_edit_upgrade.set(car.get('upgraded', '未改滿')); combo_edit_upgrade.pack()
            
            tk.Label(win, text="數量:").pack(pady=(5,2))
            ent_count = tk.Entry(win); ent_count.insert(0, str(car.get('count', 1))); ent_count.pack()
            
            tk.Label(win, text="備註:").pack(pady=(5,2))
            ent_notes = tk.Entry(win); ent_notes.insert(0, car.get('notes', '無')); ent_notes.pack()
            
            def save_single(e=None):
                car['name'] = ent_name.get()
                car['garage'] = combo_edit_garage.get()
                car['v_type'] = combo_edit_vtype.get()
                car['acquire'] = combo_edit_acquire.get()
                car['upgraded'] = combo_edit_upgrade.get()
                try: car['count'] = int(ent_count.get())
                except ValueError: car['count'] = 1 
                car['notes'] = ent_notes.get()
                
                save_data(self.all_data); self.apply_filters(); win.destroy()
                self.show_toast_progress("✅ 編輯成功！")
                
            tk.Button(win, text="儲存 (Enter)", command=save_single, bg="#4CAF50", fg="white").pack(pady=15)
            win.bind("<Return>", save_single)
            
        else:
            win = tk.Toplevel(self.root); win.title("批量修改車輛"); self.center_toplevel_window(win, 320, 390)
            tk.Label(win, text=f"⚠️ 您正在同時修改 {len(selected)} 筆車輛", fg="#E91E63", font=("Arial", 10, "bold")).pack(pady=(15, 10))
            
            tk.Label(win, text="1. 批量移至新車庫:").pack(pady=(2,2))
            combo_batch_garage = ttk.Combobox(win, state="readonly", width=20, values=["(不修改)"] + self.data["garages"])
            combo_batch_garage.set("(不修改)"); combo_batch_garage.pack()
            
            tk.Label(win, text="2. 批量更改載具類型:").pack(pady=(5,2))
            combo_batch_vtype = ttk.Combobox(win, state="readonly", width=20, values=["(不修改)"] + V_TYPE_OPTIONS)
            combo_batch_vtype.set("(不修改)"); combo_batch_vtype.pack()
            
            tk.Label(win, text="3. 批量更改取得方式:").pack(pady=(5,2))
            combo_batch_acq = ttk.Combobox(win, state="readonly", width=20, values=["(不修改)"] + ACQUIRE_OPTIONS)
            combo_batch_acq.set("(不修改)"); combo_batch_acq.pack()
            
            tk.Label(win, text="4. 批量更改改裝狀態:").pack(pady=(5,2))
            combo_batch_upg = ttk.Combobox(win, state="readonly", width=20, values=["(不修改)", "未改滿", "已改滿"])
            combo_batch_upg.set("(不修改)"); combo_batch_upg.pack()
            
            var_update_notes = tk.BooleanVar(value=False)
            chk_notes = tk.Checkbutton(win, text="5. 批量覆蓋備註內容", variable=var_update_notes); chk_notes.pack(pady=(5,2))
            ent_batch_notes = tk.Entry(win, width=23); ent_batch_notes.pack()
            
            def save_batch(e=None):
                new_g = combo_batch_garage.get(); up_g = (new_g != "(不修改)")
                new_v = combo_batch_vtype.get(); up_v = (new_v != "(不修改)")
                new_a = combo_batch_acq.get(); up_a = (new_a != "(不修改)")
                new_u = combo_batch_upg.get(); up_u = (new_u != "(不修改)")
                up_n = var_update_notes.get(); new_n = ent_batch_notes.get()
                
                if not up_g and not up_v and not up_a and not up_u and not up_n: win.destroy(); return
                
                for item in selected:
                    idx = int(item)
                    if up_g: self.data["vehicles"][idx]['garage'] = new_g
                    if up_v: self.data["vehicles"][idx]['v_type'] = new_v
                    if up_a: self.data["vehicles"][idx]['acquire'] = new_a
                    if up_u: self.data["vehicles"][idx]['upgraded'] = new_u
                    if up_n: self.data["vehicles"][idx]['notes'] = new_n
                        
                save_data(self.all_data); self.apply_filters(); win.destroy()
                self.show_toast_progress(f"✅ 批量修改成功 ({len(selected)} 筆)")
                
            tk.Button(win, text="儲存 (Enter)", command=save_batch, bg="#2196F3", fg="white", width=15).pack(pady=15)
            win.bind("<Return>", save_batch) 

if __name__ == "__main__":
    root = tk.Tk()
    app = GTAGarageApp(root)
    root.mainloop()