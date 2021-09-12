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

import pytest


@pytest.mark.parametrize(
    ("expected", "input"),
    [
        (
            (False, ["a", "b", "c"]),
            "ABC",
        ),
        (
            (False, ["xml", "http", "request"]),
            "XMLHTTPRequest",
        ),
        (
            (False, ["xml", "http", "request"]),
            "XmlHttpRequest",
        ),
    ],
)
def test_tokenize_camel_case_identifier(expected, input):
    from ..naming_conv import tokenize_camel_case_identifier

    assert tokenize_camel_case_identifier(input) == expected


@pytest.mark.parametrize(
    ("expected", "input"),
    [
        (
            "aBC",
            (False, ["a", "b", "c"]),
        ),
        (
            "xmlHttpRequest",
            (False, ["xml", "http", "request"]),
        ),
        (
            "XmlHttpRequest",
            (True, ["xml", "http", "request"]),
        ),
    ],
)
def test_render_as_camel_case(expected, input):
    from ..naming_conv import render_as_camel_case

    assert render_as_camel_case(input) == expected
