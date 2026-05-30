from __future__ import annotations

from dataclasses import asdict
import json
import threading
import time
import tkinter as tk
from tkinter import messagebox

from .agents import get_agent
from .backend import check_backend
from .config import BASE_DIR, load_config
from .interview import create_session, list_sessions, load_session, coaching_summary, session_summary
from .speech import (
    get_capture_state,
    get_microphone_config,
    list_input_devices,
    record_microphone_clip,
    set_capture_state,
    transcribe_microphone_input,
)
from .streaming import stream_task
from .tts import speak_text, speech_supported, stop_speaking
from .voice import get_listen_state, route_transcript, set_listen_state
from .router import pick_agent


BG = "#050b12"
PANEL = "#0c1824"
PANEL_ALT = "#10263a"
PANEL_EDGE = "#173145"
TEXT = "#e8f7ff"
MUTED = "#7eaac6"
ACCENT = "#57e7ff"
ACCENT_2 = "#1699c7"
SUCCESS = "#2fe0b3"
WARNING = "#ffb454"
DANGER = "#ff718b"
GLOW = "#a4f6ff"


class JarvisDesktopApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Jarvis Lite")
        self.root.geometry("1460x900")
        self.root.minsize(1240, 780)
        self.root.configure(bg=BG)

        self.project_path = str(BASE_DIR)
        self.selected_session_id: str | None = None
        self.last_recording_path: str | None = None
        self.conversation_turns: list[dict[str, str]] = []
        self.response_chunks: list[str] = []
        self.is_generating = False
        self._visual_phase = 0
        self.listen_thread: threading.Thread | None = None
        self.listen_stop_event = threading.Event()

        self.status_var = tk.StringVar(value="Neural console ready.")
        self.listen_var = tk.StringVar(value="LISTEN OFFLINE")
        self.mic_var = tk.StringVar(value="MIC DEFAULT")
        self.capture_var = tk.StringVar(value="CAPTURE IDLE")
        self.backend_var = tk.StringVar(value="MODEL CORE // CHECKING")
        self.summary_var = tk.StringVar(value="CONVERSATION CHANNEL // READY")
        self.presence_var = tk.StringVar(value="ONLINE")
        self.hero_title_var = tk.StringVar(value="OMNIRA IS ONLINE")
        self.hero_hint_var = tk.StringVar(value="Say something, press Speak, or engage live listen.")
        self.boot_message_var = tk.StringVar(value="Initializing omnira shell...")
        self.session_title_var = tk.StringVar(value="Primary Conversation")
        self.message_var = tk.StringVar()
        self.voice_reply_var = tk.BooleanVar(value=speech_supported())
        self.auto_send_voice_var = tk.BooleanVar(value=True)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._show_boot_overlay()
        self._animate_visualizer()
        self.refresh_all()

    def _build_ui(self) -> None:
        wrapper = tk.Frame(self.root, bg=BG)
        wrapper.pack(fill="both", expand=True, padx=18, pady=18)

        self._build_header(wrapper)
        self._build_welcome_stage(wrapper)

        body = tk.Frame(wrapper, bg=BG)
        body.pack(fill="both", expand=True, pady=(16, 0))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_columnconfigure(2, weight=4)
        body.grid_rowconfigure(0, weight=1)

        left = self._panel(body, "COMMAND DECK")
        left[0].grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        center = self._panel(body, "SESSION MATRIX")
        center[0].grid(row=0, column=1, sticky="nsew", padx=(0, 12))

        right = self._panel(body, "LIVE CONVERSATION")
        right[0].grid(row=0, column=2, sticky="nsew")

        self._build_control_panel(left)
        self._build_session_panel(center)
        self._build_output_panel(right)

        footer = tk.Label(
            wrapper,
            textvariable=self.status_var,
            anchor="w",
            bg=BG,
            fg=MUTED,
            font=("Consolas", 10),
        )
        footer.pack(fill="x", pady=(12, 0))

    def _build_welcome_stage(self, parent: tk.Widget) -> None:
        stage = tk.Frame(parent, bg=BG)
        stage.pack(fill="x", pady=(18, 0))
        stage.grid_columnconfigure(0, weight=7)
        stage.grid_columnconfigure(1, weight=4)

        hero_shell = tk.Frame(stage, bg=PANEL, highlightthickness=1, highlightbackground=PANEL_EDGE)
        hero_shell.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        hero_shell.grid_columnconfigure(0, weight=1)

        self.hero_canvas = tk.Canvas(hero_shell, height=310, bg=PANEL, highlightthickness=0)
        self.hero_canvas.grid(row=0, column=0, sticky="nsew")

        overlay = tk.Frame(hero_shell, bg=PANEL)
        overlay.place(relx=0.04, rely=0.1, relwidth=0.48, relheight=0.8)

        tk.Label(
            overlay,
            text="WELCOME",
            bg=PANEL,
            fg=ACCENT,
            font=("Consolas", 12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            overlay,
            textvariable=self.hero_title_var,
            bg=PANEL,
            fg=TEXT,
            justify="left",
            wraplength=420,
            font=("Segoe UI", 24, "bold"),
        ).pack(anchor="w", pady=(10, 6))
        tk.Label(
            overlay,
            textvariable=self.hero_hint_var,
            bg=PANEL,
            fg=MUTED,
            justify="left",
            wraplength=420,
            font=("Segoe UI", 11),
        ).pack(anchor="w")

        action_row = tk.Frame(overlay, bg=PANEL)
        action_row.pack(anchor="w", pady=(18, 16))
        self._button(action_row, "Engage Voice", lambda: self.set_listen(True), primary=True).pack(side="left")
        self._button(action_row, "Stand By", lambda: self.set_listen(False)).pack(side="left", padx=(10, 0))
        self._button(action_row, "Push To Talk", self.capture_voice_message).pack(side="left", padx=(10, 0))

        chip_row = tk.Frame(overlay, bg=PANEL)
        chip_row.pack(anchor="w")
        self._hero_chip(chip_row, self.presence_var, SUCCESS).pack(side="left")
        self._hero_chip(chip_row, self.backend_var, DANGER).pack(side="left", padx=(10, 0))
        self._hero_chip(chip_row, self.capture_var, WARNING).pack(side="left", padx=(10, 0))

        side_shell = tk.Frame(stage, bg=PANEL, highlightthickness=1, highlightbackground=PANEL_EDGE)
        side_shell.grid(row=0, column=1, sticky="nsew")
        side_shell.grid_columnconfigure(0, weight=1)

        tk.Label(
            side_shell,
            text="SYSTEM PRESENCE",
            bg=PANEL_ALT,
            fg=ACCENT,
            font=("Consolas", 11, "bold"),
            padx=12,
            pady=10,
        ).grid(row=0, column=0, sticky="ew")

        side_inner = tk.Frame(side_shell, bg=PANEL)
        side_inner.grid(row=1, column=0, sticky="nsew", padx=14, pady=14)
        self._presence_card(side_inner, "Assistant State", self.presence_var, TEXT).pack(fill="x")
        self._presence_card(side_inner, "Listen Channel", self.listen_var, ACCENT).pack(fill="x", pady=(10, 0))
        self._presence_card(side_inner, "Microphone Link", self.mic_var, SUCCESS).pack(fill="x", pady=(10, 0))
        self._presence_card(side_inner, "Conversation Status", self.summary_var, MUTED).pack(fill="x", pady=(10, 0))

    def _hero_chip(self, parent: tk.Widget, variable: tk.StringVar, color: str) -> tk.Label:
        return tk.Label(
            parent,
            textvariable=variable,
            bg="#08141e",
            fg=color,
            font=("Consolas", 10, "bold"),
            padx=10,
            pady=8,
            relief="flat",
            highlightthickness=1,
            highlightbackground=PANEL_EDGE,
            highlightcolor=PANEL_EDGE,
        )

    def _presence_card(self, parent: tk.Widget, title: str, variable: tk.StringVar, value_color: str) -> tk.Frame:
        card = tk.Frame(parent, bg="#08141e", highlightthickness=1, highlightbackground=PANEL_EDGE)
        tk.Label(card, text=title.upper(), bg="#08141e", fg=MUTED, font=("Consolas", 9, "bold")).pack(
            anchor="w", padx=10, pady=(10, 4)
        )
        tk.Label(card, textvariable=variable, bg="#08141e", fg=value_color, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=10, pady=(0, 10)
        )
        return card

    def _build_header(self, parent: tk.Widget) -> None:
        header = tk.Frame(parent, bg=BG)
        header.pack(fill="x")

        title_col = tk.Frame(header, bg=BG)
        title_col.pack(side="left", fill="x", expand=True)

        tk.Label(
            title_col,
            text="OMNIRA DESKTOP // VOICE-FIRST OPERATOR CONSOLE",
            bg=BG,
            fg=ACCENT,
            font=("Consolas", 11, "bold"),
        ).pack(anchor="w")

        tk.Label(
            title_col,
            text="Jarvis Lite Desktop",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 28, "bold"),
        ).pack(anchor="w", pady=(4, 2))

        tk.Label(
            title_col,
            text="Live conversation shell now, OMNIRA model core later through the same backend adapter.",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 11),
        ).pack(anchor="w")

        status_strip = tk.Frame(header, bg=BG)
        status_strip.pack(side="right", anchor="ne")
        self._status_badge(status_strip, self.listen_var, ACCENT)
        self._status_badge(status_strip, self.mic_var, SUCCESS)
        self._status_badge(status_strip, self.capture_var, WARNING)
        self._status_badge(status_strip, self.backend_var, DANGER)

    def _status_badge(self, parent: tk.Widget, variable: tk.StringVar, color: str) -> tk.Label:
        label = tk.Label(
            parent,
            textvariable=variable,
            bg=PANEL_ALT,
            fg=color,
            font=("Consolas", 10, "bold"),
            bd=1,
            relief="solid",
            padx=10,
            pady=8,
            highlightthickness=1,
            highlightbackground=PANEL_EDGE,
            highlightcolor=PANEL_EDGE,
        )
        label.pack(side="left", padx=(8, 0))
        return label

    def _panel(self, parent: tk.Widget, title: str) -> tuple[tk.Frame, tk.Frame]:
        outer = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=PANEL_EDGE)
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        heading = tk.Frame(outer, bg=PANEL_ALT, height=44)
        heading.grid(row=0, column=0, sticky="ew")
        heading.grid_columnconfigure(0, weight=1)
        tk.Label(
            heading,
            text=title,
            bg=PANEL_ALT,
            fg=ACCENT,
            font=("Consolas", 11, "bold"),
            padx=12,
            pady=10,
        ).grid(row=0, column=0, sticky="w")

        inner = tk.Frame(outer, bg=PANEL)
        inner.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        return outer, inner

    def _button(self, parent: tk.Widget, text: str, command, *, primary: bool = False) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=ACCENT if primary else PANEL_ALT,
            fg="#041019" if primary else TEXT,
            activebackground=ACCENT_2 if primary else "#17354d",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=12,
            pady=10,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )

    def _mini_stat(self, parent: tk.Widget, title: str, value: str, color: str) -> tk.Frame:
        card = tk.Frame(parent, bg="#08141e", highlightthickness=1, highlightbackground=PANEL_EDGE)
        tk.Label(card, text=title.upper(), bg="#08141e", fg=MUTED, font=("Consolas", 8, "bold")).pack(
            anchor="w", padx=10, pady=(8, 4)
        )
        tk.Label(card, text=value, bg="#08141e", fg=color, font=("Segoe UI", 11, "bold")).pack(
            anchor="w", padx=10, pady=(0, 8)
        )
        return card

    def _toggle(self, parent: tk.Widget, text: str, variable: tk.BooleanVar) -> tk.Checkbutton:
        return tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            bg=PANEL,
            fg=TEXT,
            activebackground=PANEL,
            activeforeground=TEXT,
            selectcolor="#06131f",
            font=("Segoe UI", 10),
            anchor="w",
        )

    def _build_control_panel(self, panel_tuple) -> None:
        _, parent = panel_tuple

        tk.Label(parent, text="Conversation Profile", bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        entry = tk.Entry(
            parent,
            textvariable=self.session_title_var,
            bg="#06131f",
            fg=TEXT,
            insertbackground=ACCENT,
            relief="flat",
            font=("Segoe UI", 11),
        )
        entry.pack(fill="x", pady=(6, 12), ipady=8)

        actions = tk.Frame(parent, bg=PANEL)
        actions.pack(fill="x")
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        action_specs = [
            (0, 0, "Engage Voice", lambda: self.set_listen(True), True),
            (0, 1, "Stand By", lambda: self.set_listen(False), False),
            (1, 0, "Push To Talk", self.capture_voice_message, True),
            (1, 1, "Refresh Core", self.refresh_all, False),
            (2, 0, "Inspect Mics", self.show_devices, False),
            (2, 1, "Voice Sample", self.record_clip, False),
            (3, 0, "New Thread", self.create_practice_session, False),
            (3, 1, "Stop Voice", self.stop_voice_reply, False),
        ]
        for row, column, label, callback, primary in action_specs:
            self._button(actions, label, callback, primary=primary).grid(
                row=row,
                column=column,
                sticky="ew",
                padx=(0, 6) if column == 0 else (6, 0),
                pady=6,
            )

        self._toggle(parent, "Speak assistant replies aloud", self.voice_reply_var).pack(fill="x", pady=(14, 4))
        self._toggle(parent, "Auto-send recognized speech", self.auto_send_voice_var).pack(fill="x", pady=(2, 8))

        directive = tk.Frame(parent, bg="#08141e", highlightthickness=1, highlightbackground=PANEL_EDGE)
        directive.pack(fill="both", expand=True, pady=(12, 0))
        tk.Label(
            directive,
            text="MISSION DIRECTIVE",
            bg="#08141e",
            fg=ACCENT,
            font=("Consolas", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 6))
        tk.Label(
            directive,
            text="Keep the assistant visibly present, voice-first, and ready for interruption. The shell must feel alive even while the model core is still under construction.",
            bg="#08141e",
            fg=TEXT,
            justify="left",
            wraplength=280,
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=10)

        stat_grid = tk.Frame(directive, bg="#08141e")
        stat_grid.pack(fill="x", padx=10, pady=(12, 10))
        stat_grid.grid_columnconfigure(0, weight=1)
        stat_grid.grid_columnconfigure(1, weight=1)
        self._mini_stat(stat_grid, "Voice", "Ready", SUCCESS).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._mini_stat(stat_grid, "Mode", "Live", ACCENT).grid(row=0, column=1, sticky="ew")
        self._mini_stat(stat_grid, "UI", "HUD", GLOW).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(8, 0))
        self._mini_stat(stat_grid, "Brain", "Pending", WARNING).grid(row=1, column=1, sticky="ew", pady=(8, 0))

    def _build_session_panel(self, panel_tuple) -> None:
        _, parent = panel_tuple

        tk.Label(parent, text="Conversation Threads", bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        stats = tk.Frame(parent, bg=PANEL)
        stats.pack(fill="x", pady=(8, 10))
        stats.grid_columnconfigure(0, weight=1)
        stats.grid_columnconfigure(1, weight=1)
        self._mini_stat(stats, "Threads", "Local", ACCENT).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._mini_stat(stats, "Memory", "Active", SUCCESS).grid(row=0, column=1, sticky="ew")

        self.sessions_list = tk.Listbox(
            parent,
            height=28,
            bg="#06131f",
            fg=TEXT,
            selectbackground=ACCENT_2,
            selectforeground=TEXT,
            relief="flat",
            font=("Consolas", 10),
            activestyle="none",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=PANEL_EDGE,
            highlightcolor=ACCENT,
        )
        self.sessions_list.pack(fill="both", expand=True, pady=(8, 10))
        self.sessions_list.bind("<<ListboxSelect>>", self.on_session_select)

        self._button(parent, "Load Selected Session", self.load_selected_session, primary=True).pack(fill="x", pady=4)
        self._button(parent, "Refresh Session Matrix", self.refresh_sessions).pack(fill="x", pady=4)

    def _build_output_panel(self, panel_tuple) -> None:
        _, parent = panel_tuple

        hero = tk.Frame(parent, bg=PANEL)
        hero.pack(fill="x", pady=(0, 12))
        hero.grid_columnconfigure(1, weight=1)
        hero.grid_columnconfigure(2, weight=0)

        self.visualizer = tk.Canvas(hero, width=128, height=128, bg=PANEL, highlightthickness=0)
        self.visualizer.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 12))

        tk.Label(
            hero,
            textvariable=self.summary_var,
            bg=PANEL_ALT,
            fg=ACCENT,
            font=("Consolas", 10, "bold"),
            padx=10,
            pady=10,
        ).grid(row=0, column=1, sticky="ew")

        tk.Label(
            hero,
            text="Talk naturally. When the model backend is online, replies stream live. When it is offline, the desktop stays conversational and tells you exactly what is missing.",
            bg=PANEL,
            fg=MUTED,
            justify="left",
            wraplength=560,
            font=("Segoe UI", 10),
        ).grid(row=1, column=1, sticky="ew", pady=(10, 0))

        signal_rail = tk.Frame(hero, bg=PANEL)
        signal_rail.grid(row=0, column=2, rowspan=2, sticky="ns", padx=(14, 0))
        self.wave_canvas = tk.Canvas(
            signal_rail,
            width=72,
            height=128,
            bg="#08141e",
            highlightthickness=1,
            highlightbackground=PANEL_EDGE,
        )
        self.wave_canvas.pack()

        console_shell = tk.Frame(parent, bg="#06131f", highlightthickness=1, highlightbackground=PANEL_EDGE)
        console_shell.pack(fill="both", expand=True)

        self.output = tk.Text(
            console_shell,
            wrap="word",
            bg="#06131f",
            fg=TEXT,
            insertbackground=ACCENT,
            relief="flat",
            font=("Consolas", 10),
            padx=14,
            pady=14,
            highlightthickness=0,
        )
        self.output.pack(fill="both", expand=True, padx=6, pady=6)
        self.output.tag_configure("system_label", foreground=ACCENT, font=("Consolas", 10, "bold"))
        self.output.tag_configure("system_body", foreground=MUTED, lmargin1=14, lmargin2=14, spacing3=12)
        self.output.tag_configure("user_label", foreground=SUCCESS, font=("Consolas", 10, "bold"))
        self.output.tag_configure("user_body", foreground=TEXT, lmargin1=14, lmargin2=14, spacing3=12)
        self.output.tag_configure("assistant_label", foreground=ACCENT, font=("Consolas", 10, "bold"))
        self.output.tag_configure("assistant_body", foreground=TEXT, lmargin1=14, lmargin2=14, spacing3=12)
        self.output.insert("end", "SYSTEM\n", ("system_label",))
        self.output.insert(
            "end",
            "Conversation channel online. Type naturally below to talk with the desktop assistant.\n\n",
            ("system_body",),
        )
        self.output.configure(state="disabled")

        composer = tk.Frame(parent, bg=PANEL)
        composer.pack(fill="x", pady=(12, 0))
        composer.grid_columnconfigure(0, weight=1)

        self.message_entry = tk.Entry(
            composer,
            textvariable=self.message_var,
            bg="#06131f",
            fg=TEXT,
            insertbackground=ACCENT,
            relief="flat",
            font=("Segoe UI", 12),
        )
        self.message_entry.grid(row=0, column=0, sticky="ew", ipady=10)
        self.message_entry.bind("<Return>", self._on_enter_send)
        self._button(composer, "Speak", self.capture_voice_message).grid(row=0, column=1, padx=(10, 0))
        self._button(composer, "Send", self.send_message, primary=True).grid(row=0, column=2, padx=(10, 0))

    def _draw_wave_rail(self) -> None:
        canvas = getattr(self, "wave_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 72)
        height = max(canvas.winfo_height(), 128)
        active = self.is_generating or get_listen_state().enabled
        for index in range(7):
            x0 = 8 + index * 9
            bar_height = 20 + ((self._visual_phase + index * 3) % 10) * 7 if active else 18 + (index % 3) * 8
            y0 = height - 14 - bar_height
            color = ACCENT if index % 2 == 0 else SUCCESS
            canvas.create_rectangle(x0, y0, x0 + 5, height - 14, fill=color, outline="")
        canvas.create_text(width / 2, 12, text="AUDIO", fill=MUTED, font=("Consolas", 8, "bold"))

    def _draw_hero_stage(self) -> None:
        canvas = getattr(self, "hero_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 760)
        height = max(canvas.winfo_height(), 310)

        for step in range(0, width, 34):
            color = "#0a2230" if step % 68 else "#103247"
            canvas.create_line(step, 0, step, height, fill=color)
        for step in range(0, height, 28):
            color = "#0a2230" if step % 56 else "#103247"
            canvas.create_line(0, step, width, step, fill=color)

        center_x = int(width * 0.74)
        center_y = int(height * 0.5)
        active = self.is_generating or get_listen_state().enabled
        pulse = (self._visual_phase % 18) * (4 if active else 2)
        ring_colors = (ACCENT_2, ACCENT, GLOW, SUCCESS)
        for index, color in enumerate(ring_colors):
            radius = 30 + index * 28 + pulse
            canvas.create_oval(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                outline=color,
                width=2,
            )
        canvas.create_arc(
            center_x - 122,
            center_y - 122,
            center_x + 122,
            center_y + 122,
            start=30 + self._visual_phase * 8,
            extent=260,
            style="arc",
            outline=ACCENT,
            width=3,
        )
        canvas.create_arc(
            center_x - 88,
            center_y - 88,
            center_x + 88,
            center_y + 88,
            start=220 - self._visual_phase * 9,
            extent=180,
            style="arc",
            outline=SUCCESS,
            width=3,
        )
        fill = ACCENT if self.is_generating else SUCCESS if get_listen_state().enabled else PANEL_ALT
        canvas.create_oval(center_x - 26, center_y - 26, center_x + 26, center_y + 26, fill=fill, outline="")
        canvas.create_text(center_x, center_y, text="AI", fill=BG, font=("Consolas", 16, "bold"))

        canvas.create_line(center_x - 200, center_y, center_x - 112, center_y, fill=ACCENT, width=2)
        canvas.create_line(center_x + 112, center_y, center_x + 210, center_y, fill=ACCENT, width=2)
        canvas.create_text(center_x + 210, center_y - 16, text="VOICE CORE", fill=ACCENT, anchor="w", font=("Consolas", 10, "bold"))
        canvas.create_text(center_x + 210, center_y + 4, text=self.presence_var.get(), fill=TEXT, anchor="w", font=("Segoe UI", 12, "bold"))

        canvas.create_text(42, height - 34, text="Holographic neural interface active", fill=MUTED, anchor="w", font=("Consolas", 9))

    def _animate_visualizer(self) -> None:
        self._draw_hero_stage()
        self._draw_wave_rail()
        canvas = getattr(self, "visualizer", None)
        if canvas is None:
            return
        canvas.delete("all")
        center_x = 64
        center_y = 64
        active = self.is_generating or get_listen_state().enabled
        pulse = (self._visual_phase % 12) * (3 if self.is_generating else 1)
        for index, color in enumerate((ACCENT_2, ACCENT, SUCCESS)):
            radius = 18 + index * 13 + (pulse if active else 0)
            canvas.create_oval(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                outline=color,
                width=2,
            )
        fill = ACCENT if self.is_generating else SUCCESS if get_listen_state().enabled else PANEL_ALT
        canvas.create_oval(center_x - 18, center_y - 18, center_x + 18, center_y + 18, fill=fill, outline="")
        canvas.create_text(center_x, center_y, text="AI", fill=BG, font=("Consolas", 12, "bold"))
        self._visual_phase = (self._visual_phase + 1) % 24
        self.root.after(140, self._animate_visualizer)

    def _show_boot_overlay(self) -> None:
        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        overlay.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")
        overlay.configure(bg="#02060b")
        overlay.attributes("-topmost", True)

        shell = tk.Frame(overlay, bg="#02060b")
        shell.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(shell, text="OMNIRA", bg="#02060b", fg=ACCENT, font=("Consolas", 16, "bold")).pack()
        tk.Label(shell, text="NEURAL INTERFACE BOOT", bg="#02060b", fg=TEXT, font=("Segoe UI", 24, "bold")).pack(pady=(8, 6))
        tk.Label(shell, textvariable=self.boot_message_var, bg="#02060b", fg=MUTED, font=("Consolas", 10)).pack()

        progress = tk.Canvas(shell, width=420, height=20, bg="#08141e", highlightthickness=1, highlightbackground=PANEL_EDGE)
        progress.pack(pady=(18, 0))

        steps = [
            "Initializing omnira shell...",
            "Aligning voice channels...",
            "Bringing holographic interface online...",
            "Assistant presence confirmed.",
        ]

        def advance(index: int = 0) -> None:
            if not overlay.winfo_exists():
                return
            self.boot_message_var.set(steps[min(index, len(steps) - 1)])
            progress.delete("all")
            progress.create_rectangle(0, 0, 420, 20, fill="#08141e", outline="")
            progress.create_rectangle(0, 0, int(420 * ((index + 1) / len(steps))), 20, fill=ACCENT, outline="")
            if index + 1 < len(steps):
                overlay.after(340, lambda: advance(index + 1))
            else:
                overlay.after(420, overlay.destroy)

        advance()

    def _refresh_presence_display(self) -> None:
        listen = get_listen_state()
        if self.is_generating:
            self.presence_var.set("RESPONDING")
            self.hero_title_var.set("OMNIRA IS RESPONDING")
            self.hero_hint_var.set("Streaming a response through the conversation channel.")
            return
        if listen.enabled:
            self.presence_var.set("ONLINE")
            self.hero_title_var.set("OMNIRA IS LISTENING")
            self.hero_hint_var.set("Live listen is active. Speak naturally and Jarvis will capture short utterances.")
            return
        self.presence_var.set("STANDBY")
        self.hero_title_var.set("OMNIRA IS ONLINE")
        self.hero_hint_var.set("Press Engage Voice, say something with Push To Talk, or type into the channel below.")

    def _append_block(self, label: str, body: str, label_tag: str, body_tag: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", f"{label}\n", (label_tag,))
        self.output.insert("end", f"{body}\n\n", (body_tag,))
        self.output.see("end")
        self.output.configure(state="disabled")

    def _begin_assistant_response(self, agent_name: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", f"OMNIRA // {agent_name.upper()}\n", ("assistant_label",))
        self.output.see("end")
        self.output.configure(state="disabled")

    def _append_assistant_chunk(self, chunk: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", chunk, ("assistant_body",))
        self.output.see("end")
        self.output.configure(state="disabled")

    def _finish_assistant_response(self) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", "\n\n", ("assistant_body",))
        self.output.see("end")
        self.output.configure(state="disabled")

    def _on_enter_send(self, _event) -> str:
        self.send_message()
        return "break"

    def _conversation_task(self, user_text: str) -> str:
        history = self.conversation_turns[-6:]
        history_text = "\n".join(f"{turn['role'].upper()}: {turn['text']}" for turn in history)
        return (
            "You are speaking in a live desktop conversation. Respond naturally like a calm, capable AI operator. "
            "Use direct spoken language, keep it concise by default, and only go deep when the user asks for depth.\n\n"
            f"Recent conversation:\n{history_text or 'No previous turns.'}\n\n"
            f"User just said: {user_text}\n"
            "Reply as the assistant speaking directly to the user."
        )

    def _offline_response(self, user_text: str, backend_message: str) -> str:
        cfg = load_config()
        lowered = user_text.lower()
        if any(token in lowered for token in ["model", "omnira", "backend", "trained"]):
            return (
                "The live model core is not connected yet, so I am running in desktop shell mode. "
                f"Right now the configured backend is {cfg.backend} with model {cfg.model}. "
                "When your OMNIRA service is ready, point config.yaml at that endpoint and I can use the same conversation UI with real model replies. "
                f"Current backend status: {backend_message}."
            )
        return (
            "I can stay conversational locally, but the model backend is offline right now. "
            "That means I can manage the shell, capture context, and keep the interface live, but I cannot generate real model reasoning until the backend is reachable. "
            f"Current backend status: {backend_message}."
        )

    def _set_generation_state(self, active: bool) -> None:
        self.is_generating = active
        self.summary_var.set("CONVERSATION CHANNEL // THINKING" if active else "CONVERSATION CHANNEL // READY")
        self._refresh_presence_display()

    def refresh_all(self) -> None:
        listen = get_listen_state()
        mic = get_microphone_config()
        capture = get_capture_state()
        self.listen_var.set(f"LISTEN {'ONLINE' if listen.enabled else 'OFFLINE'} // {listen.mode.upper()}")
        self.mic_var.set(f"MIC {mic.device.upper()} // {mic.sample_rate}HZ")
        self.capture_var.set(f"CAPTURE {'ACTIVE' if capture.active else 'IDLE'} // {capture.provider.upper()}")
        ok, message = check_backend()
        backend_mode = "ONLINE" if ok else "OFFLINE"
        self.backend_var.set(f"MODEL CORE // {backend_mode}")
        self.refresh_sessions()
        self._refresh_presence_display()
        self.status_var.set(message if ok else f"Backend unavailable: {message}")

    def refresh_sessions(self) -> None:
        sessions = list_sessions(limit=50)
        self.sessions_list.delete(0, tk.END)
        for session in sessions:
            self.sessions_list.insert(tk.END, f"{session.title} | {session.id} | turns={len(session.turns)}")

    def set_listen(self, enabled: bool) -> None:
        state = set_listen_state(enabled, mode="continuous")
        self.listen_var.set(f"LISTEN {'ONLINE' if state.enabled else 'OFFLINE'} // {state.mode.upper()}")
        if enabled:
            self._start_listen_loop()
        else:
            self._stop_listen_loop()
        self._refresh_presence_display()
        self.status_var.set(f"Listen mode {'enabled' if enabled else 'disabled'}.")

    def _start_listen_loop(self) -> None:
        if self.listen_thread is not None and self.listen_thread.is_alive():
            return
        self.listen_stop_event.clear()
        capture = set_capture_state(True, provider="windows_dictation", mode="continuous")
        self.capture_var.set(f"CAPTURE {'ACTIVE' if capture.active else 'IDLE'} // {capture.provider.upper()}")
        self.summary_var.set("LIVE LISTEN // ACTIVE")
        self._refresh_presence_display()
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()

    def _stop_listen_loop(self) -> None:
        self.listen_stop_event.set()
        capture = set_capture_state(False, provider="windows_dictation", mode="continuous")
        self.capture_var.set(f"CAPTURE {'ACTIVE' if capture.active else 'IDLE'} // {capture.provider.upper()}")
        if not self.is_generating:
            self.summary_var.set("CONVERSATION CHANNEL // READY")
        self._refresh_presence_display()

    def _listen_loop(self) -> None:
        while not self.listen_stop_event.is_set():
            if self.is_generating:
                time.sleep(0.4)
                continue
            try:
                result = transcribe_microphone_input(
                    duration_s=4,
                    provider="windows_dictation",
                    allow_empty=True,
                )
            except (RuntimeError, ValueError) as exc:
                self.root.after(0, lambda value=str(exc): self._handle_listen_error(value))
                time.sleep(1.0)
                continue
            if self.listen_stop_event.is_set():
                break
            transcript = " ".join(result.transcript.split())
            if not transcript:
                continue
            self.root.after(0, lambda value=transcript: self._handle_voice_transcript(value, source="live-listen"))

    def _handle_listen_error(self, message: str) -> None:
        self.summary_var.set("LIVE LISTEN // DEGRADED")
        self.hero_hint_var.set("Live listen is active, but the microphone channel reported a warning.")
        self.status_var.set(f"Live listen warning: {message}")

    def stop_voice_reply(self) -> None:
        stop_speaking()
        self.status_var.set("Voice reply stopped.")

    def show_devices(self) -> None:
        try:
            devices = list_input_devices()
        except RuntimeError as exc:
            messagebox.showerror("Microphone", str(exc))
            return
        if not devices:
            self.summary_var.set("MICROPHONE SCAN // NO DEVICES")
            self._append_block("SYSTEM", "No input devices detected.", "system_label", "system_body")
            return
        text = "\n".join(
            f"{device.index}: {device.name} | channels={device.max_input_channels} | sample_rate={device.default_sample_rate}"
            for device in devices
        )
        self.summary_var.set(f"MICROPHONE SCAN // {len(devices)} DEVICES")
        self._append_block("SYSTEM", text, "system_label", "system_body")
        self.status_var.set("Microphone device matrix loaded.")

    def record_clip(self) -> None:
        self.status_var.set("Recording 3 second voice sample...")
        self.summary_var.set("VOICE CAPTURE // RECORDING")

        def worker() -> None:
            try:
                path = record_microphone_clip(duration_s=3)
                self.root.after(0, lambda: self._record_success(str(path)))
            except RuntimeError as exc:
                self.root.after(0, lambda: messagebox.showerror("Recording", str(exc)))
                self.root.after(0, lambda: self.status_var.set("Recording failed."))
                self.root.after(0, lambda: self.summary_var.set("VOICE CAPTURE // FAILED"))

        threading.Thread(target=worker, daemon=True).start()

    def _record_success(self, path: str) -> None:
        self.last_recording_path = path
        self._append_block("SYSTEM", f"Recorded WAV file saved to\n{path}", "system_label", "system_body")
        self.summary_var.set("VOICE CAPTURE // COMPLETE")
        self.status_var.set("Recording complete.")

    def capture_voice_message(self) -> None:
        if self.is_generating:
            self.status_var.set("Wait for the current response before starting voice capture.")
            return

        self.summary_var.set("VOICE INPUT // LISTENING")
        self.status_var.set("Listening on the default microphone. Speak now.")

        def worker() -> None:
            try:
                result = transcribe_microphone_input(duration_s=6, provider="windows_dictation")
                self.root.after(0, lambda: self._handle_voice_transcript(result.transcript, source="button"))
            except (RuntimeError, ValueError) as exc:
                self.root.after(0, lambda: messagebox.showerror("Voice Input", str(exc)))
                self.root.after(0, lambda: self.summary_var.set("VOICE INPUT // FAILED"))
                self.root.after(0, lambda: self.status_var.set("Voice input failed."))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_voice_transcript(self, transcript: str, *, source: str = "voice") -> None:
        self.message_var.set(transcript)
        route = route_transcript(transcript)
        label = "YOU // LIVE" if source == "live-listen" else "YOU // VOICE"
        self._append_block(label, route.normalized_task, "user_label", "user_body")
        self.summary_var.set(f"VOICE INPUT // {route.suggested_agent.upper()}")
        self.hero_hint_var.set(f"Recognized speech routed toward the {route.suggested_agent} agent profile.")
        self.status_var.set("Voice input captured.")
        if self.auto_send_voice_var.get():
            self.send_message(from_voice=True)

    def create_practice_session(self) -> None:
        title = self.session_title_var.get().strip() or "Primary Conversation"
        session = create_session(title)
        self.selected_session_id = session.id
        self.refresh_sessions()
        self.load_session_by_id(session.id)
        self.status_var.set("New conversation created.")

    def on_session_select(self, _event=None) -> None:
        selection = self.sessions_list.curselection()
        if not selection:
            return
        line = self.sessions_list.get(selection[0])
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 2:
            self.selected_session_id = parts[1]

    def load_selected_session(self) -> None:
        self.on_session_select()
        if not self.selected_session_id:
            self.status_var.set("No session selected.")
            return
        self.load_session_by_id(self.selected_session_id)

    def load_session_by_id(self, session_id: str) -> None:
        self.selected_session_id = session_id
        try:
            session = load_session(session_id)
            summary = session_summary(session_id)
            coaching = coaching_summary(session_id)
        except FileNotFoundError as exc:
            messagebox.showerror("Session", str(exc))
            return
        payload = {
            "session": asdict(session),
            "summary": summary,
            "coaching": coaching,
        }
        self.summary_var.set(
            f"SESSION // {session.title.upper()} // SCORE {coaching.get('answer_score', 0)}/{coaching.get('max_score', 0)}"
        )
        self._append_block("SESSION", json.dumps(payload, indent=2), "system_label", "system_body")
        self.status_var.set("Session loaded.")

    def send_message(self, from_voice: bool = False) -> None:
        if self.is_generating:
            self.status_var.set("A response is already being generated.")
            return
        text = " ".join(self.message_var.get().strip().split())
        if not text:
            return

        self.message_var.set("")
        self.conversation_turns.append({"role": "user", "text": text})
        if not from_voice:
            self._append_block("YOU", text, "user_label", "user_body")
        self._set_generation_state(True)
        self.status_var.set("Generating assistant reply...")
        stop_speaking()

        worker = threading.Thread(target=self._generate_reply, args=(text,), daemon=True)
        worker.start()

    def _generate_reply(self, user_text: str) -> None:
        ok, message = check_backend()
        if not ok:
            reply = self._offline_response(user_text, message)
            self.root.after(0, lambda: self._complete_reply(reply, "offline"))
            return

        agent_name = pick_agent(user_text)
        agent = get_agent(agent_name)
        task = self._conversation_task(user_text)
        self.response_chunks = []
        self.root.after(0, lambda: self._begin_assistant_response(agent_name))
        try:
            for chunk in stream_task(task, agent, self.project_path, source="desktop.chat"):
                self.response_chunks.append(chunk)
                self.root.after(0, lambda value=chunk: self._append_assistant_chunk(value))
            reply = "".join(self.response_chunks).strip() or "I did not produce a response."
            self.root.after(0, self._finish_assistant_response)
            self.root.after(0, lambda: self._complete_reply(reply, agent_name, already_rendered=True))
        except Exception as exc:
            reply = f"Response generation failed: {exc}"
            self.root.after(0, lambda: self._complete_reply(reply, agent_name))

    def _complete_reply(self, reply: str, agent_name: str, *, already_rendered: bool = False) -> None:
        clean_reply = " ".join(reply.split())
        self.conversation_turns.append({"role": "assistant", "text": clean_reply})
        if not already_rendered:
            self._append_block(f"OMNIRA // {agent_name.upper()}", clean_reply, "assistant_label", "assistant_body")
        self._set_generation_state(False)
        self.hero_hint_var.set("Conversation channel is open. You can speak again or type the next command.")
        self.status_var.set(f"Reply ready via {agent_name}.")
        if self.voice_reply_var.get():
            speak_text(clean_reply, rate=1)

    def _on_close(self) -> None:
        self.listen_stop_event.set()
        stop_speaking()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def start_desktop() -> None:
    app = JarvisDesktopApp()
    app.run()