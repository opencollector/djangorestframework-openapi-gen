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

import typing
import urllib.parse


def quote_json_pointer(v: str) -> str:
    return v.replace("~", "~0").replace("/", "~1")


def unquote_json_pointer(v: str) -> str:
    return v.replace("~1", "/").replace("~0", "~")


TjsonP = typing.TypeVar("TjsonP", bound="JSONPointer")


class JSONPointer:
    path: typing.Tuple[str, ...]
    _cache: typing.Dict[str, "JSONPointer"]

    def new_sub_context(self, c: str) -> "JSONPointer":
        sub_ctx = self._cache.get(c)
        if sub_ctx is None:
            sub_ctx = self._cache[c] = self.__class__(self.path + (c,))
        return sub_ctx

    def __truediv__(self, c: typing.Any) -> "JSONPointer":
        if not isinstance(c, str):
            raise TypeError(f"right operand must be a string, got {c}")
        return self.new_sub_context(c)

    def __str__(self) -> str:
        return (
           "".join(
                (f"/{quote_json_pointer(c)}" if isinstance(c, str) else f"[{c}]")
                for c in self.path
            )
           if self.path
           else "/"
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(self)!r})"

    def __eq__(self, that: typing.Any) -> bool:
        return isinstance(that, self.__class__) and that.path == self.path

    def __hash__(self) -> int:
        return hash(self.path)

    def __real_init__(self, path: typing.Iterable[str] = ()) -> None:
        self.path = tuple(path)
        self._cache = {}

    @classmethod
    def from_string(class_: typing.Type[TjsonP], v: str) -> TjsonP:
        if v and v[0] == "#":
            v = urllib.parse.unquote(v[1:])
        return class_(tuple(unquote_json_pointer(c) for c in v.split("/") if c))

    def __new__(
        class_: typing.Type[TjsonP], arg: typing.Union[str, typing.Iterable[str]] = ()
    ) -> TjsonP:
        if isinstance(arg, str):
            return class_.from_string(arg)
        else:
            i = super(JSONPointer, class_).__new__(class_)
            i.__real_init__(arg)
            return i
