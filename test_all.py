import unittest
from alice import Alice
from bob import Bob
from eve import Eve
import qber as QBER

class TestAlice(unittest.TestCase):
    def setUp(self):
        self.num_qubits = 100
        self.alice = Alice(self.num_qubits)

    def test_bit_generation(self):
        bits = self.alice.generate_bits()
        self.assertTrue(all(b in (0, 1) for b in bits))
        self.assertEqual(len(bits), self.num_qubits)

    def test_base_generation(self):
        bases = self.alice.generate_bases()
        self.assertTrue(all(b in (0, 1) for b in bases))
        self.assertEqual(len(bases), self.num_qubits)

    def test_photon_encoding(self):
        self.alice.generate_bits()
        self.alice.generate_bases()
        states = self.alice.encode_photons()
        self.assertTrue(all(s in (0, 1, 2, 3) for s in states))

    def test_photon_count(self):
        self.alice.generate_bits()
        self.alice.generate_bases()
        states = self.alice.encode_photons()
        self.assertEqual(len(states), self.num_qubits)


class TestBob(unittest.TestCase):
    def test_measurement_without_eve(self):
        # Without Eve, at matching-basis positions, Bob's measurement MUST equal Alice's bit
        num_qubits = 1000
        alice = Alice(num_qubits)
        alice.generate_bits()
        alice.generate_bases()
        alice.encode_photons()

        bob = Bob(num_qubits)
        bob.generate_bases()
        bob.measure_photons(alice.photon_states)

        matching_indices, bob_sifted = bob.sift_key(alice.bases, bob.bases)
        alice_sifted = alice.get_sifted_key(matching_indices)

        # Assert zero errors at matching positions
        self.assertEqual(alice_sifted, bob_sifted)

    def test_sifting_reduces_key(self):
        num_qubits = 500
        alice = Alice(num_qubits)
        alice.generate_bits()
        alice.generate_bases()
        alice.encode_photons()

        bob = Bob(num_qubits)
        bob.generate_bases()
        bob.measure_photons(alice.photon_states)

        matching_indices, _ = bob.sift_key(alice.bases, bob.bases)
        # Should be approximately 50%, let's allow a wide 35%-65% margin
        self.assertTrue(0.35 * num_qubits < len(matching_indices) < 0.65 * num_qubits)

    def test_measurement_range(self):
        num_qubits = 10
        alice = Alice(num_qubits)
        alice.generate_bits()
        alice.generate_bases()
        alice.encode_photons()

        bob = Bob(num_qubits)
        bob.generate_bases()
        measurements = bob.measure_photons(alice.photon_states)
        self.assertTrue(all(m in (0, 1) for m in measurements))


class TestEve(unittest.TestCase):
    def test_full_interception(self):
        num_qubits = 100
        alice = Alice(num_qubits)
        alice.generate_bits()
        alice.generate_bases()
        alice.encode_photons()

        eve = Eve(intercept_probability=1.0)
        eve.intercept(alice.photon_states)
        stats = eve.get_statistics()
        self.assertEqual(stats['intercepted_count'], num_qubits)

    def test_no_interception(self):
        num_qubits = 100
        alice = Alice(num_qubits)
        alice.generate_bits()
        alice.generate_bases()
        alice.encode_photons()

        eve = Eve(intercept_probability=0.0)
        eve.intercept(alice.photon_states)
        stats = eve.get_statistics()
        self.assertEqual(stats['intercepted_count'], 0)

    def test_qber_with_eve(self):
        num_qubits = 100
        alice = Alice(num_qubits)
        alice.generate_bits()
        alice.generate_bases()
        alice.encode_photons()

        eve = Eve(intercept_probability=1.0)
        modified_photons = eve.intercept(alice.photon_states)

        bob = Bob(num_qubits)
        bob.generate_bases()
        bob.measure_photons(modified_photons)

        matching_indices, bob_sifted = bob.sift_key(alice.bases, bob.bases)
        alice_sifted = alice.get_sifted_key(matching_indices)

        errors = sum(a != b for a, b in zip(alice_sifted, bob_sifted))
        qber_val = errors / len(alice_sifted) if alice_sifted else 0.0

        # Should be between 10% and 40% with full eavesdropping
        self.assertTrue(0.10 <= qber_val <= 0.40)

    def test_qber_without_eve(self):
        num_qubits = 100
        alice = Alice(num_qubits)
        alice.generate_bits()
        alice.generate_bases()
        alice.encode_photons()

        bob = Bob(num_qubits)
        bob.generate_bases()
        bob.measure_photons(alice.photon_states)

        matching_indices, bob_sifted = bob.sift_key(alice.bases, bob.bases)
        alice_sifted = alice.get_sifted_key(matching_indices)

        errors = sum(a != b for a, b in zip(alice_sifted, bob_sifted))
        qber_val = errors / len(alice_sifted) if alice_sifted else 0.0

        self.assertLess(qber_val, 0.10)


class TestQBER(unittest.TestCase):
    def test_threshold_detection(self):
        detected, _ = QBER.detect_eavesdropper(0.05, threshold=0.11)
        self.assertFalse(detected)

        detected, _ = QBER.detect_eavesdropper(0.20, threshold=0.11)
        self.assertTrue(detected)

    def test_qber_range(self):
        # Manually testing the QBER calculation with contrived keys
        alice_key = [1, 0, 1, 0, 1, 0]
        bob_key = [1, 0, 0, 0, 1, 1] # 2 errors out of 6
        qber_val, _, mismatches = QBER.calculate_qber(list(alice_key), list(bob_key), sample_size=6)
        
        self.assertTrue(0.0 <= qber_val <= 1.0)
        self.assertEqual(mismatches, 2)

    def test_privacy_amplification(self):
        key = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1]
        
        # At 0 QBER it should remain identical or hash completely
        amp_key_0 = QBER.privacy_amplification(key, 0.0)
        self.assertEqual(len(amp_key_0), len(key))

        # At small error it should be shorter
        amp_key_error = QBER.privacy_amplification(key, 0.05)
        self.assertLess(len(amp_key_error), len(key))


class TestIntegration(unittest.TestCase):
    def test_full_protocol_no_eve(self):
        result = QBER.run_full_protocol(100, eve_present=False)
        self.assertEqual(result['status'], "KEY GENERATED")

    def test_full_protocol_with_eve(self):
        result = QBER.run_full_protocol(100, eve_present=True, intercept_prob=1.0)
        self.assertEqual(result['status'], "ABORTED")

    def test_multiple_qubit_sizes(self):
        for size in [64, 128, 256, 512]:
            result = QBER.run_full_protocol(size, eve_present=False)
            self.assertEqual(result['status'], "KEY GENERATED")


if __name__ == "__main__":
    print("Running BB84 QKD Simulation Tests...")
    unittest.main(verbosity=2)
