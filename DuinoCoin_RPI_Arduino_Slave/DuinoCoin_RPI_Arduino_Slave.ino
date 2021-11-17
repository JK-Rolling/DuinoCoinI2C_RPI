/*
  DoinoCoin_ArduinoSlave.ino
  created 10 05 2021
  by Luiz H. Cassettari
  
  Modified by JK Rolling
*/


// **WARNING**
// Only uncomment WDT_EN if the AVR is using Optiboot bootloader
// Old bootloader will stuck in boot loop
// Only power cycle can make it responsive for 8s - reprogram within this 8s with WDT_EN commented

#define WDT_EN "Optiboot"
//#define SERIAL_LOGGER Serial

/////////////////////////////////////////////////////////////////////////////////////////////////////////////

#ifdef WDT_EN
  #include <avr/wdt.h>
#endif

#ifdef SERIAL_LOGGER
  #define SerialBegin()              SERIAL_LOGGER.begin(115200);
  #define SerialPrint(x)             SERIAL_LOGGER.print(x);
  #define SerialPrintln(x)           SERIAL_LOGGER.println(x);
#else
  #define SerialBegin()
  #define SerialPrint(x)
  #define SerialPrintln(x)
#endif

void setup() {
  #ifdef WDT_EN
    wdt_disable();
  #endif
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  SerialBegin();
  DuinoCoin_setup();
  #ifdef WDT_EN
    wdt_enable(WDTO_8S);
  #endif
  SerialPrintln("Startup Done!");
}

void loop() {
  if (DuinoCoin_loop())
  {
    SerialPrint(F("Job Done : "));
    SerialPrintln(DuinoCoin_response());
    ledOff();
    #ifdef WDT_EN
      wdt_reset();
    #endif
  }
}

void ledOn() {
    // Turn on the built-in led
    #if defined(ARDUINO_ARCH_AVR)
        PORTB = PORTB & B11011111;
    #else
        digitalWrite(LED_BUILTIN, HIGH);
    #endif
}

void ledOff() {
    // Turn off the built-in led
    #if defined(ARDUINO_ARCH_AVR)
        PORTB = PORTB | B00100000;
    #else
        digitalWrite(LED_BUILTIN, LOW);
    #endif
}
