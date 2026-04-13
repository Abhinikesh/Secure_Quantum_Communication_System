"""
visualize.py - Part 6 of 7: Visualization for the BB84 QKD Simulation
=======================================================================

Generates four publication-quality figures that illustrate the BB84
protocol's behaviour across a range of conditions.

Figures produced
----------------
1. results/qber_comparison.png
        Bar chart of average QBER for five eavesdropping intensities.
2. results/qber_vs_qubits.png
        Dual-axis line graph — QBER and key length vs qubit count.
3. results/protocol_flow.png
        Matplotlib-drawn flowchart of the full BB84 protocol.
4. results/statistics.png
        Histogram + box-plot of QBER distributions over 50 runs.

Usage:
    python3 visualize.py

Requirements:
    pip install matplotlib numpy
    alice.py, bob.py, eve.py, qber.py must be in the same directory.

Style conventions:
    Eve / insecure  → red   (#e74c3c)
    No Eve / secure → green (#2ecc71)
    Threshold line  → orange dashed (#e67e22)
    Neutral steps   → steel-blue (#2980b9)
"""

import os
import warnings

import numpy as np
import matplotlib
matplotlib.use("Agg")                   # Non-interactive backend — safe for scripts
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from qber import run_full_protocol

# ======================================================================
# Constants — colour palette & output settings
# ======================================================================
C_GREEN     = "#2ecc71"   # No-Eve / secure
C_GREEN_DK  = "#27ae60"   # Dark green for final key step
C_RED       = "#e74c3c"   # Eve / insecure
C_ORANGE    = "#e67e22"   # Security threshold
C_BLUE      = "#2980b9"   # Alice / Bob protocol steps
C_YELLOW    = "#f1c40f"   # Decision diamond
C_GRAY      = "#95a5a6"   # Neutral channel steps
C_BG        = "#1a1a2e"   # Dark background for flowchart
C_WHITE     = "#ecf0f1"   # Light text on dark background

DPI         = 150
RESULTS_DIR = "results"

# ======================================================================
# Style bootstrap
# ======================================================================
def _apply_style():
    """Apply a consistent matplotlib style, falling back gracefully."""
    for style_name in ("seaborn-v0_8-darkgrid", "seaborn-darkgrid", "ggplot"):
        try:
            plt.style.use(style_name)
            return
        except OSError:
            continue
    # No recognised style found — use safe matplotlib defaults
    plt.rcParams.update({
        "axes.facecolor":  "#f8f9fa",
        "axes.edgecolor":  "#dee2e6",
        "axes.grid":       True,
        "grid.color":      "#dee2e6",
        "grid.linestyle":  "--",
        "figure.facecolor":"white",
    })

_apply_style()

# Typography
plt.rcParams.update({
    "font.family":      "DejaVu Sans",
    "axes.titlesize":   14,
    "axes.titleweight": "bold",
    "axes.labelsize":   12,
    "xtick.labelsize":  10,
    "ytick.labelsize":  10,
    "legend.fontsize":  10,
    "figure.titlesize": 15,
})


# ======================================================================
# Helper: ensure output directory exists
# ======================================================================
def _ensure_results_dir():
    """Create the results/ directory if it does not already exist."""
    os.makedirs(RESULTS_DIR, exist_ok=True)


# ======================================================================
# Helper: run scenario N times and return average QBER + key length
# ======================================================================
def _avg_results(num_qubits: int, eve: bool, prob: float,
                 runs: int = 10) -> tuple:
    """
    Run run_full_protocol() `runs` times and return (mean_qber, mean_key_len).

    Suppresses the per-run stdout output from sift_key() by redirecting
    stdout temporarily.

    Args:
        num_qubits (int):   Qubit count per run.
        eve        (bool):  Whether Eve is active.
        prob       (float): Eve's interception probability.
        runs       (int):   Number of independent runs to average.

    Returns:
        tuple: (mean_qber: float, mean_key_length: float)
    """
    import io, sys

    qbers     = []
    key_lens  = []

    for _ in range(runs):
        # Suppress protocol stdout (sift-key prints, QBER reports, etc.)
        suppress = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout  = suppress
        try:
            res = run_full_protocol(
                num_qubits     = num_qubits,
                eve_present    = eve,
                intercept_prob = prob,
            )
        finally:
            sys.stdout = old_stdout

        qbers.append(res["qber"])
        key_lens.append(res["final_key_length"])

    return float(np.mean(qbers)), float(np.mean(key_lens))


# ======================================================================
# GRAPH 1 — QBER Comparison Bar Chart
# ======================================================================
def plot_qber_comparison():
    """
    Bar chart of average QBER across five eavesdropping intensities.

    Scenarios
    ---------
    "No Eve"  → Eve intercepts 0 %  of photons
    "Eve 25%" → Eve intercepts 25 % of photons
    "Eve 50%" → Eve intercepts 50 % of photons
    "Eve 75%" → Eve intercepts 75 % of photons
    "Eve 100%"→ Eve intercepts 100% of photons

    Each scenario is run 10 times; the mean QBER is plotted.
    A horizontal dashed line marks the 11 % security threshold.

    Saves: results/qber_comparison.png
    """
    THRESHOLD = 0.11
    RUNS      = 10

    scenarios = [
        ("No Eve",   False, 0.00),
        ("Eve 25%",  True,  0.25),
        ("Eve 50%",  True,  0.50),
        ("Eve 75%",  True,  0.75),
        ("Eve 100%", True,  1.00),
    ]

    labels  = []
    qbers   = []
    colors  = []

    print("  Collecting data for Graph 1 (this may take a moment)...")
    for label, eve, prob in scenarios:
        mean_qber, _ = _avg_results(256, eve, prob, runs=RUNS)
        labels.append(label)
        qbers.append(mean_qber * 100)           # Convert to %
        colors.append(C_RED if mean_qber > THRESHOLD else C_GREEN)
        print(f"    {label:10s} → avg QBER = {mean_qber * 100:.2f}%")

    # ---- Plot --------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("white")

    x      = np.arange(len(labels))
    bars   = ax.bar(x, qbers, color=colors, width=0.55,
                    edgecolor="white", linewidth=1.5, zorder=3)

    # Value labels on top of each bar
    for bar, val in zip(bars, qbers):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.4,
            f"{val:.1f}%",
            ha="center", va="bottom",
            fontsize=11, fontweight="bold",
            color="#2c3e50",
        )

    # Security threshold line
    ax.axhline(
        THRESHOLD * 100, color=C_ORANGE, linestyle="--",
        linewidth=2.2, zorder=4, label=f"Security Threshold ({THRESHOLD*100:.0f}%)"
    )

    # Annotation text box
    ax.text(
        0.98, 0.97,
        "Bars above threshold → Protocol ABORTS",
        transform=ax.transAxes, ha="right", va="top",
        fontsize=9.5, color=C_RED,
        bbox=dict(boxstyle="round,pad=0.4", fc="#ffeeed", ec=C_RED, alpha=0.85),
    )

    # Shaded danger zone
    ax.axhspan(THRESHOLD * 100, 40, alpha=0.06, color=C_RED, zorder=1)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_xlim(-0.5, len(labels) - 0.5)
    ax.set_ylim(0, 38)
    ax.set_xlabel("Eavesdropping Scenario", fontsize=12, labelpad=8)
    ax.set_ylabel("Average QBER (%)", fontsize=12, labelpad=8)
    ax.set_title("QBER vs Eavesdropping Intensity\n"
                 r"(average of 10 independent runs, $n=256$ qubits)",
                 fontsize=14, fontweight="bold", pad=14)

    # Legend
    legend_handles = [
        mpatches.Patch(color=C_GREEN, label="Secure (QBER ≤ 11%)"),
        mpatches.Patch(color=C_RED,   label="Insecure (QBER > 11%)"),
        plt.Line2D([0], [0], color=C_ORANGE, linestyle="--",
                   linewidth=2, label="Security Threshold (11%)"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", framealpha=0.9)

    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "qber_comparison.png")
    plt.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close()
    print(f"  ✓ Saved → {path}")
    return path


# ======================================================================
# GRAPH 2 — QBER and Key Length vs Qubit Count
# ======================================================================
def plot_qber_vs_qubit_count():
    """
    Dual-axis line graph: QBER (left) and final key length (right) vs qubit count.

    Three curves are plotted:
      • QBER without Eve  (green solid)   — should stay near 0 %
      • QBER with Eve 100%(red solid)     — should hover around 25 %
      • Key length no Eve (green dashed)  — grows with qubit count
      • Key length Eve    (red dashed)    — stays 0 (aborted)

    Each (qubit_count, scenario) pair is averaged over 5 runs.

    Saves: results/qber_vs_qubits.png
    """
    QUBIT_COUNTS = [64, 128, 256, 512, 1024]
    RUNS         = 5
    THRESHOLD    = 0.11

    no_eve_qbers   = []
    eve_qbers      = []
    no_eve_keys    = []
    eve_keys       = []

    print("  Collecting data for Graph 2 (this may take a moment)...")
    for n in QUBIT_COUNTS:
        q_no, k_no = _avg_results(n, False, 0.0, runs=RUNS)
        q_ev, k_ev = _avg_results(n, True,  1.0, runs=RUNS)
        no_eve_qbers.append(q_no * 100)
        no_eve_keys.append(k_no)
        eve_qbers.append(q_ev * 100)
        eve_keys.append(k_ev)
        print(f"    n={n:4d}  no-Eve QBER={q_no*100:.1f}%  "
              f"key={k_no:.1f}  |  Eve QBER={q_ev*100:.1f}%  key={k_ev:.1f}")

    fig, ax1 = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("white")

    # ---- Left y-axis: QBER ------------------------------------------
    lw = 2.5
    ax1.plot(QUBIT_COUNTS, no_eve_qbers, color=C_GREEN, marker="o",
             linewidth=lw, markersize=8, label="QBER — No Eve", zorder=4)
    ax1.plot(QUBIT_COUNTS, eve_qbers, color=C_RED, marker="s",
             linewidth=lw, markersize=8, label="QBER — Full Eve (100%)", zorder=4)
    ax1.axhline(THRESHOLD * 100, color=C_ORANGE, linestyle="--",
                linewidth=2, label=f"Security Threshold ({THRESHOLD*100:.0f}%)", zorder=3)
    ax1.set_xlabel("Number of Qubits", fontsize=12, labelpad=8)
    ax1.set_ylabel("Average QBER (%)", fontsize=12, color="#2c3e50", labelpad=8)
    ax1.set_ylim(-1, 35)
    ax1.tick_params(axis="y", labelcolor="#2c3e50")
    ax1.set_xticks(QUBIT_COUNTS)

    # ---- Right y-axis: Key length ------------------------------------
    ax2 = ax1.twinx()
    ax2.plot(QUBIT_COUNTS, no_eve_keys, color=C_GREEN, marker="^",
             linewidth=lw, linestyle="--", markersize=8,
             label="Key Length — No Eve", zorder=4)
    ax2.plot(QUBIT_COUNTS, eve_keys, color=C_RED, marker="v",
             linewidth=lw, linestyle="--", markersize=8,
             label="Key Length — Full Eve", zorder=4)
    ax2.set_ylabel("Final Key Length (bits)", fontsize=12,
                   color="#2c3e50", labelpad=8)
    ax2.set_ylim(0, max(no_eve_keys) * 1.3 + 10)
    ax2.tick_params(axis="y", labelcolor="#2c3e50")

    # ---- Combined legend (both axes) ---------------------------------
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2,
               loc="upper left", framealpha=0.92, fontsize=10)

    ax1.set_title(
        "Effect of Qubit Count on QBER and Final Key Length\n"
        r"(average of 5 runs per data point)",
        fontsize=14, fontweight="bold", pad=14,
    )

    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "qber_vs_qubits.png")
    plt.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close()
    print(f"  ✓ Saved → {path}")
    return path


# ======================================================================
# GRAPH 3 — Protocol Flowchart
# ======================================================================
def plot_protocol_flowchart():
    """
    Draw the complete BB84 protocol flowchart using matplotlib patches.

    Boxes represent protocol steps; diamonds represent decisions.
    Two branches diverge at "Eve intercepts?" and reconverge at
    Bob's measurement step.  A second decision at QBER > 11% leads
    either to ABORT or to privacy amplification and key generation.

    Saves: results/protocol_flow.png
    """

    fig, ax = plt.subplots(figsize=(10, 16))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 16)
    ax.axis("off")

    # ------------------------------------------------------------------
    # Helper lambdas
    # ------------------------------------------------------------------
    def rect(cx, cy, w, h, color, text, fontsize=9.5, text_color="white",
             radius=0.25):
        """Draw a rounded rectangle centred at (cx, cy)."""
        box = FancyBboxPatch(
            (cx - w / 2, cy - h / 2), w, h,
            boxstyle=f"round,pad={radius}",
            facecolor=color, edgecolor=C_WHITE,
            linewidth=1.5, zorder=3,
        )
        ax.add_patch(box)
        ax.text(cx, cy, text, ha="center", va="center",
                fontsize=fontsize, color=text_color,
                fontweight="bold", zorder=4, wrap=True,
                multialignment="center")

    def diamond(cx, cy, w, h, color, text, fontsize=9):
        """Draw a diamond (decision) shape centred at (cx, cy)."""
        # Diamond: 4 points
        dx, dy = w / 2, h / 2
        pts = np.array([
            [cx,      cy + dy],   # top
            [cx + dx, cy],         # right
            [cx,      cy - dy],   # bottom
            [cx - dx, cy],         # left
        ])
        poly = plt.Polygon(pts, closed=True,
                           facecolor=color, edgecolor=C_WHITE,
                           linewidth=1.5, zorder=3)
        ax.add_patch(poly)
        ax.text(cx, cy, text, ha="center", va="center",
                fontsize=fontsize, color="#2c3e50",
                fontweight="bold", zorder=4, multialignment="center")

    def arrow(x1, y1, x2, y2, label="", label_side="right"):
        """Draw an arrow between two points with an optional label."""
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle="->,head_width=0.25,head_length=0.15",
                color=C_WHITE, lw=1.8,
            ),
            zorder=5,
        )
        if label:
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2
            offset = 0.2 if label_side == "right" else -0.2
            ax.text(mx + offset, my, label, ha="center", va="center",
                    fontsize=8.5, color=C_WHITE, fontstyle="italic", zorder=6)

    def hline(x1, y, x2, color=C_WHITE, lw=1.5):
        ax.plot([x1, x2], [y, y], color=color, lw=lw, zorder=5)

    def vline(x, y1, y2, color=C_WHITE, lw=1.5):
        ax.plot([x, x], [y1, y2], color=color, lw=lw, zorder=5)

    # ------------------------------------------------------------------
    # Box layout (centred on x=5, flowing downward from y=15.2)
    # ------------------------------------------------------------------
    BW, BH = 3.8, 0.65       # Standard box width / height
    DW, DH = 2.6, 0.8        # Diamond half-widths / half-height (visual)

    # ---- Step 1: Alice generates bits --------------------------------
    rect(5, 15.2, BW, BH, C_BLUE, "① Alice Generates Random Bits\n& Chooses Bases")
    arrow(5, 14.87, 5, 14.22)

    # ---- Step 2: Alice encodes photons --------------------------------
    rect(5, 13.9, BW, BH, C_BLUE, "② Alice Encodes Bits → Photon States\n(0° / 90° / 45° / 135°)")
    arrow(5, 13.57, 5, 12.92)

    # ---- Step 3: Quantum channel --------------------------------------
    rect(5, 12.6, BW, BH, C_GRAY, "③ Quantum Channel Transmission\n(Photons sent to Bob)")
    arrow(5, 12.27, 5, 11.5)

    # ---- Decision: Eve intercepts? ------------------------------------
    diamond(5, 11.05, DW + 0.4, DH + 0.3, C_YELLOW, "Eve\nIntercepts?")

    # YES branch (left) ------------------------------------------------
    hline(5, 11.05, 2.8)                         # left from diamond
    vline(2.8, 11.05, 10.1)                       # down
    rect(2.8, 9.75, 2.5, BH, C_RED,
         "④ Eve Measures Photon\n& Resends (corrupted)",
         fontsize=8.5)
    ax.text(3.7, 11.1, "YES", fontsize=9, color=C_RED,
            fontweight="bold", va="bottom", ha="center", zorder=6)

    # NO branch (right) ------------------------------------------------
    hline(5, 11.05, 7.2)                          # right from diamond
    vline(7.2, 11.05, 10.1)                        # down
    rect(7.2, 9.75, 2.5, BH, C_GREEN,
         "④ Photon Passes\nThrough Unchanged",
         fontsize=8.5)
    ax.text(6.3, 11.1, "NO", fontsize=9, color=C_GREEN,
            fontweight="bold", va="bottom", ha="center", zorder=6)

    # Merge both branches down to Bob ----------------------------------
    vline(2.8, 9.42, 8.95)                         # left branch continues down
    vline(7.2, 9.42, 8.95)                         # right branch continues down
    hline(2.8, 8.95, 7.2)                           # horizontal merge
    arrow(5, 8.95, 5, 8.42)                         # arrow down to Bob

    # ---- Step 5: Bob measures ----------------------------------------
    rect(5, 8.1, BW, BH, C_BLUE, "⑤ Bob Measures Photons\n(Random basis choice)")
    arrow(5, 7.77, 5, 7.12)

    # ---- Step 6: Basis sifting ---------------------------------------
    rect(5, 6.8, BW, BH, C_GRAY, "⑥ Basis Sifting\n(Compare bases over public channel)")
    arrow(5, 6.47, 5, 5.82)

    # ---- Step 7: QBER calculation ------------------------------------
    rect(5, 5.5, BW, BH, C_GRAY, "⑦ QBER Calculation\n(Random sample of sifted bits)")
    arrow(5, 5.17, 5, 4.45)

    # ---- Decision: QBER > 11%? ---------------------------------------
    diamond(5, 4.0, DW + 0.4, DH + 0.3, C_YELLOW, "QBER\n> 11%?")

    # YES → ABORT (left) -----------------------------------------------
    hline(5, 4.0, 2.4)
    vline(2.4, 4.0, 3.1)
    rect(2.4, 2.8, 2.4, BH, C_RED, "⑧ ABORT ✗\nKey Exchange Failed",
         fontsize=8.5)
    ax.text(3.5, 4.07, "YES", fontsize=9, color=C_RED,
            fontweight="bold", va="bottom", ha="center", zorder=6)

    # NO → Privacy amplification (right) --------------------------------
    hline(5, 4.0, 7.6)
    vline(7.6, 4.0, 3.1)
    rect(7.6, 2.8, 2.4, BH, C_GREEN,
         "⑧ Privacy\nAmplification",
         fontsize=8.5)
    ax.text(6.5, 4.07, "NO", fontsize=9, color=C_GREEN,
            fontweight="bold", va="bottom", ha="center", zorder=6)

    arrow(7.6, 2.47, 7.6, 1.82)
    rect(7.6, 1.5, 2.4, BH, C_GREEN_DK,
         "⑨ Secure Key\nGenerated ✓",
         fontsize=8.5)

    # ---- Title -------------------------------------------------------
    ax.set_title(
        "BB84 Protocol Flow with Eavesdropper Detection",
        fontsize=15, fontweight="bold",
        color=C_WHITE, pad=14,
    )

    # ---- Legend ------------------------------------------------------
    legend_handles = [
        mpatches.Patch(color=C_BLUE,     label="Alice / Bob step"),
        mpatches.Patch(color=C_GRAY,     label="Classical post-processing"),
        mpatches.Patch(color=C_YELLOW,   label="Decision"),
        mpatches.Patch(color=C_RED,      label="Eve / Abort"),
        mpatches.Patch(color=C_GREEN,    label="Safe / Secure path"),
        mpatches.Patch(color=C_GREEN_DK, label="Final secure key"),
    ]
    ax.legend(
        handles=legend_handles, loc="lower left",
        fontsize=8.5, framealpha=0.3,
        facecolor="#2c3e50", edgecolor=C_WHITE,
        labelcolor=C_WHITE,
    )

    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "protocol_flow.png")
    plt.savefig(path, dpi=DPI, bbox_inches="tight",
                facecolor=C_BG)
    plt.close()
    print(f"  ✓ Saved → {path}")
    return path


# ======================================================================
# GRAPH 4 — Statistical Distribution (50 runs)
# ======================================================================
def plot_multiple_runs_statistics():
    """
    Run the protocol 50 times each for two scenarios and visualise distributions.

    Left subplot  — Overlaid histogram of QBER values.
    Right subplot — Side-by-side box plots with jittered data overlay.

    Orange dashed lines mark the 11 % security threshold on both subplots.

    Saves: results/statistics.png
    """
    import io, sys

    RUNS      = 50
    THRESHOLD = 11.0    # % scale for this graph
    N_QUBITS  = 256

    print(f"  Running {RUNS} simulations for each scenario (Graph 4)...")

    no_eve_qbers  = []
    full_eve_qbers = []

    for run_idx in range(RUNS):
        suppress   = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = suppress
        try:
            r_no  = run_full_protocol(N_QUBITS, eve_present=False)
            r_eve = run_full_protocol(N_QUBITS, eve_present=True, intercept_prob=1.0)
        finally:
            sys.stdout = old_stdout
        no_eve_qbers.append(r_no["qber"]  * 100)
        full_eve_qbers.append(r_eve["qber"] * 100)

    no_eve_arr  = np.array(no_eve_qbers)
    eve_arr     = np.array(full_eve_qbers)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("white")
    fig.suptitle(
        f"QBER Statistical Analysis over {RUNS} Independent Runs  "
        f"(n = {N_QUBITS} qubits)",
        fontsize=14, fontweight="bold", y=1.01,
    )

    # ---- LEFT: Histogram --------------------------------------------
    bins = np.linspace(0, 35, 20)
    ax1.hist(no_eve_arr,  bins=bins, color=C_GREEN, alpha=0.65,
             edgecolor="white", linewidth=0.8, label=f"No Eve  (mean={no_eve_arr.mean():.1f}%)")
    ax1.hist(eve_arr,     bins=bins, color=C_RED,   alpha=0.65,
             edgecolor="white", linewidth=0.8, label=f"Full Eve (mean={eve_arr.mean():.1f}%)")

    # Mean vertical lines
    ax1.axvline(no_eve_arr.mean(),  color=C_GREEN_DK, linestyle="--",
                linewidth=2,  label=f"No-Eve mean ({no_eve_arr.mean():.1f}%)")
    ax1.axvline(eve_arr.mean(),     color="#c0392b",   linestyle="--",
                linewidth=2,  label=f"Full-Eve mean ({eve_arr.mean():.1f}%)")

    # Threshold
    ax1.axvline(THRESHOLD, color=C_ORANGE, linestyle="--",
                linewidth=2.2, label="Security Threshold (11%)")

    ax1.set_xlabel("QBER (%)", fontsize=12, labelpad=8)
    ax1.set_ylabel("Frequency (runs)", fontsize=12, labelpad=8)
    ax1.set_title("QBER Distribution over 50 Runs", fontsize=13,
                  fontweight="bold")
    ax1.legend(fontsize=9, framealpha=0.9)
    ax1.set_xlim(0, 35)

    # ---- RIGHT: Box plot + jitter ------------------------------------
    data_groups = [no_eve_arr, eve_arr]
    group_labels = ["No Eve", "Full Eve (100%)"]
    group_colors = [C_GREEN, C_RED]

    bp = ax2.boxplot(data_groups, tick_labels=group_labels, patch_artist=True,
                     widths=0.45, zorder=3,
                     medianprops=dict(color="white", linewidth=2.5),
                     whiskerprops=dict(color="#555", linewidth=1.5),
                     capprops=dict(color="#555", linewidth=1.5),
                     flierprops=dict(marker="o", markerfacecolor="#aaa",
                                     markersize=5, alpha=0.5))

    for patch, color in zip(bp["boxes"], group_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    # Jittered scatter overlay
    for i, (data, color) in enumerate(zip(data_groups, group_colors), start=1):
        jitter = np.random.uniform(-0.15, 0.15, size=len(data))
        ax2.scatter(i + jitter, data, color=color, alpha=0.45,
                    s=22, zorder=4, edgecolors="none")

    # Threshold line
    ax2.axhline(THRESHOLD, color=C_ORANGE, linestyle="--",
                linewidth=2.2, label="Security Threshold (11%)", zorder=5)

    ax2.set_ylabel("QBER (%)", fontsize=12, labelpad=8)
    ax2.set_title("QBER Statistical Summary", fontsize=13, fontweight="bold")
    ax2.legend(fontsize=9, framealpha=0.9)
    ax2.set_ylim(0, 40)

    # Annotate danger zone
    ax2.axhspan(THRESHOLD, 40, alpha=0.06, color=C_RED)
    ax2.text(2.47, THRESHOLD + 0.8, "Unsafe zone", fontsize=8.5,
             color=C_RED, va="bottom", ha="right", fontstyle="italic")

    # Summary stats table below each box
    for i, (data, label) in enumerate(zip(data_groups, group_labels), start=1):
        ax2.text(
            i, -4.5,
            f"μ={data.mean():.1f}%\nσ={data.std():.1f}%",
            ha="center", va="top", fontsize=8.5, color="#2c3e50",
            transform=ax2.get_xaxis_transform(),
        )

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    path = os.path.join(RESULTS_DIR, "statistics.png")
    plt.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close()
    print(f"  ✓ Saved → {path}")
    return path


# ======================================================================
# Master Function
# ======================================================================
def generate_all_graphs() -> list:
    """
    Generate all four visualisation figures in sequence.

    Each graph function is called in turn with progress output.
    Errors in individual graphs are caught and reported without
    stopping the remaining graphs from being generated.

    Returns:
        list: Absolute paths of successfully saved PNG files.
    """
    _ensure_results_dir()

    graph_tasks = [
        ("QBER Comparison",         plot_qber_comparison),
        ("QBER vs Qubit Count",     plot_qber_vs_qubit_count),
        ("Protocol Flowchart",      plot_protocol_flowchart),
        ("Statistical Distribution",plot_multiple_runs_statistics),
    ]

    saved_paths = []

    for idx, (name, func) in enumerate(graph_tasks, start=1):
        print(f"\nGenerating Graph {idx}/{len(graph_tasks)}: {name}...")
        try:
            path = func()
            if path:
                saved_paths.append(os.path.abspath(path))
        except Exception as exc:
            print(f"  ✗ Graph {idx} failed: {exc}")
            import traceback
            traceback.print_exc()

    print(f"\nAll graphs saved to '{RESULTS_DIR}/' folder.")
    return saved_paths


# ======================================================================
# Standalone Entry Point
# ======================================================================
if __name__ == "__main__":
    print("=" * 58)
    print(" BB84 QKD Simulation — Visualization Module")
    print("=" * 58)

    paths = generate_all_graphs()

    print("\nSaved files:")
    for p in paths:
        print(f"  📊 {p}")

    print()
