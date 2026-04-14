# BB84 Quantum Key Distribution Simulation
## DTI Project — Secure Communication Channel with Eavesdropper Detection

### Project Overview
This project simulates the BB84 Quantum Key Distribution (QKD) protocol, a fundamental quantum cryptographic system that enables two parties to securely generate a shared secret key. The simulation models quantum state encoding, transmission interference, and classical post-processing tasks like basis sifting and error checking. Crucially, it demonstrates how eavesdropping attempts irreparably disturb quantum states, allowing immediate detection through Quantum Bit Error Rate (QBER) analysis.

### How to Run
```bash
pip install -r requirements.txt
python main.py           # Full simulation (all 5 scenarios)
python main.py --quick   # Quick demo (2 scenarios)
python visualize.py      # Generate all graphs
```

### Project Structure
- `alice.py`: Represents the sender; generates random bits and encodes them into photon polarization states.
- `bob.py`: Represents the receiver; randomly measures incoming photons and extracts the sifted key.
- `eve.py`: Implements an intercept-and-resend attack across the quantum channel.
- `qber.py`: Calculates the Quantum Bit Error Rate and handles eavesdropper detection logic.
- `main.py`: The interactive master runner that coordinates full protocol scenarios and outputs summaries.
- `visualize.py`: Generates publication-quality charts to visually analyze QBER and key lengths under various attack intensities.
- `test_all.py`: Contains the unit testing suite for all simulation modules.
- `verify_project.py`: Runs an automated health-check report to verify simulation integrity and files.

### Expected Results
| Scenario | QBER | Result |
|---|---|---|
| No Eve | ~1-3% | ✅ Key Generated |
| Full Eve | ~25% | ❌ Aborted |

### Theory
The BB84 protocol leverages quantum mechanical principles, specifically the no-cloning theorem and wave-function collapse, to secure communications. Alice sends information encoded in non-orthogonal bases, compelling any eavesdropper (Eve) to guess the measurement basis. Because an incorrect guess alters the photon's state, Eve's actions introduce unavoidable errors at the receiver's end. The system monitors the Quantum Bit Error Rate (QBER); if it exceeds the theoretical threshold of 11%, eavesdropping is detected and the key is safely discarded before use.


To run in GUI

<!-- (qkd_env) (base) abhinikesh@Abhinikeshs-MacBook-Air Secure_Quantum_Communication_System % /Users/abhinikesh/Documents/Secure_Quantum_Communication_System/qkd_env/bin/python gui.py -->

/Users/abhinikesh/Documents/Secure_Quantum_Communication_System/qkd_env/bin/python gui.py