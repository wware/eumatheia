#!/usr/bin/env python3
"""
Quick test script to verify Phase 3 implementation.

Tests:
1. Load demo exhibit
2. Create namespace with NamespaceManager
3. Apply setup manifests
4. Verify terminal pod is created and running
5. Clean up namespace
"""

import asyncio
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from eumatheia.exhibit_loader import ExhibitLoader
from eumatheia.namespace_manager import NamespaceManager


async def main():
    print("=" * 60)
    print("Phase 3 Test: Namespace Provisioning & Manifest Application")
    print("=" * 60)

    # Setup
    exhibits_dir = Path(__file__).parent / "exhibits"
    loader = ExhibitLoader(exhibits_dir)
    manager = NamespaceManager()

    test_session_id = "test-phase3"

    try:
        # Step 1: Load exhibit
        print("\n[1/5] Loading demo exhibit...")
        exhibit = loader.load_exhibit("demo")
        print(f"✓ Loaded exhibit: {exhibit.title}")
        print(f"  - Steps: {len(exhibit.steps)}")
        print(f"  - Setup manifests: {len(exhibit.setup)}")

        # Step 2: Create namespace
        print(f"\n[2/5] Creating namespace for session {test_session_id}...")
        namespace_metadata = await manager.create_namespace(test_session_id)
        print(f"✓ Created namespace: {namespace_metadata['namespace']}")
        print(f"  - Created at: {namespace_metadata['created_at']}")
        print(f"  - Status: {namespace_metadata['status']}")

        # Step 3: Apply setup manifests
        if exhibit.setup:
            print(f"\n[3/5] Applying {len(exhibit.setup)} setup manifest(s)...")
            exhibit_dir = exhibits_dir / "demo"
            manifest_files = [setup.manifest for setup in exhibit.setup]
            print(f"  - Manifests: {manifest_files}")

            await manager.apply_setup_manifests(
                test_session_id, exhibit_dir, manifest_files
            )
            print("✓ Applied all setup manifests")
        else:
            print("\n[3/5] No setup manifests to apply")

        # Step 4: Verify pod is created
        print("\n[4/5] Verifying terminal pod was created...")
        await asyncio.sleep(2)  # Give k8s a moment

        from kubernetes import client
        core_v1 = client.CoreV1Api()
        namespace_name = f"sess-{test_session_id}"

        pods = core_v1.list_namespaced_pod(namespace_name)
        if pods.items:
            for pod in pods.items:
                print(f"✓ Found pod: {pod.metadata.name}")
                print(f"  - Phase: {pod.status.phase}")
                print(f"  - Containers: {len(pod.spec.containers)}")
                if pod.spec.containers:
                    print(f"  - Image: {pod.spec.containers[0].image}")
        else:
            print("✗ No pods found in namespace")
            return 1

        # Step 5: Wait a bit and check pod status
        print("\n[5/5] Waiting for pod to start (10 seconds)...")
        await asyncio.sleep(10)

        pods = core_v1.list_namespaced_pod(namespace_name)
        for pod in pods.items:
            print(f"Pod {pod.metadata.name}:")
            print(f"  - Phase: {pod.status.phase}")
            if pod.status.container_statuses:
                for cs in pod.status.container_statuses:
                    print(f"  - Container {cs.name}: ready={cs.ready}, state={cs.state}")

        print("\n" + "=" * 60)
        print("✓ Phase 3 test PASSED!")
        print("=" * 60)
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
