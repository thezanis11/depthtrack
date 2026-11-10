"""Download only the four named official TUM archives, with bounded extraction."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

SEQUENCES = {"xyz": 448204271, "rpy": 410268381, "desk": 344011403, "floor": 734599281}
BASE = "https://webshare.cvg.cit.tum.de/g/rgbd/dataset/freiburg1/"
ROOT = Path(__file__).resolve().parent.parent


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_members(archive, expected_root):
    total = 0
    for member in archive:
        path = Path(member.name)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != expected_root:
            raise ValueError("Unsafe archive path")
        if not (member.isfile() or member.isdir()) or member.issym() or member.islnk():
            raise ValueError("Unsupported archive member")
        total += member.size
        if total > 3_000_000_000 or member.size > 20_000_000:
            raise ValueError("Archive exceeds extraction budget")
        yield member


def download(sequence):
    name = f"rgbd_dataset_freiburg1_{sequence}"
    archive_dir = ROOT / "data" / "archives"
    raw_dir = ROOT / "data" / "raw"
    archive_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive = archive_dir / f"{name}.tgz"
    provenance = ROOT / "docs" / "DATASET_MANIFEST.json"
    records = json.loads(provenance.read_text()) if provenance.exists() else {}
    expected_hash = records.get(sequence, {}).get("archive_sha256")
    url = BASE + archive.name
    start = time.perf_counter()
    if not archive.exists():
        if shutil.disk_usage(ROOT).free < 3_500_000_000:
            raise RuntimeError("Need at least 3.5 GB free before another archive")
        partial = archive.with_suffix(".partial")
        request = Request(url, headers={"User-Agent": "DepthTrack-reproducible-research/0.1"})
        with urlopen(request, timeout=60) as response, partial.open("wb") as output:
            total = 0
            announced = int(response.headers.get("Content-Length", SEQUENCES[sequence]))
            if announced != SEQUENCES[sequence]:
                raise ValueError("Official archive size changed; inspect before proceeding")
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                total += len(chunk)
                if total > announced:
                    raise ValueError("Unexpected download size")
        if partial.stat().st_size != SEQUENCES[sequence]:
            raise ValueError("Truncated download")
        partial.replace(archive)
    checksum = sha256(archive)
    if expected_hash and checksum != expected_hash:
        raise ValueError("Archive differs from pinned initial acquisition SHA-256")
    if archive.stat().st_size != SEQUENCES[sequence]:
        raise ValueError("Archive size mismatch")
    extracted = raw_dir / name
    marker = extracted / ".depthtrack-complete"
    if not marker.exists():
        print(f"Extracting {sequence} after checksum verification", flush=True)
        with tarfile.open(archive, "r:gz") as source:
            for member in safe_members(source, name):
                if shutil.disk_usage(ROOT).free < 2_000_000_000:
                    raise RuntimeError("Stopped extraction to preserve 2 GB free disk")
                source.extract(member, path=raw_dir, filter="data")
        marker.write_text(checksum, encoding="ascii")
    elif marker.read_text() != checksum:
        raise ValueError("Extraction marker disagrees with archive")
    record = dict(url=url, archive_bytes=archive.stat().st_size, archive_sha256=checksum,
        checksum_origin="SHA-256 measured on initial HTTPS acquisition, not a publisher-signed checksum",
        license="CC-BY-4.0", attribution="Sturm et al., A Benchmark for the Evaluation of RGB-D SLAM Systems, IROS 2012",
        acquired_utc=records.get(sequence, {}).get("acquired_utc", datetime.now(timezone.utc).isoformat()),
        extracted_files=sum(1 for p in extracted.rglob("*") if p.is_file()),
        extracted_bytes=sum(p.stat().st_size for p in extracted.rglob("*") if p.is_file()),
        index_sha256={f:sha256(extracted/f) for f in ("rgb.txt","depth.txt","groundtruth.txt")})
    records[sequence] = record
    provenance.parent.mkdir(exist_ok=True)
    provenance.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{sequence}: {archive.stat().st_size / 1e6:.1f} MB archive, "
          f"{record['extracted_files']} files, {time.perf_counter()-start:.1f}s, "
          f"{shutil.disk_usage(ROOT).free/1e9:.2f} GB free", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sequences", nargs="+", choices=SEQUENCES, default=list(SEQUENCES))
    for sequence in parser.parse_args().sequences:
        download(sequence)
