# Testado por mim apenas com `python3 -m py_compile` e um boot local via
# uvicorn dentro do sandbox — NÃO testado com `docker build` de verdade
# (este ambiente não tem o Docker Engine instalado). Ver README.md.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
