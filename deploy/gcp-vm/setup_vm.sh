#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

echo "=== Removing Conflicting Old Node.js Packages ==="
sudo apt-get purge -y nodejs npm libnode-dev || true
sudo apt-get autoremove -y || true

echo "=== System Update and Package Installation ==="
sudo apt-get update
sudo apt-get install -y curl ca-certificates gnupg sqlite3

# Add NodeSource GPG key and repository
echo "=== Installing NodeSource Node.js v20 ==="
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y python3-pip python3-venv nodejs

# Install Puppeteer browser dependencies for headless Chrome
echo "=== Installing Puppeteer Linux Dependencies ==="
sudo apt-get install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglu1-mesa

echo "=== Setting up Python Virtual Environment ==="
cd /home/mahilkingdomorai/radio-ai-manager
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

echo "=== Installing Node.js WhatsApp Gateway dependencies ==="
cd /home/mahilkingdomorai/radio-ai-manager/whatsapp
# Remove any failed node_modules state first
rm -rf node_modules
npm install --no-audit --no-fund

echo "=== Copying and Reloading Systemd Service Files ==="
sudo cp /home/mahilkingdomorai/radio-ai-manager/deploy/gcp-vm/radio-command-center.service /etc/systemd/system/
sudo cp /home/mahilkingdomorai/radio-ai-manager/deploy/gcp-vm/radio-whatsapp-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload

echo "=== Starting and Enabling Services ==="
sudo systemctl restart radio-command-center
sudo systemctl restart radio-whatsapp-gateway
sudo systemctl enable radio-command-center
sudo systemctl enable radio-whatsapp-gateway

echo "=== Deployment Completed Successfully ==="
