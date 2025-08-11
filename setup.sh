sudo apt update -y
sudo apt upgrade -y

# Need a newer version of Rust for samedec
sudo apt remove rustc
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh


sudo apt install rtl sox cargo espeak python3-pip python3-pil python3-numpy fonts-dejavu gpiod libgpiod-dev
sudo apt install netcat-traditional multimon-ng # optional
cargo install samedec

# Download sameasy
git clone ####
cd sameasy

# Install sameasy
chmod +x *.sh *.service *.path
sudo cp *.service /etc/systemd/system/
sudo cp *.path /etc/systemd/system/
sudo systemctl daemon-reexec
sudo systemctl enable --now same_monitor.service
sudo systemctl enable --now same-eink.path
sudo systemctl start same_monitor.service

# Initialize the database
python3 init_db.py

# Setup E-Ink
sudo raspi-config nonint do_spi 0
cd /tmp/
wget https://github.com/joan2937/lg/archive/master.zip
unzip master.zip
cd lg-master
make
sudo make install
cd /tmp/
wget http://www.airspayce.com/mikem/bcm2835/bcm2835-1.71.tar.gz
tar zxvf bcm2835-1.71.tar.gz
cd bcm2835-1.71/
sudo ./configure && sudo make && sudo make check && sudo make install
cd /tmp/
git clone https://github.com/WiringPi/WiringPi
cd WiringPi
./build
gpio -v
cd ~
git clone https://github.com/waveshare/e-Paper
cd e-Paper/RaspberryPi_JetsonNano/python
pip3 install -r requirements.txt

sudo reboot