# ==========================================
# 📦 第一部分：系統常數與 UI 設定 (Config)
# ==========================================
class Config:
    APP_VERSION = "1.1.15" 
    UPDATE_URL = "https://raw.githubusercontent.com/cvk82519-boop/GTA-Garage-App/refs/heads/main/version.json"
    DATA_FILE = "gta5_garage_data.json"

    # 預設的取得方式與分類
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

# 💡 為了向下相容，暫時將 Config 的屬性映射到全域變數，避免修改下方 1400 行 UI 程式碼
APP_VERSION = Config.APP_VERSION
UPDATE_URL = Config.UPDATE_URL
DATA_FILE = Config.DATA_FILE
ACQUIRE_OPTIONS = Config.ACQUIRE_OPTIONS
V_TYPE_OPTIONS = Config.V_TYPE_OPTIONS
SUB_CARRIER_RULES = Config.SUB_CARRIER_RULES
COLOR_MAIN_BG = Config.COLOR_MAIN_BG
COLOR_CARD_BG = Config.COLOR_CARD_BG
COLOR_TEXT_WHITE = Config.COLOR_TEXT_WHITE
COLOR_TEXT_GRAY = Config.COLOR_TEXT_GRAY
COLOR_FOCUS_BG = Config.COLOR_FOCUS_BG
FONT_NORMAL = Config.FONT_NORMAL
FONT_BOLD = Config.FONT_BOLD
FONT_LARGE_BOLD = Config.FONT_LARGE_BOLD

# ✨ 全域輸入框高亮追蹤引擎
def apply_focus_highlight(widget):
    import tkinter as tk
    if isinstance(widget, tk.Entry):
        widget.bind("<FocusIn>", lambda e: widget.config(bg=Config.COLOR_FOCUS_BG), add="+")
        widget.bind("<FocusOut>", lambda e: widget.config(bg=Config.COLOR_CARD_BG), add="+")

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
        import tkinter as tk
        if not self.widget.winfo_exists() or not self.text: return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify=tk.LEFT, background="#111111", foreground="white", relief=tk.SOLID, borderwidth=0, font=Config.FONT_NORMAL, padx=8, pady=4).pack(ipadx=1)
    def hidetip(self):
        if self.tipwindow and self.tipwindow.winfo_exists(): self.tipwindow.destroy()
        self.tipwindow = None

def add_tooltip(widget, text): ToolTip(widget, text)

# ==========================================
# 📦 第二部分：資料庫管理系統 (DataManager)
# ==========================================
class DataManager:
    @staticmethod
    def load_data():
        default_structure = {"profiles": {}}
        if not os.path.exists(Config.DATA_FILE):
            return default_structure
            
        try:
            with open(Config.DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "vehicles" in data and "profiles" not in data:
                        return {"profiles": {"已移轉帳號": data}}
                    if "profiles" in data: return data
                return default_structure
        except Exception as e:
            # 🛡️ 【安全升級】防止 JSON 損壞時覆蓋玩家心血，自動備份受損檔案
            import shutil
            corrupted_file = f"{Config.DATA_FILE}.corrupted"
            try:
                shutil.copy(Config.DATA_FILE, corrupted_file)
                print(f"⚠️ 警告：資料檔損毀，已備份至 {corrupted_file}。錯誤: {e}")
            except: pass
            return default_structure

    @staticmethod
    def save_data(all_data):
        for p_name, p_data in all_data.get("profiles", {}).items():
            if "garages" not in p_data: 
                p_data["garages"] = ["未分類", "帕格薩斯", "日蝕大樓 1 號", "辦公室車庫", "名鑽賭場空中別墅", "設施"]
            else:
                if "帕格薩斯" not in p_data["garages"]:
                    if "未分類" in p_data["garages"]: p_data["garages"].insert(p_data["garages"].index("未分類") + 1, "帕格薩斯")
                    else: p_data["garages"].insert(0, "帕格薩斯")
                    
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
            
            if "wishlist" not in p_data: p_data["wishlist"] = []
                
            if "garage_category_options" not in p_data:
                p_data["garage_category_options"] = ["一般車庫", "高階公寓", "豪宅", "商辦企業", "地下設施", "豪華賭場"]
                
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
                "tab_guides": True, "tab_wishlist": True, 
                "tool_stopwatch": True, "disable_all_limits": False, "auto_backup": True, 
                "default_garage_limit": 10, "default_special_limit": 2,
                "default_countdown_sec": 300.0,
                "hotkey_pause": "pause", "hotkey_start": "w",
                "visible_columns": ["check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"] 
            }
            for k, v in defaults.items():
                if k not in p_data["app_settings"]:
                    p_data["app_settings"][k] = v

            if "acquire_options" not in p_data:
                p_data["acquire_options"] = Config.ACQUIRE_OPTIONS.copy()

            for sv in p_data.get("special_vehicles", []):
                if "location" not in sv: sv["location"] = "未分類"
                if "inner_vehicle" not in sv: sv["inner_vehicle"] = ""
                if "can_store" not in sv: sv["can_store"] = True if sv["name"] in Config.SUB_CARRIER_RULES else False

        with open(Config.DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)

# 💡 為了向下相容，保留全域函數呼叫 (讓下方的程式碼完全不用改)
def load_data():
    return DataManager.load_data()

def save_data(all_data):
    DataManager.save_data(all_data)

# ==========================================
# 📦 第三部分：主程式 UI (GTAGarageApp)
# ==========================================
# (原本的 class GTAGarageApp: 保留在這裡，不動它)
