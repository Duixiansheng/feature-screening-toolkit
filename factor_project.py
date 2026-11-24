"""Run a reproducible TerraFactor project with per-job resume."""
import argparse
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

import numpy
import scipy
import sklearn

from data_audit import audit
from fold_validation import evaluate
from method_comparison import compare_methods
from select_factors import encode_numpy

ENGINE_REVISION = "4.0.0"
OPERATIONS = {"audit": audit, "compare": compare_methods, "validate": evaluate}
ENGINE = dict(terrafactor=ENGINE_REVISION, numpy=numpy.__version__,
              scipy=scipy.__version__, scikit_learn=sklearn.__version__)


def digest(path):
    with Path(path).open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def atomic_json(path, value):
    path = Path(path)
    payload = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, default=encode_numpy)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                            prefix=".terra-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_project(path):
    path = Path(path).resolve()
    spec = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(spec, dict) or spec.get("schema") != 1:
        raise ValueError("项目文件须使用 schema: 1。")
    for field in ("input", "target"):
        if not isinstance(spec.get(field), str) or not spec[field].strip():
            raise ValueError(f"项目缺少有效的 {field}。")
    excluded = spec.get("exclude", [])
    if not isinstance(excluded, list) or not all(isinstance(name, str) for name in excluded):
        raise ValueError("exclude 须是列名数组。")
    jobs = spec.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("项目至少需要一个任务。")
    names = set()
    for job in jobs:
        if not isinstance(job, dict):
            raise ValueError("每个任务须是一个 JSON 对象。")
        key, operation, options = job.get("id"), job.get("operation"), job.get("options", {})
        if not isinstance(key, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,48}", key) or key in names:
            raise ValueError("任务 ID 须唯一，且只含 1–48 个字母、数字、连字符或下划线。")
        if not isinstance(operation, str) or operation not in OPERATIONS or not isinstance(options, dict):
            raise ValueError(f"任务 {key} 的 operation 或 options 无效。")
        names.add(key)
    return spec, (path.parent / spec["input"]).resolve()


def cache_key(input_hash, operation, options, target, excluded):
    signature = dict(input_sha256=input_hash, operation=operation, options=options,
                     target=target, exclude=excluded, engine=ENGINE)
    canonical = json.dumps(signature, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def run_project(project, output, resume=True, progress=None, cancelled=None):
    spec, source = read_project(project)
    output = Path(output).resolve()
    protected = {Path(project).resolve(), source}
    if (output / "manifest.json").resolve() in protected:
        raise ValueError("输出清单路径与项目文件或输入数据冲突。")
    output.mkdir(parents=True, exist_ok=True)
    input_hash = digest(source)
    jobs = []
    excluded = spec.get("exclude", [])
    summary = dict(schema=1, engine=ENGINE, project=str(Path(project).resolve()),
                   input=str(source), input_sha256=input_hash, jobs=jobs)
    for index, job in enumerate(spec["jobs"], 1):
        if cancelled and cancelled():
            break
        name, operation, options = job["id"], job["operation"], job.get("options", {})
        status = dict(id=name, operation=operation)
        if progress:
            progress(index, len(spec["jobs"]), name)
        try:
            key = cache_key(input_hash, operation, options, spec["target"], excluded)
            artifact = output / (key + ".json")
            if artifact.resolve() in protected:
                raise ValueError("任务结果路径与项目文件或输入数据冲突。")
            cached = False
            if resume and artifact.is_file():
                try:
                    envelope = json.loads(artifact.read_text(encoding="utf-8"))
                    cached = isinstance(envelope, dict) and envelope.get("key") == key and "result" in envelope
                except (OSError, ValueError):
                    pass
            if not cached:
                result = OPERATIONS[operation](source, spec["target"], excluded, **options)
                if digest(source) != input_hash:
                    raise ValueError("运行期间输入文件发生变化，请重新开始。")
                atomic_json(artifact, dict(key=key, operation=operation, options=options, result=result))
            status.update(state="reused" if cached else "completed", file=artifact.name)
        except Exception as exc:
            status.update(state="failed", error=str(exc))
        jobs.append(status)
    summary["cancelled"] = len(jobs) < len(spec["jobs"])
    atomic_json(output / "manifest.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refresh", action="store_true")
    cfg = parser.parse_args()
    report = run_project(cfg.project, cfg.output, resume=not cfg.refresh)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(any(job["state"] == "failed" for job in report["jobs"]))


if __name__ == "__main__":
    raise SystemExit(main())
