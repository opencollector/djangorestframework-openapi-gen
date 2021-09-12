# Copyright 2021 Open Collector, Inc,
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import re
import typing


def tokenize_camel_case_identifier(
    ident: str,
) -> typing.Tuple[bool, typing.Sequence[str]]:
    s = 0
    starts_with_capital = False
    seq: typing.List[str] = []
    keep: str = ""

    for m in re.finditer("(JSON|HTTPS|HTTP|XML|ID|[A-Z])", ident):
        span = m.span(0)
        if span[0] > s:
            seq.append((keep + ident[s : span[0]]).lower())
            keep = ""
            if s == 0:
                starts_with_capital = True
        if span[1] - span[0] == 1:
            if keep:
                seq.append(keep.lower())
            keep = ident[span[0] : span[1]]
        else:
            seq.append(ident[span[0] : span[1]].lower())
        s = span[1]
    if s < len(ident) or keep:
        seq.append((keep + ident[s:]).lower())

    return starts_with_capital, seq


def tokenize_snake_case_identifier(
    ident: str, starts_with_capital: bool = False
) -> typing.Tuple[bool, typing.Sequence[str]]:
    return starts_with_capital, ident.split("_")


def render_as_snake_case(tokens: typing.Tuple[bool, typing.Sequence[str]]) -> str:
    return "_".join(tokens[1])


def render_as_camel_case(tokens: typing.Tuple[bool, typing.Sequence[str]]) -> str:
    starts_with_capital, _tokens = tokens
    return "".join(
        (c.title() if i != 0 or starts_with_capital else c)
        for i, c in enumerate(_tokens)
    )
