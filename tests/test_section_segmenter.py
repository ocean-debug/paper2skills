from __future__ import annotations

from paper2skill.parsers.section_segmenter import segment_markdown


def test_segment_markdown_creates_stable_section_ids():
    sections = segment_markdown(
        """
# Introduction
Background text.

## Materials and Methods
We used scRNA-seq data.

### Preprocessing
NormalizeData was applied.
""".strip(),
        source_path="paper.md",
        prefix="paper",
    )
    assert [section.section_id for section in sections] == [
        "paper:introduction",
        "paper:methods",
        "paper:methods:preprocessing",
    ]
    assert sections[1].title == "Materials and Methods"
    assert sections[1].start_line == 4
    assert sections[1].end_line == 6
