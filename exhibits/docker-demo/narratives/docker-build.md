# Build Docker Image

This step uses **ancillary files**:
- `Dockerfile.app` - A custom Dockerfile for this step
- `setup.sh` - A setup script

## Step 1: Run the Setup Script

First, let's run the setup script (an ancillary file):

```bash
cd /tmp
bash setup.sh
```

**Note:** In a real implementation, the setup script would be automatically available from the exhibit's ancillary files.

## Step 2: Build the Image

Now let's build a Docker image. The Dockerfile is defined in the exhibit's ancillary files:

```bash
# View what the Dockerfile contains
echo "The Dockerfile.app creates a simple FastAPI app"
```

**Note:** In the future, you'll be able to build from the ancillary Dockerfile directly:
```bash
# docker build -f Dockerfile.app -t demo-app .
```

## What's Happening?

The exhibit YAML for this step includes:

```yaml
ancillary:
  dockerfile: Dockerfile.app
  scripts:
    - setup.sh
```

This tells Eumatheia to make these files available for this specific step.

Click **Next** when ready!
