from __future__ import annotations

from paper2skill.inference.infer_workflow import infer_workflow
from paper2skill.miners.script_miner import mine_script


def test_markdown_code_blocks_feed_workflow_step_types(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        """
# Usage

```bash
Rscript --vanilla DTEG.R ribo.tsv rna.tsv sample_info.tsv
```

```r
library(DESeq2)
dds <- DESeq(dds)
res <- lfcShrink(dds, coef = 2, type = "apeglm")
write.csv(res, "results.csv")
```
""".strip()
        + "\n",
        encoding="utf-8",
    )
    trace = mine_script(readme)

    workflow = infer_workflow(trace)
    types = [node["type"] for node in workflow["workflow_dag"]["nodes"]]

    assert "cli_execution" in types
    assert "load_package" in types
    assert "statistical_analysis" in types
    assert "output_extraction" in types or "save_output" in types
