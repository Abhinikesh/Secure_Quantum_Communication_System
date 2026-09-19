"""
network_eve.py — Eve as a Real Man-in-the-Middle Network Proxy
==============================================================

Eve sits BETWEEN Alice and Bob on the network, acting as a transparent
TCP proxy that intercepts and optionally tampers with quantum states.

Network topology with Eve
--------------------------

  NORMAL (no Eve):
    Alice (port 9999)  ←TCP→  Bob

  WITH EVE (man-in-the-middle):
    Alice (port 9999)  ←TCP→  Eve proxy (port 9998)  ←TCP→  Bob

Setup (three terminals):
  Terminal 1:  python network_alice.py --port 9999
  Terminal 2:  python network_eve.py   (proxies 9998 → 9999)
  Terminal 3:  python network_bob.py   --port 9998   # Bob connects to Eve

How the attack works
--------------------
1. Bob connects to Eve's port (9998) thinking it's Alice.
2. Eve connects to the real Alice (port 9999) pretending to be Bob.
3. Eve forwards ALL messages transparently — Alice and Bob see normal traffic.
4. BUT: when a QUANTUM_TRANSMISSION message arrives, Eve modifies the
   photon_states according to her intercept-and-resend strategy.
5. This introduces errors (~25% QBER) that Alice and Bob can detect.

Eve's interception rate is configurable (0.0 to 1.0).
  0.0 = passive / no tampering  → QBER ~0%   (undetected)
  0.5 = intercepts 50% of qubits → QBER ~12% (borderline detection)
  1.0 = full intercept-and-resend → QBER ~25% (always detected)

Run
---
  python network_eve.py                    # default: intercept 100%
  python network_eve.py --intercept 0.5   # intercept 50%
  python network_eve.py --intercept 0.0   # passive (invisible)
  python network_eve.py --alice-host 192.168.1.10  # Alice on another machine

Dependencies: eve.py (existing project file)
"""

import json
import socket
import struct
import sys
import threading
import time
import argparse
import random
from typing import Any, Dict, Optional

from eve import Eve


# ── ANSI colour helpers ────────────────────────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
MAGENTA = "\033[95m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ══════════════════════════════════════════════════════════════════════════
# Wire-format helpers (identical to alice/bob — MUST stay in sync)
# ══════════════════════════════════════════════════════════════════════════

def _send_message(sock: socket.socket, payload: Dict[str, Any]) -> int:
    body   = json.dumps(payload).encode("utf-8")
    header = struct.pack(">I", len(body))
    sock.sendall(header + body)
    return len(header) + len(body)


def _recv_message(sock: socket.socket) -> Dict[str, Any]:
    raw_len  = _recv_exact(sock, 4)
    body_len = struct.unpack(">I", raw_len)[0]
    raw_body = _recv_exact(sock, body_len)
    return json.loads(raw_body.decode("utf-8"))


def _recv_exact(sock: socket.socket, n: int) -> bytes:
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
    return time.strftime("%H:%M:%S")


# ══════════════════════════════════════════════════════════════════════════
# NetworkEve — man-in-the-middle proxy
# ══════════════════════════════════════════════════════════════════════════

class NetworkEve:
    """
    Eve — Man-in-the-Middle proxy between Alice and Bob.

    Listens on *listen_port* (impersonating Alice to Bob).
    Connects to *alice_host:alice_port* (impersonating Bob to Alice).
    Forwards all messages in both directions, but intercepts and
    optionally modifies QUANTUM_TRANSMISSION payloads.

    Attributes
    ----------
    listen_host      : str   Address Eve binds (Bob connects here).
    listen_port      : int   Port Eve listens on (default 9998).
    alice_host       : str   Real Alice's IP address.
    alice_port       : int   Real Alice's port (default 9999).
    intercept_prob   : float Fraction of photons Eve intercepts (0.0–1.0).
    """

    def __init__(
        self,
        listen_host:    str   = "0.0.0.0",
        listen_port:    int   = 9998,
        alice_host:     str   = "127.0.0.1",
        alice_port:     int   = 9999,
        intercept_prob: float = 1.0,
    ):
        self.listen_host    = listen_host
        self.listen_port    = listen_port
        self.alice_host     = alice_host
        self.alice_port     = alice_port
        self.intercept_prob = max(0.0, min(1.0, intercept_prob))
        self._eve_engine    = Eve(intercept_probability=self.intercept_prob)

        # Statistics
        self._photons_seen        = 0
        self._photons_intercepted = 0
        self._messages_forwarded  = 0

    # ── Public entry point ─────────────────────────────────────────────────
    def start(self) -> None:
        """
        Bind Eve's fake-Alice port, wait for Bob, then open a connection
        to the real Alice and bridge the two sides.
        """
        listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_sock.bind((self.listen_host, self.listen_port))
        listen_sock.listen(1)

        _eve_banner(self.intercept_prob)
        print(f"{MAGENTA}[Eve] Listening for Bob  on port {self.listen_port}...{RESET}")
        print(f"{MAGENTA}[Eve] Will forward to Alice at "
              f"{self.alice_host}:{self.alice_port}{RESET}\n")

        try:
            bob_conn, bob_addr = listen_sock.accept()
            bob_conn.settimeout(60)
        except KeyboardInterrupt:
            print("\n[Eve] Stopped by user.")
            listen_sock.close()
            return

        print(f"{GREEN}[{_ts()}] Bob connected to Eve from "
              f"{bob_addr[0]}:{bob_addr[1]}{RESET}")

        # Now connect to the REAL Alice
        print(f"{MAGENTA}[{_ts()}] Eve connecting to real Alice "
              f"({self.alice_host}:{self.alice_port})...{RESET}")
        alice_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        alice_sock.settimeout(60)
        try:
            alice_sock.connect((self.alice_host, self.alice_port))
        except (ConnectionRefusedError, OSError) as exc:
            print(f"{RED}[Eve] Cannot reach Alice: {exc}{RESET}")
            bob_conn.close()
            listen_sock.close()
            return

        print(f"{GREEN}[{_ts()}] Eve connected to Alice — MITM bridge active{RESET}\n")

        try:
            self._run_mitm_bridge(alice_sock, bob_conn)
        except ConnectionError as exc:
            print(f"{RED}[Eve] Connection error: {exc}{RESET}")
        finally:
            alice_sock.close()
            bob_conn.close()
            listen_sock.close()
            self._print_stats()

    # ── Main MITM bridge ───────────────────────────────────────────────────
    def _run_mitm_bridge(
        self, alice_sock: socket.socket, bob_conn: socket.socket
    ) -> None:
        """
        Relay messages between Alice and Bob, intercepting quantum data.

        Message flow:
          Alice → Eve → (possibly modify) → Bob
          Bob   → Eve → (pass through)    → Alice

        Eve only tampers with QUANTUM_TRANSMISSION messages.
        All other message types are forwarded verbatim.
        """
        # Track which direction we're bridging
        # The protocol alternates: Alice sends first (QUANTUM_TRANSMISSION),
        # then Bob replies (BOB_BASES), etc.
        # We model this as a relay loop that peeks at message type.

        # ── Relay loop ──────────────────────────────────────────────────────
        # We drive the relay phase-by-phase, matching the BB84 protocol
        # sequence so we know which socket to read next.

        print(f"{MAGENTA}{'─'*60}")
        print(f"  Eve's MITM Bridge Active — Relaying BB84 protocol")
        print(f"{'─'*60}{RESET}\n")

        # Phase 1: Alice → Bob (QUANTUM_TRANSMISSION)
        msg = self._relay_from_alice(alice_sock, bob_conn, tamper=True)
        if msg is None:
            return

        # Phase 2a: Bob → Alice (BOB_BASES)
        if not self._relay_from_bob(bob_conn, alice_sock):
            return
        # Phase 2b: Alice → Bob (ALICE_BASES)
        if not self._relay_from_alice(alice_sock, bob_conn):
            return

        # Phase 3: Alice → Bob (SIFTING_CONFIRM)
        if not self._relay_from_alice(alice_sock, bob_conn):
            return

        # Phase 4a: Alice → Bob (QBER_SAMPLE_REQUEST)
        if not self._relay_from_alice(alice_sock, bob_conn):
            return
        # Phase 4b: Bob → Alice (BOB_SAMPLE)
        if not self._relay_from_bob(bob_conn, alice_sock):
            return
        # Phase 4c: Alice → Bob (QBER_DECISION)
        if not self._relay_from_alice(alice_sock, bob_conn):
            return

        # Phase 5a: Alice → Bob (KEY_HASH)
        if not self._relay_from_alice(alice_sock, bob_conn):
            return
        # Phase 5b: Bob → Alice (KEY_HASH_ACK)
        if not self._relay_from_bob(bob_conn, alice_sock):
            return

        print(f"\n{MAGENTA}[Eve] Protocol relay complete.{RESET}")

    # ── Relay helpers ──────────────────────────────────────────────────────
    def _relay_from_alice(
        self,
        alice_sock: socket.socket,
        bob_conn:   socket.socket,
        tamper:     bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Read one message from Alice, optionally tamper, forward to Bob.

        Returns the (possibly modified) message dict, or None on error.
        """
        try:
            msg = _recv_message(alice_sock)
        except ConnectionError as exc:
            print(f"{RED}[Eve] Alice disconnected: {exc}{RESET}")
            return None

        msg_type = msg.get("type", "?")
        print(f"  [{_ts()}] Alice→Eve  {msg_type:30s}", end="")

        # ── Quantum interception ──────────────────────────────────────────
        if tamper and msg_type == "QUANTUM_TRANSMISSION":
            original_states = msg["photon_states"]
            modified_states = self._eve_engine.intercept(original_states)
            msg["photon_states"] = modified_states

            self._photons_seen        += len(original_states)
            self._photons_intercepted += len(self._eve_engine.intercepted_indices)

            pct_intercepted = (len(self._eve_engine.intercepted_indices) /
                               len(original_states) * 100)
            print(f"  {YELLOW}[INTERCEPTED {pct_intercepted:.0f}%]{RESET}")
            self._log_interception(original_states, modified_states)
        else:
            print()

        # Forward (possibly modified) message to Bob
        try:
            nbytes = _send_message(bob_conn, msg)
        except ConnectionError as exc:
            print(f"{RED}[Eve] Cannot forward to Bob: {exc}{RESET}")
            return None

        self._messages_forwarded += 1
        print(f"  [{_ts()}] Eve→Bob   {msg_type:30s}  ({nbytes:,} bytes)")
        return msg

    def _relay_from_bob(
        self,
        bob_conn:   socket.socket,
        alice_sock: socket.socket,
    ) -> bool:
        """
        Read one message from Bob and forward it verbatim to Alice.

        Returns True on success, False on connection error.
        """
        try:
            msg = _recv_message(bob_conn)
        except ConnectionError as exc:
            print(f"{RED}[Eve] Bob disconnected: {exc}{RESET}")
            return False

        msg_type = msg.get("type", "?")
        print(f"  [{_ts()}] Bob→Eve   {msg_type:30s}")

        try:
            nbytes = _send_message(alice_sock, msg)
        except ConnectionError as exc:
            print(f"{RED}[Eve] Cannot forward to Alice: {exc}{RESET}")
            return False

        self._messages_forwarded += 1
        print(f"  [{_ts()}] Eve→Alice {msg_type:30s}  ({nbytes:,} bytes)")
        return True

    # ── Interception logging ───────────────────────────────────────────────
    def _log_interception(
        self,
        original: list,
        modified: list,
    ) -> None:
        """Print a compact summary of what Eve changed in the photon stream."""
        diff_count = sum(o != m for o, m in zip(original, modified))
        stats = self._eve_engine.get_statistics()
        correct_pct = stats["basis_accuracy"]

        print(f"\n  {MAGENTA}┌── Eve's Intercept-and-Resend Attack ──────────────────┐")
        print(f"  │  Total photons seen         : {len(original):<6}                 │")
        print(f"  │  Photons intercepted        : "
              f"{stats['intercepted_count']:<6} ({stats['interception_rate']:.0f}%)          │")
        print(f"  │  Correct basis guesses      : "
              f"{stats['correct_basis_guesses']:<6} ({correct_pct:.0f}% accuracy)      │")
        print(f"  │  Photon states modified     : {diff_count:<6}                 │")
        print(f"  │  Expected QBER introduced   : ~{self.intercept_prob * 0.25 * 100:.1f}%               │")
        print(f"  └────────────────────────────────────────────────────────┘{RESET}\n")

    # ── Statistics ─────────────────────────────────────────────────────────
    def _print_stats(self) -> None:
        """Print Eve's end-of-session statistics."""
        print(f"\n{MAGENTA}{BOLD}{'═'*60}")
        print(f"  Eve's Session Statistics")
        print(f"{'═'*60}{RESET}")
        print(f"  Photons seen          : {self._photons_seen}")
        print(f"  Photons intercepted   : {self._photons_intercepted}")
        if self._photons_seen > 0:
            pct = self._photons_intercepted / self._photons_seen * 100
            print(f"  Interception rate     : {pct:.1f}%")
        print(f"  Messages forwarded    : {self._messages_forwarded}")
        print(f"  Target QBER introduced: ~{self.intercept_prob * 25:.1f}%")
        print(f"\n  Note: A QBER > 11% will cause Alice to abort the session.")
        if self.intercept_prob >= 0.5:
            print(f"  {RED}Eve's attack was almost certainly detected!{RESET}")
        else:
            print(f"  {GREEN}Eve's partial attack may have gone undetected.{RESET}")
        print()


# ══════════════════════════════════════════════════════════════════════════
# Pretty-print helpers
# ══════════════════════════════════════════════════════════════════════════

def _eve_banner(intercept_prob: float) -> None:
    danger = RED if intercept_prob >= 0.5 else YELLOW
    print(f"\n{MAGENTA}{BOLD}")
    print("  ╔══════════════════════════════════════════════════╗")
    print("  ║       EVE — MAN-IN-THE-MIDDLE PROXY             ║")
    print("  ║       BB84 Quantum Key Distribution Attack      ║")
    print("  ╚══════════════════════════════════════════════════╝")
    print(f"{RESET}")
    print(f"  Intercept probability : "
          f"{danger}{BOLD}{intercept_prob:.0%}{RESET}")
    print(f"  Expected QBER         : "
          f"{danger}~{intercept_prob * 25:.1f}%{RESET}  "
          f"(threshold = 11%)")
    detection = "VERY LIKELY DETECTED" if intercept_prob >= 0.5 else "May go undetected"
    print(f"  Detection likelihood  : {danger}{detection}{RESET}\n")


# ══════════════════════════════════════════════════════════════════════════
# Standalone entry point
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Eve — BB84 MITM Proxy  (listens on :9998, forwards to Alice:9999)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python network_eve.py                        # Full interception (100%)
  python network_eve.py --intercept 0.5        # Intercept 50% of photons
  python network_eve.py --intercept 0.0        # Passive — invisible to Alice/Bob
  python network_eve.py --alice-host 192.168.1.10   # Alice on another machine

Setup (three terminals):
  Terminal 1:  python network_alice.py              (Alice on :9999)
  Terminal 2:  python network_eve.py                (Eve bridges :9998→:9999)
  Terminal 3:  python network_bob.py --port 9998    (Bob connects to Eve)
""",
    )
    parser.add_argument(
        "--listen-port", type=int, default=9998,
        help="Port Eve listens on — Bob connects here (default: 9998)",
    )
    parser.add_argument(
        "--alice-host", type=str, default="127.0.0.1",
        help="Alice's IP address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--alice-port", type=int, default=9999,
        help="Alice's TCP port (default: 9999)",
    )
    parser.add_argument(
        "--intercept", type=float, default=1.0,
        metavar="PROB",
        help="Fraction of photons to intercept, 0.0–1.0 (default: 1.0)",
    )
    args = parser.parse_args()

    if not (0.0 <= args.intercept <= 1.0):
        print(f"{RED}--intercept must be between 0.0 and 1.0{RESET}")
        sys.exit(1)

    eve = NetworkEve(
        listen_port    = args.listen_port,
        alice_host     = args.alice_host,
        alice_port     = args.alice_port,
        intercept_prob = args.intercept,
    )
    eve.start()
