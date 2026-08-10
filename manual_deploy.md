# Manual Deployment Guide: Ubuntu Server (Clean Installation)

This guide explains how to manually deploy the RubriX application on an Ubuntu 24.04 server (without Docker) using Python 3, MySQL Server, Gunicorn, systemd, and Nginx. The application is configured to run under the subpath `/rubrix` on the domain `rks.polibatam.ac.id`.

---

## Steps for Deployment

### Step 1: Install Dependencies
Run this command on your Ubuntu VPS to install Python 3, virtual environment tools, MySQL, Nginx, and compiler tools:
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip mysql-server nginx build-essential libmariadb-dev gcc
```

---

### Step 2: Configure MySQL Server
1. Log in to your local MySQL server as root:
   ```bash
   sudo mysql
   ```
2. Run these SQL commands to set up the database and user (replace `'PASSWORD_DB_ANDA'` with a strong password):
   ```sql
   CREATE DATABASE rubrikrks CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'rubrikrks'@'localhost' IDENTIFIED BY 'PASSWORD_DB_ANDA';
   GRANT ALL PRIVILEGES ON rubrikrks.* TO 'rubrikrks'@'localhost';
   FLUSH PRIVILEGES;
   EXIT;
   ```

---

### Step 3: Setup Project Directory
1. Create the installation path, set owner permissions, and clone the repository:
   ```bash
   sudo mkdir -p /var/www/rubrix
   sudo chown -R $USER:$USER /var/www/rubrix
   cd /var/www/rubrix
   git clone https://github.com/idris25muhammad/rubrix-assessment.git
   cd rubrix-assessment
   ```

---

### Step 4: Setup Python Virtual Environment
1. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Upgrade pip and install the project requirements, including Gunicorn and PyMySQL (required for database connectivity):
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install gunicorn pymysql
   ```

---

### Step 5: Configure Production Environment (`.env`)
1. Create a `.env` file in the project directory:
   ```bash
   nano .env
   ```
2. Paste the following configuration, substituting your own secret key and your MySQL password:
   ```env
   RKS_SECRET_KEY=isi_dengan_random_key_bebas_dan_panjang_sekali
   RKS_PORT=5000
   RKS_DB_ENGINE=mysql
   RKS_MYSQL_HOST=127.0.0.1
   RKS_MYSQL_PORT=3306
   RKS_MYSQL_USER=rubrikrks
   RKS_MYSQL_PASSWORD=PASSWORD_DB_ANDA
   RKS_MYSQL_DB=rubrikrks
   ```
3. Save and close (`CTRL+O` -> `Enter` -> `CTRL+X`).

---

### Step 6: Migrate and Seed Database
Run the schema migration commands inside your virtual environment. This will create all the necessary database tables and auto-seed the default curriculum team accounts:
```bash
source venv/bin/activate
flask db upgrade
```

---

### Step 7: Create Gunicorn Systemd Service
Create a systemd unit file to run the Flask application as a background service:
1. Open the systemd unit file:
   ```bash
   sudo nano /etc/systemd/system/rubrix.service
   ```
2. Paste the following configuration (verify that `User` matches your VPS username, e.g., `webadmin-rks`):
   ```ini
   [Unit]
   Description=Gunicorn instance to serve RubriX Application
   After=network.target

   [Service]
   User=webadmin-rks
   WorkingDirectory=/var/www/rubrix/rubrix-assessment
   Environment="PATH=/var/www/rubrix/rubrix-assessment/venv/bin"
   ExecStart=/var/www/rubrix/rubrix-assessment/venv/bin/gunicorn --workers 4 --bind 127.0.0.1:5000 'app:app'

   [Install]
   WantedBy=multi-user.target
   ```
3. Save and close (`CTRL+O` -> `Enter` -> `CTRL+X`).
4. Start and enable the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start rubrix
   sudo systemctl enable rubrix
   ```
5. Verify the service is running:
   ```bash
   sudo systemctl status rubrix
   ```

---

### Step 8: Configure Nginx Routing for `/rubrix`
1. Disable the default symlink:
   ```bash
   sudo rm -f /etc/nginx/sites-enabled/default
   ```
2. Create and open the site configuration file:
   ```bash
   sudo ln -s /etc/nginx/sites-available/rkspolibatam /etc/nginx/sites-enabled/
   sudo nano /etc/nginx/sites-available/rkspolibatam
   ```
3. Paste the following configuration:
   ```nginx
   server {
       listen 80;
       server_name rks.polibatam.ac.id;
       return 301 https://$host$request_uri;
   }

   server {
       server_name rks.polibatam.ac.id;

       root /var/www/rkslandingnextjs/out;
       index index.html index.htm;

       if ($request_uri ~ ^/\.html$|^\.html$) {
           return 301 https://$host/$1$2;
       }

       # 1. Redirect jika user mengakses tanpa tanda '/' di akhir
       location = /rubrix {
           return 301 $scheme://$http_host/rubrix/;
       }

       # 2. Proxy ke aplikasi Gunicorn (RubriX)
       location ^~ /rubrix/ {
           proxy_pass http://127.0.0.1:5000/;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_set_header X-Forwarded-Prefix /rubrix;
       }

       location / {
           try_files $uri $uri/ $uri.html =404;
       }

       location ~* \.(jpg|jpeg|png|gif|ico|svg|webp|woff|woff2)$ {
           expires 30d;
           add_header Cache-Control "public, no-transform";
       }

       location ~* \.(css|js)$ {
           expires 1h;
           add_header Cache-Control "public, no-transform, must-revalidate";
       }

       listen 443 ssl; # managed by Certbot
       ssl_certificate /etc/letsencrypt/live/rks.polibatam.ac.id/fullchain.pem; # managed by Certbot
       ssl_certificate_key /etc/letsencrypt/live/rks.polibatam.ac.id/privkey.pem; # managed by Certbot
       include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
       ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot
   }
   ```
4. Save and close (`CTRL+O` -> `Enter` -> `CTRL+X`).
5. Test the Nginx configuration and reload it:
   ```bash
   sudo nginx -t
   sudo systemctl restart nginx
   ```

---

### Step 9: Verify
Navigate to `https://rks.polibatam.ac.id/rubrix/` on your browser to verify that the application and its assets load correctly.
