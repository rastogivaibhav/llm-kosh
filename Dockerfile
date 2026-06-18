FROM python:3.11

WORKDIR /app

# Install build dependencies for C++ extensions if needed
# python:3.11 already includes gcc/g++, but let's ensure we have everything
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the project files
COPY . .

# Install the package with all optional dependencies
# Also install pytest for testing
RUN pip install --no-cache-dir -e .[server,watch,ingest]
RUN pip install --no-cache-dir pytest pytest-asyncio pyyaml

# Set the default command to run tests
CMD ["pytest"]
