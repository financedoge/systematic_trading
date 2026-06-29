from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


DEFAULT_SERVICE_MANIFEST_PATH = Path(__file__).resolve().parents[3] / "config" / "service-manifest.json"


class ServiceType(StrEnum):
    API = "api"
    WORKER = "worker"
    EMBEDDED_WORKER = "embedded_worker"


class ServiceImplementationStatus(StrEnum):
    ACTIVE = "active"
    PLANNED = "planned"
    RETIRED = "retired"


class HealthCheckKind(StrEnum):
    HTTP = "http"
    TCP = "tcp"
    PID_FILE = "pid_file"
    STATE_FILE = "state_file"
    NONE = "none"


class RestartPolicy(BaseModel):
    mode: str = Field(min_length=1)
    max_restarts: int = Field(default=0, ge=0)


class ServiceHealthCheck(BaseModel):
    kind: HealthCheckKind
    target: str | None = None
    timeout_seconds: int = Field(default=2, ge=1)
    stale_after_seconds: int | None = Field(default=None, ge=1)


class ServiceSpec(BaseModel):
    service_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    service_type: ServiceType
    implementation_status: ServiceImplementationStatus = ServiceImplementationStatus.ACTIVE
    required: bool = True
    startup_order: int = Field(ge=0)
    command: list[str] = Field(default_factory=list)
    working_directory: str = "."
    pid_file: str | None = None
    stdout_log: str | None = None
    stderr_log: str | None = None
    health_check: ServiceHealthCheck | None = None
    environment: dict[str, str] = Field(default_factory=dict)
    restart_policy: RestartPolicy = Field(default_factory=lambda: RestartPolicy(mode="manual"))
    depends_on: list[str] = Field(default_factory=list)
    supervised_by: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_active_process_contract(self) -> "ServiceSpec":
        if self.implementation_status == ServiceImplementationStatus.ACTIVE and self.service_type != ServiceType.EMBEDDED_WORKER:
            if not self.command:
                raise ValueError(f"{self.service_id}: active non-embedded services must define a command")
            if self.pid_file is None and self.restart_policy.mode == "manual":
                raise ValueError(f"{self.service_id}: active non-embedded services must define a pid_file")
        return self


class ServiceManifest(BaseModel):
    schema_version: int = Field(ge=1)
    profile: str = Field(min_length=1)
    description: str | None = None
    services: list[ServiceSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_service_graph(self) -> "ServiceManifest":
        service_ids = [service.service_id for service in self.services]
        duplicates = sorted({service_id for service_id in service_ids if service_ids.count(service_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate service_id values: {', '.join(duplicates)}")
        known = set(service_ids)
        for service in self.services:
            missing = sorted(dependency for dependency in service.depends_on if dependency not in known)
            if missing:
                raise ValueError(f"{service.service_id}: unknown dependencies: {', '.join(missing)}")
            if service.supervised_by is not None and service.supervised_by not in known:
                raise ValueError(f"{service.service_id}: unknown supervisor: {service.supervised_by}")
        return self

    def ordered_services(self) -> list[ServiceSpec]:
        return sorted(self.services, key=lambda service: (service.startup_order, service.service_id))

    def service(self, service_id: str) -> ServiceSpec:
        for service in self.services:
            if service.service_id == service_id:
                return service
        raise KeyError(service_id)


def load_service_manifest(path: Path | str | None = None) -> ServiceManifest:
    manifest_path = Path(path) if path is not None else DEFAULT_SERVICE_MANIFEST_PATH
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return ServiceManifest.model_validate(payload)


class ServiceGraphNode(BaseModel):
    service_id: str
    display_name: str
    service_type: ServiceType
    implementation_status: ServiceImplementationStatus
    required: bool
    startup_order: int


class ServiceGraphEdge(BaseModel):
    source: str
    target: str
    relation: str


class ServiceGraph(BaseModel):
    nodes: list[ServiceGraphNode] = Field(default_factory=list)
    edges: list[ServiceGraphEdge] = Field(default_factory=list)


def build_service_graph(manifest: ServiceManifest | None = None) -> ServiceGraph:
    resolved_manifest = manifest or load_service_manifest()
    nodes = [
        ServiceGraphNode(
            service_id=service.service_id,
            display_name=service.display_name,
            service_type=service.service_type,
            implementation_status=service.implementation_status,
            required=service.required,
            startup_order=service.startup_order,
        )
        for service in resolved_manifest.ordered_services()
    ]
    edges: list[ServiceGraphEdge] = []
    for service in resolved_manifest.ordered_services():
        edges.extend(
            ServiceGraphEdge(source=dependency, target=service.service_id, relation="depends_on")
            for dependency in service.depends_on
        )
        if service.supervised_by is not None:
            edges.append(
                ServiceGraphEdge(source=service.supervised_by, target=service.service_id, relation="supervises")
            )
    return ServiceGraph(nodes=nodes, edges=edges)
