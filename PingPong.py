import concurrent.futures
import ctypes
import math
import queue
import ssl
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import win32gui


SITES = [
    {
        "name": "YouTube",
        "url": "https://www.youtube.com/generate_204",
    },
    {
        "name": "ChatGPT",
        "url": "https://chatgpt.com/",
    },
    {
        "name": "Claude",
        "url": "https://claude.ai/",
    },
]

TIMEOUT_SECONDS = 8
AUTO_INTERVAL_SECONDS = 30
ENABLE_WINDOWS_NOTIFICATIONS = False

UI = {
    "bg": "#ffffff",
    "wash": "#f2fff8",
    "panel": "#ffffff",
    "panel_2": "#ffffff",
    "panel_hot": "#101010",
    "surface": "#fafafa",
    "surface_hot": "#f6fff9",
    "text": "#0d0d0d",
    "muted": "#666666",
    "dim": "#888888",
    "faint": "#a3a3a3",
    "brand": "#18e299",
    "brand_soft": "#d4fae8",
    "brand_deep": "#0fa76e",
    "blue": "#3772cf",
    "green": "#18e299",
    "amber": "#c37d0d",
    "amber_soft": "#fff7df",
    "red": "#d45656",
    "red_soft": "#fff1f1",
    "border": "#e5e5e5",
    "border_strong": "#151515",
    "shadow": "#d8d8d8",
}


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("hWnd", ctypes.c_void_p),
        ("uID", ctypes.c_uint),
        ("uFlags", ctypes.c_uint),
        ("uCallbackMessage", ctypes.c_uint),
        ("hIcon", ctypes.c_void_p),
        ("szTip", ctypes.c_wchar * 128),
        ("dwState", ctypes.c_ulong),
        ("dwStateMask", ctypes.c_ulong),
        ("szInfo", ctypes.c_wchar * 256),
        ("uTimeoutOrVersion", ctypes.c_uint),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", ctypes.c_ulong),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", ctypes.c_void_p),
    ]


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", ctypes.c_int),
        ("xHotspot", ctypes.c_uint),
        ("yHotspot", ctypes.c_uint),
        ("hbmMask", ctypes.c_void_p),
        ("hbmColor", ctypes.c_void_p),
    ]


NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIIF_INFO = 0x00000001
NIIF_WARNING = 0x00000002
WM_APP = 0x8000
WM_TRAY_NOTIFY = WM_APP + 1
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
IDI_APPLICATION = 32512
NOTIFICATION_UID = 1
TRAY_ICON_SIZE = 16
TRAY_STATUS_COLORS = {
    "idle": (124, 130, 143),
    "good": (18, 128, 92),
    "partial": (214, 138, 23),
    "bad": (180, 35, 24),
}


def _truncate(text, limit):
    return text if len(text) < limit else text[: limit - 1]


def _color_ref(red, green, blue):
    return red | (green << 8) | (blue << 16)


def _build_notify_data(hwnd, icon_handle, title="", message="", info_flags=NIIF_INFO):
    data = NOTIFYICONDATA()
    data.cbSize = ctypes.sizeof(NOTIFYICONDATA)
    data.hWnd = hwnd
    data.uID = NOTIFICATION_UID
    data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    data.uCallbackMessage = WM_TRAY_NOTIFY
    data.hIcon = icon_handle
    data.szTip = "PingPong"

    if title or message:
        data.uFlags |= NIF_INFO
        data.szInfoTitle = _truncate(title, 64)
        data.szInfo = _truncate(message, 256)
        data.dwInfoFlags = info_flags

    return data


def _create_status_icon(color):
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    user32.GetDC.restype = ctypes.c_void_p
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.CreateIconIndirect.restype = ctypes.c_void_p
    user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
    user32.FillRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT), ctypes.c_void_p]
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi32.CreateSolidBrush.restype = ctypes.c_void_p
    gdi32.CreateSolidBrush.argtypes = [ctypes.c_uint]
    gdi32.CreatePen.restype = ctypes.c_void_p
    gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    gdi32.SelectObject.restype = ctypes.c_void_p
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.CreateBitmap.restype = ctypes.c_void_p
    gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
    gdi32.Ellipse.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]

    screen_dc = user32.GetDC(None)
    if not screen_dc:
        raise OSError("无法创建托盘图标")

    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    color_bitmap = gdi32.CreateCompatibleBitmap(screen_dc, TRAY_ICON_SIZE, TRAY_ICON_SIZE)
    mask_bitmap = gdi32.CreateBitmap(TRAY_ICON_SIZE, TRAY_ICON_SIZE, 1, 1, None)
    if not mem_dc or not color_bitmap or not mask_bitmap:
        if color_bitmap:
            gdi32.DeleteObject(color_bitmap)
        if mask_bitmap:
            gdi32.DeleteObject(mask_bitmap)
        if mem_dc:
            gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)
        raise OSError("无法分配托盘图标位图")

    previous_bitmap = gdi32.SelectObject(mem_dc, color_bitmap)
    background_brush = gdi32.CreateSolidBrush(_color_ref(248, 249, 251))
    fill_brush = gdi32.CreateSolidBrush(_color_ref(*color))
    border_pen = gdi32.CreatePen(0, 1, _color_ref(255, 255, 255))
    previous_brush = gdi32.SelectObject(mem_dc, background_brush)
    previous_pen = gdi32.SelectObject(mem_dc, border_pen)

    outer_rect = RECT(0, 0, TRAY_ICON_SIZE, TRAY_ICON_SIZE)
    user32.FillRect(mem_dc, ctypes.byref(outer_rect), background_brush)
    gdi32.SelectObject(mem_dc, fill_brush)
    gdi32.Ellipse(mem_dc, 2, 2, TRAY_ICON_SIZE - 3, TRAY_ICON_SIZE - 3)

    gdi32.SelectObject(mem_dc, previous_pen)
    gdi32.SelectObject(mem_dc, previous_brush)
    gdi32.SelectObject(mem_dc, previous_bitmap)

    icon_info = ICONINFO()
    icon_info.fIcon = True
    icon_info.hbmMask = mask_bitmap
    icon_info.hbmColor = color_bitmap
    icon_handle = user32.CreateIconIndirect(ctypes.byref(icon_info))

    gdi32.DeleteObject(border_pen)
    gdi32.DeleteObject(fill_brush)
    gdi32.DeleteObject(background_brush)
    gdi32.DeleteObject(mask_bitmap)
    gdi32.DeleteObject(color_bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(None, screen_dc)

    if not icon_handle:
        raise OSError("无法生成托盘图标句柄")

    return icon_handle


def describe_error(exc):
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, URLError):
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError):
            return "超时"
        return str(reason)
    if isinstance(exc, TimeoutError):
        return "超时"
    return str(exc)


def test_site(site):
    started = time.perf_counter()
    request = Request(
        site["url"],
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Cache-Control": "no-cache",
        },
        method="GET",
    )

    try:
        context = ssl.create_default_context()
        with urlopen(request, timeout=TIMEOUT_SECONDS, context=context) as response:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            status = response.getcode()
            return site["name"], True, elapsed_ms, f"HTTP {status}"
    except HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return site["name"], True, elapsed_ms, f"HTTP {exc.code}，服务器已响应"
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return site["name"], False, elapsed_ms, describe_error(exc)


class PingPong(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PingPong")
        self.geometry("760x470")
        self.minsize(700, 430)
        self.configure(bg=UI["bg"])

        self.rows = {}
        self.testing = False
        self.animation_tick = 0
        self.summary_state = "待检测"
        self.summary_color = UI["brand"]
        self.current_results = {}
        self.last_auto_status = {site["name"]: None for site in SITES}
        self.notification_ready = False
        self.tray_class_name = f"PingPongTrayWindow{id(self)}"
        self.tray_hwnd = None
        self.tray_ready = threading.Event()
        self.tray_events = queue.Queue()
        self.tray_thread = None
        self.exiting = False
        self.tray_hint_shown = False
        self.tray_icons = {}
        self.current_tray_state = "idle"
        self.auto_enabled = tk.BooleanVar(value=False)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(SITES))

        self._build_styles()
        self._build_ui()
        self._build_tray_menu()
        self._create_tray_message_window()
        self._create_tray_icons()
        self._init_notification_icon()
        self._process_tray_events()
        self._animate_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Root.TFrame", background=UI["bg"])

    def _build_ui(self):
        self.backdrop = tk.Canvas(self, bg=UI["bg"], highlightthickness=0)
        self.backdrop.pack(fill="both", expand=True)
        self.backdrop.bind("<Configure>", self._resize_backdrop)

        root = tk.Frame(self.backdrop, bg=UI["bg"])
        self.backdrop_window = self.backdrop.create_window(0, 0, anchor="nw", window=root)

        shell = tk.Frame(root, bg=UI["bg"], padx=22, pady=16)
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, bg=UI["bg"])
        header.pack(fill="x")

        title_block = tk.Frame(header, bg=UI["bg"])
        title_block.pack(side="left", fill="x", expand=True)

        tk.Label(
            title_block,
            text="PingPong",
            bg=UI["bg"],
            fg=UI["text"],
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")

        header_meta = tk.Frame(title_block, bg=UI["bg"])
        header_meta.pack(anchor="w", pady=(4, 0))
        tk.Label(
            header_meta,
            text="HTTPS",
            bg=UI["bg"],
            fg=UI["brand_deep"],
            font=("Consolas", 8, "bold"),
        ).pack(side="left")
        tk.Label(
            header_meta,
            text="  并发检测 YouTube、ChatGPT、Claude",
            bg=UI["bg"],
            fg=UI["muted"],
            font=("Microsoft YaHei UI", 8),
        ).pack(side="left")

        self.summary_card = tk.Frame(header, bg=UI["brand_soft"], padx=1, pady=1)
        self.summary_card.pack(side="right", padx=(18, 0), pady=(2, 0))
        self.summary_label = tk.Label(
            self.summary_card,
            text="待检测",
            bg=UI["brand_soft"],
            fg=UI["brand_deep"],
            padx=16,
            pady=6,
            font=("Segoe UI", 9, "bold"),
        )
        self.summary_label.pack()

        controls = tk.Frame(shell, bg=UI["bg"])
        controls.pack(fill="x", pady=(16, 0))

        self.test_button = tk.Button(
            controls,
            text="立即检测",
            command=self.run_tests,
            bg=UI["panel_hot"],
            fg=UI["bg"],
            activebackground="#232323",
            activeforeground=UI["bg"],
            disabledforeground="#f5f5f5",
            relief="flat",
            bd=0,
            padx=22,
            pady=8,
            cursor="hand2",
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        self.test_button.pack(side="left")

        self.auto_toggle = tk.Canvas(
            controls,
            width=36,
            height=20,
            bg=UI["bg"],
            highlightthickness=0,
            cursor="hand2",
        )
        self.auto_toggle.pack(side="left", padx=(18, 7))
        self.auto_toggle.bind("<Button-1>", self._toggle_auto)
        self.auto_label = tk.Label(
            controls,
            text=f"{AUTO_INTERVAL_SECONDS}s 自动检测",
            bg=UI["bg"],
            fg=UI["muted"],
            cursor="hand2",
            font=("Microsoft YaHei UI", 9),
        )
        self.auto_label.pack(side="left")
        self.auto_label.bind("<Button-1>", self._toggle_auto)

        self.last_test_label = tk.Label(
            controls,
            text="尚未检测",
            bg=UI["bg"],
            fg=UI["dim"],
            font=("Microsoft YaHei UI", 9),
        )
        self.last_test_label.pack(side="right")

        card_deck = tk.Frame(shell, bg=UI["bg"])
        card_deck.pack(fill="both", expand=True, pady=(18, 0))

        for index, site in enumerate(SITES):
            self._add_site_row(card_deck, site["name"], index)

        footer = tk.Frame(shell, bg=UI["bg"])
        footer.pack(fill="x", pady=(14, 0))
        self.footer_dot = tk.Canvas(footer, width=10, height=10, bg=UI["bg"], highlightthickness=0)
        self.footer_dot.pack(side="left", padx=(1, 7), pady=(2, 0))
        self.footer_label = tk.Label(
            footer,
            text="关闭窗口后仍可从系统托盘打开",
            bg=UI["bg"],
            fg=UI["dim"],
            font=("Microsoft YaHei UI", 8),
        )
        self.footer_label.pack(side="left")
        self._draw_toggle()

    def _resize_backdrop(self, event):
        self.backdrop.itemconfigure(self.backdrop_window, width=event.width, height=event.height)
        self._draw_backdrop()

    def _draw_backdrop(self):
        if not hasattr(self, "backdrop"):
            return

        width = max(self.backdrop.winfo_width(), 1)
        height = max(self.backdrop.winfo_height(), 1)
        self.backdrop.delete("bg")

        drift = int(math.sin(self.animation_tick / 26) * 18)
        self.backdrop.create_rectangle(0, 0, width, height, fill=UI["bg"], outline="", tags="bg")
        self.backdrop.create_oval(width - 320 + drift, -180, width + 120 + drift, 240, fill=UI["wash"], outline="", tags="bg")
        self.backdrop.create_oval(-160 - drift, height - 260, 270 - drift, height + 140, fill="#f8fffb", outline="", tags="bg")
        self.backdrop.create_line(32, 126, width - 32, 126, fill="#efefef", tags="bg")
        self.backdrop.tag_lower("bg")

    def _animate_ui(self):
        if self.exiting:
            return

        self.animation_tick += 1
        self._draw_backdrop()

        pulse = (math.sin(self.animation_tick / 6) + 1) / 2
        for row in self.rows.values():
            canvas = row["canvas"]
            color = row["color"]
            state = row["state"]
            canvas.delete("all")
            canvas.create_oval(7, 7, 41, 41, outline="#eeeeee", width=1)
            if state == "wait":
                halo = 3 + int(pulse * 4)
                canvas.create_oval(7 - halo, 7 - halo, 41 + halo, 41 + halo, outline=UI["amber"], width=1)
                canvas.create_arc(7, 7, 41, 41, start=self.animation_tick * 10, extent=100, outline=UI["amber"], width=3)
            else:
                canvas.create_oval(11, 11, 37, 37, fill=self._status_surface(state), outline="")
            canvas.create_oval(17, 17, 31, 31, fill=color, outline="")

        if hasattr(self, "footer_dot"):
            self.footer_dot.delete("all")
            self.footer_dot.create_oval(1, 1, 9, 9, fill=self.summary_color, outline="")

        if hasattr(self, "summary_card"):
            if self.testing:
                color = UI["brand"] if self.animation_tick % 12 < 6 else UI["brand_deep"]
                self.summary_card.configure(bg=UI["brand_soft"])
                self.summary_label.configure(fg=color)
            else:
                self.summary_card.configure(bg=self._summary_surface(self.summary_color))
                self.summary_label.configure(fg=self.summary_color)
                self.summary_label.configure(bg=self._summary_surface(self.summary_color))

        self._draw_toggle()
        self.after(60, self._animate_ui)

    def _status_color(self, status_style):
        return {
            "good": UI["green"],
            "bad": UI["red"],
            "wait": UI["amber"],
            "idle": UI["brand"],
        }.get(status_style, UI["brand"])

    def _status_surface(self, status_style):
        return {
            "good": UI["brand_soft"],
            "bad": UI["red_soft"],
            "wait": UI["amber_soft"],
            "idle": UI["surface"],
        }.get(status_style, UI["surface"])

    def _set_summary(self, text, color):
        self.summary_state = text
        self.summary_color = color
        self.summary_label.configure(text=text, fg=color)
        self.summary_card.configure(bg=self._summary_surface(color))
        self.summary_label.configure(bg=self._summary_surface(color))

    def _summary_surface(self, color):
        if color == UI["red"]:
            return UI["red_soft"]
        if color == UI["amber"]:
            return UI["amber_soft"]
        return UI["brand_soft"]

    def _build_tray_menu(self):
        self.tray_menu = tk.Menu(self, tearoff=0)
        self.tray_menu.add_command(label="打开 PingPong", command=self.show_window)
        self.tray_menu.add_separator()
        self.tray_menu.add_command(label="退出", command=self.exit_app)

    def _draw_toggle(self):
        if not hasattr(self, "auto_toggle"):
            return

        enabled = self.auto_enabled.get()
        fill = UI["brand"] if enabled else "#ededed"
        knob = UI["text"] if enabled else "#ffffff"
        outline = UI["brand"] if enabled else UI["border"]
        self.auto_toggle.delete("all")
        self.auto_toggle.create_rectangle(10, 1, 26, 19, fill=fill, outline=outline)
        self.auto_toggle.create_oval(1, 1, 19, 19, fill=fill, outline=outline)
        self.auto_toggle.create_oval(17, 1, 35, 19, fill=fill, outline=outline)
        x = 20 if enabled else 2
        self.auto_toggle.create_oval(x, 2, x + 16, 18, fill=knob, outline="")
        self.auto_label.configure(fg=UI["text"] if enabled else UI["muted"])

    def _toggle_auto(self, _event=None):
        self.auto_enabled.set(not self.auto_enabled.get())
        self._auto_toggled()

    def _add_site_row(self, parent, name, index):
        border = tk.Frame(parent, bg=UI["border"], padx=1, pady=1)
        border.pack(side="left", fill="both", expand=True, padx=(0 if index == 0 else 8, 0 if index == len(SITES) - 1 else 8))

        card = tk.Frame(border, bg=UI["panel_2"], padx=14, pady=13)
        card.pack(fill="both", expand=True)

        accent = tk.Frame(card, bg=UI["brand"], height=4)
        accent.pack(fill="x", pady=(0, 13))

        top = tk.Frame(card, bg=UI["panel_2"])
        top.pack(fill="x")

        site_label = tk.Label(
            top,
            text=name,
            bg=UI["panel_2"],
            fg=UI["text"],
            anchor="w",
            font=("Segoe UI", 12, "bold"),
        )
        site_label.pack(side="left", fill="x", expand=True)

        status_badge = tk.Frame(top, bg=UI["surface"], padx=1, pady=1)
        status_badge.pack(side="right")
        status = tk.Label(
            status_badge,
            text="待检测",
            bg=UI["surface"],
            fg=UI["muted"],
            width=7,
            padx=4,
            pady=2,
            font=("Consolas", 8, "bold"),
        )
        status.pack()

        orb = tk.Canvas(card, width=48, height=48, bg=UI["panel_2"], highlightthickness=0)
        orb.pack(anchor="w", pady=(20, 9))

        latency = tk.Label(
            card,
            text="-",
            bg=UI["panel_2"],
            fg=UI["text"],
            anchor="w",
            font=("Consolas", 22, "bold"),
        )
        latency.pack(fill="x")

        latency_label = tk.Label(
            card,
            text="ms / 响应时间",
            bg=UI["panel_2"],
            fg=UI["faint"],
            anchor="w",
            font=("Microsoft YaHei UI", 8),
        )
        latency_label.pack(fill="x", pady=(1, 14))

        detail = tk.Label(
            card,
            text="等待测试",
            bg=UI["panel_2"],
            fg=UI["muted"],
            justify="left",
            anchor="w",
            font=("Microsoft YaHei UI", 8),
            wraplength=175,
        )
        detail.pack(fill="x", side="bottom")

        self.rows[name] = {
            "border": border,
            "card": card,
            "accent": accent,
            "canvas": orb,
            "site": site_label,
            "status_badge": status_badge,
            "status": status,
            "latency": latency,
            "latency_label": latency_label,
            "detail": detail,
            "state": "idle",
            "color": UI["brand"],
        }

    def run_tests(self):
        if self.testing:
            return

        self.testing = True
        self.current_results = {}
        self._set_summary("检测中", UI["brand_deep"])
        self.test_button.configure(state="disabled", text="检测中...")
        for site in SITES:
            self._set_row(site["name"], "检测中", "wait", "-", "正在连接")

        thread = threading.Thread(target=self._run_tests_in_background, daemon=True)
        thread.start()

    def _run_tests_in_background(self):
        futures = [self.executor.submit(test_site, site) for site in SITES]
        for future in concurrent.futures.as_completed(futures):
            name, ok, elapsed_ms, detail = future.result()
            self.after(0, self._show_result, name, ok, elapsed_ms, detail)

        self.after(0, self._finish_tests)

    def _show_result(self, name, ok, elapsed_ms, detail):
        self.current_results[name] = ok
        if ok:
            self._set_row(name, "可访问", "good", f"{elapsed_ms}", detail)
        else:
            self._set_row(name, "不可访问", "bad", f"{elapsed_ms}", detail)

    def _set_row(self, name, status_text, status_style, latency_text, detail_text):
        row = self.rows[name]
        color = self._status_color(status_style)
        row["state"] = status_style
        row["color"] = color
        border = color if status_style in {"wait", "bad"} else UI["border"]
        row["border"].configure(bg=border)
        row["accent"].configure(bg=color)
        surface = self._status_surface(status_style)
        row["status_badge"].configure(bg=surface)
        row["status"].configure(text=status_text, fg=color, bg=surface)
        row["latency"].configure(text=latency_text, fg=UI["text"])
        row["detail"].configure(text=detail_text)

    def _finish_tests(self):
        self.testing = False
        self.test_button.configure(state="normal", text="立即检测")
        self.last_test_label.configure(text=f"上次检测：{datetime.now().strftime('%H:%M:%S')}")
        state = self._resolve_tray_state()
        if state == "good":
            self._set_summary("全部可访问", UI["brand_deep"])
        elif state == "bad":
            self._set_summary("全部不可访问", UI["red"])
        elif state == "partial":
            self._set_summary("部分可访问", UI["amber"])
        else:
            self._set_summary("待检测", UI["brand"])
        self._update_tray_icon()
        if self.auto_enabled.get():
            self._notify_auto_status_changes()
            self.after(AUTO_INTERVAL_SECONDS * 1000, self._auto_run)

    def _auto_toggled(self):
        if self.auto_enabled.get() and not self.testing:
            self.run_tests()

    def _auto_run(self):
        if self.auto_enabled.get() and not self.testing:
            self.run_tests()

    def _create_tray_icons(self):
        self.tray_icons = {}
        for state, color in TRAY_STATUS_COLORS.items():
            try:
                self.tray_icons[state] = _create_status_icon(color)
            except Exception:
                self.tray_icons = {}
                break

        if not self.tray_icons:
            ctypes.windll.user32.LoadIconW.restype = ctypes.c_void_p
            self.tray_icons["idle"] = ctypes.windll.user32.LoadIconW(None, IDI_APPLICATION)

        self.current_tray_state = "idle"

    def _get_tray_icon(self, state=None):
        state = state or self.current_tray_state
        return self.tray_icons.get(state) or self.tray_icons.get("idle")

    def _resolve_tray_state(self):
        completed = [self.current_results.get(site["name"]) for site in SITES]
        completed = [status for status in completed if status is not None]
        if len(completed) != len(SITES):
            return "idle"
        if all(completed):
            return "good"
        if not any(completed):
            return "bad"
        return "partial"

    def _update_tray_icon(self, state=None):
        state = state or self._resolve_tray_state()
        icon_handle = self._get_tray_icon(state)
        if not icon_handle:
            return

        self.current_tray_state = state
        if not self.notification_ready:
            return

        try:
            hwnd = ctypes.c_void_p(self.tray_hwnd or self.winfo_id())
            data = _build_notify_data(hwnd, icon_handle)
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data))
        except Exception:
            self.notification_ready = False

    def _init_notification_icon(self):
        try:
            hwnd = ctypes.c_void_p(self.tray_hwnd or self.winfo_id())
            data = _build_notify_data(hwnd, self._get_tray_icon("idle"))
            self.notification_ready = bool(ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)))
        except Exception:
            self.notification_ready = False

    def _create_tray_message_window(self):
        self.tray_thread = threading.Thread(target=self._tray_message_loop, daemon=True)
        self.tray_thread.start()
        self.tray_ready.wait(timeout=2)

    def _tray_message_loop(self):
        try:
            hinstance = win32gui.GetModuleHandle(None)
            wndclass = win32gui.WNDCLASS()
            wndclass.hInstance = hinstance
            wndclass.lpszClassName = self.tray_class_name
            wndclass.lpfnWndProc = self._handle_tray_window_message

            try:
                win32gui.RegisterClass(wndclass)
            except win32gui.error:
                pass

            self.tray_hwnd = win32gui.CreateWindow(
                self.tray_class_name,
                self.tray_class_name,
                0,
                0,
                0,
                0,
                0,
                None,
                None,
                hinstance,
                None,
            )
        finally:
            self.tray_ready.set()

        if self.tray_hwnd:
            win32gui.PumpMessages()

    def _handle_tray_window_message(self, hwnd, message, wparam, lparam):
        if message == WM_TRAY_NOTIFY:
            if lparam == WM_LBUTTONDBLCLK:
                self.tray_events.put("show")
                return 0
            if lparam == WM_RBUTTONUP:
                self.tray_events.put("menu")
                return 0

        if message == WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0

        return win32gui.DefWindowProc(hwnd, message, wparam, lparam)

    def _process_tray_events(self):
        while True:
            try:
                event = self.tray_events.get_nowait()
            except queue.Empty:
                break

            if event == "show":
                self.show_window()
            elif event == "menu":
                self._show_tray_menu()

        if not self.exiting:
            self.after(50, self._process_tray_events)

    def _show_tray_menu(self):
        point = POINT()
        ctypes.windll.user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
        ctypes.windll.user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(self.winfo_id()))
        try:
            self.tray_menu.tk_popup(point.x, point.y)
        finally:
            self.tray_menu.grab_release()

    def _show_windows_notification(self, title, message, warning=False):
        if not ENABLE_WINDOWS_NOTIFICATIONS:
            return

        if not self.notification_ready:
            return

        try:
            hwnd = ctypes.c_void_p(self.tray_hwnd or self.winfo_id())
            info_flags = NIIF_WARNING if warning else NIIF_INFO
            data = _build_notify_data(hwnd, self._get_tray_icon(), title, message, info_flags)
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data))
        except Exception:
            self.notification_ready = False

    def _notify_auto_status_changes(self):
        disconnected = []
        recovered = []

        for site in SITES:
            name = site["name"]
            ok = self.current_results.get(name)
            previous = self.last_auto_status.get(name)

            if ok is False and previous is not False:
                disconnected.append(name)
            elif ok is True and previous is False:
                recovered.append(name)

            if ok is not None:
                self.last_auto_status[name] = ok

        if disconnected or recovered:
            messages = []
            if disconnected:
                messages.append("断开：" + "、".join(disconnected))
            if recovered:
                messages.append("恢复：" + "、".join(recovered))

            self._show_windows_notification(
                "PingPong：连接状态变化",
                "；".join(messages),
                warning=bool(disconnected),
            )

    def show_window(self):
        self.state("normal")
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(self.winfo_id()))
        except Exception:
            pass

    def close(self):
        self.withdraw()
        if not self.tray_hint_shown:
            self.tray_hint_shown = True
            self._show_windows_notification(
                "PingPong 仍在运行",
                "双击右下角小图标可打开界面，右键可退出。",
            )

    def exit_app(self):
        self.exiting = True
        if self.notification_ready:
            try:
                hwnd = ctypes.c_void_p(self.tray_hwnd or self.winfo_id())
                data = _build_notify_data(hwnd, self._get_tray_icon())
                ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
            except Exception:
                pass
        if self.tray_hwnd:
            try:
                win32gui.PostMessage(self.tray_hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass
            self.tray_hwnd = None
        for state, icon_handle in self.tray_icons.items():
            if icon_handle and not (state == "idle" and len(self.tray_icons) == 1):
                try:
                    ctypes.windll.user32.DestroyIcon(ctypes.c_void_p(icon_handle))
                except Exception:
                    pass
        self.tray_icons = {}
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.destroy()


if __name__ == "__main__":
    app = PingPong()
    app.mainloop()
