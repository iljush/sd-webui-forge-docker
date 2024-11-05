FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04
LABEL org.opencontainers.image.source https://github.com/Yummiii/sd-webui-forge-docker
WORKDIR /app

# Install necessary packages
RUN apt update && apt upgrade -y
RUN apt install -y wget git python3 python3-venv libgl1 libglib2.0-0 apt-transport-https libgoogle-perftools-dev bc python3-pip

# Clone the repository directly during build
RUN git clone https://github.com/lllyasviel/stable-diffusion-webui-forge.git /app/sd-webui
WORKDIR /app/sd-webui



# Set up the Python environment and install requirements
RUN python3 -m venv venv && \
    . venv/bin/activate && \
    pip install -r requirements_versions.txt && \
    pip install insightface && \
    deactivate

# Set up permissions and user
RUN useradd -m webui && \
    chown -R webui:webui /app
USER webui

# Copy the entry point script
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

# Start the application
ENTRYPOINT ["/app/run.sh"]