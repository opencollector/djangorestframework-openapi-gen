import dataclasses
import typing

from ..json_pointer import JSONPointer
from ..parser import Path, Schema, Verb
from ..utils import IdentitySet


@dataclasses.dataclass
class SerializerDescriptor:
    schema: Schema
    name: str
    owners: typing.MutableSet["SerializerDescriptor"] = dataclasses.field(
        default_factory=IdentitySet
    )
    many: typing.Optional[JSONPointer] = None

    @property
    def serializer_class_name(self):
        return f"{self.name}Serializer"


@dataclasses.dataclass
class VerbDescriptor:
    verb: Verb
    serializer_descriptor: typing.Optional[SerializerDescriptor]


@dataclasses.dataclass
class Endpoint:
    path: Path
    class_name: str
    verbs: typing.Sequence[VerbDescriptor]
