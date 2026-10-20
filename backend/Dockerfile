FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home app && mkdir /data && chown app /data
USER app
CMD ["uvicorn", "autoapply.main:app", "--host", "0.0.0.0", "--port", "8000"]
