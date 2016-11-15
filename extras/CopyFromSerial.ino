/*
 * This is free and unencumbered software released into the public domain.
 *
 * Anyone is free to copy, modify, publish, use, compile, sell, or
 * distribute this software, either in source code form or as a compiled
 * binary, for any purpose, commercial or non-commercial, and by any
 * means.
 *
 * In jurisdictions that recognize copyright laws, the author or authors
 * of this software dedicate any and all copyright interest in the
 * software to the public domain. We make this dedication for the benefit
 * of the public at large and to the detriment of our heirs and
 * successors. We intend this dedication to be an overt act of
 * relinquishment in perpetuity of all present and future rights to this
 * software under copyright law.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 * IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
 * OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
 * ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
 * OTHER DEALINGS IN THE SOFTWARE.
 *
 * For more information, please refer to <http://unlicense.org>
 * -------------------------------------------------------------------------
 *
 * This is example code to 1) format an SPI Flash chip, and 2) copy raw
 * audio files (mono channel, 16 bit signed, 44100Hz) to it using the
 * SerialFlash library.  The audio can then be played back using the
 * AudioPlaySerialflashRaw object in the Teensy Audio library.
 *
 * To convert a .wav file to the proper .RAW format, use sox:
 * sox input.wav -r 44100 -b 16 --norm -e signed-integer -t raw OUTPUT.RAW remix 1,2
 *
 * Note that the OUTPUT.RAW filename must be all caps and contain only the following
 * characters: A-Z, 0-9, comma, period, colon, dash, underscore.  (The SerialFlash
 * library converts filenames to caps, so to avoid confusion we just enforce it here).
 *
 * It is a little difficult to see what is happening; aswe are using the Serial port
 * to upload files, we can't just throw out debug information.  Instead, we use the LED
 * (pin 13) to convey state.
 *
 * While the chip is being formatted, the LED (pin 13) will toggle at 1Hz rate.  When
 * the formatting is done, it flashes quickly (10Hz) for one second, then stays on
 * solid.  When nothing has been received for 3 seconds, the upload is assumed to be
 * completed, and the light goes off.
 *
 * Use the 'rawfile-uploader.py' python script (included in the extras folder) to upload
 * the files.  You can start the script as soon as the Teensy is turned on, and the
 * USB serial upload will just buffer and wait until the flash is formatted.
 *
 * This code was written by Wyatt Olson <wyatt@digitalcave.ca> (originally as part
 * of Drum Master http://drummaster.digitalcave.ca and later modified into a
 * standalone sample).
 *
 * Enjoy!
 */

/* Modified by John Donovan (http://geospark.co.uk)
 * I have simplified the code somewhat by getting rid of the unnecessary stream markers. They are redundant assuming
 * an 8.3 filename, and the file size is accurate.
 * Formatting the flash chip is optional now, depending on the setting of ERASE_PIN. Assert low to format, high not to.
 * The file name is a fixed length of 12 bytes, so pad shorter filenames with NULLs.
 * File name restrictions have been lifted, so use at your peril if you decide to feed it unusual characters.
 * Only one file can be uploaded at a time now, this is less of an issue now formatting is optional.
 * Errors are indicated by flashing the LED a number of times.
 * TODO: Reimplement multiple files.
 */

#include <SerialFlash.h>
#include <SPI.h>

#define FLASH_BUFFER_SIZE 4096

//Max filename length (8.3 plus a null char terminator)
#define FILENAME_STRING_SIZE 13

#define MOSI 11
#define MISO 12
#define SCK 14
#define CSPIN 15
#define ERASE_PIN 3

byte error = 0;

void setup() {
  Serial.begin(9600);  //Teensy serial is always at full USB speed and buffered... the baud rate here is required but ignored

  Serial.setTimeout(3000);
  pinMode(13, OUTPUT);
  pinMode(ERASE_PIN, INPUT);

  //Set up SPI
  SPI.setMOSI(MOSI);
  SPI.setMISO(MISO);
  SPI.setSCK(SCK);
  SerialFlash.begin(CSPIN);

  //We start by formatting the flash...
  if (digitalRead(ERASE_PIN) == LOW) {
    uint8_t id[5];
    SerialFlash.readID(id);
    SerialFlash.eraseAll();
    //Flash LED at 1Hz while formatting
    while (!SerialFlash.ready()) {
      delay(500);
      digitalWrite(13, HIGH);
      delay(500);
      digitalWrite(13, LOW);
    }

    //Quickly flash LED a few times when completed, then leave the light on solid
    for (uint8_t i = 0; i < 10; i++) {
      delay(100);
      digitalWrite(13, HIGH);
      delay(100);
      digitalWrite(13, LOW);
    }
  }

  digitalWrite(13, HIGH);

  //We are now going to wait for the upload program
  while(!Serial.available());

  SerialFlashFile flashFile;

  uint32_t fileSize = 0;
  char filename[FILENAME_STRING_SIZE];
  memset(filename, 0, FILENAME_STRING_SIZE);

  char flashBuffer[FLASH_BUFFER_SIZE];

  if (Serial.readBytes(filename, FILENAME_STRING_SIZE - 1) == 0) {
    error = 1;
    return;
  }

  if (Serial.readBytes(reinterpret_cast<char*>(&fileSize), sizeof(fileSize)) == 0) {
    error = 2;
    return;
  }

  if (SerialFlash.create(filename, fileSize)) {
    flashFile = SerialFlash.open(filename);

    if (!flashFile) {
      error = 3;
      return;
    }
  } else {
    error = 4;
    return;
  }

  while (fileSize > FLASH_BUFFER_SIZE) {
    if (Serial.readBytes(flashBuffer, FLASH_BUFFER_SIZE) == 0) {
      error = 5;
      return;
    }

    flashFile.write(flashBuffer, FLASH_BUFFER_SIZE);
    fileSize -= FLASH_BUFFER_SIZE;
  }

  if (fileSize == 0) {
    flashFile.close();
    return;
  }

  if (Serial.readBytes(flashBuffer, fileSize) == 0) {
    error = 6;
    return;
  }

  flashFile.write(flashBuffer, fileSize);
  flashFile.close();
}

void loop() {
  digitalWrite(13, LOW);
  delay(1000);

  while (error > 0) {
    digitalWrite(13, HIGH);
    delay(500);
    digitalWrite(13, LOW);
    delay(500);
    --error;
  }
}
