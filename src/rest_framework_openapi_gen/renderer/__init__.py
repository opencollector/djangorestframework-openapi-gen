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

import dataclasses
import pathlib
import typing

import black
import jinja2

from ..json_pointer import JSONPointer
from ..parser import Definition, JSONType, OpenAPISpec, Path, Schema, SchemaRef, Verb
from .codegen import (
    NodeBuilderRegistry,
    PytreeRenderer,
    build_property,
    default_node_builder_registry,
)
from .exceptions import UnresolvedRefError, UnsupportedOpenAPISchema
from .models import Endpoint, SerializerDescriptor, VerbDescriptor
from .naming_conv import (
    render_as_camel_case,
    render_as_snake_case,
    tokenize_camel_case_identifier,
    tokenize_snake_case_identifier,
)


@dataclasses.dataclass
class RenderContext:
    pytree_renderer: PytreeRenderer
    serializers: typing.Mapping[JSONPointer, SerializerDescriptor]
    node_builder_registry: NodeBuilderRegistry


def render_property(rctx: RenderContext, schema: Schema, name: str) -> str:
    return rctx.pytree_renderer(
        build_property(
            rctx,
            schema,
            name,
            render_as_snake_case(tokenize_camel_case_identifier(name)),
            {},
        )
    )


SchemaResolverFunc = typing.Callable[
    [JSONPointer],
    Schema,
]


@dataclasses.dataclass
class QualifierContext:
    resolver: SchemaResolverFunc
    serializers: typing.MutableMapping[JSONPointer, SerializerDescriptor]
    owner: typing.Optional[SerializerDescriptor] = None
    pname: typing.Optional[str] = None


def qualify_child_schemas_inner(
    qctx: QualifierContext, schema_or_ref: typing.Union[Schema, SchemaRef]
) -> None:
    if isinstance(schema_or_ref, SchemaRef):
        schema = qctx.resolver(schema_or_ref.ref)
        if isinstance(schema, Definition):
            qualify_child_schemas(
                qctx=qctx,
                name=schema.name,
                schema=schema,
            )
        else:
            qualify_child_schemas(
                qctx=qctx,
                name="{qctx.owner.name}_{qctx.pname}",
                schema=schema,
            )
    elif isinstance(schema_or_ref, Schema):
        qualify_child_schemas(
            qctx=qctx,
            name="{qctx.owner.name}_{qctx.pname}",
            schema=schema_or_ref,
        )


def qualify_child_schemas(qctx: QualifierContext, name: str, schema: Schema) -> None:
    if schema.type_ == JSONType.OBJECT:
        me = qctx.serializers.get(schema.ctx)
        if me is None:
            me = qctx.serializers[schema.ctx] = SerializerDescriptor(
                schema=schema,
                name=name,
            )
        if qctx.owner is not None:
            me.owners.add(qctx.owner)
        assert schema.properties is not None
        for pname, p in schema.properties.items():
            qualify_child_schemas_inner(
                qctx=dataclasses.replace(qctx, owner=me, pname=pname),
                schema_or_ref=p,
            )
    elif schema.type_ == JSONType.ARRAY:
        assert schema.items is not None
        if isinstance(schema, Definition):
            me = qctx.serializers.get(schema.ctx)
            if me is None:
                me = qctx.serializers[schema.ctx] = SerializerDescriptor(
                    schema=schema,
                    name=name,
                    many=(
                        schema.items.ref
                        if isinstance(schema.items, SchemaRef)
                        else schema.items.ctx
                    ),
                )
            if qctx.owner is not None:
                me.owners.add(qctx.owner)
            qualify_child_schemas_inner(
                qctx=dataclasses.replace(qctx, owner=me),
                schema_or_ref=schema.items,
            )
        else:
            qualify_child_schemas_inner(
                qctx=qctx,
                schema_or_ref=schema.items,
            )


ObjectID = int


def eval_weights(
    serializers: typing.Iterable[SerializerDescriptor],
) -> typing.Sequence[typing.Tuple[SerializerDescriptor, int]]:
    weights: typing.Dict[ObjectID, int] = {}

    def _(ser_descr: SerializerDescriptor) -> int:
        ser_descr_id = id(ser_descr)
        v = weights.get(ser_descr_id)
        if v is None:
            v = weights[ser_descr_id] = sum((_(s) for s in ser_descr.owners)) + 1
        return v

    return [(ser_descr, _(ser_descr)) for ser_descr in serializers]


class SchemaResolver:
    pointers_to_defs_map: typing.Mapping[JSONPointer, Definition]

    def resolve(self, p: JSONPointer) -> Definition:
        def_ = self.pointers_to_defs_map.get(p)
        if def_ is None:
            raise UnresolvedRefError(p)
        return def_

    def resolve_if_ref(self, schema_or_ref: typing.Union[Schema, SchemaRef]) -> Schema:
        if isinstance(schema_or_ref, SchemaRef):
            return self.resolve(schema_or_ref.ref)
        else:
            return schema_or_ref

    def __init__(self, pointers_to_defs_map: typing.Mapping[JSONPointer, Definition]):
        self.pointers_to_defs_map = pointers_to_defs_map


def build_schema_resolver(spec: OpenAPISpec) -> SchemaResolver:
    pointers_to_defs_map: typing.Dict[JSONPointer, Definition] = {}

    for def_ in spec.definitions.values():
        pointers_to_defs_map[def_.ctx] = def_

    return SchemaResolver(pointers_to_defs_map)


def build_pseudo_name(path: Path, verb: Verb) -> str:
    return "_".join(
        (c[1:-1] if c.startswith("{") and c.endswith("}") else c)
        for c in path.path.split("/")
    )


def build_serializers(
    spec: OpenAPISpec, schema_resolver: SchemaResolver
) -> typing.Mapping[JSONPointer, SerializerDescriptor]:
    serializers: typing.Dict[JSONPointer, SerializerDescriptor] = {}
    important_schema_refs: typing.MutableSet[JSONPointer] = set()
    pseudo_defs: typing.Dict[JSONPointer, Definition] = {}

    # pass 1: collect required definitions
    for path in spec.paths:
        for verb in path.verbs.values():
            if verb.function_name is None:
                continue

            for resp in verb.responses.values():
                if resp.schema is None:
                    continue
                if isinstance(resp.schema, SchemaRef):
                    important_schema_refs.add(resp.schema.ref)
                elif isinstance(resp.schema, Schema):
                    pseudo_defs[resp.schema.ctx] = Definition(
                        name=build_pseudo_name(path, verb),
                        **vars(resp.schema),
                    )

    # pass 2: qualify descendants
    for def_ in spec.definitions.values():
        if def_.ctx not in important_schema_refs:
            continue
        qualify_child_schemas(
            qctx=QualifierContext(
                resolver=schema_resolver.resolve,
                serializers=serializers,
            ),
            name=def_.name,
            schema=def_,
        )

    for def_ in pseudo_defs.values():
        if def_.type_ != JSONType.OBJECT:
            continue
        qualify_child_schemas(
            qctx=QualifierContext(
                resolver=schema_resolver.resolve,
                serializers=serializers,
            ),
            name=def_.name,
            schema=def_,
        )

    return serializers


JSON_TYPE_TO_PYTHON_TYPE_MAP = {
    JSONType.INTEGER: int,
    JSONType.NUMBER: int,
    JSONType.STRING: str,
}


def render_as_django_url_pattern(path: Path) -> str:
    param_dict: typing.Dict[str, JSONType] = {}

    for verb in path.verbs.values():
        for p in verb.parameters:
            pt = param_dict.get(p.name)
            if pt is not None:
                if pt != p.type_:
                    raise UnsupportedOpenAPISchema("inconsistent parameter type")
            else:
                param_dict[p.name] = p.type_ or JSONType.STRING

    # path components
    cs = path.path.split("/")

    # absolute paths converted to relative
    if cs[0] == "":
        cs = cs[1:]

    # resulting component list
    rcs: typing.List[str] = []

    for c in cs:
        if not c:
            continue
        if c[0] == "{" and c[-1] == "}":
            # placeholder
            name = c[1:-1]
            pt = param_dict.get(name)
            if pt is None:
                raise UnsupportedOpenAPISchema()
            ppt = JSON_TYPE_TO_PYTHON_TYPE_MAP.get(pt)
            if ppt is None:
                raise UnsupportedOpenAPISchema()
            rcs.append(f"<{ppt.__name__}:{name}>")
        else:
            rcs.append(c)

    return "/".join(rcs)


def render(
    basedir: pathlib.Path, spec: OpenAPISpec, package: typing.Optional[str] = None
):
    schema_resolver = build_schema_resolver(spec)
    serializers = build_serializers(spec, schema_resolver)

    endpoints: typing.List[Endpoint] = []
    individual_handlers: typing.List[typing.Tuple[Path, VerbDescriptor]] = []
    for path in spec.paths:
        function_names: typing.List[typing.Tuple[bool, typing.Sequence[str]]] = []
        verb_descrs: typing.List[VerbDescriptor] = []

        for verb in path.verbs.values():
            if verb.function_name is None:
                continue

            function_names.append(
                tokenize_snake_case_identifier(
                    verb.function_name,
                    starts_with_capital=True,
                )
            )

            ser_descr: typing.Optional[SerializerDescriptor] = None
            resp = verb.responses.get("200")
            if resp is not None and resp.schema is not None:
                schema = schema_resolver.resolve_if_ref(resp.schema)
                ser_descr = serializers.get(schema.ctx)
                if ser_descr is None:
                    raise UnsupportedOpenAPISchema()

            verb_descrs.append(
                VerbDescriptor(
                    verb=verb,
                    serializer_descriptor=ser_descr,
                )
            )

        endpoint_name_candidates = set(tuple(name[:-1]) for _, name in function_names)
        if endpoint_name_candidates is None:
            continue

        if len(endpoint_name_candidates) == 1:
            endpoints.append(
                Endpoint(
                    path=path,
                    class_name=render_as_camel_case(
                        (True, endpoint_name_candidates.pop())
                    )
                    + "View",
                    verbs=verb_descrs,
                )
            )
        else:
            for verb_descr in verb_descrs:
                individual_handlers.append((path, verb_descr))

    mode = black.Mode(
        string_normalization=True,
    )

    rctx = RenderContext(
        pytree_renderer=PytreeRenderer(mode),
        serializers=serializers,
        node_builder_registry=default_node_builder_registry,
    )

    env = jinja2.Environment(
        loader=jinja2.PackageLoader(__name__.rpartition(".")[0], "templates"),
    )
    env.filters.update(
        {
            "render_property": lambda value, name: render_property(
                rctx, schema_resolver.resolve_if_ref(value), name
            ),
            "repr": repr,
            "black": lambda repr_: black.format_str(repr_, mode=mode).rstrip(),
            "render_as_django_url_pattern": render_as_django_url_pattern,
        }
    )

    outdir = basedir
    outdir.mkdir(exist_ok=True)
    if package is not None:
        for d in package.split("."):
            outdir = outdir / d
            outdir.mkdir(exist_ok=True)
            (outdir / "__init__.py").touch()

    t = env.get_template("serializers.py.jinja2")
    (outdir / "serializers.py").write_text(
        t.render(
            serializers=[
                ser_descr
                for ser_descr, _ in sorted(
                    eval_weights(serializers.values()), key=lambda pair: -pair[1]
                )
            ],
        ),
    )

    t = env.get_template("views.py.jinja2")
    (outdir / "views.py").write_text(
        t.render(
            endpoints=endpoints,
            individual_handlers=individual_handlers,
            serializers=serializers,
        ),
    )

    t = env.get_template("urls.py.jinja2")
    (outdir / "urls.py").write_text(
        t.render(
            endpoints=endpoints,
            individual_handlers=individual_handlers,
            serializers=serializers,
        ),
    )
