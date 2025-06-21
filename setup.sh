#!/bin/bash

# Exit on any error
set -e

# Update package lists
apt-get update

# Install required packages for Python installation
apt-get install -y --no-install-recommends \
    build-essential \
    zlib1g-dev \
    libncurses5-dev \
    libgdbm-dev \
    libnss3-dev \
    libssl-dev \
    libreadline-dev \
    libffi-dev \
    wget \
    curl \
    llvm \
    libbz2-dev \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Download and install Python 3.11.9
PYTHON_VERSION=3.11.9
wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz
tar -xzf Python-${PYTHON_VERSION}.tgz
cd Python-${PYTHON_VERSION}
./configure --enable-optimizations --enable-loadable-sqlite-extensions
make -j $(nproc)
make altinstall
cd ..
rm -rf Python-${PYTHON_VERSION} Python-${PYTHON_VERSION}.tgz

# Update pip and install virtualenv
python3.11 -m pip install --upgrade pip
python3.11 -m pip install virtualenv

# Create and activate virtual environment
python3.11 -m virtualenv -p python3.11 venv
source venv/bin/activate

# Install project dependencies
pip install --no-cache-dir -r requirements.txt
