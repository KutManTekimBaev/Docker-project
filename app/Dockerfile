FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements && useradd -m -s /bit/bash appuser
USER appuser
CMD ["python", "app.py"]
