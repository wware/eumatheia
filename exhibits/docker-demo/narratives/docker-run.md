# Run Docker Container

This step uses an **ancillary docker-compose file**:
- `docker-compose.app.yml` - Defines the service configuration

## What's in the Compose File?

The ancillary `docker-compose.app.yml` defines:
- Service name: `demo-app`
- Build context using the ancillary Dockerfile
- Port mapping: 9001 → 8080
- Environment variables

## Try It Out

In a full implementation, you would run:

```bash
# docker-compose -f docker-compose.app.yml up -d
```

Then access the app in the **App** tab on the right!

## How It Works

The exhibit YAML for this step includes:

```yaml
ancillary:
  compose: docker-compose.app.yml
```

The ContainerManager reads this and provisions a per-session container.

## Summary

You've learned about:
- ✅ Ancillary Dockerfiles
- ✅ Ancillary scripts
- ✅ Ancillary docker-compose files
- ✅ Per-step resource configuration

This is the foundation for dynamic, step-specific container provisioning!
