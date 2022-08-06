/*
  DoinoCoin_ATTiny_Slave.ino
  adapted from Luiz H. Cassettari
  by JK Rolling
*/

#pragma GCC optimize ("-O2")
#include <ArduinoUniqueID.h>  // https://github.com/ricaun/ArduinoUniqueID
#include <EEPROM.h>
#include <Wire.h>
#include "sha1.h"

/****************** USER MODIFICATION START ****************/
#define I2CS_FIND_ADDR              false
#define ADDRESS_I2C                 8             // manual I2C address assignment
#define CRC8_EN                     true
#define WDT_EN                      true
/****************** USER MODIFICATION END ******************/
/*---------------------------------------------------------*/
/****************** FINE TUNING START **********************/
#define WORKER_NAME                 "attiny85"
#define SENSOR_EN                   false
#define WIRE_MAX                    32
#define WIRE_CLOCK                  100000
/****************** FINE TUNING END ************************/
//#define EEPROM_ADDRESS              0
#if defined(ARDUINO_AVR_UNO) | defined(ARDUINO_AVR_PRO)
#define SERIAL_LOGGER Serial
#define LED LED_BUILTIN
#endif
// user assign led pin if needed. consumes 214 bytes
//#define LED 3

// ATtiny85 - http://drazzy.com/package_drazzy.com_index.json
// SCL - PB2 - 2
// SDA - PB0 - 0

#ifdef SERIAL_LOGGER
#define SerialBegin()              SERIAL_LOGGER.begin(115200);
#define SerialPrint(x)             SERIAL_LOGGER.print(x);
#define SerialPrintln(x)           SERIAL_LOGGER.println(x);
#else
#define SerialBegin()
#define SerialPrint(x)
#define SerialPrintln(x)
#endif

#ifdef LED
#define LedBegin()                DDRB |= (1 << LED);
#define LedHigh()                 PORTB |= (1 << LED);
#define LedLow()                  PORTB &= ~(1 << LED);
#define LedBlink()                LedHigh(); delay(100); LedLow(); delay(100);
#else
#define LedBegin()
#define LedHigh()
#define LedLow()
#define LedBlink()
#endif

#define BUFFER_MAX 88
#define HASH_BUFFER_SIZE 20
#define CHAR_END '\n'
#define CHAR_DOT ','

static const char DUCOID[] PROGMEM = "DUCOID";
static const char ZEROS[] PROGMEM = "000";
static const char WK_NAME[] PROGMEM = WORKER_NAME;
static const char UNKN[] PROGMEM = "unkn";
static const char ONE[] PROGMEM = "1";
static const char ZERO[] PROGMEM = "0";

static byte address;
static char buffer[BUFFER_MAX];
static uint8_t buffer_position;
static uint8_t buffer_length;
static bool working;
static bool jobdone;


void(* resetFunc) (void) = 0;//declare reset function at address 0

// --------------------------------------------------------------------- //
// setup
// --------------------------------------------------------------------- //

void setup() {
  SerialBegin();
  if (WDT_EN) {
    wdt_disable();
    wdt_enable(WDTO_8S);
  }
  initialize_i2c();
  LedBegin();
  LedBlink();
  LedBlink();
  LedBlink();
}

// --------------------------------------------------------------------- //
// loop
// --------------------------------------------------------------------- //

void loop() {
  do_work();
  millis(); // ????? For some reason need this to work the i2c
#ifdef SERIAL_LOGGER
  if (SERIAL_LOGGER.available())
  {
#ifdef EEPROM_ADDRESS
    EEPROM.write(EEPROM_ADDRESS, SERIAL_LOGGER.parseInt());
#endif
    resetFunc();
  }
#endif
}

// --------------------------------------------------------------------- //
// run
// --------------------------------------------------------------------- //
#if WDT_EN
boolean runEvery(unsigned long interval)
{
  static unsigned long previousMillis = 0;
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval)
  {
    previousMillis = currentMillis;
    return true;
  }
  return false;
}
#endif
// --------------------------------------------------------------------- //
// work
// --------------------------------------------------------------------- //

void do_work()
{
  if (working)
  {
    LedHigh();
    SerialPrintln(buffer);

    if (buffer[0] == '&')
    {
      resetFunc();
    }

    if (buffer[0] == 'g') {
      // i2c_cmd
      //pos 0123[4]5678
      //    get,[c]rc8$
      //    get,[b]aton$
      //    get,[s]inglecore$
      //    get,[f]req$
      char f = buffer[4];
      switch (tolower(f)) {
        case 't': // temperature
          if (SENSOR_EN) strcpy_P(buffer, ONE);
          else strcpy_P(buffer, ZERO);
          SerialPrint("SENSOR_EN: ");
          break;
        case 'f': // i2c clock frequency
          char w_clk[10];
          ltoa(WIRE_CLOCK, w_clk, 10);
          strcpy(buffer, w_clk);
          SerialPrint("WIRE_CLOCK: ");
          break;
        case 'c': // crc8 status
          if (CRC8_EN) strcpy_P(buffer, ONE);
          else strcpy_P(buffer, ZERO);
          SerialPrint("CRC8_EN: ");
          break;
        case 'n': // worker name
          strcpy_P(buffer, WK_NAME);
          SerialPrint("WORKER: ");
          break;
        default:
          strcpy_P(buffer, UNKN);
          SerialPrint("command: ");
          SerialPrintln(f);
          SerialPrint("response: ");
      }
      SerialPrintln(buffer);
      buffer_position = 0;
      buffer_length = strlen(buffer);
      working = false;
      jobdone = true;
      if (WDT_EN) wdt_reset();
      return;
    }

    #if I2CS_FIND_ADDR
    if (buffer[0] == '@')
    {
      address = find_i2c();
      memset(buffer, 0, sizeof(buffer));
      buffer_position = 0;
      buffer_length = 0;
      working = false;
      jobdone = false;
      return;
    }
    #endif

    do_job();
  }
  LedLow();
}

void do_job()
{
  unsigned long startTime = millis();
  int job = work();
  unsigned long endTime = millis();
  unsigned int elapsedTime = endTime - startTime;
  if (job<5) elapsedTime = job*(1<<2);
  
  memset(buffer, 0, sizeof(buffer));
  char cstr[16];

  // Job
  if (job == 0)
    strcpy(cstr,"#"); // re-request job
  else
    itoa(job, cstr, 10);
  strcpy(buffer, cstr);
  buffer[strlen(buffer)] = CHAR_DOT;

  // Time
  itoa(elapsedTime, cstr, 10);
  strcpy(buffer + strlen(buffer), cstr);
  strcpy_P(buffer + strlen(buffer), ZEROS);
  buffer[strlen(buffer)] = CHAR_DOT;

  // DUCOID
  strcpy_P(buffer + strlen(buffer), DUCOID);
  for (size_t i = 0; i < 8; i++)
  {
    itoa(UniqueID8[i], cstr, 16);
    if (UniqueID8[i] < 16) strcpy(buffer + strlen(buffer), "0");
    strcpy(buffer + strlen(buffer), cstr);
  }

  #if CRC8_EN
  char gen_crc8[3];
  buffer[strlen(buffer)] = CHAR_DOT;

  // CRC8
  itoa(crc8((uint8_t *)buffer, strlen(buffer)), gen_crc8, 10);
  strcpy(buffer + strlen(buffer), gen_crc8);
  #endif

  SerialPrintln(buffer);

  buffer_position = 0;
  buffer_length = strlen(buffer);
  working = false;
  jobdone = true;
  
  if (WDT_EN) wdt_reset();
}

int work()
{
  char delimiters[] = ",";
  char *lastHash = strtok(buffer, delimiters);
  char *newHash = strtok(NULL, delimiters);
  char *diff = strtok(NULL, delimiters);

  #if CRC8_EN
  char *received_crc8 = strtok(NULL, delimiters);
  // do crc8 checks here
  uint8_t job_length = 3; // 3 commas
  job_length += strlen(lastHash) + strlen(newHash) + strlen(diff);
  char buffer_temp[job_length+1];
  strcpy(buffer_temp, lastHash);
  strcat(buffer_temp, delimiters);
  strcat(buffer_temp, newHash);
  strcat(buffer_temp, delimiters);
  strcat(buffer_temp, diff);
  strcat(buffer_temp, delimiters);
  
  if (atoi(received_crc8) != crc8((uint8_t *)buffer_temp,job_length)) {
    // data corrupted
    SerialPrintln("CRC8 mismatched. Abort..");
    return 0;
  }
  #endif
  
  buffer_length = 0;
  buffer_position = 0;
  return work(lastHash, newHash, atoi(diff));
}

//#define HTOI(c) ((c<='9')?(c-'0'):((c<='F')?(c-'A'+10):((c<='f')?(c-'a'+10):(0))))
#define HTOI(c) ((c<='9')?(c-'0'):((c<='f')?(c-'a'+10):(0)))
#define TWO_HTOI(h, l) ((HTOI(h) << 4) + HTOI(l))
//byte HTOI(char c) {return ((c<='9')?(c-'0'):((c<='f')?(c-'a'+10):(0)));}
//byte TWO_HTOI(char h, char l) {return ((HTOI(h) << 4) + HTOI(l));}

void HEX_TO_BYTE(char * address, char * hex, int len)
{
  for (int i = 0; i < len; i++) address[i] = TWO_HTOI(hex[2 * i], hex[2 * i + 1]);
}

// DUCO-S1A hasher
uint32_t work(char * lastblockhash, char * newblockhash, int difficulty)
{
  if (difficulty > 655) return 0;
  HEX_TO_BYTE(newblockhash, newblockhash, HASH_BUFFER_SIZE);
  for (int ducos1res = 0; ducos1res < difficulty * 100 + 1; ducos1res++)
  {
    Sha1.init();
    Sha1.print(lastblockhash);
    Sha1.print(ducos1res);
    if (memcmp(Sha1.result(), newblockhash, HASH_BUFFER_SIZE) == 0)
    {
      return ducos1res;
    }
    if (WDT_EN) {
      if (runEvery(2000)) wdt_reset();
    }
  }
  return 0;
}

// --------------------------------------------------------------------- //
// i2c
// --------------------------------------------------------------------- //

void initialize_i2c(void) {
  address = ADDRESS_I2C;

#ifdef EEPROM_ADDRESS
  address = EEPROM.read(EEPROM_ADDRESS);
  if (address == 0 || address > 127) {
    address = ADDRESS_I2C;
    EEPROM.write(EEPROM_ADDRESS, address);
  }
#endif

  SerialPrint("Wire begin ");
  SerialPrintln(address);
  Wire.begin(address);
  Wire.onReceive(onReceiveJob);
  Wire.onRequest(onRequestResult);
}

void onReceiveJob(uint8_t howMany) {    
  if (howMany == 0) return;
  if (working) return;
  if (jobdone) return;
  
  char c = Wire.read();
  buffer[buffer_length++] = c;
  if (buffer_length == BUFFER_MAX) buffer_length--;
  if (c == CHAR_END || c == '$') {
    working = true;
  }
  while (Wire.available()) {
    Wire.read();
  }
}

void onRequestResult() {
  char c = CHAR_END;
  if (jobdone) {
    c = buffer[buffer_position++];
    if ( buffer_position == buffer_length) {
      jobdone = false;
      buffer_position = 0;
      buffer_length = 0;
      memset(buffer, 0, sizeof(buffer));
    }
  }
  Wire.write(c);
}

// --------------------------------------------------------------------- //
// find_i2c
// --------------------------------------------------------------------- //

#if I2CS_FIND_ADDR

byte find_i2c()
{
  unsigned long time = (unsigned long) getTrueRotateRandomByte() * 1000 + (unsigned long) getTrueRotateRandomByte();
  delayMicroseconds(time);
  Wire.begin();
  int address;
  for (address = 1; address < WIRE_MAX; address++ )
  {
    Wire.beginTransmission(address);
    int error = Wire.endTransmission();
    if (error != 0)
    {
      break;
    }
  }
  Wire.begin(address);
  //Wire.end();
  return address;
}

// ---------------------------------------------------------------
// True Random Numbers
// https://gist.github.com/bloc97/b55f684d17edd8f50df8e918cbc00f94
// ---------------------------------------------------------------

#if defined(ARDUINO_AVR_PRO)
#define ANALOG_RANDOM A6
#else
#define ANALOG_RANDOM A1
#endif

const int waitTime = 16;

byte lastByte = 0;
byte leftStack = 0;
byte rightStack = 0;

byte rotate(byte b, int r) {
  return (b << r) | (b >> (8 - r));
}

void pushLeftStack(byte bitToPush) {
  leftStack = (leftStack << 1) ^ bitToPush ^ leftStack;
}

void pushRightStackRight(byte bitToPush) {
  rightStack = (rightStack >> 1) ^ (bitToPush << 7) ^ rightStack;
}

byte getTrueRotateRandomByte() {
  byte finalByte = 0;

  byte lastStack = leftStack ^ rightStack;

  for (int i = 0; i < 4; i++) {
    delayMicroseconds(waitTime);
    int leftBits = analogRead(ANALOG_RANDOM);

    delayMicroseconds(waitTime);
    int rightBits = analogRead(ANALOG_RANDOM);

    finalByte ^= rotate(leftBits, i);
    finalByte ^= rotate(rightBits, 7 - i);

    for (int j = 0; j < 8; j++) {
      byte leftBit = (leftBits >> j) & 1;
      byte rightBit = (rightBits >> j) & 1;

      if (leftBit != rightBit) {
        if (lastStack % 2 == 0) {
          pushLeftStack(leftBit);
        } else {
          pushRightStackRight(leftBit);
        }
      }
    }

  }
  lastByte ^= (lastByte >> 3) ^ (lastByte << 5) ^ (lastByte >> 4);
  lastByte ^= finalByte;

  return lastByte ^ leftStack ^ rightStack;
}

#endif

#if CRC8_EN
// https://stackoverflow.com/questions/51731313/cross-platform-crc8-function-c-and-python-parity-check
uint8_t crc8( uint8_t *addr, uint8_t len) {
      uint8_t crc=0;
      for (uint8_t i=0; i<len;i++) {
         uint8_t inbyte = addr[i];
         for (uint8_t j=0;j<8;j++) {
             uint8_t mix = (crc ^ inbyte) & 0x01;
             crc >>= 1;
             if (mix) 
                crc ^= 0x8C;
         inbyte >>= 1;
      }
    }
   return crc;
}
#endif
