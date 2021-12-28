# DuinoCoinI2C_RPI
This project design to mine [Duino-Coin](https://github.com/revoxhere/duino-coin) using Raspberry Pi or equivalent SBC as a master and Arduino/ATtiny85 as a slave.

Using the I2C communication to connect all the boards and make a scalable communication between the master and the slaves.

## Video Tutorial

Raspberry Pi AVR I2C Bus 1 [tutorial video](https://youtu.be/bZ2XwPpYtiw)

Raspberry Pi AVR I2C Bus 0 [tutorial video](https://youtu.be/ywO7j4yqIlg)

## Python Environment Setup

### Linux

```BASH
sudo apt update
sudo apt install python3 python3-pip git i2c-tools python3-smbus screen -y # Install dependencies
git clone https://github.com/JK-Rolling/DuinoCoinI2C_RPI.git # Clone DuinoCoinI2C_RPI repository
cd DuinoCoinI2C_RPI
python3 -m pip install -r requirements.txt # Install pip dependencies
````

Use `sudo raspi-config` to enable I2C. Refer detailed steps at [raspberry-pi-i2c](https://pimylifeup.com/raspberry-pi-i2c/)

For RPI I2C Bus 0, extra step is needed, `sudo nano /boot/config.txt` and add `dtparam=i2c_vc=on`, save and reboot

Finally, connect your I2C AVR miner and launch the software (e.g. `python3 ./AVR_Miner_RPI.py`)

### Windows

1. Download and install [Python 3](https://www.python.org/downloads/) (add Python and Pip to Windows PATH)
2. Download [the DuinoCoinI2C_RPI](https://github.com/JK-Rolling/DuinoCoinI2C_RPI/releases)
3. Extract the zip archive you've downloaded and open the folder in command prompt
4. In command prompt type `py -m pip install -r requirements.txt` to install required pip dependencies

Finally, connect your I2C AVR miner and launch the software (e.g. `python3 ./AVR_Miner_RPI.py` or `py AVR_Miner_RPI.py` in the command prompt)

## Version

DuinoCoinI2C_RPI Version 2.75

# Arduino - Slave

Occasionally slaves might hang and not responding to master. quick workaround is to press the reset button on the slave to bring it back.

Once in a blue moon, one of the slave might pull down the whole bus with it. power cycling the rig is the fastest way to bring it back.

To solve these issues permanently, update Nano with Optiboot bootloader. WDT will auto reset the board if there is no activity within 8s.

Uncomment this line to activate the WDT. works for Nano clone as well. **make sure the Nano is using Optiboot**

`#define WDT_EN "Optiboot"`

# ATtiny85 - Slave

Use tiny slave code for ATtiny85 although the same code can also be loaded into Arduino. Arduino 168p or equivalent have less program storage space/RAM should use tiny slave to work properly.

4 main feature can be turn on/off individually to cater for your specific scenario. comment out to disable.
```C
#define FIND_I2C
#define WDT_EN
#define CRC8_EN
#define HASHRATE_FORCE
```
|`#define`| Note |
|:-| :---- |
|FIND_I2C|Scan available I2CS address and self-assign|
|WDT_EN|Auto self-reset every 8s in case of inactivity|
|CRC8_EN|I2C CRC8 insertion and data integrity checks|
|HASHRATE_FORCE*|Force the hashrate to be 195H/s ±5H/s|

\* **use at own risk**

each SBC have different starting I2CS address from `i2cdetect` command. Address that is not shown is still usable. To change the I2CS starting address, modify `#define I2CS_START_ADDRESS 3`

For disabled `FIND_I2C`, manually assign I2CS address by modifying `#define DEV_INDEX 0`



## Library Dependency

* [DuinoCoin](https://github.com/ricaun/arduino-DuinoCoin) (Handle the `Ducos1a` hash work)
* [ArduinoUniqueID](https://github.com/ricaun/ArduinoUniqueID) (Handle the chip ID)
* [StreamJoin](https://github.com/ricaun/StreamJoin) (StreamString for AVR)

## I2C Address 

The I2C Address on the Arduino is hardcoded by user. if an address already exists on the I2C bus, the behavior is undefined

Change the value on the define for each Nano for unique address:
```
#define DEV_INDEX 1
```

# Raspberry PI or SBC - Master

The master requests the job on the `DuinoCoin` server and sends the work to the slave (Arduino).

After the job is done, the slave sends back the response to the master (SBC) and then sends back to the `DuinoCoin` server.

## Max Client/Slave

The code theoretically supports up to 117 clients on Raspberry PI on single I2C bus

Slave addresses range from 0x3..0x77

RPi have 2 I2C buses which bring up the count up to 234. This requires 2 separate instances of Python miner with it's own Settings.cfg file. Duplicate the directory into 2 and start the setup from there.

## Enable I2C on Raspberry PI

Google or refer to [raspberry-pi-i2c](https://pimylifeup.com/raspberry-pi-i2c/)

For RPI I2C Bus 0, there might not be pull up resistor built in. It relies on the pull up from Nano.

For other I2C slave that do not have pull up capability, add 2KOhm resistor to both SDA and SCL line on I2C bus 0.

**Note:** If you see bad shares, it could be due to a bug in [RPI I2C hardware](https://github.com/raspberrypi/linux/issues/254)

# Connection Pinouts

Connect the pins of the Raspberry PI on the Arduino like the table/images below, use a [Logic Level Converter](https://www.sparkfun.com/products/12009) to connect between the SBC and Arduino/ATtiny85

|| RPI | Logic Level Converter | Arduino |
|:-:| :----: | :-----: | :-----: |
||3.3V | <---> | 5V |
||GND | <---> | GND |
|`SDA`| PIN 3 | <---> | A4 |
|`SCL`| PIN 5 | <---> | A5 |

|| RPI | Logic Level Converter | ATtiny85 |
|:-:| :----: | :-----: | :-----: |
||3.3V | <---> | 5V |
||GND | <---> | GND |
|`SDA`| PIN 3 | <---> | PB0 |
|`SCL`| PIN 5 | <---> | PB2 |

# License and Terms of service

All refers back to original [Duino-Coin licensee and terms of service](https://github.com/revoxhere/duino-coin)
