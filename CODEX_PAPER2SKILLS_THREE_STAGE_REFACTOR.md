# Codex 工程任务：一次性完成 paper2skills 三阶段改造

> 目标：请在当前 `paper2skills` 仓库中完成一个端到端 MVP，使项目能够从 `paper + GitHub repo/tutorial` 中生成更可靠的 Codex skill。不要只做文档说明，要实现可运行代码、测试和示例。此次任务必须一次性覆盖以下三个阶段：
>
> 1. 文档解析层：支持 paper/supplementary/document 到 Markdown + section map + evidence snippets。
> 2. Tutorial-first mining 层：克隆/索引 repo，扫描并筛选 tutorial，抽取 notebook/R/Python workflow 证据。
> 3. Bio contract 推断层：从论文、tutorial、代码和依赖中推断生信输入输出、数据状态和外部资源约束。

---

## 0. 当前问题

当前项目已经有 `collectors/`、`miners/`、`inference/`、`generators/`、`runtime/`、`validators/` 等分层，但仍存在以下限制：

1. `collect_paper()` 基本只支持 `.md/.txt`，不能处理 PDF、DOCX、HTML、supplementary 等常见论文材料。
2. `collect_repo()` 对远程 GitHub URL 只记录 URL，不会 clone、pin commit、索引文件或抽取 evidence bundle。
3. Tutorial mining 目前更接近浅层 step list，尚未形成可审计的 tutorial candidates、workflow trace、input/output evidence。
4. `bio_contract` 字段设计较好，但大部分内容仍是 `not_confirmed`，缺少从 evidence 中自动填充的规则。
5. 输出文件之间的证据链不够强：algorithm contract、bio contract、tutorial trace、environment report 之间没有统一的 `evidence_id` 连接。

本次改造目标不是一次性做成完整 Paper2Agent，而是完成一个稳定、可测试、可扩展的 engineering baseline。

---

## 1. 总体设计原则

### 1.1 Evidence-first

所有推断字段必须绑定 evidence。

如果某个字段没有可靠证据，不允许猜测，必须输出：

```yaml
value: not_confirmed
confidence: low
evidence: []
```

### 1.2 Tutorial-first

论文 Methods 是辅助证据，官方 tutorial / notebook / vignette / example 是执行层的优先证据。扫描优先级：

```text
docs/**
vignettes/**
tutorials/**
examples/**
notebooks/**
README.md / README.rst
**/*.ipynb
**/*.md
**/*.Rmd
**/*.R
**/*.py  # only if no notebook/markdown/vignette tutorial exists
```

### 1.3 Bio-specific

不要只生成普通软件工程 contract。必须显式考虑生信数据约束：

```text
modality
species
genome_build
gene_id_type
matrix_state
matrix_orientation
input_file_type
metadata_keys
condition_key
batch_key
celltype_key
sample_key
perturbation_key
external_resources
statistical_thresholds
expected_outputs
```

### 1.4 Safe-by-default

不得在测试中访问真实网络；需要网络的功能必须可 mock 或用临时本地 git repo 测试。

不得自动安装依赖、下载大数据、执行远程脚本。执行层必须先 preflight，再给出 install plan，除非用户显式确认。

### 1.5 Backward compatible

保留现有 CLI、现有测试和现有输出结构。新增字段和文件可以向后兼容，不要破坏已有 toy demo。

---

## 2. 本次必须新增或修改的模块

### 2.1 新增 `paper2skill/parsers/`

新增目录：

```text
paper2skill/parsers/
  __init__.py
  base.py
  markitdown_parser.py
  plain_text_parser.py
  html_parser.py
  section_segmenter.py
```

#### `base.py`

定义统一数据结构：

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class ParsedSection:
    section_id: str
    title: str
    level: int
    text: str
    source_path: str
    start_line: int | None = None
    end_line: int | None = None

@dataclass
class ParsedDocument:
    source_path: str
    source_type: str
    parser_name: str
    markdown: str
    sections: list[ParsedSection] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
```

定义 parser interface：

```python
class DocumentParser:
    name: str
    supported_suffixes: set[str]

    def can_parse(self, path: Path) -> bool:
        ...

    def parse(self, path: Path) -> ParsedDocument:
        ...
```

#### `markitdown_parser.py`

实现 MarkItDown parser：

- 支持 `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`, `.htm`, `.csv`, `.json`, `.xml`, `.zip`, `.epub`。
- 如果 `markitdown` 未安装，不要报不可读堆栈；返回清晰错误：`MarkItDown is not installed. Install with pip install 'markitdown[pdf,docx,pptx,xlsx]'`。
- 保存 parser warnings。
- 不要在 parser 内调用网络。

#### `plain_text_parser.py`

支持 `.md`, `.txt`, `.rst`。

#### `html_parser.py`

轻量实现即可：

- 优先用 `bs4`，若未安装则 fallback 到简单 tag removal。
- 提取标题结构。

#### `section_segmenter.py`

实现 Markdown section segmentation：

- 根据 `#`, `##`, `###` 切分 section。
- 为每个 section 生成稳定 `section_id`，例如：`paper:methods:preprocessing`。
- 额外识别常见论文 section aliases：

```python
METHOD_ALIASES = ["methods", "method", "materials and methods", "online methods", "experimental procedures"]
DATA_ALIASES = ["data availability", "datasets", "data", "availability"]
CODE_ALIASES = ["code availability", "software availability", "implementation"]
RESULT_ALIASES = ["results", "experiments", "benchmark", "evaluation"]
LIMITATION_ALIASES = ["limitations", "discussion"]
```

---

### 2.2 修改 `paper2skill/collectors/paper_collector.py`

如果当前文件名不同，请在现有 collector 中等价修改。

新增功能：

```python
def collect_paper(paper: str | Path, out_dir: Path | None = None) -> dict:
    """Collect and parse a paper or supplementary document.

    Returns a dict containing:
      - source_path
      - source_type
      - parser_name
      - markdown_path
      - section_map_path
      - parsed_document
      - warnings
    """
```

输出文件：

```text
references/paper.md
references/paper_sections.json
references/paper_parser_report.json
```

`paper_sections.json` 结构：

```json
{
  "source_path": "...",
  "parser_name": "markitdown",
  "sections": [
    {
      "section_id": "paper:methods",
      "title": "Methods",
      "level": 1,
      "start_line": 120,
      "end_line": 260,
      "char_count": 10342
    }
  ],
  "warnings": []
}
```

---

### 2.3 修改 `paper2skill/collectors/repo_collector.py`

当前远程 URL 不应只记录 URL，必须支持 clone 或 archive extraction。

实现：

```python
def collect_repo(repo: str | Path, work_dir: Path, ref: str | None = None) -> dict:
    """Resolve local or remote repository into a local evidence bundle."""
```

要求：

1. 如果是本地路径，直接索引。
2. 如果是 GitHub URL，执行 shallow clone：

```bash
git clone --depth 1 <url> <work_dir>/repo/<repo_name>
```

3. 如果传入 `ref`，checkout 到对应 ref。
4. 记录 commit SHA：

```bash
git -C <repo_path> rev-parse HEAD
```

5. 输出：

```text
references/repo_manifest.json
references/repo_index.json
```

`repo_manifest.json`：

```json
{
  "repo_url": "https://github.com/...",
  "repo_name": "...",
  "local_path": "...",
  "commit_sha": "...",
  "ref": "main",
  "collected_at": "ISO-8601",
  "is_remote": true
}
```

`repo_index.json`：

```json
{
  "files": [
    {
      "path": "docs/tutorial.ipynb",
      "suffix": ".ipynb",
      "size_bytes": 12345,
      "category": "tutorial_candidate"
    }
  ]
}
```

测试不得访问 GitHub。用本地临时 git repo 模拟 remote/local repo 行为。

---

## 3. Tutorial-first mining

### 3.1 新增或重构 `paper2skill/miners/tutorial_scanner.py`

实现：

```python
@dataclass
class TutorialCandidate:
    path: str
    title: str | None
    file_type: str
    priority: int
    include_in_tools: bool
    reason: str
    signals: dict[str, bool]
    evidence_id: str
```

扫描规则：

1. 优先扫描 `docs/**`。
2. notebook / markdown / Rmd / vignette 优先。
3. `.py` 只有在无 `.ipynb/.md/.Rmd` tutorial 时才作为 tutorial 候选。
4. 排除：

```text
tests/**
test/**
benchmark/**
benchmarks/**
perf/**
profile/**
legacy/**
deprecated/**
old/**
templates/**
```

5. 文件名或标题包含以下词汇时，默认 exclude：

```text
legacy
deprecated
outdated
old
archive
```

6. include 标准：

```text
has_code
has_narrative
has_clear_task
has_input_signal
has_output_signal
not_test_or_benchmark
not_deprecated
```

输出：

```text
references/tutorial_candidates.json
references/tutorial_scanner_report.json
```

---

### 3.2 修改 notebook / R / Python miner

目标不是完整执行所有 tutorial，而是先生成可审计 workflow trace。

统一输出 `references/tutorial_trace.json`：

```json
{
  "tutorials": [
    {
      "path": "docs/tutorial.ipynb",
      "title": "Preprocessing and clustering",
      "steps": [
        {
          "step_id": "tutorial_001:cell_003",
          "language": "python",
          "source": "docs/tutorial.ipynb:cell:3",
          "code_preview": "sc.pp.normalize_total(adata)",
          "imports": ["scanpy"],
          "function_calls": ["sc.pp.normalize_total"],
          "read_files": [],
          "write_files": [],
          "input_objects": ["adata"],
          "output_objects": ["adata"],
          "bio_signals": ["normalization", "single_cell"]
        }
      ]
    }
  ]
}
```

Python notebook：

- 用 `nbformat` 读取。
- 代码 cell 用 AST 提取 import、assignment、function call、read/write file。
- Markdown cell 用于标题、任务描述和 evidence snippets。

R script/Rmd：

- 用正则 + 简单 parser 提取：`library()`, `require()`, `<-`, `read.*`, `write.*`, `saveRDS`, `readRDS`, `ggsave`, `pdf`, `png`。
- 识别 Seurat / SingleCellExperiment / DESeq2 / edgeR / clusterProfiler / CellChat / monocle3 / Signac 等常见调用。

---

## 4. Evidence graph

新增：

```text
paper2skill/evidence/
  __init__.py
  evidence_graph.py
```

数据结构：

```python
@dataclass
class EvidenceItem:
    evidence_id: str
    source_type: str  # paper, tutorial, code, dependency, repo
    source_path: str
    locator: str      # line range, cell id, function name, etc.
    text: str
    confidence_hint: str = "medium"

@dataclass
class EvidenceClaim:
    claim_id: str
    field: str
    value: Any
    confidence: str
    evidence_ids: list[str]
    notes: str | None = None
```

输出：

```text
references/evidence_graph.json
```

要求：

- 每个 algorithm contract 和 bio contract 字段都能追溯到 evidence item。
- 没有证据的字段使用 `not_confirmed`。
- 有冲突时记录：

```json
{
  "field": "matrix_state",
  "conflict": true,
  "values": ["raw_counts", "log_normalized"],
  "evidence_ids": ["...", "..."]
}
```

---

## 5. Bio contract 推断

### 5.1 修改 `paper2skill/inference/infer_bio_contract.py`

保留当前 schema，但新增 evidence-aware 推断。

建议输出结构：

```yaml
modality:
  value: scRNA-seq
  confidence: high
  evidence: [tutorial_001:cell_001, paper:methods:line_12]

species:
  value: human
  confidence: medium
  evidence: [paper:datasets]

matrix_state:
  value: raw_counts
  confidence: high
  evidence: [tutorial_001:cell_004]

metadata_keys:
  celltype_key:
    value: cell_type
    confidence: medium
    evidence: [tutorial_001:cell_006]
  batch_key:
    value: batch
    confidence: low
    evidence: []
```

### 5.2 规则库

新增：

```text
paper2skill/inference/bio_rules.py
```

实现 rule-based recognizer：

#### Modality keywords

```python
MODALITY_RULES = {
    "scRNA-seq": ["single-cell RNA", "scRNA-seq", "AnnData", "Seurat", "scanpy", "h5ad", "10x"],
    "spatial_transcriptomics": ["spatial transcriptomics", "Visium", "Slide-seq", "MERFISH", "spatial", "Squidpy"],
    "bulk_RNA-seq": ["bulk RNA", "DESeq2", "edgeR", "limma", "counts matrix"],
    "scATAC-seq": ["scATAC", "Signac", "ArchR", "peak matrix", "fragments.tsv"],
    "multiome": ["multiome", "RNA + ATAC", "paired RNA and ATAC"]
}
```

#### Matrix state rules

```python
MATRIX_STATE_RULES = {
    "raw_counts": ["raw counts", "count matrix", "read_10x_mtx", "Read10X", "counts slot", "layers['counts']"],
    "normalized": ["NormalizeData", "normalize_total", "CPM", "TPM", "size factor"],
    "log1p": ["log1p", "log-normalized", "LogNormalize"],
    "scaled": ["ScaleData", "scale", "z-score", "standardized"]
}
```

#### Gene ID rules

```python
GENE_ID_RULES = {
    "gene_symbol": ["gene symbol", "HGNC", "GeneSymbol", "symbol"],
    "ensembl_id": ["Ensembl", "ENSG", "ENSMUSG"],
    "entrez_id": ["Entrez", "NCBI gene id"]
}
```

#### Species rules

```python
SPECIES_RULES = {
    "human": ["human", "Homo sapiens", "hg19", "hg38", "GRCh37", "GRCh38"],
    "mouse": ["mouse", "Mus musculus", "mm10", "mm39", "GRCm38", "GRCm39"],
    "macaque": ["macaque", "Macaca", "rheMac"]
}
```

### 5.3 Confidence rules

```text
high: exact API/tutorial evidence, e.g. Read10X, sc.read_h5ad, NormalizeData, adata.obs['cell_type']
medium: paper Methods text or README says it explicitly
low: only inferred from package names or weak keywords
not_confirmed: no evidence
```

---

## 6. Algorithm contract 与 IO contract 联动

修改：

```text
paper2skill/inference/infer_algorithm_contract.py
paper2skill/inference/infer_io_contract.py
paper2skill/inference/infer_workflow.py
```

目标：

1. `infer_workflow()` 不再只返回 step list，要返回 source-grounded workflow trace。
2. `infer_io_contract()` 从 tutorial trace 和 bio contract 中补充 input requirements。
3. `infer_algorithm_contract()` 每个核心字段都包含 evidence。

示例：

```yaml
inputs:
  primary_data:
    value: AnnData h5ad file
    required: true
    evidence: [tutorial_001:cell_002]
  metadata_keys:
    celltype_key:
      value: cell_type
      required: false
      evidence: [tutorial_001:cell_006]
```

---

## 7. CLI 改造

检查现有 CLI。如果已有 `build` 或 `generate` 命令，请向后兼容扩展。

目标命令：

```bash
python -m paper2skill.cli build \
  --paper path/to/paper.pdf \
  --repo https://github.com/owner/repo \
  --out outputs/my_skill \
  --tutorial-filter "optional title or path"
```

必须支持：

```bash
python -m paper2skill.cli build \
  --paper path/to/paper.md \
  --repo path/to/local/repo \
  --out outputs/my_skill
```

新增选项：

```text
--repo-ref <branch/tag/sha>
--skip-repo-clone
--no-execute-tutorials
--strict-evidence
```

本次可以默认不执行 tutorial，只生成 trace；如果已有 executor，可只做 dry-run，不得强制真实运行大 notebook。

---

## 8. 输出文件要求

构建完成后，输出目录必须至少包含：

```text
outputs/my_skill/
  SKILL.md
  scripts/
    preflight.py
    plan.py
    run.py
    validate_outputs.py
  references/
    paper.md
    paper_sections.json
    paper_parser_report.json
    repo_manifest.json
    repo_index.json
    tutorial_candidates.json
    tutorial_trace.json
    evidence_graph.json
    algorithm_contract.yaml
    bio_contract.yaml
    io_contract.yaml
    environment_report.json
    install_plan.md
  tests/
```

如果某个输入缺失，例如未提供 paper，则对应文件可以不生成，但必须在 `build_report.json` 中记录原因。

---

## 9. 测试要求

新增测试目录或文件：

```text
tests/test_document_parsers.py
tests/test_section_segmenter.py
tests/test_repo_collector.py
tests/test_tutorial_scanner.py
tests/test_bio_contract_inference.py
tests/test_end_to_end_three_stage_build.py
```

### 9.1 Parser tests

- 用临时 `.md` 文件测试 plain text parser。
- 如果 `markitdown` 未安装，测试应确认错误信息清晰，而不是失败。
- 不要求在 CI 中真实解析大型 PDF。

### 9.2 Repo collector tests

- 用 `tmp_path` 创建本地 git repo。
- commit 一个 README、docs/tutorial.ipynb 或 docs/tutorial.md。
- 调用 `collect_repo()`。
- 验证 `repo_manifest.json` 中有 `commit_sha`。
- 验证 `repo_index.json` 包含 tutorial candidate。

### 9.3 Tutorial scanner tests

测试：

1. `docs/tutorial.ipynb` 应 include。
2. `tests/test_example.py` 应 exclude。
3. `legacy/tutorial.ipynb` 应 exclude。
4. 有 notebook/md 时，裸 `.py` tutorial 不应优先 include。
5. 没有 notebook/md 时，`.py` tutorial 可以 include。

### 9.4 Bio contract tests

输入 synthetic evidence：

```text
sc.read_10x_mtx("data/")
sc.pp.normalize_total(adata)
sc.pp.log1p(adata)
adata.obs["cell_type"]
```

预期：

```yaml
modality: scRNA-seq
matrix_state: raw_counts + normalized + log1p evidence trail
celltype_key: cell_type
```

不要只输出最终一个 matrix_state，要保留 transformation chain：

```yaml
matrix_transformations:
  - raw_counts_loaded
  - normalized
  - log1p_transformed
```

### 9.5 End-to-end test

创建最小项目：

```text
paper.md
repo/
  README.md
  docs/tutorial.ipynb
```

运行 build，验证：

```text
references/paper.md exists
references/paper_sections.json exists
references/repo_manifest.json exists
references/tutorial_candidates.json exists
references/tutorial_trace.json exists
references/evidence_graph.json exists
references/bio_contract.yaml exists
SKILL.md exists
```

---

## 10. README 更新

更新 README，新增章节：

```text
Three-stage evidence pipeline
  Stage 1: document parsing
  Stage 2: tutorial-first mining
  Stage 3: bio contract inference
```

加入一个最小例子：

```bash
python -m paper2skill.cli build \
  --paper examples/minimal_paper.md \
  --repo examples/minimal_repo \
  --out outputs/minimal_skill
```

说明 MarkItDown 是 optional parser backend：

```bash
pip install 'markitdown[pdf,docx,pptx,xlsx]'
```

---

## 11. 禁止项

不要做以下事情：

1. 不要删除已有 tests。
2. 不要让测试依赖真实 GitHub 网络访问。
3. 不要生成无 evidence 的确定性结论。
4. 不要把 README 当作唯一权威证据。
5. 不要在 build 过程中自动安装依赖。
6. 不要默认执行大型 notebook 或下载大型数据。
7. 不要把 toy output 声称为真实算法结果。
8. 不要为了通过测试而 hard-code 某个测试路径。

---

## 12. 推荐实现顺序

请按以下顺序完成，并在每步后运行相关测试：

```text
1. 新增 parsers/base.py、plain_text_parser.py、section_segmenter.py
2. 改造 collect_paper()
3. 改造 collect_repo()，支持本地 repo 和 shallow clone
4. 新增 tutorial_scanner.py
5. 统一 tutorial_trace 输出
6. 新增 evidence_graph.py
7. 改造 infer_bio_contract.py + bio_rules.py
8. 联动 infer_io_contract.py / infer_workflow.py / infer_algorithm_contract.py
9. 更新 generator，使 references 输出完整
10. 更新 CLI
11. 新增 tests
12. 更新 README
13. 运行完整测试
```

---

## 13. 验收命令

Codex 完成后必须运行：

```bash
python -m pytest -q
```

如果项目已有 CLI 测试命令，也运行原命令。

额外运行一个最小 end-to-end demo：

```bash
python -m paper2skill.cli build \
  --paper examples/minimal_paper.md \
  --repo examples/minimal_repo \
  --out /tmp/paper2skill_minimal_skill \
  --no-execute-tutorials
```

检查输出：

```bash
ls /tmp/paper2skill_minimal_skill/references
cat /tmp/paper2skill_minimal_skill/references/bio_contract.yaml
cat /tmp/paper2skill_minimal_skill/references/evidence_graph.json
```

---

## 14. 最终交付说明

完成后，请在最终回复中总结：

1. 修改了哪些文件。
2. 新增了哪些模块。
3. 三阶段 pipeline 如何运行。
4. 哪些测试通过。
5. 哪些功能仍是 MVP 限制。
6. 下一步建议。

不要只给概要；必须提交实际代码变更。
