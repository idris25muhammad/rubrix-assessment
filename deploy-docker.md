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

The deployment files already live in the repository root:
- `Dockerfile` — Python 3.11 image; installs dependencies and Gunicorn; on startup runs
  `flask db upgrade` (applies all migrations, including the SO-PI / sharing schema) and
  boots the app via the `app:create_app()` factory (which also seeds the default accounts
  and the RKS SO-PI set).
- `docker-compose.yml` — `rubrix_db` (`mysql:8.0`) service + `rubrix_web` service. The
  MySQL port is **not** exposed to the host, and the web service is bound **only to
  `127.0.0.1:5000`** on the host (not public). Public access is handled by nginx on the
  server via reverse proxy (see the "Nginx Reverse Proxy" section below).
- `.dockerignore` — keeps `venv`, `instance/`, `.env`, and build artifacts out of the image.

Secret values come from a `.env` file in the project root (see Step 2 below) via
`${VAR:-default}` substitution — you only need to edit `.env`, not the compose file.

---

## 3. Step-by-Step Deployment

On your Ubuntu server, perform the following steps:

### Step 1: Create the Deployment Directory and Clone the Repository
Create a deployment directory (e.g. under `/opt`) and clone the project there:
```bash
# Create the deploy directory (adjust the path if you prefer)
sudo mkdir -p /opt/rubrix
sudo chown -R $USER:$USER /opt/rubrix

cd /opt/rubrix
git clone https://github.com/idris25muhammad/rubrix-assessment.git
cd rubrix-assessment
```
> Docker Compose must be able to read the `.env` file in this directory (Step 2),
> so the directory must be writable by your user (done above via `chown`).

### Step 2: Set Up Production Environment Variables
Create a `.env` file in the project root (Docker Compose reads it automatically):
```bash
nano .env
```
Add your production values:
```env
RKS_SECRET_KEY=your_very_secure_random_key_here
MYSQL_ROOT_PASSWORD=your_root_db_password
MYSQL_USER=rubrikrks
MYSQL_PASSWORD=your_db_password
MYSQL_DB=rubrikrks
```
Generate a strong secret key with: `openssl rand -hex 32`

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
docker compose logs -f rubrix_web
```
The web app is only reachable on the host's loopback at this point:
```bash
curl -I http://127.0.0.1:5000/login
```

### Nginx Reverse Proxy
The app is **not** exposed to the internet directly. Put nginx in front of it
(e.g. on the same server) and proxy to the loopback port:

```nginx
server {
    listen 80;
    server_name rubrix.example.com;   # or your public IP / subdomain

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

If the domain already hosts another site (e.g. a landing page on port 443), serve
the app on a **dedicated HTTPS port** instead of a sub-path — that avoids prefix
rewriting entirely. Add a separate `server` block that proxies to the loopback
port:

```nginx
server {
    listen 2021 ssl;
    server_name rks.polibatam.ac.id;

    ssl_certificate /etc/letsencrypt/live/rks.polibatam.ac.id/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/rks.polibatam.ac.id/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

This exposes the app at `https://rks.polibatam.ac.id:2021` without touching the
landing page. Open the port in the firewall: `sudo ufw allow 2021/tcp`.

### Default Seeded Accounts
On first startup the app seeds one `tim_kurikulum` account per study program
(login **password = email**):
- `rks@polibatam.ac.id` (RKS)
- `ti@polibatam.ac.id` (D3-TI)
- `trm@polibatam.ac.id` (D4-TRM)
- `tg@polibatam.ac.id` (D3-TG)
- `anim@polibatam.ac.id` (D4-ANIM)
- `trpl@polibatam.ac.id` (D4-TRPL)
- `tp@polibatam.ac.id` (D4-TP)
- `s2tk@polibatam.ac.id` (S2-TK)

Each account only manages its own program's SO-PI and dashboard. Lecturers are
created later via the **Users** page, and courses can be shared to them via the
**Share** button on the dashboard.

The RKS SO-PI set is auto-seeded from `static/data/so-pi.json` on first start;
other programs' SO-PI sets are created by their tim_kurikulum account in the
**SO-PI** page. New DB migrations are applied automatically by `flask db upgrade`
in the container startup command.

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
docker compose up -d --build rubrix_web
```

### Backup Database (MySQL dump)
To backup your production data, run (use the password from your `.env` `MYSQL_PASSWORD`):
```bash
docker exec rubrix_db mysqldump -u rubrikrks -pYOUR_MYSQL_PASSWORD rubrikrks > backup.sql
```
