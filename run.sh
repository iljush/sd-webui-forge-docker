#!/bin/bash
echo "Starting Stable Diffusion WebUI"

# Check if files are available
if [ -d "/app/sd-webui" ]; then
  echo "Files found, starting..."
  cd /app/sd-webui
  git pull
  exec /app/sd-webui/webui.sh $ARGS
else
  echo "Directory /app/sd-webui is missing!"
  exit 1
fi
