"""
network_bob.py — Bob as a Real TCP/IP Network Client
=====================================================

Bob is the CLIENT node in the BB84 QKD protocol.
He connects to Alice's server and participates in the full 5-phase
BB84 handshake over a real network socket.

Protocol Phases
---------------
  Phase 1  QUANTUM_TRANSMISSION   Alice → Bob   receive photon states
  Phase 2  BASIS_EXCHANGE         Alice ↔ Bob   exchange bases
  Phase 3  SIFTING_CONFIRM        Alice → Bob   verify matching count
  Phase 4  QBER_CHECK             Alice ↔ Bob   send sample + get decision
  Phase 5  KEY_HASH               Alice → Bob   verify key hash

Run
---
  python network_bob.py                    # Connect to localhost (same machine)
  python network_bob.py 192.168.1.42       # Connect to Alice on another machine

Dependencies: bob.py (existing project file)
"""

import hashlib
import json
import random
import socket
import struct
import sys
import time
from typing import Any, Dict, List, Optional

from bob import Bob


# ── ANSI colour helpers ────────────────────────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ══════════════════════════════════════════════════════════════════════════
# Framing helpers (identical to network_alice.py — shared wire format)
# ══════════════════════════════════════════════════════════════════════════

def _send_message(sock: socket.socket, payload: Dict[str, Any]) -> int:
    """Send a length-prefixed JSON message. Returns total bytes sent."""
    body   = json.dumps(payload).encode("utf-8")
    header = struct.pack(">I", len(body))
    sock.sendall(header + body)
    return len(header) + len(body)


def _recv_message(sock: socket.socket) -> Dict[str, Any]:
    """Receive a length-prefixed JSON message and return the dict."""
    raw_len  = _recv_exact(sock, 4)
    body_len = struct.unpack(">I", raw_len)[0]
    raw_body = _recv_exact(sock, body_len)
    return json.loads(raw_body.decode("utf-8"))


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly *n* bytes, handling TCP fragmentation."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(
                f"Connection closed after {len(buf)}/{n} bytes."
            )
        buf.extend(chunk)
    return bytes(buf)


def _ts() -> str:
    """Return a compact timestamp string for log lines."""
    return time.strftime("%H:%M:%S")


# ══════════════════════════════════════════════════════════════════════════
# NetworkBob
# ══════════════════════════════════════════════════════════════════════════

class NetworkBob:
    """
    Bob — the CLIENT node in a networked BB84 QKD exchange.

    Bob creates a TCP socket, connects to Alice's server, and participates
    in the 5-phase BB84 protocol over the real network.

    Attributes
    ----------
    host       : str   IP address of Alice's server.
    port       : int   TCP port Alice is listening on (default 9999).
    sock       : socket.socket  Active TCP connection to Alice.
    final_key  : list[int]      The final privacy-amplified key.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9999):
        self.host      = host
        self.port      = port
        self.sock: Optional[socket.socket] = None
        self.final_key: List[int] = []
        self.session_qber: float  = 0.0

    # ── Public entry point ─────────────────────────────────────────────────
    def connect_to_alice(self) -> None:
        """
        Create a TCP socket, connect to Alice, and run the BB84 protocol.

        Handles connection errors and cleans up the socket on exit.
        """
        print(f"\n{CYAN}Bob connecting to Alice at {self.host}:{self.port}...{RESET}")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(60)   # 60-second timeout per receive

        try:
            self.sock.connect((self.host, self.port))
        except (ConnectionRefusedError, OSError) as exc:
            print(f"{RED}Cannot connect to Alice at {self.host}:{self.port}: {exc}{RESET}")
            print("  Is Alice's server running?  python network_alice.py")
            sys.exit(1)

        print(f"{GREEN}[{_ts()}] Connected! Starting QKD protocol...{RESET}\n")

        try:
            self.run_qkd_protocol()
        except ConnectionError as exc:
            print(f"{RED}[{_ts()}] Network error: {exc}{RESET}")
        except Exception as exc:
            print(f"{RED}[{_ts()}] Unexpected error: {exc}{RESET}")
            raise
        finally:
            self.sock.close()
            print(f"\n[{_ts()}] Connection closed.")

    # ── Framing wrappers (logged) ──────────────────────────────────────────
    def send_message(self, msg: Dict[str, Any]) -> None:
        """Serialize *msg* as length-prefixed JSON and send."""
        nbytes = _send_message(self.sock, msg)
        print(f"  [{_ts()}] → SENT  {msg.get('type','?'):30s}  ({nbytes:,} bytes)")

    def receive_message(self) -> Dict[str, Any]:
        """Receive a length-prefixed JSON message and return the dict."""
        msg = _recv_message(self.sock)
        body_bytes = len(json.dumps(msg).encode())
        print(f"  [{_ts()}] ← RECV  {msg.get('type','?'):30s}  ({body_bytes:,} bytes)")
        return msg

    # ── 5-Phase BB84 Protocol ─────────────────────────────────────────────
    def run_qkd_protocol(self) -> None:
        """
        Participate in all 5 phases of BB84 as the CLIENT.

        Phase 1 — Receive quantum photon states from Alice
        Phase 2 — Exchange bases with Alice
        Phase 3 — Confirm sifting count
        Phase 4 — Send QBER sample; receive security decision
        Phase 5 — Verify key hash
        """
        _banner("STARTING BB84 PROTOCOL")

        # ──────────────────────────────────────────────────────────────────
        # PHASE 1 — Receive Quantum States
        # ──────────────────────────────────────────────────────────────────
        _phase_header(1, "QUANTUM TRANSMISSION  (Alice → Bob)")

        qt_msg        = self.receive_message()
        photon_states = qt_msg["photon_states"]
        num_qubits    = qt_msg["num_qubits"]

        print(f"\n  [RX] Received {len(photon_states)} photon states from Alice")
        print(f"  Sample photon states (first 20): "
              f"{photon_states[:20]}{'...' if num_qubits > 20 else ''}")

        # Bob measures all photons using his randomly chosen bases
        bob = Bob(num_qubits)
        bob.generate_bases()
        bob.measure_photons(photon_states)

        print(f"\n  [BOB] Measured {num_qubits} photons with random bases")
        print(f"  Sample measurements (first 20): "
              f"{bob.measurements[:20]}{'...' if num_qubits > 20 else ''}")

        # ──────────────────────────────────────────────────────────────────
        # PHASE 2 — Basis Exchange
        # ──────────────────────────────────────────────────────────────────
        _phase_header(2, "BASIS EXCHANGE  (Alice ↔ Bob)")

        # Send Bob's bases to Alice
        self.send_message({
            "type":      "BOB_BASES",
            "bob_bases": bob.bases,
            "timestamp": _ts(),
        })

        # Receive Alice's bases
        alice_bases_msg = self.receive_message()
        alice_bases     = alice_bases_msg["alice_bases"]

        print(f"\n  [CC] Basis exchange complete")
        print(f"  Alice bases (first 20): {alice_bases[:20]}...")
        print(f"  Bob   bases (first 20): {bob.bases[:20]}...")

        # ──────────────────────────────────────────────────────────────────
        # PHASE 3 — Sifting
        # ──────────────────────────────────────────────────────────────────
        _phase_header(3, "SIFTING  (Classical reconciliation)")

        matching_indices = [
            i for i in range(num_qubits)
            if alice_bases[i] == bob.bases[i]
        ]
        bob_sifted  = [bob.measurements[i] for i in matching_indices]
        sifted_len  = len(matching_indices)
        match_pct   = sifted_len / num_qubits * 100

        # Receive Alice's sifting confirmation
        confirm_msg    = self.receive_message()
        alice_count    = confirm_msg.get("matching_count", -1)

        counts_agree = (alice_count == sifted_len)
        status_icon  = "✓" if counts_agree else "✗ MISMATCH"

        print(f"\n  Matching indices : {sifted_len}/{num_qubits} "
              f"qubits retained ({match_pct:.1f}%)")
        print(f"  Alice reports    : {alice_count} matching  [{status_icon}]")
        print(f"  Bob sifted key (first 20): "
              f"{bob_sifted[:20]}{'...' if sifted_len > 20 else ''}")

        if sifted_len == 0:
            print(f"{RED}  No matching bases — cannot continue.{RESET}")
            return

        # ──────────────────────────────────────────────────────────────────
        # PHASE 4 — QBER Check
        # ──────────────────────────────────────────────────────────────────
        _phase_header(4, "QBER CHECK  (Alice ↔ Bob)")

        # Receive Alice's sample request (she chose the indices)
        sample_req     = self.receive_message()
        sample_indices = sample_req["sample_indices"]
        alice_sample   = sample_req["alice_sample"]

        # Bob sends back his bits at those positions
        bob_sample = [bob_sifted[i] for i in sample_indices]

        self.send_message({
            "type":       "BOB_SAMPLE",
            "bob_sample": bob_sample,
            "timestamp":  _ts(),
        })

        # Receive Alice's QBER decision
        decision_msg = self.receive_message()

        # Check for abort signal
        if decision_msg.get("type") == "ABORT":
            print(f"\n{RED}  ❌ Session aborted by Alice: "
                  f"{decision_msg.get('reason', 'no reason given')}{RESET}")
            return

        qber     = decision_msg["qber"]
        decision = decision_msg["decision"]
        self.session_qber = qber

        secure = decision == "PROCEED"
        colour = GREEN if secure else RED
        print(f"\n  [QBER] Measured QBER = {colour}{qber:.2%}{RESET}")
        print(f"  [QBER] Decision      = {BOLD}{colour}{decision}{RESET}")

        if not secure:
            print(f"\n{RED}{BOLD}  ❌ SESSION ABORTED — EAVESDROPPER DETECTED{RESET}")
            return

        print(f"\n  {GREEN}✓ Channel declared SECURE — proceeding to key generation{RESET}")

        # ──────────────────────────────────────────────────────────────────
        # PHASE 5 — Key Hash Verification
        # ──────────────────────────────────────────────────────────────────
        _phase_header(5, "KEY HASH VERIFICATION  (Alice → Bob)")

        # Bob independently applies privacy amplification to his sifted key
        # (must use identical logic to Alice — removes the same sample bits)
        bob_sifted_remaining = list(bob_sifted)
        for i in sorted(sample_indices, reverse=True):
            bob_sifted_remaining.pop(i)

        # Local privacy amplification (mirrors Alice's calculation)
        from qber import privacy_amplification
        bob_final_key  = privacy_amplification(bob_sifted_remaining, qber)
        self.final_key = bob_final_key
        bob_key_str    = "".join(map(str, bob_final_key))

        # Receive Alice's key hash
        hash_msg    = self.receive_message()
        alice_hash  = hash_msg["key_hash"]
        alice_len   = hash_msg["key_length"]

        # Compute Bob's hash of his own key
        bob_hash = hashlib.sha256(bob_key_str.encode()).hexdigest()

        keys_match = (alice_hash == bob_hash)
        self.send_message({
            "type":      "KEY_HASH_ACK",
            "verified":  keys_match,
            "timestamp": _ts(),
        })

        print(f"\n  Alice's key hash : {alice_hash[:32]}...")
        print(f"  Bob's   key hash : {bob_hash[:32]}...")

        # ── Final report ──────────────────────────────────────────────────
        _banner("SESSION COMPLETE — BOB")
        if keys_match:
            print(f"{GREEN}{BOLD}  ✅ SECURE QUANTUM KEY ESTABLISHED{RESET}")
            print(f"  {GREEN}Keys verified — hashes match perfectly{RESET}")
        else:
            print(f"{RED}{BOLD}  ❌ KEY MISMATCH — hashes do not agree{RESET}")
            print(f"  Possible causes: protocol bug or active tampering")

        print(f"\n  QBER              : {qber:.2%}")
        print(f"  Sifted key length : {sifted_len} bits")
        print(f"  Final key length  : {len(bob_final_key)} bits")
        key_preview = bob_key_str[:64] + ("..." if len(bob_key_str) > 64 else "")
        print(f"  Final key         : {YELLOW}{key_preview}{RESET}\n")


# ══════════════════════════════════════════════════════════════════════════
# Pretty-print helpers (mirrors network_alice.py)
# ══════════════════════════════════════════════════════════════════════════

def _banner(title: str) -> None:
    w = 60
    print(f"\n{BOLD}{'═' * w}")
    print(f"  {title}")
    print(f"{'═' * w}{RESET}\n")


def _phase_header(num: int, title: str) -> None:
    print(f"\n{CYAN}{BOLD}── PHASE {num}: {title} ──{RESET}")


# ══════════════════════════════════════════════════════════════════════════
# Standalone entry point
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{BOLD}{CYAN}")
    print("  ╔══════════════════════════════════════╗")
    print("  ║      BOB — QKD CLIENT NODE           ║")
    print("  ║   BB84 Quantum Key Distribution      ║")
    print(f"  ╚══════════════════════════════════════╝{RESET}")

    import argparse
    parser = argparse.ArgumentParser(description="Bob — BB84 QKD Client")
    parser.add_argument("host", nargs="?", default="127.0.0.1",
                        help="Alice's IP address (default: 127.0.0.1)")
    parser.add_argument("--port",   type=int, default=9999,
                        help="Alice's TCP port (default: 9999)")
    args = parser.parse_args()

    print(f"\n  Connecting to Alice at: {args.host}:{args.port}")
    bob_node = NetworkBob(host=args.host, port=args.port)
    bob_node.connect_to_alice()
