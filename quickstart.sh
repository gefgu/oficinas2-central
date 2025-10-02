#!/bin/bash

# Oficinas2 Central - Quick Start Setup Script
# This script sets up the development environment for the trajectory analysis system

set -e  # Exit on any error

echo "🚀 Oficinas2 Central - Quick Start Setup"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Python version
echo -e "${BLUE}📋 Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed. Please install Python 3.8 or higher.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✓ Found Python $PYTHON_VERSION${NC}"
echo ""

# Create virtual environment
echo -e "${BLUE}🔧 Creating virtual environment...${NC}"
if [ -d "fastapi_env" ]; then
    echo -e "${YELLOW}⚠ Virtual environment 'fastapi_env' already exists.${NC}"
    read -p "Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing virtual environment..."
        rm -rf fastapi_env
        python3 -m venv fastapi_env
        echo -e "${GREEN}✓ Virtual environment recreated${NC}"
    else
        echo -e "${YELLOW}Using existing virtual environment${NC}"
    fi
else
    python3 -m venv fastapi_env
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi
echo ""

# Activate virtual environment
echo -e "${BLUE}🔄 Activating virtual environment...${NC}"
source fastapi_env/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Upgrade pip
echo -e "${BLUE}⬆️  Upgrading pip...${NC}"
pip install --upgrade pip > /dev/null 2>&1
echo -e "${GREEN}✓ pip upgraded${NC}"
echo ""

# Install dependencies
echo -e "${BLUE}📦 Installing dependencies from requirements.txt...${NC}"
echo "This may take a few minutes..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All dependencies installed successfully${NC}"
else
    echo -e "${RED}❌ Failed to install dependencies${NC}"
    exit 1
fi
echo ""

# Check for data files
echo -e "${BLUE}📂 Checking for required data files...${NC}"
MISSING_FILES=0

if [ ! -f "dados/Curitiba_resolution_10.geojson" ]; then
    echo -e "${YELLOW}⚠ Missing: dados/Curitiba_resolution_10.geojson${NC}"
    MISSING_FILES=1
fi

if [ ! -f "dados/bairros_curitiba.zip" ]; then
    echo -e "${YELLOW}⚠ Missing: dados/bairros_curitiba.zip${NC}"
    MISSING_FILES=1
fi

if [ $MISSING_FILES -eq 0 ]; then
    echo -e "${GREEN}✓ All required data files found${NC}"
else
    echo -e "${YELLOW}⚠ Some data files are missing. Please ensure you have:${NC}"
    echo "  - dados/Curitiba_resolution_10.geojson"
    echo "  - dados/bairros_curitiba.zip"
fi
echo ""

# Check for model files
echo -e "${BLUE}🤖 Checking for trained model files...${NC}"
MISSING_MODELS=0

if [ ! -f "modelos/lgb_purpose_model.pkl" ]; then
    echo -e "${YELLOW}⚠ Missing: modelos/lgb_purpose_model.pkl${NC}"
    MISSING_MODELS=1
fi

if [ ! -f "modelos/lgb_purpose_encoders.pkl" ]; then
    echo -e "${YELLOW}⚠ Missing: modelos/lgb_purpose_encoders.pkl${NC}"
    MISSING_MODELS=1
fi

if [ ! -f "server/random_forest_model.pkl" ]; then
    echo -e "${YELLOW}⚠ Missing: server/random_forest_model.pkl${NC}"
    MISSING_MODELS=1
fi

if [ $MISSING_MODELS -eq 0 ]; then
    echo -e "${GREEN}✓ All required model files found${NC}"
else
    echo -e "${YELLOW}⚠ Some model files are missing. You'll need to train models using:${NC}"
    echo "  - notebooks/modelo_proposito_foursquare.ipynb"
    echo "  - notebooks/modelo_de_transporte.ipynb"
fi
echo ""

# Initialize database
echo -e "${BLUE}🗄️  Initializing database...${NC}"
cd server
python3 db_commands.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database tables created${NC}"
else
    echo -e "${RED}❌ Failed to initialize database${NC}"
    cd ..
    exit 1
fi
cd ..
echo ""

# Create .env file if it doesn't exist
echo -e "${BLUE}⚙️  Configuring environment...${NC}"
if [ ! -f "server/.env" ]; then
    cat > server/.env << EOL
# Database Configuration
# Set to 'true' for production database (dados.db)
# Set to 'false' for test database (dados_test.db)
PRODUCTION_MODE=false
EOL
    echo -e "${GREEN}✓ Created server/.env file${NC}"
else
    echo -e "${YELLOW}⚠ server/.env already exists${NC}"
fi
echo ""

# Create startup script
echo -e "${BLUE}📝 Creating startup script...${NC}"
cat > start_server.sh << 'EOL'
#!/bin/bash
# Start the Oficinas2 Central server

# Activate virtual environment
source fastapi_env/bin/activate

# Set to development mode (use test database)
export PRODUCTION_MODE=false

# Start server
cd server
echo "🚀 Starting Oficinas2 Central server..."
echo "📍 Server will be available at: http://localhost:8000"
echo "📚 API documentation at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
# Use uvicorn with --reload for development (auto-restarts on code changes)
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
EOL

chmod +x start_server.sh
echo -e "${GREEN}✓ Created start_server.sh${NC}"
echo ""

# Summary
echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo ""
echo "1. Start the server:"
echo -e "   ${YELLOW}./start_server.sh${NC}"
echo ""
echo "2. Or manually (recommended - includes auto-reload):"
echo -e "   ${YELLOW}source fastapi_env/bin/activate${NC}"
echo -e "   ${YELLOW}cd server${NC}"
echo -e "   ${YELLOW}python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000${NC}"
echo ""
echo "3. Run tests:"
echo -e "   ${YELLOW}source fastapi_env/bin/activate${NC}"
echo -e "   ${YELLOW}pytest server/test_main.py -v${NC}"
echo ""
echo "4. Access API documentation:"
echo "   http://localhost:8000/docs"
echo ""

if [ $MISSING_FILES -eq 1 ] || [ $MISSING_MODELS -eq 1 ]; then
    echo -e "${YELLOW}⚠️  Warning: Some required files are missing.${NC}"
    echo "   Please check the messages above for details."
    echo ""
fi

echo -e "${BLUE}Happy coding! 🎉${NC}"
