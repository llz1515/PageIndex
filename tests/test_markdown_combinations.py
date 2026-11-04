"""Contract suite for the combined #610/#611/#555 plus boundary fixes.

This file lives on the integration-evidence branch. It requires the pending
features and is not presented as passing on current upstream main.
"""
import asyncio
from collections import Counter

import pytest

from pageindex.page_index_md import (extract_node_text_content,
    extract_nodes_from_markdown, md_to_tree)


CASES = [
    ("intro fact\nsecond fact\n", ["Preface"]),
    ("\n  \n", []),
    ("# Only\nbody fact\n", ["Only"]),
    ("intro fact\n\n# Only\nbody fact\n", ["Preface", "Only"]),
    ("Setext title\n============\nbody fact\n", ["Setext title"]),
    ("Title first line\nsecond title line\n===\nbody fact\n", ["Title first line second title line"]),
    ("intro fact\n\nSetext title\n----\nbody fact\n\n# ATX\nmore fact\n", ["Preface", "Setext title", "ATX"]),
    ("简介\n===\n中文事实\n\n## 子标题\n子章节正文\n", ["简介", "子标题"]),
    ("# Before\n```md\n# code heading\nCode title\n===\n```\n## After\nfinal fact\n", ["Before", "After"]),
    ("~~~md\n# code heading\nCode title\n===\n~~~\n# After\nfinal fact\n", ["Preface", "After"]),
    ("# Before\n````md\n```\n# code heading\n```\n````\n# After\nend\n", ["Before", "After"]),
    ("# Before\n~~~~\n~~~\n# still code\n```\n~~~~\n# After\nend\n", ["Before", "After"]),
    ("# Before\n```\n# unclosed example\nend\n", ["Before"]),
    ("~~~\n# code only\nend\n", ["Preface"]),
    ("paragraph\n~~~python\n# code\n~~~\n---\n\n# Actual\nbody\n", ["Preface", "Actual"]),
    ("~~~\n# code\n~~~\nReal title\n===\nbody\n", ["Preface", "Real title"]),
    ("# A\nbody\n\n---\nReal title\n===\nbody two\n", ["A", "Real title"]),
    ("# A\nbody\n\n***\nReal title\n===\nbody two\n", ["A", "Real title"]),
    ("# A\nbody\n\n_ _ _\nReal title\n===\nbody two\n", ["A", "Real title"]),
    ("Intro\n===\n\n- list item\n---\n\n# Actual\nbody\n", ["Intro", "Actual"]),
    ("same fact\n\n# Later\nsame fact\n", ["Preface", "Later"]),
    ("# A\n## B\n\n# C\n", ["A", "B", "C"]),
]


def nonblank_lines(text):
    # The established node text contract trims boundary whitespace. Compare
    # every nonblank source line, retaining multiplicity and interior spaces.
    return Counter(line.strip() for line in text.splitlines() if line.strip())


@pytest.mark.parametrize("body,titles", CASES)
@pytest.mark.parametrize("yaml", [False, True])
def test_combined_outline_and_source_partition(body, titles, yaml):
    prefix = ("---\n# metadata\nexample: |\n  **not a heading**\n  ---\n  ...\n  ```\n"
              "  # metadata code\n---\n") if yaml else ""
    nodes, lines = extract_nodes_from_markdown(prefix + body)
    nodes = extract_node_text_content(nodes, lines)
    assert [node["title"] for node in nodes] == titles
    assert all(node["text"].strip() for node in nodes)
    assert nonblank_lines("\n".join(node["text"] for node in nodes)) == nonblank_lines(body)
    # Every stored text comes from its own contiguous source interval.
    for i, node in enumerate(nodes):
        stop = nodes[i + 1]["line_num"] - 1 if i + 1 < len(nodes) else len(lines)
        assert node["text"] == "\n".join(lines[node["line_num"] - 1:stop]).strip()


def test_md_to_tree_keeps_combined_body_without_model(tmp_path):
    body = "intro fact\n\nMain title\n===\nmain fact\n\n~~~md\n# code\n~~~\n\n## Child\nchild fact\n"
    path = tmp_path / "combined.md"
    path.write_text("---\n# metadata\n---\n" + body)
    result = asyncio.run(md_to_tree(str(path), if_thinning=False, if_add_node_text="yes",
                                    if_add_node_summary="no", if_add_doc_description="no"))
    def walk(nodes):
        for node in nodes:
            yield node
            yield from walk(node.get("nodes") or [])
    nodes = list(walk(result["structure"]))
    assert [node["title"] for node in nodes] == ["Preface", "Main title", "Child"]
    assert nonblank_lines("\n".join(node["text"] for node in nodes)) == nonblank_lines(body)
