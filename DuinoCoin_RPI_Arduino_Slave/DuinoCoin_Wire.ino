/*
  DoinoCoin_Wire.ino
  created 10 05 2021
  by Luiz H. Cassettari
  
  Modified by JK Rolling
*/

#include <Wire.h>
#include <DuinoCoin.h>        // https://github.com/ricaun/arduino-DuinoCoin
#include <ArduinoUniqueID.h>  // https://github.com/ricaun/ArduinoUniqueID
#include <StreamString.h>     // https://github.com/ricaun/StreamJoin

// user to manually change the device number
// device number is being used to introduced fixed delay for each i2cSlave
// cloned arduino is pretty bad in generating random number
// increment this number per upload
// comment out to use as common code across all arduino. **USE AT YOUR OWN RISK**
#define DEV_INDEX 0

// change this start address to suit your SBC usable I2C address
#define I2CS_START_ADDRESS 3

/* typical i2cdetect printout. showing example of 10 I2CS
$ i2cdetect -y 1
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          03 04 05 06 07 08 09 0a 0b 0c -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
*/

byte i2c = I2CS_START_ADDRESS;
StreamString bufferReceive;
StreamString bufferRequest;

void DuinoCoin_setup()
{
  UniqueID8dump(Serial);
  
  pinMode(A5, INPUT_PULLUP);
  pinMode(A4, INPUT_PULLUP);
  
  #ifndef DEV_INDEX
    unsigned long time = getTrueRotateRandomByte() * 1000 + getTrueRotateRandomByte();
    delayMicroseconds(time);
  #else
    //each i2cSlave should take less than 20ms to scan all addresses
    delay(20*DEV_INDEX);
  #endif
  
  Wire.begin();
  // RPI I2C address starts from 0x3 to 0x77
  for (int address = I2CS_START_ADDRESS; address < 119; address++ )
  {
    Wire.beginTransmission(address);
    int error = Wire.endTransmission();
    if (error != 0)
    {
      i2c = address;
      break;
    }
  }
  Wire.end();

  // Wire begin
  Wire.begin(i2c);
  Wire.onReceive(receiveEvent);
  Wire.onRequest(requestEvent);

  Serial.print(F("Wire Address: "));
  Serial.println(i2c);
}


void receiveEvent(int howMany) {
  if (howMany == 0)
  {
    return;
  }
  while (Wire.available()) {
    char c = Wire.read();
    bufferReceive.write(c);
  }
}

void requestEvent() {
  char c = '\n';
  if (bufferRequest.length() > 0)
  {
    c = bufferRequest.read();
  }
  Wire.write(c);
}

void abort_loop()
{
    Serial.println("Detected invalid char. abort");
    while (bufferReceive.available()) bufferReceive.read();
    bufferRequest.print("#");
}

bool DuinoCoin_loop()
{
  if (bufferReceive.available() > 0 && bufferReceive.indexOf('\n') != -1) {
    
    Serial.print(F("Job: "));
    Serial.print(bufferReceive);
    
    String lastblockhash = bufferReceive.readStringUntil(',');
    if (check(lastblockhash))
    {
        abort_loop();
        return false;
    }
    String newblockhash = bufferReceive.readStringUntil(',');
    if (check(newblockhash))
    {
        abort_loop();
        return false;
    }
    unsigned int difficulty = bufferReceive.readStringUntil(',').toInt();
    if (difficulty == 0)
    {
        abort_loop();
        return false;
    }
    uint8_t crc8hash= bufferReceive.readStringUntil('\n').toInt();
    String data = lastblockhash + "," + newblockhash + "," + String(difficulty) + ",";
    if (crc8hash != str_crc8(data))
    {
        abort_loop();
        return false;
    }
        
    
    // Start time measurement
    unsigned long startTime = micros();
    // Call DUCO-S1A hasher
    unsigned int ducos1result = 0;
    if (difficulty < 655) ducos1result = Ducos1a.work(lastblockhash, newblockhash, difficulty);
    // End time measurement
    unsigned long endTime = micros();
    // Calculate elapsed time
    unsigned long elapsedTime = endTime - startTime;
    if (ducos1result == 1) elapsedTime = 5128;
    // Send result back to the program with share time
    while (bufferRequest.available()) bufferRequest.read();

    String result = String(ducos1result) + "," + String(elapsedTime) + "," + String(get_DUCOID()) + ",";
    result = result + String(str_crc8(result));
    bufferRequest.print(result + "\n");

    Serial.print(F("Done "));
    Serial.println(result + "\n");
    
    return true;
  }
  return false;
}

String DuinoCoin_response()
{
  return bufferRequest;
}

// Grab Arduino chip DUCOID
String get_DUCOID() {
  String ID = "DUCOID";
  char buff[4];
  for (size_t i = 0; i < 8; i++)
  {
    sprintf(buff, "%02X", (uint8_t) UniqueID8[i]);
    ID += buff;
  }
  return ID;
}
