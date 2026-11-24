"""Run the research feature selectors on a binary-classification CSV."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from screening import METHODS, Settings, fit_method


def load_csv(path, target, excluded):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader, [])
        if not header or any(not name.strip() for name in header) or len(set(header)) != len(header):
            raise ValueError("CSV requires nonempty, unique column names")
        missing = {target, *excluded} - set(header)
        if missing:
            raise ValueError(f"Unknown columns: {', '.join(sorted(missing))}")
        if target in excluded:
            raise ValueError("The target column cannot also be excluded")
        label_index = header.index(target)
        indexes = [i for i, name in enumerate(header) if name != target and name not in excluded]
        if not indexes:
            raise ValueError("Select at least one feature column")
        rows, labels = [], []
        for line, row in enumerate(reader, 2):
            if not row:
                continue
            if len(row) != len(header):
                raise ValueError(f"Row {line}: expected {len(header)} columns")
            try:
                label = float(row[label_index])
            except ValueError:
                label = None
            if label not in (0, 1):
                raise ValueError(f"CSV 第 {line} 行的目标列「{target}」须为 0 或 1。")
            try:
                features = [float(row[i]) for i in indexes]
            except ValueError:
                features = []
                for i in indexes:
                    try:
                        features.append(float(row[i]))
                    except ValueError:
                        features.append(np.nan)
            valid = np.isfinite(features)
            if not valid.all():
                i = indexes[int(np.flatnonzero(~valid)[0])]
                raise ValueError(f"CSV 第 {line} 行的「{header[i]}」不是有效数值。"
                                 "若是编号或类别列，请设为分组列或在「排除列」中勾选。")
            rows.append(features)
            labels.append(int(label))
    if set(labels) != {0, 1}:
        raise ValueError("Training data must contain both target classes")
    return np.asarray(rows), np.asarray(labels), [header[i] for i in indexes]


def encode_numpy(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def run_selection(input_path, target, excluded, method, output, seed=42, jobs=1):
    if not 0 <= seed <= 2**32 - 101 or jobs == 0:
        raise ValueError("Use a seed between 0 and 4294967195 and a nonzero worker count")
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    x, y, names = load_csv(input_path, target, excluded)
    if method == "mRMR" and len(x) < 11:
        raise ValueError("mRMR requires at least 11 training rows")
    result = fit_method(method, x, y, seed, Settings(jobs=jobs))
    report = {
        "method": method,
        "seed": seed,
        "training_rows": len(x),
        "features": names,
        "result": result,
    }
    payload = json.dumps(report, default=encode_numpy, ensure_ascii=False, allow_nan=False, indent=2)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(payload + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="UTF-8 training CSV")
    parser.add_argument("--target", required=True, help="Column containing binary labels")
    parser.add_argument("--exclude", action="append", default=[], help="Column to omit, repeat as needed")
    parser.add_argument("--method", choices=sorted(METHODS), required=True)
    parser.add_argument("--output", type=Path, required=True, help="New JSON file for the results")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--jobs", type=int, default=1, help="Random forest worker count")
    args = parser.parse_args()
    try:
        run_selection(args.input, args.target, args.exclude, args.method,
                      args.output, args.seed, args.jobs)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
