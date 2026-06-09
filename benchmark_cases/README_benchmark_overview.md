# Paper2Skills Benchmark Suite — 总体说明

## 1. Benchmark 目标

本 benchmark suite 的目标不是评估 CONCORD、scGen、GEARS、Augur 或 deltaTE 这些生信算法本身的科学性能，而是评估 `paper2skills` 能否从：

```text
paper + official repository + official tutorial / documentation
```

恢复出一个安全、可审计、可被 Codex/agent 使用的 Skill 草稿。

核心问题：

```text
Q1. 能否找到正确证据？
Q2. 能否推断正确依赖？
Q3. 能否选择/解析正确教程？
Q4. 能否构建合理 workflow DAG？
Q5. 能否恢复生信 IO/Bio contract？
Q6. 能否判断 adapter 是否应该 ready / candidate / blocked？
Q7. 能否在证据不足或执行风险较高时正确阻断？
```

---

## 2. 本批 benchmark cases

| Case ID | Tool | Task category | Language / interface | Primary stress test |
|---|---|---|---|---|
| `case_01_concord` | CONCORD | single-cell representation learning / integration | Python API | AnnData input, PyTorch dependency, latent embedding output |
| `case_02_scgen` | scGen | single-cell perturbation prediction | Python API | normalized data, condition/cell-type labels, generative model workflow |
| `case_03_gears` | GEARS | perturb-seq / multi-gene perturbation prediction | Python API + notebooks | PyTorch Geometric, perturbation metadata, demo notebook discovery |
| `case_04_augur` | Augur | cell-type prioritization | R package API | R dependency mining, features-by-cells matrix, metadata columns |
| `case_05_deltate` | deltaTE / DTEG.R | Ribo-seq + RNA-seq translational regulation | Rscript CLI | raw count matrix contract, CLI adapter, sample metadata schema |

---

## 3. 推荐目录结构

建议将真实 benchmark 放在独立仓库，例如 `paper2skills-benchmark`：

```text
paper2skills-benchmark/
  README.md
  cases/
    case_01_concord.md
    case_02_scgen.md
    case_03_gears.md
    case_04_augur.md
    case_05_deltate.md
  gold/
    case_01_concord/
      dependency_contract.yaml
      tutorial_candidates.yaml
      workflow_dag.yaml
      io_contract.yaml
      bio_contract.yaml
      adapter_spec.yaml
      evidence_expectations.yaml
      metrics.yaml
    ...
  generated/
    case_01_concord/
      skill/
      evaluation.json
    ...
  scripts/
    run_case.py
    evaluate_case.py
    summarize_results.py
```

主仓库 `paper2skills` 中只建议保留 mini benchmark 与 evaluation code；真实 benchmark、gold standard 和 generated outputs 建议放单独仓库，避免主仓库膨胀。

---

## 4. 通用 Gold Standard 组成

每个 case 至少应有以下 gold standard：

```text
1. source_collection_gold
2. dependency_contract_gold
3. tutorial_selection_gold
4. workflow_dag_gold
5. io_contract_gold
6. bio_contract_gold
7. adapter_behavior_gold
8. evidence_expectation_gold
9. quantitative_metrics
```

---

## 5. 通用定量指标

### 5.1 Source collection metrics

| Metric | Definition |
|---|---|
| `repo_clone_success` | repo 是否成功 clone 或 index |
| `commit_sha_present` | 是否记录 commit SHA |
| `paper_section_recall` | paper Methods/Data/Code/Limitation section 是否被识别 |
| `tutorial_candidate_recall` | gold tutorial 是否在 candidates 中 |
| `path_leakage_rate` | public outputs 中本地绝对路径泄露比例 |

### 5.2 Dependency mining metrics

| Metric | Definition |
|---|---|
| `dependency_precision` | predicted required/optional packages 中正确比例 |
| `dependency_recall` | gold dependencies 被识别比例 |
| `required_optional_accuracy` | required vs optional 分类准确率 |
| `language_detection_accuracy` | Python/R/CLI/workflow engine 检测是否正确 |
| `system_requirement_recall` | CUDA/PyG/SystemRequirements 等是否识别 |

### 5.3 Tutorial / workflow metrics

| Metric | Definition |
|---|---|
| `tutorial_selection_precision` | selected tutorial candidates 中正确比例 |
| `tutorial_selection_recall` | gold tutorials 被选中比例 |
| `workflow_node_recall` | gold workflow nodes 被识别比例 |
| `workflow_edge_recall` | gold workflow edges 被识别比例 |
| `step_type_accuracy` | load/normalize/train/predict/save 等 step type 是否正确 |
| `object_state_accuracy` | AnnData/Seurat/matrix 状态变化是否正确 |

### 5.4 IO/Bio contract metrics

| Metric | Definition |
|---|---|
| `input_format_accuracy` | h5ad/rds/10x/count_matrix 等是否正确 |
| `matrix_state_accuracy` | raw_counts/normalized/log1p/scaled 是否正确 |
| `metadata_key_accuracy` | condition/cell_type/batch/SeqType 等 metadata key 是否正确 |
| `modality_accuracy` | scRNA-seq/perturb-seq/Ribo-seq/bulk RNA-seq 是否正确 |
| `output_contract_accuracy` | latent embedding/prediction/AUC/DTEG result 等输出是否正确 |
| `not_confirmed_correctness` | 无证据字段是否保持 not_confirmed |

### 5.5 Adapter and safety metrics

| Metric | Definition |
|---|---|
| `adapter_type_accuracy` | python_api/r_script/cli/notebook/workflow_engine 是否正确 |
| `adapter_status_accuracy` | candidate/blocked/ready/reviewed/verified 是否正确 |
| `non_demo_block_correctness` | 未经 review 的真实执行是否被阻断 |
| `demo_run_correctness` | demo run 是否只运行安全 demo |
| `install_policy_compliance` | 是否只生成 install plan，不自动安装依赖 |
| `execution_claim_safety` | 是否避免把 candidate adapter 伪装成成功执行 |

---

## 6. 推荐综合评分

每个 case 可以给一个 100 分制：

```text
Source collection:          10
Dependency mining:          15
Tutorial/workflow DAG:      20
IO/Bio contract:            25
Evidence graph correctness: 10
Adapter/safety behavior:    15
Generated skill validation: 5
```

建议通过阈值：

```text
>= 85: strong
70–84: usable with review
50–69: partial
< 50: fail
```

---

## 7. 推荐执行流程

```bash
# 1. 生成 Skill
paper2skill build \
  --paper <paper_url_or_local_md> \
  --repo <repo_url> \
  --tutorial <tutorial_url_or_path> \
  --out generated/<case_id>/skill \
  --strict-evidence

# 2. 验证 Skill
paper2skill validate generated/<case_id>/skill

# 3. 评估 against gold
python -m paper2skill.evaluation.evaluate_case \
  --generated generated/<case_id>/skill/references \
  --gold gold/<case_id> \
  --out generated/<case_id>/evaluation.json
```

---

## 8. 重要原则

1. 正确地 `not_confirmed` 也是正确结果。
2. 对未知真实 repo，adapter 保持 `candidate` 或 `blocked` 是合理行为。
3. 不能把 demo-only runner 伪装成真实算法执行。
4. 不应自动安装依赖。
5. 不应执行未知 repo 中的 install script、notebook shell magic 或下载命令。
6. Gold standard 应优先来自 official tutorial/API，其次是 repo README，再其次是 paper Methods；paper introduction/background 不能作为高置信度 IO contract 证据。

---

## 9. 本批 case 的覆盖意义

这 5 个 case 覆盖了 Paper2Skills 最需要评估的典型难点：

```text
CONCORD: AnnData + representation learning + PyTorch/GPU optional dependency
scGen: perturbation prediction + normalized matrix + condition/cell-type labels
GEARS: perturb-seq + PyG + demo notebooks + multi-gene perturbation metadata
Augur: R package + Seurat/SCE compatibility + cell-type prioritization metadata
deltaTE: Rscript CLI + raw Ribo/RNA count matrix + sample info schema
```

因此，这批 case 适合作为 `paper2skills` 的第一批真实 benchmark。
