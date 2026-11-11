# 别人如何复现水稻抗逆抗病 dashboard

## 先说结论

**功能上已经可复现，仓库层面还没有完全满足。**

代码、契约、测试、面板 CSV 和生成脚本都在本地工作区，`scripts/reproduce_dashboard.py` 已经能一键跑通并写出
`reproduction.json`。但是：

- 这些改动目前只在本地分支 `release/contract-4.0.0-rbl1`，**没有 commit / push / PR**；别人 clone
  `atoz03/pdf2jsonl` 看不到；
- RBL1 的 PDF 和 13 篇水稻论文的 PDF **不在仓库里**（版权和体积原因），必须由复现者提供；
- `reproduction.json` 当前是 `dirty: true`，因为工作区未提交。提交后应为 `false`；
- 真实面板是每篇论文 page-1 的 **curated association**，不是全篇穷尽抽取；全文/图表/补充材料需要后续补齐。

所以：**本地和 CI 能复现；异地陌生人现在还不能只靠公开仓库复现。** 要真正满足，需要先 commit/push 这一段，
再按下面步骤运行。

## 前置条件

- Python 3.10+
- Git
- 能读 PDF 的本地文件（不需要联网、不需要模型 API）
- RBL1 PDF：`qt2321j386.pdf`
  - 期望 SHA256：`323646482dd6a7536dbdcf8a23a3f61cbddd964c3bb15a65de90a4443aac3812`
- 13 篇水稻论文目录，文件名需要匹配 `examples/rice_stress_panel/panel.csv` 里的 `file_glob`
  （例如 `*Pib gene*.pdf`、`COLD1*.pdf`）

## 一次性安装

```bash
git clone https://github.com/atoz03/pdf2jsonl.git
cd pdf2jsonl
git switch <提交/分支或 PR 的 head>
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e '.[dev]'            # dev 包含 pypdf、openpyxl 和 pytest
```

## 一键复现

```bash
python scripts/reproduce_dashboard.py \
  --rbl1-pdf /path/to/qt2321j386.pdf \
  --rice-pdf-dir /path/to/水稻-抗逆抗病性状 \
  --out out/reproduce
```

Windows PowerShell：

```powershell
python scripts/reproduce_dashboard.py `
  --rbl1-pdf .\qt2321j386.pdf `
  --rice-pdf-dir "D:\新建文件夹\水稻-抗逆抗病性状" `
  --out out\reproduce
```

或：

```bash
make reproduce RBL1_PDF=/path/to/qt2321j386.pdf RICE_PDF_DIR=/path/to/水稻-抗逆抗病性状
```

脚本会依次：

1. 校验 RBL1 PDF 的 SHA256；
2. 生成 `out/reproduce/rbl1_case/`；
3. 生成 13 篇真实论文面板 `out/reproduce/rice_stress_panel/`；
4. 生成 `out/reproduce/dashboard.html`；
5. 检查 RBL1 的 14 项检查、聚合计数、dashboard 关键内容；
6. 写 `out/reproduce/reproduction.json`，记录 git commit/dirty、输入哈希、版本、计数和命令。

## 预期结果

```json
{
  "rbl1_checks": 14,
  "counts": {
    "papers": 14,
    "relations": 15,
    "associations": 16,
    "evidence": 49,
    "conflicts": 0,
    "confidence": {"B": 15}
  }
}
```

另外：

```text
out/reproduce/rbl1_case/rbl1_case.json   checks 全 true
out/reproduce/dashboard.html             含“多文聚合”“论文—性状关系图”“为什么能指向同一个性状”
```

## 如何判断真的复现了

看 `out/reproduce/reproduction.json`：

- `git.dirty` 应为 `false`；
- `git.commit` 应为你们约定的提交；
- `inputs.rbl1_pdf.sha256` 应等于期望值；
- `checks.rbl1` 全部为 `true`；
- `checks.aggregate_counts` 与上面一致；
- `contract.schema_version` 为 `4.0.0`。

如果只缺 PDF，不要用别的论文替代；脚本会直接失败。没有 PDF 时只能用 `bdc rbl1` 的 CSV-only smoke
test，或 `build_rice_stress_panel.py` 的 hash-less 构建，不能声称完成了完整复现。

## 直接对话可以吗？

**不能只靠一句“帮我跑一下”**。对话式 agent 必须同时具备：

1. 仓库读写权限和正确的 commit；
2. 两个 PDF 输入路径；
3. 能执行 Python / shell；
4. 能读取生成的 `reproduction.json` 做验收。

如果这些条件满足，对话可以触发，但提示词要把输入、版本、命令和验收写死。

### 可直接使用的提示词

```text
你是复现操作员。请复现 pdf2jsonl 的水稻抗逆抗病 dashboard，不要改数据、不要用别的论文替代输入。

仓库：https://github.com/atoz03/pdf2jsonl
版本：<填写 PR head / commit / tag，例如 4.0.0 的 commit>
RBL1 PDF：<绝对路径>/qt2321j386.pdf
13 篇论文目录：<绝对路径>/水稻-抗逆抗病性状
输出目录：<绝对路径>/out/reproduce

步骤：
1. git clone 仓库，checkout 指定 commit；记录 git rev-parse HEAD。
2. python -m venv .venv，安装 pip install -e '.[dev]'。
3. 运行：
   python scripts/reproduce_dashboard.py \
     --rbl1-pdf "<RBL1 PDF>" \
     --rice-pdf-dir "<13 篇论文目录>" \
     --out "<输出目录>"
4. 读取 <输出目录>/reproduction.json，逐项验收：
   - git.dirty == false
   - inputs.rbl1_pdf.sha256 == 323646482dd6a7536dbdcf8a23a3f61cbddd964c3bb15a65de90a4443aac3812
   - checks.rbl1 全部 true
   - checks.aggregate_counts == {"papers":14,"relations":15,"associations":16,
     "evidence":49,"conflicts":0,"confidence":{"B":15}}
   - dashboard.html 存在，且包含“多文聚合”“论文—性状关系图”“为什么能指向同一个性状”
5. 运行 bdc check --strict 和
   pytest tests/test_rbl1_case.py tests/test_association_aggregate.py tests/test_rice_stress_panel.py -q。
6. 输出：commit、Python 版本、输入 SHA256、上述检查结果、dashboard 路径。
   任何一步失败就停止并报告具体失败项，不要静默换输入或跳过检查。
```

### 提示词设计要点

- **固定版本**：写 commit/PR head，不写“latest”。
- **固定输入**：写绝对路径与期望 SHA256；不要只说“论文在某个文件夹”。
- **固定命令**：直接给 `reproduce_dashboard.py`，不要只描述目标。
- **固定验收**：把 `reproduction.json` 的字段和预期计数写死。
- **失败策略**：缺 PDF、哈希不符、dirty 仓库都视为失败，不允许替换。
- **记录环境**：Python 版本、平台、git commit、输入哈希。

## 当前本地验证记录

```text
python scripts/reproduce_dashboard.py ...   -> 14 papers / 15 relations / 16 contexts / 49 evidence / B15
bdc check --strict                          -> 0 error, 0 warning
tests/test_rbl1_case.py                     -> 4 passed
tests/test_association_aggregate.py         -> 5 passed
tests/test_rice_stress_panel.py             -> 2 passed
```

但 `reproduction.json` 的 `git.dirty` 仍为 `true`，这是当前唯一阻止“异地完全复现”的仓库层面问题。
