FROM python:3.11-slim

WORKDIR /app

# Copy and install dependencies (no torch/spacy needed)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "main.py"]
