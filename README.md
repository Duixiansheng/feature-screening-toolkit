# TerraFactor 5

**地学样本的因子分析工作台**

打开带有 `0/1` 标签的 CSV，检查数据质量、对照多种因子分析方法，并在留出的样本上比较全因子与 Top K 的表现。重复分析可以保存成项目，批量执行并按输入指纹复用结果。

[Windows 64 位便携版与历史版本](https://github.com/Duixiansheng/feature-screening-toolkit/releases)

## 开始使用

1. 解压整个 `TerraFactor` 文件夹，双击 `TerraFactor.exe`，打开包内的 `example.csv`。
2. 在「数据体检」点「运行当前页」，检查样本数、类分布、缺失和重复。
3. 转到「方法对照」或「留出验证」运行相应分析，点击表头可排序。
4. 用「保存项目」保存参数。也可以直接打开包内的 `example-project.json`，把三项分析一次跑完。
5. 把当前页结果导出为 CSV 或 JSON。JSON 保留更完整的方法配置、交集、逐折预测和运行记录。

## 五代更新

| 版本 | 新能力 | 可单独运行的入口 |
| --- | --- | --- |
| 1.0 | 数据体检。检查缺失、无效数值、常量列、重复样本和类别失衡，报告 Spearman 高相关因子对。 | `data_audit.py` |
| 2.0 | 方法对照。汇集七种方法的结果，输出候选支持次数、两两交集与 Jaccard 一致度。 | `method_comparison.py` |
| 3.0 | 留出验证。支持分层及按组分折，在每折训练侧重新估计因子排名和标准化参数，报告 AP、ROC AUC、稳定性与逐样本留出预测。 | `fold_validation.py` |
| 4.0 | 批量项目。使用 JSON 描述任务，按数据、参数和软件版本指纹复用结果，失败任务可重新执行。 | `factor_project.py` |
| 5.0 | Windows 工作台。四个结果页面、图表、排序、项目保存和载入、后台运行与 JSON/CSV 导出。 | `studio.py` |

## 数据和结果怎么读

CSV 使用 UTF-8，第一行是唯一的列名。目标列使用数字 `0` 和 `1`。数据体检可以读取含缺失值和非数值的表，对照与验证要求所用因子为有限数值。样本编号、坐标等辅助字段可以排除。验证可选分组列，例如流域编号，同一组只出现在一个留出折内，分组列会自动排除在因子之外。

- 对照中，IGR、mRMR、ReliefF 和 RF-RFE 使用 Top K 规则。打分方法的边界并列可一同进入，IGR 的零分项不会计入候选。Boruta 使用确认集合，HSIC-Lasso 与 Elastic Net 使用所选配置的非零系数。报告列出各方法的配置和候选集。
- 留出验证采用同一个标准化逻辑回归模型，比较全部因子和训练折内排名靠前的固定 K 个因子。排名并列时按 CSV 列序决定顺序。AP 差值来自两套配置在相同折上的表现。尝试许多配置后再报告最佳结果时，应另用独立数据验证。
- 批量输出包含 `manifest.json` 和按指纹命名的任务结果。原始 CSV 与项目文件保持只读。HSIC-Lasso 的核计算随样本量近似二次增长。

## 从源码运行

使用带 Tk 的 Python 3.11–3.13。

```sh
python -m pip install -r requirements.txt
python studio.py example.csv
```

各命令行入口支持 `--help`。早期版本的 `select_factors.py` 仍可生成原有的单方法 JSON。

```sh
python data_audit.py example.csv --target label --output audit.json
python method_comparison.py example.csv --target label --top-k 2 --output comparison.json
python fold_validation.py example.csv --target label --top-k 2 --folds 5 --output validation.json
python factor_project.py example-project.json --output project-results
```
