#!/bin/bash
# Setup script for OPCP website

set -e

echo "=== OPCP Website Setup ==="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
echo ""
if [ ! -f ".env" ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo ".env file created. Please edit it with your configuration."
else
    echo ".env file already exists."
fi

# Create necessary directories
echo ""
echo "Creating necessary directories..."
mkdir -p logs
mkdir -p storage/uploads
mkdir -p static
mkdir -p templates

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Setup PostgreSQL database:"
echo "   createdb OPCP_db"
echo "   createuser OPCP_user"
echo "3. Run database migrations:"
echo "   alembic upgrade head"
echo "4. Start the development server:"
echo "   uvicorn app.main:app --reload"
echo ""
echo "To activate the virtual environment in the future:"
echo "   source venv/bin/activate"
