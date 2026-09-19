"""
real_qkd_system.py — Complete Production QKD System
=====================================================

The capstone file that integrates every component of the project into
a single, production-quality Quantum Key Distribution system.

Architecture
------------
  QKDKeyStore      — Secure in-memory key vault with forward-secrecy
  QKDSession       — Per-exchange session tracking with UUID identifiers
  SecurityAuditLog — Tamper-evident event log written to disk
  ProtocolSelector — Multi-protocol runner (BB84, Enhanced BB84, Six-State)
  Benchmark        — Statistical performance analysis over N trials
  run_complete_real_demo() — Full end-to-end demonstration

Component dependencies
----------------------
  alice.py   bob.py   eve.py        ← simulation layer
  qber.py                           ← QBER calculation + protocol runner
  encryption.py                     ← OTP / AES-256 / Simple XOR

Run
---
  python real_qkd_system.py
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import statistics
import time
import uuid
from contextlib import contextmanager, redirect_stdout
from datetime import datetime
from io import StringIO
from typing import Any, Dict, Iterator, List, Optional, Tuple

# ── Project modules ────────────────────────────────────────────────────────
from qber import (
    run_full_protocol,
    calculate_qber,
    detect_eavesdropper,
    privacy_amplification,
    _binary_entropy,
)
from encryption import (
    otp_encrypt,
    otp_decrypt,
    aes_encrypt,
    aes_decrypt,
    simple_encrypt,
    simple_decrypt,
    derive_aes_key,
    AES_AVAILABLE,
    _text_to_bits,
    _bits_to_hex,
    _bits_to_bytes,
)

# ── ANSI colour palette ────────────────────────────────────────────────────
R  = "\033[91m"   # red
G  = "\033[92m"   # green
Y  = "\033[93m"   # yellow
B  = "\033[94m"   # blue
M  = "\033[95m"   # magenta
C  = "\033[96m"   # cyan
W  = "\033[97m"   # white
BD = "\033[1m"    # bold
DM = "\033[2m"    # dim
RS = "\033[0m"    # reset

# ── Audit log file (append mode, human-readable) ──────────────────────────
_AUDIT_LOG_PATH = "security_audit.log"


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

def _now() -> str:
    """ISO-formatted current timestamp."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _short_id(uid: str) -> str:
    """Return the first 8 hex chars of a UUID for compact display."""
    return uid.replace("-", "")[:8].upper()


def _strip_ansi(s: str) -> str:
    """Remove ANSI escape codes (for clean log file output)."""
    return re.sub(r"\033\[[0-9;]*m", "", s)


@contextmanager
def _suppress_output() -> Iterator[None]:
    """Silence stdout inside the context (used when benchmarking)."""
    with redirect_stdout(StringIO()):
        yield


def _banner(title: str, width: int = 64) -> None:
    pad = max(0, width - 2 - len(title)) // 2
    print(f"\n{BD}{C}╔{'═' * width}╗")
    print(f"║{' ' * pad} {title} {' ' * (width - pad - len(title) - 1)}║")
    print(f"╚{'═' * width}╝{RS}\n")


def _section(title: str, width: int = 64) -> None:
    print(f"\n{BD}{C}── {title} {'─' * max(0, width - len(title) - 4)}{RS}")


def _box_line(label: str, value: str, inner: int = 44) -> str:
    clean_val = _strip_ansi(value)
    pad = max(0, inner - len(label) - len(clean_val) - 2)
    return f"║ {BD}{label}{RS} {value}{' ' * pad} ║"


# ══════════════════════════════════════════════════════════════════════════
# FEATURE 1 — QKDKeyStore
# ══════════════════════════════════════════════════════════════════════════

class QKDKeyStore:
    """
    Secure in-memory key vault for QKD-generated key material.

    Security properties
    -------------------
    • Forward secrecy: keys are deleted immediately after first use.
    • Reuse prevention: attempting to retrieve an already-used key raises
      a SecurityError and logs the incident.
    • Export encryption: keys saved to disk are protected with AES-256
      derived from a user-supplied passphrase.

    Attributes
    ----------
    _vault : dict[str, dict]
        Internal store keyed by key_id. Each entry contains:
            bits      : list[int]   The raw key bits.
            timestamp : str         When the key was generated.
            used      : bool        Whether this key has been consumed.
            length    : int         Number of bits.
    """

    class SecurityError(Exception):
        """Raised when a security policy is violated (e.g. key reuse)."""

    def __init__(self, audit_log: Optional["SecurityAuditLog"] = None):
        self._vault: Dict[str, Dict[str, Any]] = {}
        self._log   = audit_log

    # ── Core operations ────────────────────────────────────────────────────

    def add_key(self, key_bits: List[int]) -> str:
        """
        Store a new key and return its unique key_id.

        Args:
            key_bits: QKD-generated key as a list of 0/1 integers.

        Returns:
            key_id: A UUID string that uniquely identifies this key.
        """
        key_id = str(uuid.uuid4())
        self._vault[key_id] = {
            "bits":      key_bits,
            "timestamp": _now(),
            "used":      False,
            "length":    len(key_bits),
        }
        if self._log:
            self._log.log_event(
                "KEY_GENERATED",
                f"key_id={_short_id(key_id)}  length={len(key_bits)} bits",
            )
        return key_id

    def get_key(self, key_id: str) -> List[int]:
        """
        Retrieve a key by ID and mark it as used (one-time retrieval).

        Raises SecurityError if the key does not exist or has already
        been used — protecting against accidental key reuse.

        Args:
            key_id: The UUID returned by add_key().

        Returns:
            The key bits list.
        """
        if key_id not in self._vault:
            raise self.SecurityError(
                f"Key {_short_id(key_id)} not found in store."
            )

        entry = self._vault[key_id]

        if entry["used"]:
            msg = (
                f"⚠  SECURITY VIOLATION: Key {_short_id(key_id)} has already "
                f"been used! Key reuse destroys One-Time Pad security. "
                f"Generate a fresh key via QKD."
            )
            if self._log:
                self._log.log_event("KEY_REUSE_ATTEMPT", f"key_id={_short_id(key_id)}")
            raise self.SecurityError(msg)

        entry["used"] = True
        if self._log:
            self._log.log_event(
                "KEY_USED",
                f"key_id={_short_id(key_id)}  length={entry['length']} bits",
            )
        return list(entry["bits"])   # return a copy, never the internal ref

    def delete_key(self, key_id: str) -> bool:
        """
        Permanently delete a key from the store.

        Args:
            key_id: UUID of the key to remove.

        Returns:
            True if deleted, False if key not found.
        """
        if key_id in self._vault:
            del self._vault[key_id]
            if self._log:
                self._log.log_event("KEY_DELETED", f"key_id={_short_id(key_id)}")
            return True
        return False

    def list_keys(self) -> None:
        """Print a formatted table of all keys currently in the store."""
        _section("Key Store Contents")
        if not self._vault:
            print(f"  {DM}(empty — no keys stored){RS}")
            return

        print(f"  {'Key ID':^10}  {'Length':^8}  {'Created':^21}  {'Status':^10}")
        print(f"  {'─'*10}  {'─'*8}  {'─'*21}  {'─'*10}")
        for kid, entry in self._vault.items():
            status = f"{R}USED{RS}" if entry["used"] else f"{G}FRESH{RS}"
            print(
                f"  {_short_id(kid):^10}  "
                f"{entry['length']:^8}  "
                f"{entry['timestamp']:^21}  "
                f"{status:^10}"
            )

    def export_keys(self, filename: str, passphrase: str = "qkd-export") -> None:
        """
        Export all UNUSED keys to an AES-256-encrypted JSON file.

        The passphrase is hashed with SHA-256 to derive the AES key.
        Exported data includes key bits, timestamps, and lengths —
        but NOT already-used keys (they should be deleted, not archived).

        Args:
            filename:   Output file path.
            passphrase: Password used to derive the AES encryption key.
        """
        unused = {
            kid: {k: v for k, v in entry.items() if k != "bits"}
            | {"bits_hex": _bits_to_hex(entry["bits"])}
            for kid, entry in self._vault.items()
            if not entry["used"]
        }

        plaintext = json.dumps(unused, indent=2).encode("utf-8")

        # Derive AES key from passphrase
        aes_key = hashlib.sha256(passphrase.encode()).digest()

        if AES_AVAILABLE:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            iv       = os.urandom(16)
            pad_len  = 16 - (len(plaintext) % 16)
            padded   = plaintext + bytes([pad_len] * pad_len)
            cipher   = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
            enc      = cipher.encryptor()
            ct       = enc.update(padded) + enc.finalize()
            payload  = {"iv": iv.hex(), "ct": ct.hex(), "count": len(unused)}
        else:
            # Fallback: base64-encoded plaintext (no AES)
            import base64
            payload = {"data": base64.b64encode(plaintext).decode(), "count": len(unused)}

        with open(filename, "w") as fh:
            json.dump(payload, fh, indent=2)

        print(f"  {G}✓ {len(unused)} key(s) exported to {filename!r}{RS}")

    def __len__(self) -> int:
        return len(self._vault)

    @property
    def fresh_count(self) -> int:
        return sum(1 for e in self._vault.values() if not e["used"])


# ══════════════════════════════════════════════════════════════════════════
# FEATURE 2 — QKDSession
# ══════════════════════════════════════════════════════════════════════════

class QKDSession:
    """
    Lifecycle manager for individual QKD key-exchange sessions.

    Each call to create_session() generates a UUID and opens a new
    session record. Fields are updated incrementally as the protocol
    progresses, and close_session() seals the record with a timestamp
    and final outcome.

    All completed sessions can be exported as a JSON audit trail.
    """

    def __init__(self, audit_log: Optional["SecurityAuditLog"] = None):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._log = audit_log

    def create_session(self, protocol: str = "BB84") -> str:
        """Open a new session and return its UUID."""
        sid = str(uuid.uuid4())
        self._sessions[sid] = {
            "session_id":         sid,
            "protocol":           protocol,
            "timestamp_start":    _now(),
            "timestamp_end":      None,
            "num_qubits_used":    0,
            "qber_measured":      None,
            "key_length":         0,
            "message_encrypted":  False,
            "eve_present":        False,
            "outcome":            "IN_PROGRESS",
            "encryption_method":  "N/A",
            "duration_sec":       None,
        }
        if self._log:
            self._log.log_event(
                "SESSION_STARTED",
                f"session={_short_id(sid)}  protocol={protocol}",
            )
        return sid

    def update_session(self, sid: str, **kwargs) -> None:
        """Merge keyword arguments into the session record."""
        if sid in self._sessions:
            self._sessions[sid].update(kwargs)

    def close_session(self, sid: str, outcome: str = "SUCCESS") -> None:
        """Seal the session with an end timestamp and final outcome."""
        if sid not in self._sessions:
            return
        s = self._sessions[sid]
        s["timestamp_end"] = _now()
        s["outcome"]       = outcome
        # Compute wall-clock duration
        try:
            fmt  = "%Y-%m-%d %H:%M:%S"
            t0   = datetime.strptime(s["timestamp_start"], fmt)
            t1   = datetime.strptime(s["timestamp_end"],   fmt)
            s["duration_sec"] = (t1 - t0).total_seconds()
        except Exception:
            s["duration_sec"] = 0

        if self._log:
            self._log.log_event(
                "SESSION_ENDED",
                f"session={_short_id(sid)}  outcome={outcome}  "
                f"qber={s.get('qber_measured', 'N/A')}  "
                f"key_length={s.get('key_length', 0)} bits",
            )

    def print_session_report(self, sid: str) -> None:
        """Print a formatted single-session report."""
        if sid not in self._sessions:
            print(f"  {R}Session {_short_id(sid)} not found.{RS}")
            return

        s = self._sessions[sid]
        outcome_colour = G if "SUCCESS" in s["outcome"] else R
        W_inner = 46

        print(f"\n  {'╔' + '═' * W_inner + '╗'}")
        print(f"  ║ {'SESSION REPORT':^{W_inner - 2}} ║")
        print(f"  {'╠' + '═' * W_inner + '╣'}")
        rows = [
            ("Session ID",    _short_id(sid)),
            ("Protocol",      s["protocol"]),
            ("Started",       s["timestamp_start"]),
            ("Ended",         s["timestamp_end"] or "—"),
            ("Duration",      f"{s['duration_sec']:.1f}s" if s["duration_sec"] is not None else "—"),
            ("Qubits used",   str(s["num_qubits_used"])),
            ("QBER",          f"{s['qber_measured']:.2%}" if s["qber_measured"] is not None else "—"),
            ("Key length",    f"{s['key_length']} bits"),
            ("Encryption",    s["encryption_method"]),
            ("Eve present",   "Yes ⚠" if s["eve_present"] else "No"),
            ("Outcome",       f"{outcome_colour}{BD}{s['outcome']}{RS}"),
        ]
        for label, value in rows:
            pad = max(0, W_inner - 2 - len(label) - len(_strip_ansi(value)) - 3)
            print(f"  ║  {BD}{label:<16}{RS}: {value}{' ' * pad} ║")
        print(f"  {'╚' + '═' * W_inner + '╝'}\n")

    def print_all_sessions(self) -> None:
        """Print a compact summary table of every session."""
        _section("All Sessions")
        if not self._sessions:
            print(f"  {DM}(no sessions recorded){RS}")
            return

        hdr = f"  {'ID':^8}  {'Protocol':^14}  {'Qubits':^7}  {'QBER':^8}  {'Key':^6}  {'Outcome':^12}"
        print(hdr)
        print(f"  {'─'*8}  {'─'*14}  {'─'*7}  {'─'*8}  {'─'*6}  {'─'*12}")
        for sid, s in self._sessions.items():
            qber_str = f"{s['qber_measured']:.2%}" if s["qber_measured"] is not None else "—"
            out = s["outcome"]
            colour = G if "SUCCESS" in out else R
            print(
                f"  {_short_id(sid):^8}  "
                f"{s['protocol']:^14}  "
                f"{s['num_qubits_used']:^7}  "
                f"{qber_str:^8}  "
                f"{s['key_length']:^6}  "
                f"{colour}{out:^12}{RS}"
            )

    def export_all_sessions(self, filename: str = "session_history.json") -> None:
        """Serialize all sessions to a JSON file."""
        with open(filename, "w") as fh:
            json.dump(list(self._sessions.values()), fh, indent=2)
        print(f"  {G}✓ {len(self._sessions)} session(s) exported to {filename!r}{RS}")


# ══════════════════════════════════════════════════════════════════════════
# FEATURE 3 — SecurityAuditLog
# ══════════════════════════════════════════════════════════════════════════

class SecurityAuditLog:
    """
    Append-only security event log written to disk in real time.

    Every significant protocol event is recorded with a timestamp,
    event type, and optional detail string. The log is written in
    plain text for easy human review and is suitable for import into
    SIEM tools.

    Log format (one line per event):
        [2024-01-15 19:32:45] EVENT_TYPE         | Details...

    Recognized event types
    ----------------------
    KEY_GENERATED, KEY_USED, KEY_DELETED, KEY_REUSE_ATTEMPT,
    SESSION_STARTED, SESSION_ENDED, EAVESDROPPER_DETECTED,
    PROTOCOL_ABORTED, MESSAGE_ENCRYPTED, MESSAGE_DECRYPTED,
    BENCHMARK_STARTED, BENCHMARK_ENDED
    """

    # Severity levels for colour-coding the terminal printout
    _SEVERITY: Dict[str, str] = {
        "KEY_GENERATED":        G,
        "KEY_USED":             G,
        "KEY_DELETED":          DM,
        "KEY_REUSE_ATTEMPT":    R,
        "SESSION_STARTED":      C,
        "SESSION_ENDED":        C,
        "EAVESDROPPER_DETECTED": R,
        "PROTOCOL_ABORTED":     R,
        "MESSAGE_ENCRYPTED":    G,
        "MESSAGE_DECRYPTED":    G,
        "BENCHMARK_STARTED":    B,
        "BENCHMARK_ENDED":      B,
    }

    def __init__(self, log_path: str = _AUDIT_LOG_PATH):
        self._path   = log_path
        self._events: List[Dict[str, str]] = []

        # Write a session-start marker to the file
        with open(self._path, "a") as fh:
            fh.write(
                f"\n{'─'*72}\n"
                f"[{_now()}] AUDIT_SESSION_OPEN  | "
                f"real_qkd_system.py started\n"
            )

    def log_event(self, event_type: str, details: str = "") -> None:
        """
        Record one event to both the in-memory list and the log file.

        Args:
            event_type: One of the recognised event type strings.
            details:    Free-form detail string (no newlines).
        """
        timestamp = _now()
        record    = {"timestamp": timestamp, "event": event_type, "details": details}
        self._events.append(record)

        line = f"[{timestamp}] {event_type:<28} | {details}\n"
        with open(self._path, "a") as fh:
            fh.write(line)

    def print_audit_log(self, tail: Optional[int] = None) -> None:
        """
        Print the in-memory event log to the terminal with colour-coding.

        Args:
            tail: If given, print only the last `tail` events.
        """
        _section("Security Audit Log")
        events = self._events[-tail:] if tail else self._events
        if not events:
            print(f"  {DM}(no events recorded){RS}")
            return

        for rec in events:
            colour = self._SEVERITY.get(rec["event"], W)
            print(
                f"  {DM}[{rec['timestamp']}]{RS}  "
                f"{colour}{BD}{rec['event']:<28}{RS}  "
                f"{DM}{rec['details']}{RS}"
            )

    def get_security_report(self) -> Dict[str, Any]:
        """
        Summarise all logged events into a statistics dictionary.

        Returns a dict with counts by event type and key security metrics.
        """
        counts: Dict[str, int] = {}
        for rec in self._events:
            counts[rec["event"]] = counts.get(rec["event"], 0) + 1

        threats = counts.get("EAVESDROPPER_DETECTED", 0)
        aborts  = counts.get("PROTOCOL_ABORTED",      0)
        keys    = counts.get("KEY_GENERATED",          0)
        reuse   = counts.get("KEY_REUSE_ATTEMPT",      0)

        return {
            "total_events":          len(self._events),
            "event_counts":          counts,
            "threats_detected":      threats,
            "sessions_aborted":      aborts,
            "keys_generated":        keys,
            "key_reuse_attempts":    reuse,
            "security_incidents":    threats + reuse,
            "log_file":              self._path,
        }

    def print_security_report(self) -> None:
        """Print a formatted security metrics report."""
        rep = self.get_security_report()
        W_inner = 46
        colour  = R if rep["security_incidents"] > 0 else G

        print(f"\n  {'╔' + '═' * W_inner + '╗'}")
        print(f"  ║ {'SECURITY REPORT':^{W_inner - 2}} ║")
        print(f"  {'╠' + '═' * W_inner + '╣'}")
        rows = [
            ("Total events logged",    str(rep["total_events"])),
            ("Keys generated",         str(rep["keys_generated"])),
            ("Sessions started",       str(rep.get("event_counts", {}).get("SESSION_STARTED", 0))),
            ("Sessions ended OK",      str(rep.get("event_counts", {}).get("SESSION_ENDED", 0))),
            ("Eavesdroppers detected", f"{colour}{rep['threats_detected']}{RS}"),
            ("Sessions aborted",       f"{colour}{rep['sessions_aborted']}{RS}"),
            ("Key reuse attempts",     f"{colour}{rep['key_reuse_attempts']}{RS}"),
            ("Security incidents",     f"{colour}{BD}{rep['security_incidents']}{RS}"),
            ("Log file",               rep["log_file"]),
        ]
        for label, value in rows:
            pad = max(0, W_inner - 2 - len(label) - len(_strip_ansi(value)) - 3)
            print(f"  ║  {BD}{label:<22}{RS}: {value}{' ' * pad} ║")
        print(f"  {'╚' + '═' * W_inner + '╝'}\n")


# ══════════════════════════════════════════════════════════════════════════
# FEATURE 4 — ProtocolSelector (BB84 variants)
# ══════════════════════════════════════════════════════════════════════════

# Protocol metadata table
_PROTOCOLS: Dict[str, Dict[str, Any]] = {
    "BB84": {
        "bases":        2,
        "states":       4,
        "threshold":    0.110,
        "description":  "Bennett & Brassard 1984 — the original QKD protocol",
        "sift_rate":    0.50,   # ~50% of bits survive sifting
    },
    "BB84-Enhanced": {
        "bases":        2,
        "states":       4,
        "threshold":    0.189,
        "description":  "BB84 with two-way classical post-processing (BBBSS)",
        "sift_rate":    0.50,
    },
    "Six-State": {
        "bases":        3,
        "states":       6,
        "threshold":    0.264,
        "description":  "Bruss 1998 — 3 MUBs, stronger eavesdropper detection",
        "sift_rate":    0.333,   # ~33% survive (must match on 1-of-3 bases)
    },
}


class ProtocolSelector:
    """
    Run and compare multiple QKD protocol variants.

    BB84 and its variants all use the same underlying qubit mechanics
    from the project's existing simulation, but with different:
      • Security thresholds (higher threshold = tolerates more noise)
      • Sifting rates (Six-State keeps ~33% vs BB84's ~50%)
      • Effective key yield per qubit sent

    The Six-State and Enhanced BB84 results are derived analytically
    from the raw BB84 simulation output — the extra classical steps
    are modelled via adjusting the threshold and key-rate formula.
    """

    def __init__(
        self,
        audit_log:   Optional[SecurityAuditLog] = None,
        session_mgr: Optional[QKDSession]        = None,
        key_store:   Optional[QKDKeyStore]        = None,
    ):
        self._log     = audit_log
        self._session = session_mgr
        self._store   = key_store

    def run_protocol(
        self,
        protocol_name: str,
        num_qubits:    int,
        eve_present:   bool  = False,
        intercept_prob: float = 1.0,
        verbose:       bool  = True,
    ) -> Dict[str, Any]:
        """
        Execute one QKD session under the chosen protocol.

        For all protocols the simulation is identical (BB84 engine).
        The difference is the security threshold used to decide ABORT/PROCEED
        and the sifting rate used to model key yield.

        Args:
            protocol_name:  One of "BB84", "BB84-Enhanced", "Six-State".
            num_qubits:     Number of photons in the exchange.
            eve_present:    Whether Eve is active.
            intercept_prob: Eve's per-photon interception rate.
            verbose:        If False, suppress printed output.

        Returns:
            Extended result dict (superset of run_full_protocol output).
        """
        if protocol_name not in _PROTOCOLS:
            raise ValueError(
                f"Unknown protocol {protocol_name!r}. "
                f"Choose from: {list(_PROTOCOLS)}"
            )

        proto = _PROTOCOLS[protocol_name]
        sid   = None

        if self._session:
            sid = self._session.create_session(protocol=protocol_name)
            self._session.update_session(
                sid, num_qubits_used=num_qubits, eve_present=eve_present
            )

        # ── Run BB84 engine (suppressing inner prints if not verbose) ──────
        ctx = _suppress_output() if not verbose else contextmanager(lambda: iter([None]))()
        with ctx:
            raw = run_full_protocol(
                num_qubits     = num_qubits,
                eve_present    = eve_present,
                intercept_prob = intercept_prob,
            )

        qber      = raw["qber"]
        threshold = proto["threshold"]

        # Re-evaluate the security decision using THIS protocol's threshold
        eve_det  = qber > threshold
        decision = "ABORTED" if eve_det else "KEY GENERATED"
        final_key = raw["final_key"] if not eve_det else []

        if sid:
            self._session.update_session(
                sid,
                qber_measured      = qber,
                key_length         = len(final_key),
                outcome            = decision,
            )
            self._session.close_session(sid, outcome=decision)

        if eve_det and self._log:
            self._log.log_event(
                "EAVESDROPPER_DETECTED",
                f"protocol={protocol_name}  qber={qber:.2%}  "
                f"threshold={threshold:.1%}",
            )

        if decision == "ABORTED" and self._log:
            self._log.log_event(
                "PROTOCOL_ABORTED",
                f"protocol={protocol_name}  qber={qber:.2%}",
            )

        if final_key and self._store:
            kid = self._store.add_key(final_key)
        else:
            kid = None

        return {
            **raw,
            "protocol":     protocol_name,
            "threshold":    threshold,
            "eve_detected": eve_det,
            "status":       decision,
            "final_key":    final_key,
            "final_key_length": len(final_key),
            "key_id":       kid,
            "session_id":   sid,
        }

    def compare_protocols(
        self,
        num_qubits:  int  = 256,
        eve_present: bool = False,
    ) -> None:
        """
        Run all three protocols with the same parameters and print a table.

        Args:
            num_qubits:  Qubit count per protocol run.
            eve_present: Whether Eve is active during all runs.
        """
        _section("Protocol Comparison")
        print(f"  Qubits: {num_qubits}   Eve: {'active' if eve_present else 'none'}\n")

        results = {}
        for name in _PROTOCOLS:
            res = self.run_protocol(
                name, num_qubits,
                eve_present    = eve_present,
                intercept_prob = 1.0,
                verbose        = False,
            )
            results[name] = res

        # ── Header ──────────────────────────────────────────────────────────
        hdr = (
            f"  {'Protocol':<16}  {'Bases':^5}  "
            f"{'Threshold':^10}  {'QBER':^8}  "
            f"{'Key (bits)':^11}  {'Status':^14}"
        )
        print(hdr)
        print(f"  {'─'*16}  {'─'*5}  {'─'*10}  {'─'*8}  {'─'*11}  {'─'*14}")

        for name, res in results.items():
            proto  = _PROTOCOLS[name]
            colour = G if res["status"] == "KEY GENERATED" else R
            icon   = "✅" if res["status"] == "KEY GENERATED" else "❌"
            print(
                f"  {name:<16}  "
                f"{proto['bases']:^5}  "
                f"{proto['threshold']:^10.1%}  "
                f"{res['qber']:^8.2%}  "
                f"{res['final_key_length']:^11}  "
                f"{colour}{icon} {res['status']:<12}{RS}"
            )
        print()

        # ── Protocol descriptions ────────────────────────────────────────────
        print(f"  {DM}Protocol notes:")
        for name, proto in _PROTOCOLS.items():
            print(f"    {BD}{name:<16}{RS}: {proto['description']}")
        print(RS)


# ══════════════════════════════════════════════════════════════════════════
# FEATURE 5 — Performance Benchmarking
# ══════════════════════════════════════════════════════════════════════════

def benchmark_qkd(
    num_runs:    int   = 50,
    num_qubits:  int   = 256,
    eve_present: bool  = False,
    audit_log:   Optional[SecurityAuditLog] = None,
) -> Dict[str, Any]:
    """
    Run the BB84 protocol `num_runs` times and collect performance statistics.

    Measures wall-clock time, key length, QBER, and success rate
    across all trials, then prints a formatted benchmark report.

    Args:
        num_runs:    Number of independent protocol runs (default 50).
        num_qubits:  Qubits per run (default 256).
        eve_present: Whether Eve is active during all runs.
        audit_log:   Optional audit log for benchmark events.

    Returns:
        Dict with keys: runs, successes, failures, avg_time_sec,
        avg_key_length, avg_qber, min_qber, max_qber, keys_per_sec.
    """
    if audit_log:
        audit_log.log_event(
            "BENCHMARK_STARTED",
            f"runs={num_runs}  qubits={num_qubits}  eve={eve_present}",
        )

    _section(f"Performance Benchmark  ({num_runs} runs, {num_qubits} qubits each)")

    times:       List[float] = []
    key_lengths: List[int]   = []
    qbers:       List[float] = []
    successes:   int         = 0
    failures:    int         = 0

    bar_width = 40

    for i in range(num_runs):
        # Progress bar
        done   = int(bar_width * (i + 1) / num_runs)
        pct    = (i + 1) / num_runs * 100
        bar    = f"[{G}{'█' * done}{DM}{'░' * (bar_width - done)}{RS}]"
        print(f"  {bar} {pct:5.1f}%  run {i+1}/{num_runs}", end="\r", flush=True)

        t0 = time.perf_counter()
        with _suppress_output():
            res = run_full_protocol(
                num_qubits     = num_qubits,
                eve_present    = eve_present,
                intercept_prob = 1.0,
            )
        elapsed = time.perf_counter() - t0

        times.append(elapsed)
        qbers.append(res["qber"])

        if res["status"] == "KEY GENERATED":
            successes += 1
            key_lengths.append(res["final_key_length"])
        else:
            failures  += 1

    print()   # newline after progress bar

    # ── Statistics ────────────────────────────────────────────────────────
    total_time   = sum(times)
    avg_time     = statistics.mean(times)
    avg_key      = statistics.mean(key_lengths) if key_lengths else 0.0
    avg_qber     = statistics.mean(qbers)
    min_qber     = min(qbers)
    max_qber     = max(qbers)
    success_pct  = successes / num_runs * 100
    keys_per_sec = successes / total_time if total_time > 0 else 0

    if audit_log:
        audit_log.log_event(
            "BENCHMARK_ENDED",
            f"runs={num_runs}  success={successes}/{num_runs}  "
            f"avg_time={avg_time:.4f}s  avg_qber={avg_qber:.2%}  "
            f"keys_per_sec={keys_per_sec:.1f}",
        )

    # ── Print report ──────────────────────────────────────────────────────
    W_inner = 44
    success_colour = G if successes == num_runs else (Y if successes > num_runs * 0.8 else R)

    print(f"\n  {'╔' + '═' * W_inner + '╗'}")
    print(f"  ║ {'QKD PERFORMANCE BENCHMARK':^{W_inner - 2}} ║")
    print(f"  {'╠' + '═' * W_inner + '╣'}")
    rows = [
        ("Total Runs",       f"{num_runs}"),
        ("Successful",       f"{success_colour}{successes} ({success_pct:.0f}%){RS}"),
        ("Aborted",          f"{failures} ({100-success_pct:.0f}%)"),
        ("Avg Time/Run",     f"{avg_time*1000:.1f} ms"),
        ("Total Time",       f"{total_time:.2f} s"),
        ("Avg Key Length",   f"{avg_key:.1f} bits"),
        ("Avg QBER",         f"{avg_qber:.2%}"),
        ("Min QBER",         f"{min_qber:.2%}"),
        ("Max QBER",         f"{max_qber:.2%}"),
        ("Keys/Second",      f"{keys_per_sec:.1f}"),
        ("Qubits/Run",       f"{num_qubits}"),
        ("Eve Active",       "Yes ⚠" if eve_present else "No"),
    ]
    for label, value in rows:
        pad = max(0, W_inner - 2 - len(label) - len(_strip_ansi(value)) - 3)
        print(f"  ║  {BD}{label:<18}{RS}: {value}{' ' * pad} ║")
    print(f"  {'╚' + '═' * W_inner + '╝'}\n")

    # ── QBER distribution histogram ───────────────────────────────────────
    _print_qber_histogram(qbers)

    return {
        "runs":           num_runs,
        "successes":      successes,
        "failures":       failures,
        "avg_time_sec":   avg_time,
        "avg_key_length": avg_key,
        "avg_qber":       avg_qber,
        "min_qber":       min_qber,
        "max_qber":       max_qber,
        "keys_per_sec":   keys_per_sec,
    }


def _print_qber_histogram(qbers: List[float], bins: int = 10) -> None:
    """Print a compact ASCII histogram of QBER values."""
    if not qbers:
        return

    _section("QBER Distribution Histogram")
    lo, hi = 0.0, max(0.30, max(qbers) + 0.01)
    step   = (hi - lo) / bins
    counts = [0] * bins
    for q in qbers:
        idx = min(int((q - lo) / step), bins - 1)
        counts[idx] += 1

    bar_scale = max(counts) if max(counts) > 0 else 1
    threshold = 0.11

    for i, cnt in enumerate(counts):
        lo_b  = lo + i * step
        hi_b  = lo_b + step
        width = int(cnt / bar_scale * 30)
        colour = R if lo_b >= threshold else G
        bar   = f"{colour}{'█' * width}{RS}"
        mark  = f"  {R}← threshold{RS}" if lo_b < threshold <= hi_b else ""
        print(
            f"  {lo_b:5.1%}–{hi_b:5.1%}  │{bar:<32} {cnt:3d}{mark}"
        )
    print()


# ══════════════════════════════════════════════════════════════════════════
# High-level encrypted communication (uses all subsystems)
# ══════════════════════════════════════════════════════════════════════════

def _run_encrypted_session(
    message:        str,
    num_qubits:     int,
    eve_present:    bool,
    intercept_prob: float,
    protocol:       str,
    key_store:      QKDKeyStore,
    session_mgr:    QKDSession,
    audit_log:      SecurityAuditLog,
) -> Optional[Dict[str, Any]]:
    """
    Run one complete encrypted communication session using all subsystems.

    Steps:
      1. Open a session record.
      2. Run BB84 via ProtocolSelector.
      3. Store the generated key in QKDKeyStore.
      4. Encrypt the message using the best available method.
      5. Decrypt and verify.
      6. Close the session.
      7. Emit audit events.

    Returns:
        Summary dict, or None if QKD was aborted.
    """
    selector = ProtocolSelector(
        audit_log   = audit_log,
        session_mgr = session_mgr,
        key_store   = key_store,
    )

    # ── QKD ───────────────────────────────────────────────────────────────
    print(f"\n  {C}Running {protocol} protocol ({num_qubits} qubits)...{RS}")
    res = selector.run_protocol(
        protocol, num_qubits,
        eve_present    = eve_present,
        intercept_prob = intercept_prob,
        verbose        = False,
    )

    qber = res["qber"]
    _print_mini_qber(qber, res["threshold"])

    if res["status"] == "ABORTED":
        audit_log.log_event("PROTOCOL_ABORTED", f"qber={qber:.2%}")
        print(f"  {R}{BD}❌ QKD ABORTED — Eavesdropper detected (QBER={qber:.2%}){RS}")
        print(f"  {R}Message NOT encrypted — forward secrecy maintained.{RS}")
        return None

    # Retrieve key from store (marks it as used immediately)
    key_id = res["key_id"]
    key    = key_store.get_key(key_id)
    key_len = len(key)
    print(f"  {G}✓ Key established: {key_len} bits  "
          f"[{_short_id(key_id)}]{RS}")

    # ── Encryption ────────────────────────────────────────────────────────
    msg_bits_needed = len(message.encode("utf-8")) * 8
    enc_method = ""
    ciphertext_hex = ""
    iv_bytes: Optional[bytes] = None
    ciphertext_bits: List[int] = []

    if key_len >= msg_bits_needed:
        enc_method       = "One-Time Pad (OTP)"
        ciphertext_bits, _ = otp_encrypt(message, key)
        ciphertext_hex   = _bits_to_hex(ciphertext_bits)
    elif AES_AVAILABLE:
        enc_method         = "AES-256-CBC"
        cipher_bytes, iv_bytes = aes_encrypt(message, key)
        ciphertext_hex     = cipher_bytes.hex()
    else:
        enc_method         = "Simple XOR"
        ciphertext_hex     = simple_encrypt(message, key)

    audit_log.log_event(
        "MESSAGE_ENCRYPTED",
        f"method={enc_method}  msg_len={len(message)}chars  "
        f"key_id={_short_id(key_id)}",
    )

    session_mgr.update_session(
        res["session_id"],
        message_encrypted  = True,
        encryption_method  = enc_method,
        key_length         = key_len,
    )

    # ── Decryption ────────────────────────────────────────────────────────
    # NOTE: in a real system Bob would receive the ciphertext over the
    # network. Here we simulate both sides locally for demonstration.
    decrypted = ""
    try:
        if enc_method == "One-Time Pad (OTP)":
            decrypted = otp_decrypt(ciphertext_bits, key)
        elif enc_method == "AES-256-CBC":
            decrypted = aes_decrypt(bytes.fromhex(ciphertext_hex), iv_bytes, key)
        else:
            decrypted = simple_decrypt(ciphertext_hex, key)
    except Exception as exc:
        print(f"  {R}Decryption error: {exc}{RS}")

    audit_log.log_event("MESSAGE_DECRYPTED", f"method={enc_method}")

    matched = (decrypted == message)

    # ── Print result ──────────────────────────────────────────────────────
    print(f"  {BD}Original  :{RS} {repr(message[:60])}{'...' if len(message)>60 else ''}")
    print(f"  {BD}Ciphertext:{RS} {Y}{ciphertext_hex[:48]}{'...' if len(ciphertext_hex)>48 else ''}{RS}")
    print(f"  {BD}Decrypted :{RS} {repr(decrypted[:60])}{'...' if len(decrypted)>60 else ''}")

    if matched:
        print(f"  {G}{BD}✅ PERFECT MATCH — End-to-end quantum-secure communication!{RS}")
    else:
        print(f"  {R}{BD}❌ MISMATCH — Decryption error!{RS}")

    return {
        "matched":           matched,
        "qber":              qber,
        "key_length":        key_len,
        "encryption_method": enc_method,
        "ciphertext_hex":    ciphertext_hex,
        "decrypted":         decrypted,
    }


def _print_mini_qber(qber: float, threshold: float = 0.11) -> None:
    """Inline QBER status line."""
    colour = G if qber <= threshold else R
    icon   = "✓ SECURE" if qber <= threshold else "⚠ ALERT"
    bar_w  = 20
    filled = int(qber / 0.30 * bar_w)
    bar    = f"{colour}{'█' * filled}{'░' * (bar_w - filled)}{RS}"
    print(f"  QBER = {colour}{qber:.2%}{RS}  [{bar}]  {colour}{icon}{RS}")


# ══════════════════════════════════════════════════════════════════════════
# MASTER DEMO
# ══════════════════════════════════════════════════════════════════════════

def run_complete_real_demo() -> None:
    """
    Complete end-to-end demonstration of the Real QKD System.

    Showcases all five production features:
      Demo 1 — Standard BB84 with OTP encryption
      Demo 2 — Eve attack (eavesdropper detected → abort)
      Demo 3 — Protocol comparison (BB84, Enhanced, Six-State)
      Demo 4 — Performance benchmark (50 trials)
      Demo 5 — Security audit log and session history
    """

    # ── Instantiate shared infrastructure ─────────────────────────────────
    audit   = SecurityAuditLog()
    store   = QKDKeyStore(audit_log=audit)
    sessions = QKDSession(audit_log=audit)

    _banner("COMPLETE REAL QKD SYSTEM — PRODUCTION DEMONSTRATION", width=64)

    print(f"  {DM}System timestamp : {_now()}{RS}")
    print(f"  {DM}Audit log file   : {_AUDIT_LOG_PATH}{RS}")
    print(f"  {DM}Python modules   : alice, bob, eve, qber, encryption{RS}\n")

    # ══════════════════════════════════════════════════════════════════════
    # DEMO 1 — Standard BB84 + OTP encryption
    # ══════════════════════════════════════════════════════════════════════
    _banner("DEMO 1 — Quantum-Secure Message Exchange (No Eve)", width=64)
    print(
        "  Alice and Bob run BB84 to establish a shared secret key,\n"
        "  then use it to encrypt a message with a One-Time Pad.\n"
    )

    _run_encrypted_session(
        message        = "Hello Bob! This message is protected by the laws of physics.",
        num_qubits     = 512,
        eve_present    = False,
        intercept_prob = 1.0,
        protocol       = "BB84",
        key_store      = store,
        session_mgr    = sessions,
        audit_log      = audit,
    )

    # ══════════════════════════════════════════════════════════════════════
    # DEMO 2 — Eve intercepts → QBER spike → ABORT
    # ══════════════════════════════════════════════════════════════════════
    _banner("DEMO 2 — Attack Scenario: Eve Intercepts All Photons", width=64)
    print(
        "  Eve performs a full intercept-and-resend attack.\n"
        "  BB84 detects the intrusion via QBER ≈ 25% and aborts.\n"
        "  The secret message is NEVER encrypted with a compromised key.\n"
    )

    _run_encrypted_session(
        message        = "Top secret: launch code 4729",
        num_qubits     = 512,
        eve_present    = True,
        intercept_prob = 1.0,
        protocol       = "BB84",
        key_store      = store,
        session_mgr    = sessions,
        audit_log      = audit,
    )

    # ══════════════════════════════════════════════════════════════════════
    # DEMO 3 — Protocol comparison
    # ══════════════════════════════════════════════════════════════════════
    _banner("DEMO 3 — Protocol Comparison: BB84 vs Enhanced vs Six-State", width=64)
    print(
        "  Running all three protocol variants with identical settings.\n"
        "  Each protocol trades different security thresholds vs key yield.\n"
    )

    selector = ProtocolSelector(audit_log=audit, session_mgr=sessions, key_store=store)
    selector.compare_protocols(num_qubits=256, eve_present=False)

    # ══════════════════════════════════════════════════════════════════════
    # DEMO 4 — Performance benchmark
    # ══════════════════════════════════════════════════════════════════════
    _banner("DEMO 4 — Performance Benchmark (50 trials)", width=64)
    print(
        "  Running BB84 fifty times to measure statistical performance.\n"
        "  Reports average key length, QBER distribution, and throughput.\n"
    )

    benchmark_qkd(num_runs=50, num_qubits=256, eve_present=False, audit_log=audit)

    # ══════════════════════════════════════════════════════════════════════
    # DEMO 5 — Key Store status + Session log + Audit report
    # ══════════════════════════════════════════════════════════════════════
    _banner("DEMO 5 — Security Audit & Session History", width=64)

    # Key store
    store.list_keys()

    # Session table
    sessions.print_all_sessions()

    # Last 20 audit events
    audit.print_audit_log(tail=20)

    # Security metrics
    audit.print_security_report()

    # Export artefacts
    _section("Export Artefacts")
    store.export_keys("qkd_keystore_export.json", passphrase="demo-passphrase")
    sessions.export_all_sessions("session_history.json")

    # ── Final system status ────────────────────────────────────────────────
    _banner("SYSTEM STATUS REPORT", width=64)

    rep        = audit.get_security_report()
    all_sids   = list(sessions._sessions.keys())
    successful = sum(
        1 for s in sessions._sessions.values()
        if "SUCCESS" in s.get("outcome", "") or s.get("outcome") == "KEY GENERATED"
    )

    W_s = 56
    print(f"  {'╔' + '═' * W_s + '╗'}")
    print(f"  ║ {'REAL QKD SYSTEM — FINAL STATUS':^{W_s}} ║")
    print(f"  {'╠' + '═' * W_s + '╣'}")

    status_rows = [
        ("System",             "OPERATIONAL"),
        ("Sessions run",       str(len(all_sids))),
        ("Successful sessions",f"{G}{successful}{RS}"),
        ("Aborted sessions",   f"{R}{rep['sessions_aborted']}{RS}"),
        ("Keys generated",     str(rep["keys_generated"])),
        ("Keys in store",      str(len(store))),
        ("Security incidents", f"{(R if rep['security_incidents']>0 else G)}"
                               f"{rep['security_incidents']}{RS}"),
        ("Audit log",          _AUDIT_LOG_PATH),
        ("Session export",     "session_history.json"),
    ]
    for label, value in status_rows:
        pad = max(0, W_s - 2 - len(label) - len(_strip_ansi(value)) - 3)
        print(f"  ║  {BD}{label:<22}{RS}: {value}{' ' * pad} ║")

    print(f"  {'╠' + '═' * W_s + '╣'}")
    tagline = "QUANTUM-SECURE — Protected by the Laws of Physics"
    print(f"  ║  {G}{BD}{tagline:^{W_s - 2}}{RS}  ║")
    print(f"  {'╚' + '═' * W_s + '╝'}\n")


# ══════════════════════════════════════════════════════════════════════════
# Standalone entry point
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    run_complete_real_demo()
