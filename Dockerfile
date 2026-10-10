FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    postgresql-client \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Install Amazon Kiro CLI for Oracle AI
RUN curl -fsSL https://cli.kiro.dev/install | bash && \
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# Install SHAI OVH
RUN curl -fsSL https://raw.githubusercontent.com/ovh/shai/main/install.sh | sh

# Ensure Kiro CLI is in PATH for all users
ENV PATH="/root/.local/bin:${PATH}"

# Note: Kiro CLI authentication should be done manually or via device flow
# Run: docker exec ai-shai-web-interface-app-1-6136 kiro-cli login --use-device-flow
# Or configure OPENAI_API_KEY or SHAI_API_KEY as alternative providers

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p storage/uploads ssl

# Expose port
EXPOSE 8000

# Run database migrations and start application
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
