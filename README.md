# 因子筛选工具

用训练样本中的数值因子预测二分类目标时，可以用这个工具比较因子排名或获取候选因子集合。它复用了沟蚀易发性研究正式实验中的七种筛选实现。

## 安装和运行

需要 Python 3.11 至 3.13。进入本目录后运行：

```sh
python -m pip install -r requirements.txt
python select_factors.py example.csv --target label --method IGR --output result.json
```

`example.csv` 是合成数据。自己的 CSV 请保存为 UTF-8，第一行为列名，目标列只取 0 和 1 且两类均有样本。其余列默认是有限数值型因子。编号、坐标或其他无需参与筛选的列可以用 `--exclude sample_id --exclude longitude` 排除。请在运行前处理缺失值，并仅传入当前训练折的数据。

`--seed` 默认为 42。对随机森林方法可用 `--jobs -1` 使用所有可用核心。输出为新建的 JSON 文件，`features` 数组按输入列顺序排列，结果里的因子索引从 0 开始。

| 方法 | 结果 |
| --- | --- |
| RF-RFE | 完整排名与逐步剔除记录 |
| Boruta | 确认、待定和剔除的因子，附每轮记录 |
| mRMR | 三种互信息邻居数的完整排名 |
| ReliefF | 三种邻域配置的权重和排名 |
| HSIC-Lasso | 三种惩罚配置的系数和入选因子 |
| IGR | 完整排名、正调整增益排名及每列的阈值和得分 |
| Elastic Net | 各正则化和类别权重配置的系数、入选因子及收敛状态 |

方法名按表中写法传入，含空格的 `Elastic Net` 需要加双引号。入选集合允许为空。mRMR 至少需要 11 条训练样本，ReliefF 要求每类至少 2 条。HSIC-Lasso 的核计算随样本量近似二次增长。

此入口运行一次训练集筛选。研究中的空间交叉验证、基于内层 AP 的截断和模型比较属于后续评估步骤。
