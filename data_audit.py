"""Inspect CSV structure, class balance and redundant numeric columns."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from select_factors import encode_numpy

MISSING = {"", "na", "n/a", "null", "nan"}


def read_table(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, [])
        if not header or any(not col.strip() for col in header) or len(set(header)) != len(header):
            raise ValueError("CSV 列名必须非空且互不重复。")
        rows = []
        for row in reader:
            if row:
                if len(row) != len(header):
                    raise ValueError(f"CSV 第 {reader.line_num} 行有 {len(row)} 列，应为 {len(header)} 列。")
                rows.append(row)
    if not rows:
        raise ValueError("CSV 中没有样本。")
    return header, rows


def number(value):
    try:
        parsed = float(value)
        return parsed if np.isfinite(parsed) else np.nan
    except ValueError:
        return np.nan


def audit(path, target, excluded=(), correlation=.95):
    if not 0 < correlation <= 1:
        raise ValueError("相关阈值必须大于 0 且不大于 1。")
    header, rows = read_table(path)
    if target not in header or not set(excluded) <= set(header):
        raise ValueError("目标列或排除列不在 CSV 中。")
    index = header.index(target)
    labels = np.array([number(row[index]) for row in rows])
    counts = {str(label): int((labels == label).sum()) for label in (0, 1)}
    duplicates = len(rows) - len({tuple(row) for row in rows})
    stats, numeric = [], {}
    for column, name in enumerate(header):
        if column == index or name in excluded:
            continue
        raw = [row[column].strip() for row in rows]
        missing = sum(value.lower() in MISSING for value in raw)
        values = np.array([number(value) for value in raw])
        finite = values[np.isfinite(values)]
        invalid = len(rows) - len(finite) - missing
        kind = "non_numeric" if invalid else "numeric" if len(finite) else "empty"
        summary = dict(name=name, kind=kind, missing=missing, invalid_numeric=invalid,
                       valid_numeric=len(finite), distinct_numeric=len(set(finite.tolist())))
        if len(finite):
            summary.update(minimum=float(finite.min()), median=float(np.median(finite)),
                           maximum=float(finite.max()), constant=summary["distinct_numeric"] == 1)
        if kind == "numeric" and not summary.get("constant"):
            numeric[name] = values
        stats.append(summary)
    correlated = []
    for i, (left, a) in enumerate(numeric.items()):
        for right, b in list(numeric.items())[i+1:]:
            valid = np.isfinite(a) & np.isfinite(b)
            if valid.sum() >= 3 and len(set(a[valid])) > 1 and len(set(b[valid])) > 1:
                score = float(spearmanr(a[valid], b[valid]).statistic)
                if abs(score) >= correlation:
                    correlated.append(dict(left=left, right=right, spearman=score, rows=int(valid.sum())))
    return dict(rows=len(rows), target=target, class_counts=counts,
                invalid_target=len(rows)-sum(counts.values()),
                duplicate_rows=duplicates, excluded=list(excluded), columns=stats,
                correlation_threshold=correlation,
                correlated_pairs=sorted(correlated, key=lambda p: -abs(p["spearman"])))


def write_json(path, value, overwrite=False):
    payload = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, default=encode_numpy)
    mode = "w" if overwrite else "x"
    with Path(path).open(mode, encoding="utf-8") as stream:
        stream.write(payload + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--threshold", type=float, default=.95)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_json(args.output, audit(args.csv, args.target, args.exclude, args.threshold))


if __name__ == "__main__":
    main()
