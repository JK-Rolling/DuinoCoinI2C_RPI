/*
 * core1.ino
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

StreamString core1_bufferReceive;
StreamString core1_bufferRequest;
Sha1Wrapper core1_Sha1_base;

void core1_setup_i2c() {
  byte addr = 2 * DEV_INDEX + I2CS_START_ADDRESS + 1;
  I2C1.setSDA(I2C1_SDA);
  I2C1.setSCL(I2C1_SCL);
  I2C1.setClock(WIRE_CLOCK);
  if (I2CS_FIND_ADDR) {
    addr = core1_find_i2c();
    i2c1_addr = addr;
  }
  I2C1.begin(addr);
  I2C1.onReceive(core1_receiveEvent);
  I2C1.onRequest(core1_requestEvent);

  printMsgln("core1 I2C1 addr:"+String(addr));
}

byte core1_find_i2c() {
  unsigned long time_delay = (unsigned long) rnd_whitened() >> 13;
  sleep_us(time_delay);
  I2C1.begin();
  byte addr;
  for (addr = I2CS_START_ADDRESS; addr < I2CS_MAX; addr++) {
    I2C1.beginTransmission(addr);
    int error = I2C1.endTransmission();
    if (error != 0) break;
  }
  I2C1.end();
  return addr;
}

void core1_receiveEvent(int howMany) {
  if (howMany == 0) return;
  core1_bufferReceive.write(I2C1.read());
  while (I2C1.available()) I2C1.read();
}

void core1_requestEvent() {
  char c = '\n';
  if (core1_bufferRequest.available() > 0 && core1_bufferRequest.indexOf('\n') != -1) {
    c = core1_bufferRequest.read();
  }
  I2C1.write(c);
}

void core1_abort_loop() {
    SerialPrintln("core1 detected crc8 hash mismatch. Re-request job..");
    while (core1_bufferReceive.available()) core1_bufferReceive.read();
    core1_bufferRequest.print("#\n");
    if (WDT_EN && wdt_pet) {
      watchdog_update();
    }
    Blink(BLINK_BAD_CRC, LED_PIN);
}

void core1_send(String data) {
  core1_bufferRequest.print(DUMMY_DATA + data + "\n");
}

bool core1_loop() {

  if (core1_bufferReceive.available() > 0 && 
      core1_bufferReceive.indexOf("$") != -1) {
    String action = core1_bufferReceive.readStringUntil(',');
    String field  = core1_bufferReceive.readStringUntil('$');
    String response;

    if (action == "get") {
      switch (tolower(field[0])) {
        case 't': // temperature
          if (SENSOR_EN) response = String(read_temperature());
          else response = SENSOR_EN;
          printMsg("core1 temperature: ");
          break;
        case 'h': // humidity
          if (SENSOR_EN) response = String(read_humidity());
          else response = SENSOR_EN;
          printMsg("core0 humidity: ");
          break;
        case 'f': // i2c clock frequency
          response = String(WIRE_CLOCK);
          printMsg("core1 WIRE_CLOCK: ");
          break;
        case 'c': // crc8 status
          response = String(CRC8_EN);
          printMsg("core1 CRC8_EN: ");
          break;
        case 'b': // core_baton
          response = String(CORE_BATON_EN);
          printMsg("core1 CORE_BATON_EN: ");
          break;
        case 's' : // single core only
          response = String(SINGLE_CORE_ONLY);
          printMsg("core1 SINGLE_CORE_ONLY: ");
          break;
        case 'n' : // worker name
          response = String(WORKER_NAME);
          printMsg("WORKER_NAME: ");
          break;
        default:
          response = "unkn";
          printMsgln("core1 command: " + field);
          printMsg("core1 response: ");
      }
      printMsgln(response);
      core1_send(response + "$");
    }
    else if (action == "set") {
      // not used at the moment
    }
    if (WDT_EN && wdt_pet) {
      watchdog_update();
    }
  }

  // do work here
  if (core1_bufferReceive.available() > 0 && core1_bufferReceive.indexOf('\n') != -1) {

    if (core1_bufferReceive.available() > 0 && 
      core1_bufferReceive.indexOf("$") != -1) {
      core1_bufferReceive.readStringUntil('$');
    }

    printMsg("core1 job recv : " + core1_bufferReceive);
    
    // Read last block hash
    String lastblockhash = core1_bufferReceive.readStringUntil(',');
    // Read expected hash
    String newblockhash = core1_bufferReceive.readStringUntil(',');

    unsigned int difficulty;
    if (CRC8_EN) {
      difficulty = core1_bufferReceive.readStringUntil(',').toInt();
      uint8_t received_crc8 = core1_bufferReceive.readStringUntil('\n').toInt();
      String data = lastblockhash + "," + newblockhash + "," + String(difficulty) + ",";
      uint8_t expected_crc8 = calc_crc8(data);
      
      if (received_crc8 != expected_crc8) {
          core1_abort_loop();
          return false;
      }
    }
    else {
      // Read difficulty
      difficulty = core1_bufferReceive.readStringUntil('\n').toInt();
    }

    // clear in case of excessive jobs
    while (core1_bufferReceive.available() > 0 && core1_bufferReceive.indexOf('\n') != -1) {
      core1_bufferReceive.readStringUntil('\n');
    }
    
    // Start time measurement
    unsigned long startTime = micros();
    // Call DUCO-S1A hasher
    unsigned int ducos1result = 0;
    if (difficulty < DIFF_MAX) ducos1result = core1_ducos1a(lastblockhash, newblockhash, difficulty);
    // End time measurement
    unsigned long endTime = micros();
    // Calculate elapsed time
    unsigned long elapsedTime = endTime - startTime;
    // Send result back to the program with share time
    while (core1_bufferRequest.available()) core1_bufferRequest.read();

    String result = String(ducos1result) + "," + String(elapsedTime) + "," + String(DUCOID);

    // calculate crc8 for result
    if (CRC8_EN) {
      result += ",";
      result += String(calc_crc8(result));
    }
    core1_send(result);
    // prepend non-alnum data (to be discarded in py) for improved data integrity
    //core1_bufferRequest.print("   " + result + "\n");
    
    return true;
  }
  return false;
}

// DUCO-S1A hasher from Revox
uint32_t core1_ducos1a(String lastblockhash, String newblockhash,
                 uint32_t difficulty) {
  // 40+40+20+3 is the maximum size of a job
  //const uint16_t job_maxsize = 104;  
  uint8_t job[job_maxsize];
  //Sha1Wrapper core1_Sha1_base;
  newblockhash.toUpperCase();
  const char *c = newblockhash.c_str();
  uint8_t final_len = newblockhash.length() >> 1;
  for (uint8_t i = 0, j = 0; j < final_len; i += 2, j++)
    job[j] = ((((c[i] & 0x1F) + 9) % 25) << 4) + ((c[i + 1] & 0x1F) + 9) % 25;

  // Difficulty loop
  core1_Sha1_base.init();
  core1_Sha1_base.print(lastblockhash);
  for (uint32_t ducos1res = 0; ducos1res < difficulty * 100 + 1; ducos1res++) {
    core1_Sha1 = core1_Sha1_base;
    core1_Sha1.print(String(ducos1res));
    // Get SHA1 result
    uint8_t *hash_bytes = core1_Sha1.result();
    if (memcmp(hash_bytes, job, SHA1_HASH_LEN * sizeof(char)) == 0) {
      // If expected hash is equal to the found hash, return the result
      return ducos1res;
    }
    if (WDT_EN && wdt_pet) {
      if (core1_max_elapsed(millis(), wdt_period_half)) {
        watchdog_update();
      }
    }
  }
  return 0;
}

String core1_response() {
  return core1_bufferRequest;
}

bool core1_max_elapsed(unsigned long current, unsigned long max_elapsed) {
  static unsigned long _start = 0;

  if ((current - _start) > max_elapsed) {
    _start = current;
    return true;
  }
  return false;
}
