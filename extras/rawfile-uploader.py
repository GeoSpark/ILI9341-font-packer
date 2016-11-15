#!/usr/bin/python
#
# Uploads raw audio files to Teensy + Audio board with SPI Flash on board.  To use this program, first
# load the 'CopyFromSerial' example sketch.  When it first runs, it will format the SPI flash chip
# (this may take a long time for larger chips; a 128MB chip that I am using can take almost 10 minutes,
# but smaller 16MB ones should be faster).
#
# While the chip is being formatted, the LED (pin 13) will toggle at 1Hz rate.  When the formatting is
# done, it flashes quickly (10Hz) for one second, then stays on solid.  When nothing has been received
# for 3 seconds, the upload is assumed to be completed, and the light goes off.
#
# You can start this program immediately upon plugging in the Teensy.  It will buffer and wait until
# the Teensy starts to read the serial data from USB.
#
###################
# Modified by John Donovan (http://geospark.co.uk)
# I have simplified the code somewhat by getting rid of the unnecessary stream markers. They are redundant assuming
# an 8.3 filename, and the file size is accurate. This also greatly simplifies the CopyFromSerial sketch.
# The file name is a fixed length of 12 bytes, so pad shorter filenames with NULLs.

import sys
import os
import time
from io import BytesIO
import struct

import serial

if len(sys.argv) <= 2:
    print("Usage: '" + sys.argv[0] + " <port> <files>' where:\n\t<port> is the TTY USB port connected to your Teensy\n"
                                     "\t<files> is a list of files (bash globs work).")
    sys.exit()

# Flash size (in MB).  Change this to match how much space you have on your chip.
FLASH_SIZE = 16

totalFileSize = 0
for i, filename in enumerate(sys.argv):
    if i >= 2:
        totalFileSize = totalFileSize + os.path.getsize(filename)

flashSizeBytes = FLASH_SIZE * 1024 * 1024
if totalFileSize > flashSizeBytes:
    print("Too many files selected.\n\tTotal flash size:\t" + "{:>14,}".format(
        flashSizeBytes) + " bytes\n\tTotal file size:\t" + "{:>14,}".format(totalFileSize) + " bytes")
    sys.exit()

ser = serial.Serial(sys.argv[1])
print("Uploading " + str(len(sys.argv) - 2) + " files...")
for i, filename in enumerate(sys.argv):
    if i >= 2:
        startTime = time.time()
        sys.stdout.write(str(i - 1) + ": ")
        sys.stdout.write(filename)
        sys.stdout.flush()

        f = open(filename, "rb")
        fileLength = os.path.getsize(filename)
        try:
            encoded = BytesIO()
            encoded.write(filename.encode())
            encoded.write(b'\x00' * (12 - len(filename)))
            encoded.write(struct.pack('<I', fileLength))
            encoded.write(f.read())
            s = encoded.getvalue()
            ser.write(s)

        finally:
            f.close()

        endTime = time.time()
        print(" (" + str(round(fileLength / 1024 / (endTime - startTime), 2)) + " KB/s)")

print("All files uploaded")
