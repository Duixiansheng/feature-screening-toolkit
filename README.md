# TerraFactor

**地学样本的因子分析软件**

分析坡度、降水量、植被指数等数值因子与两类样本之间的关系。输入带有 `0/1` 标签的 CSV，即可按所选方法计算因子得分、排名或判定状态，并将结果导出为 JSON。

[**下载 TerraFactor v0.1.0**](https://github.com/Duixiansheng/feature-screening-toolkit/releases/download/v0.1.0/feature-screening-toolkit-v0.1.0-windows-x64.zip) · Windows 64 位 · 便携 ZIP

## 主要功能

- **比较因子表现**：用 IGR 等方法对因子打分和排序。例如，查看坡度与降水量在区分两类样本时各自得到多少分。
- **查看方法结果**：用 Boruta 查看因子的确认、待定和剔除状态，或用 RF-RFE 查看每一轮剔除了哪个因子。
- **导出分析记录**：将当前方法的参数结果和因子对应关系保存为 JSON。

## 开始使用

1. 解压整个 `FeatureScreening` 文件夹，双击 `FeatureScreening.exe`。无需另装 Python。
2. 打开包内的合成数据 `example.csv`，选择目标列 `label` 和方法 `IGR`。
3. 选择一个新的 JSON 文件路径，点击「运行并导出」。打开结果即可查看三个示例因子的得分和排名。

使用自己的数据时，请提供 UTF-8 CSV，第一行为列名，每行对应一个样本。目标列只取数字 `0` 和 `1`，两类都要有样本。参与分析的因子列须为有限数值。编号和坐标等辅助列可在窗口中勾选排除。

## 方法参考

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
