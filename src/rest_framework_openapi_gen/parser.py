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
import dataclasses
import typing

from .json_pointer import JSONPointer
from .utils import UNSPECIFIED, StrEnum, Unspecified


class ParameterPlace(StrEnum):
    PATH = "path"
    QUERY = "query"
    FORM_DATA = "formData"
    BODY = "body"


class JSONType(StrEnum):
    NUMBER = "number"
    INTEGER = "integer"
    STRING = "string"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class HttpVerb(StrEnum):
    GET = "get"
    POST = "post"
    PUT = "put"
    PATCH = "patch"
    DELETE = "delete"


@dataclasses.dataclass
class OpenAPIItem:
    ctx: JSONPointer


@dataclasses.dataclass
class SchemaRef(OpenAPIItem):
    ref: JSONPointer


@dataclasses.dataclass
class Schema(OpenAPIItem):
    type_: JSONType
    description: typing.Optional[str]
    format: typing.Optional[str]
    properties: typing.Optional[typing.Mapping[str, typing.Union[SchemaRef, "Schema"]]]
    required: typing.Optional[typing.Sequence[str]]
    items: typing.Union[SchemaRef, "Schema", None]


@dataclasses.dataclass
class Parameter(OpenAPIItem):
    name: str
    in_: ParameterPlace
    schema: typing.Union[Schema, SchemaRef, None]
    description: typing.Optional[str]
    type_: typing.Optional[JSONType] = JSONType.STRING
    required: bool = False


@dataclasses.dataclass
class Response(OpenAPIItem):
    status_code: str
    schema: typing.Union[Schema, SchemaRef, None] = None
    description: typing.Optional[str] = None


@dataclasses.dataclass
class Verb(OpenAPIItem):
    verb: HttpVerb
    tags: typing.Sequence[str]
    parameters: typing.Sequence[Parameter]
    responses: typing.Mapping[str, Response]
    function_name: typing.Optional[str] = None
    description: typing.Optional[str] = None
    operation_id: typing.Optional[str] = None


@dataclasses.dataclass
class Path(OpenAPIItem):
    path: str
    verbs: typing.Mapping[HttpVerb, Verb]


@dataclasses.dataclass
class Definition(Schema):
    name: str


@dataclasses.dataclass
class OpenAPISpec(OpenAPIItem):
    definitions: typing.Mapping[str, Definition]
    paths: typing.Sequence[Path]


class InvalidSchemaError(Exception):
    def __init__(self, message: str, *, ctx: JSONPointer) -> None:
        super().__init__(message, ctx)

    @property
    def message(self) -> str:
        return typing.cast(str, self.args[0])

    @property
    def ctx(self) -> JSONPointer:
        return typing.cast(JSONPointer, self.args[1])

    def __str__(self):
        return f"{self.ctx}: {self.message}"


def validate_as_string(ctx: JSONPointer, v: typing.Any) -> str:
    if not isinstance(v, str):
        raise InvalidSchemaError(f"value must be a string, got {v}", ctx=ctx)
    return v


def validate_as_integer(ctx: JSONPointer, v: typing.Any) -> int:
    if not isinstance(v, (int, float)):
        raise InvalidSchemaError(f"value must be an integer, got {v}", ctx=ctx)
    return int(v)


def validate_as_float(ctx: JSONPointer, v: typing.Any) -> float:
    if not isinstance(v, (int, float)):
        raise InvalidSchemaError(f"value must be an integer, got {v}", ctx=ctx)
    return float(v)


def validate_as_boolean(ctx: JSONPointer, v: typing.Any) -> bool:
    if not isinstance(v, bool):
        raise InvalidSchemaError(f"value must be a boolean, got {v}", ctx=ctx)
    return v


SCALAR_VALIDATORS = {
    str: validate_as_string,
    int: validate_as_integer,
    float: validate_as_float,
    bool: validate_as_boolean,
    collections.abc.Mapping: lambda ctx, v: validate_as_object(ctx, object, v),
    collections.abc.Sequence: lambda ctx, v: validate_as_array(ctx, object, v),
}


def find_scalar_validator(
    t: typing.Type,
) -> typing.Optional[typing.Callable[[JSONPointer, typing.Any], typing.Any]]:
    v = SCALAR_VALIDATORS.get(t)
    if v is not None:
        return v
    for tt in t.__mro__:
        v = SCALAR_VALIDATORS.get(tt)
        if v is not None:
            return v
    return None


T = typing.TypeVar("T")


def validate_as_array(
    ctx: JSONPointer, class_: typing.Type[T], v: typing.Any
) -> typing.Sequence[T]:
    if not isinstance(v, collections.abc.Sequence):
        raise InvalidSchemaError("value must be an array", ctx=ctx)
    if class_ is object:
        return v
    validator = find_scalar_validator(class_)
    if validator is not None:
        return [typing.cast(T, validator(ctx / str(i), e)) for i, e in enumerate(v)]
    else:
        return typing.cast(typing.Sequence[T], v)


def validate_as_array_optional(
    ctx: JSONPointer, class_: typing.Type[T], v: typing.Any
) -> typing.Sequence[typing.Optional[T]]:
    if not isinstance(v, collections.abc.Sequence):
        raise InvalidSchemaError("value must be an array", ctx=ctx)
    if class_ is object:
        return v
    validator = find_scalar_validator(class_)
    if validator is not None:
        return [
            (typing.cast(T, validator(ctx / str(i), e)) if e is not None else None)
            for i, e in enumerate(v)
        ]
    else:
        return typing.cast(typing.Sequence[typing.Optional[T]], v)


def validate_as_object(
    ctx: JSONPointer, class_: typing.Type[T], v: typing.Any
) -> typing.Mapping[str, T]:
    if not isinstance(v, collections.abc.Mapping):
        raise InvalidSchemaError(f"value must be an object, got {v}", ctx=ctx)
    if class_ is object:
        return v
    validator = find_scalar_validator(class_)
    if validator is not None:
        return {k: typing.cast(T, validator(ctx / k, e)) for k, e in v.items()}
    else:
        return typing.cast(typing.Mapping[str, T], v)


def validate_as_object_optional(
    ctx: JSONPointer, class_: typing.Type[T], v: typing.Any
) -> typing.Mapping[str, typing.Optional[T]]:
    if not isinstance(v, collections.abc.Mapping):
        raise InvalidSchemaError(f"value must be an object, got {v}", ctx=ctx)
    if class_ is object:
        return v
    validator = find_scalar_validator(class_)
    if validator is not None:
        return {
            k: (typing.cast(T, validator(ctx / k, e)) if e is not None else None)
            for k, e in v.items()
        }
    else:
        return typing.cast(typing.Mapping[str, T], v)


@typing.overload
def get_as_str(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    default: typing.Union[str, Unspecified] = UNSPECIFIED,
) -> str:
    ...  # pragma: nocover


@typing.overload
def get_as_str(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    default: None,
) -> typing.Optional[str]:
    ...  # pragma: nocover


def get_as_str(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    default: typing.Union[str, None, Unspecified] = UNSPECIFIED,
) -> typing.Optional[str]:
    sub_ctx = ctx / prop_name
    v = m.get(prop_name, UNSPECIFIED)
    if v is UNSPECIFIED:
        if default is UNSPECIFIED:
            raise InvalidSchemaError("no such property", ctx=sub_ctx)
        v = default
    return validate_as_string(sub_ctx, v) if v is not None else None


@typing.overload
def get_as_bool(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    default: typing.Union[bool, Unspecified] = UNSPECIFIED,
) -> bool:
    ...  # pragma: nocover


@typing.overload
def get_as_bool(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    default: None,
) -> typing.Optional[bool]:
    ...  # pragma: nocover


def get_as_bool(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    default: typing.Union[bool, None, Unspecified] = UNSPECIFIED,
) -> typing.Optional[bool]:
    sub_ctx = ctx / prop_name
    v = m.get(prop_name, UNSPECIFIED)
    if v is UNSPECIFIED:
        if default is UNSPECIFIED:
            raise InvalidSchemaError("no such property", ctx=sub_ctx)
        v = default
    return validate_as_boolean(sub_ctx, v) if v is not None else None


@typing.overload
def get_as_array(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    class_: typing.Type[T],
    default: typing.Union[typing.Sequence[T], Unspecified] = UNSPECIFIED,
) -> typing.Sequence[T]:
    ...  # pragma: nocover


@typing.overload
def get_as_array(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    class_: typing.Type[T],
    default: None,
) -> typing.Optional[typing.Sequence[T]]:
    ...  # pragma: nocover


def get_as_array(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    class_: typing.Type[T],
    default: typing.Union[typing.Sequence[T], None, Unspecified] = UNSPECIFIED,
) -> typing.Optional[typing.Sequence[T]]:
    sub_ctx = ctx / prop_name
    v = m.get(prop_name, UNSPECIFIED)
    if v is UNSPECIFIED:
        if default is UNSPECIFIED:
            raise InvalidSchemaError("no such property", ctx=sub_ctx)
        v = default
    if v is None:
        return None
    else:
        return validate_as_array(sub_ctx, class_, v)


@typing.overload
def get_as_array_optional(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    class_: typing.Type[T],
    default: typing.Union[
        typing.Sequence[typing.Optional[T]], Unspecified
    ] = UNSPECIFIED,
) -> typing.Sequence[typing.Optional[T]]:
    ...  # pragma: nocover


@typing.overload
def get_as_array_optional(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    class_: typing.Type[T],
    default: None,
) -> typing.Optional[typing.Sequence[typing.Optional[T]]]:
    ...  # pragma: nocover


def get_as_array_optional(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    class_: typing.Type[T],
    default: typing.Union[
        typing.Sequence[typing.Optional[T]], None, Unspecified
    ] = UNSPECIFIED,
) -> typing.Optional[typing.Sequence[typing.Optional[T]]]:
    sub_ctx = ctx / prop_name
    v = m.get(prop_name, UNSPECIFIED)
    if v is UNSPECIFIED:
        if default is UNSPECIFIED:
            raise InvalidSchemaError("no such property", ctx=sub_ctx)
        v = default
    return validate_as_array_optional(sub_ctx, class_, v)


@typing.overload
def get_as_object(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    class_: typing.Type[T],
    default: typing.Union[typing.Mapping[str, T], Unspecified] = UNSPECIFIED,
) -> typing.Mapping[str, T]:
    ...  # pragma: nocover


@typing.overload
def get_as_object(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    class_: typing.Type[T],
    default: None,
) -> typing.Optional[typing.Mapping[str, T]]:
    ...  # pragma: nocover


def get_as_object(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    class_: typing.Type[T],
    default: typing.Union[typing.Mapping[str, T], None, Unspecified] = UNSPECIFIED,
):
    sub_ctx = ctx / prop_name
    v = m.get(prop_name, UNSPECIFIED)
    if v is UNSPECIFIED:
        if default is UNSPECIFIED:
            raise InvalidSchemaError("no such property", ctx=sub_ctx)
        v = default
    if v is None:
        return None
    else:
        return validate_as_object(sub_ctx, class_, v)


@typing.overload
def get_as_object_optional(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    class_: typing.Type[T],
    default: typing.Union[
        typing.Mapping[str, typing.Optional[T]], Unspecified
    ] = UNSPECIFIED,
) -> typing.Mapping[str, typing.Optional[T]]:
    ...  # pragma: nocover


@typing.overload
def get_as_object_optional(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    class_: typing.Type[T],
    default: None,
) -> typing.Optional[typing.Mapping[str, typing.Optional[T]]]:
    ...  # pragma: nocover


def get_as_object_optional(
    ctx: JSONPointer,
    m: typing.Mapping[str, typing.Any],
    prop_name: str,
    class_: typing.Type[T],
    default: typing.Union[
        typing.Mapping[str, typing.Optional[T]], None, Unspecified
    ] = UNSPECIFIED,
) -> typing.Optional[typing.Mapping[str, typing.Optional[T]]]:
    sub_ctx = ctx / prop_name
    v = m.get(prop_name, UNSPECIFIED)
    if v is UNSPECIFIED:
        if default is UNSPECIFIED:
            raise InvalidSchemaError("no such property", ctx=sub_ctx)
        v = default
    if v is None:
        return None
    else:
        return validate_as_object_optional(sub_ctx, class_, v)


Tschema = typing.TypeVar("Tschema", bound=Schema, covariant=True)


class SchemaFactory(typing.Protocol, typing.Generic[Tschema]):
    def __call__(
        self,
        type_: JSONType,
        description: typing.Optional[str],
        format: typing.Optional[str],
        properties: typing.Optional[
            typing.Mapping[str, typing.Union[SchemaRef, "Schema"]]
        ],
        required: typing.Optional[typing.Sequence[str]],
        items: typing.Union[SchemaRef, "Schema", None],
        **kwargs: typing.Any,
    ) -> Tschema:
        pass


def build_schema_from_repr(
    ctx: JSONPointer,
    schema_repr: typing.Mapping[str, typing.Any],
    factory: SchemaFactory[Tschema] = Schema,
    **kwargs,
) -> Tschema:
    prop_repr_map = get_as_object(ctx, schema_repr, "properties", object, default=None)
    items_repr_map = get_as_object(ctx, schema_repr, "items", object, default=None)
    return factory(  # type: ignore
        ctx=ctx,
        description=get_as_str(ctx, schema_repr, "description", default=None),
        type_=JSONType(
            get_as_str(
                ctx,
                schema_repr,
                "type",
                default=(
                    "object"
                    if prop_repr_map is not None
                    else ("array" if items_repr_map is not None else UNSPECIFIED)
                ),
            ),
        ),
        format=get_as_str(ctx, schema_repr, "format", default=None),
        properties=(
            {
                k: resolve_schema(ctx / k, validate_as_object(ctx / k, object, v))
                for k, v in prop_repr_map.items()
            }
            if prop_repr_map is not None
            else None
        ),
        required=get_as_array(ctx, schema_repr, "required", str, default=None),
        items=(
            resolve_schema(ctx / "items", items_repr_map)
            if items_repr_map is not None
            else None
        ),
        **kwargs,
    )


def resolve_schema(
    ctx: JSONPointer,
    schema_repr: typing.Mapping[str, typing.Any],
) -> typing.Union[Schema, SchemaRef]:
    ref = get_as_str(ctx, schema_repr, "$ref", default=None)
    if ref is not None:
        return SchemaRef(ctx=ctx, ref=JSONPointer.from_string(ref))
    else:
        return build_schema_from_repr(ctx, schema_repr)


def build_response_from_repr(
    ctx: JSONPointer,
    status_code: str,
    response_repr: typing.Mapping[str, typing.Any],
) -> Response:
    schema_repr = (
        get_as_object(ctx, response_repr, "schema", object)
        if "schema" in response_repr
        else None
    )
    return Response(
        ctx=ctx,
        schema=(
            resolve_schema(
                ctx / "schema",
                schema_repr,
            )
            if schema_repr is not None
            else None
        ),
        status_code=status_code,
        description=get_as_str(ctx, response_repr, "description", default=None),
    )


def build_parameter_from_repr(
    ctx: JSONPointer,
    parameter_repr: typing.Mapping[str, typing.Any],
):
    schema_repr = get_as_object(ctx, parameter_repr, "schema", object, default=None)
    return Parameter(
        ctx=ctx,
        name=get_as_str(ctx, parameter_repr, "name"),
        in_=ParameterPlace(get_as_str(ctx, parameter_repr, "in")),
        type_=JSONType(get_as_str(ctx, parameter_repr, "type", default=None)),
        schema=(
            resolve_schema(
                ctx / "schema",
                schema_repr,
            )
            if schema_repr is not None
            else None
        ),
        description=get_as_str(ctx, parameter_repr, "description", default=None),
        required=get_as_bool(ctx, parameter_repr, "required", default=True),
    )


def build_verb_from_repr(
    ctx: JSONPointer, verb: HttpVerb, verb_repr: typing.Mapping[str, typing.Any]
) -> Verb:
    return Verb(
        ctx=ctx,
        verb=verb,
        tags=[
            validate_as_string(ctx / "tags" / str(i), v)
            for i, v in enumerate(get_as_array(ctx, verb_repr, "tags", str, []))
        ],
        function_name=get_as_str(
            ctx, verb_repr, "x-appgen-function-name", default=None
        ),
        description=get_as_str(ctx, verb_repr, "description", default=None),
        operation_id=get_as_str(ctx, verb_repr, "operationId", default=None),
        parameters=[
            build_parameter_from_repr(ctx / "parameters", parameter_repr)
            for parameter_repr in get_as_array(
                ctx, verb_repr, "parameters", dict, default=[]
            )
        ],
        responses={
            status_code: build_response_from_repr(
                ctx / "responses" / status_code, status_code, response_repr
            )
            for status_code, response_repr in get_as_object(
                ctx, verb_repr, "responses", dict
            ).items()
        },
    )


def build_definition_from_repr(
    ctx: JSONPointer, name: str, definition_repr: typing.Mapping[str, typing.Any]
) -> Definition:
    return build_schema_from_repr(
        ctx,
        definition_repr,
        factory=Definition,
        name=name,
    )


def build_openapi_from_repr(
    ctx: JSONPointer, schema_repr: typing.Mapping[str, typing.Any]
) -> OpenAPISpec:
    return OpenAPISpec(
        ctx=ctx,
        definitions={
            name: build_definition_from_repr(
                ctx / "definitions" / name, name, definition_repr
            )
            for name, definition_repr in get_as_object(
                ctx,
                schema_repr,
                "definitions",
                dict,
                default={},
            ).items()
        },
        paths=[
            Path(
                ctx=ctx,
                path=path,
                verbs={
                    verb: build_verb_from_repr(ctx / "paths" / path, verb, verb_repr)
                    for verb, verb_repr in (
                        (HttpVerb(verb), verb_repr)
                        for verb, verb_repr in path_repr.items()
                    )
                },
            )
            for path, path_repr in get_as_object(
                ctx, schema_repr, "paths", dict
            ).items()
        ],
    )
