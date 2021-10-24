/*
  DoinoCoin_ArduinoSlave.ino
  created 10 05 2021
  by Luiz H. Cassettari
  
  Modified by JK Rolling
*/

// **WARNING**
// Only uncomment WDT_EN if the AVR is using Optiboot bootloader
// Old bootloader will stuck in boot loop due to existing bug
// Only power cycle can make it responsive for 8s - reprogram within this 8s with WDT_EN commented

// auto reset if no share is returned. assume avr hung
//#define WDT_EN "Optiboot"

#ifdef WDT_EN
  #include <avr/wdt.h>
#endif

void setup() {
  #ifdef WDT_EN
    wdt_disable();
  #endif
  Serial.begin(115200);
  DuinoCoin_setup();
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  #ifdef WDT_EN
    wdt_enable(WDTO_8S);
  #endif
  Serial.println("Startup Done!");
}

void loop() {
  if (DuinoCoin_loop())
  {
    Serial.print(F("Job Done : "));
    Serial.println(DuinoCoin_response());
    Blink();
    #ifdef WDT_EN
      wdt_reset();
    #endif
  }
}

void Blink()
{
  digitalWrite(LED_BUILTIN, HIGH);
  delay(100);
  digitalWrite(LED_BUILTIN, LOW);
}
