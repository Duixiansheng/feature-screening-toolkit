# TerraFactor 3

地学样本的因子分析软件。本代新增分组留出验证与逐样本预测。

## 命令行用法

使用 Python 3.11–3.13，在仓库目录运行：

```sh
python -m pip install -r requirements.txt
python data_audit.py example.csv --target label --output audit.json
python method_comparison.py example.csv --target label --top-k 2 --output comparison.json
python fold_validation.py example.csv --target label --top-k 2 --output validation.json
```

使用 UTF-8 CSV，目标列为 `0` 和 `1`。原有 `select_factors.py` 单方法入口仍可使用。
