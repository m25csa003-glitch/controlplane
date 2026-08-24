import re
from typing import NamedTuple

_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


class Sentence(NamedTuple):
    text: str
    start: int
    end: int

    @property
    def span(self):
        return (self.start, self.end)


def sentences(text):
    """Split into sentences, keeping character offsets into the original text.
    Spans are what let the router redact one bad claim instead of the whole
    response, so the split has to stay offset-accurate."""
    out = []
    pos = 0
    for m in list(_BOUNDARY.finditer(text)) + [None]:
        end = m.start() if m else len(text)
        seg = text[pos:end]
        body = seg.strip()
        if body:
            start = pos + (len(seg) - len(seg.lstrip()))
            out.append(Sentence(body, start, start + len(body)))
        pos = m.end() if m else end
    return out
