FROM python:3.12-slim

# Work from the root so that `import app` resolves to /app/ regardless of
# whether the directory comes from COPY or the live-reload volume mount.
WORKDIR /

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
