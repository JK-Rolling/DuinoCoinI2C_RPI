/*
 * kdb - knowledge database
 * the answer here is based on experiment and findings by 'JK Rolling'
 * you may or may not see the same things as board package/sketch is constantly evolving with time
 * 
 * > Arduino IDE settings
 *    >> Description:
 *       Recommended settings in IDE to enable smoother miner bring up
 *       1. File -> Preferences -> Additional Boards Manager URLs:
 *          https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json
 *       2. Tools -> Boards -> Board Manager
 *          type "RP2040" in search box and select board from Earle F. Philhower, III
 *          click "Install"
 *       3. Tools -> Boards -> Raspberry Pi RP2040 Boards -> Raspberry Pi Pico
 *       4. Tools -> CPU Speed -> 100MHz
 *       (tested version 2.2.1 at June 2022)
 * 
 * > I2C0_SDA  / I2C0_SCL / I2C1_SDA / I2C1_SCL
 *    >> Description:
 *       Refers to I2C pins on Pico. The I2C pins always comes in pair. e.g. I2C0_SDA and I2C0_SCL.
 *       DO NOT mixed and match them. BAD example - (I2C1_SDA and I2C0_SCL) or (I2C0_SDA(GP20) and I2C0_SCL(GP17))
 *       Valid I2C pairs:
 *       - [I2C0_SDA,I2C0_SCL]: [0,1];[4,5];[8,9];[12,13];[16,17];[20,21];
 *       - [I2C1_SDA,I2C1_SCL]: [2,3];[6,7];[10,11];[14,15];[18,19];[26,27];
 * 
 * > I2CS_FIND_ADDR
 *    >> Description:
 *       with value "true", worker will auto self-assign I2CS address
 *       However, worker may find themself have clashing address between core0/core1
 *       or with other worker. This is due to the random delay before I2C bus scan
 *       might be too close to one another
 *    >> Resolution:
 *       set to "false" so worker will have fixed I2CS address
 *       workers will have more deterministic behavior for Python miner to communicate with
 *       
 * > CRC8_EN
 *    >> Description:
 *       Provide I2C data integrity checks so both RP2040 and Python can decide to discard/re-request
 *       job/result. Recommended value 'true'.
 *       Setting it to 'false' can reduce I2C transaction length rougly 4 bytes or 4.5%. Do this only
 *       if the I2C network is placed in electrically quiet area
 *       
 * > WDT_EN
 *    >> Description:
 *       Kick RP2040 back into initial state when it is stucked for whatever reason.
 *       Current timeout value is maxed at 8.3s. Reduce this value by changing WDT_PERIOD
 *       Recommended value is 'true'
 *       set to 'false' will disable WDT and RP2040 will not restart if hung
 *
 * > CORE_BATON_EN
 *    >>  Description:
 *        with value of "true", baton here limits only one core is active during SHA1 hashing.
 *        with value of "false", the true dual-core capability is unleashed, which in theory
 *        should double the share rate. Also open up possibility of supporting 
 *        true dual I2C slave where 2 independent jobs can be received and hashed simultaneously.
 *        RPi master I2C0 need external pull resistor. You may calculate the best resistance. 
 *        usually 4k7Ohms will work
 *        However, one or both core will lock up and not responsive to USB or I2C in 2.0.3
 *    >>  Resolution:
 *        Update board package to 2.2.1 or newer
 *
 * > WIRE_CLOCK
 *    >> Description:
 *       clock here will determine I2C SCL clock frequency. supported 100kHz, 400kHz, 1MHz
 *       Using 100KHz(100000), rp2040 seems to struggle with data loss/corruption
 *    >> Resolution:
 *       Use 400kHz(400000) or 1MHz(1000000) for rp2040. see table below for clarity
 *       It'll reduce I2C data flight time for faster clock
 *       |-----------|--------------------|---------------------------|
 *       | I2CM freq | RP2040 I2CS freq   | Note                      |
 *       |-----------|--------------------|---------------------------|
 *       | 100kHz    | 100kHz/400kHz/1MHz | I2CS 100kHz is not stable |
 *       | 400kHz    | 400kHz/1MHz        |                           |
 *       | 1MHz      | 1MHz               |                           |
 *       |-----------|--------------------|---------------------------|
 *       *result collected in table above is based on my testbench. I2CM=RPi Zero W 2; I2CS=RPi Pico
 *       ESP I2C master of 100kHz(with repeated write length of 8) seems to work well with rp2040 1MHz
 * 
 * > LED_EN
 *    >> Description:
 *       value 'true' will enable the led to blink whenever a share is done
 *       value 'false' will disable the led
 *       
 * > SENSOR_EN
 *    >> Description:
 *       value 'true' will enable the internal temperature reporting to DuinoCoin IoT section.
 *       currently reporting degree celcius. for degree fahrenheit, look for read_temperature() function
 *       in pico_utils.ino, comment out degree equation and uncomment fahrenheit equation.
 *       value 'false' will disbale internal temperature reporting
 *       This feature doesn't limit to internal temperature sensor. one may connect external sensor
 *       and write code for it so it can report to DuinoCoin online wallet IoT section
 * 
 * > SINGLE_CORE_ONLY
 *    >> Description:
 *       value 'true' will disable core1. Only 1 I2CS address will show up and the single core hash rate 
 *       will increase by ~10%
 *       value 'false' will active dual core.
 *       This parameter will render CORE_BATON_EN unused
 *       
 * > WORKER_NAME
 *    >> Description:
 *       Python will read this name and print on screen before worker start
 *       put a unique name if needed, else no harm done if untouched
 */
