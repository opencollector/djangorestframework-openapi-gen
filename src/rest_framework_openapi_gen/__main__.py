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

import pathlib
import typing

import click
import click_pathlib  # type: ignore
import yaml

from .json_pointer import JSONPointer
from .parser import build_openapi_from_repr
from .renderer import render


@click.command()
@click.option("--base-dir", type=click_pathlib.Path(), required=True)
@click.option(
    "--package",
    type=str,
    default=None,
)
@click.argument("input", type=click_pathlib.Path(exists=True))
def main(base_dir: pathlib.Path, package: typing.Optional[str], input: pathlib.Path):
    spec_dict: typing.Any
    with input.open("r") as f:
        spec_dict = yaml.load(f, Loader=yaml.SafeLoader)

    spec = build_openapi_from_repr(JSONPointer(), spec_dict)
    render(basedir=base_dir, spec=spec, package=package)


if __name__ == "__main__":
    main()
