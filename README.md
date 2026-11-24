# 地学因子筛选器 · GeoFactor Selector

**用一张样本表，筛选地学二分类建模的候选因子。** 将坡度、降水量、植被指数等数值因子与样本的 0/1 标签放在同一张 CSV 表里，即可在窗口中选择筛选方法，导出因子排名或入选清单。

[**下载 Windows 64 位便携版（v0.1.0 ZIP）**](https://github.com/Duixiansheng/feature-screening-toolkit/releases/download/v0.1.0/feature-screening-toolkit-v0.1.0-windows-x64.zip)

解压整个 `FeatureScreening` 文件夹，双击 `FeatureScreening.exe`。无需另装 Python。

## 用示例跑一次

1. 打开压缩包自带的 `example.csv`，目标列选 `label`。
2. 筛选方法选 `IGR`，排除列留空。
3. 指定一个新的 JSON 文件路径，点击「运行并导出」。结果中会包含三个示例因子的排名和得分。

## 换成自己的数据

将训练样本保存为 UTF-8 CSV。第一行填写列名，每行对应一个样本。目标列使用数字 `0` 和 `1`，两类都要有样本。参与筛选的因子列应为有限数值，请在导入前处理缺失值。样本编号、坐标等辅助列可在「排除列」中勾选。

如果后续要评估模型，请先划分训练集和验证集，再用训练集做筛选。交叉验证时，在每个训练折内重新运行筛选。

## 方法与输出

| 筛选方法 | JSON 中可查看的结果 |
| --- | --- |
| RF-RFE | 完整排名、逐步剔除记录 |
| Boruta | 确认、待定和剔除的因子、每轮筛选记录 |
| mRMR | 三种互信息邻域配置的因子排名 |
| ReliefF | 各邻域配置的因子权重和排名 |
| HSIC-Lasso | 各惩罚配置的系数和入选因子 |
| IGR | 信息增益率排名、分裂阈值和得分 |
| Elastic Net | 各正则化配置的系数、入选因子和收敛状态 |

JSON 中的 `features` 按参与筛选的列顺序列出因子名，结果中的索引从 0 开始。例如，排名第一项为 `0`，表示 `features` 中的第一个因子排在首位。入选集合可以为空。

mRMR 至少需要 11 条训练样本，ReliefF 要求每类至少有 2 条。HSIC-Lasso 的核计算量随样本数近似二次增长。

## 命令行用法

需要 Python 3.11–3.13。在仓库目录下运行：

```sh
python -m pip install -r requirements.txt
python select_factors.py example.csv --target label --method IGR --output result.json
```

可重复使用 `--exclude` 排除多列，例如 `--exclude sample_id --exclude longitude`。方法名包含空格时请加双引号，例如 `--method "Elastic Net"`。
