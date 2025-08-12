#!/bin/bash
set -e

echo "🚀 SAMEASY - Emergency Alert Display System Setup"
echo "=================================================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Warning: This setup is optimized for Raspberry Pi"
    echo "   Some features may not work on other systems"
fi

# Update system
echo "📦 Updating system packages..."
sudo apt update -y
sudo apt upgrade -y

# Remove old Rust if present
echo "🦀 Setting up Rust toolchain..."
sudo apt remove rustc -y 2>/dev/null || true
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source ~/.cargo/env

# Install system dependencies
echo "📚 Installing system dependencies..."
sudo apt install -y \
    python3-pip python3-venv \
    python3-pil python3-numpy \
    fonts-dejavu fonts-dejavu-core \
    rtl-sdr sox cargo \
    espeak \
    gpiod libgpiod-dev \
    sqlite3 \
    git curl wget unzip

# Optional tools for debugging
sudo apt install -y netcat-traditional multimon-ng || echo "Optional packages skipped"

# Install samedec (SAME decoder)
echo "📻 Installing SAME decoder..."
cargo install samedec

# Setup Python virtual environment
echo "🐍 Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip

# Initialize project directories and database
echo "🗄️  Initializing project..."
python3 scripts/init_db.py

# Install systemd services
echo "⚙️  Installing system services..."
chmod +x system/*.sh system/*.service system/*.path
sudo cp system/*.service /etc/systemd/system/
sudo cp system/*.path /etc/systemd/system/
sudo systemctl daemon-reload

# Enable but don't start services yet (user should configure first)
sudo systemctl enable same_monitor.service
sudo systemctl enable same-eink.path

echo "🔧 Setting up hardware (Raspberry Pi specific)..."
if command -v raspi-config >/dev/null 2>&1; then
    # Enable SPI for e-ink display
    sudo raspi-config nonint do_spi 0
    
    echo "📱 Installing e-ink display libraries..."
    
    # Install lg library
    cd /tmp/
    wget -q https://github.com/joan2937/lg/archive/master.zip
    unzip -q master.zip
    cd lg-master
    make -s
    sudo make install -s
    rm ../master.zip
    
    # Install BCM2835 library
    cd /tmp/
    wget -q http://www.airspayce.com/mikem/bcm2835/bcm2835-1.71.tar.gz
    tar zxf bcm2835-1.71.tar.gz >/dev/null
    cd bcm2835-1.71/
    sudo ./configure >/dev/null && sudo make -s && sudo make check -s && sudo make install -s
    rm ../bcm2835-1.71.tar.gz

    # Install WiringPi
    cd /tmp/
    git clone -q https://github.com/WiringPi/WiringPi
    cd WiringPi
    ./build >/dev/null
    
    # Install Waveshare e-Paper library
    cd /tmp/
    git clone -q https://github.com/waveshare/e-Paper
    cp -R e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd $HOME/sameasy/src/
    
    echo "✅ Hardware libraries installed"
else
    echo "⚠️  raspi-config not found - skipping hardware setup"
    echo "   You may need to manually configure SPI and install e-ink libraries"
fi

# Return to project directory
cd "$(dirname "$0")"

echo ""
echo "🎉 SAMEASY Installation Complete!"
echo "=================================="
echo ""
echo "📋 Next Steps:"
echo "   1. Review and edit config.json for your setup"
echo "   2. Test the system with: cd ~/sameasy && python3 scripts/test_decoder.py"
echo "   3. Start services: sudo systemctl start same_monitor.service"
echo "   4. Check logs: journalctl -u same_monitor.service -f"
echo ""
echo "🔧 Management Commands (run from ~/sameasy):"
echo "   • Check database: python3 scripts/check_database.py"
echo "   • View alerts: python3 scripts/view_alerts.py"
echo "   • Test display: python3 src/update_eink.py"
echo ""
echo "📚 Documentation: See README.md for detailed setup guide"
echo ""

# Offer to start services
read -p "🚀 Start SAME monitoring service now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo systemctl start same_monitor.service
    echo "✅ Service started. Monitor with: journalctl -u same_monitor.service -f"
else
    echo "ℹ️  Services installed but not started."
    echo "   Start when ready with: sudo systemctl start same_monitor.service"
fi

echo ""
echo "🔄 Reboot recommended to ensure all hardware changes take effect."
read -p "Reboot now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔄 Rebooting..."
    sudo reboot
fi