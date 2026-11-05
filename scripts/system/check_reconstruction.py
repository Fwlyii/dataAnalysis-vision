"""Check the reconstructed research delivery without modifying any files.

Run with ``python3 scripts/system/check_reconstruction.py`` from any directory.
Only Python's standard library is used. A hydrated unified-records LFS payload
is accepted only when HEAD still contains the protected pointer and its SHA-256
OID and size both match that payload.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path


ROOT = next(p for p in Path(__file__).resolve().parents if (p / "project.json").is_file())
APP = ROOT / "app"
TOPICS = {"budget", "scale", "concise", "limits", "language", "position", "feedback"}
GENERAL = {"budget", "scale", "concise", "limits"}
EXPERIMENTS = {
    "reasoning": 74400,
    "document_qa": 74800,
    "code_generation": 90210,
    "document_positions": 3600,
    "code_repair": 5576,
}
UNIFIED = "data/processed/all_records.csv.gz"
SVG = "{http://www.w3.org/2000/svg}"


class Checks:
    def __init__(self):
        self.errors = []
        self.hashes = {}
        self.counts = {}

    def require(self, condition, message):
        if not condition:
            self.errors.append(message)
        return bool(condition)

    def digest(self, path):
        path = Path(path)
        if path not in self.hashes:
            h = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    h.update(chunk)
            self.hashes[path] = h.hexdigest()
        return self.hashes[path]

    def local_file(self, relative, base=ROOT):
        path = (base / relative).resolve()
        if not self.require(path.is_relative_to(ROOT), f"Resource escapes repository: {relative}"):
            return None
        return path if self.require(path.is_file(), f"Missing resource: {relative}") else None

    def json_file(self, relative):
        path = self.local_file(relative)
        if path:
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def source_file(self, reference):
        """Catalog permits a bare basename in a composite source citation."""
        path = ROOT / reference
        if path.is_file():
            return self.local_file(reference)
        if Path(reference).name == reference:
            candidates = [p for folder in ("reports", "data", "scripts", "app")
                          for p in (ROOT / folder).rglob(reference) if p.is_file()]
            if len(candidates) == 1:
                return candidates[0]
        self.require(False, f"Missing or ambiguous source: {reference}")
        return None

    def atlas(self):
        catalog = self.json_file("app/data/research-charts.json")
        if catalog is None:
            return
        charts = catalog.get("charts", [])
        self.require(len(charts) == catalog.get("chart_count") == 37, "Catalog must contain exactly 37 charts")
        self.require(len(catalog.get("topics", [])) == 7 and set(catalog.get("topics", [])) == TOPICS,
                     "Catalog must declare the seven research topics")
        ids = [chart.get("id") for chart in charts]
        self.require(len(set(ids)) == len(ids), "Duplicate chart IDs")
        self.require({chart.get("topic") for chart in charts} == TOPICS, "Chart coverage must include all seven topics")
        files, sources, valid_svgs = {}, set(), 0
        for chart in charts:
            label = chart.get("id", "<missing ID>")
            self.require(bool(label) and bool(chart.get("title")), f"Missing chart ID/title: {label}")
            values = chart.get("data")
            self.require(isinstance(values, list) and bool(values) and all(isinstance(v, dict) and v for v in values),
                         f"Missing chart data: {label}")
            source = chart.get("source")
            if self.require(isinstance(source, str) and bool(source.strip()), f"Missing chart source: {label}"):
                for citation in source.split(";"):
                    resolved = self.source_file(citation.strip())
                    if resolved:
                        sources.add(resolved)
            relative = chart.get("file", "")
            path = self.local_file(relative, APP)
            if not path:
                continue
            self.require(path.suffix == ".svg", f"Chart is not SVG: {label}")
            try:
                element = ET.parse(path).getroot()
                self.require(element.tag == SVG + "svg", f"Invalid SVG root: {label}")
                for tag in ("title", "desc"):
                    nodes = element.findall(SVG + tag)
                    self.require(any("".join(node.itertext()).strip() for node in nodes),
                                 f"Missing accessible SVG {tag}: {label}")
                valid_svgs += 1
            except ET.ParseError as error:
                self.require(False, f"Malformed SVG {label}: {error}")
            files[label] = path
        self.counts.update(charts=len(charts), topics=len(TOPICS), svg=valid_svgs, sources=len(sources))
        archive_path = self.local_file("app/assets/research-svg.zip")
        if archive_path is None:
            return
        with zipfile.ZipFile(archive_path) as archive:
            self.require(archive.testzip() is None, "ZIP CRC check failed")
            names = archive.namelist()
            self.require(len(names) == len(set(names)), "ZIP contains duplicate names")
            svg_names = {name for name in names if name.endswith(".svg")}
            csv_names = {name for name in names if name.endswith(".csv")}
            self.require(svg_names == {Path(chart.get("file", "")).name for chart in charts},
                         "ZIP SVG set differs from catalog")
            self.require(csv_names == {str(chart.get("id")) + ".csv" for chart in charts},
                         "ZIP CSV set differs from catalog")
            for chart in charts:
                label = chart.get("id")
                if label in files and files[label].name in svg_names:
                    self.require(archive.read(files[label].name) == files[label].read_bytes(),
                                 f"ZIP SVG differs from delivered SVG: {label}")
                csv_name = str(label) + ".csv"
                values = chart.get("data") or []
                if csv_name in csv_names and values:
                    buffer = io.StringIO(newline="")
                    writer = csv.DictWriter(buffer, fieldnames=list(values[0]))
                    writer.writeheader()
                    writer.writerows(values)
                    expected = list(csv.DictReader(io.StringIO(buffer.getvalue())))
                    actual = list(csv.DictReader(io.StringIO(archive.read(csv_name).decode("utf-8-sig"))))
                    self.require(actual == expected, f"ZIP CSV differs from catalog values: {label}")
            catalog_entry = "图表目录与数值.json"
            self.require(catalog_entry in names, "ZIP is missing its numerical catalog")
            if catalog_entry in names:
                self.require(json.loads(archive.read(catalog_entry)) == catalog, "ZIP catalog differs from delivered catalog")
            self.counts.update(zip_svg=len(svg_names), zip_csv=len(csv_names))

    def content(self):
        content = self.json_file("app/data/research-content.json")
        if content is None:
            return
        self.require(content.get("totalRecords") == 248586, "Content total must be 248586 responses")
        self.require(len(content.get("dimensions", [])) == 4, "Content must describe four experiment dimensions")
        self.require(len(content.get("prompts", [])) == 31, "Content must list 31 actual prompt strategies")
        topics = content.get("topics", [])
        groups = Counter(topic.get("group") for topic in topics)
        self.require(len(topics) == 7 and {topic.get("id") for topic in topics} == TOPICS,
                     "Content must describe the seven research topics")
        self.require(groups == {"general": 4, "specific": 3}, "Discoveries must follow the 4 general / 3 specific structure")
        self.require({topic.get("id") for topic in topics if topic.get("group") == "general"} == GENERAL,
                     "General/specific discovery grouping is incorrect")
        expected = {experiment.get("id"): experiment.get("records") for experiment in content.get("experiments", [])}
        self.require(expected == EXPERIMENTS, "Content experiment response counts differ from the five actual experiments")
        self.require(sum(expected.values()) == content.get("totalRecords"), "Content experiment counts do not sum to total")
        source = self.local_file(UNIFIED)
        if source:
            # Count real rows, rather than trusting a duplicated summary number.
            counts, excluded = Counter(), 0
            with gzip.open(source, "rt", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    counts[row["experiment_id"]] += 1
                    excluded += row.get("environment_excluded", "").lower() in {"1", "true", "yes"}
            self.require(dict(counts) == EXPERIMENTS, f"Unified payload experiment counts differ: {dict(counts)}")
            self.require(sum(counts.values()) == 248586, "Unified payload must contain 248586 responses")
            self.require(excluded == content.get("excludedRecords") == 465, "Environment exclusions must total 465")
            provenance = content.get("cleaning", {}).get("provenance", {})
            if provenance.get("sampleSHA256"):
                self.require(provenance["sampleSHA256"] == self.digest(source), "Cleaning provenance SHA-256 differs from payload")
            self.counts.update(records=sum(counts.values()), experiments=len(counts), environment_exclusions=excluded)
        self.counts.update(dimensions=len(content.get("dimensions", [])), prompts=len(content.get("prompts", [])),
                           general=groups["general"], specific=groups["specific"])

    def protection(self):
        manifest = self.json_file("tests/fixtures/research-protection.json")
        if manifest is None:
            return
        files = manifest.get("files", {})
        self.require(len(files) == 1100, "Protection fixture must cover exactly 1100 research files")
        matched, hydrated = 0, 0
        for relative, expected in files.items():
            path = self.local_file(relative)
            if path is None:
                continue
            actual = self.digest(path)
            if actual == expected:
                matched += 1
                continue
            # Only this authorized hydration may differ byte-for-byte from the fixture.
            if relative == UNIFIED:
                result = subprocess.run(["git", "show", "HEAD:" + relative], cwd=ROOT,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                pointer = result.stdout
                pointer_match = re.fullmatch(
                    rb"version https://git-lfs.github.com/spec/v1\r?\n"
                    rb"oid sha256:([0-9a-f]{64})\r?\nsize ([0-9]+)\r?\n?", pointer)
                if (result.returncode == 0 and hashlib.sha256(pointer).hexdigest() == expected
                        and pointer_match and pointer_match[1].decode() == actual
                        and int(pointer_match[2]) == path.stat().st_size):
                    matched += 1
                    hydrated += 1
                    continue
            self.require(False, f"Protected research file changed: {relative}")
        self.counts.update(protected=matched, protected_expected=len(files), hydrated_lfs=hydrated)

    def run(self):
        for name in ("atlas", "content", "protection"):
            try:
                getattr(self, name)()
            except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
                self.require(False, f"{name}: {error}")
        print(("PASS" if not self.errors else "FAIL") + " reconstruction: " +
              " ".join(f"{key}={value}" for key, value in self.counts.items()))
        for error in self.errors:
            print("  - " + error, file=sys.stderr)
        return 1 if self.errors else 0


if __name__ == "__main__":
    raise SystemExit(Checks().run())
