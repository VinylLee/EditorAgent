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
    """
    自定义日志处理器，将日志消息发送到队列中
    
    该处理器继承自logging.Handler，用于将日志记录添加到指定的事件队列中，
    以便在GUI线程中安全地显示日志信息。
    
    Attributes:
        event_queue (queue.Queue): 存储日志事件的队列
    """

    def __init__(self, event_queue: queue.Queue[tuple[str, str]]) -> None:
        """
        初始化队列日志处理器
        
        Args:
            event_queue: 用于传递日志事件的队列对象
        """
        super().__init__()
        self.event_queue = event_queue

    def emit(self, record: logging.LogRecord) -> None:
        """
        发送日志记录到队列
        
        将格式化的日志记录放入事件队列中，如果发生异常则调用错误处理方法
        
        Args:
            record: 日志记录对象
        """
        try:
            # 格式化日志记录并将其放入队列
            message = self.format(record)
            self.event_queue.put(("log", message))
        except Exception:
            # 如果出现异常，调用错误处理方法
            self.handleError(record)


class LauncherApp:
    """
    微信教育代理启动器应用程序类
    
    这个类实现了微信教育代理的图形用户界面，允许用户配置参数并运行处理管道，
    同时实时显示日志信息。
    
    Attributes:
        root: Tkinter根窗口对象
        config: 应用程序配置对象
        logger: 日志记录器实例
        event_queue: 用于线程间通信的事件队列
        worker_thread: 工作线程对象
        log_handler: 队列日志处理器实例
        manual_news_var: 手动新闻文件路径的字符串变量
        search_provider_var: 搜索提供者的字符串变量
        topic_var: 主题的字符串变量
        news_type_var: 新闻类型的字符串变量
        status_var: 状态信息的字符串变量
    """

    def __init__(self, root: tk.Tk) -> None:
        """
        初始化启动器应用程序
        
        设置窗口属性、加载配置、初始化组件变量，并构建用户界面
        
        Args:
            root: Tkinter根窗口对象
        """
        self.root = root
        # 设置窗口标题为中文
        self.root.title("微信教育代理启动器")
        # 设置窗口大小
        self.root.geometry("920x680")
        # 设置最小窗口尺寸
        self.root.minsize(820, 600)

        # 加载应用程序配置
        self.config = load_config()
        # 获取日志记录器实例
        self.logger = get_logger()
        # 创建用于线程间通信的事件队列
        self.event_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        # 初始化工作线程引用
        self.worker_thread: threading.Thread | None = None
        # 初始化日志处理器引用
        self.log_handler: _QueueLogHandler | None = None
        # 初始化手动新闻文件组件引用
        self.manual_file_entry: ttk.Entry | None = None
        self.manual_file_button: ttk.Button | None = None

        # 初始化各种字符串变量，用于存储用户输入
        self.manual_news_var = tk.StringVar(value="")
        self.search_provider_var = tk.StringVar(value=self.config.search_provider)
        self.topic_var = tk.StringVar(value=DEFAULT_TOPIC)
        self.news_type_var = tk.StringVar(value=DEFAULT_NEWS_TYPE)
        # 初始化状态变量，显示当前应用状态
        self.status_var = tk.StringVar(value="就绪")

        # 构建用户界面
        self._build_ui()
        # 设置窗口关闭协议，确保清理资源
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 绑定搜索提供者变化事件，用于控制手动新闻文件输入框的可用性
        self.search_provider_var.trace_add("write", self._on_search_provider_change)

    def _on_search_provider_change(self, *args) -> None:
        """
        搜索提供者变化事件处理函数
        
        当搜索提供者发生变化时，根据其值启用或禁用手动新闻文件输入框
        """
        provider = self.search_provider_var.get().strip().lower()
        if provider == "manual":
            # 如果选择手动模式，启用手动新闻文件输入框
            self._enable_manual_file_widgets(True)
        else:
            # 如果选择其他模式，禁用手动新闻文件输入框并清空内容
            self._enable_manual_file_widgets(False)
            self.manual_news_var.set("")

    def _enable_manual_file_widgets(self, enabled: bool) -> None:
        """
        启用或禁用手动新闻文件相关组件
        
        Args:
            enabled: 是否启用相关组件
        """
        # 设置输入框和按钮的状态
        if self.manual_file_entry:
            self.manual_file_entry.config(state="normal" if enabled else "disabled")
        if self.manual_file_button:
            self.manual_file_button.config(state="normal" if enabled else "disabled")



    def _build_ui(self) -> None:
        """
        构建应用程序用户界面
        
        创建和布局所有GUI组件，包括标题、参数表单、按钮和日志显示区域
        """
        # 设置窗口背景颜色
        self.root.configure(bg="#101826")

        # 创建主容器框架
        container = ttk.Frame(self.root, padding=18)
        container.pack(fill="both", expand=True)

        # 创建标题框架
        title_frame = ttk.Frame(container)
        title_frame.pack(fill="x", pady=(0, 14))

        # 创建主标题标签
        title_label = ttk.Label(title_frame, text="微信教育代理", font=("Segoe UI", 18, "bold"))
        title_label.pack(anchor="w")

        # 创建副标题标签
        subtitle = ttk.Label(
            title_frame,
            text="填写参数并运行现有工作流，实时查看日志。",
        )
        subtitle.pack(anchor="w", pady=(4, 0))

        # 创建参数设置分组框
        form = ttk.LabelFrame(container, text="启动参数", padding=14)
        form.pack(fill="x")

        # 配置表单网格的列权重
        form.columnconfigure(1, weight=1)

        # 添加搜索提供者选择行
        self._add_row(
            form,
            0,
            "搜索提供者",
            self._build_provider_widget(form),
        )
        # 添加手动新闻文件选择行
        manual_file_widget = self._build_manual_file_widget(form)
        self._add_row(
            form,
            1,
            "手动新闻文件",
            manual_file_widget,
        )

        # 添加主题输入行
        self._add_row(
            form,
            2,
            "主题",
            self._build_entry_widget(form, self.topic_var),
        )
        # 添加新闻类型输入行
        self._add_row(
            form,
            3,
            "新闻类型",
            self._build_entry_widget(form, self.news_type_var),
        )

        # 创建按钮行框架
        button_row = ttk.Frame(container)
        button_row.pack(fill="x", pady=(12, 10))

        # 创建运行管道按钮
        self.run_button = ttk.Button(button_row, text="运行工作流", command=self._start_run)
        self.run_button.pack(side="left")

        # 创建状态标签
        self.status_label = ttk.Label(button_row, textvariable=self.status_var)
        self.status_label.pack(side="left", padx=(14, 0))

        # 创建日志显示分组框
        log_frame = ttk.LabelFrame(container, text="实时日志", padding=10)
        log_frame.pack(fill="both", expand=True)

        # 创建日志文本框
        self.log_text = tk.Text(log_frame, wrap="word", height=20, state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)

        # 创建滚动条
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        # 将滚动条与文本框关联
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # 在日志区域添加初始提示信息
        self._append_log("\nGUI已就绪。配置字段并点击运行工作流。\n\n主题：用于搜索新闻的主题关键词，也会作为输出文件夹名称的一部分。\n\n新闻类型: 教育部政策/学校案例/社会事件")

        # 根据初始搜索提供者值设置手动新闻文件输入框的状态
        self.root.after(100, self._on_search_provider_change)

    def _build_provider_widget(self, parent: ttk.Frame) -> ttk.Combobox:
        """
        构建搜索提供者选择下拉框
        
        Args:
            parent: 父级容器框架
            
        Returns:
            ttk.Combobox: 配置好的下拉框组件
        """
        # 创建只读的组合框，显示有效的搜索提供者选项
        combo = ttk.Combobox(
            parent,
            textvariable=self.search_provider_var,
            values=VALID_SEARCH_PROVIDERS,
            state="readonly",
        )
        return combo

    def _build_manual_file_widget(self, parent: ttk.Frame) -> ttk.Frame:
        """
        构建手动文件选择组件
        
        创建包含文件路径输入框和浏览按钮的框架
        
        Args:
            parent: 父级容器框架
            
        Returns:
            ttk.Frame: 包含文件选择组件的框架
        """
        # 创建容器框架
        frame = ttk.Frame(parent)
        
        # 创建文件路径输入框
        self.manual_file_entry = ttk.Entry(frame, textvariable=self.manual_news_var)
        self.manual_file_entry.pack(side="left", fill="x", expand=True)

        # 创建浏览按钮
        self.manual_file_button = ttk.Button(frame, text="浏览", command=self._browse_manual_file)
        self.manual_file_button.pack(side="left", padx=(8, 0))
        return frame

    def _build_entry_widget(self, parent: ttk.Frame, variable: tk.StringVar) -> ttk.Entry:
        """
        构建文本输入框组件
        
        Args:
            parent: 父级容器框架
            variable: 与输入框关联的字符串变量
            
        Returns:
            ttk.Entry: 配置好的文本输入框
        """
        return ttk.Entry(parent, textvariable=variable)

    def _add_row(self, parent: ttk.Frame, row: int, label: str, widget: tk.Widget) -> None:
        """
        在表单中添加一行（标签和控件）
        
        Args:
            parent: 父级容器框架
            row: 行号
            label: 标签文本
            widget: 要添加的控件
        """
        # 创建标签并放置在指定行的第一列
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
        # 放置控件在指定行的第二列
        widget.grid(row=row, column=1, sticky="ew", pady=6)

    def _browse_manual_file(self) -> None:
        """
        浏览并选择手动新闻文件
        
        打开文件对话框让用户选择新闻文件，并更新相关变量
        """
        # 打开文件选择对话框
        selected = filedialog.askopenfilename(
            title="选择手动新闻文件",
            filetypes=[("文本文件", "*.txt *.md *.markdown"), ("所有文件", "*.*")],
        )
        # 如果用户选择了文件，则更新变量
        if selected:
            self.manual_news_var.set(selected)

    def _start_run(self) -> None:
        """
        开始运行处理管道
        
        验证用户输入，启动工作线程运行处理管道，并更新UI状态
        """
        # 检查是否已有运行中的线程
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("运行中", "工作流已在运行中。")
            return

        # 获取用户输入的值并清理空白字符
        provider = self.search_provider_var.get().strip().lower()
        topic = self.topic_var.get().strip()
        news_type = self.news_type_var.get().strip()
        manual_text = self.manual_news_var.get().strip()
        manual_path = Path(manual_text) if manual_text else None

        # 验证搜索提供者是否有效
        if provider not in VALID_SEARCH_PROVIDERS:
            messagebox.showerror("无效提供者", f"提供者必须是以下之一: {', '.join(VALID_SEARCH_PROVIDERS)}")
            return

        # 当选择手动模式时验证文件是否存在
        if provider == "manual" and not manual_path:
            messagebox.showerror("缺少文件", "当提供者为手动时，请选择一个新闻文件。")
            return

        # 验证手动选择的文件是否存在
        if manual_path and not manual_path.exists():
            messagebox.showerror("文件未找到", f"手动新闻文件未找到: {manual_path}")
            return

        # 验证主题是否为空
        if not topic:
            messagebox.showerror("缺少主题", "请输入一个主题。")
            return

        # 验证新闻类型是否为空
        if not news_type:
            messagebox.showerror("缺少新闻类型", "请输入一个新闻类型。")
            return

        # 安装日志处理器以捕获运行时的日志
        self._install_log_handler()
        # 设置运行状态
        self._set_running_state(True)
        # 更新状态栏文本
        self.status_var.set("正在运行工作流...")
        # 在日志中添加空行和开始信息
        self._append_log("")
        self._append_log(f"开始运行: 提供者={provider}, 主题={topic}, 新闻类型={news_type}")

        # 创建并启动工作线程
        self.worker_thread = threading.Thread(
            target=self._run_worker,
            args=(manual_path, provider, topic, news_type),
            daemon=True,
        )
        self.worker_thread.start()
        # 安排定期检查事件队列
        self.root.after(100, self._poll_events)

    def _run_worker(
        self,
        manual_path: Path | None,
        provider: str,
        topic: str,
        news_type: str,
    ) -> None:
        """
        工作线程执行的实际处理函数
        
        在后台线程中运行处理管道，并将结果发送到事件队列
        
        Args:
            manual_path: 手动新闻文件路径
            provider: 搜索提供者名称
            topic: 处理主题
            news_type: 新闻类型
        """
        try:
            # 运行处理管道
            output_dir = run_pipeline(
                config=self.config,
                manual_path=manual_path,
                provider_name=provider,
                topic=topic,
                news_type=news_type,
            )
            # 将成功完成的消息放入队列
            self.event_queue.put(("done", str(output_dir)))
        except Exception as exc:
            # 如果发生异常，获取完整的堆栈跟踪信息并放入队列
            details = traceback.format_exc().strip()
            self.event_queue.put(("error", f"{exc}\n\n{details}"))

    def _install_log_handler(self) -> None:
        """
        安装队列日志处理器
        
        移除现有的处理器并安装新的队列处理器，用于实时显示日志
        """
        # 如果已有处理器，先移除它
        if self.log_handler:
            self.logger.removeHandler(self.log_handler)

        # 创建新的队列处理器
        handler = _QueueLogHandler(self.event_queue)
        # 设置日志格式
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        # 将处理器添加到日志记录器
        self.logger.addHandler(handler)
        # 保存处理器引用
        self.log_handler = handler

    def _remove_log_handler(self) -> None:
        """
        移除队列日志处理器
        
        从日志记录器中移除队列处理器并清理引用
        """
        if self.log_handler:
            self.logger.removeHandler(self.log_handler)
            self.log_handler = None

    def _poll_events(self) -> None:
        """
        轮询事件队列中的消息
        
        检查事件队列中的消息并相应地更新UI和处理完成/错误状态
        """
        # 持续检查队列中的事件
        while True:
            try:
                # 非阻塞地获取队列中的事件
                event_type, payload = self.event_queue.get_nowait()
            except queue.Empty:
                # 如果队列为空，退出循环
                break

            if event_type == "log":
                # 如果是日志消息，在日志区域显示
                self._append_log(payload)
                continue

            # 处理完成或错误状态
            self._set_running_state(False)
            self._remove_log_handler()

            if event_type == "done":
                # 处理成功完成的情况
                self.status_var.set(f"完成。输出: {payload}")
                self._append_log(f"运行完成。输出目录: {payload}")
                messagebox.showinfo("已完成", f"工作流已成功完成。\n\n输出: {payload}")
            else:
                # 处理错误情况
                self.status_var.set("运行失败。")
                self._append_log(payload)
                messagebox.showerror("运行失败", payload)
            return

        # 如果工作线程仍在运行，继续安排轮询
        if self.worker_thread and self.worker_thread.is_alive():
            self.root.after(100, self._poll_events)
        else:
            # 清理处理器并重置状态
            self._remove_log_handler()
            self._set_running_state(False)

    def _set_running_state(self, running: bool) -> None:
        """
        设置运行状态
        
        根据运行状态启用或禁用运行按钮
        
        Args:
            running: 是否正在运行的布尔值
        """
        self.run_button.configure(state="disabled" if running else "normal")

    def _append_log(self, text: str) -> None:
        """
        向日志文本框追加内容
        
        临时启用文本框编辑权限，添加新内容，并保持滚动到底部
        
        Args:
            text: 要添加到日志的文本
        """
        # 启用文本框编辑权限
        self.log_text.configure(state="normal")
        if text:
            # 如果有文本内容，添加到末尾并换行
            self.log_text.insert("end", text + "\n")
        else:
            # 如果没有文本内容，只添加换行
            self.log_text.insert("end", "\n")
        # 滚动到文本末尾
        self.log_text.see("end")
        # 禁用文本框编辑权限
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        """
        窗口关闭事件处理
        
        在窗口关闭前移除日志处理器并销毁窗口
        """
        self._remove_log_handler()
        self.root.destroy()


def launch_gui() -> None:
    """
    启动图形用户界面
    
    创建根窗口、应用样式并启动主事件循环
    """
    # 创建Tkinter根窗口
    root = tk.Tk()
    try:
        # 创建并应用主题样式
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        # 如果样式应用失败，继续运行
        pass

    # 创建并运行应用程序
    LauncherApp(root)
    # 启动主事件循环
    root.mainloop()


def launch_gui() -> None:
    """
    启动图形用户界面
    
    创建根窗口、应用样式并启动主事件循环
    """
    # 创建Tkinter根窗口
    root = tk.Tk()
    try:
        # 创建并应用主题样式
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        # 如果样式应用失败，继续运行
        pass

    # 创建并运行应用程序
    LauncherApp(root)
    # 启动主事件循环
    root.mainloop()