#!/bin/bash
echo "Starting Stable Diffusion WebUI"
if [ ! -d "/app/sd-webui/webui.sh" ] || [ ! "$(ls -A "/app/sd-webui/webui.sh")" ]; then
  echo "Files not found, cloning..."


  echo "Using Forge"
  git clone https://github.com/lllyasviel/stable-diffusion-webui-forge.git /app/sd-webui
  cd /app/sd-webui



  chmod +x /app/sd-webui/webui.sh

  #i don't really know if this is the best way to do this
  python3 -m venv venv
  source ./venv/bin/activate
  pip install -r ./requirements_versions.txt
  pip install insightface
  deactivate
fi
