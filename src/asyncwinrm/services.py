from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

from lxml import etree

from .protocol.uri import cim
from .protocol.xml.element import CIMElement
from .protocol.xml.attribute import XSIAttribute

if TYPE_CHECKING:
    from .client.winrm import WinRMClient

_SERVICE_URI = cim("Win32_Service")

_SERVICE_FIELD_MAP: dict[str, str] = {
    "accept_pause": "AcceptPause",
    "accept_stop": "AcceptStop",
    "caption": "Caption",
    "check_point": "CheckPoint",
    "creation_class_name": "CreationClassName",
    "description": "Description",
    "desktop_interact": "DesktopInteract",
    "display_name": "DisplayName",
    "error_control": "ErrorControl",
    "exit_code": "ExitCode",
    "install_date": "InstallDate",
    "name": "Name",
    "path_name": "PathName",
    "process_id": "ProcessId",
    "service_specific_exit_code": "ServiceSpecificExitCode",
    "service_type": "ServiceType",
    "started": "Started",
    "start_mode": "StartMode",
    "start_name": "StartName",
    "state": "State",
    "status": "Status",
    "system_creation_class_name": "SystemCreationClassName",
    "system_name": "SystemName",
    "tag_id": "TagId",
    "wait_hint": "WaitHint",
    "delayed_auto_start": "DelayedAutoStart",
    "load_order_group": "LoadOrderGroup",
    "dependencies": "Dependencies",
}

_DYNAMIC_FIELDS = {
    "state",
    "status",
    "process_id",
    "exit_code",
    "service_specific_exit_code",
    "started",
}


def _coerce_wmi_text(text: Optional[str]) -> Any:
    if text is None:
        return None
    if text == "false":
        return False
    if text == "true":
        return True
    try:
        return int(text)
    except ValueError:
        return text


def _parse_cim_element(el: etree.Element) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for child in el:
        name = etree.QName(child).localname
        if child.get(XSIAttribute.Nil) == "true":
            value = None
        else:
            value = _coerce_wmi_text(child.text)
        if name in result:
            existing = result[name]
            if not isinstance(existing, list):
                existing = [existing]
            existing.append(value)
            result[name] = existing
        else:
            result[name] = value
    return result


def _pythonize_service_fields(data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for py_name, wmi_name in _SERVICE_FIELD_MAP.items():
        result[py_name] = data.get(wmi_name)
    return result


class ServiceStartType(str, Enum):
    """Types of service start modes"""

    # drivers
    Boot = "Boot"
    System = "System"

    # services
    Automatic = "Automatic"
    Manual = "Manual"
    Disabled = "Disabled"


class ServiceState(str, Enum):
    """Win32_Service State values"""

    Stopped = "Stopped"
    Start_Pending = "Start Pending"
    Stop_Pending = "Stop Pending"
    Running = "Running"
    Continue_Pending = "Continue Pending"
    Pause_Pending = "Pause Pending"
    Paused = "Paused"

    @classmethod
    def from_string(cls, value: Optional[str]) -> Optional["ServiceState"]:
        if not value:
            return None
        for member in cls:
            if member.value == value:
                return member
        return None


@dataclass(frozen=True, slots=True)
class Service:
    _client: "WinRMClient" = field(repr=False, compare=False)

    accept_pause: Optional[bool]
    accept_stop: Optional[bool]
    caption: Optional[str]
    check_point: Optional[int]
    creation_class_name: Optional[str]
    description: Optional[str]
    desktop_interact: Optional[bool]
    display_name: Optional[str]
    error_control: Optional[str]
    exit_code: Optional[int]
    install_date: Optional[str]
    name: str
    path_name: Optional[str]
    process_id: Optional[int]
    service_specific_exit_code: Optional[int]
    service_type: Optional[str]
    started: Optional[bool]
    start_mode: Optional[str]
    start_name: Optional[str]
    state: Optional[str]
    status: Optional[str]
    system_creation_class_name: Optional[str]
    system_name: Optional[str]
    tag_id: Optional[int]
    wait_hint: Optional[int]
    delayed_auto_start: Optional[bool]
    load_order_group: Optional[str]
    dependencies: Optional[list[str] | list[Any]]

    async def _fetch_raw(self) -> dict[str, Any]:
        return await self._client.get_cim_object(CIMElement.Service, name=self.name)

    async def _fetch_field(self, field_name: str) -> Any:
        data = await self._fetch_raw()
        wmi_name = _SERVICE_FIELD_MAP[field_name]
        return data.get(wmi_name)

    async def get_state(self) -> Optional[ServiceState]:
        raw = await self._fetch_field("state")
        return ServiceState.from_string(str(raw) if raw is not None else None)

    async def get_status(self) -> Optional[ServiceState]:
        return await self.get_state()

    async def get_process_id(self) -> Optional[int]:
        value = await self._fetch_field("process_id")
        return int(value) if value is not None else None

    async def get_exit_code(self) -> Optional[int]:
        value = await self._fetch_field("exit_code")
        return int(value) if value is not None else None

    async def get_service_specific_exit_code(self) -> Optional[int]:
        value = await self._fetch_field("service_specific_exit_code")
        return int(value) if value is not None else None

    async def get_started(self) -> Optional[bool]:
        value = await self._fetch_field("started")
        return bool(value) if value is not None else None

    async def start(self) -> None:
        await self._client.invoke_wmi(
            _SERVICE_URI,
            "StartService",
            {},
            selectors={"Name": self.name},
        )

    async def stop(self) -> None:
        await self._client.invoke_wmi(
            _SERVICE_URI,
            "StopService",
            {},
            selectors={"Name": self.name},
        )

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    async def pause(self) -> None:
        await self._client.invoke_wmi(
            _SERVICE_URI,
            "PauseService",
            {},
            selectors={"Name": self.name},
        )

    async def resume(self) -> None:
        await self._client.invoke_wmi(
            _SERVICE_URI,
            "ResumeService",
            {},
            selectors={"Name": self.name},
        )

    async def delete(self) -> None:
        await self._client.invoke_wmi(
            _SERVICE_URI,
            "Delete",
            {},
            selectors={"Name": self.name},
        )

    async def set_start_type(self, start_type: ServiceStartType) -> None:
        await self._client.invoke_wmi(
            _SERVICE_URI,
            "ChangeStartMode",
            {"StartMode": start_type.value},
            selectors={"Name": self.name},
        )

    async def disable(self) -> None:
        await self.set_start_type(ServiceStartType.Disabled)


@dataclass(frozen=True, slots=True)
class Services:
    client: "WinRMClient"

    async def get(self, name: str) -> Service:
        data = await self.client.get_cim_object(CIMElement.Service, name=name)
        return _service_from_wmi(self.client, data)

    async def get_all(self) -> list[Service]:
        services: list[Service] = []
        async for item in self.client.enumerate(_SERVICE_URI):
            data = _parse_cim_element(item)
            services.append(_service_from_wmi(self.client, data))
        return services


# TODO: is this the best way of doing it?
def _service_from_wmi(client: "WinRMClient", data: dict[str, Any]) -> Service:
    pythonic = _pythonize_service_fields(data)
    if not pythonic.get("name"):
        raise ValueError("Service name missing from Win32_Service data")
    if isinstance(pythonic.get("dependencies"), list):
        pythonic["dependencies"] = [str(item) for item in pythonic["dependencies"] if item is not None]
    return Service(client, **pythonic)


__all__ = ["Service", "Services", "ServiceStartType", "ServiceState"]
