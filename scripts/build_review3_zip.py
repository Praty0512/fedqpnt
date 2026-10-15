"""Build the Review-3 Google-Drive zip straight from the repository (no intermediate copy).

Layout inside the zip:
  FedQPNT_Review3/README_FIRST.md, report + overview PDFs
  FedQPNT_Review3/code/      tracked files at HEAD (git archive), minus the unfiled patent draft,
                             the superseded rounds (results/m4, results/m4r2) and review3/
  FedQPNT_Review3/dataset/   README (download source of the third-party raw data) + derived calibration files

Usage: python scripts/build_review3_zip.py
"""
import io
import subprocess
import tarfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "review3" / "FedQPNT_Review3_DriveUpload.zip"
TOP = "FedQPNT_Review3"
EXCLUDE_PREFIX = ("patent/", "results/m4/", "results/m4r2/", "review3/", "docs/specs/raw/progress/PATENT")
PATENT_SECTION_FILE = "docs/specs/raw/TRUST_SPLIT_DESIGN.md"


def strip_patent_section(text: str) -> str:
    a = text.find("## 6. Patent impact")
    if a == -1:
        return text
    b = text.find("\n## ", a + 5)
    return text[:a] + (text[b + 1:] if b != -1 else "")


def main() -> None:
    tar_bytes = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=REPO,
                               capture_output=True, check=True).stdout
    n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
            for m in tar:
                if not m.isfile() or m.name.startswith(EXCLUDE_PREFIX):
                    continue
                data = tar.extractfile(m).read()
                if m.name == PATENT_SECTION_FILE:
                    data = strip_patent_section(data.decode("utf-8")).encode("utf-8")
                z.writestr(f"{TOP}/code/{m.name}", data)
                n += 1
        for name in ("README_FIRST.md", "FedQPNT_Review3_Report.pdf", "FedQPNT_Overview_Novelty_Plain_Summary.pdf"):
            z.write(REPO / "review3" / name, f"{TOP}/{name}")
        z.write(REPO / "review3" / "DATASET.md", f"{TOP}/dataset/README.md")
        for d, sub in ((REPO / "data" / "processed" / "jarlaud2024", "processed_jarlaud2024"),
                       (REPO / "results" / "data", "results_data")):
            for f in sorted(d.rglob("*")):
                if f.is_file():
                    z.write(f, f"{TOP}/dataset/derived/{sub}/{f.relative_to(d).as_posix()}")
    print(f"{OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {n} code files)")


if __name__ == "__main__":
    main()
