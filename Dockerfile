FROM python:3.11-slim

WORKDIR /app

# Install dependencies specifically
COPY resource/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set unbuffered output for logging
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
