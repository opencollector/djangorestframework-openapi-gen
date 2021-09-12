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

import itertools
import typing

import black
from black.linegen import LineGenerator, transform_line
from blib2to3 import pygram, pytree  # type: ignore
from blib2to3.pgen2 import token  # type: ignore

from ..json_pointer import JSONPointer
from ..parser import JSONType, Schema, SchemaRef
from .exceptions import UnsupportedOpenAPISchema
from .models import SerializerDescriptor

NodeOrLeaf = typing.Union[pytree.Node, pytree.Leaf]


def single_input(children: typing.List[NodeOrLeaf]) -> pytree.Node:
    return pytree.Node(
        type=pygram.python_symbols.single_input,
        children=[
            pytree.Node(
                type=pygram.python_symbols.simple_stmt,
                children=[
                    pytree.Node(
                        type=pygram.python_symbols.power,
                        children=children,
                    ),
                ],
            ),
            pytree.Leaf(type=token.NEWLINE, value="\n"),
            pytree.Leaf(type=token.ENDMARKER, value=""),
        ],
    )


class PytreeRenderer:
    mode: black.Mode

    def __call__(self, n: NodeOrLeaf) -> str:
        linegen = LineGenerator(mode=self.mode)
        return "\n".join(
            str(ll)
            for line in linegen.visit(single_input([n]))
            for ll in transform_line(line, mode=self.mode)
        ).rstrip()

    def __init__(self, mode: black.Mode) -> None:
        self.mode = mode


def render_dereference_chain_into_nodes(
    callee: typing.Iterable[str],
) -> typing.Iterator[NodeOrLeaf]:
    prev_node: typing.Optional[NodeOrLeaf] = None

    for k in callee:
        n: NodeOrLeaf
        le = pytree.Leaf(type=token.NAME, value=k)
        if prev_node is None:
            n = le
        else:
            n = pytree.Node(
                type=pygram.python_symbols.trailer,
                children=[
                    pytree.Leaf(
                        type=token.DOT,
                        value=".",
                    ),
                    le,
                ],
            )
        yield n
        prev_node = n


def build_python_function_call(
    callee: typing.Iterable[str],
    kwargs: typing.Sequence[typing.Tuple[str, NodeOrLeaf]],
) -> pytree.Node:
    return pytree.Node(
        type=pygram.python_symbols.power,
        children=[
            *render_dereference_chain_into_nodes(callee),
            pytree.Node(
                type=pygram.python_symbols.trailer,
                children=[
                    pytree.Leaf(
                        type=token.LPAR,
                        value="(",
                    ),
                    pytree.Node(
                        type=pygram.python_symbols.arglist,
                        children=list(
                            itertools.chain.from_iterable(
                                (
                                    *(
                                        (
                                            pytree.Leaf(
                                                type=token.COMMA,
                                                value=",",
                                            ),
                                        )
                                        if i > 0
                                        else ()
                                    ),
                                    pytree.Node(
                                        type=pygram.python_symbols.argument,
                                        children=[
                                            pytree.Leaf(
                                                type=token.NAME,
                                                value=name,
                                            ),
                                            pytree.Leaf(
                                                type=token.EQUAL,
                                                value="=",
                                            ),
                                            value,
                                        ],
                                    ),
                                )
                                for i, (name, value) in enumerate(kwargs)
                            ),
                        ),
                    ),
                    pytree.Leaf(
                        type=token.LPAR,
                        value=")",
                    ),
                ],
            ),
        ],
    )


class NodeBuilderContext(typing.Protocol):
    serializers: typing.Mapping[JSONPointer, SerializerDescriptor]
    node_builder_registry: "NodeBuilderRegistry"


class NodeBuilderFunction(typing.Protocol):
    def __call__(
        self,
        nbctx: NodeBuilderContext,
        schema: Schema,
        name: str,
        source: str,
        aux: typing.Mapping[str, NodeOrLeaf],
    ) -> NodeOrLeaf:
        ...  # pragma: nocover


class NodeBuilderRegistry(typing.Protocol):
    def __call__(
        self, type_: JSONType, format: typing.Optional[str]
    ) -> NodeBuilderFunction:
        ...  # pragma: nocover


def build_decimal_field(
    nbctx: NodeBuilderContext,
    schema: Schema,
    name: str,
    source: str,
    aux: typing.Mapping[str, NodeOrLeaf],
) -> NodeOrLeaf:
    return build_python_function_call(
        ["fields", "DecimalField"],
        [
            *(
                [("source", pytree.Leaf(type=token.STRING, value=repr(source)))]
                if name != source
                else []
            ),
            (
                "max_digits",
                pytree.Leaf(type=token.NUMBER, value="20"),
            ),
            (
                "decimal_places",
                pytree.Leaf(type=token.NUMBER, value="20"),
            ),
            *aux.items(),
        ],
    )


def build_integer_field(
    nbctx: NodeBuilderContext,
    schema: Schema,
    name: str,
    source: str,
    aux: typing.Mapping[str, NodeOrLeaf],
) -> NodeOrLeaf:
    return build_python_function_call(
        ["fields", "IntegerField"],
        [
            *(
                [("source", pytree.Leaf(type=token.STRING, value=repr(source)))]
                if name != source
                else []
            ),
            *aux.items(),
        ],
    )


def build_float_field(
    nbctx: NodeBuilderContext,
    schema: Schema,
    name: str,
    source: str,
    aux: typing.Mapping[str, NodeOrLeaf],
) -> NodeOrLeaf:
    return build_python_function_call(
        ["fields", "FloatField"],
        [
            *(
                [("source", pytree.Leaf(type=token.STRING, value=repr(source)))]
                if name != source
                else []
            ),
            *aux.items(),
        ],
    )


def build_char_field(
    nbctx: NodeBuilderContext,
    schema: Schema,
    name: str,
    source: str,
    aux: typing.Mapping[str, NodeOrLeaf],
) -> NodeOrLeaf:
    return build_python_function_call(
        ["fields", "CharField"],
        [
            *(
                [("source", pytree.Leaf(type=token.STRING, value=repr(source)))]
                if name != source
                else []
            ),
            *aux.items(),
        ],
    )


def build_boolean_field(
    nbctx: NodeBuilderContext,
    schema: Schema,
    name: str,
    source: str,
    aux: typing.Mapping[str, NodeOrLeaf],
) -> NodeOrLeaf:
    return build_python_function_call(
        ["fields", "BooleanField"],
        [
            *(
                [("source", pytree.Leaf(type=token.STRING, value=repr(source)))]
                if name != source
                else []
            ),
            *aux.items(),
        ],
    )


def build_list_serializer(
    nbctx: NodeBuilderContext,
    schema: Schema,
    name: str,
    source: str,
    aux: typing.Mapping[str, NodeOrLeaf],
) -> NodeOrLeaf:
    elem_schema: typing.Optional[Schema] = None
    if isinstance(schema.items, SchemaRef):
        elem_ser_descr = nbctx.serializers.get(schema.items.ref)
        if elem_ser_descr is not None:
            elem_schema = elem_ser_descr.schema
        else:
            raise UnsupportedOpenAPISchema()
    else:
        # for pseudo definition
        elem_ser_descr = nbctx.serializers.get(schema.ctx)
        if elem_ser_descr is not None and elem_ser_descr.schema is not schema:
            elem_schema = elem_ser_descr.schema
        else:
            elem_schema = schema.items

    assert elem_schema is not None

    if elem_schema.type_ == JSONType.OBJECT:
        return build_property(
            nbctx=nbctx,
            schema=elem_schema,
            name=name,
            source=source,
            aux={
                **aux,
                "many": pytree.Leaf(
                    type=token.NAME,
                    value="True",
                ),
            },
        )
    else:
        return build_python_function_call(
            ["fields", "ListField"],
            [
                *(
                    [("source", pytree.Leaf(type=token.STRING, value=repr(source)))]
                    if name != source
                    else []
                ),
                (
                    "child",
                    build_property(nbctx, elem_schema, "", "", {}),
                ),
                *aux.items(),
            ],
        )


def build_nested_serializer(
    nbctx: NodeBuilderContext,
    schema: Schema,
    name: str,
    source: str,
    aux: typing.Mapping[str, NodeOrLeaf],
) -> NodeOrLeaf:
    ser_descr = nbctx.serializers[schema.ctx]
    return build_python_function_call(
        [ser_descr.serializer_class_name],
        [
            *(
                [("source", pytree.Leaf(type=token.STRING, value=repr(source)))]
                if name != source
                else []
            ),
            *aux.items(),
        ],
    )


def build_property(
    nbctx: NodeBuilderContext,
    schema: Schema,
    name: str,
    source: str,
    aux: typing.Mapping[str, NodeOrLeaf],
):
    nbctx.node_builder_registry(schema.type_, schema.format)(
        nbctx=nbctx,
        schema=schema,
        name=name,
        source=source,
        aux=aux,
    )


NodeBuilderRegistryMapping = typing.Mapping[
    typing.Tuple[JSONType, typing.Union[str, None]], NodeBuilderFunction
]


class DefaultNodeBuilderRegistry:
    _mapping: NodeBuilderRegistryMapping

    def __call__(
        self, type_: JSONType, format: typing.Optional[str]
    ) -> NodeBuilderFunction:
        fn = self._mapping.get((type_, format))
        if fn is not None:
            return fn
        fn = self._mapping.get((type_, None))
        if fn is not None:
            return fn
        raise UnsupportedOpenAPISchema(
            f"unsupported type and format pair: {type_} and {format}"
        )

    def __init__(self, registry_mapping: NodeBuilderRegistryMapping) -> None:
        self._mapping = registry_mapping


default_node_builder_registry = DefaultNodeBuilderRegistry(
    {
        (JSONType.NUMBER, None): build_float_field,
        (JSONType.INTEGER, None): build_integer_field,
        (JSONType.STRING, None): build_char_field,
        (JSONType.BOOLEAN, None): build_boolean_field,
        (JSONType.ARRAY, None): build_list_serializer,
        (JSONType.OBJECT, None): build_nested_serializer,
    }
)
