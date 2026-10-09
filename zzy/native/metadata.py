"""Import-safe extension descriptions, separate from runtime implementations."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class NativeType:
    name: str
    mutable: bool
    ownership: str
    equality: str


@dataclass(frozen=True)
class NativeFunction:
    name: str
    parameters: tuple[str, ...]
    returns: str
    effects: tuple[str, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class Extension:
    name: str
    abi: str
    types: tuple[NativeType, ...] = ()
    functions: tuple[NativeFunction, ...] = ()


class MetadataRegistry:
    """Register descriptors without importing factories, GUI, or user code."""

    def __init__(self):
        self._extensions: dict[str, Extension] = {}

    @property
    def extensions(self):
        return MappingProxyType(self._extensions)

    def register(self, extension: Extension):
        if extension.name in self._extensions:
            raise ValueError(f"duplicate extension: {extension.name}")
        names = [item.name for item in (*extension.types, *extension.functions)]
        if len(names) != len(set(names)):
            raise ValueError("duplicate native name")
        if any(not name.startswith(extension.name + ".") for name in names):
            raise ValueError("native name must belong to its namespace")
        self._extensions[extension.name] = extension
