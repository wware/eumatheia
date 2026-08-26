# Ancillary Dockerfile for docker-demo exhibit
FROM python:3.13-slim

WORKDIR /app

# Install a simple web server
RUN pip install --no-cache-dir fastapi uvicorn

# Create a simple hello world app
RUN echo 'from fastapi import FastAPI\n\
app = FastAPI()\n\
\n\
@app.get("/")\n\
def read_root():\n\
    return {"message": "Hello from Docker!", "demo": "ancillary-files"}\n\
\n\
@app.get("/health")\n\
def health():\n\
    return {"status": "healthy"}' > main.py

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
