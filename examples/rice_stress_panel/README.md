# 水稻抗逆抗病真实论文面板

13 篇水稻抗逆/抗病论文的 page-1 **curated association**，用于测试 4.0.0 的 association 聚合、文章—性状关系图和多文 dashboard。不是全篇穷尽抽提，也不替代论文原文。

## 文件

- `panel.csv`：每篇论文一行，记录题名、年份、DOI、基因/QTL、性状、群体/材料/环境、page-1 证据 quote。
- `scripts/build_rice_stress_panel.py`：把 CSV 转成 4.0.0 association 记录，并做 schema 校验与聚合。
- PDF 不在仓库中；运行时通过 `--pdf-dir` 指定本地目录，脚本记录文件 SHA256；没有 PDF 时记录 `source_file_status=not_available`。

## 运行

```bash
python scripts/build_rice_stress_panel.py \
  --panel-csv examples/rice_stress_panel/panel.csv \
  --pdf-dir "D:\新建文件夹\水稻-抗逆抗病性状" \
  --case-dir out/rbl1_case_final \
  --out out/rice_stress_panel

# 或
make rice-panel
```

## 覆盖的论文

| 性状组 | 论文 / 位点 |
|---|---|
| 细菌性条斑病 | xa5、Xa23、Xa7 |
| 稻瘟病 | Pib、Pi9、Pigm |
| 低温/冷害 | COLD1、CTB4a、HAN1、qLTG3-1、qCTS |
| 抽穗期耐热 | qHTSF-RIL、qHTSF-CSSL |

RBL1 案例仍单独保留在 `out/rbl1_case_final`；`--case-dir` 会把它的 3 条关联一起放进聚合和关系图。

## Dashboard

```bash
python scripts/make_network_dashboard.py \
  --rbl1-case out/rbl1_case_final \
  --rbl1-aggregate out/rice_stress_panel/records.jsonl \
  --out dashboard.html

# 或
make dashboard-panel
```

“多文聚合”是独立入口，点击后在覆盖层中展示全库论文—性状关系图、聚合关系、上下文和置信；每张性状卡说明为什么不同论文能共享该性状，以及它们的位点是否相同。真实面板里多数关系只有一篇论文，因此置信为 B；跨文独立重复或冲突需要额外的论文记录。
