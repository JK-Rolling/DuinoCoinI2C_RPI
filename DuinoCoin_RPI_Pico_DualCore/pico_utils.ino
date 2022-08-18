/*
 * pico_utils.ino
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

#include "pico/unique_id.h"
#include "hardware/structs/rosc.h"
#include "hardware/adc.h"

#ifndef LED_EN
#define LED_EN false
#endif

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

uint8_t calc_crc8( String msg ) {
    int msg_len = msg.length() + 1;
    char char_array[msg_len];
    msg.toCharArray(char_array, msg_len);
    return crc8((uint8_t *)char_array,msg.length());
}

String get_DUCOID() {
  int len = 2 * PICO_UNIQUE_BOARD_ID_SIZE_BYTES + 1;
  uint8_t buff[len] = "";
  pico_get_unique_board_id_string((char *)buff, len);
  String uniqueID = String ((char *)buff, strlen((char *)buff));
  return "DUCOID"+uniqueID;
}

void enable_internal_temperature_sensor() {
  adc_init();
  adc_set_temp_sensor_enabled(true);
  adc_select_input(0x4);
}

double read_temperature() {
  uint16_t adcValue = adc_read();
  double temperature;
  temperature = 3.3f / 0x1000;
  temperature *= adcValue;
  // celcius degree
  temperature = 27.0 - ((temperature - 0.706)/ 0.001721);
  // fahrenheit degree
  // temperature = temperature * 9 / 5 + 32;
  return temperature;
}

double read_humidity() {
  // placeholder for future external sensor
  return 0.0;
}

/* Von Neumann extractor: 
From the input stream, this extractor took bits, 
two at a time (first and second, then third and fourth, and so on). 
If the two bits matched, no output was generated. 
If the bits differed, the value of the first bit was output. 
*/
uint32_t rnd_whitened(void){
    uint32_t k, random = 0;
    uint32_t random_bit1, random_bit2;
    volatile uint32_t *rnd_reg=(uint32_t *)(ROSC_BASE + ROSC_RANDOMBIT_OFFSET);
    
    for (k = 0; k < 32; k++) {
        while(1) {
            random_bit1=0x00000001 & (*rnd_reg);
            random_bit2=0x00000001 & (*rnd_reg);
            if (random_bit1 != random_bit2) break;
        }
        random = random + random_bit1;
        random = random << 1;    
    }
    return random;
}

void Blink(uint8_t count, uint8_t pin = LED_BUILTIN) {
  if (!LED_EN) return;
  uint8_t state = LOW;

  for (int x=0; x<(count << 1); ++x) {
    analogWrite(pin, state ^= LED_BRIGHTNESS);
    sleep_ms(50);
  }
}
