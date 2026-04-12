"""
qber.py - Part 4 of 7: QBER Analysis and Eavesdropper Detection
================================================================

The Quantum Bit Error Rate (QBER) is the central security metric of BB84.

After Alice and Bob have sifted their keys (discarding bits where they used
different bases), they sacrifice a random SAMPLE of those sifted bits by
publicly comparing them.  Any mismatch reveals channel noise or — crucially
— the presence of an eavesdropper such as Eve.

Why ~25% QBER implies eavesdropping
-------------------------------------
With a full intercept-and-resend attack Eve guesses the correct basis only
~50% of the time.  Each wrong-basis interception causes a 50% chance that
Bob's bit differs from Alice's.  Overall:
    QBER_Eve ≈ 0.5 × 0.5 = 0.25  (25%)

The standard BB84 security threshold is 11%.  Any QBER above that means the
channel cannot be guaranteed secure and the exchange MUST be aborted.

Module contents
---------------
    calculate_qber()          – Random-sample QBER from sifted keys
    detect_eavesdropper()     – Threshold-based abort/proceed decision
    get_secure_key_length()   – Information-theoretic key-length estimate
    privacy_amplification()   – XOR-hash key shortening to remove Eve's info
    print_qber_analysis()     – Formatted box-style QBER report
    run_full_protocol()       – Master function: end-to-end BB84 simulation

Dependencies: math, random, alice, bob, eve
"""

import math
import random
from typing import Dict, List, Optional, Tuple
from alice import Alice
from bob   import Bob
from eve   import Eve


# ======================================================================
# 1. QBER Calculation
# ======================================================================
def calculate_qber(
    alice_sifted_key: List[int],
    bob_sifted_key:   List[int],
    sample_size:      Optional[int] = None,
) -> Tuple[float, List[int], int]:
    """
    Estimate the Quantum Bit Error Rate by comparing a random sample of bits.

    Alice and Bob publicly compare a subset of their sifted key bits to check
    for errors.  These "test bits" cannot be used in the final secret key
    (they have been disclosed), so they are removed from both key lists.

    Sampling strategy
    -----------------
    Comparing *all* sifted bits would maximise accuracy but leave no secret
    key material.  The default sample size (min(50, len//4)) balances
    detection power against wasted key bits: enough bits to get a reliable
    QBER estimate while retaining ~75% of the key for actual use.

    Args:
        alice_sifted_key (list): Alice's bit values after basis sifting.
                                 This list is MODIFIED IN PLACE — sample bits
                                 are removed.
        bob_sifted_key   (list): Bob's bit values after basis sifting.
                                 This list is MODIFIED IN PLACE similarly.
        sample_size      (int | None): Number of positions to compare.
                                 Defaults to min(50, len(key) // 4).
                                 Capped at the full key length if too large.

    Returns:
        tuple:
            qber             (float): Error rate in [0.0, 1.0].
            sample_indices   (list):  Original indices that were compared
                                      (before removal from the key).
            mismatches       (int):   Number of bit positions that differed.

    Raises:
        ValueError: If the two key lists have different lengths.

    Edge cases:
        - Empty keys → returns (0.0, [], 0) immediately.
        - sample_size == 0 → returns (0.0, [], 0).
    """
    # ---- Validate inputs ------------------------------------------------
    if len(alice_sifted_key) != len(bob_sifted_key):
        raise ValueError(
            f"Key length mismatch: Alice has {len(alice_sifted_key)} bits, "
            f"Bob has {len(bob_sifted_key)} bits."
        )

    key_len = len(alice_sifted_key)

    if key_len == 0:
        return 0.0, [], 0   # Nothing to compare

    # ---- Determine sample size ------------------------------------------
    if sample_size is None:
        # Default: at most 50 bits, at most ¼ of the available key
        sample_size = min(50, key_len // 4)

    # Clamp to the actual key length (can't sample more than we have)
    sample_size = max(0, min(sample_size, key_len))

    if sample_size == 0:
        return 0.0, [], 0

    # ---- Randomly pick which positions to compare -----------------------
    # random.sample() draws without replacement, preserving statistical
    # independence between sampled positions.
    sample_indices = sorted(random.sample(range(key_len), sample_size))

    # ---- Count mismatches -----------------------------------------------
    mismatches = sum(
        alice_sifted_key[i] != bob_sifted_key[i]
        for i in sample_indices
    )

    qber = mismatches / sample_size

    # ---- Remove sampled bits from BOTH keys (they are now public) ------
    # Iterate in REVERSE order so removing by index doesn't shift positions.
    for i in reversed(sample_indices):
        alice_sifted_key.pop(i)
        bob_sifted_key.pop(i)

    return qber, sample_indices, mismatches


# ======================================================================
# 2. Eavesdropper Detection
# ======================================================================
def detect_eavesdropper(
    qber:      float,
    threshold: float = 0.11,
) -> Tuple[bool, str]:
    """
    Decide whether the measured QBER indicates eavesdropping activity.

    BB84 Security Threshold
    -----------------------
    The standard threshold is 11% (0.11).  Below this, errors could
    plausibly arise from channel noise alone, and the partial information
    Eve might hold is provably reducible to zero via privacy amplification.
    Above 11%, no amount of classical post-processing can recover security,
    and the protocol MUST be aborted.

    Args:
        qber      (float): Measured quantum bit error rate in [0.0, 1.0].
        threshold (float): QBER above which the channel is deemed insecure.
                           Default = 0.11 (11%), the BB84 standard.

    Returns:
        tuple:
            eve_detected (bool): True if QBER > threshold.
            decision     (str):  "ABORT" if detected, "PROCEED" if safe.
    """
    if qber > threshold:
        return True,  "ABORT"
    else:
        return False, "PROCEED"


# ======================================================================
# 3. Secure Key Length Estimate
# ======================================================================
def _binary_entropy(p: float) -> float:
    """
    Binary entropy function:  h(p) = -p·log₂(p) − (1−p)·log₂(1−p)

    Gives the Shannon entropy of a biased coin with P(heads) = p.
    Returns 0 for the degenerate cases p=0 or p=1 (no uncertainty).

    Args:
        p (float): Probability in [0.0, 1.0].

    Returns:
        float: Entropy in bits, in [0.0, 1.0].
    """
    if p <= 0.0 or p >= 1.0:
        return 0.0   # log(0) is undefined; entropy is 0 at the extremes
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


def get_secure_key_length(total_bits: int, qber: float) -> int:
    """
    Estimate the number of provably secret bits remaining after eavesdropping.

    The Devetak-Winter bound gives the asymptotic secret-key rate per
    channel use as:

        r = 1 − 2 · h(QBER)

    where h is the binary entropy function.  Multiplying by the number of
    sifted bits gives the maximum yield of truly secret bits.

    Intuition
    ---------
    h(QBER) represents the information Eve may have gained.  We subtract it
    TWICE: once for the legitimate errors in the channel (Bob's uncertainty),
    and once for Eve's potential knowledge — hence the factor of 2.  Privacy
    amplification then hashes the key down to this shorter, secure length.

    At QBER = 0%:  r = 1 − 0 = 1.0    (full key is secret)
    At QBER = 11%: r = 1 − 2·h(0.11) ≈ 0   (threshold — nothing left)
    At QBER > 11%: r < 0               (protocol must abort)

    Args:
        total_bits (int):   Number of sifted bits available (after sampling).
        qber       (float): Measured QBER in [0.0, 1.0].

    Returns:
        int: Number of provably secret bits (≥ 0).  0 if the QBER is too
             high to extract any secure bits.
    """
    if total_bits <= 0:
        return 0

    rate         = 1.0 - 2.0 * _binary_entropy(qber)
    secure_bits  = total_bits * rate

    # Negative rate means the QBER is beyond the security threshold
    if secure_bits <= 0 or not math.isfinite(secure_bits):
        return 0

    return int(secure_bits)   # Floor to a whole number of bits


# ======================================================================
# 4. Privacy Amplification
# ======================================================================
def privacy_amplification(key: list, qber: float) -> list:
    """
    Shorten the key via XOR hashing to eliminate Eve's partial information.

    Even if Eve intercepted some photons, she holds at most partial knowledge
    about the sifted key.  Privacy amplification maps the full key into a
    SHORTER key in a way that is information-theoretically independent of
    what Eve knows.

    XOR hashing scheme used here
    ----------------------------
    We need to compress n bits → m bits (m = secure key length).
    A simple but effective approach: repeatedly XOR adjacent bit pairs.

    Round 1 (n bits → n//2 bits):  result[i] = key[2i] XOR key[2i+1]
    Repeat until we reach the target length m.

    This destroys Eve's partial information: if she knows one of the two
    input bits but not the other, the XOR output is completely random to her.

    Note: For production systems, use a cryptographic hash function (SHA-256,
    BLAKE2) or a universal hash family for provable security.  The XOR method
    here is illustrative and works for the simulation.

    Args:
        key  (list): The remaining sifted key bits (after sample removal).
        qber (float): The measured QBER, used to determine the target length.

    Returns:
        list: The privacy-amplified key, shortened to the secure length.
              Returns the original key unchanged if amplification is not
              possible or not needed (new_length ≥ current length or ≤ 0).
    """
    if not key:
        return key   # Nothing to amplify

    new_length = get_secure_key_length(len(key), qber)

    if new_length <= 0:
        # QBER too high — no secure bits can be extracted at all
        return []

    if new_length >= len(key):
        # No compression needed (QBER is negligible)
        return key

    # ---- Iterative XOR compression -------------------------------------
    # We compress in successive halving rounds until we reach new_length.
    current = list(key)   # Work on a copy

    while len(current) > new_length:
        compressed = []
        # XOR adjacent pairs: (0,1), (2,3), (4,5), ...
        for j in range(0, len(current) - 1, 2):
            compressed.append(current[j] ^ current[j + 1])
        # If the current length is odd, the last bit has no pair —
        # carry it forward as-is (it mixes in on the next round).
        if len(current) % 2 == 1:
            compressed.append(current[-1])
        current = compressed

    # Trim to exactly new_length bits in case we overshot slightly
    return current[:new_length]


# ======================================================================
# 5. Formatted QBER Report
# ======================================================================
def print_qber_analysis(qber: float, threshold: float = 0.11):
    """
    Print a formatted box-style QBER analysis report to stdout.

    Shows the measured QBER, the security threshold, whether an
    eavesdropper was detected, and the resulting protocol decision.

    Args:
        qber      (float): Measured QBER in [0.0, 1.0].
        threshold (float): Security threshold (default 11%).

    Example output (Eve present):
        ╔══════════════════════════════════════════╗
        ║         QBER ANALYSIS REPORT             ║
        ╠══════════════════════════════════════════╣
        ║ Quantum Bit Error Rate: 24.50%           ║
        ║ Security Threshold:     11.00%           ║
        ║ Status:  ⚠️  EAVESDROPPER DETECTED!      ║
        ║ Decision: ABORT KEY EXCHANGE             ║
        ╚══════════════════════════════════════════╝
    """
    eve_detected, decision = detect_eavesdropper(qber, threshold)

    inner_width = 44   # characters between the ║ borders

    def box_line(text: str) -> str:
        return f"║ {text:<{inner_width - 2}} ║"

    border_top    = "╔" + "═" * inner_width + "╗"
    border_mid    = "╠" + "═" * inner_width + "╣"
    border_bottom = "╚" + "═" * inner_width + "╝"
    title         = "QBER ANALYSIS REPORT".center(inner_width - 2)

    if eve_detected:
        status_line   = "⚠️  EAVESDROPPER DETECTED!"
        decision_line = "ABORT KEY EXCHANGE"
    else:
        status_line   = "✅ CHANNEL SECURE"
        decision_line = "PROCEED WITH KEY GENERATION"

    print(f"\n{border_top}")
    print(f"║ {title} ║")
    print(border_mid)
    print(box_line(f"Quantum Bit Error Rate: {qber * 100:.2f}%"))
    print(box_line(f"Security Threshold:     {threshold * 100:.2f}%"))
    print(box_line(f"Status:  {status_line}"))
    print(box_line(f"Decision: {decision_line}"))
    print(f"{border_bottom}\n")


# ======================================================================
# 6. Master Protocol Runner
# ======================================================================
def run_full_protocol(
    num_qubits:     int,
    eve_present:    bool  = False,
    intercept_prob: float = 1.0,
) -> Dict:
    """
    Run the complete BB84 Quantum Key Distribution protocol end-to-end.

    This master function orchestrates all six stages of BB84:

    Stage 1 — Quantum transmission
        Alice prepares random bits, chooses random bases, and encodes each
        bit into a photon polarisation state.

    Stage 2 — (Optional) Eavesdropping
        If eve_present is True, Eve intercepts photons with the given
        probability and resends corrupted versions to Bob.

    Stage 3 — Measurement
        Bob randomly chooses measurement bases and measures all photons
        (whether original or tampered by Eve).

    Stage 4 — Basis sifting
        Alice and Bob publicly compare their basis choices and discard all
        bits where they chose differently (~50% of qubits).

    Stage 5 — QBER estimation
        A random sample of sifted bits is publicly compared to compute the
        error rate.  These bits are sacrificed and removed from both keys.

    Stage 6 — Security decision & key finalisation
        If QBER ≤ 11%:  Privacy amplification shortens the remaining key to
                         the provably secret length → key is GENERATED.
        If QBER > 11%:  The exchange is ABORTED — no key is produced.

    Args:
        num_qubits    (int):   Number of photons Alice sends.
        eve_present   (bool):  Whether Eve is active on the channel.
        intercept_prob (float): Eve's per-photon interception probability
                                (only used if eve_present=True).

    Returns:
        dict with keys:
            num_qubits        (int):   Qubit count used.
            sifted_key_length (int):   Bits remaining after basis sifting.
            sample_size       (int):   Bits sacrificed for QBER estimation.
            qber              (float): Measured error rate (0.0 – 1.0).
            eve_detected      (bool):  Whether the protocol detected Eve.
            status            (str):   "KEY GENERATED" or "ABORTED".
            final_key         (list):  The secret key bits (empty if aborted).
            final_key_length  (int):   Length of final_key.
    """
    if num_qubits <= 0:
        # Guard: nothing to do with zero or negative qubits
        return {
            "num_qubits": num_qubits, "sifted_key_length": 0,
            "sample_size": 0, "qber": 0.0, "eve_detected": False,
            "status": "ABORTED", "final_key": [], "final_key_length": 0,
        }

    # ------------------------------------------------------------------
    # Stage 1: Alice prepares photons
    # ------------------------------------------------------------------
    alice = Alice(num_qubits)
    alice.generate_bits()
    alice.generate_bases()
    alice.encode_photons()

    photon_stream = alice.photon_states   # The photons going onto the channel

    # ------------------------------------------------------------------
    # Stage 2: Eve intercepts (if active)
    # ------------------------------------------------------------------
    if eve_present:
        eve           = Eve(intercept_probability=intercept_prob)
        photon_stream = eve.intercept(photon_stream)

    # ------------------------------------------------------------------
    # Stage 3: Bob measures
    # ------------------------------------------------------------------
    bob = Bob(num_qubits)
    bob.generate_bases()
    bob.measure_photons(photon_stream)

    # ------------------------------------------------------------------
    # Stage 4: Basis sifting
    # ------------------------------------------------------------------
    matching_indices, _ = bob.sift_key(alice.bases, bob.bases)

    alice_sifted = alice.get_sifted_key(matching_indices)
    bob_sifted   = list(bob.raw_key)       # Work on a copy so originals are safe

    sifted_length = len(alice_sifted)

    # Edge case: no matching bases at all
    if sifted_length == 0:
        return {
            "num_qubits": num_qubits, "sifted_key_length": 0,
            "sample_size": 0, "qber": 0.0, "eve_detected": False,
            "status": "ABORTED", "final_key": [], "final_key_length": 0,
        }

    # ------------------------------------------------------------------
    # Stage 5: QBER estimation (sacrifices sample bits)
    # ------------------------------------------------------------------
    # calculate_qber() removes sampled bits from both lists in-place
    qber, sample_indices, mismatches = calculate_qber(alice_sifted, bob_sifted)
    sample_size = len(sample_indices)

    # ------------------------------------------------------------------
    # Stage 6: Security decision
    # ------------------------------------------------------------------
    eve_detected, decision = detect_eavesdropper(qber)
    print_qber_analysis(qber)

    if eve_detected:
        # QBER too high — abort; do NOT produce a key
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

    # ------------------------------------------------------------------
    # Stage 6b: Privacy amplification → final secret key
    # ------------------------------------------------------------------
    # alice_sifted now contains only the un-sampled bits (sample was removed)
    final_key = privacy_amplification(alice_sifted, qber)

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


# ======================================================================
# Standalone Tests
# ======================================================================
if __name__ == "__main__":

    # Scenario definitions -----------------------------------------------
    scenarios = [
        {"label": "No Eve",        "qubits": 256, "eve": False, "prob": 0.00},
        {"label": "Full Eve",      "qubits": 256, "eve": True,  "prob": 1.00},
        {"label": "Partial Eve",   "qubits": 256, "eve": True,  "prob": 0.50},
        {"label": "No Eve (512Q)", "qubits": 512, "eve": False, "prob": 0.00},
    ]

    results = []   # Collect for the summary table

    for idx, sc in enumerate(scenarios, start=1):
        print()
        print("=" * 60)
        print(f" SCENARIO {idx}: {sc['label']}  "
              f"({sc['qubits']} qubits"
              + (f", Eve p={sc['prob']:.0%}" if sc["eve"] else "") + ")")
        print("=" * 60)

        result = run_full_protocol(
            num_qubits    = sc["qubits"],
            eve_present   = sc["eve"],
            intercept_prob= sc["prob"],
        )

        # Store summary info
        status_icon = "✅" if result["status"] == "KEY GENERATED" else "❌"
        results.append({
            "Scenario":    sc["label"],
            "Qubits":      sc["qubits"],
            "Sifted bits": result["sifted_key_length"],
            "Sample used": result["sample_size"],
            "QBER":        f"{result['qber'] * 100:.1f}%",
            "Final key":   result["final_key_length"],
            "Status":      f"{status_icon} {result['status']}",
        })

        # Detailed per-scenario printout
        print(f"  Sifted key bits  : {result['sifted_key_length']}")
        print(f"  Sample bits used : {result['sample_size']}")
        print(f"  QBER             : {result['qber'] * 100:.2f}%")
        print(f"  Final key length : {result['final_key_length']} bits")
        if result["final_key"]:
            preview = result["final_key"][:20]
            ellipsis = "..." if result["final_key_length"] > 20 else ""
            print(f"  Final key (first 20): {preview}{ellipsis}")

    # ---- Summary Comparison Table ----------------------------------------
    print()
    print("=" * 60)
    print(" SUMMARY COMPARISON TABLE")
    print("=" * 60)

    # Column widths
    col_w = {
        "Scenario":    16,
        "Qubits":       7,
        "Sifted bits":  12,
        "Sample used":  12,
        "QBER":         8,
        "Final key":    10,
        "Status":       22,
    }

    # Header
    header = " | ".join(f"{k:^{v}}" for k, v in col_w.items())
    sep    = "-+-".join("-" * v for v in col_w.values())
    print(header)
    print(sep)

    for row in results:
        line = " | ".join(
            f"{str(row[k]):^{v}}" for k, v in col_w.items()
        )
        print(line)

    print()
