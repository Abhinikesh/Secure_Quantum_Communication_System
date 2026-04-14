import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import math
import random
import datetime
import os
import sys
import traceback

# Matplotlib embedded graph support
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# -----------------------------------------------------------------------------
# SAFE IMPORTS OF EXISTING PROJECT FILES
# -----------------------------------------------------------------------------
try:
    from alice import Alice
    from bob import Bob
    from eve import Eve
    import qber as QBER
    import visualize as VIS
except ImportError as e:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Import Error",
        f"Missing a core module:\n{str(e)}\n\nPlease ensure alice.py, bob.py, eve.py, "
        f"qber.py, and visualize.py are in the same directory."
    )
    sys.exit(1)

# -----------------------------------------------------------------------------
# UI CONSTANTS AND COLORS
# -----------------------------------------------------------------------------
BG_COLOR       = "#0a0a1a"    # Very dark navy
PANEL_BG       = "#0d1117"    # GitHub dark mode style
CARD_BG        = "#161b22"    # Slightly lighter dark
BORDER_COLOR   = "#30363d"    # Subtle border
ACCENT_COLOR   = "#00d4ff"    # Cyan / Quantum blue
SUCCESS_COLOR  = "#00ff88"    # Bright green
DANGER_COLOR   = "#ff4757"    # Bright red
WARN_COLOR     = "#ffa502"    # Orange
TEXT_PRIMARY   = "#e6edf3"    # Near white
TEXT_SECONDARY = "#8b949e"    # Gray
BTN_HOVER      = "#1f6feb"    # Blue
IDLE_GRAY      = "#555555"    # For disabled elements

# -----------------------------------------------------------------------------
# CUSTOM CLASSES FOR STYLING
# -----------------------------------------------------------------------------

class HoverButton(tk.Button):
    """Custom standard button with hover effect."""
    def __init__(self, master, default_bg, hover_bg, **kwargs):
        super().__init__(master, background=default_bg, activebackground=hover_bg,
                         activeforeground="white", relief=tk.FLAT, borderwidth=0,
                         cursor="hand2", **kwargs)
        self.default_bg = default_bg
        self.hover_bg = hover_bg
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, e):
        if self['state'] != 'disabled':
            self['background'] = self.hover_bg

    def on_leave(self, e):
        if self['state'] != 'disabled':
            self['background'] = self.default_bg


class QKDSimulatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("BB84 Quantum Key Distribution — Eavesdropper Detection System")
        self.root.minsize(1400, 900)
        self.root.geometry("1400x900")
        self.root.configure(bg=BG_COLOR)
        
        # Center Window
        self._center_window(1400, 900)
        
        # State variables
        self.is_running = False
        self.run_history = []
        
        self.var_qubits = tk.IntVar(value=256)
        self.var_threshold = tk.IntVar(value=11)
        self.var_sample_size = tk.IntVar(value=50)
        
        self.var_eve_enabled = tk.BooleanVar(value=False)
        self.var_intercept_rate = tk.IntVar(value=100)
        
        self.var_speed = tk.StringVar(value="Normal")
        self.var_theme = tk.StringVar(value="Dark")
        
        # Latest run properties
        self.current_qber = 0.0
        self.final_key_str = ""
        
        self.header_dots = []
        self.dot_pulse_state = 0
        
        self._setup_styles()
        self._setup_layout()
        self._setup_menu()
        
        self.update_time()

    def _center_window(self, w, h):
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        self.root.geometry('%dx%d+%d+%d' % (w, h, x, y))

    def _setup_styles(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
            
        # Custom ttk styles
        style.configure("TFrame", background=BG_COLOR)
        style.configure("Panel.TFrame", background=PANEL_BG)
        style.configure("Card.TFrame", background=CARD_BG)
        
        style.configure("TLabelframe", background=CARD_BG, bordercolor=BORDER_COLOR, 
                        lightcolor=CARD_BG, darkcolor=CARD_BG)
        style.configure("TLabelframe.Label", background=CARD_BG, foreground=ACCENT_COLOR, 
                        font=("Helvetica", 11, "bold"))
        
        style.configure("TLabel", background=CARD_BG, foreground=TEXT_PRIMARY, font=("Helvetica", 10))
        style.configure("Gray.TLabel", foreground=TEXT_SECONDARY)
        style.configure("Header.TLabel", background=PANEL_BG, foreground=TEXT_PRIMARY, font=("Helvetica", 16, "bold"))
        style.configure("SubHeader.TLabel", background=PANEL_BG, foreground=TEXT_SECONDARY, font=("Helvetica", 11))
        
        style.configure("Horizontal.TScale", background=CARD_BG, troughcolor=BG_COLOR, sliderthickness=15)
        style.configure("TRadiobutton", background=CARD_BG, foreground=TEXT_PRIMARY, selectcolor=BG_COLOR)
        style.configure("TCheckbutton", background=CARD_BG, foreground=TEXT_PRIMARY, selectcolor=BG_COLOR)
        
        style.configure("TNotebook", background=PANEL_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=CARD_BG, foreground=TEXT_PRIMARY, padding=[15, 8], font=("Helvetica", 11))
        style.map("TNotebook.Tab", background=[("selected", ACCENT_COLOR)], foreground=[("selected", BG_COLOR)])
        
        style.configure("Treeview", background=CARD_BG, foreground=TEXT_PRIMARY, fieldbackground=CARD_BG, rowheight=30)
        style.map("Treeview", background=[("selected", BTN_HOVER)], foreground=[("selected", TEXT_PRIMARY)])
        style.configure("Treeview.Heading", background=PANEL_BG, foreground=TEXT_PRIMARY, font=("Helvetica", 10, "bold"))

    def _setup_layout(self):
        # 1. Header Bar
        self.header_frame = tk.Frame(self.root, bg=PANEL_BG, height=60, highlightbackground=ACCENT_COLOR, highlightthickness=1, highlightcolor=ACCENT_COLOR)
        self.header_frame.pack(side=tk.TOP, fill=tk.X)
        self.header_frame.pack_propagate(False)
        self._setup_header()
        
        # 2. Bottom Status Bar
        self.status_bar = tk.Frame(self.root, bg="#010409", height=30, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar.pack_propagate(False)
        self._setup_status_bar()
        
        # Middle Area Container
        self.main_container = tk.Frame(self.root, bg=BG_COLOR)
        self.main_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # 3. Left Panel
        self.left_panel = tk.Frame(self.main_container, bg=CARD_BG, width=300, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        self.left_panel.pack_propagate(False)
        self._setup_left_panel()
        
        # 5. Right Panel (doing this before center so center expands)
        self.right_panel = tk.Frame(self.main_container, bg=CARD_BG, width=300, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        self.right_panel.pack_propagate(False)
        self._setup_right_panel()
        
        # 4. Center Panel
        self.center_panel = tk.Frame(self.main_container, bg=PANEL_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=10)
        self._setup_center_panel()

    def _setup_menu(self):
        menubar = tk.Menu(self.root)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Simulation", command=self.run_simulation_thread)
        file_menu.add_separator()
        file_menu.add_command(label="Save Final Key...", command=self._export_key)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Dark/Light theme (Beta)", command=self._toggle_theme)
        view_menu.add_command(label="Show/Hide Left Panel", command=lambda: self._toggle_panel(self.left_panel))
        view_menu.add_command(label="Show/Hide Right Panel", command=lambda: self._toggle_panel(self.right_panel))
        view_menu.add_command(label="Full Screen (F11)", command=self._toggle_fullscreen)
        menubar.add_cascade(label="View", menu=view_menu)
        
        sim_menu = tk.Menu(menubar, tearoff=0)
        sim_menu.add_command(label="Quick Demo (2 Scenarios)", command=self._run_quick_demo)
        sim_menu.add_command(label="Full Demo (All Scenarios)", command=self._run_full_demo)
        sim_menu.add_command(label="Run 10x Simulation for stats", command=self._run_10x_demo)
        menubar.add_cascade(label="Simulation", menu=sim_menu)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        help_menu.add_command(label="Theory", command=self._show_theory)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)
        self.root.bind('<F11>', lambda event: self._toggle_fullscreen())

    def _toggle_panel(self, panel):
        if panel.winfo_viewable():
            panel.pack_forget()
        else:
            if panel == self.left_panel:
                panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10, before=self.center_panel)
            else:
                panel.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10, after=self.center_panel)

    def _toggle_fullscreen(self, event=None):
        self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen"))
        return "break"

    def _setup_header(self):
        # Left
        left_h = tk.Frame(self.header_frame, bg=PANEL_BG)
        left_h.pack(side=tk.LEFT, padx=15, pady=10)
        
        tk.Label(left_h, text="🔐", font=("Segoe UI Emoji", 20), fg=ACCENT_COLOR, bg=PANEL_BG).pack(side=tk.LEFT, padx=5)
        vbox = tk.Frame(left_h, bg=PANEL_BG)
        vbox.pack(side=tk.LEFT)
        tk.Label(vbox, text="BB84 Quantum Key Distribution", font=("Helvetica", 16, "bold"), fg=TEXT_PRIMARY, bg=PANEL_BG).pack(anchor="w")
        tk.Label(vbox, text="Secure Communication Simulator", font=("Helvetica", 11), fg=TEXT_SECONDARY, bg=PANEL_BG).pack(anchor="w")

        # Center
        self.center_h = tk.Frame(self.header_frame, bg=PANEL_BG)
        self.center_h.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        inner_center = tk.Frame(self.center_h, bg=PANEL_BG)
        inner_center.pack(expand=True)
        
        self.dots_canvas = tk.Canvas(inner_center, bg=PANEL_BG, width=60, height=20, highlightthickness=0)
        self.dots_canvas.pack()
        self.header_dots = [
            self.dots_canvas.create_oval(5, 5, 15, 15, fill=IDLE_GRAY, outline=""),
            self.dots_canvas.create_oval(25, 5, 35, 15, fill=IDLE_GRAY, outline=""),
            self.dots_canvas.create_oval(45, 5, 55, 15, fill=IDLE_GRAY, outline="")
        ]
        
        self.lbl_head_status = tk.Label(inner_center, text="SIMULATION IDLE", font=("Helvetica", 14, "bold"), fg=ACCENT_COLOR, bg=PANEL_BG)
        self.lbl_head_status.pack()

        # Right
        right_h = tk.Frame(self.header_frame, bg=PANEL_BG)
        right_h.pack(side=tk.RIGHT, padx=15, pady=10)
        vbox2 = tk.Frame(right_h, bg=PANEL_BG)
        vbox2.pack(side=tk.RIGHT)
        tk.Label(vbox2, text="DTI Project | CSE Department", font=("Helvetica", 11), fg=TEXT_SECONDARY, bg=PANEL_BG).pack(anchor="e")
        tk.Label(vbox2, text="v1.0", font=("Helvetica", 10), fg=TEXT_SECONDARY, bg=PANEL_BG).pack(anchor="e")

    def _setup_left_panel(self):
        tk.Label(self.left_panel, text="⚙️ SIMULATION CONTROLS", font=("Helvetica", 12, "bold"), fg=ACCENT_COLOR, bg=CARD_BG).pack(pady=(15, 15))

        # SECTION 1 - Protocol Settings
        lf1 = ttk.LabelFrame(self.left_panel, text=" PROTOCOL SETTINGS ")
        lf1.pack(fill=tk.X, padx=15, pady=5)
        
        f_q = tk.Frame(lf1, bg=CARD_BG)
        f_q.pack(fill=tk.X, padx=10, pady=(10, 5))
        self.lbl_qubits = tk.Label(f_q, text="Number of Qubits: 256", bg=CARD_BG, fg=TEXT_PRIMARY)
        self.lbl_qubits.pack(anchor="w")
        scale_q = ttk.Scale(f_q, from_=64, to=1024, orient=tk.HORIZONTAL, variable=self.var_qubits, command=lambda v: self._snap_qubits(v))
        scale_q.pack(fill=tk.X, pady=5)
        tk.Label(f_q, text="Values snap to: 64, 128, 256, 512, 1024", font=("Helvetica", 8), fg=TEXT_SECONDARY, bg=CARD_BG).pack(anchor="w")
        
        f_t = tk.Frame(lf1, bg=CARD_BG)
        f_t.pack(fill=tk.X, padx=10, pady=5)
        self.lbl_threshold = tk.Label(f_t, text="Error Threshold: 11%", bg=CARD_BG, fg=TEXT_PRIMARY)
        self.lbl_threshold.pack(anchor="w")
        scale_t = ttk.Scale(f_t, from_=5, to=25, orient=tk.HORIZONTAL, variable=self.var_threshold, command=lambda v: self.lbl_threshold.config(text=f"Error Threshold: {int(float(v))}%"))
        scale_t.pack(fill=tk.X, pady=5)
        
        f_s = tk.Frame(lf1, bg=CARD_BG)
        f_s.pack(fill=tk.X, padx=10, pady=(5, 10))
        self.lbl_sample = tk.Label(f_s, text="Sample Size: 50", bg=CARD_BG, fg=TEXT_PRIMARY)
        self.lbl_sample.pack(anchor="w")
        scale_s = ttk.Scale(f_s, from_=10, to=100, orient=tk.HORIZONTAL, variable=self.var_sample_size, command=lambda v: self.lbl_sample.config(text=f"Sample Size: {int(float(v))}"))
        scale_s.pack(fill=tk.X, pady=5)

        # SECTION 2 - Eve
        lf2 = ttk.LabelFrame(self.left_panel, text=" 👤 EVE (EAVESDROPPER) ")
        lf2.pack(fill=tk.X, padx=15, pady=10)
        
        f_e = tk.Frame(lf2, bg=CARD_BG)
        f_e.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        self.btn_toggle_eve = tk.Button(f_e, text="ENABLE EVE: OFF", bg=BORDER_COLOR, fg="white", font=("Helvetica", 10, "bold"), relief=tk.FLAT, command=self._toggle_eve)
        self.btn_toggle_eve.pack(fill=tk.X, pady=5)
        
        self.lbl_irate = tk.Label(f_e, text="Interception Rate: 100%", bg=CARD_BG, fg=TEXT_SECONDARY)
        self.lbl_irate.pack(anchor="w", pady=(5,0))
        self.scale_irate = ttk.Scale(f_e, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.var_intercept_rate, command=lambda v: self.lbl_irate.config(text=f"Interception Rate: {int(float(v))}%"))
        self.scale_irate.state(['disabled'])
        self.scale_irate.pack(fill=tk.X, pady=5)
        
        tk.Label(f_e, text="Attack Type: Intercept & Resend", font=("Helvetica", 9), fg=TEXT_SECONDARY, bg=CARD_BG).pack(anchor="w", pady=(0, 10))

        # SECTION 3 - Action Buttons
        f_btn = tk.Frame(self.left_panel, bg=CARD_BG)
        f_btn.pack(fill=tk.X, padx=15, pady=10)
        
        self.btn_run = HoverButton(f_btn, ACCENT_COLOR, "#00b5d9", text="▶ RUN SIMULATION", font=("Helvetica", 13, "bold"), fg=BG_COLOR, height=2, command=self.run_simulation_thread)
        self.btn_run.pack(fill=tk.X, pady=5)
        
        btn_graphs = HoverButton(f_btn, BTN_HOVER, "#155abf", text="📊 GENERATE GRAPHS", font=("Helvetica", 13, "bold"), fg="white", height=2, command=self._generate_graphs_external)
        btn_graphs.pack(fill=tk.X, pady=5)
        
        btn_reset = HoverButton(f_btn, BORDER_COLOR, "#404852", text="🔄 RESET", font=("Helvetica", 13, "bold"), fg="white", height=2, command=self._reset_gui)
        btn_reset.pack(fill=tk.X, pady=5)

        # SECTION 4 - Speed
        f_spd = tk.Frame(self.left_panel, bg=CARD_BG)
        f_spd.pack(fill=tk.X, padx=15, pady=10, side=tk.BOTTOM)
        tk.Label(f_spd, text="Simulation Speed", bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="center")
        f_r = tk.Frame(f_spd, bg=CARD_BG)
        f_r.pack(pady=5)
        ttk.Radiobutton(f_r, text="Fast", variable=self.var_speed, value="Fast").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(f_r, text="Normal", variable=self.var_speed, value="Normal").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(f_r, text="Slow", variable=self.var_speed, value="Slow").pack(side=tk.LEFT, padx=5)

    def _snap_qubits(self, val):
        v = int(float(val))
        snaps = [64, 128, 256, 512, 1024]
        closest = min(snaps, key=lambda x: abs(x - v))
        self.var_qubits.set(closest)
        self.lbl_qubits.config(text=f"Number of Qubits: {closest}")

    def _toggle_eve(self):
        state = not self.var_eve_enabled.get()
        self.var_eve_enabled.set(state)
        
        if state:
            self.btn_toggle_eve.config(text="ENABLE EVE: ON", bg=DANGER_COLOR)
            self.scale_irate.state(['!disabled'])
            self.lbl_irate.config(fg=TEXT_PRIMARY)
        else:
            self.btn_toggle_eve.config(text="ENABLE EVE: OFF", bg=BORDER_COLOR)
            self.scale_irate.state(['disabled'])
            self.lbl_irate.config(fg=TEXT_SECONDARY)

    def _setup_center_panel(self):
        self.notebook = ttk.Notebook(self.center_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # TAB 1 - LIVE PROTOCOL
        self.tab_protocol = tk.Frame(self.notebook, bg=PANEL_BG)
        self.notebook.add(self.tab_protocol, text=" 🔬 LIVE PROTOCOL ")
        self._setup_protocol_tab()
        
        # TAB 2 - LIVE GRAPHS
        self.tab_graphs = tk.Frame(self.notebook, bg=PANEL_BG)
        self.notebook.add(self.tab_graphs, text=" 📈 LIVE GRAPHS ")
        self._setup_graphs_tab()
        
        # TAB 3 - STATISTICS
        self.tab_stats = tk.Frame(self.notebook, bg=PANEL_BG)
        self.notebook.add(self.tab_stats, text=" 📋 STATISTICS ")
        self._setup_statistics_tab()

    def _setup_protocol_tab(self):
        # TOP - Canvas
        f_top = tk.Frame(self.tab_protocol, bg=PANEL_BG, height=300)
        f_top.pack(fill=tk.X, pady=10)
        f_top.pack_propagate(False)
        
        self.anim_canvas = tk.Canvas(f_top, bg=BG_COLOR, highlightthickness=1, highlightbackground=BORDER_COLOR)
        self.anim_canvas.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Draw static elements on canvas
        self._draw_static_canvas()
        
        self.lbl_anim_step = tk.Label(f_top, text="Awaiting Simulation Start...", font=("Helvetica", 14), fg=TEXT_SECONDARY, bg=PANEL_BG)
        self.lbl_anim_step.pack(pady=5)
        
        # BOTTOM - Log
        f_bot = tk.Frame(self.tab_protocol, bg=PANEL_BG)
        f_bot.pack(fill=tk.BOTH, expand=True, pady=10, padx=15)
        
        tk.Label(f_bot, text="PROTOCOL EXECUTION LOG", font=("Helvetica", 11, "bold"), fg=TEXT_PRIMARY, bg=PANEL_BG).pack(fill=tk.X)
        
        f_log_text = tk.Frame(f_bot, bg="#000")
        f_log_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = tk.Text(f_log_text, bg="#010409", fg=TEXT_PRIMARY, font=("Consolas", 11), wrap=tk.WORD, state=tk.DISABLED, bd=1, highlightthickness=0)
        
        scrollbar = tk.Scrollbar(f_log_text, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Tag configs
        self.log_text.tag_config('success', foreground=SUCCESS_COLOR)
        self.log_text.tag_config('error', foreground=DANGER_COLOR, font=("Consolas", 11, "bold"))
        self.log_text.tag_config('warning', foreground=WARN_COLOR)
        self.log_text.tag_config('info', foreground=ACCENT_COLOR)
        self.log_text.tag_config('time', foreground=TEXT_SECONDARY)

    def _draw_static_canvas(self):
        cv = self.anim_canvas
        w = 700  # Virtual width
        h = 240
        
        # ALICE
        cv.create_rectangle(50, 80, 160, 160, outline=ACCENT_COLOR, fill=CARD_BG, width=2)
        cv.create_text(105, 120, text="👩 Alice", font=("Helvetica", 14, "bold"), fill=TEXT_PRIMARY)
        cv.create_text(105, 55, text="SENDER", font=("Helvetica", 10), fill=TEXT_SECONDARY)
        
        # BOB
        cv.create_rectangle(540, 80, 650, 160, outline=SUCCESS_COLOR, fill=CARD_BG, width=2)
        cv.create_text(595, 120, text="👨 Bob", font=("Helvetica", 14, "bold"), fill=TEXT_PRIMARY)
        cv.create_text(595, 55, text="RECEIVER", font=("Helvetica", 10), fill=TEXT_SECONDARY)
        
        # Channel line
        cv.create_line(160, 120, 540, 120, fill=TEXT_SECONDARY, dash=(4, 4), width=2)
        cv.create_text(350, 105, text="QUANTUM CHANNEL", fill=TEXT_SECONDARY, font=("Helvetica", 10))
        
        # EVE (always draw but grayed normally)
        self.eve_rect = cv.create_rectangle(295, 150, 405, 230, outline=IDLE_GRAY, fill=CARD_BG, width=2, dash=(2,2))
        self.eve_text = cv.create_text(350, 190, text="👤 Eve", font=("Helvetica", 14), fill=IDLE_GRAY)

    def _setup_graphs_tab(self):
        self.fig = Figure(figsize=(10, 5), dpi=100, facecolor=PANEL_BG)
        self.ax1 = self.fig.add_subplot(121)
        self.ax2 = self.fig.add_subplot(122)
        
        self.canvas_plot = FigureCanvasTkAgg(self.fig, master=self.tab_graphs)
        self.canvas_plot.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        f_bot = tk.Frame(self.tab_graphs, bg=PANEL_BG)
        f_bot.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        tk.Label(f_bot, text="🔄 Graphs auto-update after each simulation run", bg=PANEL_BG, fg=TEXT_SECONDARY).pack(side=tk.LEFT, padx=15)
        
        HoverButton(f_bot, BORDER_COLOR, BTN_HOVER, text="📥 Save Custom Figures", font=("Helvetica", 10), command=self._save_custom_graphs).pack(side=tk.RIGHT, padx=15)
        
        self._update_matplotlib_theme()
        self._draw_placeholder_graphs()

    def _update_matplotlib_theme(self):
        import matplotlib
        matplotlib.rcParams['text.color'] = TEXT_PRIMARY
        matplotlib.rcParams['axes.labelcolor'] = TEXT_PRIMARY
        matplotlib.rcParams['xtick.color'] = TEXT_PRIMARY
        matplotlib.rcParams['ytick.color'] = TEXT_PRIMARY
        matplotlib.rcParams['axes.facecolor'] = CARD_BG
        matplotlib.rcParams['axes.edgecolor'] = BORDER_COLOR
        matplotlib.rcParams['grid.color'] = BORDER_COLOR

    def _draw_placeholder_graphs(self):
        self.ax1.clear()
        self.ax1.text(0.5, 0.5, "Awaiting Data...", ha='center', va='center', color=TEXT_SECONDARY)
        self.ax1.set_title("QBER per Simulation Run", color=TEXT_PRIMARY)
        
        self.ax2.clear()
        self.ax2.text(0.5, 0.5, "Awaiting Data...", ha='center', va='center', color=TEXT_SECONDARY)
        self.ax2.set_title("Key Bit Distribution", color=TEXT_PRIMARY)
        self.canvas_plot.draw()

    def _update_live_graphs(self, current_run_stats):
        self.ax1.clear()
        self.ax2.clear()
        
        recent_runs = self.run_history[-5:]
        x_labels = [f"Run {r['id']}" for r in recent_runs]
        qbers = [r['qber'] for r in recent_runs]
        threshold = self.var_threshold.get()
        
        colors = [SUCCESS_COLOR if q <= threshold else DANGER_COLOR for q in qbers]
        
        bars = self.ax1.bar(x_labels, qbers, color=colors)
        self.ax1.axhline(threshold, color=WARN_COLOR, linestyle="--", linewidth=1.5, label="Threshold")
        self.ax1.set_title("QBER History (Last 5 Runs)")
        self.ax1.set_ylabel("QBER (%)")
        for bar in bars:
            yval = bar.get_height()
            self.ax1.text(bar.get_x() + bar.get_width()/2.0, yval, f'{yval:.1f}%', va='bottom', ha='center', color=TEXT_PRIMARY, fontsize=9)
            
        # Pie chart
        stats = current_run_stats
        total = stats['start_qubits']
        sifted = stats['sifted']
        discarded_basis = total - sifted
        sample = stats['sample']
        final = stats['final']
        lost_to_amp = sifted - sample - final
        
        labels = ['Discarded (Basis)', 'Sampled (QBER)', 'Lost (Privacy Amp)', 'Final Key']
        sizes = [discarded_basis, sample, max(0, lost_to_amp), final]
        pie_colors = [BORDER_COLOR, WARN_COLOR, IDLE_GRAY, SUCCESS_COLOR]
        
        # Filter 0s
        labels_f = [l for l,s in zip(labels, sizes) if s > 0]
        sizes_f = [s for s in sizes if s > 0]
        colors_f = [c for c,s in zip(pie_colors, sizes) if s > 0]
        
        if sizes_f:
            wedges, texts, autotexts = self.ax2.pie(sizes_f, labels=labels_f, colors=colors_f, autopct='%1.1f%%', startangle=90)
            for t in texts: t.set_color(TEXT_PRIMARY)
            for t in autotexts: t.set_color(BG_COLOR); t.set_fontweight('bold')
            self.ax2.set_title("Current Key Bit Distribution")
        else:
            self.ax2.text(0.5, 0.5, "No bits processed", ha='center', va='center')
            
        self.canvas_plot.draw()

    def _setup_statistics_tab(self):
        # ROW 1 - Stats Cards
        f_cards = tk.Frame(self.tab_stats, bg=PANEL_BG)
        f_cards.pack(fill=tk.X, pady=15, padx=15)
        
        self.lbls_stat = {}
        for i, title in enumerate(["TOTAL RUNS", "SUCCESSFUL", "ABORTED", "AVG QBER"]):
            f = tk.Frame(f_cards, bg=CARD_BG, highlightbackground=ACCENT_COLOR, highlightthickness=1)
            f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
            tk.Label(f, text=title, font=("Helvetica", 10), fg=TEXT_SECONDARY, bg=CARD_BG).pack(pady=(10, 0))
            lbl_val = tk.Label(f, text="0" if i<3 else "0.0%", font=("Helvetica", 28, "bold"), fg=TEXT_PRIMARY, bg=CARD_BG)
            lbl_val.pack(pady=(5, 10))
            self.lbls_stat[title] = lbl_val
            
        # ROW 2 - Treeview 
        f_tree = tk.Frame(self.tab_stats, bg=PANEL_BG)
        f_tree.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        cols = ('ID', 'Qubits', 'Eve', 'QBER', 'Status', 'Key Len')
        self.tree = ttk.Treeview(f_tree, columns=cols, show='headings')
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor=tk.CENTER, width=100)
            
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(f_tree, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # ROW 3 - Analysis
        f_anal = tk.Frame(self.tab_stats, bg=PANEL_BG)
        f_anal.pack(fill=tk.X, padx=15, pady=15)
        HoverButton(f_anal, BORDER_COLOR, DANGER_COLOR, text="Clear History", command=self._clear_history).pack(side=tk.LEFT)
        self.lbl_analysis = tk.Label(f_anal, text="(Run simulation to generate auto-analysis...)", font=("Helvetica", 10, "italic"), fg=TEXT_SECONDARY, bg=PANEL_BG, justify=tk.LEFT, wraplength=400)
        self.lbl_analysis.pack(side=tk.LEFT, padx=20)

    def _setup_right_panel(self):
        tk.Label(self.right_panel, text="🔑 SIMULATION RESULTS", font=("Helvetica", 12, "bold"), fg=ACCENT_COLOR, bg=CARD_BG).pack(pady=(15, 15))
        
        # SECTION 1 - Status Card
        self.f_status = tk.Frame(self.right_panel, bg=BG_COLOR, highlightbackground=BORDER_COLOR, highlightthickness=2)
        self.f_status.pack(fill=tk.X, padx=15, pady=5)
        self.lbl_status_icon = tk.Label(self.f_status, text="⬤", font=("Helvetica", 36), fg=TEXT_SECONDARY, bg=BG_COLOR)
        self.lbl_status_icon.pack(pady=(15,0))
        self.lbl_status_main = tk.Label(self.f_status, text="IDLE", font=("Helvetica", 16, "bold"), fg=TEXT_PRIMARY, bg=BG_COLOR)
        self.lbl_status_main.pack()
        self.lbl_status_sub = tk.Label(self.f_status, text="Waiting for input...", font=("Helvetica", 10), fg=TEXT_SECONDARY, bg=BG_COLOR)
        self.lbl_status_sub.pack(pady=(0,15))
        
        self.progress_bar = ttk.Progressbar(self.right_panel, orient=tk.HORIZONTAL, length=100, mode='determinate')

        # SECTION 2 - QBER Meter
        tk.Label(self.right_panel, text="QBER METER", font=("Helvetica", 10, "bold"), fg=TEXT_SECONDARY, bg=CARD_BG).pack(pady=(15,0))
        self.qber_canvas = tk.Canvas(self.right_panel, bg=CARD_BG, width=220, height=120, highlightthickness=0)
        self.qber_canvas.pack(pady=5)
        self._init_qber_gauge()

        # SECTION 3 - Key Information
        lf_key = ttk.LabelFrame(self.right_panel, text=" 🔑 KEY INFORMATION ")
        lf_key.pack(fill=tk.X, padx=15, pady=10)
        
        self.lbl_ki_qubits = tk.Label(lf_key, text="Initial Qubits:    --", bg=CARD_BG, fg=TEXT_PRIMARY)
        self.lbl_ki_qubits.pack(anchor="w", padx=10, pady=2)
        self.lbl_ki_sifted = tk.Label(lf_key, text="Sifted Key:        --", bg=CARD_BG, fg=TEXT_PRIMARY)
        self.lbl_ki_sifted.pack(anchor="w", padx=10, pady=2)
        self.lbl_ki_sample = tk.Label(lf_key, text="Sample Used:        --", bg=CARD_BG, fg=TEXT_PRIMARY)
        self.lbl_ki_sample.pack(anchor="w", padx=10, pady=2)
        self.lbl_ki_final = tk.Label(lf_key, text="Final Key Length:   --", bg=CARD_BG, fg=ACCENT_COLOR, font=("Helvetica", 10, "bold"))
        self.lbl_ki_final.pack(anchor="w", padx=10, pady=(2, 10))

        # SECTION 4 - Final Key
        tk.Label(self.right_panel, text="FINAL SECRET KEY", font=("Helvetica", 10, "bold"), fg=TEXT_SECONDARY, bg=CARD_BG).pack(pady=(5,0))
        f_keybox = tk.Frame(self.right_panel, bg=BG_COLOR, highlightbackground=BORDER_COLOR, highlightthickness=1)
        f_keybox.pack(fill=tk.BOTH, expand=True, padx=15, pady=(5,5))
        
        self.text_final_key = tk.Text(f_keybox, bg=BG_COLOR, fg=SUCCESS_COLOR, font=("Consolas", 11), height=5, width=25, bd=0, state=tk.DISABLED)
        self.text_final_key.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        f_key_btns = tk.Frame(self.right_panel, bg=CARD_BG)
        f_key_btns.pack(fill=tk.X, padx=15, pady=(0, 10))
        HoverButton(f_key_btns, BORDER_COLOR, ACCENT_COLOR, text="📋 Copy", command=self._copy_key).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,5))
        HoverButton(f_key_btns, BORDER_COLOR, SUCCESS_COLOR, text="💾 Save", command=self._export_key).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(5,0))

    def _init_qber_gauge(self):
        cv = self.qber_canvas
        # Draw arcs
        cv.create_arc(10, 10, 210, 210, start=0, extent=180, outline=BORDER_COLOR, width=15, style=tk.ARC)
        cv.create_arc(10, 10, 210, 210, start=126, extent=54, outline=SUCCESS_COLOR, width=15, style=tk.ARC) # 0-11% (11/35 * 180 = ~56 deg from left = start 180-56=124)
        # 11% to 18%
        cv.create_arc(10, 10, 210, 210, start=90, extent=36, outline=WARN_COLOR, width=15, style=tk.ARC) 
        # 18% to 35%
        cv.create_arc(10, 10, 210, 210, start=0, extent=90, outline=DANGER_COLOR, width=15, style=tk.ARC)
        
        # Center pin
        cv.create_oval(100, 100, 120, 120, fill=TEXT_PRIMARY)
        
        # Initial Needle at 0 (angle 180 left)
        self.needle = cv.create_line(110, 110, 25, 110, fill=TEXT_PRIMARY, width=3, arrow=tk.LAST)
        self.lbl_qber_val = cv.create_text(110, 135, text="0.0%", font=("Helvetica", 14, "bold"), fill=TEXT_PRIMARY)

    def _setup_status_bar(self):
        self.lbl_sb_dot = tk.Label(self.status_bar, text="●", fg=TEXT_SECONDARY, bg="#010409", font=("Helvetica", 10))
        self.lbl_sb_dot.pack(side=tk.LEFT, padx=(10,2))
        self.lbl_sb_status = tk.Label(self.status_bar, text="Ready", fg=TEXT_SECONDARY, bg="#010409")
        self.lbl_sb_status.pack(side=tk.LEFT)
        
        tk.Label(self.status_bar, text="| Protocol: BB84 |", fg=BORDER_COLOR, bg="#010409").pack(side=tk.LEFT, padx=10)
        self.lbl_sb_info = tk.Label(self.status_bar, text="Qubits: 256  |  QBER: --  |  Eve: Disabled", fg=TEXT_SECONDARY, bg="#010409")
        self.lbl_sb_info.pack(side=tk.LEFT)
        
        tk.Label(self.status_bar, text="Python 3 | tkinter", fg=BORDER_COLOR, bg="#010409").pack(side=tk.RIGHT, padx=10)
        self.lbl_sb_time = tk.Label(self.status_bar, text="00:00:00", fg=TEXT_SECONDARY, bg="#010409")
        self.lbl_sb_time.pack(side=tk.RIGHT)

    def update_time(self):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.lbl_sb_time.config(text=now)
        self._animate_header_dots()
        self.root.after(1000, self.update_time)

    def _animate_header_dots(self):
        if not self.is_running:
            for dot in self.header_dots:
                self.dots_canvas.itemconfig(dot, fill=IDLE_GRAY)
            return
            
        colors = [PANEL_BG, ACCENT_COLOR]
        self.dot_pulse_state = (self.dot_pulse_state + 1) % 3
        for i, dot in enumerate(self.header_dots):
            if i == self.dot_pulse_state:
                self.dots_canvas.itemconfig(dot, fill=ACCENT_COLOR)
            else:
                self.dots_canvas.itemconfig(dot, fill=IDLE_GRAY)

    # -------------------------------------------------------------------------
    # UI ACTIONS AND ANIMATIONS
    # -------------------------------------------------------------------------
    def _reset_gui(self):
        if self.is_running: return
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        self.lbl_anim_step.config(text="Awaiting Simulation Start...")
        self.lbl_status_icon.config(text="⬤", fg=TEXT_SECONDARY)
        self.lbl_status_main.config(text="IDLE", fg=TEXT_PRIMARY)
        self.lbl_status_sub.config(text="Waiting for input...")
        self.f_status.config(highlightbackground=BORDER_COLOR)
        self._update_qber_needle(0.0)
        
        self.text_final_key.config(state=tk.NORMAL)
        self.text_final_key.delete(1.0, tk.END)
        self.text_final_key.config(state=tk.DISABLED)
        
        self.lbl_ki_qubits.config(text="Initial Qubits:    --")
        self.lbl_ki_sifted.config(text="Sifted Key:        --")
        self.lbl_ki_sample.config(text="Sample Used:        --")
        self.lbl_ki_final.config(text="Final Key Length:   --")
        
        self._update_status_bar_info()

    def _update_status_bar_info(self):
        eve_st = f"Enabled ({self.var_intercept_rate.get()}%)" if self.var_eve_enabled.get() else "Disabled"
        qb = self.var_qubits.get()
        self.lbl_sb_info.config(text=f"Qubits: {qb}  |  QBER: {self.current_qber:.1f}%  |  Eve: {eve_st}")

    def _log_message(self, tag, message):
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S] ")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, timestamp, 'time')
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

    def _pulse_alert(self, widget, color1, color2, count):
        if count <= 0:
            widget.config(highlightbackground=color1)
            return
        current = widget.cget("highlightbackground")
        next_c = color2 if current == color1 else color1
        widget.config(highlightbackground=next_c)
        self.root.after(300, lambda: self._pulse_alert(widget, color1, color2, count-1))

    def _update_qber_needle(self, qber):
        self.qber_canvas.itemconfig(self.lbl_qber_val, text=f"{qber*100:.1f}%")
        # Max scale 35%
        val = min(qber*100, 35)
        # angle mapping from 180 (left, 0%) to 0 (right, 35%)
        angle_deg = 180 - (val / 35.0) * 180.0
        angle_rad = math.radians(angle_deg)
        cx, cy = 110, 110
        r = 85
        nx = cx + r * math.cos(angle_rad)
        ny = cy - r * math.sin(angle_rad)
        self.qber_canvas.coords(self.needle, cx, cy, nx, ny)

    def _animate_qber_needle(self, final_qber):
        steps = 20
        curr = []
        def step(i):
            if i > steps: return
            val = (final_qber / steps) * i
            self._update_qber_needle(val)
            self.root.after(50, lambda: step(i+1))
        step(1)

    def _animate_photons(self, is_eve_active):
        if not self.is_running:
            return
            
        cv = self.anim_canvas
        speed_mapping = {"Fast": 5, "Normal": 15, "Slow": 30}
        delay = speed_mapping.get(self.var_speed.get(), 15)
        
        # Spawn probability
        if random.random() < 0.2: # 20% chance to spawn a new photon per frame
            y_pos = random.randint(110, 130)
            p = cv.create_oval(160, y_pos-4, 168, y_pos+4, fill=ACCENT_COLOR, outline=ACCENT_COLOR)
            self._move_photon(p, is_eve_active, delay)
            
        self.root.after(delay * 5, lambda: self._animate_photons(is_eve_active))

    def _move_photon(self, p, is_eve_active, delay):
        if not self.is_running:
            self.anim_canvas.delete(p)
            return
            
        coords = self.anim_canvas.coords(p)
        if not coords: return
        x1, y1, x2, y2 = coords
        
        if is_eve_active and 290 < x1 < 310:
            self.anim_canvas.itemconfig(p, fill=DANGER_COLOR, outline=DANGER_COLOR)
            
        if x1 > 540:
            self.anim_canvas.delete(p)
        else:
            self.anim_canvas.move(p, 8, 0)
            self.root.after(delay, lambda: self._move_photon(p, is_eve_active, delay))

    def _show_popup(self, title, msg, is_success):
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.configure(bg=CARD_BG, highlightthickness=2, highlightbackground=SUCCESS_COLOR if is_success else DANGER_COLOR)
        
        # Position bottom right
        w, h = 300, 80
        x = self.root.winfo_x() + self.root.winfo_width() - w - 20
        y = self.root.winfo_y() + self.root.winfo_height() - h - 20
        popup.geometry(f"{w}x{h}+{x}+{y}")
        
        tk.Label(popup, text=title, font=("Helvetica", 11, "bold"), fg=SUCCESS_COLOR if is_success else DANGER_COLOR, bg=CARD_BG).pack(pady=(10,5))
        tk.Label(popup, text=msg, font=("Helvetica", 10), fg=TEXT_PRIMARY, bg=CARD_BG).pack()
        
        # Auto dismiss
        self.root.after(2500 if is_success else 3500, popup.destroy)

    # -------------------------------------------------------------------------
    # SIMULATION EXECUTION
    # -------------------------------------------------------------------------
    def run_simulation_thread(self):
        if self.is_running:
            messagebox.showwarning("Simulation Running", "A simulation is already in progress.")
            return
            
        self.is_running = True
        self.notebook.select(self.tab_protocol)
        self._reset_gui()
        self.is_running = True # Reset clears it, reset it back
        
        self.btn_run.config(state=tk.DISABLED, bg=IDLE_GRAY)
        self.lbl_head_status.config(text="SIMULATION RUNNING...")
        
        self.lbl_status_icon.config(text="⟳", fg=ACCENT_COLOR) # Using simple character rotation or just display
        self.lbl_status_main.config(text="RUNNING")
        self.lbl_status_sub.config(text="Executing protocol steps...")
        self.lbl_sb_dot.config(fg=WARN_COLOR)
        self.lbl_sb_status.config(text="Running...")
        
        self.progress_bar.pack(pady=10, fill=tk.X, padx=20)
        self.progress_bar['value'] = 0
        
        # Eve visuals setup
        if self.var_eve_enabled.get():
            self.anim_canvas.itemconfig(self.eve_rect, outline=DANGER_COLOR, fill="#3d1418")
            self.anim_canvas.itemconfig(self.eve_text, fill=DANGER_COLOR)
        else:
            self.anim_canvas.itemconfig(self.eve_rect, outline=IDLE_GRAY, fill=CARD_BG)
            self.anim_canvas.itemconfig(self.eve_text, fill=IDLE_GRAY)
            
        # Start photon animation loop
        self._animate_photons(self.var_eve_enabled.get())
        
        thread = threading.Thread(target=self._simulation_worker)
        thread.daemon = True
        thread.start()

    def _sleep_scaled(self, multiplier=1.0):
        base = {"Fast": 0.2, "Normal": 0.6, "Slow": 1.5}.get(self.var_speed.get(), 0.6)
        time.sleep(base * multiplier)

    def _update_ui(self, fn, *args):
        try:
            self.root.after(0, lambda: fn(*args))
        except Exception:
            pass

    def _sim_set_step(self, msg, prog):
        self._update_ui(self.lbl_anim_step.config, {"text": msg, "fg": ACCENT_COLOR})
        self._update_ui(self.progress_bar.configure, {"value": prog})

    def _simulation_worker(self):
        try:
            nq = self.var_qubits.get()
            thresh = self.var_threshold.get() / 100.0
            eve_on = self.var_eve_enabled.get()
            prob = self.var_intercept_rate.get() / 100.0
            s_size = self.var_sample_size.get()
            
            self._update_ui(self._update_status_bar_info)

            # Stage 1
            self._sim_set_step(f"⚡ Alice is generating {nq} random quantum bits...", 10)
            self._update_ui(self._log_message, 'success', f"✓ Alice generated {nq} bits")
            self._sleep_scaled()
            
            alice = Alice(nq)
            alice.generate_bits()
            alice.generate_bases()
            self._sim_set_step("⚡ Alice is encoding photons...", 20)
            alice.encode_photons()
            self._update_ui(self._log_message, 'success', f"✓ Alice encoded photons")
            self._sleep_scaled()
            
            stream = alice.photon_states
            
            # Stage 2
            self._sim_set_step("⚡ Quantum channel established...", 35)
            self._update_ui(self._log_message, 'success', f"✓ Quantum channel established")
            self._sleep_scaled()
            
            if eve_on:
                self._sim_set_step(f"⚠ Eve intercepting photons ({prob*100:.0f}%)...", 50)
                self._update_ui(self._log_message, 'warning', f"⚠ Eve intercepting photons ({prob*100:.0f}%)")
                eve = Eve(intercept_probability=prob)
                stream = eve.intercept(stream)
                self._sleep_scaled(1.5)
                
            # Stage 3
            self._sim_set_step("⚡ Bob measuring photons...", 65)
            bob = Bob(nq)
            bob.generate_bases()
            bob.measure_photons(stream)
            self._update_ui(self._log_message, 'success', f"✓ Bob measured photons")
            self._sleep_scaled()
            
            # Stage 4
            self._sim_set_step("⚡ Performing basis sifting...", 80)
            matching_indices, _ = bob.sift_key(alice.bases, bob.bases)
            alice_sifted = alice.get_sifted_key(matching_indices)
            bob_sifted = list(bob.raw_key)
            
            sifted_len = len(alice_sifted)
            self._update_ui(self._log_message, 'success', f"✓ Basis sifting complete ({sifted_len} matching)")
            self._sleep_scaled()
            
            # Stage 5
            self._sim_set_step("⚡ Estimating QBER...", 90)
            qber, sample_indices, mismatches = QBER.calculate_qber(alice_sifted, bob_sifted, sample_size=s_size)
            sample_used = len(sample_indices)
            self.current_qber = qber
            
            self._update_ui(self._animate_qber_needle, qber)
            
            q_str = f"{qber*100:.2f}%"
            if qber > thresh:
                self._update_ui(self._log_message, 'error', f"✗ QBER = {q_str} > {thresh*100:.0f}% threshold")
            else:
                self._update_ui(self._log_message, 'success', f"✓ QBER = {q_str} ≤ {thresh*100:.0f}% threshold")
            self._sleep_scaled(1.5)
            
            # Stage 6
            eve_detected, decision = QBER.detect_eavesdropper(qber, thresh)
            
            final_key = []
            final_len = 0
            if eve_detected:
                status_str = "ABORTED"
                self._sim_set_step("❌ EAVESDROPPER DETECTED! PROTOCOL ABORTED.", 100)
                self._update_ui(self._log_message, 'error', "✗ EAVESDROPPER DETECTED! ABORTED")
            else:
                self._sim_set_step("⚡ Performing privacy amplification...", 95)
                self._sleep_scaled()
                final_key = QBER.privacy_amplification(alice_sifted, qber)
                final_len = len(final_key)
                status_str = "GENERATED"
                self._sim_set_step("✅ SECURE KEY GENERATED SUCCESSFULLY.", 100)
                self._update_ui(self._log_message, 'success', f"✓ Privacy amplification applied. Final key: {final_len} bits.")
            
            # Assemble stats container for this run
            run_stats = {
                "id": len(self.run_history) + 1,
                "start_qubits": nq,
                "eve_str": f"{prob*100:.0f}%" if eve_on else "No",
                "qber": qber * 100.0,
                "status": "❌ ABORTED" if eve_detected else "✅ GENERATED",
                "key_len": final_len,
                "sifted": sifted_len,
                "sample": sample_used,
                "final": final_len,
                "is_success": not eve_detected,
                "final_key_arr": final_key
            }
            self.run_history.append(run_stats)
            self.final_key_str = "".join(str(b) for b in final_key) if final_len > 0 else ""
            
            self._update_ui(self._finish_simulation_ui, run_stats)

        except Exception as e:
            err = traceback.format_exc()
            self._update_ui(self._log_message, 'error', f"SIMULATION CRASH: {str(e)}")
            self._update_ui(lambda: messagebox.showerror("Error", f"Simulation crashed:\n{err}"))
            self._update_ui(self._emergency_reset)

    def _finish_simulation_ui(self, stats):
        self.is_running = False
        self.progress_bar.pack_forget()
        self.btn_run.config(state=tk.NORMAL, bg=ACCENT_COLOR)
        
        self.lbl_head_status.config(text="SIMULATION IDLE")
        
        if stats['is_success']:
            self._pulse_alert(self.f_status, SUCCESS_COLOR, BORDER_COLOR, 5)
            self.lbl_status_icon.config(text="✅", fg=SUCCESS_COLOR)
            self.lbl_status_main.config(text="KEY SECURE", fg=SUCCESS_COLOR)
            self.lbl_status_sub.config(text=f"Status: SECURE ✓")
            self.lbl_sb_dot.config(fg=SUCCESS_COLOR)
            self.lbl_sb_status.config(text="Key Generated")
            self._show_popup("✅ Simulation Complete", f"Key generated: {stats['key_len']} bits\nQBER: {stats['qber']:.2f}%", True)
        else:
            self._pulse_alert(self.f_status, DANGER_COLOR, BORDER_COLOR, 8)
            self.lbl_status_icon.config(text="❌", fg=DANGER_COLOR)
            self.lbl_status_main.config(text="EVE DETECTED!", fg=DANGER_COLOR)
            self.lbl_status_sub.config(text=f"Status: ABORTED ✗")
            self.lbl_sb_dot.config(fg=DANGER_COLOR)
            self.lbl_sb_status.config(text="Aborted")
            self._show_popup("⚠️ Security Alert!", f"Eavesdropper detected!\nQBER: {stats['qber']:.2f}% > Threshold", False)
            
        # Update Info cards
        self.lbl_ki_qubits.config(text=f"Initial Qubits:    {stats['start_qubits']}")
        self.lbl_ki_sifted.config(text=f"Sifted Key:        {stats['sifted']}")
        self.lbl_ki_sample.config(text=f"Sample Used:        {stats['sample']}")
        self.lbl_ki_final.config(text=f"Final Key Length:   {stats['final']}")
        
        # Display Key
        self.text_final_key.config(state=tk.NORMAL)
        self.text_final_key.delete(1.0, tk.END)
        if stats['is_success']:
            # Format in blocks of 8
            k = self.final_key_str
            formatted_key = " ".join(k[i:i+8] for i in range(0, len(k), 8))
            self.text_final_key.insert(tk.END, formatted_key)
            self.text_final_key.config(fg=SUCCESS_COLOR)
        else:
            self.text_final_key.insert(tk.END, "🔒 NO KEY GENERATED")
            self.text_final_key.config(fg=DANGER_COLOR)
        self.text_final_key.config(state=tk.DISABLED)

        # Update History & Graphs
        self._update_status_bar_info()
        self._update_statistics_tab()
        self._update_live_graphs(stats)
        
        # Reset Eve visual if she was on
        if self.var_eve_enabled.get():
            self.anim_canvas.itemconfig(self.eve_rect, outline=IDLE_GRAY, fill=CARD_BG)
            self.anim_canvas.itemconfig(self.eve_text, fill=IDLE_GRAY)

    def _emergency_reset(self):
        self.is_running = False
        self.btn_run.config(state=tk.NORMAL, bg=ACCENT_COLOR)
        self.lbl_head_status.config(text="ERROR")

    # -------------------------------------------------------------------------
    # STATISTICS AND DISPLAY UDPATES
    # -------------------------------------------------------------------------
    def _update_statistics_tab(self):
        tot = len(self.run_history)
        succ = sum(1 for r in self.run_history if r['is_success'])
        abrt = tot - succ
        avg_q = sum(r['qber'] for r in self.run_history) / tot if tot > 0 else 0.0
        
        # Simple count-up anim simulation (just set it here to be robust)
        self.lbls_stat["TOTAL RUNS"].config(text=str(tot))
        self.lbls_stat["SUCCESSFUL"].config(text=f"{succ}\n✅ {int(succ/tot*100) if tot>0 else 0}%", font=("Helvetica", 14, "bold"))
        self.lbls_stat["ABORTED"].config(text=f"{abrt}\n❌ {int(abrt/tot*100) if tot>0 else 0}%", font=("Helvetica", 14, "bold"))
        self.lbls_stat["AVG QBER"].config(text=f"{avg_q:.1f}%")
        
        # Add to Treeview
        r = self.run_history[-1]
        item = self.tree.insert("", 0, values=(r['id'], r['start_qubits'], r['eve_str'], f"{r['qber']:.1f}%", r['status'], f"{r['key_len']} bits"))
        self.tree.selection_set(item)
        
        # Update Analysis text
        anal_text = f"Analysis of Run {r['id']}: With {r['start_qubits']} qubits "
        anal_text += f"and Eve {'active' if r['eve_str']!='No' else 'inactive'}, "
        anal_text += f"the protocol achieved a QBER of {r['qber']:.1f}%. "
        if r['is_success']:
            anal_text += f"This is below the threshold. A final key of length {r['final']} bits was generated securely."
        else:
            anal_text += f"This exceeds the threshold. The presence of an eavesdropper was detected and key generation was aborted."
            
        self.lbl_analysis.config(text=anal_text)

    def _clear_history(self):
        self.run_history.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.lbls_stat["TOTAL RUNS"].config(text="0")
        self.lbls_stat["SUCCESSFUL"].config(text="0\n✅ 0%", font=("Helvetica", 14, "bold"))
        self.lbls_stat["ABORTED"].config(text="0\n❌ 0%", font=("Helvetica", 14, "bold"))
        self.lbls_stat["AVG QBER"].config(text="0.0%")
        self.lbl_analysis.config(text="(History cleared)")
        self._draw_placeholder_graphs()

    # -------------------------------------------------------------------------
    # EXPORTS AND EXTERNAL CALLS
    # -------------------------------------------------------------------------
    def _copy_key(self):
        if not self.final_key_str:
            messagebox.showinfo("Copy", "No key generated to copy.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.final_key_str)
        self.root.update()
        messagebox.showinfo("Copied", "Secret key copied to clipboard!")

    def _export_key(self):
        if not self.final_key_str:
            messagebox.showinfo("Save", "No key generated to save.")
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".txt", title="Save Secret Key", 
                                                initialfile="bb84_secret_key.txt")
        if filepath:
            with open(filepath, 'w') as f:
                f.write(self.final_key_str)
            messagebox.showinfo("Success", f"Key saved to:\n{filepath}")

    def _generate_graphs_external(self):
        threading.Thread(target=self._generate_graphs_worker, daemon=True).start()
        
    def _generate_graphs_worker(self):
        self._update_ui(self.lbl_head_status.config, {"text": "GENERATING EXTERNAL GRAPHS...", "fg":WARN_COLOR})
        try:
            VIS.generate_all_graphs()
            self._update_ui(self._show_popup, "📊 Graphs Saved!", "→ results/ folder\n4 files created", True)
        except Exception as e:
            self._update_ui(messagebox.showerror, "Generation Error", f"Failed to generate graphs:\n{str(e)}")
        finally:
            self._update_ui(self.lbl_head_status.config, {"text": "SIMULATION IDLE", "fg":ACCENT_COLOR})

    def _save_custom_graphs(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".png", title="Save Live Graphs", 
                                                initialfile="live_graphs.png")
        if filepath:
            self.fig.savefig(filepath, facecolor=self.fig.get_facecolor(), 
                             edgecolor='none', bbox_inches='tight')
            messagebox.showinfo("Success", f"Custom live graphs saved to:\n{filepath}")

    def _run_quick_demo(self):
        """Run 2 most common scenarios: Safe and Full Eve."""
        if self.is_running: return
        scenarios = [
            {"qubits": 256, "eve": False, "rate": 0},
            {"qubits": 256, "eve": True, "rate": 100}
        ]
        self._run_multi_scenarios(scenarios)

    def _run_full_demo(self):
        """Run all 5 standard scenarios."""
        if self.is_running: return
        scenarios = [
            {"qubits": 256, "eve": False, "rate": 0},
            {"qubits": 256, "eve": True, "rate": 25},
            {"qubits": 256, "eve": True, "rate": 50},
            {"qubits": 256, "eve": True, "rate": 75},
            {"qubits": 256, "eve": True, "rate": 100}
        ]
        self._run_multi_scenarios(scenarios)

    def _run_multi_scenarios(self, scenarios):
        self.var_speed.set("Fast")
        def run_next(idx):
            if idx >= len(scenarios):
                messagebox.showinfo("Demo Complete", "All demo scenarios have been executed.")
                return
            s = scenarios[idx]
            self.var_qubits.set(s["qubits"])
            self._snap_qubits(s["qubits"])
            self.var_eve_enabled.set(s["eve"])
            self.var_intercept_rate.set(s["rate"])
            self._toggle_eve()
            
            self.run_simulation_thread()
            
            def check():
                if self.is_running:
                    self.root.after(500, check)
                else:
                    self.root.after(1000, lambda: run_next(idx + 1))
            check()
        run_next(0)

    def _run_10x_demo(self):
        if self.is_running: return
        self.var_speed.set("Fast")
        def multi_run(count):
            if count <= 0: return
            self.run_simulation_thread()
            # Check periodically if run finished
            def check():
                if self.is_running:
                    self.root.after(500, check)
                else:
                    multi_run(count - 1)
            check()
        multi_run(10)

    def _toggle_theme(self):
        """Toggle between Dark and Light mode (Bonus Feature)."""
        new_theme = "Light" if self.var_theme.get() == "Dark" else "Dark"
        self.var_theme.set(new_theme)
        
        # Define Palettes
        if new_theme == "Dark":
            bg, panel, card, text, sec = BG_COLOR, PANEL_BG, CARD_BG, TEXT_PRIMARY, TEXT_SECONDARY
        else:
            bg, panel, card, text, sec = "#f0f2f5", "#ffffff", "#ffffff", "#1c1e21", "#606770"
            
        # Update Styles
        style = ttk.Style()
        style.configure("TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("Card.TFrame", background=card)
        style.configure("TLabel", background=card, foreground=text)
        style.configure("Header.TLabel", background=panel, foreground=text)
        style.configure("SubHeader.TLabel", background=panel, foreground=sec)
        style.configure("TLabelframe", background=card)
        style.configure("TLabelframe.Label", background=card, foreground=ACCENT_COLOR)
        style.configure("TNotebook", background=panel)
        style.configure("TNotebook.Tab", background=card, foreground=text)
        style.map("TNotebook.Tab", background=[("selected", ACCENT_COLOR)], foreground=[("selected", bg)])
        
        style.configure("Treeview", background=card, foreground=text, fieldbackground=card)
        style.configure("Treeview.Heading", background=panel, foreground=text)
        
        # Recursively update all non-ttk widgets
        self._apply_theme_recursive(self.root, bg, panel, card, text, sec)
        
        # Specific overrides
        self.header_frame.config(bg=panel)
        self.status_bar.config(bg="#010409" if new_theme == "Dark" else "#f0f2f5")
        self.lbl_head_status.config(bg=panel)
        self.dots_canvas.config(bg=panel)
        self.log_text.config(bg="#010409" if new_theme == "Dark" else "#f9f9f9", fg=text)
        self.text_final_key.config(bg=BG_COLOR if new_theme == "Dark" else "#f9f9f9")
        self.anim_canvas.config(bg=BG_COLOR if new_theme == "Dark" else "#e4e6eb")
        self.qber_canvas.config(bg=card if new_theme == "Dark" else "#ffffff")
        self.f_status.config(bg=BG_COLOR if new_theme == "Dark" else "#f0f2f5")
        self.lbl_status_icon.config(bg=BG_COLOR if new_theme == "Dark" else "#f0f2f5")
        self.lbl_status_main.config(bg=BG_COLOR if new_theme == "Dark" else "#f0f2f5")
        self.lbl_status_sub.config(bg=BG_COLOR if new_theme == "Dark" else "#f0f2f5")
        
        # Redraw matplotlib if needed
        self.fig.set_facecolor(panel)
        self.canvas_plot.draw()

    def _apply_theme_recursive(self, parent, bg, panel, card, text, sec):
        for child in parent.winfo_children():
            name = child.winfo_class()
            try:
                if name == "Frame" or name == "LabelFrame":
                    # Check if it was meant to be a panel or card based on existing bg
                    curr_bg = child.cget("bg")
                    if curr_bg == PANEL_BG or curr_bg == "#ffffff": child.config(bg=panel)
                    elif curr_bg == CARD_BG or curr_bg == "#ffffff": child.config(bg=card)
                    else: child.config(bg=bg)
                elif name == "Label":
                    curr_bg = child.cget("bg")
                    if curr_bg == PANEL_BG or curr_bg == "#ffffff": child.config(bg=panel, fg=text)
                    elif curr_bg == CARD_BG or curr_bg == "#ffffff": child.config(bg=card, fg=text)
                    elif curr_bg == BG_COLOR or curr_bg == "#f0f2f5": child.config(bg=bg, fg=text)
                elif name == "Button":
                    if not isinstance(child, HoverButton):
                        child.config(bg=card, fg=text)
                elif name == "Text":
                    pass # Handled specifically
            except Exception:
                pass
            self._apply_theme_recursive(child, bg, panel, card, text, sec)

    # -------------------------------------------------------------------------
    # POPUPS
    # -------------------------------------------------------------------------
    def _show_about(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("About BB84 Simulator")
        dialog.geometry("600x400")
        dialog.configure(bg=PANEL_BG)
        self._center_toplevel(dialog, 600, 400)
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="BB84 QKD SIMULATION v1.0", font=("Helvetica", 16, "bold"), fg=ACCENT_COLOR, bg=PANEL_BG).pack(pady=(20, 5))
        tk.Label(dialog, text="Secure Communication Channel Simulator", font=("Helvetica", 12), fg=TEXT_SECONDARY, bg=PANEL_BG).pack(pady=(0, 20))
        
        f = tk.Frame(dialog, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        f.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        text = """
DTI Project — Computer Science Engineering
Under guidance of: Ms. Rashi Shay

Team Members:
• Shimesh Gupta      (1/24/SET/BCS/261)
• Abhinikesh
• Ayush Parasher     (1/24/SET/BCS/233)
• Shivam Mishra
• Preeti Sharma

Built with: Python 3 | tkinter | matplotlib
Protocol: Bennett-Brassard 1984 (BB84)
"""
        tk.Label(f, text=text, font=("Consolas", 12), fg=TEXT_PRIMARY, bg=CARD_BG, justify=tk.LEFT).pack(pady=10, padx=20, anchor="w")
        HoverButton(dialog, BORDER_COLOR, BTN_HOVER, text="Close", font=("Helvetica", 11), command=dialog.destroy, width=15).pack(pady=15)

    def _show_theory(self):
        messagebox.showinfo("BB84 Theory", "In the BB84 Quantum Key Distribution protocol, Alice sends polarized photons "
                            "to Bob across a quantum channel. The No-Cloning Theorem prevents Eve from copying unknown "
                            "quantum states, and measurements alter the state. Alice and Bob check a sample of sifted bits "
                            "to find the Quantum Bit Error Rate (QBER). A QBER > 11% proves an eavesdropper's presence.")

    def _center_toplevel(self, top, w, h):
        top.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        top.geometry(f"{w}x{h}+{x}+{y}")


if __name__ == "__main__":
    root = tk.Tk()
    app = QKDSimulatorGUI(root)
    root.mainloop()
