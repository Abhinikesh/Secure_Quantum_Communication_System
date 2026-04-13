"""
main.py - Part 5 of 7: Main Runner for the BB84 QKD Simulation
===============================================================

This is the top-level entry point for the entire BB84 Quantum Key
Distribution simulation.  It orchestrates Alice, Bob, Eve, and the QBER
analysis module to run five distinct protocol scenarios and presents
results in a clean, professor-ready format.

Usage:
    python3 main.py           # Run all 5 scenarios
    python3 main.py --quick   # Run only Scenarios 1 & 2 (quick demo)

Scenarios:
    1. Normal operation — no eavesdropper          (256 qubits)
    2. Full attack — Eve intercepts every photon    (256 qubits)
    3. Partial attack — Eve intercepts 50% of photons (256 qubits)
    4. Large key — no eavesdropper                  (512 qubits)
    5. Small key test — no eavesdropper              (64 qubits)

Dependencies: alice, bob, eve, qber, time, argparse
Optional:     colorama  (for ANSI colour output; falls back gracefully)
"""

import argparse
import time
import sys

from alice import Alice
from bob   import Bob
from eve   import Eve
import qber as QBER

# ======================================================================
# Optional colour support (colorama)
# ======================================================================
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
    _HAS_COLOR = True
except ImportError:
    # Provide no-op stubs so the rest of the file can freely reference
    # Fore.* and Style.* without branching everywhere.
    class _Stub:
        def __getattr__(self, _: str) -> str:
            return ""
    Fore  = _Stub()
    Style = _Stub()
    _HAS_COLOR = False


# ======================================================================
# Colour-wrapped helper functions
# ======================================================================
def _green(text: str) -> str:
    return f"{Fore.GREEN}{text}{Style.RESET_ALL}"

def _red(text: str) -> str:
    return f"{Fore.RED}{text}{Style.RESET_ALL}"

def _yellow(text: str) -> str:
    return f"{Fore.YELLOW}{text}{Style.RESET_ALL}"

def _cyan(text: str) -> str:
    return f"{Fore.CYAN}{text}{Style.RESET_ALL}"

def _bold(text: str) -> str:
    return f"{Style.BRIGHT}{text}{Style.RESET_ALL}"

def _magenta(text: str) -> str:
    return f"{Fore.MAGENTA}{text}{Style.RESET_ALL}"


# ======================================================================
# 1. Main Header
# ======================================================================
def print_main_header():
    """
    Print the ASCII-art banner that opens the simulation.

    Shows the project name, system description, and academic affiliation
    in a unicode box — designed to impress at first glance.
    """
    line = "═" * 54
    header_lines = [
        f"╔{line}╗",
        f"║{'QUANTUM KEY DISTRIBUTION (BB84) SIMULATION':^54}║",
        f"║{'Eavesdropper Detection & Security Analysis':^54}║",
        f"║{'DTI Project  —  CSE Department':^54}║",
        f"╚{line}╝",
    ]

    print()
    for ln in header_lines:
        print(_cyan(_bold(ln)))
    print()

    if not _HAS_COLOR:
        print("  (Tip: pip install colorama for colour output)\n")


# ======================================================================
# 2. Scenario Header
# ======================================================================
def _print_scenario_header(number: int, title: str):
    """Print a clearly delimited header block for each scenario."""
    bar   = "─" * 56
    label = f"  SCENARIO {number}: {title}"
    print(_bold(_yellow(f"\n┌{bar}┐")))
    print(_bold(_yellow(f"│{label:<56}│")))
    print(_bold(_yellow(f"└{bar}┘")))
    print()


# ======================================================================
# 3. Step Printer
# ======================================================================
def _step(number: int, description: str, icon: str = "✓",
          color_fn=None, delay: float = 0.3):
    """
    Print a single protocol step with step number, description, and icon.

    Args:
        number      (int):  Step number to display.
        description (str):  Human-readable description of the step.
        icon        (str):  Completion icon (✓, ✗, ⚠️, …).
        color_fn:           Optional colour wrapper for the icon.
        delay       (float): Seconds to pause after printing (dramatic effect).
    """
    label = f"  [STEP {number}] {description}"
    # Pad description to a fixed column so icons align neatly
    padded = f"{label:<55}"

    icon_str = color_fn(icon) if color_fn else icon
    print(f"{padded} {icon_str}")
    time.sleep(delay)


# ======================================================================
# 4. Core Scenario Runner
# ======================================================================
def run_scenario(
    scenario_name:  str,
    num_qubits:     int,
    eve_present:    bool,
    intercept_prob: float = 1.0,
    threshold:      float = 0.11,
) -> dict:
    """
    Execute a single end-to-end BB84 protocol scenario with live step output.

    Each protocol stage is printed as it executes, with a short pause
    between steps to give a clear sense of progress when demonstrated live.

    Args:
        scenario_name  (str):   Display name for this scenario.
        num_qubits     (int):   Number of photons Alice sends.
        eve_present    (bool):  True if Eve is active on the quantum channel.
        intercept_prob (float): Eve's per-photon interception probability.
        threshold      (float): QBER threshold for eavesdropper detection.

    Returns:
        dict: Result dictionary from QBER.run_full_protocol() with added
              'scenario_name' key for the summary table.
    """

    # ------------------------------------------------------------------
    # STEP 1 — Alice generates bits
    # ------------------------------------------------------------------
    _step(1, f"Alice generating {num_qubits} random bits...",
          icon="✓", color_fn=_green)

    alice = Alice(num_qubits)
    alice.generate_bits()
    alice.generate_bases()

    # ------------------------------------------------------------------
    # STEP 2 — Alice encodes photons
    # ------------------------------------------------------------------
    _step(2, "Alice choosing bases & encoding photons...",
          icon="✓", color_fn=_green)

    alice.encode_photons()
    photon_stream = alice.photon_states

    # ------------------------------------------------------------------
    # STEP 3 — Quantum channel transmission (or Eve's interception)
    # ------------------------------------------------------------------
    if eve_present:
        pct_label = f"{int(intercept_prob * 100)}%"
        _step(3, f"Photons transmitted over quantum channel...",
              icon="✓", color_fn=_green)
        _step(4, f"Eve intercepting photons ({pct_label})...",
              icon="⚠️ ", color_fn=_yellow)

        eve           = Eve(intercept_probability=intercept_prob)
        photon_stream = eve.intercept(photon_stream)

        # Print Eve's stats inline
        stats = eve.get_statistics()
        print(f"       Eve intercepted {stats['intercepted_count']} photons "
              f"| Basis accuracy: {stats['basis_accuracy']:.1f}%")
        step_offset = 1   # We used an extra step for Eve
    else:
        _step(3, "Photons transmitted over quantum channel...",
              icon="✓", color_fn=_green)
        step_offset = 0

    # ------------------------------------------------------------------
    # STEP 4/5 — Bob measures
    # ------------------------------------------------------------------
    _step(4 + step_offset, "Bob measuring received photons...",
          icon="✓", color_fn=_green)

    bob = Bob(num_qubits)
    bob.generate_bases()
    bob.measure_photons(photon_stream)

    # ------------------------------------------------------------------
    # STEP 5/6 — Basis sifting
    # ------------------------------------------------------------------
    _step(5 + step_offset, "Basis sifting (comparing bases publicly)...",
          icon="✓", color_fn=_green)

    matching_indices, _ = bob.sift_key(alice.bases, bob.bases)
    alice_sifted = alice.get_sifted_key(matching_indices)
    bob_sifted   = list(bob.raw_key)
    sifted_len   = len(alice_sifted)

    # ------------------------------------------------------------------
    # STEP 6/7 — QBER calculation (sacrifices a sample of bits)
    # ------------------------------------------------------------------
    _step(6 + step_offset, "Calculating QBER from random sample...",
          icon="✓", color_fn=_green)

    if sifted_len == 0:
        # Edge case: no sifted bits available — abort immediately
        print(_red("  ⚠  No sifted bits available. Aborting."))
        return {
            "scenario_name": scenario_name,
            "num_qubits": num_qubits, "sifted_key_length": 0,
            "sample_size": 0, "qber": 0.0,
            "eve_detected": False, "status": "ABORTED",
            "final_key": [], "final_key_length": 0,
        }

    measured_qber, sample_indices, mismatches = QBER.calculate_qber(
        alice_sifted, bob_sifted
    )
    sample_size = len(sample_indices)
    print(f"       Sample: {sample_size} bits compared | "
          f"Mismatches: {mismatches} | "
          f"QBER: {measured_qber * 100:.2f}%")

    # ------------------------------------------------------------------
    # STEP 7/8 — Security check
    # ------------------------------------------------------------------
    eve_detected, decision = QBER.detect_eavesdropper(measured_qber, threshold)

    if eve_detected:
        _step(7 + step_offset, "Security check failed — EAVESDROPPER DETECTED",
              icon="✗", color_fn=_red)
        QBER.print_qber_analysis(measured_qber, threshold)
        result = {
            "scenario_name": scenario_name,
            "num_qubits": num_qubits,
            "sifted_key_length": sifted_len,
            "sample_size": sample_size,
            "qber": measured_qber,
            "eve_detected": True,
            "status": "ABORTED",
            "final_key": [],
            "final_key_length": 0,
        }
    else:
        _step(7 + step_offset, "Security check passed — channel is secure",
              icon="✓", color_fn=_green)
        QBER.print_qber_analysis(measured_qber, threshold)

        # Privacy amplification
        final_key = QBER.privacy_amplification(alice_sifted, measured_qber)
        result = {
            "scenario_name": scenario_name,
            "num_qubits": num_qubits,
            "sifted_key_length": sifted_len,
            "sample_size": sample_size,
            "qber": measured_qber,
            "eve_detected": False,
            "status": "KEY GENERATED",
            "final_key": final_key,
            "final_key_length": len(final_key),
        }

    # ------------------------------------------------------------------
    # Final per-scenario result banner
    # ------------------------------------------------------------------
    print()
    if result["status"] == "KEY GENERATED":
        outcome = _green(_bold("✅  KEY GENERATED SUCCESSFULLY"))
        key_preview = result["final_key"][:16]
        ellipsis   = "..." if result["final_key_length"] > 16 else ""
        print(f"  {outcome}")
        print(f"  Final key length : {result['final_key_length']} bits")
        print(f"  Key preview      : {key_preview}{ellipsis}")
    else:
        outcome = _red(_bold("❌  KEY EXCHANGE ABORTED"))
        print(f"  {outcome}")
        print(f"  Reason           : QBER ({result['qber'] * 100:.2f}%) "
              f"exceeds threshold ({threshold * 100:.2f}%)")
    print()

    return result


# ======================================================================
# 5. Final Summary Table
# ======================================================================
def print_summary_table(results: list):
    """
    Print a unicode box table summarising all scenario results side-by-side.

    Args:
        results (list): List of result dicts returned by run_scenario().
    """
    # Column definitions: (header, width, key, formatter)
    # scenario_name is truncated to 18 chars to keep the table tidy
    columns = [
        ("Scenario",   18, "scenario_name",    lambda v: v[:18]),
        ("Qubits",      7, "num_qubits",        lambda v: str(v)),
        ("QBER",        9, "qber",              lambda v: f"{v * 100:.2f}%"),
        ("Status",     15, "status",            lambda v: (
            "✅ GENERATED" if v == "KEY GENERATED" else "❌ ABORTED"
        )),
        ("Key Length",  10, "final_key_length", lambda v: f"{v} bits"),
    ]

    # Box drawing characters
    top_sep  = "╦".join("═" * (w + 2) for _, w, *_ in columns)
    mid_sep  = "╬".join("═" * (w + 2) for _, w, *_ in columns)
    bot_sep  = "╩".join("═" * (w + 2) for _, w, *_ in columns)
    row_div  = "┼".join("─" * (w + 2) for _, w, *_ in columns)

    def make_row(values: list, sep: str = "║") -> str:
        cells = []
        for val, (_, width, *_) in zip(values, columns):
            cells.append(f" {str(val):^{width}} ")
        return sep + sep.join(cells) + sep

    print(_bold(_cyan(f"\n╔{top_sep}╗")))
    # Header row
    headers = [h for h, *_ in columns]
    print(_bold(_cyan(make_row(headers, sep="║"))))
    print(_bold(_cyan(f"╠{mid_sep}╣")))

    # Data rows
    for i, res in enumerate(results):
        formatted = [fmt(res[key]) for _, _, key, fmt in columns]
        row_str   = make_row(formatted, sep="║")

        # Colour the row based on outcome
        if res["status"] == "KEY GENERATED":
            print(_green(row_str))
        else:
            print(_red(row_str))

        # Thin divider between rows (but not after the last one)
        if i < len(results) - 1:
            print(_cyan(f"╠{mid_sep}╣"))

    print(_bold(_cyan(f"╚{bot_sep}╝")))
    print()


# ======================================================================
# 6. Main Execution Block
# ======================================================================
if __name__ == "__main__":

    # ---- Argument parsing --------------------------------------------
    parser = argparse.ArgumentParser(
        description="BB84 Quantum Key Distribution Simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 main.py           # Full simulation (5 scenarios)\n"
            "  python3 main.py --quick   # Quick demo    (2 scenarios)\n"
        ),
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run only Scenario 1 (No Eve) and Scenario 2 (Full Eve) for a quick demo.",
    )
    args = parser.parse_args()

    # ---- Opening banner ----------------------------------------------
    print_main_header()
    mode_label = "QUICK" if args.quick else "FULL"
    print(f"  Mode: {_bold(mode_label)} simulation\n")
    time.sleep(0.4)

    # ---- Scenario definitions ----------------------------------------
    all_scenarios = [
        {
            "number":        1,
            "name":          "Normal Operation — No Eavesdropper",
            "num_qubits":    256,
            "eve_present":   False,
            "intercept_prob": 0.0,
        },
        {
            "number":        2,
            "name":          "Full Attack — Eve Intercepts All Photons",
            "num_qubits":    256,
            "eve_present":   True,
            "intercept_prob": 1.0,
        },
        {
            "number":        3,
            "name":          "Partial Attack — Eve Intercepts 50% of Photons",
            "num_qubits":    256,
            "eve_present":   True,
            "intercept_prob": 0.5,
        },
        {
            "number":        4,
            "name":          "Large Key — No Eavesdropper",
            "num_qubits":    512,
            "eve_present":   False,
            "intercept_prob": 0.0,
        },
        {
            "number":        5,
            "name":          "Small Key Test — No Eavesdropper",
            "num_qubits":    64,
            "eve_present":   False,
            "intercept_prob": 0.0,
        },
    ]

    # In quick mode run only scenarios 1 and 2
    scenarios_to_run = all_scenarios[:2] if args.quick else all_scenarios

    # ---- Run each scenario -------------------------------------------
    all_results = []

    for sc in scenarios_to_run:
        _print_scenario_header(sc["number"], sc["name"])
        time.sleep(0.2)

        result = run_scenario(
            scenario_name  = sc["name"],
            num_qubits     = sc["num_qubits"],
            eve_present    = sc["eve_present"],
            intercept_prob = sc["intercept_prob"],
        )
        all_results.append(result)

        # Brief pause between scenarios for readability
        time.sleep(0.5)

    # ---- Final summary table -----------------------------------------
    bar = "═" * 56
    print(_bold(_cyan(f"\n╔{bar}╗")))
    print(_bold(_cyan(f"║{'FINAL SUMMARY — ALL SCENARIOS':^56}║")))
    print(_bold(_cyan(f"╚{bar}╝")))

    print_summary_table(all_results)

    # ---- Closing message ---------------------------------------------
    generated = sum(1 for r in all_results if r["status"] == "KEY GENERATED")
    aborted   = len(all_results) - generated

    print(_bold("  Results at a glance:"))
    print(_green(f"    ✅  Keys generated : {generated}"))
    print(_red(  f"    ❌  Exchanges aborted : {aborted}"))
    print()
    print(_bold(_cyan(
        "  Simulation complete. See visualize.py for graphs."
    )))
    print()
