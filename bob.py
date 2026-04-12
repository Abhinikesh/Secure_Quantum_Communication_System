"""
bob.py - Part 2 of 7: Bob's Role in the BB84 QKD Protocol
===========================================================

In the BB84 Quantum Key Distribution protocol, Bob is the RECEIVER.
His responsibilities are:

1. Randomly choose a measurement basis for each incoming photon.
   (He does this blindly — he has NO knowledge of Alice's bases.)
2. Measure each photon using his chosen basis:
   - If his basis MATCHES Alice's: he always recovers the correct bit.
   - If his basis MISMATCHES Alice's: quantum mechanics forces a
     random outcome (50/50 chance — he gets the wrong bit half the time).
3. After measurement, Bob and Alice publicly compare their basis choices
   over a classical (non-secret) channel.
4. Discard bits where bases didn't match — keep only the "sifted key".

Measurement Outcome Rules (core BB84 quantum physics):
  Bob basis 0 (+, Rectilinear) measures states 0 or 1:
    - State 0 → bit 0  (correct if Alice used basis 0)
    - State 1 → bit 1  (correct if Alice used basis 0)
  Bob basis 1 (x, Diagonal) measures states 2 or 3:
    - State 2 → bit 0  (correct if Alice used basis 1)
    - State 3 → bit 1  (correct if Alice used basis 1)
  Basis mismatch → random bit (quantum indeterminacy)

Dependencies: random, alice
"""

import random
from alice import Alice


class Bob:
    """
    Represents Bob — the receiver in the BB84 Quantum Key Distribution protocol.

    Bob randomly selects measurement bases and measures incoming photons from
    Alice (or a potentially intercepted stream from Eve). After public basis
    comparison with Alice, he extracts the sifted key from positions where
    both parties used the same measurement basis.

    Attributes:
        num_qubits   (int):  Total number of photons Bob will receive and measure.
        bases        (list): Bob's randomly chosen measurement bases (0=+, 1=x).
        measurements (list): Bob's raw measurement outcomes after measuring photons.
        raw_key      (list): Bob's sifted key — measurements kept at matching-basis indices.
    """

    def __init__(self, num_qubits: int):
        """
        Initialise Bob with a given number of qubits.

        Args:
            num_qubits (int): Number of photons Bob expects to receive.

        Sets up empty lists for bases, measurements, and raw_key, which are
        populated when the respective methods are called.
        """
        self.num_qubits   = num_qubits  # Total photons Bob will measure
        self.bases        = []           # Bob's random basis choices (0 = +, 1 = x)
        self.measurements = []           # Raw bit results after measuring each photon
        self.raw_key      = []           # Sifted key (measurements at matching-basis positions)

    # ------------------------------------------------------------------
    # Step 1: Generate Random Measurement Bases
    # ------------------------------------------------------------------
    def generate_bases(self) -> list:
        """
        Randomly choose a measurement basis for each incoming photon.

        Bob selects his bases completely independently of Alice — he has no
        information about which basis Alice used. This randomness is crucial:
        it guarantees that, on average, ~50% of bases will match Alice's,
        and any eavesdropping by Eve will disturb the quantum states in a
        statistically detectable way.

          - 0 → Rectilinear basis (+): measures horizontal / vertical polarization
          - 1 → Diagonal basis (x):   measures 45° / 135° diagonal polarization

        Returns:
            list: A list of `num_qubits` random bases, each 0 or 1.

        Example:
            bob.generate_bases()  →  [1, 0, 0, 1, 0, 1, 1, 0, ...]
        """
        # Use Python's built-in random module (consistent with the rest of Bob's logic)
        # random.randint(0, 1) is inclusive on both ends → gives 0 or 1
        self.bases = [random.randint(0, 1) for _ in range(self.num_qubits)]
        return self.bases

    # ------------------------------------------------------------------
    # Step 2: Measure Incoming Photons
    # ------------------------------------------------------------------
    def measure_photons(self, photon_states: list) -> list:
        """
        Measure each photon using Bob's previously chosen basis.

        This is the quantum measurement step.  Two outcomes are possible:

        MATCHING BASIS (Bob's basis == the basis Alice used to encode the photon):
            Bob's detector is aligned with the photon's polarisation axis, so he
            always recovers the correct bit — this is deterministic quantum physics.

            Rectilinear basis (Bob basis = 0) correctly measures states 0 and 1:
              state 0 (0°)  → bit 0
              state 1 (90°) → bit 1

            Diagonal basis (Bob basis = 1) correctly measures states 2 and 3:
              state 2 (45°)  → bit 0
              state 3 (135°) → bit 1

        MISMATCHING BASIS (Bob's basis ≠ Alice's basis):
            The photon's polarisation is incompatible with Bob's measurement axis.
            Quantum mechanics (Born rule) collapses the state to 0 or 1 with equal
            50% probability — purely random.  Bob cannot know the original bit.

        Basis identification for each photon state:
            states 0, 1  →  encoded with Alice's basis 0 (Rectilinear)
            states 2, 3  →  encoded with Alice's basis 1 (Diagonal)

        Args:
            photon_states (list): List of photon polarisation states (integers 0–3)
                                  received from Alice (or from Eve if intercepted).

        Returns:
            list: Bob's measurement outcomes — a list of bits (0 or 1) for each photon.
        """
        self.measurements = []  # Reset before measuring

        for i, state in enumerate(photon_states):
            bob_basis = self.bases[i]

            # Determine which basis Alice originally used to create this photon state.
            # Rectilinear states: 0 (horizontal) and 1 (vertical)  → alice_basis = 0
            # Diagonal    states: 2 (45°) and 3 (135°)             → alice_basis = 1
            alice_basis = 0 if state in (0, 1) else 1

            if bob_basis == alice_basis:
                # ---- Bases MATCH: deterministic, always correct ----
                # Decode the photon's polarisation state into the original bit.
                # Within each basis pair, even state → 0, odd state → 1:
                #   Rectilinear: state 0 → bit 0,  state 1 → bit 1
                #   Diagonal:    state 2 → bit 0,  state 3 → bit 1
                measured_bit = 0 if state in (0, 2) else 1
            else:
                # ---- Bases MISMATCH: quantum randomness (50 / 50) ----
                # The measuring device disrupts the photon's superposition.
                # The outcome is genuinely random — Bob gains no information
                # about Alice's original bit.
                measured_bit = random.randint(0, 1)

            self.measurements.append(measured_bit)

        return self.measurements

    # ------------------------------------------------------------------
    # Step 3: Sift the Key (Basis Reconciliation)
    # ------------------------------------------------------------------
    def sift_key(self, alice_bases: list, bob_bases: list):
        """
        Compare Alice's and Bob's basis lists to extract the sifted key.

        After the quantum channel transmission is complete, Alice and Bob
        communicate over a PUBLIC classical channel to compare which basis
        they each used for every qubit.  They do NOT reveal the bits themselves.

        Any qubit where the bases differ is discarded — Bob's measurement of
        those photons is random and carries no information.  Qubits where both
        used the SAME basis form the "sifted key", which is the shared secret
        material used in subsequent error-correction and privacy-amplification steps.

        On average, ~50% of qubits survive sifting (since bases are chosen randomly).

        Args:
            alice_bases (list): Alice's basis choices (0 or 1) for each qubit.
            bob_bases   (list): Bob's basis choices   (0 or 1) for each qubit.

        Returns:
            tuple:
                matching_indices (list): Indices where Alice's and Bob's bases matched.
                raw_key          (list): Bob's measurements at those matching indices.
        """
        # Find every index where Alice and Bob both chose the same basis
        matching_indices = [
            i for i in range(len(alice_bases))
            if alice_bases[i] == bob_bases[i]
        ]

        # Extract Bob's measurement results only at the matched positions
        self.raw_key = [self.measurements[i] for i in matching_indices]

        # ---- Statistics -----------------------------------------------
        total       = len(alice_bases)
        num_matches = len(matching_indices)
        match_rate  = (num_matches / total) * 100 if total > 0 else 0.0

        print(f"\nBasis match rate:   {match_rate:.1f}%")
        print(f"Sifted key length:  {num_matches} bits (from {total} total)")

        return matching_indices, self.raw_key

    # ------------------------------------------------------------------
    # Utility: Side-by-side Comparison Table
    # ------------------------------------------------------------------
    def print_comparison(self, alice_bits: list, alice_bases: list, limit: int = 20):
        """
        Print a formatted table comparing Alice's and Bob's values side-by-side.

        For each qubit (up to `limit`), shows:
          - Alice's original bit
          - Alice's chosen basis (+ or x)
          - Bob's chosen basis   (+ or x)
          - Bob's measurement outcome
          - Whether the bases matched (✓) or not (✗)

        This gives an at-a-glance view of the BB84 exchange: rows with ✓ are
        the ones that contribute to the sifted key; rows with ✗ are discarded.

        Args:
            alice_bits  (list): Alice's original bit values.
            alice_bases (list): Alice's chosen bases (0 or 1).
            limit       (int):  Maximum rows to print (default 20).
        """
        n = min(limit, self.num_qubits)  # Never exceed the actual qubit count

        print("\n=== Alice ↔ Bob Measurement Comparison ===\n")

        # Table header
        header = (
            f"{'Qubit':^7} | {'Alice Bit':^9} | {'Alice Basis':^11} | "
            f"{'Bob Basis':^9} | {'Bob Measurement':^15} | {'Match?':^7}"
        )
        separator = "-" * len(header)
        print(header)
        print(separator)

        for i in range(n):
            alice_bit         = alice_bits[i]
            alice_basis_sym   = '+' if alice_bases[i] == 0 else 'x'
            bob_basis_sym     = '+' if self.bases[i]  == 0 else 'x'
            bob_measurement   = self.measurements[i]

            # Mark whether the bases agreed — ✓ = sifted key, ✗ = discarded
            match_symbol = '✓' if alice_bases[i] == self.bases[i] else '✗'

            print(
                f"  {i:<4}  |    {alice_bit:<6} |     {alice_basis_sym:<9} |"
                f"    {bob_basis_sym:<7} |       {bob_measurement:<11} | {match_symbol:^7}"
            )

        print(separator)

        if self.num_qubits > limit:
            print(f"  ... ({self.num_qubits - limit} more qubits not shown)")
        print()


# ======================================================================
# Standalone Test — runs only when this file is executed directly
# ======================================================================
if __name__ == "__main__":

    # ---- Setup --------------------------------------------------------
    NUM_QUBITS = 20

    # ---- Step 1: Alice prepares and sends photons ---------------------
    alice = Alice(NUM_QUBITS)
    alice.generate_bits()          # Alice creates random bits
    alice.generate_bases()         # Alice picks random encoding bases
    alice.encode_photons()         # Alice encodes bits into photon states

    # ---- Step 2: Bob receives and measures photons --------------------
    bob = Bob(NUM_QUBITS)
    bob.generate_bases()                           # Bob picks random measurement bases
    bob.measure_photons(alice.photon_states)       # Bob measures the photons from Alice

    # ---- Step 3: Basis reconciliation (sifting) -----------------------
    # Alice and Bob compare bases over the public classical channel.
    # Neither reveals their actual bits — only which basis they used.
    matching_indices, bob_raw_key = bob.sift_key(alice.bases, bob.bases)

    # ---- Step 4: Print side-by-side comparison table ------------------
    bob.print_comparison(alice.bits, alice.bases, limit=NUM_QUBITS)

    # ---- Step 5: Extract Alice's sifted key for verification ----------
    alice_sifted = alice.get_sifted_key(matching_indices)

    print("=== Sifted Key Comparison ===\n")
    print(f"  Matching indices : {matching_indices}")
    print(f"  Alice sifted key : {alice_sifted}")
    print(f"  Bob   sifted key : {bob_raw_key}")

    # ---- Step 6: Core BB84 Guarantee Verification ---------------------
    # Without Eve, Bob's measurements at EVERY matching-basis index MUST
    # exactly equal Alice's original bits at those same indices.
    # This is the fundamental correctness property of BB84 — if this fails,
    # there is a bug in the implementation.
    print("\n=== BB84 Core Guarantee Verification ===\n")

    if alice_sifted == bob_raw_key:
        print("  VERIFICATION PASSED ✓")
        print("  All sifted bits match — no eavesdropping, no errors.")
    else:
        print("  VERIFICATION FAILED ✗")
        print("  Sifted bits do NOT match — there is a bug in the simulation.")
        # Print the specific mismatches for debugging
        for idx, (a_bit, b_bit) in enumerate(zip(alice_sifted, bob_raw_key)):
            if a_bit != b_bit:
                qubit_pos = matching_indices[idx]
                print(
                    f"  Mismatch at qubit {qubit_pos}: "
                    f"Alice={a_bit}, Bob={b_bit}"
                )
