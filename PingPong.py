import concurrent.futures
import ssl
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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
        self.geometry("680x390")
        self.minsize(620, 360)
        self.configure(bg="#f5f7fa")

        self.rows = {}
        self.testing = False
        self.auto_enabled = tk.BooleanVar(value=False)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(SITES))

        self._build_styles()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Root.TFrame", background="#f5f7fa")
        style.configure("Header.TLabel", background="#f5f7fa", foreground="#172033", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Sub.TLabel", background="#f5f7fa", foreground="#5c667a", font=("Microsoft YaHei UI", 10))
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("Site.TLabel", background="#ffffff", foreground="#172033", font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("Value.TLabel", background="#ffffff", foreground="#172033", font=("Microsoft YaHei UI", 12))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#697386", font=("Microsoft YaHei UI", 10))
        style.configure("Good.TLabel", background="#ffffff", foreground="#12805c", font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("Bad.TLabel", background="#ffffff", foreground="#b42318", font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("Wait.TLabel", background="#ffffff", foreground="#8a5a00", font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 11, "bold"), padding=(18, 8))
        style.configure("TCheckbutton", background="#f5f7fa", foreground="#172033", font=("Microsoft YaHei UI", 10))

    def _build_ui(self):
        root = ttk.Frame(self, style="Root.TFrame", padding=22)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="PingPong", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            root,
            text="点击一次即可并发测试 YouTube、ChatGPT、Claude 的 HTTPS 连通延迟。",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(4, 18))

        card = ttk.Frame(root, style="Card.TFrame", padding=(18, 10))
        card.pack(fill="both", expand=True)

        for site in SITES:
            self._add_site_row(card, site["name"])

        controls = ttk.Frame(root, style="Root.TFrame")
        controls.pack(fill="x", pady=(18, 0))

        self.test_button = ttk.Button(controls, text="同时测试", style="Primary.TButton", command=self.run_tests)
        self.test_button.pack(side="left")

        ttk.Checkbutton(
            controls,
            text=f"自动每 {AUTO_INTERVAL_SECONDS} 秒测试",
            variable=self.auto_enabled,
            command=self._auto_toggled,
        ).pack(side="left", padx=(16, 0))

        self.last_test_label = ttk.Label(controls, text="还没有测试", style="Sub.TLabel")
        self.last_test_label.pack(side="right")

    def _add_site_row(self, parent, name):
        row = ttk.Frame(parent, style="Card.TFrame", padding=(0, 10))
        row.pack(fill="x")

        ttk.Label(row, text=name, style="Site.TLabel", width=12).pack(side="left")

        status = ttk.Label(row, text="待测试", style="Muted.TLabel", width=12)
        status.pack(side="left", padx=(12, 0))

        latency = ttk.Label(row, text="-", style="Value.TLabel", width=12)
        latency.pack(side="left", padx=(12, 0))

        detail = ttk.Label(row, text="", style="Muted.TLabel")
        detail.pack(side="left", padx=(12, 0), fill="x", expand=True)

        self.rows[name] = {
            "status": status,
            "latency": latency,
            "detail": detail,
        }

    def run_tests(self):
        if self.testing:
            return

        self.testing = True
        self.test_button.configure(state="disabled", text="测试中...")
        for site in SITES:
            self._set_row(site["name"], "测试中", "Wait.TLabel", "-", "正在连接")

        thread = threading.Thread(target=self._run_tests_in_background, daemon=True)
        thread.start()

    def _run_tests_in_background(self):
        futures = [self.executor.submit(test_site, site) for site in SITES]
        for future in concurrent.futures.as_completed(futures):
            name, ok, elapsed_ms, detail = future.result()
            self.after(0, self._show_result, name, ok, elapsed_ms, detail)

        self.after(0, self._finish_tests)

    def _show_result(self, name, ok, elapsed_ms, detail):
        if ok:
            self._set_row(name, "可连通", "Good.TLabel", f"{elapsed_ms} ms", detail)
        else:
            self._set_row(name, "不可访问", "Bad.TLabel", f"{elapsed_ms} ms", detail)

    def _set_row(self, name, status_text, status_style, latency_text, detail_text):
        row = self.rows[name]
        row["status"].configure(text=status_text, style=status_style)
        row["latency"].configure(text=latency_text)
        row["detail"].configure(text=detail_text)

    def _finish_tests(self):
        self.testing = False
        self.test_button.configure(state="normal", text="同时测试")
        self.last_test_label.configure(text=f"上次测试：{datetime.now().strftime('%H:%M:%S')}")
        if self.auto_enabled.get():
            self.after(AUTO_INTERVAL_SECONDS * 1000, self._auto_run)

    def _auto_toggled(self):
        if self.auto_enabled.get() and not self.testing:
            self.run_tests()

    def _auto_run(self):
        if self.auto_enabled.get() and not self.testing:
            self.run_tests()

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.destroy()


if __name__ == "__main__":
    app = PingPong()
    app.mainloop()
