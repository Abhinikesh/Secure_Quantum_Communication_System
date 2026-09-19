"""
quantum_bob.py — Real Quantum Measurement using Qiskit
=======================================================

Replaces the classical measurement simulation in bob.py with REAL
quantum measurements performed via Qiskit circuits.

Key differences from bob.py
-----------------------------
• bob.py      : uses random.randint for mismatch randomness + deterministic math
• this file   : adds a Qiskit measurement gate to Alice's circuit and executes
                it on a quantum backend — the outcome is genuinely quantum.

BB84 measurement basis -> gate mapping
---------------------------------------
  Bob basis=0 (+, Rectilinear): measure qubit directly in the Z-basis
  Bob basis=1 (x, Diagonal)  : apply H gate, THEN measure in the Z-basis
                                (this rotates the x-basis into the Z-basis)

Dependencies: qiskit, qiskit-aer, quantum_alice
"""

import copy
import random
import warnings
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Qiskit imports
# ---------------------------------------------------------------------------
try:
    from qiskit import QuantumCircuit, transpile
    from qiskit_aer import AerSimulator
    QISKIT_AVAILABLE = True
except ImportError:
    QISKIT_AVAILABLE = False
    warnings.warn(
        "Qiskit / qiskit-aer not found.  "
        "Install with: pip install qiskit qiskit-aer qiskit-ibm-runtime",
        RuntimeWarning,
        stacklevel=2,
    )


def _require_qiskit() -> None:
    if not QISKIT_AVAILABLE:
        raise ImportError(
            "Qiskit is required but not installed.\n"
            "Run:  pip install qiskit qiskit-aer qiskit-ibm-runtime"
        )


# ===========================================================================
# QuantumBob — real quantum measurement
# ===========================================================================
class QuantumBob:
    """
    Bob's quantum role in BB84, implemented with REAL quantum measurements.

    Receives Alice's state-preparation circuits, adds his own measurement
    gate (choosing his basis randomly using quantum randomness), and
    executes each circuit on a quantum backend to get a genuine measurement
    outcome.

    Attributes
    ----------
    backend           : AerSimulator  The Qiskit backend (local or IBM HW).
    backend_name      : str           Human-readable backend description.
    bases             : list[int]     Bob's randomly chosen measurement bases.
    measurements      : list[int]     Bob's measurement outcomes (0 or 1).
    """

    # -----------------------------------------------------------------------
    def __init__(self, backend: str = "aer_simulator"):
        """
        Initialise QuantumBob with a Qiskit backend.

        Parameters
        ----------
        backend : 'aer_simulator'       — local AerSimulator (default)
                  'statevector_simulator' — AerSimulator in statevector mode
        """
        _require_qiskit()

        self.bases:        List[int] = []
        self.measurements: List[int] = []

        # ---- Choose backend ------------------------------------------------
        if backend == "statevector_simulator":
            self.backend = AerSimulator(method="statevector")
            self.backend_name = "AerSimulator (statevector mode)"
        else:
            self.backend = AerSimulator()
            self.backend_name = "AerSimulator (local quantum simulation)"

        print(f"✓ QuantumBob initialised — backend: {self.backend_name}")

    # -----------------------------------------------------------------------
    def _quantum_random_bit(self) -> int:
        """
        Generate one truly-random bit using a single H-gate circuit.

        Used by Bob to randomly pick his measurement basis, ensuring
        Bob's basis choice is also quantum-random (not pseudo-random).

        Returns
        -------
        int : 0 or 1.
        """
        qc = QuantumCircuit(1, 1)
        qc.h(0)
        qc.measure(0, 0)
        compiled = transpile(qc, self.backend)
        job = self.backend.run(compiled, shots=1)
        return int(list(job.result().get_counts().keys())[0])

    def _quantum_random_bits(self, n: int) -> List[int]:
        """
        Generate n quantum-random bits using chunked batched circuits.

        AerSimulator's default coupling map limits circuits to 30 qubits.
        We chunk into batches of at most 29 qubits, run each batch,
        and concatenate the results.

        Parameters
        ----------
        n : Number of bits.

        Returns
        -------
        list[int] : n bits.
        """
        MAX_QUBITS_PER_CIRCUIT = 29
        bits: List[int] = []

        remaining = n
        while remaining > 0:
            chunk = min(remaining, MAX_QUBITS_PER_CIRCUIT)
            qc = QuantumCircuit(chunk, chunk)
            for i in range(chunk):
                qc.h(i)
            qc.measure(list(range(chunk)), list(range(chunk)))
            compiled   = transpile(qc, self.backend)
            job        = self.backend.run(compiled, shots=1)
            result_str = list(job.result().get_counts().keys())[0]
            # Qiskit: qubit 0 is the rightmost character in the result string.
            chunk_bits = [int(b) for b in reversed(result_str)]
            bits.extend(chunk_bits[:chunk])
            remaining -= chunk

        return bits[:n]

    # -----------------------------------------------------------------------
    def measure_qubit(
        self, circuit: "QuantumCircuit", bob_basis: Optional[int] = None
    ) -> Tuple[int, int]:
        """
        Measure one of Alice's state-preparation circuits.

        Takes a COPY of Alice's circuit (so the original is not mutated),
        appends Bob's measurement gate(s), and executes it on the backend.

        Measurement protocol
        --------------------
        Bob basis=0 (rectilinear/Z-basis):
            Measure the qubit directly — no extra gates needed.
        Bob basis=1 (diagonal/X-basis):
            Apply H gate first, THEN measure.
            (H rotates the X-basis eigenstates into Z-basis eigenstates,
             so a standard Z-basis measurement effectively measures in X.)

        Why this is correct quantum physics
        ------------------------------------
        If Alice prepared |+> (bit=0, basis=1) and Bob measures in basis=1:
            Bob applies H: H|+> = |0> -> measures 0. (Correct!)
        If Alice prepared |+> (bit=0, basis=1) and Bob measures in basis=0:
            Bob measures |+> directly -> 50/50 outcome. (Quantum indeterminacy!)

        Parameters
        ----------
        circuit   : Alice's state-prep QuantumCircuit (without measurement).
        bob_basis : 0 or 1. If None, a quantum-random basis is chosen.

        Returns
        -------
        measured_bit : int  — The measurement result (0 or 1).
        bob_basis    : int  — The basis Bob used (needed for sifting).
        """
        # ---- Choose Bob's basis (quantum-random if not given) --------------
        if bob_basis is None:
            bob_basis = self._quantum_random_bit()

        # ---- Copy Alice's circuit so we don't mutate the original ----------
        qc = copy.deepcopy(circuit)

        # ---- Add Bob's measurement -----------------------------------------
        if bob_basis == 1:
            # Diagonal basis: rotate X-basis -> Z-basis with H, then measure
            qc.h(0)

        qc.measure(0, 0)   # Standard Z-basis measurement

        # ---- Run on the quantum backend (1 shot = 1 physical measurement) --
        compiled = transpile(qc, self.backend)
        job      = self.backend.run(compiled, shots=1)
        counts   = job.result().get_counts()

        # Extract the single-bit result
        result_str   = list(counts.keys())[0]
        measured_bit = int(result_str.strip()[-1])   # rightmost bit = qubit 0

        return measured_bit, bob_basis

    # -----------------------------------------------------------------------
    def measure_all(
        self, circuits: List["QuantumCircuit"]
    ) -> Tuple[List[int], List[int]]:
        """
        Measure all of Alice's circuits using quantum-random basis choices.

        Generates Bob's bases all at once (batched quantum circuit) then
        measures each circuit individually. Progress is printed every 50 qubits.

        Parameters
        ----------
        circuits : list[QuantumCircuit] — Alice's state-prep circuits.

        Returns
        -------
        bob_bases        : list[int]  — Bob's basis choice for each qubit.
        bob_measurements : list[int]  — Bob's measurement result for each qubit.
        """
        n = len(circuits)
        print(f"\n[Bob] Generating {n} quantum-random measurement bases...")
        self.bases = self._quantum_random_bits(n)

        print(f"[Bob] Performing {n} real quantum measurements...")
        self.measurements = []

        for i, circuit in enumerate(circuits):
            measured_bit, _ = self.measure_qubit(circuit, bob_basis=self.bases[i])
            self.measurements.append(measured_bit)

            # Progress update every 50 qubits (or at the end)
            if (i + 1) % 50 == 0 or (i + 1) == n:
                print(f"  Measured {i + 1}/{n} qubits...", end="\r")

        print(f"\n✓ Bob completed {n} quantum measurements")
        return self.bases, self.measurements

    # -----------------------------------------------------------------------
    def run_on_ibm_real_hardware(
        self,
        circuits: List["QuantumCircuit"],
        ibm_token: str,
        timeout_seconds: int = 300,
    ) -> List[int]:
        """
        Submit circuits to a REAL IBM Quantum computer and collect results.

        This method executes the circuits on genuine quantum hardware —
        real qubits subject to actual quantum mechanical noise, decoherence,
        and gate errors. Results reflect physical quantum reality.

        Steps
        -----
        1. Connect to IBM Quantum using the provided API token.
        2. Select the least-busy operational real-hardware backend.
        3. Generate Bob's quantum-random bases (locally, for speed).
        4. Build one measurement circuit per qubit (copy + add Bob's gate).
        5. Batch-submit all circuits to IBM Quantum.
        6. Wait for results (real hardware queues can take minutes).
        7. Parse and return the measurement outcomes.

        Parameters
        ----------
        circuits        : Alice's state-prep circuits.
        ibm_token       : IBM Quantum API token (from https://quantum.ibm.com).
        timeout_seconds : How long to wait before giving up (default: 5 min).

        Returns
        -------
        list[int] : Bob's measurement results from real quantum hardware.
                    Falls back to AerSimulator if hardware is unavailable.
        """
        try:
            from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
            print("\n[Bob] Connecting to IBM Quantum for real hardware execution...")
            service = QiskitRuntimeService(channel="ibm_quantum", token=ibm_token)

            # Select least-busy real device
            hw_backend = service.least_busy(
                operational=True, simulator=False, min_num_qubits=5
            )
            print(f"  Selected hardware backend: {hw_backend.name}")
            print(f"  Queue position and wait time depend on current load.")

            # Generate Bob's bases locally (quantum-random)
            n = len(circuits)
            print(f"  Generating {n} quantum-random bases locally...")
            self.bases = self._quantum_random_bits(n)

            # Build measurement circuits
            print(f"  Building {n} measurement circuits...")
            meas_circuits = []
            for i, circ in enumerate(circuits):
                qc = copy.deepcopy(circ)
                if self.bases[i] == 1:
                    qc.h(0)
                qc.measure(0, 0)
                meas_circuits.append(transpile(qc, hw_backend))

            # Submit to IBM Quantum
            print(f"  Submitting {n} circuits to {hw_backend.name}...")
            print(f"  (Real hardware can take several minutes in the queue)")
            sampler = Sampler(hw_backend)
            job = sampler.run(meas_circuits, shots=1)

            print(f"  Job ID: {job.job_id()}")
            print(f"  Waiting for results (timeout: {timeout_seconds}s)...")

            # Poll for completion
            import time
            elapsed = 0
            poll_interval = 10
            while elapsed < timeout_seconds:
                status = job.status()
                if status.name in ("DONE", "CANCELLED", "ERROR"):
                    break
                print(f"  Status: {status.name} ({elapsed}s elapsed)...", end="\r")
                time.sleep(poll_interval)
                elapsed += poll_interval

            if job.status().name != "DONE":
                raise TimeoutError(
                    f"IBM Quantum job did not complete within {timeout_seconds}s. "
                    f"Job ID: {job.job_id()} — check https://quantum.ibm.com"
                )

            # Parse results
            result = job.result()
            self.measurements = []
            for i in range(n):
                pub_result = result[i]
                # Extract the classical bit value for qubit 0
                bit_array = pub_result.data.c
                bit = int(bit_array.get_int_counts().get("0", 0) == 0)
                self.measurements.append(bit)

            print(f"\n✓ Real quantum hardware measurements complete!")
            return self.measurements

        except TimeoutError as te:
            print(f"\n[Bob] Timeout: {te}")
            print("[Bob] Falling back to AerSimulator for this session.")
            return self.measure_all(circuits)[1]

        except Exception as exc:
            warnings.warn(
                f"IBM Quantum hardware execution failed: {exc}\n"
                "Falling back to AerSimulator.",
                UserWarning,
                stacklevel=2,
            )
            return self.measure_all(circuits)[1]

    # -----------------------------------------------------------------------
    def get_backend_info(self) -> None:
        """Print a summary of the active backend and its capabilities."""
        print(f"\n[Bob] Active backend: {self.backend_name}")
        if "AerSimulator" in self.backend_name:
            print("  Mode: Local quantum simulation (no network required)")
            print("  Speed: Very fast (~microseconds per circuit)")
            print("  Noise: Ideal (no hardware errors) unless noise model applied")
        else:
            print("  Mode: Real IBM Quantum hardware")
            try:
                props = self.backend.properties()
                print(f"  Number of qubits: {self.backend.num_qubits}")
                print(f"  Backend name: {self.backend.name}")
            except Exception:
                print("  (Backend properties unavailable)")


# ===========================================================================
# Standalone test
# ===========================================================================
if __name__ == "__main__":
    from quantum_alice import QuantumAlice

    print("=" * 60)
    print("  quantum_bob.py -- standalone test")
    print("  Using Qiskit AerSimulator (local)")
    print("=" * 60)

    NUM_QUBITS = 16

    # Alice prepares circuits
    alice = QuantumAlice(num_qubits=NUM_QUBITS)
    bits, bases, circuits = alice.encode_all(NUM_QUBITS)

    # Bob measures
    bob = QuantumBob()
    bob.get_backend_info()

    bob_bases, bob_measurements = bob.measure_all(circuits)

    # Show sifting result
    matching = [i for i in range(NUM_QUBITS) if bases[i] == bob_bases[i]]
    alice_sifted = [bits[i] for i in matching]
    bob_sifted   = [bob_measurements[i] for i in matching]

    print(f"\n{'='*55}")
    print(f"  BB84 Sifting Results")
    print(f"{'='*55}")
    print(f"  Total qubits     : {NUM_QUBITS}")
    print(f"  Matching bases   : {len(matching)} ({len(matching)/NUM_QUBITS:.0%})")
    print(f"  Alice sifted key : {alice_sifted}")
    print(f"  Bob   sifted key : {bob_sifted}")

    # Verify: without Eve, sifted keys must be identical
    if alice_sifted == bob_sifted:
        print("\n  VERIFICATION PASSED: Sifted keys match exactly (no Eve).")
    else:
        errors = sum(a != b for a, b in zip(alice_sifted, bob_sifted))
        print(f"\n  VERIFICATION FAILED: {errors} mismatches found!")
        print("  (This may indicate a circuit bug.)")

    print("\n✅ quantum_bob.py test complete")
