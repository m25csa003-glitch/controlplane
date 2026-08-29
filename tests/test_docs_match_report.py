"""The documents quote the benchmark. This checks they still quote it correctly.

Every figure in the proposal and the README is supposed to come from
`eval/results/report.md`. Three of them did not: the docs carried numbers from
an earlier run and nobody re-read them after the eval was re-run with a live
judge. A reviewer checking one number against the report would have found it,
and "every number has provenance" is the claim this project rests on.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "eval" / "results" / "report.md"

pytestmark = pytest.mark.skipif(not REPORT.exists(), reason="no committed report")


def by_case_type():
    """{case type: (correct, n)} from the report's own table."""
    rows = {}
    section = REPORT.read_text().split("## By case type")[1].split("\n## ")[0]
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[1].isdigit() and cells[3].isdigit():
            rows[cells[0]] = (int(cells[3]), int(cells[1]))
    return rows


def docs():
    return {f: (ROOT / f).read_text() for f in
            ("docs/proposal.md", "docs/tasks.md", "README.md", "CLAUDE.md",
             "docs/assumptions.md", "docs/pitch_video.md")}


def test_the_report_still_has_the_table():
    rows = by_case_type()
    assert len(rows) > 15, rows
    for k in ("multi_hop", "quantifier_flip", "hedged_correct"):
        assert k in rows, k


@pytest.mark.parametrize("kind", ["multi_hop", "quantifier_flip", "hedged_correct"])
def test_no_document_quotes_a_stale_figure(kind):
    correct, n = by_case_type()[kind]
    # Two case types share n=15, so a bare "<a> of 15" is ambiguous - the figure
    # only counts as a claim about this kind if the kind is named nearby. Match
    # within the same line, which is how every one of these is written.
    words = kind.replace("_", "[ _-]?")
    for name, text in docs().items():
        for line in text.splitlines():
            if not re.search(words, line, re.I):
                continue
            for m in re.finditer(rf"\b(\d+)\s*(?:of|/)\s*{n}\b", line):
                assert int(m.group(1)) == correct, (
                    f"{name}: {line.strip()[:90]!r} says '{m.group(0)}' but the "
                    f"report says {correct} of {n} for {kind}")


def test_the_headline_numbers_are_quoted_as_published():
    report = REPORT.read_text()
    for figure in ("94.6%", "7.4%", "2.8%", "15.6%"):
        assert figure in report, f"{figure} is no longer in the report"
    for name, text in docs().items():
        if "94.6" in text:
            assert "7.4" in text, f"{name} quotes the catch rate without the false positive rate"


@pytest.mark.xfail(reason="the committed report predates the judge-mode fix: its "
                          "header says offline while its own call table records "
                          "328 live calls. Regenerating it needs a re-run.",
                   strict=False)
def test_the_report_does_not_contradict_its_own_judge_counters():
    """The header said the judge was offline while the call table in the same
    document showed 328 live calls. The header was derived from which env var
    was set - and it only looked for Anthropic keys, so an OpenAI-driven run
    reported offline and then attached caveats about a stand-in judge that had
    not been used."""
    text = REPORT.read_text()
    header = re.search(r"Tier 2 judge: \*\*(.+?)\*\*", text)
    assert header, "the report no longer states a judge mode"
    mode = header.group(1)

    calls = re.search(r"## Judge calls(.+?)(?:\n## |\Z)", text, re.S)
    assert calls, "the report no longer counts judge calls"
    api = sum(int(m) for m in re.findall(r"\|\s*`\w+`\s*\|\s*(\d+)\s*\|", calls.group(1)))

    if api:
        assert not mode.startswith("offline"), (
            f"the report says the judge was '{mode}' but records {api} API calls")
    else:
        assert mode.startswith("offline") or mode == "never ran", mode
