"""Evaluate candidate subsets and all factors on identical held-out folds."""
import argparse
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from data_audit import number, read_table, write_json
from method_comparison import RANKING_METHODS, check_options, method_evidence
from select_factors import load_csv


def validation_input(path, target, excluded, group):
    if not group:
        x, y, names = load_csv(Path(path), target, excluded)
        return x, y, names, None
    header, rows = read_table(path)
    if group == target or target in excluded or not {group, target, *excluded} <= set(header):
        raise ValueError("目标列、分组列或排除列配置无效。")
    names = [name for name in header if name not in {target, group, *excluded}]
    if not names:
        raise ValueError("至少保留一个数值因子。")
    gi, ti = header.index(group), header.index(target)
    columns = [header.index(name) for name in names]
    groups = np.asarray([row[gi].strip() for row in rows])
    if any(groups == ""):
        raise ValueError(f"分组列「{group}」有空值，请补齐或清空分组列设置。")
    x = np.asarray([[number(row[i]) for i in columns] for row in rows])
    y = np.asarray([number(row[ti]) for row in rows])
    valid = np.isfinite(x)
    if not valid.all():
        row, col = divmod(int(valid.argmin()), len(names))
        raise ValueError(f"样本 {row + 1} 的「{names[col]}」不是有效数值。"
                         "若是样本编号，请在「排除列」中勾选。")
    if set(y) != {0, 1}:
        raise ValueError(f"目标列「{target}」须为数字 0 或 1，且两类都要有样本。")
    return x, y.astype(int), names, groups


def predict(train_x, train_y, test_x):
    pipeline = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    return pipeline.fit(train_x, train_y).predict_proba(test_x)[:, 1]


def score(y, prediction):
    return dict(ap=float(average_precision_score(y, prediction)),
                roc_auc=float(roc_auc_score(y, prediction)))


def evaluate(path, target, excluded=(), method="IGR", top_k=2, folds=5, group=None, seed=42):
    x, y, names, groups = validation_input(path, target, excluded, group)
    check_options((method,), top_k, seed, len(names))
    if method not in RANKING_METHODS:
        raise ValueError("验证支持 IGR、mRMR、ReliefF 和 RF-RFE。")
    if not 2 <= folds <= int(np.bincount(y).min()):
        raise ValueError("折数至少为 2，且不能超过最少类别的样本数。")
    if groups is not None and len(set(groups)) < folds:
        raise ValueError(f"分组列「{group}」只有 {len(set(groups))} 个不同组，无法分成 {folds} 折。"
                         "请选择流域等分组字段，或清空分组列。")
    if groups is None:
        splitter = StratifiedKFold(folds, shuffle=True, random_state=seed)
    else:
        splitter = StratifiedGroupKFold(folds, shuffle=True, random_state=seed)
    splits = list(splitter.split(x, y, groups))
    for step, (training, held) in enumerate(splits, 1):
        if len(set(y[training])) != 2 or len(set(y[held])) != 2:
            raise ValueError(f"第 {step} 折缺少一个类别，请减少折数或调整分组。")
        if method == "mRMR" and len(training) < 11:
            raise ValueError(f"第 {step} 折训练样本不足 11 条。")
        if method == "ReliefF" and np.bincount(y[training]).min() < 2:
            raise ValueError(f"第 {step} 折训练集中每类至少需要两条样本。")
    results, predictions = [], []
    counts = np.zeros(len(names), dtype=int)
    for step, (training, held) in enumerate(splits, 1):
        detail = method_evidence(method, x[training], y[training], seed, top_k)
        indices = np.argsort(detail["ranks"], kind="stable")[:top_k]
        counts[indices] += 1
        subset = predict(x[training][:, indices], y[training], x[held][:, indices])
        baseline = predict(x[training], y[training], x[held])
        baseline_scores, subset_scores = score(y[held], baseline), score(y[held], subset)
        results.append(dict(fold=step, training_rows=len(training), test_rows=len(held),
                            positive_test_rows=int(y[held].sum()),
                            test_groups=sorted(set(groups[held])) if groups is not None else None,
                            selected=[names[i] for i in indices], all_factors=baseline_scores,
                            top_k=subset_scores, delta_ap=subset_scores["ap"]-baseline_scores["ap"]))
        predictions.extend(dict(row=int(row)+1, fold=step, target=int(y[row]),
                                group=str(groups[row]) if groups is not None else None,
                                all_factors=float(base), top_k=float(top))
                           for row, base, top in zip(held, baseline, subset))
    summary = {key: {metric: float(np.mean([fold[key][metric] for fold in results]))
                     for metric in ("ap", "roc_auc")}
               for key in ("all_factors", "top_k")}
    summary["delta_ap"] = summary["top_k"]["ap"] - summary["all_factors"]["ap"]
    return dict(method=method, features=names, target=target, group_column=group,
                splitter="stratified_group" if group else "stratified", model="standardized_logistic",
                top_k=top_k, seed=seed, folds=results, summary=summary,
                appearance=[dict(factor=name, folds=int(count)) for name, count in zip(names, counts)],
                held_out_predictions=sorted(predictions, key=lambda item: item["row"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--group")
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--method", choices=sorted(RANKING_METHODS), default="IGR")
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    write_json(args.output, evaluate(args.csv, args.target, args.exclude, args.method,
                                    args.top_k, args.folds, args.group, args.seed))


if __name__ == "__main__":
    main()
