#!/bin/bash
#
# Live Audio Translator - Installation Script
# For macOS - Uses uv for fast, modern Python package management
#

set -e

echo "============================================"
echo "  Live Audio Translator - Installation"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check for Homebrew (needed for portaudio)
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}Homebrew is not installed.${NC}"
    echo "Homebrew is required to install audio dependencies."
    echo ""
    echo "Install Homebrew with:"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo ""
    exit 1
fi

# Install portaudio (required for pyaudio)
echo "Checking for portaudio..."
if ! brew list portaudio &> /dev/null; then
    echo "Installing portaudio (required for microphone access)..."
    brew install portaudio
else
    echo -e "${GREEN}✓ portaudio is installed${NC}"
fi

# Check for uv
echo ""
echo "Checking for uv..."
if ! command -v uv &> /dev/null; then
    echo "Installing uv (fast Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Source the shell config to get uv in path
    if [ -f "$HOME/.cargo/env" ]; then
        source "$HOME/.cargo/env"
    fi

    # Verify installation
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}Failed to install uv. Please install manually:${NC}"
        echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
fi
echo -e "${GREEN}✓ uv is installed${NC}"

# Create virtual environment and install dependencies
echo ""
echo "Setting up Python environment..."
uv venv --python 3.11

echo ""
echo "Installing dependencies (this may take a few minutes)..."
uv pip install -e .

# Install pip (required by argostranslate at runtime)
uv pip install pip

echo ""
echo "============================================"
echo "  Downloading AI Models"
echo "============================================"
echo ""
echo "The application will download the following on first run:"
echo "  - Whisper 'small' model (~465 MB)"
echo "  - Argos Translate EN↔FR packages (~100 MB)"
echo ""
echo "This is a one-time download and may take a few minutes."
echo ""

# Create the run script
cat > "$SCRIPT_DIR/run.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
source .venv/bin/activate
python -m src.main
EOF
chmod +x "$SCRIPT_DIR/run.sh"

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "To run the application:"
echo ""
echo "  cd $SCRIPT_DIR"
echo "  ./run.sh"
echo ""
echo "Or double-click run.sh in Finder."
echo ""
