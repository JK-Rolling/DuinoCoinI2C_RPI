/*
 * core0.ino
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

StreamString core0_bufferReceive;
StreamString core0_bufferRequest;
Sha1Wrapper core0_Sha1_base;

void core0_setup_i2c() {
  byte addr = 2 * DEV_INDEX + I2CS_START_ADDRESS;
  I2C0.setSDA(I2C0_SDA);
  I2C0.setSCL(I2C0_SCL);
  I2C0.setClock(WIRE_CLOCK);
  if (I2CS_FIND_ADDR) {
    do {
      addr = core0_find_i2c();
      // search again if address clashes with other core
    } while (addr == i2c1_addr);
  }
  I2C0.begin(addr);
  I2C0.onReceive(core0_receiveEvent);
  I2C0.onRequest(core0_requestEvent);

  printMsgln("core0 I2C0 addr:"+String(addr));
}

byte core0_find_i2c() {
  unsigned long time_delay = (unsigned long) rnd_whitened() >> 13;
  sleep_us(time_delay);
  I2C0.begin();
  byte addr;
  for (addr = I2CS_START_ADDRESS; addr < I2CS_MAX; addr++) {
    I2C0.beginTransmission(addr);
    int error = I2C0.endTransmission();
    if (error != 0) break;
  }
  I2C0.end();
  return addr;
}

void core0_receiveEvent(int howMany) {
  if (howMany == 0) return;
  core0_bufferReceive.write(I2C0.read());
  while (I2C0.available()) I2C0.read();
}

void core0_requestEvent() {
  char c = '\n';
  if (core0_bufferRequest.available() > 0 && core0_bufferRequest.indexOf('\n') != -1) {
    c = core0_bufferRequest.read();
  }
  I2C0.write(c);
}

void core0_abort_loop() {
    SerialPrintln("core0 detected crc8 hash mismatch. Re-request job..");
    while (core0_bufferReceive.available()) core0_bufferReceive.read();
    core0_bufferRequest.print("#\n");
    if (WDT_EN && wdt_pet) {
      watchdog_update();
    }
    Blink(BLINK_BAD_CRC, LED_PIN);
}

void core0_send(String data) {
  core0_bufferRequest.print(DUMMY_DATA + data + "\n");
}

bool core0_loop() {

  if (core0_bufferReceive.available() > 0 && 
      core0_bufferReceive.indexOf("$") != -1) {
    String action = core0_bufferReceive.readStringUntil(',');
    String field  = core0_bufferReceive.readStringUntil('$');
    String response;

    if (action == "get") {
      switch (tolower(field[0])) {
        case 't': // temperature
          if (SENSOR_EN) response = String(read_temperature());
          else response = SENSOR_EN;
          printMsg("core0 temperature: ");
          break;
        case 'h': // humidity
          if (SENSOR_EN) response = String(read_humidity());
          else response = SENSOR_EN;
          printMsg("core0 humidity: ");
          break;
        case 'f': // i2c clock frequency
          response = String(WIRE_CLOCK);
          printMsg("core0 WIRE_CLOCK: " );
          break;
        case 'c': // crc8 status
          response = String(CRC8_EN);
          printMsg("core0 CRC8_EN: ");
          break;
        case 'b': // core_baton
          response = String(CORE_BATON_EN);
          printMsg("core0 CORE_BATON_EN: ");
          break;
        case 's' : // single core only
          response = String(SINGLE_CORE_ONLY);
          printMsg("core0 SINGLE_CORE_ONLY: ");
          break;
        case 'n' : // worker name
          response = String(WORKER_NAME);
          printMsg("WORKER_NAME: ");
          break;
        default:
          response = "unkn";
          printMsgln("core0 command: " + field);
          printMsg("core0 response: ");
      }
      printMsgln(response);
      core0_send(response + "$");
    }
    else if (action == "set") {
      // not used at the moment
    }
    if (WDT_EN && wdt_pet) {
      watchdog_update();
    }
  }

  // do work here
  if (core0_bufferReceive.available() > 0 && core0_bufferReceive.indexOf('\n') != -1) {

    if (core0_bufferReceive.available() > 0 && 
      core0_bufferReceive.indexOf("$") != -1) {
      core0_bufferReceive.readStringUntil('$');
    }
    
    printMsg("core0 job recv : " + core0_bufferReceive);
    
    // Read last block hash
    String lastblockhash = core0_bufferReceive.readStringUntil(',');
    // Read expected hash
    String newblockhash = core0_bufferReceive.readStringUntil(',');

    unsigned int difficulty;
    if (CRC8_EN) {
      difficulty = core0_bufferReceive.readStringUntil(',').toInt();
      uint8_t received_crc8 = core0_bufferReceive.readStringUntil('\n').toInt();
      String data = lastblockhash + "," + newblockhash + "," + String(difficulty) + ",";
      uint8_t expected_crc8 = calc_crc8(data);

      if (received_crc8 != expected_crc8) {
        core0_abort_loop();
        return false;
      }
    }
    else {
      // Read difficulty
      difficulty = core0_bufferReceive.readStringUntil('\n').toInt();
    }

    // clear in case of excessive jobs
    while (core0_bufferReceive.available() > 0 && core0_bufferReceive.indexOf('\n') != -1) {
      core0_bufferReceive.readStringUntil('\n');
    }

    // Start time measurement
    unsigned long startTime = micros();
    // Call DUCO-S1A hasher
    unsigned int ducos1result = 0;
    if (difficulty < DIFF_MAX) ducos1result = core0_ducos1a(lastblockhash, newblockhash, difficulty);
    // End time measurement
    unsigned long endTime = micros();
    // Calculate elapsed time
    unsigned long elapsedTime = endTime - startTime;
    // Send result back to the program with share time
    while (core0_bufferRequest.available()) core0_bufferRequest.read();

    String result = String(ducos1result) + "," + String(elapsedTime) + "," + String(DUCOID);

    // calculate crc8 for result
    if (CRC8_EN) {
      result += ",";
      result += String(calc_crc8(result));
    }
    core0_send(result);
    // prepend non-alnum data (to be discarded in py) for improved data integrity
    //core0_bufferRequest.print("   " + result + "\n");
    
    return true;
  }
  return false;
}

// DUCO-S1A hasher from Revox
uint32_t core0_ducos1a(String lastblockhash, String newblockhash,
                 uint32_t difficulty) {
  
  uint8_t job[job_maxsize];
  newblockhash.toUpperCase();
  const char *c = newblockhash.c_str();
  uint8_t final_len = newblockhash.length() >> 1;
  for (uint8_t i = 0, j = 0; j < final_len; i += 2, j++)
    job[j] = ((((c[i] & 0x1F) + 9) % 25) << 4) + ((c[i + 1] & 0x1F) + 9) % 25;

  // Difficulty loop
  core0_Sha1_base.init();
  core0_Sha1_base.print(lastblockhash);
  for (uint32_t ducos1res = 0; ducos1res < difficulty * 100 + 1; ducos1res++) {
    core0_Sha1 = core0_Sha1_base;
    core0_Sha1.print(String(ducos1res));
    // Get SHA1 result
    uint8_t *hash_bytes = core0_Sha1.result();
    if (memcmp(hash_bytes, job, SHA1_HASH_LEN * sizeof(char)) == 0) {
      // If expected hash is equal to the found hash, return the result
      return ducos1res;
    }
    if (WDT_EN && wdt_pet) {
      if (core0_max_elapsed(millis(), wdt_period_half)) {
        watchdog_update();
      }
    }
  }
  return 0;
}

String core0_response() {
  return core0_bufferRequest;
}

bool core0_max_elapsed(unsigned long current, unsigned long max_elapsed) {
  static unsigned long _start = 0;

  if ((current - _start) > max_elapsed) {
    _start = current;
    return true;
  }
  return false;
}
