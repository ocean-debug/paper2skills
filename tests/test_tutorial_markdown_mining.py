from __future__ import annotations

from paper2skill.miners.script_miner import mine_script
from paper2skill.miners.tutorial_scanner import scan_tutorial_candidates


def test_markdown_heading_sections_are_tutorial_candidates(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        """
# Demo package

## Usage

Run the workflow on input files.

```bash
Rscript --vanilla run.R counts.tsv metadata.tsv
```

## Demonstration

This section describes expected output.
""".strip()
        + "\n",
        encoding="utf-8",
    )

    scan = scan_tutorial_candidates(tmp_path)
    paths = {item.path for item in scan["candidates"]}
    titles = {item.section_title for item in scan["candidates"]}

    assert "README.md#usage" in paths
    assert "README.md#demonstration" in paths
    assert "Usage" in titles


def test_markdown_fenced_code_blocks_create_workflow_steps(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        """
# Method

## Preparing input files

The Ribo-seq count matrix and RNA-seq count matrix use genes-by-samples columns.
The sample information file includes SampleID, SeqType, condition, and batch.

```r
library(DESeq2)
dds <- DESeqDataSetFromMatrix(countData = counts, colData = sample_info, design = ~ condition)
dds <- DESeq(dds)
res <- lfcShrink(dds, coef = 2, type = "apeglm")
write.csv(res, "results.csv")
```
""".strip()
        + "\n",
        encoding="utf-8",
    )

    trace = mine_script(readme)
    text = "\n".join(step["command_or_code"] for step in trace["workflow_steps"])

    assert "Preparing input files" in trace["section_titles"]
    assert "library(DESeq2)" in text
    assert "lfcShrink" in text
    assert any("raw_counts" in step["bio_signals"] for step in trace["workflow_steps"])
