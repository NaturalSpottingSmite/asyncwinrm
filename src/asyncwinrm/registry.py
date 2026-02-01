from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum
from types import MappingProxyType
from typing import Optional, Sequence, Any, TYPE_CHECKING

from .protocol.uri import wmi

if TYPE_CHECKING:
    from .client.winrm import WinRMClient

_REGISTRY_URI = wmi("StdRegProv")


def _normalize_value_name(name: Optional[str]) -> str:
    return name or ""


class Tree(IntEnum):
    """Registry tree types that can be accessed over WMI"""

    ClassesRoot = 0x80000000
    CurrentUser = 0x80000001
    LocalMachine = 0x80000002
    Users = 0x80000003
    CurrentConfig = 0x80000005


class RegistryValueType(IntEnum):
    """Types of registry values"""

    String = 1
    ExpandString = 2
    Binary = 3
    DWord = 4
    MultiString = 7
    QWord = 11

    @classmethod
    def from_code(cls, code: int) -> Optional["RegistryValueType"]:
        """Converts the integer representation of a registry value type to an enum member."""
        try:
            return cls(code)
        except ValueError:
            return None


@dataclass(frozen=True, slots=True)
class RegistryValueInfo:
    """Information about a specific registry value"""

    name: str
    value_type: Optional[RegistryValueType]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r}, {self.value_type!r})"


class Registry:
    def __init__(self, client: "WinRMClient"):
        self.client = client

    @property
    def hklm(self) -> "RegistryTree":
        """Returns the HKEY_LOCAL_MACHINE registry tree."""
        return RegistryTree(self, Tree.LocalMachine)

    @property
    def hkcu(self) -> "RegistryTree":
        """Returns the HKEY_CURRENT_USER registry tree."""
        return RegistryTree(self, Tree.CurrentUser)

    @property
    def hkcr(self) -> "RegistryTree":
        """Returns the HKEY_CLASSES_ROOT registry tree."""
        return RegistryTree(self, Tree.ClassesRoot)

    @property
    def hku(self) -> "RegistryTree":
        """Returns the HKEY_USERS registry tree."""
        return RegistryTree(self, Tree.Users)

    @property
    def hkcc(self) -> "RegistryTree":
        """Returns the HKEY_CURRENT_CONFIG registry tree."""
        return RegistryTree(self, Tree.CurrentConfig)

    def tree(self, tree: Tree) -> "RegistryTree":
        """Creates a new RegistryTree accessor corresponding to a given tree."""
        return RegistryTree(self, tree)

    def get_key(self, tree: Tree, path: str) -> "RegistryKey":
        """Creates a new RegistryKey accessor corresponding to a subpath of a given tree."""
        return RegistryKey(self, tree, path)


@dataclass(frozen=True, slots=True)
class RegistryTree:
    """Represents a registry tree (the root object for registry operations over WMI)"""

    registry: Registry
    tree: Tree

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.tree!r})"

    def key(self, path: str) -> "RegistryKey":
        """
        Creates and returns a new RegistryKey accessor corresponding to a key in this tree.

        The key does not need to exist. This function does not perform any registry operation. It simply creates an
        accessor that can, in turn, be used to execute operations on the key. You can create the key by calling
        `await registry_key.create()` on the returned :class:`RegistryKey` object.

        :param path: The subpath of the registry key from the root of the tree.
        :return: A :class:`RegistryKey` object that can be used to execute operations on the key.
        """
        return RegistryKey(self.registry, self.tree, path)


@dataclass(frozen=True, slots=True)
class RegistryKey:
    """
    Represents a registry (sub-)key.

    This class can be used as an asynchronous context manager to get a dictionary view of the key's values.
    """

    registry: Registry
    tree: Tree
    path: str

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.tree!r}, {self.path!r})"

    def _child_path(self, subkey: str) -> str:
        if not self.path:
            return subkey
        if not subkey:
            return self.path
        return f"{self.path}\\{subkey}"

    def key(self, path: str) -> "RegistryKey":
        """
        Creates and returns a new RegistryKey accessor corresponding to a subkey of this key.

        The subkey does not need to exist. This function does not perform any registry operation. It simply creates an
        accessor that can, in turn, be used to execute operations on the subkey. You can create the subkey by calling
        `await registry_key.create()` on the returned :class:`RegistryKey` object.

        :param path: The subpath of the subkey from this key.
        :return: A :class:`RegistryKey` object that can be used to execute operations on the subkey.
        """
        return RegistryKey(self.registry, self.tree, self._child_path(path))

    async def create(self) -> None:
        """Creates this key."""
        await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "CreateKey",
            {"hDefKey": int(self.tree), "sSubKeyName": self.path},
        )

    async def delete(self) -> None:
        """Deletes this key."""
        await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "DeleteKey",
            {"hDefKey": int(self.tree), "sSubKeyName": self.path},
        )

    async def delete_value(self, name: Optional[str] = None) -> None:
        """Deletes a value inside this key."""
        await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "DeleteValue",
            {"hDefKey": int(self.tree), "sSubKeyName": self.path, "sValueName": _normalize_value_name(name)},
        )

    async def list_values(self) -> list[RegistryValueInfo]:
        """Lists the values inside this key."""
        output = await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "EnumValues",
            {"hDefKey": int(self.tree), "sSubKeyName": self.path},
        )
        names = output.get("sNames") or []
        types = output.get("Types") or []
        if not isinstance(names, list):
            names = [names]
        if not isinstance(types, list):
            types = [types]
        values = []
        for index, name in enumerate(names):
            value_type = RegistryValueType.from_code(int(types[index])) if index < len(types) else None
            values.append(RegistryValueInfo(name=str(name), value_type=value_type))
        return values

    async def list_subkeys(self) -> list[str]:
        """Lists the subkeys inside this key."""
        output = await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "EnumKey",
            {"hDefKey": int(self.tree), "sSubKeyName": self.path},
        )
        names = output.get("sNames") or []
        if isinstance(names, list):
            return [str(name) for name in names]
        if names is None:
            return []
        return [str(names)]

    async def get_value(self, name: Optional[str], value_type: RegistryValueType) -> Any:
        """Gets a value inside this key."""
        if value_type == RegistryValueType.String:
            return await self.get_string(name)
        if value_type == RegistryValueType.ExpandString:
            return await self.get_expand_string(name)
        if value_type == RegistryValueType.MultiString:
            return await self.get_multi_string(name)
        if value_type == RegistryValueType.Binary:
            return await self.get_binary(name)
        if value_type == RegistryValueType.DWord:
            return await self.get_dword(name)
        if value_type == RegistryValueType.QWord:
            return await self.get_qword(name)
        raise ValueError(f"Unsupported registry value type: {value_type}")

    async def set_value(self, name: Optional[str], value_type: RegistryValueType, value: Any) -> None:
        """Sets a value inside this key."""
        if value_type == RegistryValueType.String:
            await self.set_string(name, value)
        elif value_type == RegistryValueType.ExpandString:
            await self.set_expand_string(name, value)
        elif value_type == RegistryValueType.MultiString:
            await self.set_multi_string(name, value)
        elif value_type == RegistryValueType.Binary:
            await self.set_binary(name, value)
        elif value_type == RegistryValueType.DWord:
            await self.set_dword(name, value)
        elif value_type == RegistryValueType.QWord:
            await self.set_qword(name, value)
        else:
            raise ValueError(f"Unsupported registry value type: {value_type}")

    async def get_string(self, name: Optional[str] = None) -> Optional[str]:
        """Gets an SZ value inside this key."""
        output = await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "GetStringValue",
            {"hDefKey": int(self.tree), "sSubKeyName": self.path, "sValueName": _normalize_value_name(name)},
        )
        return output.get("sValue")

    async def get_expand_string(self, name: Optional[str] = None) -> Optional[str]:
        """Gets an EXPAND_SZ value inside this key."""
        output = await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "GetExpandedStringValue",
            {"hDefKey": int(self.tree), "sSubKeyName": self.path, "sValueName": _normalize_value_name(name)},
        )
        return output.get("sValue")

    async def get_multi_string(self, name: Optional[str] = None) -> list[str]:
        """Gets a MULTI_SZ value inside this key."""
        output = await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "GetMultiStringValue",
            {"hDefKey": int(self.tree), "sSubKeyName": self.path, "sValueName": _normalize_value_name(name)},
        )
        value = output.get("sValue") or []
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]

    async def get_binary(self, name: Optional[str] = None) -> bytes:
        """Gets a BINARY value inside this key."""
        output = await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "GetBinaryValue",
            {"hDefKey": int(self.tree), "sSubKeyName": self.path, "sValueName": _normalize_value_name(name)},
        )
        value = output.get("uValue") or []
        if isinstance(value, list):
            return bytes(int(item) for item in value if item is not None)
        if value is None:
            return b""
        return bytes([int(value)])

    async def get_dword(self, name: Optional[str] = None) -> Optional[int]:
        """Gets a DWORD value inside this key."""
        output = await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "GetDWORDValue",
            {"hDefKey": int(self.tree), "sSubKeyName": self.path, "sValueName": _normalize_value_name(name)},
        )
        value = output.get("uValue")
        return int(value) if value is not None else None

    async def get_qword(self, name: Optional[str] = None) -> Optional[int]:
        """Gets a QWORD value inside this key."""
        output = await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "GetQWORDValue",
            {"hDefKey": int(self.tree), "sSubKeyName": self.path, "sValueName": _normalize_value_name(name)},
        )
        value = output.get("uValue")
        return int(value) if value is not None else None

    async def set_string(self, name: Optional[str], value: str) -> None:
        """Sets an SZ value inside this key."""
        await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "SetStringValue",
            {
                "hDefKey": int(self.tree),
                "sSubKeyName": self.path,
                "sValueName": _normalize_value_name(name),
                "sValue": value,
            },
        )

    async def set_expand_string(self, name: Optional[str], value: str) -> None:
        """Sets an EXPAND_SZ value inside this key."""
        await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "SetExpandedStringValue",
            {
                "hDefKey": int(self.tree),
                "sSubKeyName": self.path,
                "sValueName": _normalize_value_name(name),
                "sValue": value,
            },
        )

    async def set_multi_string(self, name: Optional[str], value: Sequence[str]) -> None:
        """Sets a MULTI_SZ value inside this key."""
        await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "SetMultiStringValue",
            {
                "hDefKey": int(self.tree),
                "sSubKeyName": self.path,
                "sValueName": _normalize_value_name(name),
                "sValue": list(value),
            },
        )

    async def set_binary(self, name: Optional[str], value: bytes) -> None:
        """Sets a BINARY value inside this key."""
        await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "SetBinaryValue",
            {
                "hDefKey": int(self.tree),
                "sSubKeyName": self.path,
                "sValueName": _normalize_value_name(name),
                "uValue": [int(b) for b in value],
            },
        )

    async def set_dword(self, name: Optional[str], value: int) -> None:
        """Sets a DWORD value inside this key."""
        await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "SetDWORDValue",
            {
                "hDefKey": int(self.tree),
                "sSubKeyName": self.path,
                "sValueName": _normalize_value_name(name),
                "uValue": value,
            },
        )

    async def set_qword(self, name: Optional[str], value: int) -> None:
        """Sets a QWORD value inside this key."""
        await self.registry.client.invoke_wmi(
            _REGISTRY_URI,
            "SetQWORDValue",
            {
                "hDefKey": int(self.tree),
                "sSubKeyName": self.path,
                "sValueName": _normalize_value_name(name),
                "uValue": value,
            },
        )

    async def __aenter__(self) -> Mapping[str, Any]:
        values = await self.list_values()
        result: dict[str, Any] = {}
        for info in values:
            if info.value_type is None:
                result[info.name] = None
                continue
            result[info.name] = await self.get_value(info.name, info.value_type)
        return MappingProxyType(result)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        pass


__all__ = [
    "Tree",
    "RegistryValueType",
    "RegistryValueInfo",
    "Registry",
    "RegistryTree",
    "RegistryKey",
]
