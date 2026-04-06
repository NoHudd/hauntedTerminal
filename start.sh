#!/bin/bash

# Colors for cool output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ASCII Art Banner
clear
echo -e "${PURPLE}${BOLD}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██╗  ██╗███████╗███████╗███████╗                          ║
║   ██║  ██║██╔════╝██╔════╝██╔════╝                          ║
║   ███████║█████╗  ███████╗█████╗                            ║
║   ██╔══██║██╔══╝  ╚════██║██╔══╝                            ║
║   ██║  ██║██║     ███████║███████╗                          ║
║   ╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝                          ║
║                                                               ║
║        Haunted Filesystem Experience                          ║
║        Learn command-line skills through adventure!           ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo -e "${CYAN}${BOLD}[HFSE Launcher]${NC} Initializing..."
echo ""

# Check Python installation
echo -e "${YELLOW}→${NC} Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗${NC} Python 3 is not installed!"
    echo -e "${YELLOW}Please install Python 3.7 or higher from https://www.python.org/${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✓${NC} Python ${PYTHON_VERSION} found"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}→${NC} First time setup detected!"
    echo -e "${CYAN}Creating virtual environment...${NC}"
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗${NC} Failed to create virtual environment"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${GREEN}✓${NC} Virtual environment found"
fi

# Activate virtual environment
echo -e "${YELLOW}→${NC} Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed (pip show avoids spawning a Python process)
echo -e "${YELLOW}→${NC} Checking dependencies..."
if ! pip show textual > /dev/null 2>&1; then
    echo -e "${CYAN}Installing required packages...${NC}"
    echo -e "${BLUE}This may take a moment...${NC}"
    pip install -q -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗${NC} Failed to install dependencies"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} All dependencies installed successfully"
else
    echo -e "${GREEN}✓${NC} All dependencies satisfied"
fi

# Create necessary directories
mkdir -p saves
mkdir -p config

# Check for config file
if [ ! -f "config/settings.py" ]; then
    echo -e "${YELLOW}→${NC} Setting up configuration..."
    if [ -f "config/settings.example.py" ]; then
        cp config/settings.example.py config/settings.py
        echo -e "${GREEN}✓${NC} Configuration file created"
    fi
fi

# Launch the game
echo ""
echo -e "${PURPLE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}        🎮 Launching Haunted Filesystem Experience! 🎮${NC}"
echo -e "${PURPLE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo ""
python main.py

# Deactivate virtual environment on exit
deactivate
