#!/bin/bash

# Exit on any error
set -e

# Install Python 3.11.9 if not already installed
if ! command -v python3.11 &> /dev/null; then
    echo "Installing Python 3.11.9..."
    apt-get update && apt-get install -y python3.11 python3.11-dev python3.11-venv
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
    update-alternatives --set python3 /usr/bin/python3.11
fi

# Create and activate virtual environment
python3.11 -m venv /opt/render/venv
source /opt/render/venv/bin/activate

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
python -m pip install --no-cache-dir -r requirements.txt

echo "Build completed successfully!"
