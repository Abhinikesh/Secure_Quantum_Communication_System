"""
encryption.py — Real Message Encryption Using a QKD-Generated Key
==================================================================

This module is the final piece of an end-to-end Quantum-Secure Communication
system. It takes the secret key produced by the BB84 QKD protocol and uses it
to encrypt and decrypt real text messages.

Three encryption methods are provided, ordered by theoretical strength:

  Method 1 — One-Time Pad (OTP)
      The ONLY provably unbreakable cipher (Shannon, 1949).
      Requires a key at least as long as the message in bits.
      Perfect for short messages when QKD produces enough key material.

  Method 2 — AES-256-CBC
      The global industry standard, used by banks, governments, and TLS.
      The QKD key is hashed with SHA-256 to produce a 256-bit AES key,
      making message length unconstrained regardless of key length.

  Method 3 — Simple XOR (demonstration)
      XOR each character with a repeating key byte. No extra libraries.
      Weaker than OTP (key repeats), but illustrates the core concept.

How QKD + Encryption fits together
------------------------------------
  Traditional crypto  :  Alice and Bob agree on a key OVER the network
                          → an eavesdropper can steal the key
  QKD + This module   :  Alice and Bob establish a key using PHYSICS
                          → eavesdropping is physically detectable
                          → the key is then used here to encrypt messages

Dependencies: qber.py (existing), cryptography (pip install cryptography)
"""

import hashlib
import os
import struct
from typing import List, Optional, Tuple

# ── cryptography library (AES-256) ─────────────────────────────────────────
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    AES_AVAILABLE = True
except ImportError:
    AES_AVAILABLE = False

# ── Existing project module ────────────────────────────────────────────────
from qber import run_full_protocol


# ── ANSI colour helpers (degrade gracefully on terminals without colour) ───
_RED    = "\033[91m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"


# ══════════════════════════════════════════════════════════════════════════
# Helper utilities
# ══════════════════════════════════════════════════════════════════════════

def _text_to_bits(text: str) -> List[int]:
    """
    Convert a UTF-8 string to a flat list of bits (MSB first per byte).

    Each character is encoded as its UTF-8 byte sequence; each byte is
    represented as 8 bits from most-significant to least-significant.

    Example:
        'A' (ASCII 65 = 0b01000001) → [0, 1, 0, 0, 0, 0, 0, 1]

    Args:
        text: Any Python string (ASCII or Unicode).

    Returns:
        List of 0s and 1s with length = len(text.encode('utf-8')) * 8.
    """
    bits = []
    for byte in text.encode("utf-8"):
        for shift in range(7, -1, -1):      # MSB first (bit 7 → bit 0)
            bits.append((byte >> shift) & 1)
    return bits


def _bits_to_text(bits: List[int]) -> str:
    """
    Convert a flat list of bits back to a UTF-8 string.

    Pads the bit list to a multiple of 8 if needed (shouldn't happen in
    normal use, but guards against off-by-one mistakes).

    Args:
        bits: List of 0s and 1s. Length must be a multiple of 8.

    Returns:
        Decoded Python string.

    Raises:
        ValueError: If bits cannot be decoded as valid UTF-8.
    """
    # Pad to multiple of 8 just in case
    padded = bits[:]
    while len(padded) % 8 != 0:
        padded.append(0)

    byte_values = []
    for i in range(0, len(padded), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | padded[i + j]
        byte_values.append(byte)

    return bytes(byte_values).decode("utf-8", errors="replace")


def _bits_to_bytes(bits: List[int]) -> bytes:
    """
    Pack a list of bits into a bytes object (MSB-first, padded to byte boundary).

    Used internally to convert QKD key bits into a byte string for hashing.

    Args:
        bits: List of 0s and 1s.

    Returns:
        Packed bytes (length = ceil(len(bits) / 8)).
    """
    padded = bits[:]
    while len(padded) % 8 != 0:
        padded.append(0)

    result = bytearray()
    for i in range(0, len(padded), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | padded[i + j]
        result.append(byte)
    return bytes(result)


def _bits_to_hex(bits: List[int]) -> str:
    """
    Convert a bit list to a compact hexadecimal string for display.

    Args:
        bits: List of 0s and 1s.

    Returns:
        Lowercase hex string (e.g. 'a3f9d2c8...').
    """
    return _bits_to_bytes(bits).hex()


def _xor_bits(a: List[int], b: List[int]) -> List[int]:
    """
    Bitwise XOR of two equal-length bit lists.

    This is the fundamental operation of both the One-Time Pad and simple XOR.
    XOR has the beautiful property:  (a XOR b) XOR b = a
    which means the same operation encrypts and decrypts.

    Args:
        a: First bit list.
        b: Second bit list (must be same length as a).

    Returns:
        List of XOR results, same length as inputs.

    Raises:
        ValueError: If the lists have different lengths.
    """
    if len(a) != len(b):
        raise ValueError(
            f"XOR requires equal-length lists: got {len(a)} and {len(b)}"
        )
    return [x ^ y for x, y in zip(a, b)]


# ══════════════════════════════════════════════════════════════════════════
# METHOD 1 — One-Time Pad (OTP)
# ══════════════════════════════════════════════════════════════════════════

def otp_encrypt(
    message_text: str,
    key_bits:     List[int],
) -> Tuple[List[int], List[int]]:
    """
    Encrypt a text message using the One-Time Pad cipher.

    The One-Time Pad is the ONLY cipher with mathematical proof of perfect
    secrecy (Claude Shannon, 1949). An adversary who intercepts the ciphertext
    gains ZERO information about the plaintext — every possible message of that
    length is equally likely without the key.

    How it works
    ------------
    1. Convert the message to bits (UTF-8, 8 bits per byte).
    2. XOR each message bit with the corresponding key bit.
    3. The result is the ciphertext — indistinguishable from random noise.

    Requirements
    ------------
    - The key MUST be at least as long as the message in bits.
    - The key MUST be used only once (hence "one-time" pad). Reuse destroys
      security — this is why QKD generates a fresh key for every session.
    - The key MUST be truly random — QKD guarantees this via quantum physics.

    Args:
        message_text: The plaintext message to encrypt (str, UTF-8).
        key_bits:     The QKD-generated key as a list of 0s and 1s.
                      Must have length >= len(message_text.encode()) * 8.

    Returns:
        Tuple (ciphertext_bits, used_key_bits):
            ciphertext_bits : Encrypted bits (same length as message bits).
            used_key_bits   : The portion of the key consumed (for record-keeping).

    Raises:
        ValueError: If key_bits is shorter than the message requires.
        ValueError: If message_text is empty.
    """
    if not message_text:
        raise ValueError("Message cannot be empty.")

    message_bits = _text_to_bits(message_text)
    msg_len      = len(message_bits)

    if len(key_bits) < msg_len:
        raise ValueError(
            f"Key too short for One-Time Pad!\n"
            f"  Message needs : {msg_len} bits  ({len(message_text.encode())} bytes)\n"
            f"  Key provides  : {len(key_bits)} bits\n"
            f"  Shortfall     : {msg_len - len(key_bits)} bits\n"
            f"  Fix: increase num_qubits in run_full_protocol(), or use AES encryption."
        )

    used_key      = key_bits[:msg_len]
    ciphertext    = _xor_bits(message_bits, used_key)

    # ── Visual walkthrough for the first character ────────────────────────
    first_char    = message_text[0]
    first_char_bits = message_bits[:8]
    first_key_bits  = used_key[:8]
    first_cipher    = ciphertext[:8]

    print(f"\n  {_CYAN}One-Time Pad — Encryption Walkthrough{_RESET}")
    print(f"  {'─'*52}")
    print(f"  First char    : {repr(first_char)!s:>6}  "
          f"(ASCII {ord(first_char)}  =  {''.join(map(str, first_char_bits))})")
    print(f"  Key bits      :          "
          f"  {''.join(map(str, first_key_bits))}")
    print(f"  XOR result    :          "
          f"  {''.join(map(str, first_cipher))}"
          f"  =  {_YELLOW}{_bits_to_hex(first_cipher)}{_RESET}")
    if len(message_text) > 1:
        print(f"  ... (repeated for all {len(message_text)} characters)")
    print(f"  {'─'*52}")

    return ciphertext, used_key


def otp_decrypt(
    ciphertext_bits: List[int],
    key_bits:        List[int],
) -> str:
    """
    Decrypt a One-Time Pad ciphertext back to the original message.

    XOR is its own inverse: if  C = M XOR K,  then  M = C XOR K.
    So decryption is identical to encryption — just XOR again.

    Args:
        ciphertext_bits: Encrypted bits produced by otp_encrypt().
        key_bits:        The SAME key bits used during encryption.
                         Must have length >= len(ciphertext_bits).

    Returns:
        The decrypted plaintext as a Python string.

    Raises:
        ValueError: If key_bits is shorter than ciphertext_bits.
    """
    n = len(ciphertext_bits)

    if len(key_bits) < n:
        raise ValueError(
            f"Key too short for decryption: need {n} bits, have {len(key_bits)}."
        )

    used_key       = key_bits[:n]
    plaintext_bits = _xor_bits(ciphertext_bits, used_key)

    return _bits_to_text(plaintext_bits)


# ══════════════════════════════════════════════════════════════════════════
# METHOD 2 — AES-256-CBC
# ══════════════════════════════════════════════════════════════════════════

def derive_aes_key(key_bits: List[int]) -> bytes:
    """
    Derive a 256-bit AES key from QKD key bits using SHA-256.

    The QKD key may be any length. SHA-256 maps it deterministically to
    a fixed 32-byte (256-bit) AES key. Both Alice and Bob independently
    compute the same hash from their shared QKD key bits — no key transfer
    over the network is needed.

    Why hash? The raw QKD bits may be too short or have mild correlations
    from imperfect hardware. SHA-256 is a cryptographic hash that:
      • Produces exactly 256 bits regardless of input length.
      • Has avalanche effect: 1-bit change → ~128-bit change in output.
      • Is preimage-resistant: you cannot recover the QKD bits from the hash.

    Args:
        key_bits: QKD-generated key bits (any length >= 1).

    Returns:
        32-byte AES-256 key (bytes object).
    """
    key_bytes = _bits_to_bytes(key_bits)
    aes_key   = hashlib.sha256(key_bytes).digest()   # Always 32 bytes
    return aes_key


def aes_encrypt(
    message_text: str,
    qkd_key_bits: List[int],
) -> Tuple[bytes, bytes]:
    """
    Encrypt a text message with AES-256-CBC using the QKD key as seed.

    AES-256-CBC is used by:
      • TLS (HTTPS — every secure website)
      • Signal, WhatsApp, iMessage
      • US government classified communications (NSA Suite B)
      • Bitcoin wallet encryption

    The QKD key makes AES quantum-secure: even a quantum computer running
    Grover's algorithm cannot break 256-bit AES in any practical timeframe.

    Mode: CBC (Cipher Block Chaining)
    ----------------------------------
    Each 16-byte plaintext block is XORed with the previous ciphertext block
    before encryption. This means:
      • Identical plaintext blocks produce different ciphertext blocks.
      • A random IV (Initialization Vector) ensures different ciphertexts
        even for the same message encrypted twice.

    Args:
        message_text: Any length plaintext string.
        qkd_key_bits: QKD-generated key bits (any length).

    Returns:
        Tuple (ciphertext_bytes, iv_bytes):
            ciphertext_bytes : Encrypted bytes (PKCS7-padded to block boundary).
            iv_bytes         : 16-byte random IV (needed for decryption — NOT secret).

    Raises:
        ImportError: If the cryptography library is not installed.
    """
    if not AES_AVAILABLE:
        raise ImportError(
            "AES requires the cryptography library.\n"
            "Install it with: pip install cryptography"
        )

    aes_key  = derive_aes_key(qkd_key_bits)
    iv       = os.urandom(16)                          # 16 random bytes = 128-bit IV

    # ── PKCS7 padding (pad message to 16-byte block boundary) ────────────
    raw          = message_text.encode("utf-8")
    pad_length   = 16 - (len(raw) % 16)
    padded       = raw + bytes([pad_length] * pad_length)

    # ── AES-256-CBC encrypt ───────────────────────────────────────────────
    cipher       = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor    = cipher.encryptor()
    ciphertext   = encryptor.update(padded) + encryptor.finalize()

    return ciphertext, iv


def aes_decrypt(
    ciphertext_bytes: bytes,
    iv_bytes:         bytes,
    qkd_key_bits:     List[int],
) -> str:
    """
    Decrypt AES-256-CBC ciphertext using the same QKD key.

    Args:
        ciphertext_bytes: Encrypted bytes from aes_encrypt().
        iv_bytes:         The IV returned by aes_encrypt().
        qkd_key_bits:     The SAME QKD key bits used during encryption.

    Returns:
        Decrypted plaintext string.

    Raises:
        ImportError: If the cryptography library is not installed.
        ValueError:  If decryption or padding removal fails (tampered data).
    """
    if not AES_AVAILABLE:
        raise ImportError("AES requires: pip install cryptography")

    aes_key   = derive_aes_key(qkd_key_bits)
    cipher    = Cipher(algorithms.AES(aes_key), modes.CBC(iv_bytes), backend=default_backend())
    decryptor = cipher.decryptor()
    padded    = decryptor.update(ciphertext_bytes) + decryptor.finalize()

    # ── Remove PKCS7 padding ──────────────────────────────────────────────
    pad_length = padded[-1]
    if pad_length < 1 or pad_length > 16:
        raise ValueError(f"Invalid PKCS7 padding byte: {pad_length}")
    plaintext  = padded[:-pad_length]

    return plaintext.decode("utf-8")


# ══════════════════════════════════════════════════════════════════════════
# METHOD 3 — Simple XOR (no extra libraries required)
# ══════════════════════════════════════════════════════════════════════════

def simple_encrypt(message: str, key_bits: List[int]) -> str:
    """
    Encrypt a message using repeating-key XOR, returned as hex.

    This is a DEMONSTRATION cipher — simpler than OTP but weaker because
    the key repeats if the message is longer than the key in bytes.
    It requires NO extra libraries beyond Python's standard library.

    How it works
    ------------
    1. Pack key_bits into bytes to form a key byte-string.
    2. For each character in the message:
         ciphertext_byte = ord(char) XOR key_byte[i % key_length]
    3. Return the result as a hex string for safe display/storage.

    Args:
        message:  Plaintext string (any length).
        key_bits: QKD key bits. Packed into bytes and used cyclically.

    Returns:
        Hex-encoded ciphertext string.

    Raises:
        ValueError: If message or key_bits is empty.
    """
    if not message:
        raise ValueError("Message cannot be empty.")
    if not key_bits:
        raise ValueError("Key bits cannot be empty.")

    key_bytes  = _bits_to_bytes(key_bits)
    key_len    = len(key_bytes)
    raw_msg    = message.encode("utf-8")

    cipher_bytes = bytes(
        raw_msg[i] ^ key_bytes[i % key_len]
        for i in range(len(raw_msg))
    )
    return cipher_bytes.hex()


def simple_decrypt(ciphertext_hex: str, key_bits: List[int]) -> str:
    """
    Decrypt a simple XOR ciphertext back to the original message.

    XOR decryption is identical to encryption (XOR is its own inverse).

    Args:
        ciphertext_hex: Hex string produced by simple_encrypt().
        key_bits:       The SAME key bits used during encryption.

    Returns:
        Decrypted plaintext string.
    """
    cipher_bytes = bytes.fromhex(ciphertext_hex)
    key_bytes    = _bits_to_bytes(key_bits)
    key_len      = len(key_bytes)

    plain_bytes = bytes(
        cipher_bytes[i] ^ key_bytes[i % key_len]
        for i in range(len(cipher_bytes))
    )
    return plain_bytes.decode("utf-8")


# ══════════════════════════════════════════════════════════════════════════
# Master function — full end-to-end quantum-secure communication
# ══════════════════════════════════════════════════════════════════════════

def run_full_encrypted_communication(
    message:      str,
    num_qubits:   int  = 512,
    eve_present:  bool = False,
    intercept_prob: float = 1.0,
) -> Optional[dict]:
    """
    Run a complete end-to-end quantum-secure communication session.

    Pipeline
    --------
    Phase 1 — QKD         : Alice and Bob establish a shared secret key
                            using the BB84 quantum protocol.
    Phase 2 — Encryption  : Alice encrypts the message with the QKD key.
    Phase 3 — Decryption  : Bob decrypts using the same key.
    Phase 4 — Verification: Confirm the decrypted message matches the original.
    Phase 5 — Summary     : Print a formatted report of the session.

    Encryption method selection
    ---------------------------
    • OTP is used if key_bits >= message_bits (theoretically perfect security).
    • AES-256 is used as fallback (e.g. long messages or short QKD runs).
    • If AES is unavailable, Simple XOR is used as a last resort.

    Args:
        message:        The plaintext message Alice wants to send to Bob.
        num_qubits:     Number of photons in the QKD exchange.
                        More qubits → longer key → stronger OTP coverage.
        eve_present:    If True, Eve intercepts photons → QBER spike → abort.
        intercept_prob: Eve's per-photon interception rate (0.0–1.0).

    Returns:
        A summary dict with keys: status, message, decrypted, qber,
        key_length, encryption_method, ciphertext_hex, matched.
        Returns None if the session was aborted due to eavesdropping.
    """
    _section_banner("QUANTUM-SECURE COMMUNICATION SYSTEM")

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 1 — QKD Key Generation
    # ──────────────────────────────────────────────────────────────────────
    _phase_header(1, "Quantum Key Distribution (BB84 Protocol)")

    print(f"  Qubits requested : {num_qubits}")
    print(f"  Eve present      : {'YES — attack active' if eve_present else 'No'}")
    print(f"  Running BB84 protocol...\n")

    result = run_full_protocol(
        num_qubits     = num_qubits,
        eve_present    = eve_present,
        intercept_prob = intercept_prob,
    )

    qber   = result["qber"]
    status = result["status"]

    if status == "ABORTED":
        print(f"\n{_RED}{_BOLD}  ❌ QKD ABORTED — Eavesdropper detected!{_RESET}")
        print(f"  QBER = {qber:.2%}  (threshold = 11.00%)")
        print(f"  The quantum channel was compromised.")
        print(f"  Message NOT encrypted — no insecure key will be used.")
        _summary_box(
            message        = message,
            encryption     = "N/A",
            ciphertext_hex = "N/A",
            key_length     = 0,
            qber           = qber,
            eve_present    = eve_present,
            decrypted      = "N/A",
            matched        = False,
            status         = "ABORTED — Eavesdropper Detected",
        )
        return None

    key         = result["final_key"]
    key_length  = len(key)
    key_preview = "".join(map(str, key[:32]))

    print(f"  {_GREEN}✓ QKD key generated successfully{_RESET}")
    print(f"  Key length (bits): {key_length}")
    print(f"  Key (first 32b)  : {_YELLOW}{key_preview}{'...' if key_length > 32 else ''}{_RESET}")

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 2 — Encryption
    # ──────────────────────────────────────────────────────────────────────
    _phase_header(2, "Message Encryption (Alice's side)")

    if not message:
        print(f"  {_RED}Error: Cannot encrypt an empty message.{_RESET}")
        return None

    message_bits_needed = len(message.encode("utf-8")) * 8
    print(f"  Message          : {repr(message)}")
    print(f"  Message length   : {len(message)} chars  →  {message_bits_needed} bits needed")
    print(f"  Key available    : {key_length} bits")

    ciphertext_hex    = ""
    ciphertext_bits   = []
    encryption_method = ""
    iv_bytes: Optional[bytes] = None

    # ── Choose encryption method ──────────────────────────────────────────
    if key_length >= message_bits_needed:
        # OTP: theoretically perfect security
        encryption_method = "One-Time Pad (OTP)"
        print(f"\n  {_GREEN}Key is long enough for One-Time Pad — using perfect secrecy!{_RESET}")

        try:
            ciphertext_bits, used_key = otp_encrypt(message, key)
            ciphertext_hex = _bits_to_hex(ciphertext_bits)

            print(f"\n  Ciphertext bits : {''.join(map(str, ciphertext_bits[:32]))}"
                  f"{'...' if len(ciphertext_bits) > 32 else ''}")
            print(f"  Ciphertext hex  : {_YELLOW}{ciphertext_hex[:40]}"
                  f"{'...' if len(ciphertext_hex) > 40 else ''}{_RESET}")

        except ValueError as exc:
            print(f"  {_RED}OTP error: {exc}{_RESET}")
            return None

    elif AES_AVAILABLE:
        # AES-256: industry-standard fallback
        encryption_method = "AES-256-CBC"
        print(f"\n  {_YELLOW}Key shorter than message — using AES-256-CBC (industry standard){_RESET}")
        print(f"  QKD key hashed with SHA-256 → 256-bit AES key")

        try:
            ciphertext_bytes, iv_bytes = aes_encrypt(message, key)
            ciphertext_hex = ciphertext_bytes.hex()

            print(f"\n  IV (hex)        : {iv_bytes.hex()}")
            print(f"  Ciphertext hex  : {_YELLOW}{ciphertext_hex[:40]}"
                  f"{'...' if len(ciphertext_hex) > 40 else ''}{_RESET}")

        except Exception as exc:
            print(f"  {_RED}AES error: {exc}{_RESET}")
            return None

    else:
        # Simple XOR: last resort (no extra libraries)
        encryption_method = "Simple XOR (repeating key)"
        print(f"\n  {_YELLOW}Using Simple XOR (no external libraries required){_RESET}")

        try:
            ciphertext_hex = simple_encrypt(message, key)
            print(f"  Ciphertext hex  : {_YELLOW}{ciphertext_hex[:40]}"
                  f"{'...' if len(ciphertext_hex) > 40 else ''}{_RESET}")
        except ValueError as exc:
            print(f"  {_RED}Simple XOR error: {exc}{_RESET}")
            return None

    print(f"\n  {_GREEN}✓ Encryption complete using {encryption_method}{_RESET}")

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 3 — Decryption (Bob's side)
    # ──────────────────────────────────────────────────────────────────────
    _phase_header(3, "Message Decryption (Bob's side)")
    print(f"  Bob uses the SAME QKD key to reverse the encryption...")

    decrypted = ""
    try:
        if encryption_method == "One-Time Pad (OTP)":
            decrypted = otp_decrypt(ciphertext_bits, key)
        elif encryption_method == "AES-256-CBC":
            decrypted = aes_decrypt(
                bytes.fromhex(ciphertext_hex), iv_bytes, key
            )
        else:   # Simple XOR
            decrypted = simple_decrypt(ciphertext_hex, key)
    except Exception as exc:
        print(f"  {_RED}Decryption error: {exc}{_RESET}")
        decrypted = ""

    print(f"  Ciphertext received : {ciphertext_hex[:40]}"
          f"{'...' if len(ciphertext_hex) > 40 else ''}")
    print(f"  Decrypted message   : {_GREEN}{repr(decrypted)}{_RESET}")

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 4 — Verification
    # ──────────────────────────────────────────────────────────────────────
    _phase_header(4, "Verification")

    matched = (decrypted == message)

    if matched:
        print(f"  {_GREEN}{_BOLD}✅ PERFECT MATCH — Decrypted message equals original!{_RESET}")
    else:
        print(f"  {_RED}{_BOLD}❌ MISMATCH — Decryption produced wrong output!{_RESET}")
        print(f"  Expected : {repr(message)}")
        print(f"  Got      : {repr(decrypted)}")

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 5 — Summary
    # ──────────────────────────────────────────────────────────────────────
    session_status = "✅ UNCONDITIONALLY SECURE" if matched else "❌ ERROR"
    _summary_box(
        message        = message,
        encryption     = encryption_method,
        ciphertext_hex = ciphertext_hex,
        key_length     = key_length,
        qber           = qber,
        eve_present    = eve_present,
        decrypted      = decrypted,
        matched        = matched,
        status         = session_status,
    )

    return {
        "status":             session_status,
        "message":            message,
        "decrypted":          decrypted,
        "qber":               qber,
        "key_length":         key_length,
        "encryption_method":  encryption_method,
        "ciphertext_hex":     ciphertext_hex,
        "matched":            matched,
    }


# ══════════════════════════════════════════════════════════════════════════
# Pretty-print helpers
# ══════════════════════════════════════════════════════════════════════════

def _section_banner(title: str) -> None:
    """Print a full-width section banner."""
    w = 62
    print(f"\n{_BOLD}{'╔' + '═' * w + '╗'}")
    print(f"║ {title:^{w}} ║")
    print(f"{'╚' + '═' * w + '╝'}{_RESET}\n")


def _phase_header(num: int, title: str) -> None:
    """Print a numbered phase header."""
    print(f"\n{_CYAN}{_BOLD}── PHASE {num}: {title} ──{_RESET}\n")


def _summary_box(
    message:        str,
    encryption:     str,
    ciphertext_hex: str,
    key_length:     int,
    qber:           float,
    eve_present:    bool,
    decrypted:      str,
    matched:        bool,
    status:         str,
) -> None:
    """
    Print the final session summary in a formatted box.

    Shows all protocol parameters and outcomes at a glance — designed
    to be legible for a non-technical audience.
    """
    _phase_header(5, "Session Summary")

    msg_bytes    = len(message.encode("utf-8"))
    msg_bits     = msg_bytes * 8
    cipher_short = (ciphertext_hex[:32] + "...") if len(ciphertext_hex) > 32 else ciphertext_hex
    match_icon   = f"{_GREEN}✅ PERFECT MATCH{_RESET}" if matched else f"{_RED}❌ MISMATCH{_RESET}"
    eve_str      = "Yes ⚠️" if eve_present else "No"
    qber_str     = f"{qber:.2%}"

    # Determine security label
    if not matched or "ABORTED" in status:
        sec_label = f"{_RED}NOT ESTABLISHED{_RESET}"
    elif encryption == "One-Time Pad (OTP)":
        sec_label = f"{_GREEN}UNCONDITIONALLY SECURE (OTP){_RESET}"
    elif "AES" in encryption:
        sec_label = f"{_GREEN}COMPUTATIONALLY SECURE (AES-256){_RESET}"
    else:
        sec_label = f"{_YELLOW}DEMONSTRATION LEVEL (Simple XOR){_RESET}"

    W = 56   # inner width between box edges

    def _row(label: str, value: str) -> None:
        """Print one row of the summary table."""
        # Strip ANSI codes for width calculation
        import re
        clean = re.sub(r'\033\[[0-9;]*m', '', value)
        padding = max(0, W - 2 - len(label) - len(clean))
        print(f"║ {_BOLD}{label}{_RESET} {value}{' ' * padding} ║")

    print(f"{'╔' + '═' * (W + 2) + '╗'}")
    title = "QUANTUM-SECURE COMMUNICATION SUMMARY"
    print(f"║ {_BOLD}{title:^{W}}{_RESET} ║")
    print(f"{'╠' + '═' * (W + 2) + '╣'}")

    _row("Original message  :", f"{repr(message[:30]) + ('...' if len(message) > 30 else repr(message)[len(repr(message[:30]))-1:])!s}")
    _row("Message length    :", f"{len(message)} char{'s' if len(message) != 1 else ''}  ({msg_bits} bits)")
    _row("QKD key length    :", f"{key_length} bits")
    _row("Encryption method :", encryption)
    _row("Ciphertext (hex)  :", cipher_short)
    _row("Eve present       :", eve_str)
    _row("QBER measured     :", qber_str)
    _row("Security level    :", sec_label)
    _row("Decryption result :", match_icon)

    print(f"{'╠' + '═' * (W + 2) + '╣'}")

    # Status line (centred)
    clean_status = status.replace("✅ ", "").replace("❌ ", "")
    colour = _GREEN if matched and "ABORTED" not in status else _RED
    status_display = f"{colour}{_BOLD}{status}{_RESET}"
    clean_len = len(clean_status) + 4   # approximate visible length
    pad = max(0, W - clean_len) // 2
    print(f"║{' ' * (pad + 1)}{status_display}{' ' * max(0, W - clean_len - pad + 1)} ║")

    print(f"{'╚' + '═' * (W + 2) + '╝'}\n")


# ══════════════════════════════════════════════════════════════════════════
# Standalone test suite
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    import textwrap

    def _test_header(n: int, title: str) -> None:
        print(f"\n{'='*64}")
        print(f"  TEST {n}: {title}")
        print(f"{'='*64}")

    # ── TEST 1: Normal secure communication ───────────────────────────────
    _test_header(1, "Normal communication — no eavesdropper (OTP)")
    run_full_encrypted_communication(
        message      = "Hello Bob! This message is quantum-secured.",
        num_qubits   = 512,
        eve_present  = False,
    )

    # ── TEST 2: Eve intercepts — protocol aborts ──────────────────────────
    _test_header(2, "Eve intercepts 100% of photons — protocol should ABORT")
    run_full_encrypted_communication(
        message        = "Top secret: launch code 4729",
        num_qubits     = 512,
        eve_present    = True,
        intercept_prob = 1.0,
    )

    # ── TEST 3: Various message lengths ───────────────────────────────────
    _test_header(3, "Different message lengths")
    messages = [
        "Hi",
        "Secret!",
        "Quantum cryptography is the future of security!",
    ]
    for msg in messages:
        bits_needed = len(msg.encode()) * 8
        print(f"\n  → '{msg}'  ({len(msg)} chars, {bits_needed} bits needed)")
        run_full_encrypted_communication(
            message     = msg,
            num_qubits  = 1024,
            eve_present = False,
        )

    # ── TEST 4: Unicode message ────────────────────────────────────────────
    _test_header(4, "Unicode characters (emoji + non-ASCII)")
    run_full_encrypted_communication(
        message     = "Quantum is safe! 🔐 मेरा संदेश सुरक्षित है",
        num_qubits  = 2048,
        eve_present = False,
    )

    # ── TEST 5: AES fallback (very long message) ───────────────────────────
    _test_header(5, "Long message — AES-256 fallback when key too short")
    long_msg = (
        "This is a very long message that demonstrates AES-256 encryption. "
        "When the QKD key is shorter than the message in bits, we automatically "
        "switch from the One-Time Pad to AES-256-CBC, which uses the QKD key "
        "as a cryptographic seed via SHA-256 hashing. AES-256 is used by banks, "
        "governments, and every HTTPS connection on the internet. "
        "Combined with a QKD-derived key, it provides quantum-resistant security."
    )
    run_full_encrypted_communication(
        message     = long_msg,
        num_qubits  = 256,     # intentionally short → forces AES fallback
        eve_present = False,
    )

    # ── TEST 6: Partial Eve attack ─────────────────────────────────────────
    _test_header(6, "Partial Eve attack (50% interception) — may be detected")
    run_full_encrypted_communication(
        message        = "Can Eve stay hidden?",
        num_qubits     = 512,
        eve_present    = True,
        intercept_prob = 0.5,
    )

    print(f"\n{'='*64}")
    print(f"  All encryption.py tests complete.")
    print(f"{'='*64}\n")
