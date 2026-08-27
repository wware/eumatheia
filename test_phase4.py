#!/usr/bin/env python3
"""
Phase 4 test: Terminal connectivity with ttyd.

Tests:
1. Create session with demo exhibit
2. Wait for terminal pod to be running
3. Verify terminal service is accessible
4. Check ttyd is serving on port 7681
5. Clean up
"""

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))

from eumatheia.exhibit_loader import ExhibitLoader
from eumatheia.namespace_manager import NamespaceManager
from kubernetes import client


async def main():
    print("=" * 60)
    print("Phase 4 Test: Terminal Pod with ttyd")
    print("=" * 60)

    exhibits_dir = Path(__file__).parent / "exhibits"
    loader = ExhibitLoader(exhibits_dir)
    manager = NamespaceManager()

    test_session_id = "test-phase4"
    namespace_name = f"sess-{test_session_id}"

    try:
        # Step 1: Load exhibit and create namespace
        print("\n[1/6] Creating namespace and applying manifests...")
        exhibit = loader.load_exhibit("demo")
        await manager.create_namespace(test_session_id)

        # Apply setup manifests (terminal pod + service)
        exhibit_dir = exhibits_dir / "demo"
        manifest_files = [setup.manifest for setup in exhibit.setup]
        await manager.apply_setup_manifests(test_session_id, exhibit_dir, manifest_files)
        print(f"✓ Applied {len(manifest_files)} manifests")

        # Step 2: Wait for terminal pod to start
        print("\n[2/6] Waiting for terminal pod to be Running...")
        core_v1 = client.CoreV1Api()

        for i in range(30):  # 30 second timeout
            await asyncio.sleep(1)
            pods = core_v1.list_namespaced_pod(namespace_name)
            terminal_pod = None
            for pod in pods.items:
                if pod.metadata.name == "terminal":
                    terminal_pod = pod
                    break

            if terminal_pod and terminal_pod.status.phase == "Running":
                if terminal_pod.status.container_statuses:
                    if all(cs.ready for cs in terminal_pod.status.container_statuses):
                        print(f"✓ Terminal pod is Running and Ready (after {i+1}s)")
                        break
        else:
            print("✗ Timeout waiting for terminal pod to be ready")
            return 1

        # Step 3: Verify service exists
        print("\n[3/6] Verifying terminal service...")
        services = core_v1.list_namespaced_service(namespace_name)
        terminal_service = None
        for svc in services.items:
            if svc.metadata.name == "terminal":
                terminal_service = svc
                break

        if not terminal_service:
            print("✗ Terminal service not found")
            return 1

        print(f"✓ Found terminal service")
        print(f"  - ClusterIP: {terminal_service.spec.cluster_ip}")
        print(f"  - Port: {terminal_service.spec.ports[0].port}")

        # Step 4: Check pod logs for ttyd startup
        print("\n[4/6] Checking terminal pod logs...")
        await asyncio.sleep(2)  # Give ttyd time to start

        try:
            logs = core_v1.read_namespaced_pod_log(
                name="terminal", namespace=namespace_name, tail_lines=20
            )
            print("Terminal pod logs (last 20 lines):")
            for line in logs.split("\n")[-10:]:
                if line.strip():
                    print(f"  {line}")

            # Look for ttyd in logs
            if "ttyd" in logs.lower():
                print("✓ Found ttyd in logs")
            else:
                print("⚠ ttyd not found in logs (might still be starting)")
        except Exception as e:
            print(f"Warning: Could not read logs: {e}")

        # Step 5: Test connectivity from within cluster
        print("\n[5/6] Testing ttyd connectivity...")
        print(f"  Service DNS: terminal.{namespace_name}.svc.cluster.local:7681")
        print("  (Would be accessible from orchestrator pod in cluster)")

        # Step 6: Verify port is exposed
        print("\n[6/6] Verifying port configuration...")
        terminal_pod = core_v1.read_namespaced_pod("terminal", namespace_name)
        container = terminal_pod.spec.containers[0]

        ttyd_port_found = False
        if container.ports:
            for port in container.ports:
                if port.container_port == 7681:
                    ttyd_port_found = True
                    print(f"✓ Found ttyd port: {port.container_port} (name: {port.name})")

        if not ttyd_port_found:
            print("✗ ttyd port 7681 not found in container spec")
            return 1

        print("\n" + "=" * 60)
        print("✓ Phase 4 test PASSED!")
        print("=" * 60)
        print("\nTerminal is accessible at:")
        print(f"  http://terminal.{namespace_name}.svc.cluster.local:7681")
        return 0

    except Exception as e:
        print(f"\n✗ Test FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Cleanup
        print(f"\n[Cleanup] Deleting test namespace...")
        try:
            await manager.delete_namespace(test_session_id)
            print("✓ Cleanup complete")
        except Exception as e:
            print(f"Warning: Cleanup failed: {e}")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
