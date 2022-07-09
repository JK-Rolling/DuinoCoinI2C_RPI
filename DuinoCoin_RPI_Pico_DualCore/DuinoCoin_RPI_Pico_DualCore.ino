/*
 * DuinoCoin_RPI_Pico_DualCore.ino
 * created by JK Rolling
 * 27 06 2022
 * 
 * Dual core and dual I2C (400kHz/1MHz)
 * DuinoCoin worker
 * 
 * See kdb.ino on Arduino IDE settings to compile for RP2040
 * 
 * with inspiration from 
 * * Revox (Duino-Coin founder)
 * * Ricaun (I2C Nano sketch)
 */

#pragma GCC optimize ("-Ofast")

#include <Wire.h>
#include <StreamString.h>     // https://github.com/ricaun/StreamJoin
#include "pico/mutex.h"
extern "C" {
  #include <hardware/watchdog.h>
};
#include "sha1.h"

/****************** USER MODIFICATION START ****************/
#define DEV_INDEX                   0
#define I2CS_START_ADDRESS          8
#define I2CS_FIND_ADDR              false               // >>> see kdb before setting it to true <<<
#define WIRE_CLOCK                  1000000             // >>> see kdb before changing this I2C clock frequency <<<
#define I2C0_SDA                    20
#define I2C0_SCL                    21
#define I2C1_SDA                    26
#define I2C1_SCL                    27
#define CRC8_EN                     true
#define WDT_EN                      true
#define CORE_BATON_EN               false
#define LED_EN                      true
#define SENSOR_EN                   true
#define SINGLE_CORE_ONLY            false               // >>> see kdb before setting it to true <<<
#define WORKER_NAME                 "rp2040"
/****************** USER MODIFICATION END ******************/
/*---------------------------------------------------------*/
/****************** FINE TUNING START **********************/
#define LED_PIN                     LED_BUILTIN
#define BLINK_SHARE_FOUND           1
#define BLINK_SETUP_COMPLETE        2
#define BLINK_BAD_CRC               3
#define WDT_PERIOD                  8300
// USB-Serial --> Serial
// UART0-Serial --> Serial1 (preferred, connect FTDI RX pin to Pico GP0)
#define SERIAL_LOGGER               Serial1
#define I2C0                        Wire
#define I2C1                        Wire1
#define I2CS_MAX                    32
#define DIFF_MAX                    1000
#define DUMMY_DATA                  "    "
#define MCORE_WDT_THRESHOLD         10
/****************** FINE TUNING END ************************/

#ifdef SERIAL_LOGGER
#define SerialBegin()               SERIAL_LOGGER.begin(115200);
#define SerialPrint(x)              SERIAL_LOGGER.print(x);
#define SerialPrintln(x)            SERIAL_LOGGER.println(x);
#else
#define SerialBegin()
#define SerialPrint(x)
#define SerialPrintln(x)
#endif

#if SINGLE_CORE_ONLY
#define DISABLE_2ND_CORE
#endif

// prototype
void Blink(uint8_t count, uint8_t pin);

static String DUCOID;
static mutex_t serial_mutex;
static bool core_baton;
static bool wdt_pet = true;
static uint16_t wdt_period_half = WDT_PERIOD/2;
// 40+40+20+3 is the maximum size of a job
const uint16_t job_maxsize = 104;
byte i2c1_addr=0;
bool core0_started = false, core1_started = false;
uint32_t core0_shares = 0, core0_shares_ss = 0, core0_shares_local = 0;
uint32_t core1_shares = 0, core1_shares_ss = 0, core1_shares_local = 0;

// Core0
void setup() {
  bool print_on_por = true;
  SerialBegin();

  // core status indicator
  if (LED_EN) {
    pinMode(LED_PIN, OUTPUT);
  }

  // initialize pico internal temperature sensor
  if (SENSOR_EN) {
    enable_internal_temperature_sensor();
  }

  // initialize mutex
  mutex_init(&serial_mutex);

  // initialize watchdog
  if (WDT_EN) {
    if (watchdog_caused_reboot()) {
      printMsgln(F("\nRebooted by Watchdog!"));
      Blink(BLINK_SETUP_COMPLETE, LED_PIN);
      print_on_por = false;
    }
    // Enable the watchdog, requiring the watchdog to be updated every 8000ms or the chip will reboot
    // Maximum of 0x7fffff, which is approximately 8.3 seconds
    // second arg is pause on debug which means the watchdog will pause when stepping through code
    watchdog_enable(WDT_PERIOD, 1);
  }
  
  // let core0 run first
  core_baton = true;
  
  DUCOID = get_DUCOID();
  core0_setup_i2c();
  Blink(BLINK_SETUP_COMPLETE, LED_PIN);
  if (print_on_por) {
    printMsgln("I2CS_START_ADDRESS: "+String(I2CS_START_ADDRESS));
    printMsgln("I2CS_FIND_ADDR: "+String(I2CS_FIND_ADDR));
    printMsgln("DEV_INDEX: "+String(DEV_INDEX));
    printMsgln("WIRE_CLOCK: "+String(WIRE_CLOCK));
    printMsgln("I2C0_SDA: "+String(I2C0_SDA));
    printMsgln("I2C0_SCL: "+String(I2C0_SCL));
    printMsgln("I2C1_SDA: "+String(I2C1_SDA));
    printMsgln("I2C1_SCL: "+String(I2C1_SCL));
    printMsgln("CRC8_EN: "+String(CRC8_EN));
    printMsgln("WDT_EN: "+String(WDT_EN));
    printMsgln("CORE_BATON_EN: "+String(CORE_BATON_EN));
    printMsgln("LED_EN: "+String(LED_EN));
    printMsgln("SENSOR_EN: "+String(SENSOR_EN));
    printMsgln("SINGLE_CORE_ONLY: "+String(SINGLE_CORE_ONLY));
  }
  printMsgln("core0 startup done!");
}

void loop() {
  if (core_baton || !CORE_BATON_EN) {
    if (core0_loop()) {
      core0_started = true;
      printMsg(F("core0 job done :"));
      printMsg(core0_response());
      Blink(BLINK_SHARE_FOUND, LED_PIN);
      if (WDT_EN && wdt_pet) {
        watchdog_update();
      }
      
      if (core0_started && core1_started && !SINGLE_CORE_ONLY) {
        core0_shares++;
        if (core1_shares != core1_shares_ss) {
          core1_shares_ss = core1_shares;
          core1_shares_local = 0;
        }
        else {
          printMsgln("core0: core1 " + String(MCORE_WDT_THRESHOLD - core1_shares_local) + " remaining count to WDT disable");
          
          if (core1_shares_local >= MCORE_WDT_THRESHOLD) {
            printMsgln("core0: Detected core1 hung. Disable WDT");
            wdt_pet = false;
          }
          if ((MCORE_WDT_THRESHOLD - core1_shares_local) != 0) {
            core1_shares_local++;
          }
        }
      }
    }
    if (!SINGLE_CORE_ONLY)
      core_baton = false;
  }
}

#ifndef DISABLE_2ND_CORE
// Core1
void setup1() {
  sleep_ms(100);
  core1_setup_i2c();
  Blink(BLINK_SETUP_COMPLETE, LED_PIN);
  printMsgln("core1 startup done!");
}

void loop1() {
  if (!core_baton || !CORE_BATON_EN) {
    if (core1_loop()) {
      core1_started = true;
      printMsg(F("core1 job done :"));
      printMsg(core1_response());
      Blink(BLINK_SHARE_FOUND, LED_PIN);
      if (WDT_EN && wdt_pet) {
        watchdog_update();
      }

      if (core0_started && core1_started && !SINGLE_CORE_ONLY) {
        core1_shares++;
        if (core0_shares != core0_shares_ss) {
          core0_shares_ss = core0_shares;
          core0_shares_local = 0;
        }
        else {
          printMsgln("core1: core0 " + String(MCORE_WDT_THRESHOLD - core0_shares_local) + " remaining count to WDT disable");
          if (core0_shares_local >= MCORE_WDT_THRESHOLD) {
            printMsgln("core1: Detected core0 hung. Disable WDT");
            wdt_pet = false;
          }
          if ((MCORE_WDT_THRESHOLD - core0_shares_local) != 0) {
            core0_shares_local++;
          }
        }
      }
    }
    core_baton = true;
  }
}
#endif

// protect scarce resource
void printMsg(String msg) {
  uint32_t owner;
  if (!mutex_try_enter(&serial_mutex, &owner)) {
    if (owner == get_core_num()) return;
    mutex_enter_blocking(&serial_mutex);
  }
  SerialPrint(msg);
  mutex_exit(&serial_mutex);
}

void printMsgln(String msg) {
  printMsg(msg+"\n");
}
