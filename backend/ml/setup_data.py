"""
Data setup script — run this once after cloning to put the training data
in the right place before using the ML notebook.

Place the following files in the same directory as this script before running:
  - student_labels.csv
  - CVs/  (folder containing cv_0001.txt … cv_0200.txt)

Usage:
    cd backend/ml
    python setup_data.py
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA_RAW = HERE.parent.parent / "data" / "raw"

EXPECTED = {
    "labels": HERE / "student_labels.csv",
    "cvs": HERE / "CVs",
}


def check_source():
    missing = []
    if not EXPECTED["labels"].exists():
        missing.append("student_labels.csv  (place next to this script)")
    if not EXPECTED["cvs"].exists() or not list(EXPECTED["cvs"].glob("*.txt")):
        missing.append("CVs/  (folder with cv_0001.txt … cv_0200.txt, place next to this script)")
    if missing:
        print("Missing files:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)


def main():
    check_source()

    DATA_RAW.mkdir(parents=True, exist_ok=True)
    dest_labels = DATA_RAW / "student_labels.csv"
    dest_cvs = DATA_RAW / "CVs"

    shutil.copy2(EXPECTED["labels"], dest_labels)
    print(f"Copied student_labels.csv → {dest_labels}")

    if dest_cvs.exists():
        shutil.rmtree(dest_cvs)
    shutil.copytree(EXPECTED["cvs"], dest_cvs)
    count = len(list(dest_cvs.glob("*.txt")))
    print(f"Copied {count} CV files → {dest_cvs}")

    print("\nDone. You can now open backend/ml/cv_screening_ml.ipynb and run all cells.")


if __name__ == "__main__":
    main()
