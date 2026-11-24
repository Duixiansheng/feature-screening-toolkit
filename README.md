# TerraFactor · 地学因子分析

TerraFactor 用于量化地学样本中数值因子与二元标签的关系。导入包含坡度、降水量、植被指数等因子和 `0/1` 标签的 CSV，选择分析方法，即可将因子得分、排名或方法判定结果导出为 JSON。

[**下载 Windows 64 位便携版（v0.1.0 ZIP）**](https://github.com/Duixiansheng/feature-screening-toolkit/releases/download/v0.1.0/feature-screening-toolkit-v0.1.0-windows-x64.zip)

解压整个 `FeatureScreening` 文件夹，双击 `FeatureScreening.exe`。无需另装 Python。

## 快速体验

1. 打开包内的合成示例 `example.csv`。
2. 目标列选 `label`，方法选 `IGR`。
3. 指定新的 JSON 文件路径，点击「运行并导出」，查看三个示例因子的得分和排名。

## 数据格式

使用 UTF-8 CSV。第一行为列名，每行对应一个样本。目标列使用数字 `0` 和 `1`，两类均需有样本。参与分析的因子列应为有限数值。样本编号、坐标等辅助列可在窗口中勾选排除。

## 分析方法

| 方法 | 输出内容 |
| --- | --- |
| RF-RFE | 因子排名、逐步剔除记录 |
| Boruta | 确认、待定和剔除状态、各轮记录 |
| mRMR | 互信息、冗余度、不同邻域配置的排名 |
| ReliefF | 不同邻域配置的权重和排名 |
| HSIC-Lasso | 不同惩罚配置的系数和非零系数对应的因子 |
| IGR | 信息增益率、分裂阈值和排名 |
| Elastic Net | 各配置的系数、非零系数对应的因子和收敛状态 |

结果中的因子索引从 `0` 开始，与 JSON 中 `features` 数组的顺序对应。mRMR 至少需要 11 条样本，ReliefF 要求每类至少 2 条。HSIC-Lasso 的核计算量随样本数近似二次增长。

## 命令行

需要 Python 3.11–3.13。在仓库目录下运行：

```sh
python -m pip install -r requirements.txt
python select_factors.py example.csv --target label --method IGR --output result.json
```

可重复使用 `--exclude` 排除多列，例如 `--exclude sample_id --exclude longitude`。方法名包含空格时请加双引号，例如 `--method "Elastic Net"`。
