#!/bin/bash
rtl_fm -f 162.4M -M fm -s 176400 -r 22050 -E dc -p -35 -g 29 -E deemp -F 9 | \
tee >(aplay -r 22050 -f S16_LE -c 1 -D plughw:0,0) | \
/home/noaa/.cargo/bin/samedec -r 22050 | \
/usr/bin/python3 /home/noaa/sameasy/same_decoder.py
