"""
network_alice.py — Alice as a Real TCP/IP Network Server
=========================================================

Alice is the SERVER node in the BB84 QKD protocol.
She listens on a TCP port, waits for Bob to connect, then runs the
full 5-phase BB84 handshake over a real network socket.

Protocol Phases
---------------
  Phase 1  QUANTUM_TRANSMISSION   Alice → Bob   photon states
  Phase 2  BASIS_EXCHANGE         Alice ↔ Bob   compare bases
  Phase 3  SIFTING_CONFIRM        Alice → Bob   confirm matching indices
  Phase 4  QBER_CHECK             Alice ↔ Bob   sample bits + decision
  Phase 5  KEY_HASH               Alice → Bob   SHA-256 of final key

Run
---
  python network_alice.py

Dependencies: alice.py, qber.py (existing project files)
"""

import hashlib
import json
import socket
import struct
import sys
import time
import random
from typing import Any, Dict, List, Optional, Tuple

from alice import Alice
from qber  import detect_eavesdropper, privacy_amplification


# ── ANSI colour helpers ────────────────────────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

QBER_THRESHOLD = 0.11   # BB84 standard security threshold (11 %)


# ══════════════════════════════════════════════════════════════════════════
# Framing helpers (shared logic — identical in network_bob.py)
# ══════════════════════════════════════════════════════════════════════════

def _send_message(sock: socket.socket, payload: Dict[str, Any]) -> int:
    """
    Send a length-prefixed JSON message over *sock*.

    Wire format:
        [4 bytes big-endian uint32 = length of body]
        [<length> bytes of UTF-8 JSON]

    Returns the total bytes sent (header + body).
    """
    body   = json.dumps(payload).encode("utf-8")
    header = struct.pack(">I", len(body))      # 4-byte big-endian length
    sock.sendall(header + body)
    return len(header) + len(body)


def _recv_message(sock: socket.socket) -> Dict[str, Any]:
    """
    Receive a length-prefixed JSON message from *sock*.

    Reads the 4-byte header first to learn the body size, then reads
    exactly that many bytes, handles fragmented TCP delivery correctly.

    Returns the deserialized dict.
    Raises ConnectionError on unexpected close or malformed data.
    """
    # ── Read the 4-byte length header ──────────────────────────────────────
    raw_len = _recv_exact(sock, 4)
    body_len = struct.unpack(">I", raw_len)[0]

    # ── Read the body ───────────────────────────────────────────────────────
    raw_body = _recv_exact(sock, body_len)
    return json.loads(raw_body.decode("utf-8"))


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """
    Read exactly *n* bytes from *sock*, handling TCP fragmentation.

    TCP is a stream protocol — a single send() may arrive in multiple
    recv() calls.  This helper keeps reading until all *n* bytes arrive.

    Raises ConnectionError if the connection closes prematurely.
    """
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
# NetworkAlice
# ══════════════════════════════════════════════════════════════════════════

class NetworkAlice:
    """
    Alice — the SERVER node in a networked BB84 QKD exchange.

    Alice binds a TCP socket, accepts one connection from Bob, and then
    runs the 5-phase BB84 protocol over the real network.

    Attributes
    ----------
    host       : str   Bind address ('0.0.0.0' = any interface).
    port       : int   TCP port to listen on (default 9999).
    num_qubits : int   Number of photons to prepare per session.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9999,
        num_qubits: int = 256,
    ):
        self.host       = host
        self.port       = port
        self.num_qubits = num_qubits

        # Results stored after the protocol completes
        self.final_key:   List[int] = []
        self.session_qber: float    = 0.0

    # ── Public entry point ─────────────────────────────────────────────────
    def start_server(self) -> None:
        """
        Bind the TCP socket, accept Bob's connection, and run BB84.

        Handles a single session (point-to-point QKD).  For a persistent
        server that handles multiple sessions, wrap in a loop.
        """
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # SO_REUSEADDR avoids "address already in use" on quick restarts
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(1)

        print(f"\n{CYAN}{BOLD}Alice (Server) listening on port {self.port}...{RESET}")
        print(f"{CYAN}Waiting for Bob to connect...{RESET}\n")

        try:
            conn, bob_addr = server_sock.accept()
            conn.settimeout(60)   # 60-second timeout per receive
        except KeyboardInterrupt:
            print("\nAlice: Server stopped by user.")
            server_sock.close()
            return

        print(f"{GREEN}[{_ts()}] Bob connected from {bob_addr[0]}:{bob_addr[1]}{RESET}\n")

        try:
            self.run_qkd_protocol(conn)
        except ConnectionError as exc:
            print(f"{RED}[{_ts()}] Network error: {exc}{RESET}")
        except Exception as exc:
            print(f"{RED}[{_ts()}] Unexpected error: {exc}{RESET}")
            raise
        finally:
            conn.close()
            server_sock.close()
            print(f"\n[{_ts()}] Connection closed.")

    # ── Framing wrappers (logged) ──────────────────────────────────────────
    def send_message(self, conn: socket.socket, msg: Dict[str, Any]) -> None:
        """Serialize *msg* as length-prefixed JSON and send over *conn*."""
        nbytes = _send_message(conn, msg)
        print(f"  [{_ts()}] → SENT  {msg.get('type','?'):30s}  ({nbytes:,} bytes)")

    def receive_message(self, conn: socket.socket) -> Dict[str, Any]:
        """Receive a length-prefixed JSON message from *conn* and return it."""
        msg = _recv_message(conn)
        body_bytes = len(json.dumps(msg).encode())
        print(f"  [{_ts()}] ← RECV  {msg.get('type','?'):30s}  ({body_bytes:,} bytes)")
        return msg

    # ── 5-Phase BB84 Protocol ─────────────────────────────────────────────
    def run_qkd_protocol(self, conn: socket.socket) -> None:
        """
        Execute all 5 phases of BB84 over the real TCP connection.

        Phase 1 — Quantum Transmission   (Alice → Bob)
        Phase 2 — Basis Exchange         (Alice ↔ Bob)
        Phase 3 — Sifting Confirmation   (Alice → Bob)
        Phase 4 — QBER Check             (Alice ↔ Bob)
        Phase 5 — Key Hash Verification  (Alice → Bob)
        """
        _banner("STARTING BB84 PROTOCOL")

        # ──────────────────────────────────────────────────────────────────
        # PHASE 1 — Quantum Transmission
        # ──────────────────────────────────────────────────────────────────
        _phase_header(1, "QUANTUM TRANSMISSION  (Alice → Bob)")

        alice = Alice(self.num_qubits)
        alice.generate_bits()
        alice.generate_bases()
        alice.encode_photons()

        t_start = time.perf_counter()
        self.send_message(conn, {
            "type":          "QUANTUM_TRANSMISSION",
            "photon_states": alice.photon_states,
            "num_qubits":    self.num_qubits,
            "timestamp":     _ts(),
        })
        elapsed = (time.perf_counter() - t_start) * 1000
        print(f"\n  [TX] Sent {self.num_qubits} photon states to Bob  "
              f"({elapsed:.1f} ms network latency)")

        # ──────────────────────────────────────────────────────────────────
        # PHASE 2 — Basis Exchange
        # ──────────────────────────────────────────────────────────────────
        _phase_header(2, "BASIS EXCHANGE  (Alice ↔ Bob)")

        # Receive Bob's bases first
        bob_bases_msg = self.receive_message(conn)
        bob_bases      = bob_bases_msg["bob_bases"]

        # Send Alice's bases back
        self.send_message(conn, {
            "type":        "ALICE_BASES",
            "alice_bases": alice.bases,
            "timestamp":   _ts(),
        })
        print(f"\n  [CC] Basis exchange complete")

        # ──────────────────────────────────────────────────────────────────
        # PHASE 3 — Sifting (independent local calculation)
        # ──────────────────────────────────────────────────────────────────
        _phase_header(3, "SIFTING  (Classical reconciliation)")

        matching_indices = [
            i for i in range(self.num_qubits)
            if alice.bases[i] == bob_bases[i]
        ]
        alice_sifted = [alice.bits[i] for i in matching_indices]
        sifted_len   = len(matching_indices)
        match_pct    = sifted_len / self.num_qubits * 100

        print(f"\n  Matching indices : {sifted_len}/{self.num_qubits} "
              f"qubits retained ({match_pct:.1f}%)")
        print(f"  Sifted key (first 20 bits): "
              f"{alice_sifted[:20]}{'...' if sifted_len > 20 else ''}")

        # Confirm sifting to Bob so he can verify he computed the same count
        self.send_message(conn, {
            "type":               "SIFTING_CONFIRM",
            "matching_count":     sifted_len,
            "timestamp":          _ts(),
        })

        if sifted_len == 0:
            self._abort(conn, "No basis matches — cannot establish a key.")
            return

        # ──────────────────────────────────────────────────────────────────
        # PHASE 4 — QBER Check
        # ──────────────────────────────────────────────────────────────────
        _phase_header(4, "QBER CHECK  (Alice ↔ Bob)")

        # Alice decides which positions to sample and tells Bob
        sample_size    = min(50, sifted_len // 4)
        sample_indices = sorted(random.sample(range(sifted_len), sample_size)) \
                         if sample_size > 0 else []
        alice_sample   = [alice_sifted[i] for i in sample_indices]

        self.send_message(conn, {
            "type":           "QBER_SAMPLE_REQUEST",
            "sample_indices": sample_indices,
            "alice_sample":   alice_sample,
            "timestamp":      _ts(),
        })

        # Receive Bob's sample bits
        bob_sample_msg = self.receive_message(conn)
        bob_sample     = bob_sample_msg["bob_sample"]

        # Calculate QBER
        if sample_size > 0:
            mismatches = sum(a != b for a, b in zip(alice_sample, bob_sample))
            qber       = mismatches / sample_size
        else:
            qber, mismatches = 0.0, 0

        self.session_qber = qber
        eve_detected, decision = detect_eavesdropper(qber)

        _qber_box(qber, sample_size, mismatches, decision)

        # Send decision to Bob
        self.send_message(conn, {
            "type":      "QBER_DECISION",
            "qber":      qber,
            "decision":  decision,
            "timestamp": _ts(),
        })

        if eve_detected:
            print(f"\n{RED}  ❌ EAVESDROPPER DETECTED — SESSION ABORTED{RESET}")
            return

        # ──────────────────────────────────────────────────────────────────
        # PHASE 5 — Key Finalisation & Hash Verification
        # ──────────────────────────────────────────────────────────────────
        _phase_header(5, "KEY HASH VERIFICATION  (Alice → Bob)")

        # Remove sampled bits from sifted key (they are now public)
        for i in sorted(sample_indices, reverse=True):
            alice_sifted.pop(i)

        # Privacy amplification
        final_key      = privacy_amplification(alice_sifted, qber)
        self.final_key = final_key
        key_str        = "".join(map(str, final_key))

        # Hash the key — send the hash, NEVER the key itself
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()

        self.send_message(conn, {
            "type":      "KEY_HASH",
            "key_hash":  key_hash,
            "key_length": len(final_key),
            "timestamp": _ts(),
        })
        print(f"\n  [HASH] SHA-256 of key sent to Bob (key itself NOT transmitted)")
        print(f"  [HASH] {key_hash[:32]}...")

        # Wait for Bob's verification acknowledgement
        ack = self.receive_message(conn)
        bob_verified = ack.get("verified", False)

        # ── Final report ──────────────────────────────────────────────────
        _banner("SESSION COMPLETE — ALICE")
        if bob_verified:
            print(f"{GREEN}{BOLD}  ✅ SECURE QUANTUM KEY ESTABLISHED{RESET}")
        else:
            print(f"{RED}{BOLD}  ❌ KEY MISMATCH — Bob could not verify{RESET}")

        print(f"\n  QBER              : {qber:.2%}")
        print(f"  Sifted key length : {sifted_len} bits")
        print(f"  Final key length  : {len(final_key)} bits")
        key_preview = key_str[:64] + ("..." if len(key_str) > 64 else "")
        print(f"  Final key         : {YELLOW}{key_preview}{RESET}\n")

    # ── Internal helpers ───────────────────────────────────────────────────
    def _abort(self, conn: socket.socket, reason: str) -> None:
        """Send an ABORT signal to Bob and print the reason."""
        print(f"\n{RED}  ABORTING: {reason}{RESET}")
        try:
            self.send_message(conn, {
                "type":    "ABORT",
                "reason":  reason,
                "timestamp": _ts(),
            })
        except Exception:
            pass   # Best-effort; connection may already be broken


# ══════════════════════════════════════════════════════════════════════════
# Pretty-print helpers
# ══════════════════════════════════════════════════════════════════════════

def _banner(title: str) -> None:
    w = 60
    print(f"\n{BOLD}{'═' * w}")
    print(f"  {title}")
    print(f"{'═' * w}{RESET}\n")


def _phase_header(num: int, title: str) -> None:
    print(f"\n{CYAN}{BOLD}── PHASE {num}: {title} ──{RESET}")


def _qber_box(qber: float, sample: int, mismatches: int, decision: str) -> None:
    secure = decision == "PROCEED"
    colour = GREEN if secure else RED
    icon   = "✅ CHANNEL SECURE" if secure else "⚠️  EAVESDROPPER DETECTED"
    w = 46
    print(f"\n  {'╔' + '═' * w + '╗'}")
    print(f"  ║ {'QBER ANALYSIS REPORT':^{w - 2}} ║")
    print(f"  {'╠' + '═' * w + '╣'}")
    print(f"  ║  Quantum Bit Error Rate : {qber * 100:6.2f}%{' ' * (w - 34)}║")
    print(f"  ║  Security Threshold     : 11.00%{' ' * (w - 34)}║")
    print(f"  ║  Sample size            : {sample} bits ({mismatches} errors){' ' * max(0, w - 34 - len(str(sample)) - len(str(mismatches)))}║")
    print(f"  ║  Status : {colour}{icon}{RESET}{' ' * max(0, w - 10 - len(icon))}║")
    print(f"  ║  Decision : {BOLD}{decision}{RESET}{' ' * max(0, w - 12 - len(decision))}║")
    print(f"  {'╚' + '═' * w + '╝'}")


# ══════════════════════════════════════════════════════════════════════════
# Standalone entry point
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{BOLD}{CYAN}")
    print("  ╔══════════════════════════════════════╗")
    print("  ║      ALICE — QKD SERVER NODE         ║")
    print("  ║   BB84 Quantum Key Distribution      ║")
    print(f"  ╚══════════════════════════════════════╝{RESET}")

    import argparse
    parser = argparse.ArgumentParser(description="Alice — BB84 QKD Server")
    parser.add_argument("--port",    type=int, default=9999,  help="TCP port (default: 9999)")
    parser.add_argument("--qubits",  type=int, default=256,   help="Number of qubits (default: 256)")
    parser.add_argument("--host",    type=str, default="0.0.0.0", help="Bind address")
    args = parser.parse_args()

    alice_node = NetworkAlice(host=args.host, port=args.port, num_qubits=args.qubits)
    alice_node.start_server()
