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

import collections.abc
import enum
import typing

T = typing.TypeVar("T")


class IdentitySet(collections.abc.MutableSet, typing.Generic[T]):
    _items: typing.MutableMapping[int, T]

    def add(self, item: T) -> None:
        self._items[id(item)] = item

    def discard(self, item: T) -> None:
        del self._items[id(item)]

    def __contains__(self, item: object) -> bool:
        return id(item) in self._items

    def __iter__(self) -> typing.Iterator[T]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def __init__(self, items: typing.Iterable[T] = ()) -> None:
        self._items = {id(item): item for item in items}


class StrEnum(str, enum.Enum):
    pass


class Unspecified:
    pass


UNSPECIFIED = Unspecified()
