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

byte i2c = 3;
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
  // RPI I2C address starts from 0x3
  for (int address = 3; address < 119; address++ )
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

bool DuinoCoin_loop()
{
  if (bufferReceive.available() > 0 && bufferReceive.indexOf('\n') != -1) {
    
    Serial.print(F("Job: "));
    Serial.print(bufferReceive);
    
    String local_bufferReceive = bufferReceive.readStringUntil('\n');
    while (bufferReceive.available()) bufferReceive.read();
    local_bufferReceive = str_sanitize(local_bufferReceive);
    StreamString received;
    received.print(local_bufferReceive);

    String lastblockhash = received.readStringUntil(',');
    String newblockhash = received.readStringUntil(',');
    unsigned int difficulty = received.readStringUntil('\n').toInt();
    
    
    // Start time measurement
    unsigned long startTime = micros();
    // Call DUCO-S1A hasher
    unsigned int ducos1result = 0;
    if (difficulty < 655) ducos1result = Ducos1a.work(lastblockhash, newblockhash, difficulty);
    // End time measurement
    unsigned long endTime = micros();
    // Calculate elapsed time
    unsigned long elapsedTime = endTime - startTime;
    // Send result back to the program with share time
    while (bufferRequest.available()) bufferRequest.read();
    bufferRequest.print(String(ducos1result) + "," + String(elapsedTime) + "," + String(get_DUCOID()) + "\n");

    Serial.print(F("Done "));
    Serial.print(String(ducos1result) + "," + String(elapsedTime) + "," + String(get_DUCOID()) + "\n");
    
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
