"""
alice.py - Part 1 of 7: Alice's Role in the BB84 QKD Protocol
==============================================================

In the BB84 Quantum Key Distribution protocol, Alice is the SENDER.
Her responsibilities are:

1. Generate a random sequence of classical bits (0s and 1s).
2. Randomly choose a measurement basis for each bit:
   - Rectilinear basis (+): encodes bits as horizontal (0°) or vertical (90°) polarization.
   - Diagonal basis (x):   encodes bits as 45° or 135° diagonal polarization.
3. Encode each bit into a photon polarization state based on bit + basis.
4. Send the encoded photons to Bob over the quantum channel.
5. After Bob measures and they publicly compare bases (via classical channel),
   keep only the bits where both used the SAME basis — this forms the "sifted key".

Photon State Encoding Table:
  Basis 0 (+, Rectilinear) | Bit 0 → State 0 (horizontal ↔,  0°)
  Basis 0 (+, Rectilinear) | Bit 1 → State 1 (vertical   ↕, 90°)
  Basis 1 (x, Diagonal)   | Bit 0 → State 2 (diagonal   ↗, 45°)
  Basis 1 (x, Diagonal)   | Bit 1 → State 3 (diagonal   ↖,135°)

Dependencies: numpy
"""

import numpy as np


class Alice:
    """
    Represents Alice — the sender in the BB84 Quantum Key Distribution protocol.

    Alice prepares random quantum states (photons) and sends them to Bob.
    After the quantum transmission and public basis comparison, she extracts
    the sifted key from positions where she and Bob used the same basis.

    Attributes:
        num_qubits (int):       Total number of qubits (photons) to prepare.
        bits (list):            Alice's randomly generated classical bits.
        bases (list):           Alice's randomly chosen measurement bases.
        photon_states (list):   Encoded photon polarization states (0–3).
    """

    def __init__(self, num_qubits: int):
        """
        Initialize Alice with a given number of qubits.

        Args:
            num_qubits (int): The number of qubits Alice will prepare and send.

        Sets up empty lists for bits, bases, and photon_states, which will
        be populated when the respective generate/encode methods are called.
        """
        self.num_qubits = num_qubits   # Total photons to prepare
        self.bits = []                  # Alice's random bit string (0s and 1s)
        self.bases = []                 # Alice's random basis choices (0 = +, 1 = x)
        self.photon_states = []         # Encoded photon polarization states (0, 1, 2, 3)

    # ------------------------------------------------------------------
    # Step 1: Generate Random Bits
    # ------------------------------------------------------------------
    def generate_bits(self) -> list:
        """
        Generate a random sequence of bits for Alice to encode.

        Uses numpy's randint to generate uniformly random 0s and 1s.
        These bits represent the secret key material Alice wants to share
        with Bob (before eavesdropping detection and sifting).

        Returns:
            list: A list of `num_qubits` random bits, each either 0 or 1.

        Example:
            alice.generate_bits()  →  [1, 0, 1, 1, 0, 0, 1, 0, ...]
        """
        # numpy.random.randint(low, high) generates integers in [low, high)
        # So randint(0, 2) produces only 0 or 1
        # Convert numpy int64 → plain Python int for clean printing
        self.bits = [int(b) for b in np.random.randint(0, 2, self.num_qubits)]
        return self.bits

    # ------------------------------------------------------------------
    # Step 2: Generate Random Bases
    # ------------------------------------------------------------------
    def generate_bases(self) -> list:
        """
        Generate a random sequence of measurement bases for Alice to use.

        Each basis is chosen independently at random:
          - 0 → Rectilinear basis (+): horizontal/vertical polarization
          - 1 → Diagonal basis (x):   45°/135° polarization

        In BB84, keeping the basis choice SECRET is critical — Bob doesn't
        know Alice's bases during transmission. They compare bases AFTER
        the quantum channel transmission over a classical (public) channel.

        Returns:
            list: A list of `num_qubits` random bases, each either 0 or 1.

        Example:
            alice.generate_bases()  →  [0, 1, 0, 0, 1, 1, 0, 1, ...]
        """
        # Same technique — 0 means rectilinear (+), 1 means diagonal (x)
        # Convert numpy int64 → plain Python int for clean printing
        self.bases = [int(b) for b in np.random.randint(0, 2, self.num_qubits)]
        return self.bases

    # ------------------------------------------------------------------
    # Step 3: Encode Photons
    # ------------------------------------------------------------------
    def encode_photons(self) -> list:
        """
        Encode each bit–basis pair into a specific photon polarization state.

        This is the quantum step: Alice maps her classical bit + basis choice
        into one of four polarization states that can be physically sent as
        a photon.

        Encoding Table:
          Basis 0 (+) + Bit 0  →  State 0  (Horizontal ↔,   0°)
          Basis 0 (+) + Bit 1  →  State 1  (Vertical   ↕,  90°)
          Basis 1 (x) + Bit 0  →  State 2  (Diagonal   ↗,  45°)
          Basis 1 (x) + Bit 1  →  State 3  (Diagonal   ↖, 135°)

        Requires:
            self.bits and self.bases must already be populated by calling
            generate_bits() and generate_bases() first.

        Returns:
            list: A list of photon polarization states (integers 0–3).

        Raises:
            ValueError: If bits or bases have not been generated yet.
        """
        # Validate that bits and bases have been generated
        if not self.bits or not self.bases:
            raise ValueError(
                "Bits and bases must be generated before encoding photons. "
                "Call generate_bits() and generate_bases() first."
            )

        self.photon_states = []  # Reset before encoding

        for i in range(self.num_qubits):
            bit = self.bits[i]
            basis = self.bases[i]

            # Apply the encoding table using conditional logic
            if basis == 0 and bit == 0:
                state = 0   # Horizontal polarization (↔, 0°)
            elif basis == 0 and bit == 1:
                state = 1   # Vertical polarization   (↕, 90°)
            elif basis == 1 and bit == 0:
                state = 2   # 45° diagonal            (↗, 45°)
            else:           # basis == 1 and bit == 1
                state = 3   # 135° diagonal            (↖, 135°)

            self.photon_states.append(state)

        return self.photon_states

    # ------------------------------------------------------------------
    # Step 4: Extract Sifted Key
    # ------------------------------------------------------------------
    def get_sifted_key(self, matching_indices: list) -> list:
        """
        Extract Alice's sifted key from the positions where bases matched.

        After Alice and Bob publicly compare their basis choices over a
        classical channel, they discard all bits where they used DIFFERENT
        bases. The remaining bits — where both used the SAME basis — form
        the "sifted key", which is used as the foundation for the secret key.

        Args:
            matching_indices (list): A list of qubit indices where Alice's
                                     and Bob's bases were identical.

        Returns:
            list: Alice's bit values at the matching indices only.

        Example:
            If matching_indices = [0, 2, 5] and self.bits = [1, 0, 1, 0, 1, 0]
            → returns [1, 1, 0]  (bits at positions 0, 2, 5)
        """
        # Use list comprehension to extract only the bits at matching positions
        sifted_key = [self.bits[i] for i in matching_indices]
        return sifted_key

    # ------------------------------------------------------------------
    # Utility: Print Alice's Info
    # ------------------------------------------------------------------
    def print_info(self, limit: int = 20):
        """
        Display Alice's bits, bases, and photon states in a readable format.

        Useful for debugging or demonstrating the protocol step-by-step.
        Prints the first `limit` values of each list to avoid overwhelming
        output for large qubit counts.

        Args:
            limit (int): Maximum number of values to print per field.
                         Defaults to 20. If the list is shorter, all values
                         are shown.
        """
        print("\n--- Alice's Prepared Quantum States ---")

        # Truncate lists to the specified limit for display
        bits_display  = self.bits[:limit]
        bases_display = self.bases[:limit]
        states_display = self.photon_states[:limit]

        # Convert basis integers to readable symbols
        basis_symbols = ['+' if b == 0 else 'x' for b in bases_display]

        print(f"  Bits generated  ({limit} shown): {bits_display}")
        print(f"  Bases chosen    ({limit} shown): {basis_symbols}")
        print(f"  Photon states   ({limit} shown): {states_display}")
        print(f"  Total qubits: {self.num_qubits}")
        print("---------------------------------------\n")


# ======================================================================
# Standalone Test — runs only when this file is executed directly
# ======================================================================
if __name__ == "__main__":

    # ---- Setup --------------------------------------------------------
    NUM_QUBITS = 20

    # Mapping from photon state integer → human-readable polarization angle
    STATE_TO_ANGLE = {
        0: "  0°",
        1: " 90°",
        2: " 45°",
        3: "135°",
    }

    # ---- Create Alice and run all steps -------------------------------
    alice = Alice(NUM_QUBITS)

    bits          = alice.generate_bits()    # Step 1: Generate random bits
    bases         = alice.generate_bases()   # Step 2: Choose random bases
    photon_states = alice.encode_photons()   # Step 3: Encode into photon states

    # ---- Print formatted table ----------------------------------------
    print("\n=== ALICE's Quantum State Preparation ===\n")

    # Table header
    header = f"{'Qubit':^7} | {'Bit':^5} | {'Basis':^7} | {'State':^7} | {'Angle':^7}"
    separator = "-" * len(header)
    print(header)
    print(separator)

    # One row per qubit
    for i in range(NUM_QUBITS):
        bit   = bits[i]
        basis = bases[i]
        state = photon_states[i]
        angle = STATE_TO_ANGLE[state]

        # Convert basis integer to symbol for readability
        basis_symbol = '+' if basis == 0 else 'x'

        print(
            f"  {i:<4}  |  {bit:<3}  |   {basis_symbol:<5} |   {state:<4}  | {angle}"
        )

    # ---- Summary section ----------------------------------------------
    print(separator)
    print(f"\nTotal qubits prepared: {NUM_QUBITS}")
    print(f"Bits generated: {bits}")
    print(f"Bases chosen:   {['+' if b == 0 else 'x' for b in bases]}")
    print(f"Photon states:  {photon_states}")

    # ---- Demonstrate get_sifted_key -----------------------------------
    # Simulate a scenario: assume even-indexed qubits had matching bases
    sample_matching = [i for i in range(NUM_QUBITS) if i % 2 == 0]
    sifted = alice.get_sifted_key(sample_matching)
    print(f"\n[Demo] Sifted key (even-index positions): {sifted}")
    print(f"       Sifted key length: {len(sifted)} bits")

    # ---- Use print_info() method --------------------------------------
    alice.print_info(limit=20)
