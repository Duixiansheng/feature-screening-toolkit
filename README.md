# TerraFactor 5

**地学样本的因子分析工作台**

打开带有 `0/1` 标签的 CSV，检查数据质量、对照多种因子分析方法，并在留出的样本上比较全因子与 Top K 的表现。重复分析可以保存成项目，批量执行并按输入指纹复用结果。

[**下载 TerraFactor 5.0.1 · Windows 64 位便携 ZIP**](https://github.com/Duixiansheng/feature-screening-toolkit/releases/download/v5.0.1/terrafactor-v5.0.1-windows-x64.zip) · [历史版本](https://github.com/Duixiansheng/feature-screening-toolkit/tags)

## 主要功能

### 检查样本数据

查看两类样本的数量，定位缺失值、无效数值、重复行和常量列。用 Spearman 相关系数找出信息可能重叠的因子对。

### 对照因子分析结果

在同一张样本表上运行多种方法，查看每个因子得到哪些方法支持，以及各方法的候选结果有多少重合。

### 在留出样本上比较表现

按类别分层，或按流域、地块等字段分组。每折在训练样本上重新计算排名，再用同一批留出样本比较全因子与排名靠前的 K 个因子。查看逐折 AP、ROC AUC 和候选因子出现次数。

### 重复运行并导出结果

把数据与参数保存成项目，一次运行多项分析。重跑时可复用已完成且数据与参数一致的结果。桌面版支持查看图表、排序，以及导出 CSV 或 JSON。

## 开始使用

1. 解压整个 `TerraFactor` 文件夹，双击 `TerraFactor.exe`，打开包内的 `example.csv`。
2. 在「数据体检」点「运行当前页」，检查样本数、类分布、缺失和重复。
3. 转到「方法对照」或「留出验证」运行相应分析，点击表头可排序。
4. 用「保存项目」保存参数。也可以直接打开包内的 `example-project.json`，把三项分析一次跑完。
5. 把当前页结果导出为 CSV 或 JSON。JSON 保留更完整的方法配置、交集、逐折预测和运行记录。

### 滑坡合成案例

打开 `examples/terrafactor-landslide-project.json`，点击「运行当前页」并选择输出目录。完成后可以切到「数据体检」「方法对照」和「留出验证」查看结果。直接打开同目录的 CSV 时，软件会默认排除 `sample_id`，用 `basin_id` 分组。若要手动复现项目的验证结果，验证方法选 IGR，Top K 填 3，折数填 4。

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
