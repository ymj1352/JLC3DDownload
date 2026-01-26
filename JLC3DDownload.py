import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import requests
import json
import os
import threading
import configparser
from datetime import datetime
import webbrowser
import subprocess
import sys

# =====================================================
# 配置与逻辑 (保持不变)
# =====================================================
APP_DIR = os.path.join(os.path.expanduser("~"), ".jlc3d")
CONFIG_FILE = os.path.join(APP_DIR, "config.ini")

def ensure_app_dir():
    if not os.path.exists(APP_DIR): os.makedirs(APP_DIR)

def save_download_path(path):
    ensure_app_dir()
    cfg = configparser.ConfigParser()
    cfg["PATH"] = {"DownloadPath": path}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f: cfg.write(f)

def load_download_path():
    if not os.path.exists(CONFIG_FILE): return None
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE, encoding="utf-8")
    return cfg.get("PATH", "DownloadPath", fallback=None)

def default_desktop():
    return os.path.join(os.path.expanduser("~"), "Desktop")

# API 逻辑
BASE_API = "https://pro.lceda.cn/api"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def search_product(code):
    r = requests.post(f"{BASE_API}/eda/product/search", data={"keyword": code, "needAggs": "true", "currPage": "1", "pageSize": "10"}, headers=HEADERS, timeout=10)
    r.raise_for_status()
    products = r.json()["result"]["productList"]
    if not products: raise ValueError("未找到该器件")
    return products[0]["hasDevice"]

def get_model_uuid(device_uuid):
    r = requests.post(f"{BASE_API}/devices/searchByIds", data={"uuids[]": device_uuid}, headers=HEADERS, timeout=10)
    r.raise_for_status()
    attrs = r.json()["result"][0]["attributes"]
    if "3D Model" not in attrs: raise ValueError("该器件没有 3D 模型")
    return attrs["3D Model"]

def get_model_file(model_uuid):
    r = requests.post(f"{BASE_API}/components/searchByIds?forceOnline=1", data={"uuids[]": model_uuid, "dataStr": "yes"}, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = json.loads(r.json()["result"][0]["dataStr"])
    return data["model"]

def download_step_file(model_file):
    url = f"https://modules.lceda.cn/qAxj6KHrDKw4blvCG8QJPs7Y/{model_file}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.content

# =====================================================
# 调整后的 UI
# =====================================================

class JLC3DApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("嘉立创 3D 模型下载器")
        self.geometry("540x440")
        self.configure(bg="#f8f9fa")

        self.download_path = load_download_path() or default_desktop()
        self.last_download_file = None

        self._build_ui()

    def _build_ui(self):
        # 主容器
        main_container = tk.Frame(self, bg="#f8f9fa", padx=20, pady=15)
        main_container.pack(fill="both", expand=True)

        # 1. 标题标签（加大字体）
        tk.Label(main_container, text="元器件编号：", bg="#f8f9fa", font=("Microsoft YaHei", 12, "bold")).pack(anchor="w")

        # 2. 输入区域
        top_row = tk.Frame(main_container, bg="#f8f9fa")
        top_row.pack(fill="x", pady=(10, 20))

        # 输入框：设置 width 限制长度，字体加大
        self.entry = ttk.Entry(top_row, font=("Arial", 14), width=15)
        self.entry.insert(0, "C8734")
        self.entry.pack(side="left", padx=(0, 15))

        # 下载按钮：绿色，加大字体
        self.btn_download = tk.Button(
            top_row,
            text="立即下载",
            bg="#28a745",
            fg="white",
            font=("Microsoft YaHei", 11, "bold"),
            relief="flat",
            width=12,
            height=1,
            cursor="hand2",
            command=self.start_download
        )
        self.btn_download.pack(side="left")

        # 3. 日志区域（保持原有 Consolas 字体）
        self.log = scrolledtext.ScrolledText(
            main_container,
            height=10,
            font=("Consolas", 10),
            bg="white",
            relief="solid",
            borderwidth=1
        )
        self.log.pack(fill="both", expand=True)

        # 4. 底部路径栏（加大字体）
        bottom_frame = tk.Frame(main_container, bg="#f8f9fa", pady=15)
        bottom_frame.pack(fill="x")

        self.path_label = tk.Label(
            bottom_frame,
            text=f"保存至: {self.download_path}",
            bg="#f8f9fa",
            fg="#495057",
            font=("Microsoft YaHei", 10),
            anchor="w"
        )
        self.path_label.pack(side="left", fill="x", expand=True)

        # 定位按钮也略微调大
        btn_style = ttk.Style()
        btn_style.configure("Large.TButton", font=("Microsoft YaHei", 10))
        ttk.Button(bottom_frame, text="定位文件", style="Large.TButton", width=10, command=self.locate_file).pack(side="right")

        # 菜单
        menu = tk.Menu(self)
        self.config(menu=menu)
        file_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="修改下载路径", command=self.choose_path)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.quit)
        help_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self.show_about)

    def log_msg(self, msg):
        now = datetime.now().strftime("%H:%M:%S")
        self.log.insert(tk.END, f"[{now}] {msg}\n")
        self.log.see(tk.END)

    def choose_path(self):
        p = filedialog.askdirectory()
        if p:
            self.download_path = p
            save_download_path(p)
            self.path_label.config(text=f"保存至: {p}")

    def locate_file(self):
        if not self.last_download_file or not os.path.exists(self.last_download_file):
            messagebox.showinfo("提示", "还没有可定位的下载文件")
            return
        path = self.last_download_file
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif sys.platform.startswith("darwin"):
            subprocess.call(["open", "-R", path])
        else:
            subprocess.call(["xdg-open", os.path.dirname(path)])

    # 关于内容完全保留
    def show_about(self):
        about = tk.Toplevel(self)
        about.title("关于")
        about.geometry("360x220")
        about.resizable(False, False)
        text = tk.Text(about, wrap="word", padx=10, pady=10)
        text.pack(fill="both", expand=True)
        content = (
            "嘉立创 3D 模型下载器\n"
            "版本：1.2\n"
            "作者：Jupiter\n\n"
            "项目地址：\n"
            "https://github.com/zhutongxueya/JLC3DDownload\n\n"
            "感谢 kulya97 的原始思路"
        )
        text.insert("1.0", content)
        text.config(state="disabled")
        text.tag_add("link", "5.0", "5.end")
        text.tag_config("link", foreground="blue", underline=True)
        text.tag_bind("link", "<Button-1>", lambda e: webbrowser.open("https://github.com/zhutongxueya/JLC3DDownload"))

    def start_download(self):
        # 下载中变色逻辑
        self.btn_download.config(state="disabled", bg="#6c757d", text="下载中...")
        threading.Thread(target=self.download_task, daemon=True).start()

    def download_task(self):
        code = self.entry.get().strip()
        if not code:
            self.after(0, lambda: messagebox.showwarning("提示", "请输入元器件编号"))
            self.after(0, lambda: self.btn_download.config(state="normal", bg="#28a745", text="立即下载"))
            return

        try:
            self.after(0, lambda: self.log_msg(f"搜索器件【{code}】…"))
            device = search_product(code)
            self.after(0, lambda: self.log_msg("解析模型 ID…"))
            model_uuid = get_model_uuid(device)
            self.after(0, lambda: self.log_msg("下载 STEP 文件…"))
            model_file = get_model_file(model_uuid)
            data = download_step_file(model_file)

            filepath = os.path.join(self.download_path, f"{code}.step")
            with open(filepath, "wb") as f:
                f.write(data)

            self.last_download_file = filepath
            self.after(0, lambda: self.log_msg(f"下载完成 ✔\n保存至：{filepath}"))

        except Exception as e:
            self.after(0, lambda: self.log_msg(f"错误：{e}"))
        finally:
            self.after(0, lambda: self.btn_download.config(state="normal", bg="#28a745", text="立即下载"))

if __name__ == "__main__":
    JLC3DApp().mainloop()
