from __future__ import annotations

import logging
import queue
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app_constants import DEFAULT_NEWS_TYPE, DEFAULT_TOPIC, VALID_SEARCH_PROVIDERS
from config import load_config
from launcher import run_pipeline
from utils.logger import get_logger


class _QueueLogHandler(logging.Handler):
    def __init__(self, event_queue: queue.Queue[tuple[str, str]]) -> None:
        super().__init__()
        self.event_queue = event_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self.event_queue.put(("log", message))
        except Exception:
            self.handleError(record)


class LauncherApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("WeChat Education Agent Launcher")
        self.root.geometry("920x680")
        self.root.minsize(820, 600)

        self.config = load_config()
        self.logger = get_logger()
        self.event_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self.log_handler: _QueueLogHandler | None = None

        self.manual_news_var = tk.StringVar(value="")
        self.search_provider_var = tk.StringVar(value=self.config.search_provider)
        self.topic_var = tk.StringVar(value=DEFAULT_TOPIC)
        self.news_type_var = tk.StringVar(value=DEFAULT_NEWS_TYPE)
        self.status_var = tk.StringVar(value="Ready.")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.root.configure(bg="#101826")

        container = ttk.Frame(self.root, padding=18)
        container.pack(fill="both", expand=True)

        title_frame = ttk.Frame(container)
        title_frame.pack(fill="x", pady=(0, 14))

        title_label = ttk.Label(title_frame, text="WeChat Education Agent", font=("Segoe UI", 18, "bold"))
        title_label.pack(anchor="w")

        subtitle = ttk.Label(
            title_frame,
            text="Fill in the parameters and run the existing pipeline with live logs.",
        )
        subtitle.pack(anchor="w", pady=(4, 0))

        form = ttk.LabelFrame(container, text="Launch Parameters", padding=14)
        form.pack(fill="x")

        form.columnconfigure(1, weight=1)

        self._add_row(
            form,
            0,
            "Search provider",
            self._build_provider_widget(form),
        )
        self._add_row(
            form,
            1,
            "Manual news file",
            self._build_manual_file_widget(form),
        )
        self._add_row(
            form,
            2,
            "Topic",
            self._build_entry_widget(form, self.topic_var),
        )
        self._add_row(
            form,
            3,
            "News type",
            self._build_entry_widget(form, self.news_type_var),
        )

        button_row = ttk.Frame(container)
        button_row.pack(fill="x", pady=(12, 10))

        self.run_button = ttk.Button(button_row, text="Run Pipeline", command=self._start_run)
        self.run_button.pack(side="left")

        self.status_label = ttk.Label(button_row, textvariable=self.status_var)
        self.status_label.pack(side="left", padx=(14, 0))

        log_frame = ttk.LabelFrame(container, text="Live Logs", padding=10)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, wrap="word", height=20, state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self._append_log("GUI ready. Configure the fields and click Run Pipeline.")

    def _build_provider_widget(self, parent: ttk.Frame) -> ttk.Combobox:
        combo = ttk.Combobox(
            parent,
            textvariable=self.search_provider_var,
            values=VALID_SEARCH_PROVIDERS,
            state="readonly",
        )
        return combo

    def _build_manual_file_widget(self, parent: ttk.Frame) -> ttk.Frame:
        frame = ttk.Frame(parent)
        entry = ttk.Entry(frame, textvariable=self.manual_news_var)
        entry.pack(side="left", fill="x", expand=True)

        browse_button = ttk.Button(frame, text="Browse", command=self._browse_manual_file)
        browse_button.pack(side="left", padx=(8, 0))
        return frame

    def _build_entry_widget(self, parent: ttk.Frame, variable: tk.StringVar) -> ttk.Entry:
        return ttk.Entry(parent, textvariable=variable)

    def _add_row(self, parent: ttk.Frame, row: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
        widget.grid(row=row, column=1, sticky="ew", pady=6)

    def _browse_manual_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select manual news file",
            filetypes=[("Text files", "*.txt *.md *.markdown"), ("All files", "*.*")],
        )
        if selected:
            self.manual_news_var.set(selected)

    def _start_run(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("Running", "The pipeline is already running.")
            return

        provider = self.search_provider_var.get().strip().lower()
        topic = self.topic_var.get().strip()
        news_type = self.news_type_var.get().strip()
        manual_text = self.manual_news_var.get().strip()
        manual_path = Path(manual_text) if manual_text else None

        if provider not in VALID_SEARCH_PROVIDERS:
            messagebox.showerror("Invalid provider", f"Provider must be one of: {', '.join(VALID_SEARCH_PROVIDERS)}")
            return

        if provider == "manual" and not manual_path:
            messagebox.showerror("Missing file", "Please choose a manual news file when provider is manual.")
            return

        if manual_path and not manual_path.exists():
            messagebox.showerror("File not found", f"Manual news file not found: {manual_path}")
            return

        if not topic:
            messagebox.showerror("Missing topic", "Please enter a topic.")
            return

        if not news_type:
            messagebox.showerror("Missing news type", "Please enter a news type.")
            return

        self._install_log_handler()
        self._set_running_state(True)
        self.status_var.set("Running pipeline...")
        self._append_log("")
        self._append_log(f"Starting run: provider={provider}, topic={topic}, news_type={news_type}")

        self.worker_thread = threading.Thread(
            target=self._run_worker,
            args=(manual_path, provider, topic, news_type),
            daemon=True,
        )
        self.worker_thread.start()
        self.root.after(100, self._poll_events)

    def _run_worker(
        self,
        manual_path: Path | None,
        provider: str,
        topic: str,
        news_type: str,
    ) -> None:
        try:
            output_dir = run_pipeline(
                config=self.config,
                manual_path=manual_path,
                provider_name=provider,
                topic=topic,
                news_type=news_type,
            )
            self.event_queue.put(("done", str(output_dir)))
        except Exception as exc:
            details = traceback.format_exc().strip()
            self.event_queue.put(("error", f"{exc}\n\n{details}"))

    def _install_log_handler(self) -> None:
        if self.log_handler:
            self.logger.removeHandler(self.log_handler)

        handler = _QueueLogHandler(self.event_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        self.logger.addHandler(handler)
        self.log_handler = handler

    def _remove_log_handler(self) -> None:
        if self.log_handler:
            self.logger.removeHandler(self.log_handler)
            self.log_handler = None

    def _poll_events(self) -> None:
        while True:
            try:
                event_type, payload = self.event_queue.get_nowait()
            except queue.Empty:
                break

            if event_type == "log":
                self._append_log(payload)
                continue

            self._set_running_state(False)
            self._remove_log_handler()

            if event_type == "done":
                self.status_var.set(f"Done. Output: {payload}")
                self._append_log(f"Run completed. Output directory: {payload}")
                messagebox.showinfo("Completed", f"Pipeline finished successfully.\n\nOutput: {payload}")
            else:
                self.status_var.set("Run failed.")
                self._append_log(payload)
                messagebox.showerror("Run failed", payload)
            return

        if self.worker_thread and self.worker_thread.is_alive():
            self.root.after(100, self._poll_events)
        else:
            self._remove_log_handler()
            self._set_running_state(False)

    def _set_running_state(self, running: bool) -> None:
        self.run_button.configure(state="disabled" if running else "normal")

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        if text:
            self.log_text.insert("end", text + "\n")
        else:
            self.log_text.insert("end", "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        self._remove_log_handler()
        self.root.destroy()


def launch_gui() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    LauncherApp(root)
    root.mainloop()