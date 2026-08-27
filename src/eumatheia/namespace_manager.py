"""
Kubernetes Namespace Manager for session isolation.

This module manages the lifecycle of per-session Kubernetes namespaces,
applying resource quotas, network policies, and RBAC rules.
"""

from pathlib import Path
from typing import Any
import logging

from kubernetes import client, config
from kubernetes.client.rest import ApiException
import yaml

logger = logging.getLogger(__name__)


class NamespaceManager:
    """Manages Kubernetes namespaces for session isolation."""

    def __init__(self, template_dir: Path | None = None) -> None:
        """
        Initialize the namespace manager.

        Args:
            template_dir: Directory containing namespace template YAML files.
                         Defaults to manifests/session-templates/
        """
        try:
            # Try to load in-cluster config first (when running in k8s)
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes configuration")
        except config.ConfigException:
            # Fall back to kubeconfig (local development)
            config.load_kube_config()
            logger.info("Loaded kubeconfig from ~/.kube/config")

        self.core_v1 = client.CoreV1Api()
        self.rbac_v1 = client.RbacAuthorizationV1Api()
        self.networking_v1 = client.NetworkingV1Api()

        if template_dir is None:
            # Default to manifests/session-templates relative to project root
            template_dir = Path(__file__).parent.parent.parent / "manifests" / "session-templates"
        self.template_dir = template_dir

        logger.info(f"NamespaceManager initialized with templates from {self.template_dir}")

    def _load_template(self, filename: str, session_id: str) -> list[dict[str, Any]]:
        """
        Load and process a YAML template file.

        Args:
            filename: Name of the template file (e.g., "resource-quota.yaml")
            session_id: Session ID to inject into namespace field

        Returns:
            List of Kubernetes resource dictionaries with namespace set
        """
        template_path = self.template_dir / filename
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        content = template_path.read_text()
        # Parse YAML (may contain multiple documents separated by ---)
        resources = list(yaml.safe_load_all(content))

        # Inject namespace into each resource
        namespace = f"sess-{session_id}"
        for resource in resources:
            if resource and "metadata" in resource:
                resource["metadata"]["namespace"] = namespace

        return resources

    async def create_namespace(self, session_id: str) -> dict[str, Any]:
        """
        Create a new namespace for the session with all isolation resources.

        Args:
            session_id: Unique session identifier

        Returns:
            Dictionary with namespace metadata including name and creation time

        Raises:
            ApiException: If namespace creation fails
        """
        namespace_name = f"sess-{session_id}"
        logger.info(f"Creating namespace {namespace_name}")

        # 1. Create the namespace
        namespace = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=namespace_name,
                labels={
                    "app": "eumatheia",
                    "session-id": session_id,
                    "managed-by": "eumatheia-orchestrator",
                },
            )
        )

        try:
            ns_response = self.core_v1.create_namespace(namespace)
            logger.info(f"Created namespace: {namespace_name}")
        except ApiException as e:
            if e.status == 409:
                logger.warning(f"Namespace {namespace_name} already exists")
                ns_response = self.core_v1.read_namespace(namespace_name)
            else:
                logger.error(f"Failed to create namespace {namespace_name}: {e}")
                raise

        # 2. Apply ResourceQuota
        try:
            quota_resources = self._load_template("resource-quota.yaml", session_id)
            for resource in quota_resources:
                self.core_v1.create_namespaced_resource_quota(
                    namespace=namespace_name,
                    body=resource,
                )
            logger.info(f"Applied ResourceQuota to {namespace_name}")
        except ApiException as e:
            logger.error(f"Failed to create ResourceQuota: {e}")
            raise

        # 3. Apply LimitRange
        try:
            limit_resources = self._load_template("limit-range.yaml", session_id)
            for resource in limit_resources:
                self.core_v1.create_namespaced_limit_range(
                    namespace=namespace_name,
                    body=resource,
                )
            logger.info(f"Applied LimitRange to {namespace_name}")
        except ApiException as e:
            logger.error(f"Failed to create LimitRange: {e}")
            raise

        # 4. Apply NetworkPolicy
        try:
            network_resources = self._load_template("network-policy.yaml", session_id)
            for resource in network_resources:
                self.networking_v1.create_namespaced_network_policy(
                    namespace=namespace_name,
                    body=resource,
                )
            logger.info(f"Applied NetworkPolicy to {namespace_name}")
        except ApiException as e:
            logger.error(f"Failed to create NetworkPolicy: {e}")
            raise

        # 5. Apply RBAC (ServiceAccount, Role, RoleBinding)
        try:
            rbac_resources = self._load_template("service-account.yaml", session_id)
            for resource in rbac_resources:
                kind = resource.get("kind")
                if kind == "ServiceAccount":
                    self.core_v1.create_namespaced_service_account(
                        namespace=namespace_name,
                        body=resource,
                    )
                elif kind == "Role":
                    self.rbac_v1.create_namespaced_role(
                        namespace=namespace_name,
                        body=resource,
                    )
                elif kind == "RoleBinding":
                    self.rbac_v1.create_namespaced_role_binding(
                        namespace=namespace_name,
                        body=resource,
                    )
            logger.info(f"Applied RBAC resources to {namespace_name}")
        except ApiException as e:
            logger.error(f"Failed to create RBAC resources: {e}")
            raise

        return {
            "namespace": namespace_name,
            "session_id": session_id,
            "created_at": ns_response.metadata.creation_timestamp.isoformat(),
            "status": "active",
        }

    async def delete_namespace(self, session_id: str) -> None:
        """
        Delete the namespace for the session.

        This will cascade delete all resources within the namespace.

        Args:
            session_id: Unique session identifier

        Raises:
            ApiException: If namespace deletion fails
        """
        namespace_name = f"sess-{session_id}"
        logger.info(f"Deleting namespace {namespace_name}")

        try:
            self.core_v1.delete_namespace(
                name=namespace_name,
                body=client.V1DeleteOptions(
                    propagation_policy="Foreground",
                ),
            )
            logger.info(f"Deleted namespace: {namespace_name}")
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Namespace {namespace_name} not found (already deleted?)")
            else:
                logger.error(f"Failed to delete namespace {namespace_name}: {e}")
                raise

    async def get_namespace_metadata(self, session_id: str) -> dict[str, Any] | None:
        """
        Get metadata about a namespace.

        Args:
            session_id: Unique session identifier

        Returns:
            Dictionary with namespace metadata or None if not found
        """
        namespace_name = f"sess-{session_id}"

        try:
            ns = self.core_v1.read_namespace(namespace_name)
            return {
                "namespace": namespace_name,
                "session_id": session_id,
                "created_at": ns.metadata.creation_timestamp.isoformat(),
                "status": ns.status.phase,
                "labels": ns.metadata.labels,
            }
        except ApiException as e:
            if e.status == 404:
                logger.debug(f"Namespace {namespace_name} not found")
                return None
            logger.error(f"Failed to read namespace {namespace_name}: {e}")
            raise

    async def list_active_sessions(self) -> list[dict[str, Any]]:
        """
        List all active session namespaces.

        Returns:
            List of namespace metadata dictionaries
        """
        try:
            namespaces = self.core_v1.list_namespace(
                label_selector="app=eumatheia,managed-by=eumatheia-orchestrator"
            )
            return [
                {
                    "namespace": ns.metadata.name,
                    "session_id": ns.metadata.labels.get("session-id"),
                    "created_at": ns.metadata.creation_timestamp.isoformat(),
                    "status": ns.status.phase,
                }
                for ns in namespaces.items
            ]
        except ApiException as e:
            logger.error(f"Failed to list namespaces: {e}")
            raise
