# Deployment Guide: Ubuntu Server with Docker

This guide explains how to deploy the RubriX application to an Ubuntu Server using Docker and Docker Compose.

---

## 1. Prerequisites (Ubuntu Server)

Before starting, ensure your Ubuntu server has Docker and Git installed.

### Install Docker on Ubuntu
Run the following commands on your Ubuntu server to install Docker:
```bash
# Update package database
sudo apt update

# Install prerequisites
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common gnupg lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up the repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine & Compose
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable and start Docker service
sudo systemctl enable docker
sudo systemctl start docker

# Add your user to the docker group (optional, requires relog)
sudo usermod -aG docker $USER
```

---

## 2. Project Deployment Configuration Files

Create these files in the root of your project directory (`rubrix-assessment`).

### `Dockerfile`
Create a `Dockerfile` file in your project root:
```dockerfile
# Use official slim Python runtime
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Set work directory
WORKDIR /app

# Install system dependencies (required for compiling PyMySQL/Argon2 if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmariadb-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# Copy project source code
COPY . .

# Expose port
EXPOSE 5000

# Startup script to run migrations and start gunicorn
CMD ["sh", "-c", "flask db upgrade && gunicorn --bind 0.0.0.0:5000 --workers 4 app:create_app\\(\\)"]
```

### `docker-compose.yml`
Create a `docker-compose.yml` file in your project root:
```yaml
version: '3.8'

services:
  db:
    image: mysql:8.0
    container_name: rubrix_mysql
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: root_password_here
      MYSQL_DATABASE: rubrikrks
      MYSQL_USER: rubrikrks
      MYSQL_PASSWORD: rubrikrks_prod_password
    volumes:
      - mysql_data:/var/lib/mysql
    ports:
      - "3306:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      timeout: 20s
      retries: 10

  web:
    build: .
    container_name: rubrix_web
    restart: always
    ports:
      - "80:5000"
    environment:
      - RKS_SECRET_KEY=production-secret-key-change-me
      - RKS_PORT=5000
      - RKS_DB_ENGINE=mysql
      - RKS_MYSQL_HOST=db
      - RKS_MYSQL_PORT=3306
      - RKS_MYSQL_USER=rubrikrks
      - RKS_MYSQL_PASSWORD=rubrikrks_prod_password
      - RKS_MYSQL_DB=rubrikrks
    depends_on:
      db:
        condition: service_healthy

volumes:
  mysql_data:
```

---

## 3. Step-by-Step Deployment

On your Ubuntu server, perform the following steps:

### Step 1: Clone the Repository
```bash
git clone https://github.com/idris25muhammad/rubrix-assessment.git
cd rubrix-assessment
```

### Step 2: Set Up Production Environment Variables
If you want to configure variables outside `docker-compose.yml`, create a `.env` file in the root directory:
```bash
nano .env
```
Add your production values:
```env
RKS_SECRET_KEY=your_very_secure_random_key_here
RKS_PORT=5000
RKS_DB_ENGINE=mysql
RKS_MYSQL_HOST=db
RKS_MYSQL_PORT=3306
RKS_MYSQL_USER=rubrikrks
RKS_MYSQL_PASSWORD=rubrikrks_prod_password
RKS_MYSQL_DB=rubrikrks
```

### Step 3: Run the Containers
Start the services in the background using Docker Compose:
```bash
docker compose up -d --build
```

### Step 4: Verify Deployment
Check if the containers are up and running:
```bash
docker compose ps
```
You can read container logs to verify database migrations and server initialization:
```bash
docker compose logs -f web
```

---

## 4. Maintenance & Updates

### Restart Services
```bash
docker compose restart
```

### Apply Code Updates (Git Pull & Rebuild)
To pull the latest changes from your repository and rebuild the app:
```bash
# Pull changes
git pull origin main

# Rebuild and restart web container
docker compose up -d --build web
```

### Backup Database (MySQL dump)
To backup your production data, run:
```bash
docker exec rubrix_mysql mysqldump -u rubrikrks -prubrikrks_prod_password rubrikrks > backup.sql
```
