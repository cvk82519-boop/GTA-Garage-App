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

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

APP_VERSION = "1.8.9"
DATA_FILE = "gta5_garage_data.json"

ACQUIRE_OPTIONS = ["購買獲得", "任務獲得", "生涯成就", "賭場轉盤", "搶劫獲得", "車友會", "其他備註"]
V_TYPE_OPTIONS = ["個人載具", "非個人載具", "帕格薩斯", "個人飛行載具"]
SUB_CARRIER_RULES = {
    "驚駭位元": ["暴君MKII", "暴君 Mk II", "Oppressor Mk II"],
    "科薩卡": ["鬥牛勇士", "斯特龍伯格", "Toreador", "Stromberg"]
}

COLOR_MAIN_BG, COLOR_CARD_BG, COLOR_TEXT_WHITE, COLOR_TEXT_GRAY, COLOR_FOCUS_BG = "#212121", "#2d2d2d", "#ffffff", "#cccccc", "#1565C0"
FONT_NORMAL, FONT_BOLD, FONT_LARGE_BOLD = ("Microsoft JhengHei", 12), ("Microsoft JhengHei", 13, "bold"), ("Microsoft JhengHei", 14, "bold")

def apply_focus_highlight(widget):
    if isinstance(widget, tk.Entry) or isinstance(widget, tk.Text):
        widget.bind("<FocusIn>", lambda e: widget.config(bg=COLOR_FOCUS_BG), add="+")
        widget.bind("<FocusOut>", lambda e: widget.config(bg=COLOR_CARD_BG), add="+")

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
        if "guides" not in p_data: p_data["guides"] = []
        if "action_logs" not in p_data: p_data["action_logs"] = []
        if "app_settings" not in p_data: p_data["app_settings"] = {}
        defaults = {"tab_bulletin": True, "tab_vehicles": True, "tab_non_personal": True, "tab_special": True, "tab_garages": True, "tab_hangars": True, "tab_statistics": True, "tab_logs": True, "tab_wishlist": True, "tab_guides": True, "tool_stopwatch": True, "disable_all_limits": False, "auto_backup": True, "default_garage_limit": 10, "default_special_limit": 2, "default_countdown_sec": 300.0, "hotkey_pause": "pause", "hotkey_start": "w", "visible_columns": ["check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"] }
        for k, v in defaults.items():
            if k not in p_data["app_settings"]: p_data["app_settings"][k] = v
        if "acquire_options" not in p_data: p_data["acquire_options"] = ACQUIRE_OPTIONS.copy()
        for sv in p_data.get("special_vehicles", []):
            if "location" not in sv: sv["location"] = "未分類"
            if "inner_vehicle" not in sv: sv["inner_vehicle"] = ""
            if "can_store" not in sv: sv["can_store"] = True if sv["name"] in SUB_CARRIER_RULES else False
    with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(all_data, f, ensure_ascii=False, indent=4)

class GTAGarageApp:
    def _prevent_multi_instance(self, root):
        import socket
        try:
            # 嘗試綁定專屬通訊埠，這會隨程式關閉自動釋放
            self._instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._instance_socket.bind(('127.0.0.1', 48921))
        except socket.error:
            # 如果通訊埠被佔用，代表程式真的開著
            import tkinter.messagebox as mb
            mb.showwarning("防護提示", "⛔ GTAV 資產管理系統已經在執行中了！\n\n為保護您的資料庫安全，不允許重複開啟。")
            try: root.destroy()
            except: pass
            import sys
            sys.exit()
        except Exception:
            # 🛡️ 絕對豁免：如果遇到防毒軟體或任何其他系統攔截，直接放行，保證主程式能順利打開！
            pass

    def __init__(self, root):
        self._prevent_multi_instance(root)
        self.root = root
        self.root.title(f"GTAV資產管理系統 {APP_VERSION} (終極完美合併版)")
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
        
        self.style = ttk.Style(); self.style.theme_use("clam")
        self.style.configure(".", background=COLOR_MAIN_BG, foreground=COLOR_TEXT_WHITE, font=FONT_NORMAL)
        self.style.configure("TNotebook", background=COLOR_MAIN_BG, borderwidth=0, padding=2)
        self.style.configure("TNotebook.Tab", background=COLOR_CARD_BG, foreground=COLOR_TEXT_GRAY, font=("Microsoft JhengHei", 10, "bold"), padding=[6, 4])
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
        
        self.notebook = ttk.Notebook(root); self.notebook.pack(fill="both", expand=True, padx=8, pady=5); self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed); self.notebook.bind("<Button-3>", self.show_tab_context_menu)
        self.tab_bulletin = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.tab_account = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.tab_vehicles = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.tab_non_personal = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.tab_special = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.tab_garages = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.tab_wishlist = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.tab_guides = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.tab_statistics = tk.Frame(self.notebook, bg=COLOR_MAIN_BG); self.tab_logs = tk.Frame(self.notebook, bg=COLOR_MAIN_BG)

        self.tab_hangars = ttk.Frame(self.notebook)
        self.tab_widgets = {"📢 系統公告": self.tab_bulletin, "👥 帳號管理": self.tab_account, "🚗 車輛管理": self.tab_vehicles, "🚜 非個人與帕格薩斯": self.tab_non_personal, "🚁 特殊載具": self.tab_special, "🏠 車庫管理": self.tab_garages, "✈️ 機庫管理": self.tab_hangars, "🛒 購車願望清單": self.tab_wishlist, "📚 攻略筆記": self.tab_guides, "📊 統計資料": self.tab_statistics, "📜 操作日誌": self.tab_logs}
        self.tab_order = app_config.get("tab_order", list(self.tab_widgets.keys()))
        for expected_tab in self.tab_widgets.keys():
            if expected_tab not in self.tab_order: self.tab_order.insert(max(0, len(self.tab_order)-2), expected_tab)
        for t_name in self.tab_order:
            if t_name in self.tab_widgets: self.notebook.add(self.tab_widgets[t_name], text=f" {t_name} ")
        
        self.setup_menu_bar(); self.setup_profile_bar(); self.setup_status_bar(); self.setup_bulletin_tab(); self.setup_account_tab(); self.setup_vehicles_tab(); self.setup_non_personal_tab(); self.setup_special_tab(); self.setup_garages_tab(); self.setup_hangars_tab(); self.setup_wishlist_tab(); self.setup_guides_tab(); self.setup_statistics_tab(); self.setup_logs_tab()
        self.apply_settings(); self.check_login_status()

    # ==========================
    # ✈️ 官方機庫圖鑑管理系統 (V1.7.4)
    # ==========================
    def check_hangar_data(self):
        if getattr(self, 'data', None) is None: return False
        if "hangars" not in self.data: self.data["hangars"] = {}
        if "hangar_vehicles" not in self.data: self.data["hangar_vehicles"] = []
        return True

    def setup_hangars_tab(self):
        paned = tk.PanedWindow(self.tab_hangars, orient="horizontal", bg="#2d2d2d", sashwidth=4)
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        left_frame = tk.Frame(paned, bg="#212121", width=260)
        paned.add(left_frame, minsize=260)

        tk.Label(left_frame, text="🏢 洛聖都機庫地產", font=("Microsoft JhengHei", 12, "bold"), bg="#212121", fg="#00BCD4").pack(pady=(5, 10))

        self.lb_hangars = tk.Listbox(left_frame, font=("Microsoft JhengHei", 11), bg="#2d2d2d", fg="white", selectbackground="#00BCD4", bd=0, highlightthickness=1)
        self.lb_hangars.pack(fill="both", expand=True, padx=5, pady=5)
        self.lb_hangars.bind('<<ListboxSelect>>', self.on_hangar_select)

        self.right_frame = tk.Frame(paned, bg="#212121")
        paned.add(self.right_frame, minsize=450)
        
        self.r_top = tk.Frame(self.right_frame, bg="#212121")
        self.r_top.pack(fill="x", padx=5, pady=10)
        self.lbl_hangar_title = tk.Label(self.r_top, text="✈️ 請選擇左側機庫", font=("Microsoft JhengHei", 12, "bold"), bg="#212121", fg="#F39C12")
        self.lbl_hangar_title.pack(side="left")
        
        self.btn_buy_h = tk.Button(self.r_top, text="💰 購買此機庫", font=("Microsoft JhengHei", 10, "bold"), bg="#4CAF50", fg="white", relief="flat", command=self.buy_selected_hangar)
        self.btn_add_plane = tk.Button(self.r_top, text="➕ 登記飛機", font=("Microsoft JhengHei", 10, "bold"), bg="#3498db", fg="white", relief="flat", command=self.add_hangar_vehicle)
        
        self.plane_frame = tk.Frame(self.right_frame, bg="#212121")
        
        style = ttk.Style()
        style.configure("Treeview", font=("Microsoft JhengHei", 10), rowheight=25)
        style.configure("Treeview.Heading", font=("Microsoft JhengHei", 10, "bold"))
        
        scroll_y = ttk.Scrollbar(self.plane_frame)
        scroll_y.pack(side="right", fill="y")
        
        cols = ("載具名稱", "取得方式", "購入價格", "備註")
        self.tv_hangar_vh = ttk.Treeview(self.plane_frame, columns=cols, show="headings", yscrollcommand=scroll_y.set)
        
        self.tv_hangar_vh.heading("載具名稱", text="載具名稱")
        self.tv_hangar_vh.column("載具名稱", width=160, anchor="center") 
        self.tv_hangar_vh.heading("取得方式", text="取得方式")
        self.tv_hangar_vh.column("取得方式", width=100, anchor="center")
        self.tv_hangar_vh.heading("購入價格", text="購入價格")
        self.tv_hangar_vh.column("購入價格", width=100, anchor="center")
        self.tv_hangar_vh.heading("備註", text="備註")
        self.tv_hangar_vh.column("備註", width=160, anchor="center")
        
        scroll_y.config(command=self.tv_hangar_vh.yview)
        self.tv_hangar_vh.pack(fill="both", expand=True, pady=5)
        
        # 🌟 重新綁定事件：雙擊修改與右鍵選單
        self.tv_hangar_vh.bind("<Double-1>", self.edit_hangar_vehicle)
        self.tv_hangar_vh.bind("<Button-3>", self.show_hangar_context_menu)
        
        self.btn_del_plane = tk.Button(self.plane_frame, text="❌ 刪除選定飛機", font=("Microsoft JhengHei", 10), bg="#e74c3c", fg="white", relief="flat", command=self.del_hangar_vehicle)
        self.btn_del_plane.pack(fill="x", pady=5)

        self.tab_hangars.bind("<Visibility>", lambda e: self.refresh_hangars_ui())

    def refresh_hangars_ui(self):
        self.lb_hangars.delete(0, tk.END)
        self.tv_hangar_vh.delete(*self.tv_hangar_vh.get_children())
        self.btn_buy_h.pack_forget()
        self.btn_add_plane.pack_forget()
        self.plane_frame.pack_forget()
        
        if not getattr(self, 'data', None):
            self.lbl_hangar_title.config(text="⚠️ 請先至「帳號管理」登入，方可使用機庫")
            return
            
        if not self.check_hangar_data(): return
        
        official_hangars = ["洛聖都國際機場機庫 A17", "洛聖都國際機場機庫 1", "桑庫多堡壘機庫 3499", "桑庫多堡壘機庫 3497", "桑庫多堡壘機庫 A2"]
        for h_name in official_hangars:
            if h_name in self.data["hangars"]:
                count = sum(1 for v in self.data["hangar_vehicles"] if v.get("garage") == h_name)
                self.lb_hangars.insert(tk.END, f"✅ {h_name} ({count}/20)")
                self.lb_hangars.itemconfig(tk.END, {'fg': '#4CAF50'})
            else:
                self.lb_hangars.insert(tk.END, f"❌ {h_name}")
                self.lb_hangars.itemconfig(tk.END, {'fg': '#95a5a6'})
        
        self.lbl_hangar_title.config(text="✈️ 請選擇左側機庫")

    def get_selected_hangar_name(self):
        if not self.lb_hangars.curselection(): return None
        raw_text = self.lb_hangars.get(self.lb_hangars.curselection()[0])
        return raw_text[2:].split(" (")[0].strip()

    def on_hangar_select(self, event):
        if not getattr(self, 'data', None): return
        h_name = self.get_selected_hangar_name()
        if not h_name: return
        
        self.btn_buy_h.pack_forget()
        self.btn_add_plane.pack_forget()
        self.plane_frame.pack_forget()
        self.tv_hangar_vh.delete(*self.tv_hangar_vh.get_children())
        
        if h_name in self.data["hangars"]:
            self.lbl_hangar_title.config(text=f"✈️ {h_name} 專屬機隊")
            self.btn_add_plane.pack(side="right", padx=5)
            self.plane_frame.pack(fill="both", expand=True)
            
            for i, v in enumerate(self.data["hangar_vehicles"]):
                if v.get("garage") == h_name:
                    self.tv_hangar_vh.insert("", "end", iid=str(i), values=(v.get("name",""), v.get("source",""), v.get("price",""), v.get("note","")))
        else:
            self.lbl_hangar_title.config(text=f"🏢 {h_name} (尚未購買)")
            self.btn_buy_h.pack(side="right", padx=5)

    def buy_selected_hangar(self):
        h_name = self.get_selected_hangar_name()
        if not h_name: return
        if not messagebox.askyesno("購買地產", f"確定要購入【{h_name}】嗎？\n(標準容量為 20 架飛行載具)"): return
        
        self.data["hangars"][h_name] = 20
        save_data(self.all_data)
        
        idx = self.lb_hangars.curselection()[0]
        self.refresh_hangars_ui()
        self.lb_hangars.selection_set(idx)
        self.on_hangar_select(None)
        self.show_toast_progress("🏢 成功購入機庫！")

    def add_hangar_vehicle(self):
        h_name = self.get_selected_hangar_name()
        if not h_name or h_name not in self.data["hangars"]: return
        
        count = sum(1 for v in self.data["hangar_vehicles"] if v.get("garage") == h_name)
        if count >= self.data["hangars"][h_name]:
            return messagebox.showerror("錯誤", "機庫容量已滿 (20/20)，無法再停放飛機！")
            
        def save_new_plane(event=None):
            n, s, p, nt = e_n.get().strip(), c_s.get().strip(), e_p.get().strip(), e_nt.get().strip()
            if not n: return messagebox.showwarning("錯誤", "請輸入飛機名稱！")
            
            self.data["hangar_vehicles"].append({"name": n, "source": s, "price": p, "note": nt, "garage": h_name, "type": "個人飛行載具"})
            save_data(self.all_data)
            
            idx = self.lb_hangars.curselection()[0]
            self.refresh_hangars_ui()
            self.lb_hangars.selection_set(idx)
            self.on_hangar_select(None)
            w.destroy()
            self.show_toast_progress("✈️ 飛機登記成功！")
            
        w = tk.Toplevel(self.root)
        w.title(f"登記飛機至 {h_name}")
        w.geometry("320x350")
        w.configure(bg="#2d2d2d")
        w.attributes("-topmost", True)
        w.bind("<Return>", save_new_plane)
        
        tk.Label(w, text="飛機名稱:", bg="#2d2d2d", fg="white").pack(pady=(10,0))
        e_n = tk.Entry(w, width=25)
        e_n.pack()
        tk.Label(w, text="取得方式:", bg="#2d2d2d", fg="white").pack(pady=(10,0))
        c_s = ttk.Combobox(w, values=["軍火大亨", "必達交通", "抽獎/活動", "其他"], width=23)
        c_s.pack()
        c_s.set("軍火大亨")
        tk.Label(w, text="購入價格:", bg="#2d2d2d", fg="white").pack(pady=(10,0))
        e_p = tk.Entry(w, width=25)
        e_p.pack()
        tk.Label(w, text="備註:", bg="#2d2d2d", fg="white").pack(pady=(10,0))
        e_nt = tk.Entry(w, width=25)
        e_nt.pack()
        tk.Button(w, text="💾 儲存 (Enter)", bg="#4CAF50", fg="white", font=("Microsoft JhengHei", 10, "bold"), command=save_new_plane).pack(pady=20)
        e_n.focus_set()

    # 🖱️ 右鍵智慧選單
    def show_hangar_context_menu(self, event):
        iid = self.tv_hangar_vh.identify_row(event.y)
        if iid:
            self.tv_hangar_vh.selection_set(iid)
            menu = tk.Menu(self.root, tearoff=0, font=("Microsoft JhengHei", 10))
            menu.add_command(label="📝 修改飛機資料", command=self.edit_hangar_vehicle)
            menu.add_separator()
            menu.add_command(label="❌ 銷毀此架飛機", command=self.del_hangar_vehicle)
            menu.post(event.x_root, event.y_root)

    def edit_hangar_vehicle(self, event=None):
        sel = self.tv_hangar_vh.selection()
        if not sel: return
        idx = int(sel[0])
        h_name = self.get_selected_hangar_name()
        if not h_name: return
        
        v_data = self.data["hangar_vehicles"][idx]
        
        def save_edit(event=None):
            n, s, p, nt = e_n.get().strip(), c_s.get().strip(), e_p.get().strip(), e_nt.get().strip()
            if not n: return messagebox.showwarning("錯誤", "請輸入飛機名稱！")
            
            v_data.update({"name": n, "source": s, "price": p, "note": nt, "type": "個人飛行載具"})
            save_data(self.all_data)
            
            list_idx = self.lb_hangars.curselection()[0]
            self.refresh_hangars_ui()
            self.lb_hangars.selection_set(list_idx)
            self.on_hangar_select(None)
            w.destroy()
            self.show_toast_progress("📝 飛機資料已更新！")

        w = tk.Toplevel(self.root)
        w.title(f"修改飛機 - {v_data.get('name','')}")
        w.geometry("320x350")
        w.configure(bg="#2d2d2d")
        w.attributes("-topmost", True)
        w.bind("<Return>", save_edit)
        
        tk.Label(w, text="飛機名稱:", bg="#2d2d2d", fg="white").pack(pady=(10,0))
        e_n = tk.Entry(w, width=25)
        e_n.insert(0, v_data.get("name", ""))
        e_n.pack()
        tk.Label(w, text="取得方式:", bg="#2d2d2d", fg="white").pack(pady=(10,0))
        c_s = ttk.Combobox(w, values=["軍火大亨", "必達交通", "抽獎/活動", "其他"], width=23)
        c_s.set(v_data.get("source", "軍火大亨"))
        c_s.pack()
        tk.Label(w, text="購入價格:", bg="#2d2d2d", fg="white").pack(pady=(10,0))
        e_p = tk.Entry(w, width=25)
        e_p.insert(0, v_data.get("price", ""))
        e_p.pack()
        tk.Label(w, text="備註:", bg="#2d2d2d", fg="white").pack(pady=(10,0))
        e_nt = tk.Entry(w, width=25)
        e_nt.insert(0, v_data.get("note", ""))
        e_nt.pack()
        tk.Button(w, text="💾 儲存修改 (Enter)", bg="#F39C12", fg="white", font=("Microsoft JhengHei", 10, "bold"), command=save_edit).pack(pady=20)
        e_n.focus_set()

    def del_hangar_vehicle(self):
        sel = self.tv_hangar_vh.selection()
        if not sel: return messagebox.showwarning("提示", "請先選擇要刪除的飛機。")
        if not messagebox.askyesno("警告", "確定要銷毀這架飛機嗎？"): return
        
        idx = int(sel[0])
        del self.data["hangar_vehicles"][idx]
        save_data(self.all_data)
        
        list_idx = self.lb_hangars.curselection()[0]
        self.refresh_hangars_ui()
        self.lb_hangars.selection_set(list_idx)
        self.on_hangar_select(None)
        self.show_toast_progress("❌ 飛機已刪除")

    def check_win(self, win_name):
        try:
            if hasattr(self, win_name):
                w = getattr(self, win_name)
                if w and w.winfo_exists():
                    w.lift()
                    w.focus_force()
                    return True
        except: pass
        return False

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

    def show_toast_progress(self, message="✅ 操作成功"):
        toast = tk.Toplevel(self.root); toast.overrideredirect(True); toast.attributes("-topmost", True); toast.configure(bg=COLOR_CARD_BG)
        self.root.update_idletasks()
        try: x, y = self.root.winfo_rootx() + self.root.winfo_width() - 340, self.root.winfo_rooty() + self.root.winfo_height() - 90; toast.geometry(f"320x70+{x}+{y}")
        except: toast.geometry("320x70")
        f = tk.Frame(toast, bg=COLOR_CARD_BG, highlightbackground="#4CAF50", highlightthickness=2); f.pack(fill="both", expand=True)
        tk.Label(f, text=message, bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).pack(expand=True, pady=5)
        def step(v):
            if not toast.winfo_exists(): return 
            if v <= 100: toast.after(20, step, v + 5)
            else: toast.after(800, lambda: toast.destroy() if toast.winfo_exists() else None)
        step(0)

    def setup_menu_bar(self):
        self.menubar = tk.Menu(self.root)
        
        fm = tk.Menu(self.menubar, tearoff=0, bg="#2d2d2d", fg="white")
        fm.add_command(label="🚪 結束系統 (Exit)", command=self.on_app_closing)
        self.menubar.add_cascade(label="檔案 (F)", menu=fm)
        
        nm = tk.Menu(self.menubar, tearoff=0, bg="#2d2d2d", fg="white")
        nm.add_command(label="📝 新增任務攻略", command=self.open_add_guide_window)
        self.menubar.add_cascade(label="任務 (M)", menu=nm)
        
        def open_add_garage_popup():
            popup = tk.Toplevel(self.root)
            popup.title("🏠 新增車庫 / 購買物業")
            popup.geometry("380x280")
            popup.configure(bg="#2d2d2d")
            popup.attributes("-topmost", True)
            popup.focus_force()

            tk.Label(popup, text="主物業名稱:", font=("Microsoft JhengHei", 10, "bold"), bg="#2d2d2d", fg="white").pack(anchor="w", padx=20, pady=(15, 5))
            new_eng = tk.Entry(popup, font=("Microsoft JhengHei", 10), bg="#3d3d3d", fg="white", insertbackground="white", relief="solid")
            new_eng.pack(fill="x", padx=20)
            
            tk.Label(popup, text="附加額外樓層數:", font=("Microsoft JhengHei", 10, "bold"), bg="#2d2d2d", fg="white").pack(anchor="w", padx=20, pady=(15, 5))
            
            fr = tk.Frame(popup, bg="#2d2d2d")
            fr.pack(fill="x", padx=20)
            new_engf = tk.Entry(fr, width=8, font=("Microsoft JhengHei", 10), bg="#3d3d3d", fg="white", insertbackground="white", relief="solid")
            new_engf.insert(0, "1")
            new_engf.pack(side="left")
            
            from tkinter import ttk
            new_cft = ttk.Combobox(fr, width=18, font=("Microsoft JhengHei", 10), state="readonly", values=["地上 (車庫1...)", "地下 (B1...)"])
            new_cft.set("地上 (車庫1...)")
            new_cft.pack(side="left", padx=10)
            
            def save_and_close(e=None):
                self.eng = new_eng
                self.engf = new_engf
                self.cft = new_cft
                self.add_garage_simple()
                popup.destroy()

            popup.bind("<Return>", save_and_close)
            tk.Button(popup, text="➕ 確認置產", bg="#4CAF50", fg="white", font=("Microsoft JhengHei", 11, "bold"), relief="flat", command=save_and_close).pack(fill="x", padx=20, pady=25)
            new_eng.focus()

        gm = tk.Menu(self.menubar, tearoff=0, bg="#2d2d2d", fg="white")
        gm.add_command(label="🏠 新增車庫 (購買物業)", command=open_add_garage_popup)
        if hasattr(self, 'open_batch_garage_window'):
            gm.add_command(label="📦 批量新增車庫", command=self.open_batch_garage_window)

        self.menubar.add_cascade(label="車庫 (G)", menu=gm)
        
        em = tk.Menu(self.menubar, tearoff=0, bg="#2d2d2d", fg="white")
        em.add_command(label="📦 批量新增載具", command=self.open_batch_import_window)
        em.add_separator()
        em.add_command(label="🔍 檢查重複車輛", command=self.check_duplicate_vehicles)
        em.add_command(label="📝 編輯已勾選載具 (0)", command=self.edit_checked_vehicles)
        em.add_command(label="🎲 今天開哪台？", command=self.random_ride)
        self.menubar.add_cascade(label="載具 (V)", menu=em); self.edit_menu = em
        
        tm = tk.Menu(self.menubar, tearoff=0, bg="#2d2d2d", fg="white")
        tm.add_command(label="⏱️ 呼叫任務碼錶", command=self.toggle_stopwatch_window)
        tm.add_separator()
        tm.add_command(label="⚙️ 系統全域設定", command=self.open_settings_window)
        self.menubar.add_cascade(label="系統工具 (T)", menu=tm); self.tools_menu = tm
        
        sm = tk.Menu(self.menubar, tearoff=0, bg="#2d2d2d", fg="white")
        sm.add_command(label="💾 手動備份資料 (Backup)", command=self.backup_data)
        sm.add_command(label="📂 載入備份還原 (Restore)", command=self.restore_data)
        sm.add_command(label="📥 匯出資料為 CSV (Export)", command=self.export_csv)
        self.menubar.add_cascade(label="安全 (S)", menu=sm)
        
        self.root.config(menu=self.menubar)
        
        # 🌟 終極動態攔截引擎加強版：左右夾擊，見一個刪一個
        def _active_wipe_loop():
            def search_widget(w):
                try:
                    for child in w.winfo_children():
                        # 1. 處理右側的舊版面
                        if child.winfo_class() == "Label":
                            txt = str(child.cget("text"))
                            if "🏠 購買新物業" in txt and not hasattr(child, "_wiped_flag"):
                                child._wiped_flag = True
                                p_frame = child.master
                                for sibling in list(p_frame.winfo_children()):
                                    if sibling != child:
                                        sibling.destroy()
                                child.config(
                                    text="\n\n✨ 新增功能已完美升級！\n\n\n請點擊最上方工具列的【車庫 (G)】選單\n\n即可使用全新的彈出式新增功能。",
                                    font=("Microsoft JhengHei", 14, "bold"),
                                    fg="#3498db",
                                    bg=p_frame.cget("bg"),
                                    justify="center"
                                )
                                child.pack(expand=True, fill="both", pady=50)
                                
                        # 2. 處理左側的清單 (徹底拔除！)
                        elif child.winfo_class() == "Listbox":
                            items = child.get(0, tk.END)
                            # 倒序掃描，安全刪除目標選項
                            for idx in range(len(items)-1, -1, -1):
                                if "進階管理" in str(items[idx]) or "購買新物業" in str(items[idx]):
                                    child.delete(idx)
                                    
                        search_widget(child)
                except: pass
            search_widget(self.root)
            pass # 停用背景引擎
            
        pass # 停用背景引擎
    def open_column_selector(self):
        if self.check_win('col_window'): return
        if not self.data: return messagebox.showwarning("操作提示", "請先登入角色 ID！")
        self.col_window = win = tk.Toplevel(self.root); win.title("👁️ 顯示/隱藏自訂欄位"); self.center_toplevel_window(win, 300, 450); win.configure(bg=COLOR_CARD_BG)
        tk.Label(win, text="請勾選您想在表格中顯示的欄位：", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#3498db").pack(pady=(15, 10))
        all_cols = {"check": "☑ 選取方塊", "name": "車輛名稱", "garage": "存放位置", "vtype": "車輛類型", "acquire": "取得方式", "price": "購入價格估值", "upgrade": "改裝狀態", "count": "資產數量", "notes": "自訂備註"}
        current_visible = self.data.get("app_settings", {}).get("visible_columns", list(all_cols.keys()))
        fc = tk.Frame(win, bg=COLOR_CARD_BG); fc.pack(fill="both", expand=True, padx=40)
        vd = {}
        for c_id, c_name in all_cols.items():
            var = tk.BooleanVar(value=(c_id in current_visible)); vd[c_id] = var
            tk.Checkbutton(fc, text=c_name, variable=var, bg=COLOR_CARD_BG, fg="white", selectcolor="#757575", font=FONT_BOLD).pack(anchor="w", pady=4)
        def save_cols():
            nv = [c_id for c_id, v in vd.items() if v.get()]
            if not nv: return messagebox.showwarning("警告", "請至少保留一個顯示欄位！", parent=win)
            self.data["app_settings"]["visible_columns"] = nv; save_data(self.all_data)
            if hasattr(self, 'tree_vehicles') and self.tree_vehicles.winfo_exists(): self.tree_vehicles["displaycolumns"] = nv
            if hasattr(self, 'tree_non_personal') and self.tree_non_personal.winfo_exists(): self.tree_non_personal["displaycolumns"] = nv
            self.show_toast_progress("✅ 欄位顯示設定已更新！"); win.destroy()
        ttk.Button(win, text="💾 儲存並即時套用", command=save_cols, style="Success.TButton").pack(fill="x", padx=40, pady=(10, 20), ipady=4)

    def master_stopwatch_loop(self):
        if getattr(self, 'is_running', False):
            now = time.time(); mode = getattr(self, 'sw_mode', 'STOPWATCH')
            if mode == "STOPWATCH": self.elapsed_time = now - self.start_time
            else: 
                passed = now - self.start_time; rem = getattr(self, 'cd_target_sec', 300.0) - passed
                if rem <= 0.0:
                    self.elapsed_time, self.is_running, self.sw_state = 0.0, False, "IDLE"
                    self.update_stopwatch_ui_state(); self.update_stopwatch_ui(); self.show_toast_progress("⏰ 倒數計時時間到！"); self.set_status("⏰ 倒數計時時間到！", "#e74c3c")
                    if hasattr(self, 'stopwatch_window') and self.stopwatch_window.winfo_exists(): self.stopwatch_window.deiconify(); self.stopwatch_window.attributes("-topmost", True)
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
        st = getattr(self, 'sw_state', 'IDLE'); m = getattr(self, 'sw_mode', 'STOPWATCH')
        if st == "RUNNING": self.sw_state, self.is_running = "IDLE", False
        elif st == "IDLE":
            if m == "COUNTDOWN" and getattr(self, 'elapsed_time', 0.0) <= 0.0: self.elapsed_time = getattr(self, 'cd_target_sec', 300.0)
            self.sw_state, self.is_running = "READY", False
        elif st == "READY": self.sw_state, self.is_running = "IDLE", False
        self.update_stopwatch_ui_state()

    def action_start(self):
        self.sw_state, self.is_running, m, now = "RUNNING", True, getattr(self, 'sw_mode', 'STOPWATCH'), time.time()
        if m == "STOPWATCH": self.start_time = now - getattr(self, 'elapsed_time', 0.0)
        else: self.start_time = now - (self.cd_target_sec - (self.elapsed_time if self.elapsed_time > 0 else self.cd_target_sec))
        self.update_stopwatch_ui_state()

    def action_reset(self):
        self.sw_state, self.is_running = "IDLE", False
        self.elapsed_time = 0.0 if getattr(self, 'sw_mode', 'STOPWATCH') == "STOPWATCH" else getattr(self, 'cd_target_sec', 300.0)
        self.update_stopwatch_ui_state(); self.update_stopwatch_ui()

    def set_countdown_target(self, seconds, close_window=False):
        self.cd_target_sec = float(seconds)
        if self.data: self.data.setdefault("app_settings", {})["default_countdown_sec"] = self.cd_target_sec; save_data(self.all_data)
        self.action_reset(); self.show_toast_progress(f"⏳ 已記憶倒數: {int(seconds//60)}分{int(seconds%60)}秒")
        if close_window and hasattr(self, 'stopwatch_window') and self.stopwatch_window.winfo_exists(): self.stopwatch_window.withdraw()

    def set_sw_mode(self, mode):
        self.sw_mode = mode
        if hasattr(self, 'btn_mode_sw'):
            if mode == "STOPWATCH": self.btn_mode_sw.config(style="Primary.TButton"); self.btn_mode_cd.config(style="Dark.TButton"); self.frame_cd_opts.pack_forget()
            else: self.btn_mode_sw.config(style="Dark.TButton"); self.btn_mode_cd.config(style="Primary.TButton"); self.frame_cd_opts.pack(after=self.frame_mode_btn, pady=4)
        self.action_reset()

    def update_stopwatch_ui_state(self):
        if hasattr(self, 'btn_sw_action') and self.btn_sw_action.winfo_exists():
            st = self.data.get("app_settings", {}) if getattr(self, 'data', None) else {}
            pk, sk = st.get("hotkey_pause", "pause").upper(), st.get("hotkey_start", "w").upper()
            state = getattr(self, 'sw_state', 'IDLE')
            if state == "READY": self.btn_sw_action.config(text=f"等待起跑 (按 {sk})", style="Warning.TButton") 
            elif state == "RUNNING": self.btn_sw_action.config(text=f"計時中 (按 {pk} 停)", style="Danger.TButton") 
            else: self.btn_sw_action.config(text=f"準備 (按 {pk})", style="Success.TButton") 
            if hasattr(self, 'lbl_sw_hint') and self.lbl_sw_hint.winfo_exists():
                self.lbl_sw_hint.config(text=f"💡 快捷鍵提示：【{pk}】預備/暫停  |  【{sk}】開始")

    def toggle_stopwatch_window(self):
        if self.check_win('stopwatch_window'): return
        self.stopwatch_window = tw = tk.Toplevel(self.root); tw.title("⏱️ 碼錶"); tw.geometry("400x320"); tw.configure(bg=COLOR_CARD_BG); tw.attributes("-topmost", True); tw.resizable(False, False)
        tw.protocol("WM_DELETE_WINDOW", tw.withdraw)
        self.frame_mode_btn = tk.Frame(tw, bg=COLOR_CARD_BG); self.frame_mode_btn.pack(pady=(8, 2))
        self.btn_mode_sw = ttk.Button(self.frame_mode_btn, text="⏱️ 正向計時", command=lambda: self.set_sw_mode("STOPWATCH"), style="Primary.TButton"); self.btn_mode_sw.pack(side="left", padx=4)
        self.btn_mode_cd = ttk.Button(self.frame_mode_btn, text="⏳ 倒數計時", command=lambda: self.set_sw_mode("COUNTDOWN"), style="Dark.TButton"); self.btn_mode_cd.pack(side="left", padx=4)
        self.frame_cd_opts = tk.Frame(tw, bg=COLOR_CARD_BG)
        if self.sw_mode == "COUNTDOWN": self.frame_cd_opts.pack(pady=4)
        fp = tk.Frame(self.frame_cd_opts, bg=COLOR_CARD_BG); fp.pack()
        for lt, sv in [("1分", 60), ("5分", 300), ("10分", 600), ("20分", 1200), ("48分", 2880)]: ttk.Button(fp, text=lt, command=lambda s=sv: self.set_countdown_target(s), style="Secondary.TButton").pack(side="left", padx=2)
        fc = tk.Frame(self.frame_cd_opts, bg=COLOR_CARD_BG); fc.pack(pady=(4, 0))
        tk.Label(fc, text="自訂:", bg=COLOR_CARD_BG, fg="white", font=("Microsoft JhengHei", 9)).pack(side="left")
        ecm = tk.Entry(fc, width=3, font=("Microsoft JhengHei", 10), bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid"); ecm.insert(0, str(int(self.cd_target_sec // 60))); ecm.pack(side="left", padx=1)
        tk.Label(fc, text="分", bg=COLOR_CARD_BG, fg="white", font=("Microsoft JhengHei", 9)).pack(side="left")
        ecs = tk.Entry(fc, width=3, font=("Microsoft JhengHei", 10), bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid"); ecs.insert(0, str(int(self.cd_target_sec % 60))); ecs.pack(side="left", padx=1)
        tk.Label(fc, text="秒", bg=COLOR_CARD_BG, fg="white", font=("Microsoft JhengHei", 9)).pack(side="left", padx=(0,3))
        def apply_cd(e=None):
            try: t = float(ecm.get().strip() or 0)*60 + float(ecs.get().strip() or 0)
            except: t = 0
            if t > 0: self.set_countdown_target(t, True)
        ttk.Button(fc, text="儲存", command=apply_cd, style="Primary.TButton").pack(side="left", padx=2)
        self.lbl_sw = tk.Label(tw, text="00:00.0", font=("Consolas", 30, "bold"), bg=COLOR_CARD_BG, fg="white"); self.lbl_sw.pack(pady=(4, 4))
        bf = tk.Frame(tw, bg=COLOR_CARD_BG); bf.pack(pady=(0, 5))
        self.btn_sw_action = ttk.Button(bf, text="準備", command=self.action_pause_single, style="Success.TButton"); self.btn_sw_action.pack(side="left", padx=5)
        ttk.Button(bf, text="歸零", command=self.action_reset, style="Danger.TButton").pack(side="left", padx=5)
        self.lbl_sw_hint = tk.Label(tw, text="", bg=COLOR_CARD_BG, fg="#a8e6cf", font=("Microsoft JhengHei", 10)); self.lbl_sw_hint.pack(pady=(5, 0))
        self.update_stopwatch_ui_state(); self.update_stopwatch_ui()

    def update_stopwatch_ui(self):
        if hasattr(self, 'lbl_sw') and self.lbl_sw.winfo_exists():
            m, s, ms = int(self.elapsed_time // 60), int(self.elapsed_time % 60), int((self.elapsed_time * 10) % 10)
            self.lbl_sw.config(text=f"{m:02d}:{s:02d}.{ms}")

    def auto_scroll_to_newest(self, tab_name):
        try:
            def focus_and_select(tree):
                c = tree.get_children()
                if c:
                    tree.selection_set(c[-1])  # 🌟 自動反白選取最後一筆
                    tree.focus(c[-1])          # 🌟 將系統焦點對準它
                    tree.see(c[-1])            # 🌟 確保畫面滾動到最底部
                    
            if "車輛" in tab_name and hasattr(self, 'tree_vehicles'): focus_and_select(self.tree_vehicles)
            elif "非個人" in tab_name and hasattr(self, 'tree_non_personal'): focus_and_select(self.tree_non_personal)
            elif "特殊載具" in tab_name and hasattr(self, 'tree_special'): focus_and_select(self.tree_special)
            elif "機庫" in tab_name and hasattr(self, 'tv_hangar_vh'): focus_and_select(self.tv_hangar_vh)
            elif "願望" in tab_name and hasattr(self, 'tree_wishlist'): focus_and_select(self.tree_wishlist)
            elif "攻略" in tab_name and hasattr(self, 'tree_guides'): focus_and_select(self.tree_guides)
            elif "日誌" in tab_name and hasattr(self, 'text_logs'): self.text_logs.see("1.0")
        except: pass

    def on_tab_changed(self, event=None):
        sid = self.notebook.select()
        if not sid: return
        t = self.notebook.tab(sid, "text").strip()
        if "統計" in t: self.refresh_statistics()
        self.auto_scroll_to_newest(t) # 🌟 觸發自動聚焦最新資料
        
        if hasattr(self, 'menubar'):
            # 🎯 登入防護：未登入時全面鎖定所有工具列
            if not getattr(self, 'current_id', None):
                try: 
                    self.menubar.entryconfig("任務 (M)", state="disabled")
                    self.menubar.entryconfig("載具 (V)", state="disabled")
                    self.menubar.entryconfig("安全 (S)", state="disabled")
                    self.menubar.entryconfig("系統工具 (T)", state="disabled")
                except: pass
                return
            else:
                try:
                    self.menubar.entryconfig("任務 (M)", state="normal")
                    self.menubar.entryconfig("安全 (S)", state="normal")
                    self.menubar.entryconfig("系統工具 (T)", state="normal")
                except: pass
                
            # 🎯 智慧動態選單：僅在車輛相關分頁啟用載具選單
            if "車輛" in t or "非個人" in t:
                try: self.menubar.entryconfig("載具 (V)", state="normal")
                except: pass
            else:
                try: self.menubar.entryconfig("載具 (V)", state="disabled")
                except: pass

    def backup_data(self):
        if not getattr(self, 'current_id', None) or not getattr(self, 'data', None):
            return messagebox.showinfo("備份", "請先登入帳號，才能進行單一角色備份。")
        fp = filedialog.asksaveasfilename(title="選擇儲存位置", initialfile=f"GTA_Backup_{self.current_id}.json", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if fp:
            try:
                # 🌟 只將當前角色的資料包裝成標準格式並匯出
                bk_data = {"profiles": {self.current_id: self.data}}
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(bk_data, f, ensure_ascii=False, indent=4)
                self.set_status("✅ 單一角色備份完成", "#4CAF50")
                messagebox.showinfo("成功", f"已成功將角色【{self.current_id}】備份至：\n{fp}")
            except Exception as e:
                messagebox.showerror("錯誤", f"備份失敗：{e}")

    def restore_data(self):
        fp = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if fp:
            try:
                with open(fp, "r", encoding="utf-8") as f: 
                    bd = json.load(f)
                
                source_profiles = bd.get("profiles", {})
                if not source_profiles and "vehicles" in bd:
                    source_profiles = {"舊版備份": bd}
                
                # 情境 1：如果使用者根本沒登入
                if not getattr(self, 'current_id', None):
                    if not messagebox.askyesno("警告", "您目前未登入任何角色！\n這將把備份檔內的角色新增至系統中，確定嗎？"): return
                    for p, d in source_profiles.items(): 
                        self.all_data.setdefault("profiles", {})[p] = d
                # 情境 2：使用者有登入，開始智慧判斷
                else:
                    if len(source_profiles) == 1:
                        source_name = list(source_profiles.keys())[0]
                        source_data = source_profiles[source_name]
                        
                        # 🌟 核心：備份檔的名字 跟 現在登入的名字 不一樣！
                        if source_name != self.current_id:
                            ans = messagebox.askyesnocancel("跨角色還原", f"📦 備份檔來源：【{source_name}】\n👤 當前登入：【{self.current_id}】\n\n請問您想怎麼做？\n\n• 按【是 (Yes)】：將資料『轉移並覆蓋』給目前的 {self.current_id}\n• 按【否 (No)】：不要轉移，保留為原本的 {source_name} (新增角色)\n• 按【取消 (Cancel)】：放棄還原")
                            if ans is None: return
                            elif ans is True:
                                self.all_data["profiles"][self.current_id] = source_data
                            else:
                                self.all_data.setdefault("profiles", {})[source_name] = source_data
                        else:
                            if not messagebox.askyesno("還原", f"確定要用備份檔覆蓋目前【{self.current_id}】的資料嗎？"): return
                            self.all_data["profiles"][self.current_id] = source_data
                    else:
                        if not messagebox.askyesno("多角色還原", "這份備份包含多個角色！\n這不會影響您現有其他角色的資料，確定要匯入嗎？"): return
                        for p, d in source_profiles.items(): 
                            self.all_data.setdefault("profiles", {})[p] = d
                
                save_data(self.all_data)
                if self.current_id and self.current_id not in self.all_data.get("profiles", {}): 
                    self.current_id = ""
                self.check_login_status()
                self.show_toast_progress("📂 備份還原/轉移成功！")
            except Exception as e: 
                messagebox.showerror("錯誤", f"還原失敗：{e}")
    def export_csv(self):
        if not self.data or not self.data.get("vehicles"): return messagebox.showinfo("匯出", "無資料。")
        fp = filedialog.asksaveasfilename(initialfile=f"Export_{self.current_id}.csv", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if fp:
            try:
                with open(fp, 'w', newline='', encoding='utf-8-sig') as f:
                    w = csv.writer(f)
                    w.writerow(["名稱", "位置", "類型", "取得", "價格", "改裝", "數量", "備註", "登記日", "修改日"])
                    for c in self.data["vehicles"]: w.writerow([c.get("name",""), c.get("garage",""), c.get("v_type",""), c.get("acquire",""), c.get("price",0), c.get("upgraded",""), c.get("count",1), c.get("notes",""), c.get("created_at",""), c.get("updated_at","")])
                self.show_toast_progress("📥 CSV 匯出成功！"); messagebox.showinfo("成功", f"匯出至：\n{fp}")
            except Exception as e: messagebox.showerror("錯誤", f"匯出失敗：{e}")

    def open_settings_window(self):
        if self.check_win('settings_window'): return
        if not self.data: return messagebox.showwarning("提示", "請先登入！")
        self.settings_window = win = tk.Toplevel(self.root); win.title("⚙️ 全域設定"); self.center_toplevel_window(win, 520, 650); win.configure(bg=COLOR_CARD_BG)
        cv = tk.Canvas(win, borderwidth=0, bg=COLOR_CARD_BG, highlightthickness=0); sb = ttk.Scrollbar(win, orient="vertical", command=cv.yview)
        sf = tk.Frame(cv, bg=COLOR_CARD_BG); sf.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=sf, anchor="nw", width=500); cv.configure(yscrollcommand=sb.set); cv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        win.bind("<Enter>", lambda e: cv.bind_all("<MouseWheel>", lambda ev: cv.yview_scroll(int(-1*(ev.delta/120)), "units"))); win.bind("<Leave>", lambda e: cv.unbind_all("<MouseWheel>"))
        tk.Label(sf, text="👁️ 版面顯示設定", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#4CAF50").pack(pady=(15, 5))
        st = self.data.get("app_settings", {}); vd = {}
        fc = tk.Frame(sf, bg=COLOR_CARD_BG); fc.pack(fill="x", padx=40)
        for k, t in [("tab_vehicles", "🚗 車輛管理"), ("tab_non_personal", "🚜 非個人與帕格薩斯"), ("tab_special", "🚁 特殊載具"), ("tab_garages", "🏠 車庫管理"), ("tab_hangars", "✈️ 機庫管理"), ("tab_wishlist", "🛒 購車願望清單"), ("tab_guides", "📚 攻略筆記"), ("tab_statistics", "📊 統計資料"), ("tab_logs", "📜 操作日誌"), ("tool_stopwatch", "⏱️ 任務碼錶工具"), ("auto_backup", "🔄 自動備份資料")]:
            v = tk.BooleanVar(win, value=st.get(k, True)); vd[k] = v
            tk.Checkbutton(fc, text=t, variable=v, bg=COLOR_CARD_BG, fg="white", selectcolor="#757575", font=FONT_BOLD, command=lambda key=k, var=v: var.set(True) if key == "auto_backup" and not var.get() and not messagebox.askyesno("⚠️ 安全警告", "關閉「自動備份」代表未來關閉系統時不再保留備份存檔！\n若不慎發生資料遺失將無法還原，確定要取消保護嗎？", parent=win) else None).pack(anchor="w", pady=3)
        ttk.Separator(sf, orient="horizontal").pack(fill="x", pady=15, padx=20)
        tk.Label(sf, text="🛠️ 全域容量設定", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#e74c3c").pack(pady=(5, 5))
        fi = tk.Frame(sf, bg=COLOR_CARD_BG); fi.pack(fill="x", padx=40, pady=5)
        tk.Label(fi, text="一般車庫預設上限:", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).grid(row=0, column=0, sticky="e", pady=8)
        eg = tk.Entry(fi, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=10); eg.insert(0, str(st.get("default_garage_limit", 10))); eg.grid(row=0, column=1, padx=10, pady=8)
        tk.Label(fi, text="特殊載具預設上限:", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).grid(row=1, column=0, sticky="e", pady=8)
        es = tk.Entry(fi, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=10); es.insert(0, str(st.get("default_special_limit", 2))); es.grid(row=1, column=1, padx=10, pady=8)
        vl = tk.BooleanVar(win, value=st.get("disable_all_limits", False)); tk.Checkbutton(sf, text="♾️ 解除所有容量上限", variable=vl, bg=COLOR_CARD_BG, fg="white", selectcolor="#757575", font=FONT_BOLD).pack(pady=5)
        vo = tk.BooleanVar(win, value=False); tk.Checkbutton(sf, text="⚠️ 強制套用上限至現有車庫", variable=vo, bg=COLOR_CARD_BG, fg="#F39C12", selectcolor="#757575", font=FONT_BOLD).pack(pady=5)
        ttk.Separator(sf, orient="horizontal").pack(fill="x", pady=15, padx=20)
        tk.Label(sf, text="🏷️ 「取得方式」管理", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#F39C12").pack(pady=(5, 5))
        fa = tk.Frame(sf, bg=COLOR_CARD_BG); fa.pack(fill="x", padx=50, pady=5); sba = ttk.Scrollbar(fa); sba.pack(side="right", fill="y")
        la = tk.Listbox(fa, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", selectbackground="#4CAF50", height=5, relief="solid", yscrollcommand=sba.set); la.pack(side="left", fill="both", expand=True); sba.config(command=la.yview)
        t_acq = self.data.get("acquire_options", ACQUIRE_OPTIONS).copy()
        for opt in t_acq: la.insert(tk.END, opt)
        bfa = tk.Frame(sf, bg=COLOR_CARD_BG); bfa.pack(fill="x", padx=50, pady=5); ena = tk.Entry(bfa, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=14); ena.pack(side="left", padx=(0, 10), fill="x", expand=True, ipady=3)
        def add_a():
            v = ena.get().strip()
            if v and v not in t_acq: t_acq.append(v); la.insert(tk.END, v); ena.delete(0, tk.END); la.see(tk.END)
        def del_a():
            s = la.curselection()
            if s: t_acq.pop(s[0]); la.delete(s[0])
        ttk.Button(bfa, text="➕ 新增", command=add_a, style="Success.TButton").pack(side="left", padx=2); ttk.Button(bfa, text="❌ 刪除", command=del_a, style="Danger.TButton").pack(side="left", padx=2)
        ttk.Separator(sf, orient="horizontal").pack(fill="x", pady=15, padx=20)
        tk.Label(sf, text="⌨️ 任務碼錶快捷鍵", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#9b59b6").pack(pady=(5, 5))
        fh = tk.Frame(sf, bg=COLOR_CARD_BG); fh.pack(fill="x", padx=40, pady=5)
        tk.Label(fh, text="準備/暫停:", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).grid(row=0, column=0, sticky="e", pady=8)
        ehp = tk.Entry(fh, font=FONT_NORMAL, bg="#111111", fg="#4CAF50", insertbackground="white", relief="sunken", bd=2, width=12)
        ehp.insert(0, st.get("hotkey_pause", "pause")); ehp.grid(row=0, column=1, padx=10, pady=8)
        tk.Label(fh, text="起跑/計時:", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).grid(row=1, column=0, sticky="e", pady=8)
        ehs = tk.Entry(fh, font=FONT_NORMAL, bg="#111111", fg="#4CAF50", insertbackground="white", relief="sunken", bd=2, width=12)
        ehs.insert(0, st.get("hotkey_start", "w")); ehs.grid(row=1, column=1, padx=10, pady=8)
        def setup_hotkey_capture(entry):
            def on_key(e):
                k = e.keysym.lower()
                km = {'return': 'enter', 'prior': 'page up', 'next': 'page down', 'escape': 'esc', 'control_l': 'ctrl', 'control_r': 'ctrl', 'shift_l': 'shift', 'shift_r': 'shift', 'alt_l': 'alt', 'alt_r': 'alt', 'delete': 'del', 'insert': 'ins', 'caps_lock': 'capslock'}
                if k in km: k = km[k]
                if "win" in k or "menu" in k: return "break"
                entry.delete(0, tk.END); entry.insert(0, k); return "break"
            entry.bind("<Key>", on_key); entry.bind("<FocusIn>", lambda e: entry.config(bg=COLOR_FOCUS_BG)); entry.bind("<FocusOut>", lambda e: entry.config(bg="#111111"))
        setup_hotkey_capture(ehp); setup_hotkey_capture(ehs)
        def save():
            for k, v in vd.items(): self.data["app_settings"][k] = v.get()
            try: ng = int(eg.get().strip())
            except: ng = 10
            try: ns = int(es.get().strip())
            except: ns = 2
            self.data["app_settings"]["disable_all_limits"] = vl.get(); self.data["app_settings"]["default_garage_limit"] = ng; self.data["app_settings"]["default_special_limit"] = ns; self.data["app_settings"]["hotkey_pause"] = ehp.get().strip().lower() or "pause"; self.data["app_settings"]["hotkey_start"] = ehs.get().strip().lower() or "w"
            if vo.get():
                sc = [s["name"] for s in self.data.get("special_vehicles", [])]
                for g in self.data.get("garages", []):
                    if g not in ["未分類", "帕格薩斯"]: self.data["garage_limits"][g] = ns if g in sc else ng
            self.data["acquire_options"] = t_acq; save_data(self.all_data); self.apply_settings(); self.check_login_status(); self.refresh_garage_table(); win.destroy(); self.show_toast_progress("⚙️ 設定已儲存")
        ttk.Button(sf, text="💾 儲存並套用", command=save, style="Primary.TButton").pack(fill="x", padx=40, pady=(20, 20), ipady=4)

    def apply_settings(self):
        st = self.data.get("app_settings", {}) if self.data else {"tool_stopwatch": True}
        pk, sk = st.get("hotkey_pause", "pause"), st.get("hotkey_start", "w")
        if st.get("tool_stopwatch", True):
            self.tools_menu.entryconfig("⏱️ 呼叫任務碼錶", state="normal")
            if HAS_KEYBOARD:
                try: keyboard.unhook_all(); keyboard.add_hotkey(pk, self.handle_pause_key); keyboard.add_hotkey(sk, self.handle_w_key)
                except: pass
            else: self.root.bind_all(f"<{pk.capitalize()}>", self.handle_pause_key); self.root.bind_all(f"<{sk.lower()}>", self.handle_w_key)
        else:
            self.tools_menu.entryconfig("⏱️ 呼叫任務碼錶", state="disabled")
            if HAS_KEYBOARD:
                try: keyboard.unhook_all()
                except: pass
            self.root.unbind_all(f"<{pk.capitalize()}>"); self.root.unbind_all(f"<{sk.lower()}>")

    def setup_status_bar(self):
        self.status_bar = tk.Label(self.root, text="💡 系統就緒。", bg="#111111", fg="#FF9800", font=FONT_BOLD, anchor="w", padx=15, pady=6); self.status_bar.pack(side="bottom", fill="x")
        self.root.after(1000, self.apply_new_tags_loop)

    def apply_new_tags_loop(self):
        if getattr(self, 'data', None):
            import datetime; now = datetime.datetime.now()
            for tree in [getattr(self, 'tree_vehicles', None), getattr(self, 'tree_non_personal', None)]:
                if not tree or not tree.winfo_exists(): continue
                for child in tree.get_children():
                    try:
                        car = self.data["vehicles"][int(child)]; curr = tree.set(child, "name")
                        try: is_n = (now - datetime.datetime.strptime(car.get("updated_at", car.get("created_at", "")), '%Y-%m-%d %H:%M')).total_seconds() < 86400
                        except: is_n = False
                        if is_n and not curr.startswith("🆕 "): tree.set(child, "name", "🆕 " + curr.replace("🆕 ", ""))
                        elif not is_n and curr.startswith("🆕 "): tree.set(child, "name", curr.replace("🆕 ", ""))
                    except: pass
        self.root.after(3000, self.apply_new_tags_loop)

    def set_status(self, msg, color="#FF9800"):
        if hasattr(self, 'status_bar') and self.status_bar.winfo_exists(): self.status_bar.config(text=msg, fg=color)

    def log_action(self, msg):
        if not self.data: return
        self.data.setdefault("action_logs", []).append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]  {msg}"); self.data["action_logs"] = self.data["action_logs"][-200:]; save_data(self.all_data); self.refresh_logs_display()

    def center_toplevel_window(self, win, width, height):
        w, h = int(width * 1.1) + 40, int(height * 1.15) + 120; win.configure(bg=COLOR_MAIN_BG); self.root.update_idletasks()
        x, y = self.root.winfo_x() + (self.root.winfo_width() - w) // 2, max(30, self.root.winfo_y() + (self.root.winfo_height() - h) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}"); win.minsize(w, h)

    def sort_treeview(self, tv, col, reverse): return

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
        tf = tk.Frame(self.root, bg="#1a1a1a", pady=10); tf.pack(fill="x", side="top")
        self.lbl_current_user = tk.Label(tf, text="👤 當前狀態：尚未登入 (請至「帳號管理」登入)", bg="#1a1a1a", fg="#F39C12", font=FONT_BOLD); self.lbl_current_user.pack(side="left", padx=20)
        self.lbl_clock = tk.Label(tf, text="", bg="#1a1a1a", fg="#4CAF50", font=("Consolas", 13, "bold")); self.lbl_clock.pack(side="right", padx=20); self.update_clock() 

    def random_ride(self):
        if not self.data: return
        vc = [c for c in self.data["vehicles"] if c.get("v_type") == "個人載具" and c.get("garage") not in ["帕格薩斯", "未分類"]]
        if not vc: return messagebox.showinfo("隨機選車", "車庫裡目前沒有可用的個人載具喔！")
        car = random.choice(vc); win = tk.Toplevel(self.root); win.title("🎲 今天開哪台？"); self.center_toplevel_window(win, 350, 220); win.configure(bg=COLOR_CARD_BG)
        tk.Label(win, text="🎯 系統為您今日指定了：", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#e91e63").pack(pady=(20, 10)); tk.Label(win, text=f"🚗 【 {car['name']} 】", font=("Microsoft JhengHei", 18, "bold"), bg=COLOR_CARD_BG, fg="white").pack(); tk.Label(win, text=f"📍 停放於：{car['garage']}", font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="#3498db").pack(pady=10); ttk.Button(win, text="太棒了，今天就開這台！", command=win.destroy, style="Success.TButton").pack(pady=10)

    def update_clock(self): self.lbl_clock.config(text=f"🕒 {time.strftime('%Y-%m-%d  %H:%M:%S')}"); self.root.after(1000, self.update_clock)
    def update_profile_combo(self):
        if hasattr(self, "refresh_account_listbox"): self.refresh_account_listbox()

    # ==========================
    # 🖱️ 分頁右鍵快速隱藏系統
    # ==========================
    def show_tab_context_menu(self, event):
        try:
            # 取得游標下的分頁 ID
            tab_id = self.notebook.tk.call(self.notebook._w, "identify", "tab", event.x, event.y)
            if tab_id == '': return
            
            tab_name = self.notebook.tab(int(tab_id), "text").strip()
            
            if not hasattr(self, 'tab_popup_menu'): 
                self.tab_popup_menu = tk.Menu(self.root, tearoff=0, bg="#2d2d2d", fg="white", font=("Microsoft JhengHei", 10))
                
            self.tab_popup_menu.delete(0, tk.END)
            # 這裡使用全形空白以維持 V1.7.9 的對齊標準
            self.tab_popup_menu.add_command(label=f"👁️ 快速隱藏【{tab_name}】", command=lambda: self.hide_tab_by_name(tab_name))
            self.tab_popup_menu.post(event.x_root, event.y_root)
        except: pass

    def hide_tab_by_name(self, tab_name):
        if not getattr(self, 'data', None): 
            return messagebox.showwarning("提示", "請先登入帳號！")
            
        map_dict = {
            "🚗 車輛管理": "tab_vehicles", "🚜 非個人與帕格薩斯": "tab_non_personal", 
            "🚁 特殊載具": "tab_special", "🏠 車庫管理": "tab_garages", 
            "✈️ 機庫管理": "tab_hangars", "🛒 購車願望清單": "tab_wishlist", 
            "📚 攻略筆記": "tab_guides", "📊 統計資料": "tab_statistics", 
            "📜 操作日誌": "tab_logs"
        }
        
        if tab_name in map_dict:
            self.data.setdefault("app_settings", {})[map_dict[tab_name]] = False
            save_data(self.all_data)
            self.check_login_status() # 重新刷新分頁顯示狀態
            self.show_toast_progress(f"👁️ 已隱藏，可至全域設定恢復")
        else:
            messagebox.showinfo("提示", "此為系統核心分頁，不可隱藏！")

    def check_login_status(self):
        is_l = bool(self.current_id and self.current_id in self.all_data["profiles"])
        if hasattr(self, 'lbl_current_user'):
            file_path = os.path.abspath(DATA_FILE)
            if is_l:
                self.lbl_current_user.config(text=f"👤 當前登入：{self.current_id}    |    💾 存檔位置：{file_path}", fg="#4CAF50")
            else:
                self.lbl_current_user.config(text=f"👤 當前狀態：尚未登入 (請至「帳號管理」登入)    |    💾 存檔位置：{file_path}", fg="#F39C12")
        if hasattr(self, 'btn_tab_login'): self.btn_tab_login.config(state="disabled" if is_l else "normal"); self.btn_tab_logout.config(state="normal" if is_l else "disabled")
        if hasattr(self, "refresh_account_listbox"): self.refresh_account_listbox()
        if hasattr(self, 'edit_menu'):
            for i in [0, 1, 2]:
                try: self.edit_menu.entryconfig(i, state="normal" if is_l else "disabled")
                except: pass
        if is_l:
            self.data = self.all_data["profiles"][self.current_id]
            for k, d in [("vehicles", []), ("special_vehicles", []), ("garages", ["未分類", "帕格薩斯", "日蝕大樓", "日蝕大樓 - 車庫1"]), ("action_logs", []), ("acquire_options", ACQUIRE_OPTIONS.copy()), ("wishlist", []), ("guides", [])]:
                if k not in self.data: self.data[key] = d
            if "garage_limits" not in self.data:
                self.data["garage_limits"] = {"未分類": 999}; 
                for g in self.data["garages"]: 
                    if g != "未分類": self.data["garage_limits"][g] = 10
            if "app_settings" not in self.data: self.data["app_settings"] = {}
            for k, v in {"tab_bulletin": True, "tab_vehicles": True, "tab_non_personal": True, "tab_special": True, "tab_garages": True, "tab_hangars": True, "tab_statistics": True, "tab_logs": True, "tab_wishlist": True, "tab_guides": True, "tool_stopwatch": True, "disable_all_limits": False, "auto_backup": True, "default_garage_limit": 10, "default_special_limit": 2, "visible_columns": ["check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"]}.items():
                if k not in self.data["app_settings"]: self.data["app_settings"][k] = v
            for v in self.data["vehicles"]:
                if v.get("garage") == "帕格薩斯" or v.get("v_type") == "帕格薩斯": v.update({"garage":"帕格薩斯", "v_type":"帕格薩斯", "count":1, "upgraded":"不可改裝"})
            self.checked_indices.clear() 
            self.cd_target_sec = self.data["app_settings"].get("default_countdown_sec", 300.0)
            if not getattr(self, 'is_running', False) and self.sw_mode == "COUNTDOWN": self.elapsed_time = self.cd_target_sec; self.update_stopwatch_ui()
            vc = self.data["app_settings"].get("visible_columns", ["check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"])
            if hasattr(self, 'tree_vehicles') and self.tree_vehicles.winfo_exists(): self.tree_vehicles["displaycolumns"] = vc
            if hasattr(self, 'tree_non_personal') and self.tree_non_personal.winfo_exists(): self.tree_non_personal["displaycolumns"] = vc
        else: 
            self.current_id, self.data = "", None
            if hasattr(self, 'text_logs'): self.text_logs.config(state="normal"); self.text_logs.delete("1.0", tk.END); self.text_logs.config(state="disabled")
        s = self.data.get("app_settings", {}) if self.data else {}
        self.notebook.tab(self.tab_bulletin, state="normal"); self.notebook.tab(self.tab_account, state="normal")
        for k, t in [("tab_vehicles", self.tab_vehicles), ("tab_non_personal", self.tab_non_personal), ("tab_special", self.tab_special), ("tab_garages", self.tab_garages), ("tab_hangars", self.tab_hangars), ("tab_wishlist", self.tab_wishlist), ("tab_guides", self.tab_guides), ("tab_statistics", self.tab_statistics), ("tab_logs", self.tab_logs)]:
            self.notebook.tab(t, state="normal" if (is_l and s.get(k, True)) else "hidden")
        self.update_garage_comboboxes(); self.update_acquire_comboboxes(); self.refresh_vehicle_tables(); self.refresh_special_table(); self.refresh_garage_table(); self.apply_settings(); self.on_tab_changed()
        if is_l: self.refresh_bulletin_display(); self.refresh_logs_display(); self.refresh_wishlist_table(); self.refresh_guides_table(); self.update_checked_button_text()
        if is_l and self.notebook.select() and "統計" in self.notebook.tab(self.notebook.select(), "text"): self.refresh_statistics()

    def update_acquire_comboboxes(self):
        if hasattr(self, 'combo_acquire'): self.combo_acquire["values"] = self.data.get("acquire_options", ACQUIRE_OPTIONS) if self.data else ACQUIRE_OPTIONS

    def login_profile(self):
        sel_idx = self.list_accounts.curselection()
        if not sel_idx: return messagebox.showwarning("提示", "請選擇要登入的帳號！")
        sel = self.list_accounts.get(sel_idx[0]).replace("  (當前登入)", "").strip()
        if sel and sel in self.all_data["profiles"]: 
            self.current_id = sel; self.check_login_status(); self.show_toast_progress(f"🔑 登入成功：{sel}"); self.set_status(f"🔑 登入：{sel}", "#4CAF50"); self.log_action("🔑 登入系統"); self.on_tab_changed()
            if self.data.get("app_settings", {}).get("tab_vehicles", True): self.notebook.select(self.tab_vehicles)

    def logout_profile(self): 
        if self.data: self.log_action("🚪 登出系統")
        self.current_id = ""; self.check_login_status(); self.show_toast_progress("🚪 已登出"); self.set_status("🚪 已登出。", "#FF9800")

    def get_active_tree(self, event=None):
        if event and hasattr(event, 'widget') and isinstance(event.widget, ttk.Treeview): return event.widget
        if self.notebook.select() and "非個人" in self.notebook.tab(self.notebook.select(), "text"): return self.tree_non_personal
        return self.tree_vehicles

    def on_vehicle_hover(self, event):
        if not self.data: return
        t, iid = event.widget, event.widget.identify_row(event.y)
        if iid:
            if getattr(self, "last_hovered_iid", None) != iid:
                self.last_hovered_iid = iid
                try: self.set_status(f"🕒 【{self.data['vehicles'][int(iid)]['name']}】 登記：{self.data['vehicles'][int(iid)].get('created_at', '-')}   |   修改：{self.data['vehicles'][int(iid)].get('updated_at', '-')}", "#3498db")
                except: pass
        else:
            if getattr(self, "last_hovered_iid", None) is not None: self.last_hovered_iid = None; self.set_status("💡 系統就緒。", "#FF9800")

    def setup_account_tab(self):
        tk.Label(self.tab_account, text="👥 系統帳號與角色管理", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#3498db").pack(pady=(20, 15))
        fl = tk.LabelFrame(self.tab_account, text=" 🔑 選擇帳號登入 ", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="white"); fl.pack(fill="both", expand=True, padx=40, pady=10)
        sa = ttk.Scrollbar(fl); sa.pack(side="right", fill="y")
        self.list_accounts = tk.Listbox(fl, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", selectbackground="#3498db", yscrollcommand=sa.set, relief="solid"); self.list_accounts.pack(side="left", fill="both", expand=True, padx=(15, 0), pady=15); sa.config(command=self.list_accounts.yview)
        self.list_accounts.bind("<Double-1>", lambda e: self.login_profile()); self.list_accounts.bind("<Return>", lambda e: self.login_profile())
        bfl = tk.Frame(fl, bg=COLOR_CARD_BG); bfl.pack(side="right", fill="y", padx=15, pady=15)
        self.btn_tab_login = ttk.Button(bfl, text="🔑 登入選取帳號", command=self.login_profile, style="Success.TButton"); self.btn_tab_login.pack(fill="x", pady=5, ipady=4)
        self.btn_tab_logout = ttk.Button(bfl, text="🚪 登出當前帳號", command=self.logout_profile, style="Warning.TButton"); self.btn_tab_logout.pack(fill="x", pady=5, ipady=4)
        ttk.Button(bfl, text="❌ 刪除選取的帳號", command=self.delete_profile_from_tab, style="Danger.TButton").pack(side="bottom", fill="x", pady=5, ipady=4)
        fa = tk.LabelFrame(self.tab_account, text=" ➕ 註冊新帳號/角色 ID ", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="#4CAF50"); fa.pack(fill="x", padx=40, pady=10, ipady=5)
        tk.Label(fa, text="輸入新 ID 名稱:", font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white").pack(side="left", padx=(15,5), pady=15)
        self.entry_new_account = tk.Entry(fa, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=25); self.entry_new_account.pack(side="left", padx=5); apply_focus_highlight(self.entry_new_account)
        ttk.Button(fa, text="建立帳號", command=self.create_profile_from_tab, style="Success.TButton").pack(side="left", padx=10); self.entry_new_account.bind("<Return>", lambda e: self.create_profile_from_tab())
        self.refresh_account_listbox()

    def refresh_account_listbox(self):
        if hasattr(self, 'list_accounts') and self.list_accounts.winfo_exists():
            self.list_accounts.delete(0, tk.END)
            for acc in self.all_data.get("profiles", {}).keys():
                if acc == self.current_id: self.list_accounts.insert(tk.END, f"{acc}  (當前登入)"); self.list_accounts.itemconfig(tk.END, {'fg': '#4CAF50'})
                else: self.list_accounts.insert(tk.END, acc)

    def create_profile_from_tab(self):
        name = self.entry_new_account.get().strip()
        if not name: return messagebox.showwarning("提示", "請輸入角色 ID 名稱！")
        if name in self.all_data["profiles"]: return messagebox.showwarning("重複", "ID 已經存在！")
        self.all_data["profiles"][name] = {"vehicles": [], "special_vehicles": [], "garages": ["未分類", "帕格薩斯", "日蝕大樓", "日蝕大樓 - 車庫1"], "garage_limits": {"未分類": 999, "帕格薩斯": 999, "日蝕大樓": 10, "日蝕大樓 - 車庫1": 10}, "action_logs": [f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]  🌟 建立角色 ID 檔案"], "acquire_options": ACQUIRE_OPTIONS.copy(), "wishlist": [], "app_settings": {"tab_bulletin": True, "tab_vehicles": True, "tab_non_personal": True, "tab_special": True, "tab_garages": True, "tab_hangars": True, "tab_statistics": True, "tab_logs": True, "tab_wishlist": True, "tab_guides": True, "tool_stopwatch": True, "disable_all_limits": False, "auto_backup": True, "default_garage_limit": 10, "default_special_limit": 2, "visible_columns": ["check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"]}}
        save_data(self.all_data); self.refresh_account_listbox(); self.entry_new_account.delete(0, tk.END); self.show_toast_progress(f"✅ 成功建立：{name}")

    def delete_profile_from_tab(self):
        if self.current_id: return messagebox.showwarning("提示", "請先登出！")
        s = self.list_accounts.curselection()
        if not s: return messagebox.showwarning("提示", "請先選取要刪除的帳號！")
        acc = self.list_accounts.get(s[0]).replace("  (當前登入)", "").strip()
        if messagebox.askyesno("⚠️ 極度危險操作", f"確定徹底刪除 ID：【 {acc} 】嗎？"):
            vc = str(random.randint(100000, 999999))
            ui = simpledialog.askstring("安全驗證", f"⚠️ 資料無法還原！\n請輸入密碼以抹除：\n\n【 {vc} 】", parent=self.root)
            if ui == vc: del self.all_data["profiles"][acc]; save_data(self.all_data); self.show_toast_progress(f"❌ 已抹除：{acc}"); self.set_status(f"❌ 移除 {acc}。", "#c62828"); self.refresh_account_listbox()
            elif ui is not None: messagebox.showerror("驗證失敗", "密碼錯誤。")

    def setup_bulletin_tab(self):
        tk.Label(self.tab_bulletin, text="📢 洛聖都資產管理系統 - 系統公告", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#4CAF50").pack(pady=(30, 15))
        tf = tk.Frame(self.tab_bulletin, bg=COLOR_MAIN_BG); tf.pack(fill="both", expand=True, padx=40, pady=(0, 40))
        sb = ttk.Scrollbar(tf); sb.pack(side="right", fill="y")
        self.text_bulletin = tk.Text(tf, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, relief="solid", padx=20, pady=20, wrap="word", yscrollcommand=sb.set); self.text_bulletin.pack(side="left", fill="both", expand=True); sb.config(command=self.text_bulletin.yview); self.refresh_bulletin_display()
        
    def refresh_bulletin_display(self):
        if not hasattr(self, 'text_bulletin') or not self.text_bulletin.winfo_exists(): return
        cl = f"""==================================================
【GTAV 資產管理系統 - 開發與重大更新日誌】
🌟 目前版本：V{APP_VERSION} (極致體驗升級版)
📅 更新日期：2026-09

==================================================
【 🚀 近期重大更新 (V1.8.0 ~ V1.8.6) 】
==================================================
🔹 V1.8.6 - 全域分頁自動聚焦
  • [新增] 切換任何頁面時，清單將自動平滑滾動至最底部的最新一筆資料。
  • [優化] 操作日誌智慧反向聚焦，確保永遠優先顯示最新的操作紀錄。

🔹 V1.8.3 ~ V1.8.5 - 體驗優化與防呆保護機制
  • [新增] 分頁列快捷操作：對著上方分頁標籤點擊「右鍵」可快速將其隱藏。
  • [防護] 全域設定「自動備份資料」加入防手滑二次確認警告，保護存檔安全。
  • [淨化] 移除車庫選單內冗餘的舊版機庫快捷鍵，維持資料庫最高純粹度。

🔹 V1.8.0 ~ V1.8.2 - 歷史建檔與排版完美對齊
  • [新增] 系統公告板完整建檔從 V1.0 到最新版本的血汗開發歷史。
  • [修復] 根治 Windows 底層 Emoji (🛡️、🗑️) 寬度渲染導致的介面內縮 Bug。
  • [優化] 右鍵智慧選單圖示全面標準化 (❌、📝、📌、🔒)，達成 100% 垂直對齊。

==================================================
【 ✈️ 機庫系統大型擴展 (V1.7.0 ~ V1.7.6) 】
==================================================
  • [新增] 打造全新「✈️ 機庫管理」專屬大分頁，資料庫與一般車輛徹底分離。
  • [新增] 內建官方 5 大機庫地產圖鑑，支援「一鍵購買解鎖」。
  • [優化] 機庫採用「雙拼空間調度佈局」，左側機庫清單連動右側專屬機隊。
  • [防護] 嚴密登入安全鎖，未登入時機庫資料強制隱藏，並深度掛載至全域設定。

==================================================
【 🛠️ 歷史核心更新回顧 (V1.0.0 ~ V1.6.8) 】
==================================================
  • [重構] 徹底根治陣列錯位與閃退問題，系統穩定度大幅提升。
  • [新增] 獨立出全新的「🏠 車庫管理」彈出式視窗，告別擁擠的舊版面。
  • [新增] 導入「📚 攻略筆記」極簡全螢幕模式，支援多行菁英條件預覽。
  • [新增] 手動備份升級為「單一角色」，並支援「跨角色繼承轉移」。
  • [新增] 內建「⏱️ 任務碼錶工具」，支援正向計時與自訂倒數功能。
=================================================="""
        self.text_bulletin.config(state="normal"); self.text_bulletin.delete("1.0", tk.END); self.text_bulletin.insert("1.0", cl); self.text_bulletin.config(state="disabled")

    def setup_statistics_tab(self):
        tk.Label(self.tab_statistics, text="📊 洛聖都資產統計儀表板", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#F39C12").pack(pady=(20, 10))
        self.canvas_stats = tk.Canvas(self.tab_statistics, borderwidth=0, bg=COLOR_MAIN_BG, highlightthickness=0); sb = ttk.Scrollbar(self.tab_statistics, orient="vertical", command=self.canvas_stats.yview); self.stats_frame = tk.Frame(self.canvas_stats, bg=COLOR_MAIN_BG); self.stats_frame.bind("<Configure>", lambda e: self.canvas_stats.configure(scrollregion=self.canvas_stats.bbox("all"))); self.canvas_stats.create_window((0, 0), window=self.stats_frame, anchor="nw", width=1200); self.canvas_stats.configure(yscrollcommand=sb.set); self.canvas_stats.pack(side="left", fill="both", expand=True, padx=15, pady=10); sb.pack(side="right", fill="y"); self.tab_statistics.bind("<Enter>", lambda e: self.canvas_stats.bind_all("<MouseWheel>", lambda ev: self.canvas_stats.yview_scroll(int(-1 * (ev.delta / 120)), "units") if hasattr(self, 'canvas_stats') and self.canvas_stats.winfo_exists() else None)); self.tab_statistics.bind("<Leave>", lambda e: self.canvas_stats.unbind_all("<MouseWheel>"))

    def refresh_statistics(self):
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
        if not self.data: return
        
        vehicles = self.data.get("vehicles", [])
        garages = self.data.get("garages", [])
        specials = self.data.get("special_vehicles", [])
        limits = self.data.get("garage_limits", {})
        disable_limits = self.data.get("app_settings", {}).get("disable_all_limits", False)
        
        total_cars = sum(v.get("count", 1) for v in vehicles)
        actual_garages = [g for g in garages if g not in ["未分類", "帕格薩斯"]]
        total_garages = len(actual_garages)
        
        type_counts = {"個人載具": 0, "非個人載具": 0, "帕格薩斯": 0, "個人飛行載具": 0, "未設定": 0}
        upg_counts = {"已改滿": 0, "未改滿": 0, "不可改裝": 0, "未設定": 0}
        acq_counts = {}
        total_value = 0 
        
        for v in vehicles:
            c = v.get("count", 1)
            try: p = int(v.get("price", 0))
            except: p = 0
            total_value += (p * c)
            
            vt = v.get("v_type", "") or "未設定"
            type_counts[vt] = type_counts.get(vt, 0) + c
            
            upg = v.get("upgraded", "") or "未設定"
            upg_counts[upg] = upg_counts.get(upg, 0) + c
            
            acq = v.get("acquire", "") or "未設定"
            acq_counts[acq] = acq_counts.get(acq, 0) + c
            
        total_capacity = sum(limits.get(g, 10) for g in actual_garages) + sum(limits.get(sv.get("name"), 2) for sv in specials if sv.get("can_store", False))
        total_used_in_capacity = sum(self.count_cars_in_garage(g) for g in actual_garages) + sum(self.count_cars_in_garage(sv.get("name")) for sv in specials if sv.get("can_store", False))
        
        row1 = tk.Frame(self.stats_frame, bg=COLOR_MAIN_BG)
        row1.pack(fill="x", pady=10)
        
        def create_stat_card(parent, title, value, color): 
            f = tk.Frame(parent, bg=COLOR_CARD_BG, highlightbackground=color, highlightthickness=2, padx=15, pady=15)
            f.pack(side="left", fill="both", expand=True, padx=10)
            tk.Label(f, text=title, font=FONT_BOLD, bg=COLOR_CARD_BG, fg=COLOR_TEXT_GRAY).pack()
            tk.Label(f, text=str(value), font=("Consolas", 24, "bold"), bg=COLOR_CARD_BG, fg=color).pack(pady=(10, 0))
            
        create_stat_card(row1, "🚗 總擁有載具數量", total_cars, "#3498db")
        create_stat_card(row1, "💎 車庫總資產估值", f"$ {total_value:,}", "#9b59b6")
        create_stat_card(row1, "🏠 總車庫/樓層數", total_garages, "#4CAF50")
        create_stat_card(row1, "🅿️ 總車位使用率", f"{total_used_in_capacity} / ∞" if disable_limits else f"{total_used_in_capacity} / {total_capacity}", "#F39C12")
        
        row2 = tk.Frame(self.stats_frame, bg=COLOR_MAIN_BG)
        row2.pack(fill="x", pady=15)
        
        def create_bar_stat(parent, title, items): 
            f = tk.LabelFrame(parent, text=f" {title} ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="white", bd=2, padx=20, pady=20)
            f.pack(side="left", fill="both", expand=True, padx=10)
            tot = sum(val for val, lbl, color in items) or 1 
            for idx, (val, lbl, color) in enumerate(items): 
                pct = val / tot * 100
                tk.Label(f, text=f"{lbl} ({val}) - {pct:.1f}%", font=FONT_BOLD, bg=COLOR_CARD_BG, fg=color).pack(anchor="w")
                ttk.Progressbar(f, length=400, mode="determinate", value=pct).pack(fill="x", pady=(2, 10 if idx < len(items) - 1 else 0))
                
        create_bar_stat(row2, "🔧 改裝狀態分布", [(upg_counts["已改滿"], "✅ 已改滿", "#4CAF50"), (upg_counts["未改滿"], "⚠️ 未改滿", "#e74c3c"), (upg_counts["不可改裝"], "❌ 不可改裝", "#9b59b6"), (upg_counts["未設定"], "❓ 未設定", "#95a5a6")])
        create_bar_stat(row2, "🚜 載具類型分布", [(type_counts["個人載具"], "🚗 個人載具", "#3498db"), (type_counts["非個人載具"], "🚜 非個人載具", "#F39C12"), (type_counts["帕格薩斯"], "🚁 帕格薩斯", "#9b59b6"), (type_counts["個人飛行載具"], "✈️ 飛行載具", "#00BCD4"), (type_counts["未設定"], "❓ 未設定", "#95a5a6")])
        
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

    def setup_logs_tab(self):
        hf = tk.Frame(self.tab_logs, bg=COLOR_MAIN_BG); hf.pack(fill="x", padx=15, pady=15); tk.Label(hf, text="📜 操作日誌", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#4CAF50").pack(side="left"); ttk.Button(hf, text="❌ 清空日誌", command=self.clear_logs, style="Danger.TButton").pack(side="right")
        self.text_logs = tk.Text(self.tab_logs, font=("Consolas", 11), bg=COLOR_CARD_BG, fg="#a8e6cf", relief="solid", padx=15, pady=15); sb = ttk.Scrollbar(self.tab_logs, orient="vertical", command=self.text_logs.yview); self.text_logs.configure(yscrollcommand=sb.set); sb.pack(side="right", fill="y", pady=(0, 15), padx=(0, 15)); self.text_logs.pack(fill="both", expand=True, padx=(15, 0), pady=(0, 15)); self.text_logs.config(state="disabled")

    def refresh_logs_display(self):
        if not hasattr(self, 'text_logs') or not self.text_logs.winfo_exists(): return
        self.text_logs.config(state="normal"); self.text_logs.delete("1.0", tk.END)
        if self.data and "action_logs" in self.data:
            for log in reversed(self.data["action_logs"]): self.text_logs.insert(tk.END, log + "\n\n")
        self.text_logs.config(state="disabled")

    def clear_logs(self):
        if not self.data: return
        if messagebox.askyesno("警告", "確定要清空操作日誌？"): self.data["action_logs"] = []; save_data(self.all_data); self.refresh_logs_display(); self.show_toast_progress("❌ 日誌已清空"); self.log_action("❌ 清空日誌")
    def setup_wishlist_tab(self):
        inf = tk.LabelFrame(self.tab_wishlist, text=" 🛒 新增願望 ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#3498db", padx=12, pady=12, bd=2); inf.pack(fill="x", padx=15, pady=10)
        for i in range(5): inf.columnconfigure(i, weight=0)
        inf.columnconfigure(1, weight=1); inf.columnconfigure(3, weight=1)
        tk.Label(inf, text="名稱:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=0, column=0, sticky="e", pady=5, padx=5); self.ewn = tk.Entry(inf, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); self.ewn.grid(row=0, column=1, sticky="we", padx=5, pady=5); apply_focus_highlight(self.ewn)
        tk.Label(inf, text="價格:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=0, column=2, sticky="e", pady=5, padx=5); self.ewp = tk.Entry(inf, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); self.ewp.grid(row=0, column=3, sticky="we", padx=5, pady=5); apply_focus_highlight(self.ewp)
        tk.Label(inf, text="備註:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=1, column=0, sticky="e", pady=5, padx=5); self.ewo = tk.Entry(inf, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); self.ewo.grid(row=1, column=1, columnspan=3, sticky="we", padx=5, pady=5); apply_focus_highlight(self.ewo)
        ttk.Button(inf, text="➕ 加入", command=self.add_wishlist, style="Primary.TButton", padding=(20, 4)).grid(row=0, column=4, rowspan=2, sticky="ns", padx=(15, 5), pady=5)
        self.ewn.bind("<Return>", lambda e: self.ewp.focus()); self.ewp.bind("<Return>", lambda e: self.ewo.focus()); self.ewo.bind("<Return>", lambda e: self.add_wishlist())
        af = tk.Frame(self.tab_wishlist, bg=COLOR_MAIN_BG); af.pack(fill="x", padx=15, pady=5); ttk.Button(af, text="🎉 買到了！轉入車庫", command=self.buy_wishlist_item, style="Success.TButton").pack(side="left", padx=3); ttk.Button(af, text="❌ 放棄購買", command=self.delete_wishlist_item, style="Danger.TButton").pack(side="right", padx=3)
        tf = tk.Frame(self.tab_wishlist, bg=COLOR_MAIN_BG); tf.pack(fill="both", expand=True, padx=15, pady=10); self.tree_wishlist = ttk.Treeview(tf, columns=("name", "price", "notes"), show="headings", selectmode="extended"); self.tree_wishlist.heading("name", text="目標車輛名稱"); self.tree_wishlist.heading("price", text="預計花費(GTA$)"); self.tree_wishlist.heading("notes", text="願望備註"); self.tree_wishlist.column("name", width=250, anchor="w", stretch=True); self.tree_wishlist.column("price", width=150, anchor="center", stretch=False); self.tree_wishlist.column("notes", width=350, anchor="w", stretch=True); sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree_wishlist.yview); self.tree_wishlist.configure(yscrollcommand=sb.set); sb.pack(side="right", fill="y"); self.tree_wishlist.pack(side="left", fill="both", expand=True)

    def refresh_wishlist_table(self):
        if not hasattr(self, 'tree_wishlist'): return
        for i in self.tree_wishlist.get_children(): self.tree_wishlist.delete(i)
        if not self.data or "wishlist" not in self.data: return
        for idx, w in enumerate(self.data["wishlist"]): self.tree_wishlist.insert("", "end", iid=str(idx), values=(w.get("name", ""), f"$ {int(w.get('price', 0)):,}" if w.get('price') else "$ 0", w.get("notes", "")))

    def add_wishlist(self):
        if not self.data: return
        n = self.ewn.get().strip()
        if not n: return
        try: p = int(self.ewp.get().strip() or 0)
        except: p = 0
        self.data.setdefault("wishlist", []).append({"name": n, "price": p, "notes": self.ewo.get()}); save_data(self.all_data); self.log_action(f"🛒 加入願望：{n}"); self.ewn.delete(0, tk.END); self.ewp.delete(0, tk.END); self.ewo.delete(0, tk.END); self.refresh_wishlist_table(); self.show_toast_progress("🛒 願望已加入！")

    def delete_wishlist_item(self):
        if not self.data or "wishlist" not in self.data: return
        sel = self.tree_wishlist.selection()
        if not sel: return
        if messagebox.askyesno("刪除", "確定移除？"):
            for i in sorted([int(s) for s in sel], reverse=True): del self.data["wishlist"][i]
            save_data(self.all_data); self.refresh_wishlist_table(); self.show_toast_progress("❌ 已從願望清單移除")

    def buy_wishlist_item(self):
        if not self.data or "wishlist" not in self.data: return
        sel = self.tree_wishlist.selection()
        if not sel: return messagebox.showwarning("提示", "請先點選願望車輛！")
        c = 0
        for i in sorted([int(s) for s in sel], reverse=True): 
            w = self.data["wishlist"][i]
            self.data["vehicles"].append({"name": w["name"], "garage": "未分類", "v_type": "", "acquire": "購買獲得", "price": w["price"], "upgraded": "未改滿", "count": 1, "notes": w["notes"], "locked": False, "pinned": False, "created_at": time.strftime('%Y-%m-%d %H:%M'), "updated_at": time.strftime('%Y-%m-%d %H:%M')})
            del self.data["wishlist"][i]; c += 1
        save_data(self.all_data); self.log_action(f"🎉 願望達成：牽入 {c} 台夢想載具！"); self.refresh_wishlist_table(); self.refresh_vehicle_tables(); self.refresh_statistics(); messagebox.showinfo("🎉 恭喜！", f"成功移入 {c} 輛車！\n停放在【未分類】！"); self.notebook.select(self.tab_vehicles)

    def update_checked_button_text(self):
        c = len(self.checked_indices) if hasattr(self, 'checked_indices') else 0
        if hasattr(self, 'btn_batch_edit_v') and self.btn_batch_edit_v.winfo_exists(): self.btn_batch_edit_v.config(text=f"📝 編輯已勾選載具 ({c})")
        if hasattr(self, 'edit_menu'):
            try: self.edit_menu.entryconfig(1, label=f"📝 編輯已勾選載具 ({c})")
            except: pass

    def on_tree_click(self, event):
        if not self.data: return
        t = event.widget
        if t.identify_region(event.x, event.y) != "cell": return
        cs = t.identify_column(event.x)
        if not cs: return
        ci = int(cs.replace("#", "")) - 1
        dc = t.cget("displaycolumns")
        ac = t.cget("columns")[ci] if not dc or dc == "#all" else dc[ci]
        if ac == "check": 
            iid = t.identify_row(event.y)
            if not iid: return
            i = int(iid)
            if i in self.checked_indices: self.checked_indices.remove(i); t.set(iid, "check", "☐")
            else: self.checked_indices.add(i); t.set(iid, "check", "☑")
            self.update_checked_button_text()

    def select_all_vehicles(self, event=None):
        if not self.data: return
        t = self.get_active_tree(event); c = 0
        for ch in t.get_children():
            i = int(ch)
            if i not in self.checked_indices: self.checked_indices.add(i); t.set(ch, "check", "☑"); c += 1
        self.update_checked_button_text(); self.set_status(f"☑️ 已全選 {c} 筆載具！", "#9b59b6")

    def edit_checked_vehicles(self):
        if not self.data: return
        if not self.checked_indices: return messagebox.showwarning("提示", "您還沒有勾選任何載具！")
        self.open_edit_window(pre_selected=[str(i) for i in self.checked_indices])

    def check_duplicate_vehicles(self):
        if self.check_win('dup_window'): return
        if not self.data: return
        nm = defaultdict(list)
        for i, v in enumerate(self.data.get("vehicles", [])): nm[v["name"].strip().lower()].append(i)
        dup = {n: ind for n, ind in nm.items() if len(ind) > 1}
        if not dup: return messagebox.showinfo("檢查", "✅ 無重複車輛。")
        self.dup_window = win = tk.Toplevel(self.root); win.title("🔍 發現重複"); self.center_toplevel_window(win, 450, 500); win.configure(bg=COLOR_CARD_BG)
        tk.Label(win, text=f"⚠️ 發現 {len(dup)} 組重複：", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#F39C12").pack(pady=(15, 5))
        fl = tk.Frame(win, bg=COLOR_MAIN_BG); fl.pack(fill="both", expand=True, padx=25, pady=5); sb = ttk.Scrollbar(fl); sb.pack(side="right", fill="y")
        lb = tk.Listbox(fl, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", yscrollcommand=sb.set, relief="solid", selectbackground="#4CAF50")
        for n, ind in dup.items():
            lb.insert(tk.END, f"▪ {self.data['vehicles'][ind[0]]['name']} (共 {len(ind)} 筆)")
            lb.insert(tk.END, f"  📍 分佈: {', '.join([self.data['vehicles'][i]['garage'] for i in ind])[:27] + '...'}")
            lb.insert(tk.END, "") 
        lb.pack(side="left", fill="both", expand=True); sb.config(command=lb.yview)
        def merge():
            if not messagebox.askyesno("確認", "確定合併嗎？", parent=win): return
            dl = []; c = 0
            for n, ind in dup.items():
                f_idx = ind[0]; ext = 0
                ip = self.data["vehicles"][f_idx].get("garage") == "帕格薩斯" or self.data["vehicles"][f_idx].get("v_type") == "帕格薩斯"
                for o_idx in ind[1:]:
                    if not ip: ext += int(self.data["vehicles"][o_idx].get("count", 1) or 1)
                    dl.append(o_idx); c += 1
                if ip: self.data["vehicles"][f_idx]["count"] = 1; self.data["vehicles"][f_idx]["upgraded"] = "不可改裝"
                else: self.data["vehicles"][f_idx]["count"] = int(self.data["vehicles"][f_idx].get("count", 1) or 1) + ext
                self.data["vehicles"][f_idx]["updated_at"] = time.strftime('%Y-%m-%d %H:%M')
            for i in sorted(dl, reverse=True): del self.data["vehicles"][i]
            self.checked_indices.clear(); self.update_checked_button_text(); self.sync_special_from_vehicles(); save_data(self.all_data); self.refresh_vehicle_tables(); self.refresh_special_table(); self.refresh_garage_table(); self.show_toast_progress(f"✅ 合併 {c} 筆"); win.destroy()
        bf = tk.Frame(win, bg=COLOR_CARD_BG); bf.pack(fill="x", padx=25, pady=15)
        ttk.Button(bf, text="✨ 一鍵智能合併", command=merge, style="Primary.TButton").pack(side="left", expand=True, fill="x", padx=(0, 5), ipady=4); ttk.Button(bf, text="關閉", command=win.destroy, style="Secondary.TButton").pack(side="right", expand=True, fill="x", padx=(5, 0), ipady=4)

    def _setup_tree(self, tree):
        for col, text in {"check": "☑", "name": "車輛名稱", "garage": "存放位置", "vtype": "類型", "acquire": "取得方式", "price":"價值(GTA$)", "upgrade": "改裝", "count": "數量", "notes": "備註"}.items(): tree.heading(col, text=text)
        for col, w in zip(["check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"], [60, 180, 140, 90, 100, 110, 80, 50, 120]): tree.column(col, width=w, anchor="center" if col not in ["name", "notes"] else "w", stretch=(col in ["name", "garage", "notes"]))
        tree.bind("<ButtonRelease-1>", self.on_tree_click); tree.bind("<Control-a>", self.select_all_vehicles); tree.bind("<Control-A>", self.select_all_vehicles); tree.bind("<Double-1>", self.open_edit_window); tree.bind("<Return>", self.open_edit_window); tree.bind("<Delete>", self.delete_vehicle); tree.bind("<Motion>", self.on_vehicle_hover); tree.bind("<Leave>", lambda e: self.set_status("💡 系統就緒。", "#FF9800")); tree.bind("<Button-3>", self.show_vehicle_context_menu)

    def setup_vehicles_tab(self):
        inf = tk.LabelFrame(self.tab_vehicles, text=" 📝 登記新載具資產 ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#4CAF50", padx=12, pady=12, bd=2)
        inf.pack(fill="x", padx=15, pady=(5, 10))
        
        # 總共需要 9 個欄位 (4個標籤 + 4個輸入框 + 1個按鈕 = index 0~8)
        for i in range(9): 
            inf.columnconfigure(i, weight=0)
            
        # 讓輸入框 (index 1, 3, 5, 7) 可以自動延伸寬度
        inf.columnconfigure(1, weight=1)
        inf.columnconfigure(3, weight=1)
        inf.columnconfigure(5, weight=1)
        inf.columnconfigure(7, weight=1)
        
        # --- 第 1 組：載具名稱 ---
        tk.Label(inf, text="載具名稱:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=0, sticky="e", pady=5, padx=5)
        self.entry_name = tk.Entry(inf, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid")
        self.entry_name.grid(row=0, column=1, sticky="we", padx=5, pady=5)
        apply_focus_highlight(self.entry_name)
        
        # --- 第 2 組：存放位置 ---
        tk.Label(inf, text="存放位置:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=2, sticky="e", pady=5, padx=5)
        self.combo_garage = ttk.Combobox(inf, state="readonly", font=FONT_NORMAL)
        self.combo_garage.grid(row=0, column=3, sticky="we", padx=5, pady=5)
        
        # --- 第 3 組：取得方式 ---
        tk.Label(inf, text="取得方式:", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=4, sticky="e", pady=5, padx=5)
        self.combo_acquire = ttk.Combobox(inf, state="readonly", font=FONT_NORMAL)
        self.combo_acquire.grid(row=0, column=5, sticky="we", padx=5, pady=5)
        
        # --- 第 4 組：購入價格 ---
        tk.Label(inf, text="購入價格(GTA$):", bg=COLOR_CARD_BG, fg=COLOR_TEXT_WHITE, font=FONT_NORMAL).grid(row=0, column=6, sticky="e", pady=5, padx=5)
        self.entry_price = tk.Entry(inf, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid")
        self.entry_price.grid(row=0, column=7, sticky="we", padx=5, pady=5)
        apply_focus_highlight(self.entry_price)
        
        # --- 第 5 組：新增按鈕 (全部都在 row 0，取消原本的 rowspan) ---
        ttk.Button(inf, text="➕ 新增登記", command=self.add_vehicle, style="Success.TButton", padding=(15, 4)).grid(row=0, column=8, sticky="ns", padx=(10, 5), pady=5)
        
        # 綁定 Enter 鍵自動跳到下一格的快捷功能
        self.entry_name.bind("<Return>", lambda e: self.combo_garage.focus())
        self.combo_garage.bind("<Return>", lambda e: self.combo_acquire.focus())
        self.combo_acquire.bind("<Return>", lambda e: self.entry_price.focus())
        self.entry_price.bind("<Return>", lambda e: self.add_vehicle())
        af = tk.Frame(self.tab_vehicles, bg=COLOR_MAIN_BG); af.pack(fill="x", padx=15, pady=5)
        tk.Label(af, text="🔍 全域搜尋:", bg=COLOR_MAIN_BG, fg="white", font=FONT_NORMAL).pack(side="left")
        self.entry_search = tk.Entry(af, width=20, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid"); self.entry_search.pack(side="left", padx=5); self.entry_search.bind("<KeyRelease>", self.apply_filters); apply_focus_highlight(self.entry_search) 
        tk.Label(af, text="  |  篩選車庫位置:", bg=COLOR_MAIN_BG, fg="white", font=FONT_NORMAL).pack(side="left", padx=5)
        self.combo_garage_filter = ttk.Combobox(af, width=20, state="readonly", font=FONT_NORMAL); self.combo_garage_filter.pack(side="left", padx=5); self.combo_garage_filter.bind("<<ComboboxSelected>>", self.apply_filters)
        ttk.Button(af, text="重置", command=self.reset_filters, style="Secondary.TButton").pack(side="left", padx=6); ttk.Button(af, text="👁️ 欄位設定", command=self.open_column_selector, style="Dark.TButton").pack(side="left", padx=6)
        tf = tk.Frame(self.tab_vehicles, bg=COLOR_MAIN_BG); tf.pack(fill="both", expand=True, padx=15, pady=10)
        self.tree_vehicles = ttk.Treeview(tf, columns=("check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"), show="headings", selectmode="extended")
        self._setup_tree(self.tree_vehicles); sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree_vehicles.yview); self.tree_vehicles.configure(yscrollcommand=sb.set); sb.pack(side="right", fill="y"); self.tree_vehicles.pack(side="left", fill="both", expand=True)
        self.vehicle_popup_menu = tk.Menu(self.root, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)

    def setup_non_personal_tab(self):
        hf = tk.Frame(self.tab_non_personal, bg=COLOR_MAIN_BG); hf.pack(fill="x", padx=15, pady=15)
        tk.Label(hf, text="🚜 非個人載具列表", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#FF9800").pack(side="left"); tk.Label(hf, text=" (請統一在「車輛管理」面板新增)", font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg=COLOR_TEXT_GRAY).pack(side="left")
        ttk.Button(hf, text="👁️ 欄位設定", command=self.open_column_selector, style="Dark.TButton").pack(side="right", padx=3)
        tf = tk.Frame(self.tab_non_personal, bg=COLOR_MAIN_BG); tf.pack(fill="both", expand=True, padx=15, pady=5)
        self.tree_non_personal = ttk.Treeview(tf, columns=("check", "name", "garage", "vtype", "acquire", "price", "upgrade", "count", "notes"), show="headings", selectmode="extended")
        self._setup_tree(self.tree_non_personal); sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree_non_personal.yview); self.tree_non_personal.configure(yscrollcommand=sb.set); sb.pack(side="right", fill="y"); self.tree_non_personal.pack(side="left", fill="both", expand=True)

    def update_garage_comboboxes(self):
        if not self.data: return
        sc = [sv["name"] for sv in self.data.get("special_vehicles", []) if sv.get("can_store", False)]
        ug = [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]
        cl = ["未分類", "帕格薩斯"] + ug + sc
        if hasattr(self, 'combo_garage'): self.combo_garage["values"] = cl
        if hasattr(self, 'combo_garage_filter'): 
            self.combo_garage_filter["values"] = ["全部"] + cl
            if self.combo_garage_filter.get() == "": self.combo_garage_filter.set("全部")
        if hasattr(self, 'combo_spec_location'):
            self.combo_spec_location["values"] = ["未分類"] + ug
            if not self.combo_spec_location.get(): self.combo_spec_location.set("未分類")

    def count_cars_in_garage(self, garage_name):
        return sum(c.get("count", 1) for c in self.data["vehicles"] if c["garage"] == garage_name) if self.data else 0

    def refresh_vehicle_tables(self, search_results=None):
        if not self.data: return
        ds = search_results if search_results is not None else enumerate(self.data["vehicles"])
        pi, ni = [], []
        for i, c in ds:
            if c.get("pinned", False): pi.append((i, c))
            else: ni.append((i, c))
        em = set(self.tree_vehicles.get_children()); en = set(self.tree_non_personal.get_children()) if hasattr(self, 'tree_non_personal') else set()
        nm, nn, ts = set(), set(), time.strftime('%Y-%m-%d')
        for i, c in pi + ni:
            iid = str(i); dn = ("🆕 " if c.get("created_at", "").startswith(ts) else "") + c["name"]
            if c.get("locked", False): dn = "🔒 " + dn
            if c.get("pinned", False): dn = "📌 " + dn
            vs = ("☑" if i in getattr(self, 'checked_indices', set()) else "☐", dn, c["garage"], c.get("v_type", ""), c.get("acquire", ""), f"$ {int(c.get('price', 0)):,}" if c.get("price") else "$ 0", c.get("upgraded", ""), c.get("count", 1), c.get("notes", ""))
            isp = c.get("v_type", "") in ["非個人載具", "帕格薩斯"]; tt = self.tree_non_personal if isp and hasattr(self, 'tree_non_personal') else self.tree_vehicles; tse = nn if isp else nm; tse.add(iid)
            if iid in (en if isp else em): tt.item(iid, values=vs); tt.move(iid, "", "end")
            else: tt.insert("", "end", iid=iid, values=vs)
        for iid in em - nm: self.tree_vehicles.delete(iid)
        if hasattr(self, 'tree_non_personal'):
            for iid in en - nn: self.tree_non_personal.delete(iid)

    def add_vehicle(self):
        if not self.data: return
        name = self.entry_name.get().strip()
        garage = self.combo_garage.get().strip() or "未分類"
        if not name: return
        vtype = ""
        upgraded = ""
        count = 1
        try: price = int(self.entry_price.get().strip() or 0)
        except: price = 0
        disable_limits = self.data.get("app_settings", {}).get("disable_all_limits", False)
        
        if garage == "帕格薩斯": 
            vtype = "帕格薩斯"
            upgraded = "不可改裝"
            count = 1
        
        existing_idx = next((i for i, v in enumerate(self.data["vehicles"]) if v["name"].lower() == name.lower()), None)
        if existing_idx is not None:
            choice = messagebox.askyesnocancel("發現重複車輛", f"系統偵測到資產中已存在名為【{name}】的載具！\n\n• 按「是 (Yes)」：將該現有車輛的數量 +1\n• 按「否 (No)」：強制新增為另一筆獨立紀錄\n• 按「取消 (Cancel)」：放棄本次新增")
            if choice is None: return
            elif choice is True:
                if self.data["vehicles"][existing_idx].get("garage") == "帕格薩斯": 
                    return messagebox.showinfo("系統提示", "帕格薩斯載具無法疊加數量！")
                    
                self.data["vehicles"][existing_idx]["count"] = int(self.data["vehicles"][existing_idx].get("count", 1) or 1) + 1
                self.data["vehicles"][existing_idx]["updated_at"] = time.strftime('%Y-%m-%d %H:%M')
                
                if price > 0 and self.data["vehicles"][existing_idx].get("price", 0) == 0: 
                    self.data["vehicles"][existing_idx]["price"] = price 
                    
                self.sync_special_from_vehicles()
                save_data(self.all_data)
                self.refresh_vehicle_tables()
                self.refresh_special_table()
                self.refresh_garage_table()
                self.entry_name.delete(0, tk.END)
                self.combo_acquire.set("")
                self.entry_price.delete(0, tk.END)
                self.show_toast_progress("🚗 數量合併成功！")
                self.entry_name.focus()
                
                # 🎯 自動切換分頁並跳轉反白 (合併現有車輛時)
                target_vtype = self.data["vehicles"][existing_idx].get("v_type")
                target_tree = self.tree_non_personal if target_vtype in ["非個人載具", "帕格薩斯"] and hasattr(self, 'tree_non_personal') else self.tree_vehicles
                
                # 告訴系統畫面要切換到哪一個標籤頁
                if target_vtype in ["非個人載具", "帕格薩斯"]:
                    self.notebook.select(self.tab_non_personal)
                else:
                    self.notebook.select(self.tab_vehicles)

                target_tree.selection_remove(target_tree.selection())
                target_tree.selection_set(str(existing_idx))
                target_tree.see(str(existing_idx))
                return

        if garage != "未分類" and garage != "帕格薩斯":
            if not self.validate_tab1_vehicle_to_garage(name, garage): return
            lim = self.data["garage_limits"].get(garage, self.data.get("app_settings", {}).get("default_garage_limit", 10))
            if not disable_limits and self.count_cars_in_garage(garage) >= lim: 
                return messagebox.showerror("位置已滿", f"【{garage}】容量已滿！")

        self.data["vehicles"].append({
            "name": name, "garage": garage, "v_type": vtype, "acquire": self.combo_acquire.get(), 
            "price": price, "upgraded": upgraded, "count": count, "notes": "", "locked": False, 
            "pinned": False, "created_at": time.strftime('%Y-%m-%d %H:%M'), "updated_at": time.strftime('%Y-%m-%d %H:%M')
        })
        
        self.sync_special_from_vehicles()
        save_data(self.all_data)
        self.log_action(f"✅ 新增載具：【{name}】 (儲存至：{garage})")
        self.refresh_vehicle_tables()
        self.refresh_special_table()
        self.refresh_garage_table()
        self.refresh_statistics()
        self.entry_name.delete(0, tk.END)
        self.combo_acquire.set("")
        self.entry_price.delete(0, tk.END)
        self.show_toast_progress("🚗 登記成功！")
        self.entry_name.focus()
        
        # 🎯 自動切換分頁並跳轉反白 (新增全新車輛時)
        new_idx = str(len(self.data["vehicles"]) - 1)
        target_tree = self.tree_non_personal if vtype in ["非個人載具", "帕格薩斯"] and hasattr(self, 'tree_non_personal') else self.tree_vehicles
        
        # 告訴系統畫面要切換到哪一個標籤頁
        if vtype in ["非個人載具", "帕格薩斯"]:
            self.notebook.select(self.tab_non_personal)
        else:
            self.notebook.select(self.tab_vehicles)
            
        target_tree.selection_remove(target_tree.selection())
        target_tree.selection_set(new_idx)
        target_tree.see(new_idx)

    def delete_vehicle(self, event=None):
        if not self.data: return
        s = self.get_active_tree(event).selection()
        if not s: return
        for i in s:
            if self.data["vehicles"][int(i)].get("locked", False): return messagebox.showwarning("鎖定", "⚠️ 包含鎖定車輛！")
        if messagebox.askyesno("確認", f"刪除選定 【 {len(s)} 】 筆？"):
            for i in sorted([int(x) for x in s], reverse=True): del self.data["vehicles"][i]
            self.checked_indices.clear(); self.update_checked_button_text(); self.sync_special_from_vehicles(); save_data(self.all_data); self.apply_filters(); self.refresh_special_table(); self.refresh_garage_table(); self.refresh_statistics(); self.set_status(f"❌ 成功刪除 {len(s)} 筆。", "#FF9800")

    def toggle_pin_vehicle(self, event=None):
        if not self.data: return
        t = self.get_active_tree(event); s = t.selection()
        if not s: return
        ns = not self.data["vehicles"][int(s[0])].get("pinned", False)
        for i in s: self.data["vehicles"][int(i)]["pinned"] = ns
        save_data(self.all_data); self.apply_filters()

    def toggle_lock_vehicle(self, event=None):
        if not self.data: return
        t = self.get_active_tree(event); s = t.selection()
        if not s: return
        ns = not self.data["vehicles"][int(s[0])].get("locked", False)
        for i in s: self.data["vehicles"][int(i)]["locked"] = ns
        save_data(self.all_data); self.apply_filters()

    def apply_filters(self, event=None):
        if not self.data: return
        kw = self.entry_search.get().lower(); sg = self.combo_garage_filter.get()
        f = [(i, c) for i, c in enumerate(self.data["vehicles"]) if (kw in c["name"].lower() or kw in c["garage"].lower()) and (sg in ["全部", ""] or c["garage"] == sg)]
        self.refresh_vehicle_tables(search_results=f)

    def reset_filters(self):
        if not self.data: return
        self.entry_search.delete(0, tk.END); self.combo_garage_filter.set("全部"); self.checked_indices.clear(); self.update_checked_button_text(); self.refresh_vehicle_tables()

    def show_vehicle_context_menu(self, event):
        if not self.data: return
        t = self.get_active_tree(event); i = t.identify_row(event.y)
        if i: 
            if i not in t.selection(): t.selection_set(i)
            self.vehicle_popup_menu.delete(0, tk.END); self.vehicle_popup_menu.add_command(label="📝 編輯資產", command=self.open_edit_window); self.vehicle_popup_menu.add_separator(); self.vehicle_popup_menu.add_command(label="📌 置頂/取消置頂", command=self.toggle_pin_vehicle); self.vehicle_popup_menu.add_command(label="🔒 檔案鎖定/解鎖", command=self.toggle_lock_vehicle); self.vehicle_popup_menu.add_separator(); self.vehicle_popup_menu.add_command(label="❌ 刪除資產", command=self.delete_vehicle); self.vehicle_popup_menu.post(event.x_root, event.y_root)

    def open_batch_import_window(self):
        if self.check_win('import_window'): return
        if not getattr(self, 'data', None): return messagebox.showwarning("提示", "請先登入帳號！")
        
        self.import_window = win = tk.Toplevel(self.root)
        win.title("📦 批量新增載具")
        try: self.center_toplevel_window(win, 550, 480)
        except: win.geometry("550x480")
        win.configure(bg=COLOR_CARD_BG)
        
        tk.Label(win, text="📦 批量新增載具資料", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#3498db").pack(pady=(20, 5))
        tk.Label(win, text="請貼上車輛資料（一行一筆）。\n格式：載具名稱, 車庫位置 (若無車庫請留空，預設未分類)", font=("Microsoft JhengHei", 10), bg=COLOR_CARD_BG, fg="#a8e6cf").pack(pady=(0, 10))
        
        tf = tk.Frame(win, bg=COLOR_CARD_BG)
        tf.pack(fill="both", expand=True, padx=35, pady=5)
        sb = ttk.Scrollbar(tf)
        sb.pack(side="right", fill="y")
        ta = tk.Text(tf, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", relief="solid", yscrollcommand=sb.set, height=12)
        ta.pack(side="left", fill="both", expand=True)
        sb.config(command=ta.yview)
        apply_focus_highlight(ta)
        
        def proc():
            c = ta.get("1.0", tk.END).strip(); a = 0
            if not c: return messagebox.showwarning("提示", "請輸入資料！", parent=win)
            for l in c.split('\n'):
                if not l.strip(): continue
                p = l.split(','); n = p[0].strip(); g = p[1].strip() if len(p) > 1 else "未分類"
                if not g: g = "未分類"
                self.data["vehicles"].append({
                    "name": n, "garage": g, "v_type": "", "acquire": "", "price": 0, 
                    "upgraded": "", "count": 1, "notes": "", "locked": False, "pinned": False, 
                    "created_at": time.strftime('%Y-%m-%d %H:%M'), "updated_at": time.strftime('%Y-%m-%d %H:%M')
                })
                a += 1
            self.sync_special_from_vehicles()
            save_data(self.all_data)
            self.refresh_vehicle_tables()
            self.refresh_garage_table()
            self.refresh_statistics()
            self.show_toast_progress(f"✅ 成功批量匯入 {a} 筆載具")
            win.destroy()
            
        bf = tk.Frame(win, bg=COLOR_CARD_BG)
        bf.pack(fill="x", padx=35, pady=20)
        ttk.Button(bf, text="✔️ 開始匯入", command=proc, style="Success.TButton").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=4)
        ttk.Button(bf, text="❌ 取消", command=win.destroy, style="Secondary.TButton").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4)

    def on_vehicle_double_click(self, event):
        if not event.widget.identify_row(event.y): return
        self.open_edit_window(event)

    def open_edit_window(self, event=None, pre_selected=None):
        if self.check_win('edit_window'): return
        if not self.data: return
        sel = pre_selected if pre_selected is not None else self.get_active_tree(event).selection()
        if not sel: return
        if event and not self.get_active_tree(event).identify_row(event.y): return

        for i in sel:
            if self.data["vehicles"][int(i)].get("locked", False): return messagebox.showwarning("鎖定", "⚠️ 資料已鎖定！")
        
        cl = ["未分類", "帕格薩斯"] + [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]] + [s["name"] for s in self.data.get("special_vehicles", []) if s.get("can_store", False)]
        
        if len(sel) == 1:
            idx = int(sel[0]); c = self.data["vehicles"][idx]
            self.edit_window = win = tk.Toplevel(self.root); win.title("編輯"); self.center_toplevel_window(win, 350, 580) 
            def clbl(t): tk.Label(win, text=t, bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(6 if t!="載具名稱:" else 12,2))
            clbl("載具名稱:"); en = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=22); en.insert(0, c['name']); en.pack(); en.focus()
            cg = ttk.Combobox(win, state="readonly", values=cl, font=FONT_NORMAL); cv = ttk.Combobox(win, state="readonly", values=V_TYPE_OPTIONS, font=FONT_NORMAL); ca = ttk.Combobox(win, state="readonly", values=self.data.get("acquire_options", ACQUIRE_OPTIONS), font=FONT_NORMAL); cu = ttk.Combobox(win, state="readonly", values=["未改滿", "已改滿", "不可改裝"], font=FONT_NORMAL); ep = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=22); ec = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=22); eo = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=22)
            clbl("存放位置:"); cg.set(c.get('garage', '未分類')); cg.pack()
            clbl("載具類型:"); cv.set(c.get('v_type', '')); cv.pack()
            clbl("取得方式:"); ca.set(c.get('acquire', '')); ca.pack()
            clbl("價格:"); ep.insert(0, str(c.get('price', 0))); ep.pack()
            clbl("改裝:"); cu.set(c.get('upgraded', '')); cu.pack()
            clbl("數量:"); ec.insert(0, str(c.get('count', 1))); ec.pack()
            clbl("備註:"); eo.insert(0, c.get('notes', '')); eo.pack()
            def sv_sg(e=None):
                try: p = int(ep.get() or 0)
                except: p = 0
                try: ct = int(ec.get() or 1)
                except: ct = 1
                c.update({'name': en.get(), 'garage': cg.get(), 'v_type': cv.get(), 'acquire': ca.get(), 'price': p, 'upgraded': cu.get(), 'count': ct, 'notes': eo.get(), 'updated_at': time.strftime('%Y-%m-%d %H:%M')}); self.sync_special_from_vehicles(); save_data(self.all_data)
                if pre_selected is not None: self.checked_indices.clear(); self.update_checked_button_text()
                self.refresh_vehicle_tables(); self.refresh_garage_table(); self.refresh_special_table(); self.refresh_statistics(); win.destroy(); self.show_toast_progress("✅ 修改成功！")
            def del_act():
                if messagebox.askyesno("刪除", f"刪除選定的 1 筆？", parent=win):
                    del self.data["vehicles"][idx]; self.checked_indices.discard(idx); self.update_checked_button_text(); self.sync_special_from_vehicles(); save_data(self.all_data); self.refresh_vehicle_tables(); self.refresh_garage_table(); self.refresh_special_table(); win.destroy()
            bf = tk.Frame(win, bg=COLOR_MAIN_BG); bf.pack(fill="x", padx=35, pady=15)
            ttk.Button(bf, text="儲存", command=sv_sg, style="Success.TButton").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=4); ttk.Button(bf, text="❌ 刪除", command=del_act, style="Danger.TButton").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4); win.bind("<Return>", sv_sg)
        else:
            self.edit_window = win = tk.Toplevel(self.root); win.title("批量修改"); self.center_toplevel_window(win, 380, 620) 
            tk.Label(win, text=f"👁️ 勾選 {len(sel)} 筆：", fg="#e91e63", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG).pack(pady=(10, 5))
            def clbl(t): tk.Label(win, text=t, bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack()
            clbl("1. 位置:"); cbg = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]"] + cl); cbg.set("[不修改]"); cbg.pack(pady=3)
            clbl("2. 類型:"); cbv = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]"] + V_TYPE_OPTIONS); cbv.set("[不修改]"); cbv.pack(pady=3)
            clbl("3. 改裝:"); cbu = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["[不修改]", "未改滿", "已改滿", "不可改裝"]); cbu.set("[不修改]"); cbu.pack(pady=3)
            def sv_b():
                ct = time.strftime('%Y-%m-%d %H:%M')
                for i in sel:
                    ix = int(i)
                    if cbg.get() != "[不修改]": self.data["vehicles"][ix]['garage'] = cbg.get()
                    if cbv.get() != "[不修改]": self.data["vehicles"][ix]['v_type'] = cbv.get()
                    if cbu.get() != "[不修改]": self.data["vehicles"][ix]['upgraded'] = cbu.get()
                    self.data["vehicles"][ix]['updated_at'] = ct
                self.sync_special_from_vehicles(); save_data(self.all_data)
                if pre_selected is not None: self.checked_indices.clear(); self.update_checked_button_text()
                self.refresh_vehicle_tables(); self.refresh_garage_table(); self.refresh_special_table(); win.destroy(); self.show_toast_progress("✅ 批量完畢")
            ttk.Button(win, text="執行", command=sv_b, style="Primary.TButton").pack(fill="x", padx=35, pady=25, ipady=4); win.bind("<Return>", lambda e: sv_b())

    def setup_special_tab(self):
        inf = tk.LabelFrame(self.tab_special, text=" 🚁 登記大型特種 ", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="#e91e63", padx=12, pady=12, bd=2); inf.pack(fill="x", padx=15, pady=10)
        tk.Label(inf, text="名稱:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=0, column=0, pady=5, padx=5, sticky="e")
        self.combo_spec_name = ttk.Combobox(inf, state="normal", font=FONT_NORMAL, values=list(SUB_CARRIER_RULES.keys()) + ["機動作戰中心", "復仇者"]); self.combo_spec_name.grid(row=0, column=1, pady=5, padx=5, sticky="we"); self.combo_spec_name.bind("<KeyRelease>", self.on_main_spec_carrier_changed); self.combo_spec_name.bind("<<ComboboxSelected>>", self.on_main_spec_carrier_changed)
        tk.Label(inf, text="位置:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=0, column=2, pady=5, padx=5, sticky="e")
        self.combo_spec_location = ttk.Combobox(inf, state="readonly", font=FONT_NORMAL); self.combo_spec_location.grid(row=0, column=3, pady=5, padx=5, sticky="we")
        ttk.Button(inf, text="➕ 建立", command=self.add_special, style="Pink.TButton", padding=(10, 4)).grid(row=0, column=4, rowspan=2, padx=15, pady=5, sticky="ns")
        self.var_can_store = tk.BooleanVar(value=False); self.chk_can_store = tk.Checkbutton(inf, text="啟用車庫", variable=self.var_can_store, bg=COLOR_CARD_BG, fg="white", selectcolor="#757575", font=FONT_BOLD); self.chk_can_store.grid(row=1, column=0, columnspan=2, pady=5, padx=5, sticky="w")
        tk.Label(inf, text="專屬車輛:", bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL).grid(row=1, column=2, pady=5, padx=5, sticky="e"); self.combo_inner_car = ttk.Combobox(inf, state="disabled", font=FONT_NORMAL, values=[""]); self.combo_inner_car.grid(row=1, column=3, pady=5, padx=5, sticky="we")
        tf = tk.Frame(self.tab_special, bg=COLOR_MAIN_BG); tf.pack(fill="both", expand=True, padx=15, pady=10)
        self.tree_special = ttk.Treeview(tf, columns=("name", "location", "inner"), show="headings", selectmode="extended")
        for c, t in {"name": "名稱", "location": "位置", "inner": "內部"}.items(): self.tree_special.heading(c, text=t)
        self.tree_special.column("name", width=200, stretch=True); self.tree_special.column("location", width=200, stretch=True); self.tree_special.column("inner", width=300, stretch=True); self.tree_special.pack(side="left", fill="both", expand=True)
        self.tree_special.bind("<Double-1>", self.on_special_double_click); self.tree_special.bind("<Delete>", self.delete_special)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree_special.yview); self.tree_special.configure(yscrollcommand=sb.set); sb.pack(side="right", fill="y")
        self.special_popup_menu = tk.Menu(self.root, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL); self.tree_special.bind("<Button-3>", self.show_special_context_menu)

    def on_special_double_click(self, event):
        if not event.widget.identify_row(event.y): return
        self.open_special_edit_window(event)

    def on_main_spec_carrier_changed(self, event=None):
        c = self.combo_spec_name.get().strip()
        if c in SUB_CARRIER_RULES: self.var_can_store.set(True); self.chk_can_store.config(state="disabled"); self.combo_inner_car.config(state="readonly"); self.combo_inner_car["values"] = [""] + SUB_CARRIER_RULES[c] 
        else: self.chk_can_store.config(state="normal"); self.combo_inner_car.set(""); self.combo_inner_car.config(state="disabled") 

    def add_special(self):
        if not self.data: return
        n, l, i = self.combo_spec_name.get().strip(), self.combo_spec_location.get().strip() or "未分類", self.combo_inner_car.get().strip()
        if not n: return
        self.data["special_vehicles"].append({"name": n, "location": l, "inner_vehicle": i if i != "無" else "", "can_store": self.var_can_store.get(), "locked": False, "pinned": False, "updated_at": time.strftime("%Y-%m-%d %H:%M")}) 
        self.sync_vehicles_from_special(); save_data(self.all_data); self.refresh_special_table(); self.update_garage_comboboxes(); self.refresh_vehicle_tables(); self.combo_spec_name.set(""); self.combo_inner_car.set(""); self.var_can_store.set(False); self.on_main_spec_carrier_changed(); self.combo_spec_location.set("未分類"); self.show_toast_progress("🚁 建立成功！")

    def refresh_special_table(self):
        for i in self.tree_special.get_children(): self.tree_special.delete(i)
        if not self.data: return
        
        # 🌟 讓特殊載具也支援置頂排序
        ds = list(enumerate(self.data.get("special_vehicles", [])))
        pi = [(i, m) for i, m in ds if m.get("pinned", False)]
        ni = [(i, m) for i, m in ds if not m.get("pinned", False)]
        
        for i, m in pi + ni:
            dn = ("🔒 " if m.get("locked") else "") + ("📌 " if m.get("pinned") else "") + m["name"]
            self.tree_special.insert("", "end", iid=str(i), values=(dn, m.get("location", "未分類"), m.get("inner_vehicle", "") or ""))

    def toggle_pin_special(self):
        if not self.data or not self.tree_special.selection(): return
        ns = not self.data["special_vehicles"][int(self.tree_special.selection()[0])].get("pinned", False)
        for i in self.tree_special.selection(): self.data["special_vehicles"][int(i)]["pinned"] = ns
        save_data(self.all_data); self.refresh_special_table()

    def toggle_lock_special(self):
        if not self.data or not self.tree_special.selection(): return
        ns = not self.data["special_vehicles"][int(self.tree_special.selection()[0])].get("locked", False)
        for i in self.tree_special.selection(): self.data["special_vehicles"][int(i)]["locked"] = ns
        save_data(self.all_data); self.refresh_special_table()

    def show_special_context_menu(self, event):
        i = self.tree_special.identify_row(event.y)
        if i:
            if i not in self.tree_special.selection(): self.tree_special.selection_set(i)
            self.special_popup_menu.delete(0, tk.END); self.special_popup_menu.add_command(label="📝 編輯", command=self.open_special_edit_window); self.special_popup_menu.add_separator(); self.special_popup_menu.add_command(label="📌 置頂/取消", command=self.toggle_pin_special); self.special_popup_menu.add_command(label="🔒 鎖定/解鎖", command=self.toggle_lock_special); self.special_popup_menu.add_separator(); self.special_popup_menu.add_command(label="❌ 報廢", command=self.delete_special); self.special_popup_menu.post(event.x_root, event.y_root)

    def delete_special(self, event=None):
        s = self.tree_special.selection()
        if not s: return
        if messagebox.askyesno("刪除", "確定報廢？"):
            for i in sorted([int(x) for x in s], reverse=True): 
                on = self.data["special_vehicles"][i]["name"]; del self.data["special_vehicles"][i]
                if on in self.data["garage_limits"]: del self.data["garage_limits"][on] 
                for v in self.data["vehicles"]:
                    if v.get("garage") == on: v["garage"] = "未分類"
            save_data(self.all_data); self.refresh_special_table(); self.update_garage_comboboxes(); self.apply_filters()

    def open_special_edit_window(self, event=None):
        if self.check_win('special_edit_window'): return
        if event and not self.tree_special.identify_row(event.y): return
        s = self.tree_special.selection()
        if not s or len(s) > 1: return 
        i = int(s[0]); sv = self.data["special_vehicles"][i]
        self.special_edit_window = win = tk.Toplevel(self.root); win.title("修改特種"); self.center_toplevel_window(win, 350, 420) 
        tk.Label(win, text="名稱:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(12,2)); cn = ttk.Combobox(win, state="normal", font=FONT_NORMAL, values=list(SUB_CARRIER_RULES.keys()) + ["機動作戰中心", "復仇者"]); cn.set(sv["name"]); cn.pack()
        tk.Label(win, text="位置:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(5,2)); csl = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=["未分類"] + [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]); csl.set(sv.get("location", "未分類")); csl.pack()
        ev = tk.BooleanVar(value=sv.get("can_store", False)); tk.Checkbutton(win, text="設為車庫", variable=ev, bg=COLOR_MAIN_BG, fg="white", selectcolor="#757575", font=FONT_BOLD).pack(pady=4)
        def save(e=None):
            nn = cn.get().strip()
            if nn != sv["name"]:
                for v in self.data["vehicles"]:
                    if v.get("garage") == sv["name"]: v["garage"] = nn
            self.data["special_vehicles"][i].update({"name": nn, "location": csl.get().strip() or "未分類", "can_store": ev.get(), "updated_at": time.strftime("%Y-%m-%d %H:%M")}); self.sync_vehicles_from_special(); save_data(self.all_data); self.refresh_vehicle_tables(); self.update_garage_comboboxes(); self.refresh_special_table(); win.destroy()
        ttk.Button(win, text="儲存", command=save, style="Success.TButton").pack(fill="x", padx=35, pady=15, ipady=4); win.bind("<Return>", save)

    def setup_garages_tab(self):
        self.expanded_bases = set()  
        self.garage_paned = tk.PanedWindow(self.tab_garages, orient="horizontal", bg=COLOR_MAIN_BG, bd=0, sashwidth=4); self.garage_paned.pack(fill="both", expand=True, padx=15, pady=10)
        self.gta_menu_frame = tk.Frame(self.garage_paned, bg="#000000", width=380); self.gta_menu_frame.pack_propagate(False); self.garage_paned.add(self.gta_menu_frame, minsize=380)
        h = tk.Frame(self.gta_menu_frame, bg="#000000", pady=12, padx=15); h.pack(fill="x")
        tk.Label(h, text="選擇車庫", bg="#000000", fg="white", font=("Microsoft JhengHei", 16, "bold")).pack(side="left"); self.lbl_menu_count = tk.Label(h, text="1 / 1", bg="#000000", fg="white", font=("Microsoft JhengHei", 14, "bold")); self.lbl_menu_count.pack(side="right")
        self.menu_listbox = tk.Listbox(self.gta_menu_frame, bg="#1a1a1a", fg="white", selectmode="extended", selectbackground="#ffffff", selectforeground="#000000", font=("Microsoft JhengHei", 13, "bold"), borderwidth=0, highlightthickness=0, activestyle='none'); self.menu_listbox.pack(fill="both", expand=True, pady=(0, 2))
        self.menu_listbox.bind("<<ListboxSelect>>", self.on_garage_menu_select); self.menu_listbox.bind("<Double-1>", self.on_garage_menu_double_click); self.menu_listbox.bind("<Return>", self.on_garage_menu_double_click); self.menu_listbox.bind("<Button-3>", self.show_garage_menu_context)
        ft = tk.Frame(self.gta_menu_frame, bg="#000000", pady=8); ft.pack(fill="x", side="bottom")
        bf = tk.Frame(ft, bg="#000000"); bf.pack(fill="x")
        ttk.Button(bf, text="⬆️ 上移", command=self.move_left_menu_up, style="Dark.TButton").pack(side="left", fill="x", expand=True, padx=(15, 5)); ttk.Button(bf, text="⬇️ 下移", command=self.move_left_menu_down, style="Dark.TButton").pack(side="right", fill="x", expand=True, padx=(5, 15))
        fd = tk.Frame(self.gta_menu_frame, bg="#111111", pady=8, padx=15); fd.pack(fill="x", side="bottom"); tk.Label(fd, text="點擊查看內容，【右鍵】可管理/刪除，支援 Ctrl 多選。", bg="#111111", fg="white", font=FONT_NORMAL).pack(side="left")
        self.garage_details_frame = tk.Frame(self.garage_paned, bg=COLOR_MAIN_BG); self.garage_paned.add(self.garage_details_frame)

    def refresh_garage_table(self):
        if not hasattr(self, 'menu_listbox'): return
        os = self.menu_listbox.curselection(); si = os[0] if os else 0
        self.menu_listbox.delete(0, tk.END); self.menu_items_data = []
        if not self.data: return
        ag = [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]
        pass # V1.6.3 拔除新增按鈕，根治陣列錯位
        grps = defaultdict(list); obs = []
        for g in ag:
            bn = g.split(" - ", 1)[0]
            grps[bn].append(g)
            if bn not in obs: obs.append(bn)
        for b in obs:
            gl = grps[b]
            if len(gl) == 1 and gl[0] == b: self.menu_items_data.append({"type": "single", "name": b, "display": b}); self.menu_listbox.insert(tk.END, f"  {b}")
            else:
                ie = b in self.expanded_bases; ic = "▼" if ie else "▶"; dt = f"{ic} {b}"
                self.menu_items_data.append({"type": "base", "name": b, "display": dt}); self.menu_listbox.insert(tk.END, f"  {dt}")
                if ie:
                    for g in gl:
                        sn = g.split(" - ", 1)[1] if " - " in g else "主物業樓層"; ds = f"      {sn}"
                        self.menu_items_data.append({"type": "sub", "name": g, "base": b, "display": ds}); self.menu_listbox.insert(tk.END, ds)
        ti = len(self.menu_items_data)
        if si >= ti: si = max(0, ti - 1)
        if ti > 0:
            if getattr(self, "skip_refresh_select", False): return
            self.menu_listbox.selection_clear(0, tk.END); self.menu_listbox.selection_set(si); self.menu_listbox.see(si); self.lbl_menu_count.config(text=f"{si + 1} / {ti}"); self.render_garage_details(self.menu_items_data[si])

    def on_garage_menu_select(self, event=None):
        s = self.menu_listbox.curselection()
        if not s: return
        if len(s) > 1: self.lbl_menu_count.config(text=f"多選 ({len(s)})"); self.render_multi_garage_details(s)
        else: i = s[0]; self.lbl_menu_count.config(text=f"{i + 1} / {len(self.menu_items_data)}"); self.render_garage_details(self.menu_items_data[i])

    def on_garage_menu_double_click(self, event=None):
        if not self.menu_listbox.nearest(event.y) >= 0: return
        s = self.menu_listbox.curselection()
        if not s or len(s) > 1: return
        i = self.menu_items_data[s[0]]
        if i["type"] == "base":
            bn = i["name"]
            if bn in self.expanded_bases: self.expanded_bases.remove(bn)
            else: self.expanded_bases.add(bn)
            self.refresh_garage_table()
            for ix, d in enumerate(self.menu_items_data):
                if d["name"] == bn and d["type"] == "base": self.menu_listbox.selection_set(ix); self.menu_listbox.see(ix); self.render_garage_details(d); break

    def render_multi_garage_details(self, sel_indices):
        for w in self.garage_details_frame.winfo_children(): w.destroy()
        it = [self.menu_items_data[i] for i in sel_indices if self.menu_items_data[i]["type"] != "add"]
        if not it: return
        p = tk.Frame(self.garage_details_frame, bg=COLOR_MAIN_BG, padx=30, pady=20); p.pack(fill="both", expand=True); tk.Label(p, text="📦 批量管理", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#9b59b6").pack(anchor="w", pady=(0, 20)); h = tk.Frame(p, bg=COLOR_CARD_BG, pady=20, padx=25, bd=1, relief="solid"); h.pack(fill="x", pady=10); tk.Label(h, text=f"已選取 {len(it)} 個車庫", font=("Microsoft JhengHei", 18, "bold"), bg=COLOR_CARD_BG, fg="white").pack(side="left"); lf = tk.Frame(p, bg=COLOR_MAIN_BG); lf.pack(fill="both", expand=True, pady=10); sb = ttk.Scrollbar(lf); sb.pack(side="right", fill="y"); dl = tk.Listbox(lf, font=("Microsoft JhengHei", 12), bg="#1e1e1e", fg="white", yscrollcommand=sb.set, relief="solid", bd=1); dl.pack(side="left", fill="both", expand=True); sb.config(command=dl.yview)
        for x in it: dl.insert(tk.END, f" ▪️ {x['display'].strip().replace('▼ ', '').replace('▶ ', '')}")
        bf = tk.Frame(p, bg=COLOR_MAIN_BG); bf.pack(fill="x", pady=(15, 0)); ttk.Button(bf, text="❌ 批量刪除", command=lambda: self.delete_multiple_garages_from_menu(it), style="Danger.TButton").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4)

    def render_garage_details(self, idt):
        for w in self.garage_details_frame.winfo_children(): w.destroy()
        if idt["type"] == "add":
            p = tk.Frame(self.garage_details_frame, bg=COLOR_MAIN_BG, padx=30, pady=20); p.pack(fill="both", expand=True); tk.Label(p, text="🏠 購買新物業", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#4CAF50").pack(anchor="w", pady=(0, 20)); ff = tk.Frame(p, bg=COLOR_CARD_BG, padx=20, pady=20, bd=1, relief="solid"); ff.pack(fill="x", pady=10); tk.Label(ff, text="主物業名稱:", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="white").pack(anchor="w", pady=5); self.eng = tk.Entry(ff, width=28, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid"); self.eng.pack(anchor="w", pady=5); apply_focus_highlight(self.eng); tk.Label(ff, text="附加額外樓層數:", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="white").pack(anchor="w", pady=(15, 5)); fr = tk.Frame(ff, bg=COLOR_CARD_BG); fr.pack(anchor="w", pady=5); self.engf = tk.Entry(fr, width=8, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", justify="center"); self.engf.insert(0, "1"); self.engf.pack(side="left"); apply_focus_highlight(self.engf); self.cft = ttk.Combobox(fr, width=18, font=FONT_NORMAL, state="readonly", values=["地上 (車庫1...)", "地下 (B1...)"]); self.cft.set("地上 (車庫1...)"); self.cft.pack(side="left", padx=10); self.eng.bind("<Return>", lambda e: self.engf.focus()); self.engf.bind("<Return>", lambda e: self.add_garage_simple()); ttk.Button(ff, text="➕ 置產", command=self.add_garage_simple, style="Success.TButton").pack(anchor="w", pady=20, ipadx=10); ttk.Separator(p, orient="horizontal").pack(fill="x", pady=25); tk.Label(p, text="⚙️ 批量管理", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#F39C12").pack(anchor="w", pady=10); tfr = tk.Frame(p, bg=COLOR_MAIN_BG); tfr.pack(fill="x", pady=5); ttk.Button(tfr, text="📦 批量新增車庫", command=self.open_batch_garage_window, style="Purple.TButton").pack(side="left")
        elif idt["type"] == "base":
            bn = idt["name"]; gl = [g for g in self.data["garages"] if g == bn or g.startswith(bn + " - ")]; tl = sum(self.data["garage_limits"].get(g, 10) for g in gl); tu = sum(self.count_cars_in_garage(g) for g in gl); dl = self.data.get("app_settings", {}).get("disable_all_limits", False); ld = "∞" if dl else tl
            p = tk.Frame(self.garage_details_frame, bg=COLOR_MAIN_BG, padx=30, pady=20); p.pack(fill="both", expand=True); tk.Label(p, text="🏢 物業總覽", font=FONT_LARGE_BOLD, bg=COLOR_MAIN_BG, fg="#F39C12").pack(anchor="w", pady=(0, 10)); h = tk.Frame(p, bg=COLOR_CARD_BG, pady=25, padx=25, bd=1, relief="solid"); h.pack(fill="x", pady=10); tk.Label(h, text=f"{bn}", font=("Microsoft JhengHei", 20, "bold"), bg=COLOR_CARD_BG, fg="white").pack(side="left"); tk.Label(h, text=f"{tu} / {ld} 輛", font=("Consolas", 20, "bold"), bg=COLOR_CARD_BG, fg="#F39C12").pack(side="right"); bf = tk.Frame(p, bg=COLOR_MAIN_BG); bf.pack(fill="x", pady=25); ttk.Button(bf, text="➕ 擴建附屬", command=lambda: self.add_sub_floor(bn), style="Primary.TButton").pack(side="left", padx=(0, 10), ipady=4); ttk.Button(bf, text="📝 重新命名整棟", command=lambda: self.rename_entire_property(bn), style="Warning.TButton").pack(side="left", padx=10, ipady=4); ttk.Button(bf, text="❌ 變賣整棟", command=lambda: self.delete_entire_property(bn), style="Danger.TButton").pack(side="right", ipady=4)
        else:
            gn = idt["name"]; l = self.data["garage_limits"].get(gn, 10); u = self.count_cars_in_garage(gn); dl = self.data.get("app_settings", {}).get("disable_all_limits", False); ld = "∞" if dl else l
            p = tk.Frame(self.garage_details_frame, bg=COLOR_MAIN_BG, padx=20, pady=20); p.pack(fill="both", expand=True); h = tk.Frame(p, bg=COLOR_CARD_BG, pady=20, padx=25, bd=1, relief="solid"); h.pack(fill="x", pady=(0, 15)); tk.Label(h, text=f"📍 {gn}", font=("Microsoft JhengHei", 18, "bold"), bg=COLOR_CARD_BG, fg="white").pack(side="left"); count_fg = "#ff1744" if (not dl and u >= l) else "#3498db"; tk.Label(h, text=f"{u} / {ld} 輛", font=("Consolas", 18, "bold"), bg=COLOR_CARD_BG, fg=count_fg).pack(side="right"); lf = tk.Frame(p, bg=COLOR_MAIN_BG); lf.pack(fill="both", expand=True, pady=5); tk.Label(lf, text="💡 提示：按住 Ctrl 或 Shift 鍵多選，對載具點擊「右鍵」可移動至其他車庫", font=("Microsoft JhengHei", 10), bg=COLOR_MAIN_BG, fg="#a8e6cf").pack(anchor="w", pady=(0, 5)); sb = ttk.Scrollbar(lf); sb.pack(side="right", fill="y"); clb = tk.Listbox(lf, font=("Microsoft JhengHei", 12), bg="#1e1e1e", fg="white", selectmode="extended", selectbackground="#3498db", yscrollcommand=sb.set, relief="solid", bd=1); clb.pack(side="left", fill="both", expand=True); sb.config(command=clb.yview)
            cig = [(ix, c) for ix, c in enumerate(self.data.get("vehicles", [])) if c.get("garage") == gn]; self.current_garage_car_indices = []
            if not cig: clb.insert(tk.END, "  (無載具)"); clb.config(fg="#888888")
            else:
                for ix, c in cig: clb.insert(tk.END, f"  🚗 {c['name']}" + (f"  [{c.get('v_type', '')}]" if c.get('v_type') else "")); self.current_garage_car_indices.append(ix)
            def scm(e):
                if not cig: return
                i = clb.nearest(e.y)
                if i >= 0:
                    if i not in clb.curselection(): clb.selection_clear(0, tk.END); clb.selection_set(i); clb.activate(i)
                    s = clb.curselection()
                    if s:
                        if not hasattr(self, 'car_popup_menu'): self.car_popup_menu = tk.Menu(self.root, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
                        self.car_popup_menu.delete(0, tk.END); self.car_popup_menu.add_command(label=f"🚚 移動 {len(s)} 輛載具...", command=lambda: self.open_move_vehicle_window(gn, clb)); self.car_popup_menu.post(e.x_root, e.y_root)
            clb.bind("<Button-3>", scm); bf = tk.Frame(p, bg=COLOR_MAIN_BG); bf.pack(fill="x", pady=(15, 0)); ttk.Button(bf, text="📝 修改屬性", command=lambda: self.open_garage_edit_window_by_name(gn), style="Secondary.TButton").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=4); ttk.Button(bf, text="❌ 變賣", command=lambda: self.delete_garage_by_name(gn), style="Danger.TButton").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4)

    def move_left_menu_up(self):
        s = self.menu_listbox.curselection()
        if not s or len(s) > 1: return messagebox.showwarning("提示", "請單選！")
        i = s[0]; it = self.menu_items_data[i]
        if it["type"] == "add": return
        ag = [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]
        if it["type"] == "base":
            bn = it["name"]; gg = [g for g in ag if g.split(" - ", 1)[0] == bn]; fi = ag.index(gg[0])
            if fi == 0: return 
            pb = ag[fi - 1].split(" - ", 1)[0]; pg = [g for g in ag if g.split(" - ", 1)[0] == pb]
            for g in gg: ag.remove(g)
            idx = ag.index(pg[0])
            for g in reversed(gg): ag.insert(idx, g)
        elif it["type"] in ["single", "sub"]:
            gn = it["name"]; bn = it.get("base", gn); ii = ag.index(gn)
            if ii == 0: return
            if it["type"] == "sub":
                if ag[ii - 1].split(" - ", 1)[0] != bn: return 
            ag.remove(gn); ag.insert(ii - 1, gn)
        self.data["garages"] = ["未分類", "帕格薩斯"] + ag; save_data(self.all_data); self.skip_refresh_select = True; self.refresh_garage_table(); self.skip_refresh_select = False; self.menu_listbox.selection_clear(0, tk.END)
        for ix, d in enumerate(self.menu_items_data):
            if d.get("name") == it["name"] and d.get("type") == it["type"]: self.menu_listbox.selection_set(ix); self.menu_listbox.see(ix); self.on_garage_menu_select(); break
        self.menu_listbox.focus_set()

    def move_left_menu_down(self):
        s = self.menu_listbox.curselection()
        if not s or len(s) > 1: return messagebox.showwarning("提示", "請單選！")
        i = s[0]; it = self.menu_items_data[i]
        if it["type"] == "add": return
        ag = [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]]
        if it["type"] == "base":
            bn = it["name"]; gg = [g for g in ag if g.split(" - ", 1)[0] == bn]; li = ag.index(gg[-1])
            if li == len(ag) - 1: return 
            nb = ag[li + 1].split(" - ", 1)[0]; ng = [g for g in ag if g.split(" - ", 1)[0] == nb]
            for g in gg: ag.remove(g)
            idx = ag.index(ng[-1]) + 1
            for g in reversed(gg): ag.insert(idx, g)
        elif it["type"] in ["single", "sub"]:
            gn = it["name"]; bn = it.get("base", gn); ii = ag.index(gn)
            if ii == len(ag) - 1: return
            if it["type"] == "sub":
                if ag[ii + 1].split(" - ", 1)[0] != bn: return 
            ag.remove(gn); ag.insert(ii + 1, gn)
        self.data["garages"] = ["未分類", "帕格薩斯"] + ag; save_data(self.all_data); self.skip_refresh_select = True; self.refresh_garage_table(); self.skip_refresh_select = False; self.menu_listbox.selection_clear(0, tk.END)
        for ix, d in enumerate(self.menu_items_data):
            if d.get("name") == it["name"] and d.get("type") == it["type"]: self.menu_listbox.selection_set(ix); self.menu_listbox.see(ix); self.on_garage_menu_select(); break
        self.menu_listbox.focus_set()

    def show_garage_menu_context(self, event):
        if not self.data: return
        i = self.menu_listbox.nearest(event.y)
        if i < 0 or i >= self.menu_listbox.size(): return
        if i not in self.menu_listbox.curselection(): self.menu_listbox.selection_clear(0, tk.END); self.menu_listbox.selection_set(i); self.menu_listbox.activate(i); self.on_garage_menu_select()
        s = self.menu_listbox.curselection(); ita = [self.menu_items_data[x] for x in s if x < len(self.menu_items_data) and self.menu_items_data[x]["type"] != "add"]
        if not ita: return
        if not hasattr(self, 'left_menu_popup'): self.left_menu_popup = tk.Menu(self.root, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        self.left_menu_popup.delete(0, tk.END)
        if len(ita) == 1:
            it = ita[0]; gn = it["name"]
            if it["type"] == "base":
                self.left_menu_popup.add_command(label=f"➕ 擴建樓層 ({gn})", command=lambda: self.add_sub_floor(gn)); self.left_menu_popup.add_command(label=f"📝 重新命名", command=lambda: self.rename_entire_property(gn)); self.left_menu_popup.add_separator(); self.left_menu_popup.add_command(label=f"❌ 移除", command=lambda: self.delete_entire_property(gn))
            elif it["type"] in ["single", "sub"]:
                self.left_menu_popup.add_command(label=f"📝 修改屬性", command=lambda: self.open_garage_edit_window_by_name(gn)); self.left_menu_popup.add_separator(); self.left_menu_popup.add_command(label=f"❌ 移除", command=lambda: self.delete_garage_by_name(gn))
        else: self.left_menu_popup.add_command(label=f"❌ 批量刪除 {len(ita)} 個", command=lambda: self.delete_multiple_garages_from_menu(ita))
        self.left_menu_popup.post(event.x_root, event.y_root)

    def delete_multiple_garages_from_menu(self, items):
        gd = set()
        for it in items:
            if it["type"] == "base":
                bn = it["name"]
                for g in self.data["garages"]:
                    if g == bn or g.startswith(bn + " - "): gd.add(g)
            elif it["type"] in ["single", "sub"]: gd.add(it["name"])
        if not gd: return
        gstr = "\n".join(list(gd)[:10])
        if len(gd) > 10: gstr += f"\n...等共 {len(gd)} 個"
        if messagebox.askyesno("批量刪除", f"⚠️ 將批量拆除以下車庫！\n\n{gstr}\n\n確定？"):
            for g in gd:
                if g in self.data["garages"]: self.data["garages"].remove(g)
                if g in self.data["garage_limits"]: del self.data["garage_limits"][g]
                for v in self.data["vehicles"]:
                    if v.get("garage") == g: v["garage"] = "未分類"
                for sv in self.data.get("special_vehicles", []):
                    if sv.get("location") == g: sv["location"] = "未分類"
            for b in list(self.expanded_bases):
                if b in gd or not any(x == b or x.startswith(b + " - ") for x in self.data["garages"]): self.expanded_bases.discard(b)
            save_data(self.all_data); self.log_action(f"🏠 批量移除 {len(gd)} 個車庫"); self.refresh_garage_table(); self.apply_filters(); self.update_garage_comboboxes(); self.refresh_special_table(); self.set_status(f"🏠 批量出售 {len(gd)} 個車庫。", "#FF9800")

    def open_move_vehicle_window(self, g_name, listbox):
        if self.check_win('move_vehicle_window'): return
        s = listbox.curselection()
        if not s: return messagebox.showwarning("提示", "請先點選！")
        if not getattr(self, 'current_garage_car_indices', []): return
        sai = [self.current_garage_car_indices[i] for i in s]
        self.move_vehicle_window = win = tk.Toplevel(self.root); win.title("🚚 移動"); self.center_toplevel_window(win, 400, 220); win.configure(bg=COLOR_CARD_BG)
        tk.Label(win, text=f"將 {len(sai)} 輛移至：", font=FONT_LARGE_BOLD, bg=COLOR_CARD_BG, fg="white").pack(pady=(20, 10))
        cl = ["未分類"] + [g for g in self.data["garages"] if g not in ["未分類", "帕格薩斯"]] + [x["name"] for x in self.data.get("special_vehicles", []) if x.get("can_store", False)]
        cd = ttk.Combobox(win, state="readonly", font=FONT_NORMAL, values=cl, width=28); cd.pack(pady=5); cd.set("未分類")
        def cf():
            d = cd.get()
            if d == g_name: return messagebox.showinfo("提示", "目標相同！", parent=win)
            dl = self.data.get("app_settings", {}).get("disable_all_limits", False)
            if d != "未分類" and not dl:
                l = self.data["garage_limits"].get(d, 10); u = self.count_cars_in_garage(d)
                if u + len(sai) > l: return messagebox.showerror("錯誤", f"【{d}】不足！", parent=win)
            for i in sai: self.data["vehicles"][i]["garage"] = d; self.data["vehicles"][i]["updated_at"] = time.strftime('%Y-%m-%d %H:%M')
            self.sync_special_from_vehicles(); save_data(self.all_data); self.show_toast_progress(f"🚚 成功移動！"); self.refresh_garage_table(); self.refresh_vehicle_tables(); self.refresh_statistics(); win.destroy()
        bf = tk.Frame(win, bg=COLOR_CARD_BG); bf.pack(pady=20); ttk.Button(bf, text="移動", command=cf, style="Primary.TButton").pack(side="left", padx=10, ipady=4); ttk.Button(bf, text="取消", command=win.destroy, style="Secondary.TButton").pack(side="right", padx=10, ipady=4)

    def open_garage_edit_window_by_name(self, old_name):
        if self.check_win('garage_edit_window'): return
        ol = self.data["garage_limits"].get(old_name, 10)
        self.garage_edit_window = win = tk.Toplevel(self.root); win.title("編輯屬性"); self.center_toplevel_window(win, 340, 260) 
        tk.Label(win, text="名稱:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(15,2)); en = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=24); en.insert(0, old_name); en.pack(); en.focus()
        tk.Label(win, text="上限:", bg=COLOR_MAIN_BG, fg="white", font=FONT_BOLD).pack(pady=(10,2)); el = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg="white", insertbackground="white", relief="solid", width=12); el.insert(0, str(ol)); el.pack()
        apply_focus_highlight(en); apply_focus_highlight(el)
        def sv(e=None):
            nn = en.get().strip()
            try: nl = int(el.get().strip() or 10)
            except: nl = 10
            dl = self.data.get("app_settings", {}).get("disable_all_limits", False)
            if nn != old_name and nn in self.data["garages"]: return messagebox.showerror("錯誤", "已存在！")
            if not dl and nl < self.count_cars_in_garage(old_name): return messagebox.showerror("錯誤", "不可小於目前數量！")
            ix = self.data["garages"].index(old_name); self.data["garages"][ix] = nn; self.data["garage_limits"][nn] = nl
            if nn != old_name:
                del self.data["garage_limits"][old_name]
                for v in self.data["vehicles"]:
                    if v.get("garage") == old_name: v["garage"] = nn
                for s in self.data.get("special_vehicles", []):
                    if s.get("location") == old_name: s["location"] = nn
                if any(g != old_name and g.startswith(old_name + " - ") for g in self.data["garages"]):
                    if messagebox.askyesno("同步", f"是否同步將附屬名稱改為【{nn}】？", parent=win):
                        for c in [x for x in self.data["garages"] if x != nn and x.startswith(old_name + " - ")]:
                            nc = c.replace(old_name, nn, 1); ci = self.data["garages"].index(c)
                            self.data["garages"][ci] = nc; self.data["garage_limits"][nc] = self.data["garage_limits"].pop(c)
                            for v in self.data["vehicles"]:
                                if v.get("garage") == c: v["garage"] = nc
                            for s in self.data.get("special_vehicles", []):
                                if s.get("location") == c: s["location"] = nc
                bs = old_name.split(" - ", 1)[0]
                if old_name == bs and nn != bs and bs in self.expanded_bases: self.expanded_bases.remove(bs); self.expanded_bases.add(nn)
            save_data(self.all_data); self.refresh_garage_table(); self.refresh_vehicle_tables(); self.update_garage_comboboxes(); self.refresh_special_table(); win.destroy(); self.set_status(f"📝 更新 {nn} 成功。", "#3498db")
        def dga(): self.delete_garage_by_name(old_name); win.destroy()
        bf = tk.Frame(win, bg=COLOR_MAIN_BG); bf.pack(fill="x", padx=35, pady=15); ttk.Button(bf, text="保存", command=sv, style="Success.TButton").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=4); ttk.Button(bf, text="❌ 刪除", command=dga, style="Danger.TButton").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4)
        en.bind("<Return>", lambda e: el.focus()); el.bind("<Return>", sv)

    def delete_garage_by_name(self, g_name):
        if messagebox.askyesno("確認", f"拆除「{g_name}」？"):
            if g_name in self.data["garages"]: self.data["garages"].remove(g_name)
            if g_name in self.data["garage_limits"]: del self.data["garage_limits"][g_name]
            for v in self.data["vehicles"]:
                if v.get("garage") == g_name: v["garage"] = "未分類"
            for s in self.data.get("special_vehicles", []):
                if s.get("location") == g_name: s["location"] = "未分類"
            save_data(self.all_data); self.refresh_garage_table(); self.apply_filters(); self.update_garage_comboboxes(); self.refresh_special_table(); self.set_status(f"🏠 出售 {g_name}。", "#FF9800")

    def open_batch_garage_window(self):
        if self.check_win('batch_g_window'): return
        if not self.data: return
        self.batch_g_window = win = tk.Toplevel(self.root); win.title("📦 批量新增"); self.center_toplevel_window(win, 550, 280); win.configure(bg=COLOR_CARD_BG)
        fa = tk.LabelFrame(win, text=" ➕ 批量新增 (一行一個) ", font=FONT_BOLD, bg=COLOR_CARD_BG, fg="#4CAF50"); fa.pack(fill="x", padx=15, pady=10, ipady=5); ta = tk.Text(fa, height=6, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", relief="solid"); ta.pack(fill="x", padx=10, pady=5)
        def do_ba():
            ls = ta.get("1.0", tk.END).strip().split('\n'); a = 0; dg = self.data.get("app_settings", {}).get("default_garage_limit", 10)
            for l in ls:
                n = l.strip()
                if not n or n in self.data["garages"]: continue
                self.data["garages"].append(n); self.data["garage_limits"][n] = dg; a += 1
            if a > 0:
                if "garage_timestamps" not in self.data: self.data["garage_timestamps"] = {}
                for l in ls:
                    n = l.strip()
                    if n and n in self.data["garages"]: self.data["garage_timestamps"][n] = time.strftime("%Y-%m-%d %H:%M")
                save_data(self.all_data); self.refresh_garage_table(); self.update_garage_comboboxes(); ta.delete("1.0", tk.END); self.show_toast_progress(f"✅ 成功新增 {a} 個")
            else: messagebox.showinfo("提示", "無效名稱或已存在！", parent=win)
        ttk.Button(fa, text="執行", command=do_ba, style="Success.TButton").pack(side="right", padx=10, pady=5)

    def add_garage_simple(self):
        if not self.data: return
        n = self.eng.get().strip()
        if not n: return
        try: f = int(self.engf.get().strip() or 1)
        except: f = 1
        ft = self.cft.get(); dg = self.data.get("app_settings", {}).get("default_garage_limit", 10)
        lim = simpledialog.askinteger("上限", f"輸入上限\n(預設 {dg}):", initialvalue=dg, minvalue=1)
        if not lim: return 
        an = []
        if n not in self.data["garages"]: self.data["garages"].append(n); self.data["garage_limits"][n] = lim; an.append(n)
        elif f == 1: return messagebox.showerror("錯誤", "名稱重複！")
        if f > 1:
            for i in range(1, f + 1):
                fn = f"{n} - {'B' if '地下' in ft else '車庫'}{i}"
                if fn not in self.data["garages"]: self.data["garages"].append(fn); self.data["garage_limits"][fn] = lim; an.append(fn)
        if "garage_timestamps" not in self.data: self.data["garage_timestamps"] = {}
        for fn in an: self.data["garage_timestamps"][fn] = time.strftime("%Y-%m-%d %H:%M")
        save_data(self.all_data); self.show_toast_progress(f"🏠 成功！"); self.refresh_garage_table(); self.update_garage_comboboxes(); self.eng.delete(0, tk.END); self.engf.delete(0, tk.END); self.engf.insert(0, "1"); self.eng.focus()

    def add_sub_floor(self, bn):
        fn = simpledialog.askstring("擴建", f"輸入【{bn}】的新附屬名稱:")
        if not fn: return
        f_n = f"{bn} - {fn}"
        if f_n in self.data["garages"]: return messagebox.showerror("錯誤", "已存在！")
        dg = self.data.get("app_settings", {}).get("default_garage_limit", 10)
        lim = simpledialog.askinteger("上限", f"上限:", initialvalue=dg, minvalue=1)
        if not lim: return
        ii = len(self.data["garages"])
        for i, g in enumerate(self.data["garages"]):
            if g == bn or g.startswith(bn + " - "): ii = i + 1
        self.data["garages"].insert(ii, f_n); self.data["garage_limits"][f_n] = lim; self.data.setdefault("garage_timestamps", {})[f_n] = time.strftime("%Y-%m-%d %H:%M")
        save_data(self.all_data); self.show_toast_progress(f"🏠 擴建：{fn}"); self.expanded_bases.add(bn); self.refresh_garage_table(); self.update_garage_comboboxes()

    def rename_entire_property(self, ob):
        nb = simpledialog.askstring("改名", f"新物業名稱\n(原：{ob}):", initialvalue=ob)
        if not nb or nb == ob: return
        if any(g == nb or g.startswith(nb + " - ") for g in self.data["garages"]): return messagebox.showerror("錯誤", "名稱衝突！")
        for og in [g for g in self.data["garages"] if g == ob or g.startswith(ob + " - ")]:
            ng = og.replace(ob, nb, 1); ix = self.data["garages"].index(og)
            self.data["garages"][ix] = ng; self.data["garage_limits"][ng] = self.data["garage_limits"].pop(og)
            for v in self.data["vehicles"]:
                if v.get("garage") == og: v["garage"] = ng
            for s in self.data.get("special_vehicles", []):
                if s.get("location") == og: s["location"] = ng
        if ob in self.expanded_bases: self.expanded_bases.remove(ob); self.expanded_bases.add(nb)
        save_data(self.all_data); self.refresh_garage_table(); self.refresh_vehicle_tables(); self.update_garage_comboboxes(); self.refresh_special_table(); self.show_toast_progress(f"✅ 更名為：{nb}")

    def delete_entire_property(self, bn):
        rg = [g for g in self.data["garages"] if g == bn or g.startswith(bn + " - ")]
        if messagebox.askyesno("警告", f"拆除整棟【{bn}】？\n\n包含：\n{', '.join(rg)}\n\n確定？"):
            for gn in rg:
                self.data["garages"].remove(gn); del self.data["garage_limits"][gn]
                for v in self.data["vehicles"]:
                    if v.get("garage") == gn: v["garage"] = "未分類"
                for s in self.data.get("special_vehicles", []):
                    if s.get("location") == gn: s["location"] = "未分類"
            if bn in self.expanded_bases: self.expanded_bases.remove(bn)
            save_data(self.all_data); self.log_action(f"🏠 變賣：【{bn}】"); self.refresh_garage_table(); self.apply_filters(); self.update_garage_comboboxes(); self.refresh_special_table(); self.set_status(f"🏠 出售【{bn}】", "#FF9800")
    # ==========================================
    # 📚 全新架構：攻略筆記 (極簡全螢幕 + 右鍵選單管理)
    # ==========================================
    def setup_guides_tab(self):
        af = tk.Frame(self.tab_guides, bg=COLOR_MAIN_BG)
        af.pack(fill="x", padx=15, pady=(15, 5))
        
        # 提示文字，引導用戶去上方選單與使用右鍵
        tk.Label(af, text="💡 提示：按上方【新增 (N)】建立攻略。在下方清單按【滑鼠右鍵】可編輯或刪除資料。", font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="#a8e6cf").pack(side="left")
        
        tf = tk.Frame(self.tab_guides, bg=COLOR_MAIN_BG)
        tf.pack(fill="both", expand=True, padx=15, pady=10)
        
        self.txt_guide_preview = tk.Text(tf, font=FONT_NORMAL, bg="#111111", fg="#a8e6cf", relief="solid", height=5)
        self.txt_guide_preview.pack(side="bottom", fill="x", pady=(10, 0))
        self.txt_guide_preview.insert("1.0", "💡 點擊上方的任務清單，這裡會「垂直顯示」完整的多行菁英條件...")
        self.txt_guide_preview.config(state="disabled")
        
        self.tree_guides = ttk.Treeview(tf, columns=("category", "name", "elite", "time"), show="headings", selectmode="extended")
        self.tree_guides.heading("category", text="系列大標題")
        self.tree_guides.heading("name", text="任務名稱")
        self.tree_guides.heading("elite", text="菁英條件 (預覽)")
        self.tree_guides.heading("time", text="更新時間")
        
        self.tree_guides.column("category", width=160, anchor="w", stretch=False)
        self.tree_guides.column("name", width=180, anchor="w", stretch=False)
        self.tree_guides.column("elite", width=420, anchor="w", stretch=True)
        self.tree_guides.column("time", width=140, anchor="center", stretch=False)
        
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree_guides.yview)
        self.tree_guides.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree_guides.pack(side="left", fill="both", expand=True)
        
        self.tree_guides.bind("<Double-1>", self.open_guide_edit_window)
        self.tree_guides.bind("<<TreeviewSelect>>", self.on_guide_select)
        
        # 🎯 綁定右鍵專屬選單
        self.guide_popup_menu = tk.Menu(self.root, tearoff=0, bg=COLOR_CARD_BG, fg="white", font=FONT_NORMAL)
        self.tree_guides.bind("<Button-3>", self.show_guide_context_menu)

    def on_guide_select(self, event=None):
        if not self.data or "guides" not in self.data: return
        sel = self.tree_guides.selection()
        self.txt_guide_preview.config(state="normal")
        self.txt_guide_preview.delete("1.0", tk.END)
        if not sel:
            self.txt_guide_preview.insert("1.0", "💡 點擊上方的任務清單，這裡會「垂直顯示」完整的多行菁英條件...")
        else:
            idx = int(sel[0])
            g = self.data["guides"][idx]
            cat = g.get('category', '').strip()
            name = g.get('mission_name', '').strip()
            title = f"【{cat}】 - {name}" if cat else f"【{name}】"
            self.txt_guide_preview.insert("1.0", f"🎯 {title} 菁英條件：\n{g.get('elite_conditions', '')}")
        self.txt_guide_preview.config(state="disabled")

    def show_guide_context_menu(self, event):
        if not self.data: return
        iid = self.tree_guides.identify_row(event.y)
        if iid:
            # 如果滑鼠右鍵點擊的那一行沒有被選取，就自動幫它選起來
            if iid not in self.tree_guides.selection():
                self.tree_guides.selection_set(iid)
            self.on_guide_select() # 手動刷新一下底下的預覽黑板
            
            # 展開右鍵選單
            self.guide_popup_menu.delete(0, tk.END)
            self.guide_popup_menu.add_command(label="📝 編輯選取的任務", command=lambda: self.open_guide_edit_window(event))
            self.guide_popup_menu.add_separator()
            self.guide_popup_menu.add_command(label="❌ 刪除該筆任務", command=self.delete_guide)
            self.guide_popup_menu.post(event.x_root, event.y_root)
    def refresh_guides_table(self):
        if hasattr(self, 'tree_guides') and self.tree_guides.winfo_exists():
            for i in self.tree_guides.get_children(): self.tree_guides.delete(i)
            if self.data and "guides" in self.data:
                # 1. 智慧分類排序：以「大標題」為第一優先，相同的再依照「任務名稱」排序
                sorted_indices = sorted(
                    range(len(self.data["guides"])), 
                    key=lambda i: (self.data["guides"][i].get("category", ""), self.data["guides"][i].get("mission_name", ""))
                )
                
                # 2. 視覺留白邏輯：紀錄上一筆的大標題
                last_cat = None
                
                for idx in sorted_indices: 
                    g = self.data["guides"][idx]
                    elite_display = g.get("elite_conditions", "").replace("\n", "  /  ")
                    current_cat = g.get("category", "").strip()
                    
                    # 💡 核心魔法：如果這個大標題跟上一個一樣，顯示名稱就設為空白；反之則顯示大標題
                    display_cat = current_cat if current_cat != last_cat else ""
                    last_cat = current_cat # 更新紀錄
                    
                    # 將資料插入表格 (使用 display_cat)
                    self.tree_guides.insert("", "end", iid=str(idx), values=(display_cat, g.get("mission_name", ""), elite_display, g.get("updated_at", "")))
            self.on_guide_select()

    def delete_guide(self):
        if not self.data or "guides" not in self.data: return
        sel = self.tree_guides.selection()
        if not sel: return messagebox.showwarning("提示", "請先點選要刪除的任務！")
        if messagebox.askyesno("刪除", "確定要刪除選取的任務嗎？"):
            for i in sorted([int(s) for s in sel], reverse=True): 
                del self.data["guides"][i]
            save_data(self.all_data)
            self.refresh_guides_table()
            self.show_toast_progress("❌ 任務已刪除")

    # 🎯 全新獨立新增視窗 (下拉選單版)
    def open_add_guide_window(self):
        if not getattr(self, 'data', None): 
            return messagebox.showwarning("提示", "請先至「帳號管理」登入角色 ID！")
            
        if self.check_win('guide_add_window'): return
        
        self.guide_add_window = win = tk.Toplevel(self.root)
        win.title("📝 新增任務攻略")
        try: self.center_toplevel_window(win, 450, 420)
        except: win.geometry("450x420")
        win.configure(bg=COLOR_CARD_BG)
        
        tk.Label(win, text="系列大標題 (可選現有或輸入新名稱):", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).pack(pady=(15,2))
        
        # 💡 自動抓取現有大標題清單
        existing_cats = []
        if self.data and "guides" in self.data:
            for g in self.data["guides"]:
                c = g.get("category", "").strip()
                if c and c not in existing_cats:
                    existing_cats.append(c)
                    
        # 將原本的 Entry 升級為 Combobox
        ecat = ttk.Combobox(win, font=FONT_NORMAL, values=existing_cats, width=33)
        last_cat = self.data.get("guides", [])[-1].get("category", "") if self.data.get("guides") else ""
        ecat.insert(0, last_cat)
        ecat.pack()
        
        tk.Label(win, text="任務名稱:", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).pack(pady=(10,2))
        en = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=35)
        en.pack()
        en.focus() # 自動對焦到任務名稱
        apply_focus_highlight(en)
        
        tk.Label(win, text="菁英條件 (可多行):", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).pack(pady=(10,2))
        ee = tk.Text(win, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=35, height=6)
        ee.pack()
        apply_focus_highlight(ee)
        
        def save_new(e=None):
            cat = ecat.get().strip()
            n = en.get().strip()
            el = ee.get("1.0", tk.END).strip()
            
            if not n: return messagebox.showwarning("提示", "請輸入任務名稱！", parent=win)
            
            self.data.setdefault("guides", []).append({
                "category": cat,
                "mission_name": n, 
                "elite_conditions": el, 
                "created_at": time.strftime('%Y-%m-%d %H:%M'), 
                "updated_at": time.strftime('%Y-%m-%d %H:%M')
            })
            save_data(self.all_data)
            self.log_action(f"📚 新增任務：【{cat}】{n}")
            
            self.refresh_guides_table()
            self.show_toast_progress("📚 任務已儲存！")
            
            # 動態更新下拉選單清單，不用重開視窗就能立刻看到新的分類
            if cat and cat not in ecat["values"]:
                ecat["values"] = list(ecat["values"]) + [cat]
            
            # 儲存後清空任務名稱與條件
            en.delete(0, tk.END)
            ee.delete("1.0", tk.END)
            en.focus()
            
        bf = tk.Frame(win, bg=COLOR_CARD_BG)
        bf.pack(fill="x", padx=45, pady=20)
        ttk.Button(bf, text="✨ 儲存並繼續新增", command=save_new, style="Success.TButton").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=4)
        ttk.Button(bf, text="關閉", command=win.destroy, style="Secondary.TButton").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4)

    def open_guide_edit_window(self, event=None):
        if event and not self.tree_guides.identify_row(event.y): 
            return
            
        if self.check_win('guide_edit_window'): return
        if not self.data or "guides" not in self.data: return
        sel = self.tree_guides.selection()
        if not sel or len(sel) > 1: return messagebox.showwarning("提示", "請單選一筆編輯！")
        
        idx = int(sel[0])
        g = self.data["guides"][idx]
        self.guide_edit_window = win = tk.Toplevel(self.root)
        win.title("編輯任務")
        
        try: self.center_toplevel_window(win, 450, 420)
        except: win.geometry("450x420")
        
        win.configure(bg=COLOR_CARD_BG)
        
        tk.Label(win, text="系列大標題 (可選現有或輸入新名稱):", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).pack(pady=(15,2))
        
        # 💡 自動抓取現有大標題清單 (編輯視窗同樣升級)
        existing_cats = []
        for temp_g in self.data.get("guides", []):
            c = temp_g.get("category", "").strip()
            if c and c not in existing_cats:
                existing_cats.append(c)
                
        ecat = ttk.Combobox(win, font=FONT_NORMAL, values=existing_cats, width=33)
        ecat.insert(0, g.get('category', ''))
        ecat.pack()
        
        tk.Label(win, text="任務名稱:", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).pack(pady=(10,2))
        en = tk.Entry(win, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=35)
        en.insert(0, g.get('mission_name', ''))
        en.pack()
        en.focus()
        apply_focus_highlight(en)
        
        tk.Label(win, text="菁英條件 (可多行):", bg=COLOR_CARD_BG, fg="white", font=FONT_BOLD).pack(pady=(10,2))
        ee = tk.Text(win, font=FONT_NORMAL, bg=COLOR_MAIN_BG, fg="white", insertbackground="white", relief="solid", width=35, height=6)
        ee.insert("1.0", g.get('elite_conditions', ''))
        ee.pack()
        apply_focus_highlight(ee)
        
        def save(e=None): 
            g.update({
                'category': ecat.get().strip(),
                'mission_name': en.get().strip(), 
                'elite_conditions': ee.get("1.0", tk.END).strip(), 
                'updated_at': time.strftime('%Y-%m-%d %H:%M')
            })
            save_data(self.all_data)
            self.refresh_guides_table()
            win.destroy()
            self.show_toast_progress("✅ 修改成功！")
            
        bf = tk.Frame(win, bg=COLOR_CARD_BG)
        bf.pack(fill="x", padx=45, pady=20)
        ttk.Button(bf, text="儲存", command=save, style="Success.TButton").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=4)
        ttk.Button(bf, text="取消", command=win.destroy, style="Secondary.TButton").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=4)

if __name__ == "__main__":
    try:
        import ctypes
        if ctypes.windll.kernel32.CreateMutexW(None, False, "GTA_Garage_App_Single_Instance_Mutex") and ctypes.windll.kernel32.GetLastError() == 183:
            er = tk.Tk(); er.withdraw(); messagebox.showerror("失敗", "⚠️ 程式已在執行中！"); er.destroy(); sys.exit(0)
    except: pass
    try: root = tk.Tk(); app = GTAGarageApp(root); root.mainloop()
    except Exception as e:
        import traceback; er = tk.Tk(); er.withdraw(); messagebox.showerror("系統崩潰報告", f"啟動失敗，錯誤代碼：\n\n{traceback.format_exc()}"); er.destroy()
