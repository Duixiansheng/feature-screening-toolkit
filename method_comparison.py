"""Compare the seven built-in methods through a common evidence table."""
import argparse
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

from data_audit import write_json
from screening import METHODS, fit_method
from select_factors import load_csv

DEFAULT_METHODS = ("IGR", "mRMR", "ReliefF")
RANKING_METHODS = {"IGR", "mRMR", "ReliefF", "RF-RFE"}


def check_options(methods, top_k, seed, width):
    if not methods or len(set(methods)) != len(methods) or set(methods) - METHODS:
        raise ValueError("请选择互不重复的有效分析方法。")
    if not 1 <= top_k <= width:
        raise ValueError(f"Top K 必须在 1 到 {width} 之间。")
    if not 0 <= seed <= 2**32 - 101:
        raise ValueError("随机种子超出允许范围。")


def method_evidence(method, x, y, seed, top_k):
    if method == "mRMR" and len(y) < 11:
        raise ValueError("mRMR 至少需要 11 条样本。")
    result = fit_method(method, x, y, seed)
    ranks, scores, evidence, selected = None, None, None, None
    setting = "default"
    if method == "IGR":
        scores = [item["ratio"] for item in result["scores"]]
        evidence = result["scores"]
    elif method == "mRMR":
        setting = "neighbors=5"
        details = result["settings"][5]
        ranks = rank_from_order(details["rank"])
        evidence = details["steps"]
    elif method == "ReliefF":
        setting = "requested_neighbors=10"
        details = result["settings"][10]
        scores = details["weights"].tolist()
        evidence = {"effective_neighbors": details["effective_k"]}
    elif method == "RF-RFE":
        ranks = rank_from_order(result["rank"])
    elif method == "Boruta":
        selected = result["confirmed"].tolist()
        evidence = result["status"]
    elif method == "Elastic Net":
        setting = "balanced/0.3/0.75"
        details = result["settings"][setting]
        if not details["converged"]:
            raise ValueError("Elastic Net 所用配置未收敛。")
        scores = details["coefficients"].tolist()
        selected = details["selected"].tolist()
        evidence = {"iterations": details["iterations"]}
    elif method == "HSIC-Lasso":
        setting = "penalty_fraction=0.05"
        details = result["settings"][.05]
        scores = details["coefficients"].tolist()
        selected = details["selected"].tolist()
        evidence = {"lambda": details["lambda"]}
    if ranks is None and method in RANKING_METHODS:
        ranks = rankdata(-np.asarray(scores), method="min").astype(int).tolist()
    if selected is None:
        selected = [i for i, value in enumerate(ranks) if value <= top_k]
        if method == "IGR":
            selected = [i for i in selected if scores[i] > 0]
    return dict(method=method, setting=setting, ranks=ranks, scores=scores,
                candidates=selected, evidence=evidence)


def rank_from_order(order):
    return (np.argsort(order) + 1).tolist()


def compare_methods(path, target, excluded=(), methods=DEFAULT_METHODS, top_k=2, seed=42):
    x, y, names = load_csv(Path(path), target, excluded)
    check_options(methods, top_k, seed, len(names))
    results = [method_evidence(method, x, y, seed, top_k) for method in methods]
    candidate_sets = [set(result["candidates"]) for result in results]
    votes = []
    for index, name in enumerate(names):
        supporting = [method for method, candidates in zip(methods, candidate_sets) if index in candidates]
        votes.append(dict(factor=name, votes=len(supporting), methods=supporting))
    agreement = []
    for i, j in combinations(range(len(results)), 2):
        a, b = candidate_sets[i], candidate_sets[j]
        agreement.append(dict(left=methods[i], right=methods[j],
                              jaccard=len(a & b)/len(a | b) if a or b else None,
                              shared=[names[n] for n in sorted(a & b)]))
    return dict(rows=len(y), features=names, target=target, seed=seed, top_k=top_k,
                methods=results, agreement=agreement,
                votes=sorted(votes, key=lambda item: (-item["votes"], item["factor"])))


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("csv", type=Path)
    args.add_argument("--target", required=True)
    args.add_argument("--exclude", action="append", default=[])
    args.add_argument("--method", action="append", choices=sorted(METHODS))
    args.add_argument("--top-k", type=int, default=2)
    args.add_argument("--seed", type=int, default=42)
    args.add_argument("--output", required=True, type=Path)
    cfg = args.parse_args()
    write_json(cfg.output, compare_methods(cfg.csv, cfg.target, cfg.exclude,
                                          cfg.method or DEFAULT_METHODS, cfg.top_k, cfg.seed))


if __name__ == "__main__":
    main()
