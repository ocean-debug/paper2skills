# PRD: Paper2Skill Builder

## 0. 一句话目标

从零开始构建一个 **Paper2Skill Builder**：输入一篇算法论文、官方源代码仓库和官方运行示例，自动生成一个可被 Codex 或其他 coding agent 调用的算法 Skill。生成的子 Skill 必须包含输入/输出规范、证据链、运行计划、环境管理、依赖检查、安装确认、执行脚本、结果验证和最小测试。

本项目不迁移、不兼容、不引用任何旧项目实现，采用 greenfield implementation。

---

## 1. 项目背景与动机

当前很多生物信息学算法论文都配有 GitHub 仓库、tutorial notebook、example script 或 demo data，但这些材料通常分散在论文、README、docs、notebooks、examples 和源码 API 中。用户要真正复用一个算法，往往需要解决以下问题：

1. 论文中描述的是方法逻辑，仓库中暴露的是实际 API，两者经常不完全一致。
2. README 通常只提供安装和简单示例，不足以指导 agent 稳定调用算法。
3. 官方 tutorial/notebook 才最接近可运行流程，但其步骤、参数、输入输出和环境假设没有被结构化。
4. 生物信息学算法对环境依赖极强，例如 Python/R 包、Bioconductor、系统库、conda 环境、CUDA、Jupyter、Rscript 等。
5. Codex 或其他 agent 如果只读论文和 README，很容易误用输入状态、混淆 raw counts 与 normalized matrix、错误选择物种/基因 ID、跳过 QC，或者在依赖缺失时直接失败。
6. 生成的 Skill 不能只是说明文档，还应该能执行 preflight、plan、run、validate，并在缺失依赖时给出明确安装方案。

因此，本项目的核心目标是把“算法论文 + 官方源码 + 官方运行示例”转化为一个结构化、可验证、可运行、可被 agent 调用的算法 Skill。

---

## 2. 产品定位

### 2.1 产品名称

建议包名和项目名：

```text
paper2skill
```

建议核心 Skill 名称：

```text
paper2skill-builder
```

### 2.2 产品定义

Paper2Skill Builder 是一个用于生成算法 Skill 的工程工具。

它不是：

- 不是论文总结器；
- 不是通用组学分析 agent；
- 不是直接替代用户运行所有分析的黑盒平台；
- 不是一开始就做 MCP server 或 Codex plugin；
- 不是根据 abstract 生成伪 workflow 的工具。

它是：

- 一个 evidence-first 的 Skill 生成器；
- 一个从官方运行示例中挖掘算法执行流程的工具；
- 一个为 Codex/agent 生成可调用算法 Skill 的 builder；
- 一个能够管理子 Skill 环境依赖、运行前检查和安装确认的框架。

### 2.3 第一阶段输出形态

优先输出 Codex Skill。

生成的子 Skill 应位于：

```text
.agents/skills/<generated-skill-name>/
```

一个 Codex Skill 是一个目录，必须包含 `SKILL.md`，并可包含 `scripts/`、`references/`、`assets/`、`agents/openai.yaml` 等文件。Paper2Skill Builder 生成的子 Skill 必须充分利用这些目录，而不是只生成一个说明文档。

### 2.4 后续扩展

第一版不实现 MCP server 和 plugin，但架构要预留导出层：

```text
paper2skill export-mcp
paper2skill package-plugin
```

---

## 3. 目标用户

### 3.1 主要用户

1. 生物信息学研究者  
   希望把新的算法论文和官方代码转成可复用分析 Skill。

2. 算法开发者  
   希望把自己的算法仓库包装成 Codex 可调用的标准 Skill。

3. Agent / Codex 使用者  
   希望 Codex 能稳定调用某个算法，而不是每次重新读 README 和 notebook。

4. 多组学 workflow 构建者  
   希望把多个算法 Skill 组合为更大的分析 workflow。

### 3.2 典型使用场景

#### 场景 A：根据论文和 GitHub 生成 Skill

用户提供：

```text
paper: path/to/paper.pdf
repo: https://github.com/xxx/algorithm
tutorial: examples/demo.ipynb
```

系统生成：

```text
.agents/skills/algorithm-name-task/
```

#### 场景 B：Codex 调用生成的子 Skill

用户在 Codex 中说：

```text
$algorithm-name-task
请用这个 Skill 检查我的输入数据是否符合算法要求，并生成运行计划。
```

子 Skill 应先执行 `scripts/preflight.py`，检查输入文件、参数和环境依赖。

#### 场景 C：依赖缺失时询问用户是否安装

子 Skill 检查环境后发现缺少依赖：

```text
Missing Python packages:
- scanpy
- anndata
- leidenalg

Missing R packages:
- Seurat
```

系统必须停止执行，生成安装方案，并询问用户：

```text
检测到依赖缺失。是否允许自动安装？
选项：
1. 在当前环境安装
2. 创建独立 conda/mamba 环境
3. 只输出安装命令，不安装
4. 取消运行
```

未经用户明确确认，不能自动安装任何包。

---

## 4. 核心原则

### 4.1 从零开始

本项目不依赖旧项目代码、目录结构或命名。可以借鉴旧讨论中的思想，但不能保留旧项目的历史负担。

### 4.2 Skill first, plugin later

第一阶段只做 Codex Skill 生成。Plugin 和 MCP 作为后续可选导出目标，不进入 MVP。

### 4.3 Tutorial first

证据优先级必须固定为：

```text
1. 官方 tutorial notebook / example script / demo
2. 官方 docs / vignette
3. 源码 API / function signatures / docstrings
4. dependency files / environment files
5. paper Methods
6. paper abstract
7. README
```

README 只能作为导航证据，不应成为核心 workflow、参数或输入输出声明的唯一依据。

### 4.4 Environment first

生成的子 Skill 在任何 run 之前都必须执行环境检查。缺失依赖时必须先报告并等待用户确认。

### 4.5 Evidence traceability

每个重要结论都需要 evidence：

- 算法分类；
- 输入要求；
- 输出要求；
- 参数默认值；
- workflow step；
- DAG edge；
- 环境依赖；
- 安装命令来源；
- tutorial 运行示例来源。

### 4.6 Honest maturity

生成的子 Skill 必须标注成熟度。不能把只会 dry-run 的 Skill 标记为可执行。

---

## 5. MVP 范围

### 5.1 MVP 必须支持

1. Python 项目：
   - `requirements.txt`
   - `pyproject.toml`
   - `setup.py`
   - notebook / `.py` tutorial

2. R 项目：
   - `DESCRIPTION`
   - `renv.lock`
   - `.R` script
   - `.Rmd` 或 notebook-style example

3. 论文输入：
   - PDF 文件；
   - article URL；
   - paper title + repo URL；
   - 本地 markdown/text 论文内容。

4. 运行示例输入：
   - `.ipynb`
   - `.py`
   - `.R`
   - `.Rmd`

5. 生成 Codex Skill：
   - `SKILL.md`
   - `scripts/preflight.py`
   - `scripts/env_manager.py`
   - `scripts/plan.py`
   - `scripts/run.py`
   - `scripts/validate_outputs.py`
   - `references/evidence_report.md`
   - `references/paper_summary.md`
   - `references/api_reference.md`
   - `references/tutorial_trace.md`
   - `references/tutorial_trace.json`
   - `assets/input_manifest_template.yaml`
   - `assets/config_template.yaml`
   - `assets/environment_spec.yaml`
   - `tests/test_preflight.py`
   - `tests/test_environment.py`
   - `tests/test_plan.py`
   - `agents/openai.yaml`

6. 环境检查：
   - 检查 Python 可执行文件；
   - 检查 Python package 是否可 import；
   - 检查 Rscript 是否存在；
   - 检查 R package 是否 installed；
   - 检查命令行工具是否存在；
   - 输出缺失依赖；
   - 生成安装建议；
   - 未经用户确认不安装。

7. CLI 命令：
   - `paper2skill plan`
   - `paper2skill build`
   - `paper2skill validate`
   - `paper2skill test`
   - `paper2skill inspect-env`

### 5.2 MVP 不做

1. 不做 MCP server 生成；
2. 不做 Codex plugin 打包；
3. 不做大规模自动下载数据；
4. 不做自动修复所有 tutorial 运行错误；
5. 不做多论文合并；
6. 不做 full Snakemake/Nextflow pipeline 生成；
7. 不做 GPU/CUDA 自动配置；
8. 不做自动选择替代算法；
9. 不做没有官方源码或官方运行示例的完整可执行 Skill；
10. 不做未经用户确认的依赖安装。

---

## 6. 系统架构

### 6.1 顶层目录结构

```text
paper2skill/
  README.md
  pyproject.toml
  prd.md

  paper2skill/
    __init__.py
    cli.py

    collectors/
      __init__.py
      paper_collector.py
      repo_collector.py
      tutorial_collector.py

    miners/
      __init__.py
      paper_miner.py
      api_miner.py
      notebook_miner.py
      script_miner.py
      r_miner.py
      dependency_miner.py
      environment_miner.py

    inference/
      __init__.py
      classify_algorithm.py
      infer_io_contract.py
      infer_parameters.py
      infer_workflow.py
      infer_bio_contract.py
      infer_environment.py

    generators/
      __init__.py
      codex_skill_generator.py
      skill_markdown_generator.py
      script_generator.py
      test_generator.py
      report_generator.py

    validators/
      __init__.py
      schema_validator.py
      skill_validator.py
      env_validator.py
      tutorial_validator.py
      output_validator.py

    runtime/
      __init__.py
      env_manager.py
      python_probe.py
      r_probe.py
      install_planner.py
      command_runner.py

    schemas/
      algorithm_skill_schema.yaml
      bio_contract_schema.yaml
      evidence_schema.yaml
      environment_schema.yaml
      tutorial_trace_schema.yaml

    templates/
      codex_skill/
        SKILL.md.j2
        scripts/
          preflight.py.j2
          env_manager.py.j2
          plan.py.j2
          run.py.j2
          validate_outputs.py.j2
        references/
          evidence_report.md.j2
          paper_summary.md.j2
          api_reference.md.j2
          tutorial_trace.md.j2
        assets/
          input_manifest_template.yaml.j2
          config_template.yaml.j2
          environment_spec.yaml.j2
        tests/
          test_preflight.py.j2
          test_environment.py.j2
          test_plan.py.j2
        agents/
          openai.yaml.j2

  .agents/
    skills/
      paper2skill-builder/
        SKILL.md
        scripts/
          build_skill.py
        references/
          generated_skill_schema.yaml
          environment_management_policy.md

  tests/
    fixtures/
      toy_python_algorithm/
      toy_r_algorithm/
      toy_notebook.ipynb
      toy_script.py
      toy_script.R
    test_collectors.py
    test_miners.py
    test_environment.py
    test_generator.py
    test_generated_skill.py
```

---

## 7. CLI 设计

### 7.1 `paper2skill plan`

只分析输入，不生成 Skill 文件。

```bash
paper2skill plan \
  --paper path/to/paper.pdf \
  --repo https://github.com/org/repo \
  --tutorial examples/demo.ipynb \
  --out paper2skill_plan/
```

输出：

```text
paper2skill_plan/
  source_manifest.json
  paper_evidence.json
  repo_evidence.json
  tutorial_trace.json
  algorithm_contract.preview.yaml
  environment_report.json
  build_plan.md
```

### 7.2 `paper2skill build`

生成 Codex Skill。

```bash
paper2skill build \
  --paper path/to/paper.pdf \
  --repo https://github.com/org/repo \
  --tutorial examples/demo.ipynb \
  --skill-name algorithm-task \
  --out .agents/skills/algorithm-task
```

### 7.3 `paper2skill validate`

验证生成的 Skill 结构、schema、证据链、环境策略和测试文件是否完整。

```bash
paper2skill validate \
  --skill .agents/skills/algorithm-task
```

### 7.4 `paper2skill test`

运行生成 Skill 的测试。

```bash
paper2skill test \
  --skill .agents/skills/algorithm-task \
  --mode preflight
```

支持模式：

```text
preflight
environment
plan
demo
all
```

### 7.5 `paper2skill inspect-env`

独立检查某个算法 Skill 的环境依赖。

```bash
paper2skill inspect-env \
  --skill .agents/skills/algorithm-task \
  --manifest input_manifest.yaml
```

---

## 8. 输入规范

### 8.1 Builder 输入

```yaml
paper:
  path: path/to/paper.pdf
  url: null
  title: null

repo:
  url: https://github.com/org/repo
  local_path: null
  ref: main

tutorial:
  paths:
    - examples/demo.ipynb
  mode: official_example

output:
  skill_name: algorithm-task
  out_dir: .agents/skills/algorithm-task

options:
  target: codex_skill
  allow_network: false
  install_policy: ask
  maturity_target: L1
```

### 8.2 子 Skill 输入

每个生成的子 Skill 必须要求用户提供 `input_manifest.yaml`。

示例：

```yaml
inputs:
  primary_data:
    path: data/demo.h5ad
    format: h5ad
    exists: true

  metadata:
    celltype_key: cell_type
    sample_key: sample
    condition_key: condition

  algorithm:
    mode: demo_or_user_data
    parameters:
      target_gene: STAT3
      n_neighbors: 30

environment:
  preferred_manager: conda
  environment_name: algorithm-task-env
  install_policy: ask
```

---

## 9. 生成的子 Skill 目录规范

```text
.agents/skills/<skill-name>/
  SKILL.md

  scripts/
    preflight.py
    env_manager.py
    plan.py
    run.py
    validate_outputs.py

  references/
    evidence_report.md
    paper_summary.md
    repo_summary.md
    api_reference.md
    tutorial_trace.md
    tutorial_trace.json
    environment_report.json
    install_plan.md

  assets/
    input_manifest_template.yaml
    config_template.yaml
    environment_spec.yaml
    requirements.txt
    environment.yml
    renv.lock.placeholder
    demo_input_manifest.yaml

  tests/
    test_preflight.py
    test_environment.py
    test_plan.py
    test_output_contract.py

  agents/
    openai.yaml
```

---

## 10. 生成的 `SKILL.md` 要求

`SKILL.md` 必须是 Codex 可读、可执行、边界清晰的操作说明。

### 10.1 Front matter

```markdown
---
name: <skill-name>
description: Use this skill to plan, validate, run, and interpret <algorithm-name> for <task>. Trigger when the user asks to use <algorithm-name>, reproduce its official tutorial, or apply the algorithm to compatible input data.
---
```

### 10.2 必须包含章节

```markdown
# <Algorithm> Skill

## What this skill does

## When to use

## When not to use

## Required inputs

## Input state requirements

## Environment policy

## Preflight workflow

## Planning workflow

## Execution workflow

## Output contract

## Validation workflow

## Interpretation boundary

## Failure modes

## Evidence sources
```

### 10.3 Environment policy 必须写明

```markdown
Before running the algorithm, always execute `scripts/preflight.py`.

If dependencies are missing:
1. Stop execution.
2. Report missing Python packages, R packages, executables, and system-level requirements.
3. Show install options generated by `scripts/env_manager.py plan`.
4. Ask the user whether to install automatically.
5. Do not install anything unless the user explicitly approves.
6. If the user declines, provide manual installation commands and keep the run blocked.
```

---

## 11. 环境管理需求

### 11.1 总体规则

生成的子 Skill 必须内置环境管理能力。

环境管理由以下文件负责：

```text
scripts/env_manager.py
assets/environment_spec.yaml
references/environment_report.json
references/install_plan.md
tests/test_environment.py
```

### 11.2 依赖检测

必须检测以下类型：

#### Python

- Python executable；
- Python version；
- pip 是否可用；
- required Python packages；
- import name 与 package name 的映射；
- extras 和 version specifier 处理。

例如：

```text
scanpy[leiden]>=1.10; python_version >= "3.10"
```

检测 import 时必须：

```text
package spec: scanpy[leiden]>=1.10; python_version >= "3.10"
import probe: scanpy
preserve original spec in install command
```

#### R

- Rscript 是否可用；
- R version；
- required CRAN packages；
- required Bioconductor packages；
- `DESCRIPTION`、`renv.lock`、tutorial `library()` 和 `require()` 调用。

#### CLI executables

- command 是否在 PATH；
- 版本命令，例如 `tool --version`；
- 是否来自 conda environment。

#### Optional

MVP 可以只记录但不自动处理：

- CUDA；
- system libraries；
- Java；
- compilers；
- external databases；
- reference genomes；
- large model weights。

### 11.3 环境报告

`preflight.py` 必须输出：

```text
qc/environment_report.json
qc/missing_dependencies.json
references/install_plan.md
```

`environment_report.json` 示例：

```json
{
  "status": "blocked_dependencies_missing",
  "python": {
    "executable": "/usr/bin/python",
    "version": "3.11.8",
    "packages": [
      {
        "name": "scanpy[leiden]>=1.10",
        "import_name": "scanpy",
        "installed": false,
        "required": true
      }
    ]
  },
  "r": {
    "rscript_available": true,
    "packages": [
      {
        "name": "Seurat",
        "installed": false,
        "source": "CRAN_or_unknown"
      }
    ]
  },
  "executables": [],
  "install_policy": "ask"
}
```

### 11.4 安装策略

支持四种策略：

```text
never
ask
current_env
isolated_env
```

默认必须是：

```text
ask
```

但在非交互式测试或 CI 中，`ask` 必须退化为：

```text
never
```

也就是不能在 CI 中自动安装。

### 11.5 安装选项

当依赖缺失时，`env_manager.py plan` 必须生成：

```text
Option A: install into current environment
Option B: create isolated venv
Option C: create conda/mamba environment
Option D: manual install only
Option E: cancel
```

示例：

```bash
python scripts/env_manager.py plan \
  --manifest input_manifest.yaml \
  --out qc/install_plan.json
```

如果用户明确同意：

```bash
python scripts/env_manager.py install \
  --strategy isolated_env \
  --confirm yes
```

必须要求 `--confirm yes`，否则退出。

### 11.6 安装命令优先级

安装命令来源优先级：

```text
1. 官方 docs/tutorial 中的安装命令
2. environment.yml / conda.yml
3. requirements.txt / pyproject.toml / setup.py
4. DESCRIPTION / renv.lock
5. README
6. 自动推断 fallback
```

不能无脑使用 `pip install <repo-name>`。

### 11.7 安装后复检

安装完成后必须重新执行：

```bash
python scripts/preflight.py --manifest input_manifest.yaml
```

只有复检通过，才能进入 run。

---

## 12. 论文解析需求

### 12.1 输出文件

```text
references/paper_summary.md
references/paper_evidence.json
```

### 12.2 必须抽取

```yaml
paper:
  title:
  doi:
  year:
  authors:
  official_code:
  official_data:
  method_purpose:
  algorithm_type:
  input_data:
  output_data:
  core_steps:
  key_parameters:
  benchmark_datasets:
  evaluation_metrics:
  limitations:
```

### 12.3 论文证据边界

论文主要用于：

- 方法目的；
- 生物学/算法背景；
- benchmark 指标；
- 解释边界；
- 方法适用范围。

论文不应作为唯一依据来确定：

- 运行命令；
- 真实 API；
- 包安装方式；
- 输入文件路径；
- 参数默认值；
- workflow 执行顺序。

这些应优先来自 tutorial、docs 和源码。

---

## 13. 源码解析需求

### 13.1 输出文件

```text
references/repo_summary.md
references/api_reference.md
references/repo_evidence.json
```

### 13.2 必须解析

```yaml
repo:
  language:
  package_type:
  install_files:
  dependency_files:
  entrypoints:
  cli_commands:
  api_functions:
  classes:
  tutorials:
  notebooks:
  examples:
  docs:
```

### 13.3 API 解析

Python：

- AST 解析 `def`、`class`、import；
- docstring；
- function signature；
- default parameters；
- file read/write；
- package imports。

R：

- 函数定义；
- `library()` / `require()`；
- `read.csv` / `readRDS` / `read_h5ad`；
- `write.csv` / `saveRDS`；
- R package DESCRIPTION；
- exported functions from NAMESPACE。

---

## 14. Tutorial Trace Mining 需求

### 14.1 Tutorial 是最高优先级证据

必须优先使用官方 tutorial / example / notebook 推断：

- workflow steps；
- step order；
- input/output；
- default parameters；
- execution mode；
- expected outputs；
- demo data；
- required environment。

### 14.2 输出文件

```text
references/tutorial_trace.json
references/tutorial_trace.md
```

### 14.3 Notebook trace

对 `.ipynb` 必须解析：

```yaml
cells:
  - index:
    cell_type:
    source:
    imports:
    assignments:
    function_calls:
    file_reads:
    file_writes:
    parameters:
    plots:
```

### 14.4 Script trace

对 `.py`、`.R` 必须解析：

```yaml
script:
  path:
  language:
  imports:
  functions:
  top_level_steps:
  parameters:
  file_reads:
  file_writes:
```

### 14.5 Workflow step inference

每个 step 必须包含：

```yaml
id:
name:
description:
source:
source_type:
evidence_id:
inputs:
outputs:
parameters:
command_or_code:
confidence:
```

---

## 15. Algorithm Contract 需求

生成的子 Skill 必须包含 machine-readable contract：

```text
references/algorithm_contract.yaml
```

示例：

```yaml
algorithm:
  name: CellOracle
  task: in_silico_tf_perturbation
  domain: bioinformatics
  modality: single_cell_transcriptomics
  language: python
  execution_mode: python_api
  maturity_level: L1

input_contract:
  required:
    - name: input_data
      type: h5ad
      state: raw_or_normalized
    - name: celltype_key
      type: string
    - name: perturbation_targets
      type: list[string]

output_contract:
  required:
    - qc/environment_report.json
    - qc/input_validation.json
    - results/
    - report.md

environment_contract:
  install_policy_default: ask
  preflight_required: true
  auto_install_requires_confirmation: true
```

---

## 16. Bioinformatics Contract 需求

生成的子 Skill 如属于生物信息学算法，必须包含：

```text
references/bio_contract.yaml
```

字段：

```yaml
bio_contract:
  modality:
    primary:
    secondary:

  organism:
    species_supported:
    genome_build:
    gene_id_type:

  input_matrix_state:
    raw_counts_required:
    normalized_allowed:
    log_transformed_allowed:
    matrix_orientation:

  metadata_requirements:
    celltype_key:
    sample_key:
    batch_key:
    condition_key:

  minimum_data_requirements:
    min_cells:
    min_genes:
    min_cells_per_group:

  reference_resources:
    genome:
    annotation:
    database:
    grn:
    ligand_receptor_database:

  statistical_contract:
    multiple_testing:
    fdr_threshold:
    metric:

  interpretation_boundary:
    dry_run_is_not_biological_result: true
    demo_run_is_not_user_data_validation: true
    cross_species_mapping_requires_confirmation: true
```

如果证据不足，字段必须写：

```text
not_confirmed
```

不能自动猜测。

---

## 17. Skill 成熟度分级

每个生成的子 Skill 必须标注 maturity。

```yaml
maturity:
  level: L1
  status: contract_and_preflight
```

### L0: summary only

只有论文/方法说明，无可执行脚本。

### L1: contract + preflight

有输入输出 contract、环境检查、运行计划，但不保证能跑官方 demo。

### L2: demo executable

能跑通官方 tutorial/demo 的最小路径。

### L3: user-data executable

能应用到用户提供的真实数据，并有明确输入状态检查。

### L4: benchmarked

有 reference output、regression test、关键数值/表格/图形对齐。

### L5: agent-ready

可被 Codex 或其他 agent 稳定调用，具备完整错误恢复和解释边界。

MVP 目标：

```text
稳定生成 L1；
至少 1 个 toy Python 算法达到 L2；
至少 1 个 toy R 算法达到 L2。
```

---

## 18. 子 Skill 脚本行为规范

### 18.1 `scripts/preflight.py`

职责：

1. 读取 input manifest；
2. 检查输入路径；
3. 检查输入状态字段；
4. 检查环境依赖；
5. 检查必需参数；
6. 输出 QC JSON；
7. 如果依赖缺失，状态为 `blocked_dependencies_missing`。

不能执行主算法。

### 18.2 `scripts/env_manager.py`

职责：

1. 解析 environment spec；
2. 检测 Python/R/CLI 依赖；
3. 生成安装计划；
4. 在用户确认后执行安装；
5. 安装后复检。

命令：

```bash
python scripts/env_manager.py inspect
python scripts/env_manager.py plan
python scripts/env_manager.py install --strategy isolated_env --confirm yes
```

### 18.3 `scripts/plan.py`

职责：

1. 读取 manifest；
2. 读取 tutorial trace；
3. 生成 workflow execution plan；
4. 不运行主算法；
5. 输出 `workflow/plan.json` 和 `workflow/plan.md`。

### 18.4 `scripts/run.py`

职责：

1. 必须先调用 preflight；
2. 如果 preflight 不通过，停止；
3. 如果环境缺失，停止；
4. 如果用户未确认安装，停止；
5. 运行 demo 或用户数据路径；
6. 输出结果目录；
7. 输出 `result.json`。

### 18.5 `scripts/validate_outputs.py`

职责：

1. 检查 expected outputs；
2. 检查关键表格/图形/JSON 是否存在；
3. 对 demo run 可检查 reference output；
4. 输出 `qc/output_validation.json`。

---

## 19. 子 Skill 输出结果规范

运行后必须输出：

```text
result/
  README.md
  report.md
  result.json

  qc/
    input_validation.json
    environment_report.json
    missing_dependencies.json
    output_validation.json
    qc_summary.json

  workflow/
    plan.json
    plan.md
    executed_steps.json

  parameters/
    resolved_parameters.json
    parameter_sources.json

  results/
    <algorithm outputs>

  logs/
    preflight.log
    env_manager.log
    run.log

  reproducibility/
    source_manifest.json
    algorithm_contract.yaml
    bio_contract.yaml
    environment_spec.yaml
    command_history.sh
```

`result.json` 必须包含：

```json
{
  "status": "pass | warn | fail | blocked_dependencies_missing | blocked_input_invalid",
  "skill_name": "",
  "algorithm": "",
  "maturity_level": "",
  "input_validation": {},
  "environment": {},
  "parameter_resolution": {},
  "workflow_summary": {},
  "outputs": [],
  "caveats": [],
  "evidence_used": []
}
```

---

## 20. 测试需求

### 20.1 Builder 测试

必须有：

```text
tests/test_collectors.py
tests/test_notebook_miner.py
tests/test_script_miner.py
tests/test_dependency_miner.py
tests/test_environment.py
tests/test_generator.py
tests/test_generated_skill.py
```

### 20.2 生成子 Skill 的测试

每个子 Skill 必须生成：

```text
tests/test_preflight.py
tests/test_environment.py
tests/test_plan.py
tests/test_output_contract.py
```

### 20.3 环境测试

必须测试：

1. 所有依赖存在 → preflight pass；
2. 缺少 Python 包 → blocked_dependencies_missing；
3. 缺少 R 包 → blocked_dependencies_missing；
4. 缺少 Rscript → blocked_runtime_missing；
5. 非交互模式下不自动安装；
6. 未传 `--confirm yes` 不安装；
7. 安装计划能正确保留原始 package spec；
8. `scanpy[leiden]` 这类 extras 能正确 strip import name；
9. R package 能通过 `Rscript -e` 检测。

### 20.4 模拟缺失依赖

支持环境变量：

```text
PAPER2SKILL_FORCE_MISSING_PACKAGES=scanpy,Seurat
PAPER2SKILL_FORCE_MISSING_EXECUTABLES=Rscript
```

用于测试 blocked 状态。

---

## 21. 安全与边界

### 21.1 安装安全

1. 不自动安装；
2. 不自动升级用户环境中的包；
3. 不自动删除或覆盖已有环境；
4. 不自动运行未知 shell script；
5. 不自动执行 repository 中的 arbitrary install script；
6. 安装命令必须写入 `install_plan.md`；
7. 用户确认后才执行。

### 21.2 数据安全

1. 不自动上传用户数据；
2. 不把用户数据路径写入公开文档；
3. 不自动下载大型数据集；
4. 不自动修改原始输入文件。

### 21.3 生物学解释边界

生成 Skill 必须明确：

```text
dry-run 结果不是生物学结果；
demo run 只证明 tutorial 路径可运行；
用户数据分析必须通过输入状态检查；
跨物种、跨平台、跨 assay 迁移需要用户确认；
缺少证据时必须标记 not_confirmed。
```

---

## 22. README 要求

项目 README 必须包含：

1. 项目定位；
2. 为什么不是论文总结器；
3. 为什么优先生成 Codex Skill；
4. 安装方式；
5. 快速开始；
6. 输入示例；
7. 输出 Skill 结构；
8. 环境管理策略；
9. maturity level；
10. toy Python demo；
11. toy R demo；
12. 开发路线图。

---

## 23. Codex Skill: `paper2skill-builder`

项目本身要提供一个 Codex Skill，用于让 Codex 调用 Paper2Skill Builder。

目录：

```text
.agents/skills/paper2skill-builder/
  SKILL.md
  scripts/
    build_skill.py
  references/
    generated_skill_schema.yaml
    environment_management_policy.md
  agents/
    openai.yaml
```

`SKILL.md` front matter：

```markdown
---
name: paper2skill-builder
description: Use this skill when the user wants to generate a Codex skill from an algorithm paper, official source code repository, and official tutorial or example. The generated skill must include environment preflight, dependency checks, install planning, execution planning, output validation, and evidence reports.
---
```

---

## 24. Codex `/plan` 提示词

把本 PRD 放进仓库后，先让 Codex 执行：

```text
/plan

请阅读 prd.md，并为从零实现 Paper2Skill Builder 制定工程计划。

要求：
1. 不引用任何旧项目。
2. 第一阶段只做 Codex Skill 生成，不做 MCP 和 plugin。
3. 必须实现环境管理：生成的子 Skill 在 run 前先检查依赖；缺少包时先报告并询问用户是否安装；未经确认不得自动安装。
4. 先支持 Python 和 R 算法仓库。
5. 先实现 toy Python 和 toy R demo。
6. 请输出 PR 拆分、文件结构、实现顺序、测试命令和验收标准。
```

---

## 25. Codex `/goal` 提示词：Milestone 1

```text
/goal

Milestone 1: Build the greenfield Paper2Skill Builder skeleton.

Read prd.md first and implement only the MVP skeleton.

Scope:
- Do not import or reference any previous project.
- Do not implement MCP or plugin export.
- Implement the package structure, CLI skeleton, schemas, templates, and the repository-level Codex skill `paper2skill-builder`.
- Add toy Python and toy R fixtures.
- Add basic tests for CLI availability, schema loading, and generated skill scaffold.

Required outputs:
1. paper2skill/ Python package.
2. CLI commands: plan, build, validate, test, inspect-env.
3. .agents/skills/paper2skill-builder/SKILL.md.
4. schemas for algorithm skill, bio contract, evidence, environment, tutorial trace.
5. templates for generated Codex skills.
6. tests with toy fixtures.

Definition of done:
- `python -m paper2skill.cli --help` works.
- `paper2skill build` can scaffold a toy generated skill.
- Generated skill contains SKILL.md, scripts/preflight.py, scripts/env_manager.py, scripts/plan.py, scripts/run.py, scripts/validate_outputs.py, references, assets, tests, and agents/openai.yaml.
- Unit tests pass.
```

---

## 26. Codex `/goal` 提示词：Milestone 2

```text
/goal

Milestone 2: Implement environment management for generated child skills.

Read prd.md and implement the environment management requirements.

Scope:
- Add dependency detection for Python, R, and CLI executables.
- Generated child skills must run preflight before run.
- Missing dependencies must block execution.
- The system must generate install plans and ask for user confirmation before installation.
- No automatic install without `--confirm yes`.

Required behavior:
1. Detect Python packages using importlib.util.find_spec.
2. Strip extras/version markers for import probing but preserve original specs for installation.
3. Detect R packages using Rscript.
4. Detect missing Rscript.
5. Generate environment_report.json, missing_dependencies.json, install_plan.md.
6. Support install policies: never, ask, current_env, isolated_env.
7. In non-interactive mode, ask must behave as never.
8. Add tests using PAPER2SKILL_FORCE_MISSING_PACKAGES and PAPER2SKILL_FORCE_MISSING_EXECUTABLES.

Definition of done:
- Missing scanpy triggers blocked_dependencies_missing.
- Missing Seurat triggers blocked_dependencies_missing.
- Missing Rscript triggers blocked_runtime_missing.
- No install command runs without explicit `--confirm yes`.
- All environment tests pass.
```

---

## 27. Codex `/goal` 提示词：Milestone 3

```text
/goal

Milestone 3: Implement tutorial trace mining and workflow inference.

Read prd.md and implement tutorial-first evidence extraction.

Scope:
- Parse .ipynb, .py, .R, and .Rmd examples.
- Extract imports, assignments, function calls, file reads, file writes, parameters, and execution order.
- Generate tutorial_trace.json and tutorial_trace.md.
- Use tutorial trace as highest-priority evidence for workflow steps.

Definition of done:
- Toy notebook trace includes ordered code cells.
- Toy Python script trace includes imports, calls, reads, writes.
- Toy R script trace includes library calls and function calls.
- Generated child skill workflow steps cite tutorial evidence.
- Tests pass.
```

---

## 28. 验收标准

MVP 完成时，必须满足：

1. 可以从 toy Python 算法生成一个 Codex Skill；
2. 可以从 toy R 算法生成一个 Codex Skill；
3. 生成的 Skill 能执行 preflight；
4. 依赖缺失时能正确 block；
5. 依赖缺失时能生成安装计划；
6. 未确认时不自动安装；
7. 生成的 Skill 有完整 `SKILL.md`；
8. 生成的 Skill 有 environment manager；
9. 生成的 Skill 有 evidence report；
10. 生成的 Skill 有 tutorial trace；
11. 生成的 Skill 有 tests；
12. Builder 自身测试通过。

---

## 29. 非目标

以下内容不应在 MVP 中实现：

```text
MCP server
Codex plugin packaging
自动运行任意外部 install.sh
大规模真实数据下载
GPU/CUDA 自动配置
复杂 workflow engine 生成
多算法组合 workflow
无 tutorial 情况下声称 native executable
无用户确认自动安装
```

---

## 30. 最终交付物

```text
paper2skill/
  prd.md
  README.md
  pyproject.toml
  paper2skill/
  .agents/skills/paper2skill-builder/
  tests/
```

运行命令：

```bash
python -m paper2skill.cli --help
python -m paper2skill.cli build --example toy_python
python -m paper2skill.cli validate --skill .agents/skills/toy-python-skill
python -m paper2skill.cli test --skill .agents/skills/toy-python-skill --mode all
```

最终目标：

```text
Paper2Skill Builder 能把算法论文、官方源码和官方运行示例转化为一个 Codex 可调用的算法 Skill。
生成的子 Skill 在运行前必须检查环境，缺少依赖时必须询问用户是否安装，并且未经用户明确确认不得自动安装。
```
