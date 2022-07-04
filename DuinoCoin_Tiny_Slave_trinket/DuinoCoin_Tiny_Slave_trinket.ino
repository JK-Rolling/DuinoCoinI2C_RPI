/*
  DoinoCoin_Tiny_Slave_trinket.ino
  created 07 08 2021
  by Luiz H. Cassettari
  Modified by JK-Rolling
  
  12 Sep 2021
  for Adafruit Trinket attiny85
  v3.18-1
  * Added worker info report support
  * support i2c data redundancy
  V3.0-1
  * use -O2 optimization
  v2.7.5-2
  * added HASHRATE_FORCE
  v2.7.5-1
  * added CRC8 checks
  * added WDT to auto reset after 8s of inactivity
*/
#pragma GCC optimize ("-O2")
#include <ArduinoUniqueID.h>  // https://github.com/ricaun/ArduinoUniqueID
#include "TinyWireS.h"
#include "sha1.h"
#include <avr/power.h>

/****************** USER MODIFICATION START ****************/
#define WDT_EN                      true
#define CRC8_EN                     false
#define DEV_INDEX                   0
#define I2CS_START_ADDRESS          8
/****************** USER MODIFICATION END ******************/
/*---------------------------------------------------------*/
/****************** FINE TUNING START **********************/
#define WORKER_NAME                 "trinket"
#define SENSOR_EN                   false
#define WIRE_MAX                    32
#define WIRE_CLOCK                  100000
#define LED                         LED_BUILTIN
/****************** FINE TUNING END ************************/

#if WDT_EN
#include <avr/wdt.h>
#endif

#if defined(ARDUINO_AVR_UNO) | defined(ARDUINO_AVR_PRO)
#define SERIAL_LOGGER Serial
#endif


// Adafruit Trinket ATtiny85 https://adafruit.github.io/arduino-board-index/package_adafruit_index.json
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
#define LedBegin()                pinMode(LED, OUTPUT);
#define LedHigh()                 digitalWrite(LED, HIGH);
#define LedLow()                  digitalWrite(LED, LOW);
#define LedBlink()                LedHigh(); delay(100); LedLow(); delay(100);
#else
#define LedBegin()
#define LedHigh()
#define LedLow()
#define LedBlink()
#endif

#define BUFFER_MAX 90
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
  if (F_CPU == 16000000) clock_prescale_set(clock_div_1);
  SerialBegin();
  initialize_i2c();
  #if WDT_EN
  wdt_disable();
  wdt_enable(WDTO_8S);
  #endif
  LedBegin();
  LedBlink();
  LedBlink();
  LedBlink();
  SerialPrintln("Startup Done!");
}

// --------------------------------------------------------------------- //
// loop
// --------------------------------------------------------------------- //

void loop() {
  do_work();
  millis(); // ????? For some reason need this to work the i2c
  TinyWireS_stop_check();
}

// --------------------------------------------------------------------- //
// run
// --------------------------------------------------------------------- //

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
      return;
    }
    
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
  
  #if WDT_EN
  wdt_reset();
  #endif
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
    #if WDT_EN
    if (runEvery(2000))
      wdt_reset();
    #endif
  }
  return 0;
}

// --------------------------------------------------------------------- //
// i2c
// --------------------------------------------------------------------- //

void initialize_i2c(void) {
  address = DEV_INDEX + I2CS_START_ADDRESS;

  SerialPrint("Wire begin ");
  SerialPrintln(address);
  TinyWireS.begin(address);
  TinyWireS.onReceive(onReceiveJob);
  TinyWireS.onRequest(onRequestResult);
}

void onReceiveJob(uint8_t howMany) {    
  if (howMany == 0) return;
  if (working) return;
  if (jobdone) return;
  
  char c = TinyWireS.read();
  buffer[buffer_length++] = c;
  if (buffer_length == BUFFER_MAX) buffer_length--;
  if (c == CHAR_END || c == '$') {
    working = true;
  }
  while (TinyWireS.available()) {
    TinyWireS.read();
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
  TinyWireS.write(c);
}

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
