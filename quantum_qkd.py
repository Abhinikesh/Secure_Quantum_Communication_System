"""
quantum_qkd.py — Master Real-Quantum BB84 Protocol Runner
==========================================================

Ties together QuantumAlice and QuantumBob to run a complete BB84
Quantum Key Distribution protocol using REAL quantum circuits via Qiskit.

All randomness (Alice's bits, Alice's bases, Bob's bases) is generated
using genuine quantum measurements — Hadamard-gate superpositions
collapsed by measurement, not pseudo-random classical algorithms.

Usage
-----
  # Local simulation (free, fast, no account needed):
  python quantum_qkd.py

  # IBM Quantum hardware (requires free IBM account):
  from quantum_qkd import run_quantum_bb84
  result = run_quantum_bb84(use_real_hardware=True, token="YOUR_TOKEN_HERE")

  # Get your token at: https://quantum.ibm.com

Dependencies: qiskit, qiskit-aer, qiskit-ibm-runtime, quantum_alice, quantum_bob, qber
"""

from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Local module imports
# ---------------------------------------------------------------------------
from quantum_alice import QuantumAlice
from quantum_bob   import QuantumBob
from qber import calculate_qber, detect_eavesdropper, privacy_amplification, print_qber_analysis


# ===========================================================================
# Master BB84 runner
# ===========================================================================
def run_quantum_bb84(
    num_qubits:        int            = 64,
    use_real_hardware: bool           = False,
    token:             Optional[str]  = None,
) -> Dict:
    """
    Run the complete BB84 protocol using REAL quantum circuits.

    Every step that involves randomness or quantum measurement uses
    genuine quantum circuits — not pseudo-random numbers.

    Steps
    -----
    1. Initialise backends (local AerSimulator or IBM Quantum hardware).
    2. Alice generates quantum-random bits & bases, builds state-prep circuits.
    3. Bob generates quantum-random bases & measures Alice's circuits.
    4. Classical basis reconciliation (sifting) over a public channel.
    5. QBER estimation from a sacrificial sample of sifted bits.
    6. Security decision: proceed with privacy amplification, or abort.

    Parameters
    ----------
    num_qubits        : Number of photons to simulate (default: 64).
    use_real_hardware : True  -> submit to real IBM Quantum hardware.
                        False -> use local AerSimulator (default).
    token             : IBM Quantum API token (only for real hardware).

    Returns
    -------
    dict with keys:
        num_qubits        (int)   : Qubit count.
        sifted_key_length (int)   : Bits after basis sifting.
        sample_size       (int)   : Bits used for QBER estimation.
        qber              (float) : Measured Quantum Bit Error Rate.
        eve_detected      (bool)  : Whether QBER exceeded the threshold.
        status            (str)   : "KEY GENERATED" or "ABORTED".
        final_key         (list)  : The privacy-amplified secret key bits.
        final_key_length  (int)   : Length of final_key.
    """
    backend_label = "IBM Quantum Hardware" if use_real_hardware else "Qiskit AerSimulator (local)"

    # =========================================================================
    # STEP 1 — Initialise
    # =========================================================================
    print("\n" + "=" * 65)
    print("   REAL QUANTUM BB84 PROTOCOL — Powered by Qiskit")
    print("=" * 65)
    print(f"  Qubits   : {num_qubits}")
    print(f"  Backend  : {backend_label}")
    print("=" * 65)

    # =========================================================================
    # STEP 2 — Alice prepares REAL quantum states
    # =========================================================================
    print("\n--- STEP 2: Alice prepares real quantum states ---")
    alice = QuantumAlice(
        num_qubits        = num_qubits,
        use_real_hardware = use_real_hardware,
        ibm_token         = token,
    )

    bits, bases, circuits = alice.encode_all(num_qubits)

    print(f"\n✓ Alice prepared {num_qubits} real quantum circuits")
    print("\nSample circuit — Qubit 0:")
    print(circuits[0].draw("text"))

    # =========================================================================
    # STEP 3 — Bob measures with REAL quantum measurement
    # =========================================================================
    print("\n--- STEP 3: Bob performs real quantum measurements ---")
    bob = QuantumBob()

    if use_real_hardware and token:
        # Submit to real IBM Quantum hardware
        bob_measurements = bob.run_on_ibm_real_hardware(circuits, ibm_token=token)
        bob_bases = bob.bases   # set inside run_on_ibm_real_hardware
    else:
        # Local AerSimulator — fast and free
        bob_bases, bob_measurements = bob.measure_all(circuits)

    print(f"✓ Bob performed {num_qubits} real quantum measurements")

    # =========================================================================
    # STEP 4 — Classical basis reconciliation (public channel)
    # =========================================================================
    print("\n--- STEP 4: Classical basis comparison (public channel) ---")

    matching = [i for i in range(num_qubits) if bases[i] == bob_bases[i]]
    alice_sifted = [bits[i]            for i in matching]
    bob_sifted   = [bob_measurements[i] for i in matching]
    sifted_length = len(matching)

    match_pct = sifted_length / num_qubits * 100
    print(f"✓ Basis match: {sifted_length}/{num_qubits} qubits kept ({match_pct:.1f}%)")

    if sifted_length == 0:
        print("  ERROR: No matching bases — cannot proceed. Try more qubits.")
        return _abort_result(num_qubits, 0, 0, 0.0)

    # =========================================================================
    # STEP 5 — QBER calculation
    # =========================================================================
    print("\n--- STEP 5: QBER estimation ---")

    # calculate_qber() modifies alice_sifted and bob_sifted IN PLACE
    # (removes the sampled bits from both lists — they are now public)
    alice_sifted_copy = list(alice_sifted)
    bob_sifted_copy   = list(bob_sifted)

    qber, sample_indices, mismatches = calculate_qber(alice_sifted_copy, bob_sifted_copy)
    sample_size = len(sample_indices)

    print(f"✓ QBER = {qber:.2%}   (from {sample_size} sacrificed test bits, {mismatches} errors)")

    # =========================================================================
    # STEP 6 — Security decision & key generation
    # =========================================================================
    print("\n--- STEP 6: Security decision ---")
    eve_detected, decision = detect_eavesdropper(qber)
    print_qber_analysis(qber)

    if eve_detected:
        print("❌ EAVESDROPPER DETECTED — ABORTING KEY EXCHANGE")
        return _abort_result(num_qubits, sifted_length, sample_size, qber)

    # Privacy amplification: shorten remaining key to provably secret length
    final_key = privacy_amplification(alice_sifted_copy, qber)

    print("✅ REAL QUANTUM KEY GENERATED SUCCESSFULLY")
    if final_key:
        key_str = "".join(map(str, final_key))
        preview = key_str[:64] + ("..." if len(key_str) > 64 else "")
        print(f"   Key ({len(final_key)} bits): {preview}")

    # =========================================================================
    # Simulation vs Real Quantum Comparison Table
    # =========================================================================
    _print_comparison_table()

    return {
        "num_qubits":        num_qubits,
        "sifted_key_length": sifted_length,
        "sample_size":       sample_size,
        "qber":              qber,
        "eve_detected":      False,
        "status":            "KEY GENERATED",
        "final_key":         final_key,
        "final_key_length":  len(final_key),
    }


# ---------------------------------------------------------------------------
def _abort_result(
    num_qubits: int,
    sifted_length: int,
    sample_size: int,
    qber: float,
) -> Dict:
    """Return a standard abort-result dictionary."""
    return {
        "num_qubits":        num_qubits,
        "sifted_key_length": sifted_length,
        "sample_size":       sample_size,
        "qber":              qber,
        "eve_detected":      True,
        "status":            "ABORTED",
        "final_key":         [],
        "final_key_length":  0,
    }


# ---------------------------------------------------------------------------
def _print_comparison_table() -> None:
    """Print a formatted Simulation vs Real Quantum feature comparison."""
    print("\n" + "=" * 65)
    print("  SIMULATION vs REAL QUANTUM — Feature Comparison")
    print("=" * 65)

    rows = [
        ("Feature",          "Classical Simulation",  "Real Quantum (Qiskit)"),
        ("-" * 18,           "-" * 22,                "-" * 22),
        ("Randomness",       "Pseudo-random (PRNG)",  "Quantum H-gate meas."),
        ("Photon states",    "Integer 0-3 (fake)",    "Real QuantumCircuit"),
        ("Alice's gates",    "Lookup table",          "X, H Qiskit gates"),
        ("Bob measurement",  "Math formula",          "Qiskit measure gate"),
        ("Basis mismatch",   "random.randint(0,1)",   "Quantum collapse"),
        ("Basis choice",     "random.randint(0,1)",   "Quantum H-gate meas."),
        ("Hardware",         "CPU only",              "Simulator / IBM QPU"),
        ("Security proof",   "Algorithmic model",     "Physical law (QM)"),
    ]

    col_w = [20, 24, 24]
    for row in rows:
        line = " | ".join(f"{cell:<{col_w[j]}}" for j, cell in enumerate(row))
        print(f"  {line}")

    print("=" * 65)


# ===========================================================================
# Standalone entry point
# ===========================================================================
if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  Running REAL Quantum BB84 Protocol...")
    print("  Using Qiskit AerSimulator (local quantum simulation)")
    print("=" * 65)

    result = run_quantum_bb84(num_qubits=64, use_real_hardware=False)

    # Final result summary
    print("\n" + "=" * 65)
    print("  FINAL PROTOCOL RESULTS")
    print("=" * 65)
    print(f"  Total qubits sent    : {result['num_qubits']}")
    print(f"  Sifted key length    : {result['sifted_key_length']} bits")
    print(f"  Test bits sacrificed : {result['sample_size']}")
    print(f"  QBER                 : {result['qber']:.2%}")
    print(f"  Eve detected?        : {'Yes' if result['eve_detected'] else 'No'}")
    print(f"  Status               : {result['status']}")
    print(f"  Final key length     : {result['final_key_length']} bits")
    print("=" * 65)

    print("\n" + "-" * 65)
    print("  To use REAL IBM Quantum Hardware:")
    print("-" * 65)
    print("  1. Go to  https://quantum.ibm.com")
    print("  2. Create a free account")
    print("  3. Copy your API token from the dashboard")
    print("  4. Run:")
    print()
    print("     from quantum_qkd import run_quantum_bb84")
    print("     result = run_quantum_bb84(")
    print("         num_qubits        = 64,")
    print("         use_real_hardware = True,")
    print("         token             = 'YOUR_IBM_TOKEN_HERE'")
    print("     )")
    print("-" * 65)
