FROM python:3

WORKDIR /app

RUN mkdir -p /app/src

# Install Google Cloud and required python libraries for running the analysis pipeline
RUN apt-get update && \
    # Install prerequisites 
    apt-get install -y --no-install-recommends \
        apt-transport-https \
        ca-certificates \
        gnupg \
        libgl1 && \
    \
    # Download Google Cloud
    curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
    \
    # Add the Google Cloud SDK repository
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee /etc/apt/sources.list.d/google-cloud-sdk.list && \
    \
    # Update and install the SDK
    apt-get update && \
    apt-get install -y google-cloud-sdk && \
    \
    # Clean up the package list cache and remove unneeded packages
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*


# Install python dependencies
COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

COPY . /app

ENV PYTHONPATH=$PYTHONPATH:/app
