# SAMEasy 🚨

**Emergency Alert Display System for Raspberry Pi**

SAMEasy is a complete emergency alert monitoring system that receives SAME (Specific Area Message Encoding) alerts from weather radios and displays them on an e-ink screen. Perfect for emergency preparedness, weather monitoring, and staying informed about local threats.

![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi-red)
![Python](https://img.shields.io/badge/Python-3.7%2B-blue)

## 🎯 What It Does

SAMEasy automatically:
- **📻 Monitors** weather radio frequencies for emergency alerts
- **🔍 Decodes** SAME messages (tornado warnings, flood alerts, etc.)
- **💾 Stores** alerts in a searchable database with full history
- **🖥️ Displays** current alerts on an e-ink screen with icons
- **📱 Outputs** structured JSON data for integration with other systems

## 🛠️ Hardware Requirements

### Required
- **[Raspberry Pi 4](https://amzn.to/4mdhmHK)** (3B+ works, but slower)
- **[RTL-SDR USB Dongle](https://amzn.to/4lufskJ)** (RTL2832U based, ~$20)
- **[Waveshare 2.7" E-Ink Display](https://amzn.to/3JbP8yg)** (264x176 pixels)
- **[MicroSD Card](https://amzn.to/4oLEIWC)** (16GB+ recommended)
- **[Weather Radio Antenna](https://amzn.to/4oxWX1y)** (or just a wire for testing)
- **[SMA to UHF RF Adapter](https://amzn.to/45wmLTa)** 

### Optional
- **Powered USB Hub** (if using multiple RTL-SDR dongles)
- **Case/Enclosure** (for weather protection)

## 🚀 Quick Start

### 1. Flash Raspberry Pi OS
Flash Raspberry Pi OS Lite to your SD card and enable SSH.

### 2. Clone and Setup
```bash
# On your Raspberry Pi as user 'noaa'
cd ~
git clone git@github.com:ifnull/sameasy.git sameasy
cd sameasy
chmod +x setup.sh
sudo ./setup.sh
```

The setup script will:
- Install all dependencies (Python, Rust, system packages)
- Set up the database and directory structure
- Install systemd services for automatic monitoring
- Configure SPI for the e-ink display
- Install Waveshare e-Paper libraries

### 3. Configure Your Setup
Edit the configuration file:
```bash
nano config.json
```

Key settings to review:
- **Font paths**: Verify fonts exist on your system
- **Icon mappings**: Customize alert type icons
- **Display settings**: Adjust padding and icon size

### 4. Test the System
```bash
# Change to the sameasy directory
cd ~/sameasy

# Test database
python3 scripts/check_database.py

# Test with sample alert
python3 scripts/test_decoder.py

# Test e-ink display (if connected)
python3 src/update_eink.py
```

### 5. Monitor the System
After setup completes, the services are installed and ready. If you chose to start monitoring during setup, you can monitor the system with:

```bash
# Check service status
sudo systemctl status same_monitor.service

# Monitor live logs
journalctl -u same_monitor.service -f
```

If you didn't start the service during setup, start it manually:
```bash
sudo systemctl start same_monitor.service
```

## 📁 Project Structure

```
sameasy/
├── README.md                 # This file
├── setup.sh                  # Automated installation script
├── config.json              # Display and system configuration
│
├── src/                      # Core application code
│   ├── same_decoder.py      # SAME message parser and processor
│   ├── update_eink.py       # E-ink display renderer
│   └── database_migrations.py # Database schema management
│
├── scripts/                  # Utility and management scripts
│   ├── init_db.py           # Database initialization
│   ├── check_database.py    # Database health checker
│   ├── view_alerts.py       # Alert viewing and search tool
│   └── test_decoder.py      # System testing script
│
├── system/                   # System service files
│   ├── same_monitor.service # Main monitoring service
│   ├── same_monitor.sh      # Service startup script
│   ├── same-eink.service    # E-ink update service
│   └── same-eink.path       # File watcher for JSON updates
│
├── data/                     # Reference data files
│   ├── eas_events.csv       # Emergency event codes
│   ├── fips_counties.csv    # County FIPS codes
│   ├── fips_states.csv      # State codes
│   └── originators.csv      # Alert originator codes
│
├── icons/material/           # Alert type icons
│   ├── tornado.png          # Tornado warnings
│   ├── flood.png            # Flood alerts
│   ├── warning.png          # General warnings
│   └── [more icons...]
│
└── runtime/                  # Runtime data (auto-created)
    ├── logs/                # Application logs
    ├── alerts.db            # SQLite alert database
    └── last_message.json    # Current alert for display
```

## 🔧 System Architecture

### Data Flow
```
Weather Radio → RTL-SDR → samedec → same_decoder.py → Database + JSON → E-ink Display
                    ↓
                Audio Processing & SAME Decoding
```

### Components

**1. Radio Reception**
- RTL-SDR receives weather radio audio
- `samedec` (Rust) decodes SAME bursts
- Outputs structured alert data

**2. Message Processing**
- `same_decoder.py` validates and parses alerts
- Resolves codes to human-readable descriptions
- Stores in SQLite database with full history

**3. Display Management**
- Monitors JSON file for new alerts
- Renders formatted display with icons
- Updates e-ink screen via SPI

**4. Database System**
- Automatic schema migrations
- Performance indexes for fast queries
- Full alert history with search capabilities

## 📊 Database Schema

### Alerts Table
```sql
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TEXT NOT NULL,      -- When alert was issued
    originator TEXT NOT NULL,         -- Who issued it (NWS, etc.)
    event TEXT NOT NULL,              -- Human readable event type
    event_code TEXT,                  -- SAME event code (TOR, FFW, etc.)
    fips_codes TEXT NOT NULL,         -- Affected area codes
    regions TEXT NOT NULL,            -- Human readable regions
    duration_minutes INTEGER NOT NULL, -- How long alert is valid
    issued_code TEXT NOT NULL,        -- Raw timestamp code
    source TEXT NOT NULL,             -- Radio station ID
    raw_message TEXT NOT NULL,        -- Original SAME message
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Indexes for Performance
- `idx_alerts_timestamp` - Time-based queries
- `idx_alerts_event_code` - Filter by alert type
- `idx_alerts_originator` - Filter by source
- `idx_alerts_created_at` - Recent alerts

## 🎨 Display Features

### E-ink Display Layout
```
┌─────────────────────────────────────┐
│ Tornado Warning                     │
│ National Weather Service (NWS/ABC)  │
│ ─────────────────────────────────── │
│ Oct 15 2025, 2:30 PM (60 minutes)  │
│ Madison, Jefferson, Hamilton        │
│                                     │
│ 🌪️                Updated: 14:35   │
└─────────────────────────────────────┘
```

### Features
- **Clean Typography**: Uses DejaVu Sans for readability
- **Smart Text Wrapping**: Handles long region names
- **Status Icons**: Visual indicators for alert types
- **Automatic Updates**: Refreshes when new alerts arrive
- **County Name Cleanup**: Removes redundant "County" text

### Icon Mapping
- 🌪️ **Tornado** - TOR, SVR warnings  
- 🌊 **Flood** - FFW, FLW alerts
- ❄️ **Winter** - WSW, BWS warnings
- ⚠️ **General** - Other warnings
- 👁️ **Watch** - TOA, SVA watches
- 🧪 **Test** - RWT, RMT test messages

## 🔍 Alert Types Supported

### Weather Warnings (Immediate Action Required)
- **TOR** - Tornado Warning
- **SVR** - Severe Thunderstorm Warning  
- **FFW** - Flash Flood Warning
- **FLW** - Flood Warning
- **WSW** - Winter Storm Warning

### Weather Watches (Conditions Possible)
- **TOA** - Tornado Watch
- **SVA** - Severe Thunderstorm Watch
- **FFA** - Flash Flood Watch

### Test Messages
- **RWT** - Required Weekly Test
- **RMT** - Required Monthly Test
- **NPT** - National Periodic Test

### Other Emergency Types
- **CAE** - Child Abduction Emergency (AMBER Alert)
- **EAN** - Emergency Action Notification
- **And many more...**

## 📱 Management Commands

### Database Operations
```bash
# Change to sameasy directory
cd ~/sameasy

# Check database status
python3 scripts/check_database.py

# View recent alerts
python3 scripts/view_alerts.py --limit 5

# Search for specific alerts
python3 scripts/view_alerts.py --event "Warning" --since 2025-08-01
python3 scripts/view_alerts.py --event-code "TOR"

# Initialize/migrate database
python3 scripts/init_db.py
```

### System Management
```bash
# Service status
sudo systemctl status same_monitor.service

# View logs
journalctl -u same_monitor.service -f

# Restart services
sudo systemctl restart same_monitor.service
sudo systemctl restart same-eink.path

# Test e-ink display (from ~/sameasy directory)
cd ~/sameasy
python3 src/update_eink.py
```

### Testing and Debugging
```bash
# Change to sameasy directory
cd ~/sameasy

# Test with sample message
python3 scripts/test_decoder.py

# Manual message processing
echo "ZCZC-EAS-TOR-048013+0030-1234567-KLOX/NWS-" | python3 src/same_decoder.py

# Monitor SDR input (if samedec is running)
samedec --help
```

## ⚡ Performance & Reliability

### System Requirements
- **CPU**: ARM Cortex-A72 (Pi 4) or better
- **RAM**: 1GB+ (database and image processing)
- **Storage**: 8GB+ for logs and alert history
- **Network**: Optional (for time sync and updates)

### Reliability Features
- **Automatic Recovery**: Services restart on failure
- **Database Backups**: Created before schema migrations  
- **Error Logging**: Comprehensive logging to files and journal
- **Atomic Operations**: Database transactions prevent corruption
- **Graceful Degradation**: System continues without display if needed

### Performance Optimizations
- **CSV Caching**: Reference data loaded once at startup
- **Database Indexes**: Fast queries on large datasets
- **Efficient Rendering**: Minimal e-ink updates to preserve display
- **Memory Management**: Proper cleanup of resources

## 🛠️ Customization

### Adding New Alert Types
1. Edit `config.json` to add icon mappings:
```json
{
  "icon_mappings": {
    "NEW": "custom_icon.png"
  }
}
```

2. Add icon file to `icons/material/custom_icon.png`

### Customizing Display Layout
Edit `src/update_eink.py`:
- Modify font sizes in config.json
- Adjust padding and spacing
- Change icon size and position
- Add new display elements

### Adding Data Sources
The system is designed to be extensible:
- Add new CSV files to `data/` directory
- Modify `load_all_csv_data()` in `same_decoder.py`
- Update database schema if needed

## 🔐 Security Considerations

### Network Security
- System works offline (no network required for core function)
- No incoming network connections
- Radio reception is passive (receive-only)

### Data Security
- Local SQLite database (no cloud dependencies)
- Alert data stays on device
- Standard file permissions on logs and database

### System Security
- Runs as unprivileged user where possible
- Systemd services with restart limits
- No sudo required for normal operation

## 🐛 Troubleshooting

### Common Issues

**No Alerts Received**
```bash
# Check if RTL-SDR is detected
lsusb | grep RTL

# Check samedec is working
samedec --help
ps aux | grep samedec

# Check service status
sudo systemctl status same_monitor.service
journalctl -u same_monitor.service -n 50
```

**E-ink Display Not Working**
```bash
# Check SPI is enabled
sudo raspi-config nonint get_spi

# Test display connection
python3 -c "from waveshare_epd import epd2in7_V2; epd = epd2in7_V2.EPD(); print('Display OK')"

# Check for errors in display service
journalctl -u same-eink.service -n 20
```

**Database Issues**
```bash
# Change to sameasy directory
cd ~/sameasy

# Check database health
python3 scripts/check_database.py

# Run migrations manually
python3 src/database_migrations.py

# View recent database activity
tail -f runtime/logs/same_decoder.log
```

**Font/Display Rendering Issues**
```bash
# Check font files exist
ls -la /usr/share/fonts/truetype/dejavu/

# Test font loading
python3 -c "from PIL import ImageFont; ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)"

# Verify config.json syntax (from ~/sameasy directory)
cd ~/sameasy
python3 -c "import json; print(json.load(open('config.json')))"
```

### Log Files
- **Application Logs**: `runtime/logs/same_decoder.log`
- **System Logs**: `journalctl -u same_monitor.service`
- **Display Logs**: `journalctl -u same-eink.service`

## 🤝 Contributing

### Development Setup
```bash
# Clone repository
git clone git@github.com:ifnull/sameasy.git sameasy-dev
cd sameasy-dev

# Create development environment
python3 -m venv dev-venv
source dev-venv/bin/activate
pip install -r requirements-dev.txt  # If exists

# Run tests
python3 scripts/test_decoder.py
```

### Code Style
- Follow PEP 8 for Python code
- Use type hints where possible
- Include docstrings for functions
- Add logging for debugging
- Write tests for new features

### Areas for Contribution
- Additional alert type support
- New display layouts or themes
- Integration with other systems
- Performance optimizations
- Documentation improvements
- Hardware support (different displays, etc.)

## 📚 References & Resources

### SAME Protocol
- [SAME Protocol Specification](https://www.nws.noaa.gov/nwr/info/nwrsame.html)
- [Event Codes Reference](https://www.nws.noaa.gov/nwr/info/eventcodes.html)
- [FIPS County Codes](https://www.nist.gov/standardsgov/compliance-faqs/list-fips-codes-counties-and-county-equivalent-entities)

### Hardware Resources
- [RTL-SDR Setup Guide](https://www.rtl-sdr.com/rtl-sdr-quick-start-guide/)
- [Waveshare E-Paper Documentation](https://www.waveshare.com/wiki/2.7inch_e-Paper_HAT)
- [Raspberry Pi SPI Configuration](https://www.raspberrypi.org/documentation/hardware/raspberrypi/spi/)

### Software Dependencies
- [samedec](https://github.com/cbs228/samedec) - SAME message decoder
- [Pillow](https://pillow.readthedocs.io/) - Python image processing
- [SQLite](https://www.sqlite.org/) - Embedded database

## 📜 License

[Specify your license here - MIT, GPL, Apache, etc.]

## 🆘 Support

### Getting Help
- **Issues**: Create GitHub issues for bugs or feature requests
- **Discussions**: Use GitHub discussions for questions
- **Documentation**: Check this README and inline comments

### Emergency Use
This system is designed for **informational purposes only**. Always have multiple sources of emergency information:
- Battery/hand-crank weather radio
- Mobile phone emergency alerts
- Local emergency management notifications
- Television and radio broadcasts

**🚨 This system should complement, not replace, official emergency alerting systems.**

---

**Built with ❤️ for emergency preparedness and community safety**

*Last updated: August 2025*