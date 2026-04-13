import os
import sys

def check_file(filename):
    exists = os.path.isfile(filename)
    icon = "✅" if exists else "❌"
    return exists, f"{icon} Found" if exists else f"{icon} Missing"

def run_project_verification():
    files_to_check = [
        "alice.py",
        "bob.py",
        "eve.py",
        "qber.py",
        "main.py",
        "visualize.py"
    ]
    
    report = []
    all_good = True

    # Check files & imports
    for file in files_to_check:
        exists, status = check_file(file)
        if not exists:
            all_good = False
            report.append((file, status))
            continue
            
        if file.endswith(".py") and file not in ("main.py", "visualize.py"):
            module_name = file.replace(".py", "")
            try:
                __import__(module_name)
                report.append((file, "✅ Found & Importable"))
            except Exception as e:
                all_good = False
                report.append((file, f"❌ Found but error: {e}"))
        else:
             report.append((file, "✅ Found"))

    # Test QBER Protocol No Eve
    import qber
    res_no_eve = qber.run_full_protocol(256, eve_present=False)
    if res_no_eve['status'] == "KEY GENERATED":
        report.append(("No-Eve Test", "✅ Key Generated"))
    else:
        all_good = False
        report.append(("No-Eve Test", "❌ Failed"))

    # Test QBER Protocol With Eve
    res_eve = qber.run_full_protocol(256, eve_present=True, intercept_prob=1.0)
    if res_eve['status'] == "ABORTED":
        report.append(("Eve Test", "✅ Eavesdropper Found"))
    else:
        all_good = False
        report.append(("Eve Test", "❌ Failed to detect Eve"))

    import visualize
    if os.path.exists("results"):
        report.append(("Results Folder", "✅ Exists"))
    else:
        all_good = False
        report.append(("Results Folder", "❌ Missing"))

    # Print the report
    print()
    print("╔" + "═" * 39 + "╗")
    print("║" + "PROJECT VERIFICATION REPORT".center(39) + "║")
    print("╠" + "═" * 39 + "╣")
    for item, status in report:
        line = f"║ {item:<15} {status:<21} ║"
        print(line)
    
    print("╠" + "═" * 39 + "╣")
    final_status = "✅ READY TO SUBMIT" if all_good else "❌ ISSUES FOUND"
    print(f"║ PROJECT STATUS: {final_status:<22}║")
    print("╚" + "═" * 39 + "╝")
    print()

if __name__ == "__main__":
    # Ensure stdout is fine
    run_project_verification()
