"""
eve.py - Part 3 of 7: Eve's Role in the BB84 QKD Protocol
==========================================================

Eve is the eavesdropper who performs an "intercept-and-resend" attack.

She sits covertly on the quantum channel between Alice and Bob.
For each photon she chooses to intercept, she:
  1. Randomly guesses a measurement basis (she cannot know Alice's).
  2. Measures the photon — correct bit if she guessed right, random if not.
  3. Re-encodes her measurement into a BRAND-NEW photon using HER basis.
  4. Forwards this new photon to Bob instead of the original.

Why this causes detectable errors
-----------------------------------
A photon carries no memory of Alice's original basis. When Eve guesses the
wrong basis (which happens ~50% of the time), she collapses the quantum
state into one of two polarisations that are incompatible with Alice's
original encoding. Bob then receives a corrupted photon.

Even if Bob later uses the SAME basis as Alice, he still measures the wrong
bit ~50% of the time on the photons that Eve disturbed.

Net effect on the sifted key:
  - ~50%  of photons are intercepted with a wrong basis guess  (Eve errors)
  - Of those, ~50% cause Bob to measure the wrong bit
  - → ~25% of the final sifted key bits are wrong  (Quantum Bit Error Rate)

A QBER of ~25% is the signature of a full (100%) intercept-and-resend attack
and is well above the safe threshold (typically 11% for BB84).

Encoding table (mirrors Alice's):
  basis 0 (+, Rectilinear) | bit 0 → state 0  (horizontal  ↔,   0°)
  basis 0 (+, Rectilinear) | bit 1 → state 1  (vertical    ↕,  90°)
  basis 1 (x, Diagonal)   | bit 0 → state 2  (diagonal    ↗,  45°)
  basis 1 (x, Diagonal)   | bit 1 → state 3  (diagonal    ↖, 135°)

Dependencies: random, alice, bob
"""

import random
from alice import Alice
from bob import Bob


class Eve:
    """
    Represents Eve — the eavesdropper in the BB84 QKD protocol.

    Eve mounts an intercept-and-resend attack on the quantum channel.
    She can be configured to intercept any fraction of photons, from none
    (passive; identical to no eavesdropping) to all (worst-case attack).

    Attributes:
        intercept_probability (float): Probability [0.0, 1.0] that Eve
                                       intercepts any individual photon.
        guessed_bases        (list):  Eve's randomly chosen basis per
                                       intercepted photon.
        measurements         (list):  Eve's measurement result per
                                       intercepted photon.
        intercepted_indices  (list):  Qubit indices that Eve intercepted.
        _total_photons       (int):   Total photons seen (set during intercept).
        _correct_guesses     (int):   How many times Eve's basis matched Alice's.
    """

    def __init__(self, intercept_probability: float = 1.0):
        """
        Initialise Eve with a given interception rate.

        Args:
            intercept_probability (float): Fraction of photons Eve intercepts.
                - 1.0 → Full attack  (intercepts every photon)
                - 0.5 → Partial attack (intercepts every other photon on average)
                - 0.0 → Passive (intercepts nothing; QBER stays ~0%)
                Must be in [0.0, 1.0].

        Raises:
            ValueError: If intercept_probability is outside [0.0, 1.0].
        """
        if not (0.0 <= intercept_probability <= 1.0):
            raise ValueError(
                f"intercept_probability must be in [0.0, 1.0], "
                f"got {intercept_probability}"
            )

        self.intercept_probability = intercept_probability

        # Per-photon records for intercepted photons only
        self.guessed_bases       = []  # Eve's basis guess at each intercepted qubit
        self.measurements        = []  # Eve's measurement result at each intercepted qubit
        self.intercepted_indices = []  # Which qubit indices Eve actually intercepted

        # Internal counters set during intercept()
        self._total_photons  = 0   # Total photons in the stream
        self._correct_guesses = 0  # How many of Eve's basis guesses were correct

    # ------------------------------------------------------------------
    # Core Attack: Intercept and Resend
    # ------------------------------------------------------------------
    def intercept(self, photon_states: list) -> list:
        """
        Perform the intercept-and-resend attack on a stream of photons.

        For each photon Eve decides (probabilistically) whether to intercept.

        If she intercepts:
          1. She randomly guesses a measurement basis (0 = +, 1 = x).
          2. She measures the photon:
             - Correct basis → deterministic (recovers the original bit).
             - Wrong basis   → random bit (quantum collapse, 50/50).
          3. She re-encodes her measurement result into a NEW photon using
             HER chosen basis and forwards THAT to Bob.
             → If her basis was wrong, Bob now receives a corrupted photon.

        If she does NOT intercept:
          The original photon passes through to Bob completely undisturbed.

        Args:
            photon_states (list): Original list of photon polarisation states
                                  (integers 0–3) produced by Alice.

        Returns:
            list: Modified photon stream — some photons replaced by Eve's
                  re-emitted versions, others unchanged.

        Note:
            After calling this method, the returned list should be passed
            directly to Bob's measure_photons() instead of Alice's original.
        """
        # ---------- Reset state for a fresh attack ----------
        self.guessed_bases       = []
        self.measurements        = []
        self.intercepted_indices = []
        self._total_photons      = len(photon_states)
        self._correct_guesses    = 0

        # Work on a copy so Alice's original list is never mutated
        modified_states = list(photon_states)

        for i, state in enumerate(photon_states):

            # ---- Decide whether to intercept this photon ----
            # random.random() returns a float in [0.0, 1.0).
            # If intercept_probability=1.0 this is always True.
            # If intercept_probability=0.0 this is always False.
            if random.random() < self.intercept_probability:

                # ---- Record that Eve intercepted this qubit ----
                self.intercepted_indices.append(i)

                # ---- Step 1: Eve randomly guesses a basis ----
                eve_basis = random.randint(0, 1)
                self.guessed_bases.append(eve_basis)

                # ---- Determine the basis Alice originally used ----
                # States 0 and 1 were encoded with rectilinear basis (0).
                # States 2 and 3 were encoded with diagonal basis (1).
                alice_basis = 0 if state in (0, 1) else 1

                # ---- Step 2: Eve measures the photon ----
                if eve_basis == alice_basis:
                    # Bases match: Eve measures the correct bit deterministically.
                    # Within each basis pair, even state → bit 0, odd state → bit 1:
                    #   Rectilinear: state 0 → 0,  state 1 → 1
                    #   Diagonal:    state 2 → 0,  state 3 → 1
                    eve_bit = 0 if state in (0, 2) else 1
                    self._correct_guesses += 1
                else:
                    # Bases mismatch: quantum randomness forces a 50/50 outcome.
                    # Eve has NO information about the original bit.
                    eve_bit = random.randint(0, 1)

                self.measurements.append(eve_bit)

                # ---- Step 3: Eve re-encodes and resends ----
                # Eve creates a brand-new photon using her measured bit and
                # her chosen basis.  This mirrors Alice's encoding table exactly.
                if eve_basis == 0 and eve_bit == 0:
                    new_state = 0   # Horizontal polarisation (↔, 0°)
                elif eve_basis == 0 and eve_bit == 1:
                    new_state = 1   # Vertical polarisation   (↕, 90°)
                elif eve_basis == 1 and eve_bit == 0:
                    new_state = 2   # 45° diagonal            (↗, 45°)
                else:               # eve_basis == 1 and eve_bit == 1
                    new_state = 3   # 135° diagonal           (↖, 135°)

                # Replace the original photon with Eve's re-emitted one
                modified_states[i] = new_state

            # If Eve doesn't intercept, modified_states[i] remains unchanged.

        return modified_states

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    def get_statistics(self) -> dict:
        """
        Return a summary of Eve's interception activity as a dictionary.

        Should be called after intercept() has been run.

        Returns:
            dict with keys:
                total_photons         (int):   Total photons in the stream.
                intercepted_count     (int):   Number Eve actually intercepted.
                interception_rate     (float): intercepted / total × 100 (%).
                correct_basis_guesses (int):   Times Eve's basis matched Alice's.
                basis_accuracy        (float): correct / intercepted × 100 (%).
        """
        intercepted = len(self.intercepted_indices)
        total       = self._total_photons

        # Avoid division by zero if intercept() hasn't been called or nothing intercepted
        interception_rate = (intercepted / total * 100) if total > 0 else 0.0
        basis_accuracy    = (self._correct_guesses / intercepted * 100) if intercepted > 0 else 0.0

        return {
            "total_photons":         total,
            "intercepted_count":     intercepted,
            "interception_rate":     interception_rate,
            "correct_basis_guesses": self._correct_guesses,
            "basis_accuracy":        basis_accuracy,
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def print_attack_report(self):
        """
        Print a formatted box-style report summarising Eve's attack.

        Displays interception counts, basis-guess accuracy, and the
        number of wrong-basis measurements that will have disturbed
        Bob's photon stream.

        Example output:
            ╔══════════════════════════════════╗
            ║       EVE'S ATTACK REPORT        ║
            ╠══════════════════════════════════╣
            ║ Total Photons:        100        ║
            ║ Intercepted:          100 (100%) ║
            ║ Correct Basis Guess:   51  (51%) ║
            ║ Wrong Basis Guess:     49  (49%) ║
            ╚══════════════════════════════════╝
        """
        stats        = self.get_statistics()
        total        = stats["total_photons"]
        intercepted  = stats["intercepted_count"]
        inter_rate   = stats["interception_rate"]
        correct      = stats["correct_basis_guesses"]
        wrong        = intercepted - correct
        accuracy     = stats["basis_accuracy"]
        wrong_pct    = 100.0 - accuracy if intercepted > 0 else 0.0

        # Build each data line — pad to a fixed inner width for the box
        inner_width = 34  # characters inside the ║ … ║ borders

        def box_line(text: str) -> str:
            """Centre-pad `text` inside the box borders."""
            return f"║ {text:<{inner_width - 2}} ║"

        border_top    = "╔" + "═" * inner_width + "╗"
        border_mid    = "╠" + "═" * inner_width + "╣"
        border_bottom = "╚" + "═" * inner_width + "╝"
        title         = "EVE'S ATTACK REPORT".center(inner_width - 2)

        print(f"\n{border_top}")
        print(f"║ {title} ║")
        print(border_mid)
        print(box_line(f"Total Photons:        {total}"))
        print(box_line(f"Intercepted:          {intercepted} ({inter_rate:.0f}%)"))
        print(box_line(f"Correct Basis Guess:  {correct} ({accuracy:.0f}%)"))
        print(box_line(f"Wrong Basis Guess:    {wrong} ({wrong_pct:.0f}%)"))
        print(f"{border_bottom}\n")


# ======================================================================
# Standalone Test — runs only when this file is executed directly
# ======================================================================
if __name__ == "__main__":

    # -------------------------------------------------------------------
    # Helper: calculate QBER between two sifted keys
    # -------------------------------------------------------------------
    def calculate_qber(alice_key: list, bob_key: list) -> float:
        """
        Quantum Bit Error Rate = fraction of sifted bits that differ.

        Args:
            alice_key (list): Alice's sifted bits.
            bob_key   (list): Bob's sifted bits at the same positions.

        Returns:
            float: QBER in [0.0, 1.0].  Multiply by 100 for a percentage.
        """
        if len(alice_key) == 0:
            return 0.0
        errors = sum(a != b for a, b in zip(alice_key, bob_key))
        return errors / len(alice_key)

    NUM_QUBITS = 100   # Use 100 qubits for statistically meaningful results

    # ===================================================================
    # TEST 1: Full eavesdropping — Eve intercepts every photon
    # ===================================================================
    print("=" * 60)
    print(" TEST 1: Full Eavesdropping (intercept_probability = 1.0)")
    print("=" * 60)

    # --- Alice prepares photons ---
    alice = Alice(NUM_QUBITS)
    alice.generate_bits()
    alice.generate_bases()
    alice.encode_photons()

    # --- Eve intercepts the entire photon stream ---
    eve = Eve(intercept_probability=1.0)
    modified_photons = eve.intercept(alice.photon_states)

    # Print Eve's attack report (she intercepted everything)
    eve.print_attack_report()

    # --- Bob measures Eve's (corrupted) photons ---
    bob = Bob(NUM_QUBITS)
    bob.generate_bases()
    bob.measure_photons(modified_photons)     # ← Bob sees Eve's photons, not Alice's

    # --- Basis reconciliation: Alice and Bob compare bases publicly ---
    matching_indices, bob_sifted = bob.sift_key(alice.bases, bob.bases)

    # --- Extract Alice's sifted key at the same matching indices ---
    alice_sifted = alice.get_sifted_key(matching_indices)

    # --- Compute QBER ---
    qber = calculate_qber(alice_sifted, bob_sifted)

    print(f"Sifted key length : {len(alice_sifted)} bits")
    print(f"Alice sifted key  : {alice_sifted[:20]}{'...' if len(alice_sifted) > 20 else ''}")
    print(f"Bob   sifted key  : {bob_sifted[:20]}{'...' if len(bob_sifted) > 20 else ''}")
    print()
    print("Expected QBER ~25% with full eavesdropping")
    print(f"Actual   QBER: {qber:.2%}")

    # QBER should sit between ~15% and ~35% for a full attack on 100 qubits
    if 0.15 < qber < 0.35:
        print("TEST PASSED ✓  (QBER within expected 15–35% range)\n")
    else:
        print("TEST FAILED ✗  (QBER outside expected range — possible bug)\n")

    # ===================================================================
    # TEST 2: No eavesdropping — Eve intercepts nothing
    # ===================================================================
    print("=" * 60)
    print(" TEST 2: No Eavesdropping  (intercept_probability = 0.0)")
    print("=" * 60)

    # --- Alice prepares a fresh batch ---
    alice2 = Alice(NUM_QUBITS)
    alice2.generate_bits()
    alice2.generate_bases()
    alice2.encode_photons()

    # --- Eve is passive — photons pass through untouched ---
    eve2 = Eve(intercept_probability=0.0)
    unmodified_photons = eve2.intercept(alice2.photon_states)

    eve2.print_attack_report()   # Should show 0 intercepted

    # --- Bob measures the unmodified photon stream ---
    bob2 = Bob(NUM_QUBITS)
    bob2.generate_bases()
    bob2.measure_photons(unmodified_photons)

    # --- Sift ---
    matching_indices2, bob_sifted2 = bob2.sift_key(alice2.bases, bob2.bases)
    alice_sifted2 = alice2.get_sifted_key(matching_indices2)

    # --- Compute QBER ---
    qber2 = calculate_qber(alice_sifted2, bob_sifted2)

    print(f"Sifted key length : {len(alice_sifted2)} bits")
    print()
    print("No eavesdropping — QBER should be ~0%")
    print(f"Actual   QBER: {qber2:.2%}")

    # Without Eve, the QBER must be exactly 0%
    if qber2 == 0.0:
        print("TEST PASSED ✓  (QBER is exactly 0% — no eavesdropping confirmed)\n")
    else:
        print("TEST FAILED ✗  (Non-zero QBER without Eve — there is a bug)\n")
