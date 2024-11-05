
ARG HF_TOKEN


FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04
LABEL org.opencontainers.image.source https://github.com/Yummiii/sd-webui-forge-docker
WORKDIR /app

# Install necessary packages
RUN apt update && apt upgrade -y
RUN apt install -y wget git python3 python3-venv libgl1 libglib2.0-0 apt-transport-https libgoogle-perftools-dev bc python3-pip

# Clone the repository directly during build
RUN git clone https://github.com/lllyasviel/stable-diffusion-webui-forge.git /app/sd-webui 
    
RUN git clone https://github.com/Tok/sd-forge-deforum /app/sd-webui/extensions/sd-forge-deforum



#ADJUST FORGE
WORKDIR /app/sd-webui

#settings
COPY config.json config.json


# Set up the Python environment and install requirements
RUN python3 -m venv venv && \
    . venv/bin/activate && \
    pip install -r requirements_versions.txt && \
    pip install insightface && \
    pip install -r extensions/sd-forge-deforum/requirements.txt && \
    deactivate
 
RUN mkdir -p models/Stable-diffusion && \
    mkdir -p models/Stable-diffusion/Flux && \
    mkdir -p models/VAE && \
    mkdir -p models/Deforum   

RUN wget --header="Authorization: Bearer $HF_TOKEN" -O models/Stable-diffusion/Flux/flux1-dev-bnb-nf4-v2.safetensors https://huggingface.co/lllyasviel/flux1-dev-bnb-nf4/resolve/main/flux1-dev-bnb-nf4-v2.safetensors \
    && wget --header="Authorization: Bearer $HF_TOKEN" -O models/VAE/ae.safetensors https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors \
    && wget --header="Authorization: Bearer $HF_TOKEN" -O models/VAE/clip_l.safetensors https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors \
    && wget --header="Authorization: Bearer $HF_TOKEN" -O models/VAE/t5xxl_fp16.safetensors https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors \
    && wget --header="Authorization: Bearer $HF_TOKEN" -O models/Deforum/dpt_large-midas-2f21e586.pt https://huggingface.co/deforum/MiDaS/resolve/main/dpt_large-midas-2f21e586.pt

# Copy the entry point script
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh
# Set up permissions and user
RUN useradd -m webui && \
    chown -R webui:webui /app
USER webui


# Start the application
ENTRYPOINT ["/app/run.sh"]