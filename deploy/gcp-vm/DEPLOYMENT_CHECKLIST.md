# Orai Radio GCP VM Deployment Checklist

Use this checklist to complete the production installation of the Orai Radio system on the GCP Compute VM instance.

## 1. Prerequisites Check
- [ ] GCP Compute VM instance `orai-radio-server` is running on IP `8.231.73.115`.
- [ ] OS is verified as `Ubuntu 22.04.5 LTS`.
- [ ] Incoming traffic rules (GCP VPC Firewall) allow ports:
  - `8000` (FastAPI backend console/API)
  - `3001` (Node/Express WhatsApp status endpoint)
  - `80` (HTTP stream & dashboard access)
- [ ] AzuraCast dashboard is active and running on `http://8.231.73.115/station/1`.

## 2. Server Installation Steps
- [ ] Connect to the VM via SSH:
  ```bash
  ssh mahilkingdomorai@8.231.73.115
  ```
- [ ] Install package dependencies:
  ```bash
  sudo apt update && sudo apt install -y python3-pip python3-venv nodejs npm git sqlite3
  ```
- [ ] Clone repository into `/home/mahilkingdomorai/radio-ai-manager`:
  ```bash
  git clone <repository_url> /home/mahilkingdomorai/radio-ai-manager
  cd /home/mahilkingdomorai/radio-ai-manager
  ```
- [ ] Copy and edit production environment variables:
  ```bash
  cp .env.example .env
  nano .env
  ```
  *(Fill in GEMINI_API_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, and ADMIN_API_KEY)*
- [ ] Initialize Python Virtual Environment & dependencies:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  pip install -r backend/requirements.txt
  ```
- [ ] Install Node.js Gateway dependencies:
  ```bash
  cd whatsapp
  npm install
  cd ..
  ```

## 3. Systemd Services Setup
- [ ] Copy systemd templates to system services directory:
  ```bash
  sudo cp deploy/gcp-vm/radio-command-center.service /etc/systemd/system/
  sudo cp deploy/gcp-vm/radio-whatsapp-gateway.service /etc/systemd/system/
  ```
- [ ] Reload systemd configurations:
  ```bash
  sudo systemctl daemon-reload
  ```
- [ ] Enable and start the backend service:
  ```bash
  sudo systemctl enable radio-command-center
  sudo systemctl start radio-command-center
  ```
- [ ] Enable and start the WhatsApp Gateway service:
  ```bash
  sudo systemctl enable radio-whatsapp-gateway
  sudo systemctl start radio-whatsapp-gateway
  ```
- [ ] Check service runtime health:
  ```bash
  sudo systemctl status radio-command-center
  sudo systemctl status radio-whatsapp-gateway
  ```

## 4. Reverse Proxy Setup (Optional)
- [ ] Install Nginx to reverse-proxy port 80 to port 8000 for public dashboard access:
  ```bash
  sudo apt install nginx
  ```
- [ ] Configure server blocks in `/etc/nginx/sites-available/default` to forward `/` to `http://localhost:8000`.

## 5. Security & Locks Verification
- [ ] Verify that `/api/admin/*` and the main dashboard request auth credentials.
- [ ] Verify that Vapi phone calling remains fully disabled (`CALLING_ENABLED=false` and `CALL_PROVIDER=disabled`).
- [ ] Verify that public endpoints `/api/public/*` return JSON responses correctly without authentication.
