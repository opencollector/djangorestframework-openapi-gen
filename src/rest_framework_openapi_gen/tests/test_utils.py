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


class TestIdentitySet:
    @pytest.fixture
    def target(self):
        from ..utils import IdentitySet
        return IdentitySet

    def test_instantiate_no_arg(self, target):
        assert len(target()) == 0

    def test_instantiate_with_iterable(self, target):
        assert len(target(["a"])) == 1
        assert len(target(iter(["a"]))) == 1

    def test_add(self, target):
        t = target()
        t.add(object())
        t.add(object())
        assert len(t) == 2

    def test_add_duplicate(self, target):
        t = target()
        o = object()
        t.add(o)
        t.add(o)
        assert len(t) == 1

    def test_discard(self, target):
        o = object()
        t = target([o])
        assert len(t) == 1
        t.discard(o)
        assert len(t) == 0


class TestUnspecified:
    @pytest.fixture
    def target(self):
        from ..utils import UNSPECIFIED
        return UNSPECIFIED


    def test_hashable(self, target):
        try:
            hash(target)
        except TypeError:
            pytest.fail()
