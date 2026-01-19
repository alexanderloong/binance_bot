FROM python:3.9-slim

WORKDIR /app

# Install dependencies specifically
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set unbuffered output for logging
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
