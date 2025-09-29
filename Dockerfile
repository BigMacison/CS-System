FROM python:3.11-slim

# Workdir in Container
WORKDIR /app

RUN mkdir -p /app/configs /app/logs /app/Servers

# Copy requirements.txt into container and install python modules
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything else into container
COPY . .

EXPOSE 8000

CMD ["python", "main.py"]

