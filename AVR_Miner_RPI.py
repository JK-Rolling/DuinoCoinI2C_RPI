#!/usr/bin/env python3
"""
RPI I2C Unofficial AVR Miner 4.1 © MIT licensed
Modified by JK-Rolling
20210919

Full credit belong to
https://duinocoin.com
https://github.com/revoxhere/duino-coin
Duino-Coin Team & Community 2019-current
"""

from os import _exit, mkdir
from os import name as osname
from os import path
from os import system as ossystem
from platform import machine as osprocessor
from platform import system
import sys

from configparser import ConfigParser
from pathlib import Path

from json import load as jsonload
from random import choice
from locale import LC_ALL, getdefaultlocale, getlocale, setlocale

from re import sub
from socket import socket
from datetime import datetime
from statistics import mean
from signal import SIGINT, signal
from collections import deque
from time import ctime, sleep, strptime, time
import pip

from subprocess import DEVNULL, Popen, check_call, call
from threading import Thread
from threading import Lock as thread_lock
from threading import Semaphore

import base64 as b64

import os
import random
printlock = Semaphore(value=1)
i2clock = Semaphore(value=1)


# Python <3.5 check
f"Your Python version is too old. Duino-Coin Miner requires version 3.6 or above. Update your packages and try again"


def install(package):
    try:
        pip.main(["install",  package])
    except AttributeError:
        check_call([sys.executable, '-m', 'pip', 'install', package])
    call([sys.executable, __file__])

try:
    from smbus import SMBus
except ModuleNotFoundError:
    print("SMBus is not installed. "
          + "Miner will try to automatically install it "
          + "If it fails, please manually execute "
          + "python3 -m pip install smbus")
    install('smbus')

try:
    import requests
except ModuleNotFoundError:
    print("Requests is not installed. "
          + "Miner will try to automatically install it "
          + "If it fails, please manually execute "
          + "python3 -m pip install requests")
    install('requests')

try:
    from colorama import Back, Fore, Style, init
    init(autoreset=True)
except ModuleNotFoundError:
    print("Colorama is not installed. "
          + "Miner will try to automatically install it "
          + "If it fails, please manually execute "
          + "python3 -m pip install colorama")
    install("colorama")

try:
    from pypresence import Presence
except ModuleNotFoundError:
    print("Pypresence is not installed. "
          + "Miner will try to automatically install it "
          + "If it fails, please manually execute "
          + "python3 -m pip install pypresence")
    install("pypresence")


def now():
    return datetime.now()


def port_num(com):
    #return str(''.join(filter(str.isdigit, com)))
    return "{:02x}".format(int(com,16))


class Settings:
    VER = '4.3'
    SOC_TIMEOUT = 10
    REPORT_TIME = 120
    AVR_TIMEOUT = 4  # diff 10 * 100 / 340 h/s = 2.95 s
    DELAY_START = 5  # 5 seconds start delay between worker to help kolka sync efficiency drop
    IoT_EN = "n"
    DATA_DIR = "Duino-Coin AVR Miner " + str(VER)
    SEPARATOR = ","
    ENCODING = "utf-8"
    I2C_WR_RDDCY = 2
    WORKER_CFG_SHARED = "y"
    disable_title = False
    try:
        # Raspberry Pi latin users can't display this character
        "‖".encode(sys.stdout.encoding)
        BLOCK = " ‖ "
    except:
        BLOCK = " | "
    PICK = ""
    COG = " @"
    if (osname != "nt"
        or bool(osname == "nt"
                and os.environ.get("WT_SESSION"))):
        # Windows' cmd does not support emojis, shame!
        # And some codecs same, for example the Latin-1 encoding don`t support emoji
        try:
            "⛏ ⚙".encode(sys.stdout.encoding) # if the terminal support emoji
            PICK = " ⛏ "
            COG = " ⚙ "
        except UnicodeEncodeError: # else
            PICK = ""
            COG = " @ "

def has_mining_key(username):
    response = requests.get(
        "https://server.duinocoin.com/mining_key"
            + "?u=" + username,
        timeout=10
    ).json()
    return response["has_key"]
    
def check_mining_key(user_settings):
    user_settings = user_settings["AVR Miner"]

    if user_settings["mining_key"] != "None":
        key = "&k=" + b64.b64decode(user_settings["mining_key"]).decode('utf-8')
    else:
        key = ''

    response = requests.get(
        "https://server.duinocoin.com/mining_key"
            + "?u=" + user_settings["username"]
            + key,
        timeout=10
    ).json()
    debug_output(response)

    if response["success"] and not response["has_key"]: # if the user doesn't have a mining key
        user_settings["mining_key"] = "None"
        config["AVR Miner"] = user_settings

        with open(Settings.DATA_DIR + '/Settings.cfg',
            "w") as configfile:
            config.write(configfile)
            print("sys0",
                Style.RESET_ALL + get_string("config_saved"),
                "info")
        return

    if not response["success"]:
        if response["message"] == "Too many requests":
            debug_output("Skipping mining key check - getting 429")
            return

        if user_settings["mining_key"] == "None":
            pretty_print(
                "sys0",
                get_string("mining_key_required"),
                "warning")

            mining_key = input("Enter your mining key: ")
            user_settings["mining_key"] = b64.b64encode(mining_key.encode("utf-8")).decode('utf-8')
            config["AVR Miner"] = user_settings

            with open(Settings.DATA_DIR + '/Settings.cfg',
                      "w") as configfile:
                config.write(configfile)
                print("sys0",
                    Style.RESET_ALL + get_string("config_saved"),
                    "info")
            check_mining_key(config)
        else:
            pretty_print(
                "sys0",
                get_string("invalid_mining_key"),
                "error")

            retry = input("Do you want to retry? (y/n): ")
            if retry == "y" or retry == "Y":
                mining_key = input("Enter your mining key: ")
                user_settings["mining_key"] = b64.b64encode(mining_key.encode("utf-8")).decode('utf-8')
                config["AVR Miner"] = user_settings

                with open(Settings.DATA_DIR + '/Settings.cfg',
                        "w") as configfile:
                    config.write(configfile)
                print("sys0",
                    Style.RESET_ALL + get_string("config_saved"),
                    "info")
                sleep(1.5)
                check_mining_key(config)
            else:
                return


class Client:
    """
    Class helping to organize socket connections
    """
    def connect(pool: tuple):
        s = socket()
        s.settimeout(Settings.SOC_TIMEOUT)
        s.connect((pool))
        return s

    def send(s, msg: str):
        sent = s.sendall(str(msg).encode(Settings.ENCODING))
        return True

    def recv(s, limit: int = 128):
        data = s.recv(limit).decode(Settings.ENCODING).rstrip("\n")
        return data

    def fetch_pool():
        while True:
            pretty_print("net0", " " + get_string("connection_search"),
                         "info")
            try:
                response = requests.get(
                    "https://server.duinocoin.com/getPool",
                    timeout=10).json()
                    
                if response["success"] == True:
                    pretty_print("net0", get_string("connecting_node")
                                 + response["name"],
                                 "info")
                                 
                    NODE_ADDRESS = response["ip"]
                    NODE_PORT = response["port"]
                    debug_output(f"Fetched pool: {response['name']}")
                    return (NODE_ADDRESS, NODE_PORT)
                    
                elif "message" in response:
                    pretty_print(f"Warning: {response['message']}"
                                 + ", retrying in 15s", "warning", "net0")
                    sleep(15)
                else:
                    raise Exception(
                        "no response - IP ban or connection error")
            except Exception as e:
                if "Expecting value" in str(e):
                    pretty_print("net0", get_string("node_picker_unavailable")
                                 + f"15s {Style.RESET_ALL}({e})",
                                 "warning")
                else:
                    pretty_print("net0", get_string("node_picker_error")
                                 + f"15s {Style.RESET_ALL}({e})",
                                 "error")
                sleep(15)


class Donate:
    def load(donation_level):
        if donation_level > 0:
            if osname == 'nt':
                if not Path(
                        f"{Settings.DATA_DIR}/Donate.exe").is_file():
                    url = ('https://server.duinocoin.com/'
                           + 'donations/DonateExecutableWindows.exe')
                    r = requests.get(url, timeout=15)
                    with open(f"{Settings.DATA_DIR}/Donate.exe",
                              'wb') as f:
                        f.write(r.content)
            elif osname == "posix":
                if osprocessor() == "aarch64":
                    url = ('https://server.duinocoin.com/'
                           + 'donations/DonateExecutableAARCH64')
                elif osprocessor() == "armv7l":
                    url = ('https://server.duinocoin.com/'
                           + 'donations/DonateExecutableAARCH32')
                else:
                    url = ('https://server.duinocoin.com/'
                           + 'donations/DonateExecutableLinux')
                if not Path(
                        f"{Settings.DATA_DIR}/Donate").is_file():
                    r = requests.get(url, timeout=15)
                    with open(f"{Settings.DATA_DIR}/Donate",
                              "wb") as f:
                        f.write(r.content)

    def start(donation_level):
        donation_settings = requests.get(
            "https://server.duinocoin.com/donations/settings.json").json()

        if os.name == 'nt':
            cmd = (f'cd "{Settings.DATA_DIR}" & Donate.exe '
                   + f'-o {donation_settings["url"]} '
                   + f'-u {donation_settings["user"]} '
                   + f'-p {donation_settings["pwd"]} '
                   + f'-s 4 -e {donation_level*2}')
        elif os.name == 'posix':
            cmd = (f'cd "{Settings.DATA_DIR}" && chmod +x Donate '
                   + '&& nice -20 ./Donate '
                   + f'-o {donation_settings["url"]} '
                   + f'-u {donation_settings["user"]} '
                   + f'-p {donation_settings["pwd"]} '
                   + f'-s 4 -e {donation_level*2}')

        if donation_level <= 0:
            pretty_print(
                'sys0', Fore.YELLOW
                + get_string('free_network_warning').lstrip()
                + get_string('donate_warning').replace("\n", "\n\t\t")
                + Fore.GREEN + 'https://duinocoin.com/donate'
                + Fore.YELLOW + get_string('learn_more_donate'),
                'warning')
            sleep(5)

        if donation_level > 0:
            debug_output(get_string('starting_donation'))
            donateExecutable = Popen(cmd, shell=True, stderr=DEVNULL)
            pretty_print('sys0',
                         get_string('thanks_donation').replace("\n", "\n\t\t"),
                         'error')


shares = [0, 0, 0]
bad_crc8 = 0
i2c_retry_count = 0
hashrate_mean = deque(maxlen=25)
ping_mean = deque(maxlen=25)
diff = 0
shuffle_ports = "y"
donator_running = False
job = ''
debug = 'n'
discord_presence = 'y'
rig_identifier = 'None'
donation_level = 0
hashrate = 0
config = ConfigParser()
mining_start_time = time()
worker_cfg_global = {"valid":False}

if not path.exists(Settings.DATA_DIR):
    mkdir(Settings.DATA_DIR)

if not Path(Settings.DATA_DIR + '/Translations.json').is_file():
    url = ('https://raw.githubusercontent.com/'
           + 'revoxhere/'
           + 'duino-coin/master/Resources/'
           + 'AVR_Miner_langs.json')
    r = requests.get(url, timeout=5)
    with open(Settings.DATA_DIR + '/Translations.json', 'wb') as f:
        f.write(r.content)

# Load language file
with open(Settings.DATA_DIR + '/Translations.json', 'r',
          encoding='utf8') as lang_file:
    lang_file = jsonload(lang_file)

# OS X invalid locale hack
if system() == 'Darwin':
    if getlocale()[0] is None:
        setlocale(LC_ALL, 'en_US.UTF-8')

try:
    if not Path(Settings.DATA_DIR + '/Settings.cfg').is_file():
        locale = getdefaultlocale()[0]
        if locale.startswith('es'):
            lang = 'spanish'
        elif locale.startswith('sk'):
            lang = 'slovak'
        elif locale.startswith('ru'):
            lang = 'russian'
        elif locale.startswith('pl'):
            lang = 'polish'
        elif locale.startswith('de'):
            lang = 'german'
        elif locale.startswith('fr'):
            lang = 'french'
        elif locale.startswith('jp'):
            lang = 'japanese'
        elif locale.startswith('tr'):
            lang = 'turkish'
        elif locale.startswith('it'):
            lang = 'italian'
        elif locale.startswith('pt'):
            lang = 'portuguese'
        elif locale.startswith("zh_TW"):
            lang = "chinese_Traditional"
        elif locale.startswith('zh'):
            lang = 'chinese_simplified'
        elif locale.startswith('th'):
            lang = 'thai'
        elif locale.startswith('az'):
            lang = 'azerbaijani'
        elif locale.startswith('nl'):
            lang = 'dutch'
        elif locale.startswith('ko'):
            lang = 'korean'
        elif locale.startswith("id"):
            lang = "indonesian"
        elif locale.startswith("cz"):
            lang = "czech"
        elif locale.startswith("fi"):
            lang = "finnish"
        else:
            lang = 'english'
    else:
        try:
            config.read(Settings.DATA_DIR + '/Settings.cfg')
            lang = config["AVR Miner"]['language']
        except Exception:
            lang = 'english'
except:
    lang = 'english'


def get_string(string_name: str):
    if string_name in lang_file[lang]:
        return lang_file[lang][string_name]
    elif string_name in lang_file['english']:
        return lang_file['english'][string_name]
    else:
        return string_name


def get_prefix(symbol: str,
               val: float,
               accuracy: int):
    """
    H/s, 1000 => 1 kH/s
    """
    if val >= 1_000_000_000_000:  # Really?
        val = str(round((val / 1_000_000_000_000), accuracy)) + " T"
    elif val >= 1_000_000_000:
        val = str(round((val / 1_000_000_000), accuracy)) + " G"
    elif val >= 1_000_000:
        val = str(round((val / 1_000_000), accuracy)) + " M"
    elif val >= 1_000:
        val = str(round((val / 1_000))) + " k"
    else:
        if symbol:
            val = str(round(val)) + " "
        else:
            val = str(round(val))
    return val + symbol


def debug_output(text: str):
    if debug == 'y':
        print(Style.RESET_ALL + Fore.WHITE
              + now().strftime(Style.DIM + '%H:%M:%S.%f ')
              + Style.NORMAL + f'DEBUG: {text}')

def ondemand_print(text: str):
    print(Style.RESET_ALL + Fore.WHITE
          + now().strftime(Style.DIM + '%H:%M:%S.%f ')
          + Style.NORMAL + f'DEBUG: {text}')

def title(title: str):
    if not Settings.disable_title:
        if osname == 'nt':
            """
            Changing the title in Windows' cmd
            is easy - just use the built-in
            title command
            """
            ossystem('title ' + title)
        else:
            """
            Most *nix terminals use
            this escape sequence to change
            the console window title
            """
            try:
                print('\33]0;' + title + '\a', end='')
                sys.stdout.flush()
            except Exception as e:
                debug_output("Error setting title: " +str(e))
                Settings.disable_title = True


def handler(signal_received, frame):
    pretty_print(
        'sys0', get_string('sigint_detected')
        + Style.NORMAL + Fore.RESET
        + get_string('goodbye'), 'warning')

    _exit(0)


# Enable signal handler
signal(SIGINT, handler)


def load_config():
    global username
    global donation_level
    global avrport
    global hashrate_list
    global debug
    global rig_identifier
    global discord_presence
    global shuffle_ports
    global SOC_TIMEOUT
    global i2c

    if not Path(str(Settings.DATA_DIR) + '/Settings.cfg').is_file():
        print(
            Style.BRIGHT + get_string('basic_config_tool')
            + Settings.DATA_DIR
            + get_string('edit_config_file_warning'))

        print(
            Style.RESET_ALL + get_string('dont_have_account')
            + Fore.YELLOW + get_string('wallet') + Fore.RESET
            + get_string('register_warning'))

        correct_username = False
        while not correct_username:
            username = input(
                Style.RESET_ALL + Fore.YELLOW
                + get_string('ask_username')
                + Fore.RESET + Style.BRIGHT)
            if not username:
                username = choice(["revox", "Bilaboz"])

            r = requests.get(f"https://server.duinocoin.com/users/{username}", 
                             timeout=Settings.SOC_TIMEOUT).json()
            correct_username = r["success"]
            if not correct_username:
                print(get_string("incorrect_username"))

        mining_key = "None"
        if has_mining_key(username):
            mining_key = input(Style.RESET_ALL + Fore.YELLOW
                           + get_string("ask_mining_key")
                           + Fore.RESET + Style.BRIGHT)
            mining_key = b64.b64encode(mining_key.encode("utf-8")).decode('utf-8')
        
        i2c = input(
            Style.RESET_ALL + Fore.YELLOW
            + 'Enter your choice of I2C bus (e.g. 1): '
            + Fore.RESET + Style.BRIGHT)
        i2c = int(i2c)

        if ossystem(f'i2cdetect -y {i2c}') != 0:
            print(Style.RESET_ALL + Fore.RED
                    + 'I2C is disabled. Exiting..')
            _exit(1)
        else :
            print(Style.RESET_ALL + Fore.YELLOW
                + 'i2cdetect has found I2C addresses above')
                
        avrport = ''
        rig_identifier = ''
        while True:
            current_port = input(
                Style.RESET_ALL + Fore.YELLOW
                + 'Enter your I2C slave address (e.g. 8): '
                + Fore.RESET + Style.BRIGHT)
                
            confirm_identifier = input(
                Style.RESET_ALL + Fore.YELLOW
                + get_string('ask_rig_identifier') + ":"
                + Fore.RESET + Style.BRIGHT)
            if confirm_identifier == 'y' or confirm_identifier == 'Y':
                current_identifier = input(
                    Style.RESET_ALL + Fore.YELLOW
                    + get_string('ask_rig_name')
                    + Fore.RESET + Style.BRIGHT)
                rig_identifier += current_identifier
            else:
                rig_identifier += "None"

            avrport += current_port
            confirmation = input(
                Style.RESET_ALL + Fore.YELLOW
                + get_string('ask_anotherport')
                + Fore.RESET + Style.BRIGHT)

            if confirmation == 'y' or confirmation == 'Y':
                avrport += ','
                rig_identifier += ','
            else:
                break
                
        Settings.IoT_EN = input(
            Style.RESET_ALL + Fore.YELLOW
            + 'Do you want to turn on Duino IoT feature? (y/N): '
            + Fore.RESET + Style.BRIGHT)
        Settings.IoT_EN = Settings.IoT_EN.lower()
        if len(Settings.IoT_EN) == 0: Settings.IoT_EN = "n"
        elif Settings.IoT_EN.lower() != "n": Settings.IoT_EN = "y"

        donation_level = '0'
        if osname == 'nt' or osname == 'posix':
            donation_level = input(
                Style.RESET_ALL + Fore.YELLOW
                + get_string('ask_donation_level')
                + Fore.RESET + Style.BRIGHT)

        donation_level = sub(r'\D', '', donation_level)
        if donation_level == '':
            donation_level = 1
        if float(donation_level) > int(5):
            donation_level = 5
        if float(donation_level) < int(0):
            donation_level = 0
        donation_level = int(donation_level)

        config["AVR Miner"] = {
            'username':         username,
            'avrport':          avrport,
            'donate':           donation_level,
            'language':         lang,
            'identifier':       rig_identifier,
            'debug':            'n',
            "soc_timeout":      45,
            "avr_timeout":      Settings.AVR_TIMEOUT,
            "delay_start":      Settings.DELAY_START,
            "duinoiot_en":      Settings.IoT_EN,
            "discord_presence": "y",
            "periodic_report":  Settings.REPORT_TIME,
            "shuffle_ports":    "y",
            "mining_key":       mining_key,
            "i2c":              i2c,
            "i2c_wr_rddcy":     Settings.I2C_WR_RDDCY,
            "worker_cfg_shared":Settings.WORKER_CFG_SHARED}

        with open(str(Settings.DATA_DIR)
                  + '/Settings.cfg', 'w') as configfile:
            config.write(configfile)

        avrport = avrport.split(',')
        rig_identifier = rig_identifier.split(',')
        print(Style.RESET_ALL + get_string('config_saved'))
        hashrate_list = [0] * len(avrport)

    else:
        config.read(str(Settings.DATA_DIR) + '/Settings.cfg')
        username = config["AVR Miner"]['username']
        avrport = config["AVR Miner"]['avrport']
        avrport = avrport.replace(" ", "").split(',')
        donation_level = int(config["AVR Miner"]['donate'])
        debug = config["AVR Miner"]['debug'].lower()
        rig_identifier = config["AVR Miner"]['identifier'].split(',')
        Settings.SOC_TIMEOUT = int(config["AVR Miner"]["soc_timeout"])
        Settings.AVR_TIMEOUT = float(config["AVR Miner"]["avr_timeout"])
        Settings.DELAY_START = int(config["AVR Miner"]["delay_start"])
        Settings.IoT_EN = config["AVR Miner"]["duinoiot_en"].lower()
        discord_presence = config["AVR Miner"]["discord_presence"]
        shuffle_ports = config["AVR Miner"]["shuffle_ports"]
        Settings.REPORT_TIME = int(config["AVR Miner"]["periodic_report"])
        hashrate_list = [0] * len(avrport)
        i2c = int(config["AVR Miner"]["i2c"])
        Settings.I2C_WR_RDDCY = int(config["AVR Miner"]["i2c_wr_rddcy"])
        Settings.WORKER_CFG_SHARED = config["AVR Miner"]["worker_cfg_shared"].lower()


def greeting():
    global greeting
    print(Style.RESET_ALL)

    current_hour = strptime(ctime(time())).tm_hour
    if current_hour < 12:
        greeting = get_string('greeting_morning')
    elif current_hour == 12:
        greeting = get_string('greeting_noon')
    elif current_hour > 12 and current_hour < 18:
        greeting = get_string('greeting_afternoon')
    elif current_hour >= 18:
        greeting = get_string('greeting_evening')
    else:
        greeting = get_string('greeting_back')

    print(
        Style.DIM + Fore.MAGENTA
        + Settings.BLOCK + Fore.YELLOW
        + Style.BRIGHT + '\n  Unofficial Duino-Coin RPI I2C AVR Miner'
        + Style.RESET_ALL + Fore.MAGENTA
        + f' {Settings.VER}' + Fore.RESET
        + ' 2021-current')

    print(
        Style.DIM + Fore.MAGENTA
        + Settings.BLOCK + Style.NORMAL + Fore.MAGENTA
        + 'https://github.com/JK-Rolling  '
        + 'https://github.com/revoxhere/duino-coin')

    if lang != "english":
        print(
            Style.DIM + Fore.MAGENTA
            + Settings.BLOCK + Style.NORMAL
            + Fore.RESET + lang.capitalize()
            + " translation: " + Fore.MAGENTA
            + get_string("translation_autor"))

    print(
        Style.DIM + Fore.MAGENTA
        + Settings.BLOCK + Style.NORMAL
        + Fore.RESET + get_string('avr_on_port')
        + Style.BRIGHT + Fore.YELLOW
        + ', '.join(avrport))

    if osname == 'nt' or osname == 'posix':
        print(
            Style.DIM + Fore.MAGENTA + Settings.BLOCK
            + Style.NORMAL + Fore.RESET
            + get_string('donation_level') + Style.BRIGHT
            + Fore.YELLOW + str(donation_level))

    print(
        Style.DIM + Fore.MAGENTA
        + Settings.BLOCK + Style.NORMAL
        + Fore.RESET + get_string('algorithm')
        + Style.BRIGHT + Fore.YELLOW
        + 'DUCO-S1A ⚙ AVR diff')

    if rig_identifier[0] != "None" or len(rig_identifier) > 1:
        print(
            Style.DIM + Fore.MAGENTA
            + Settings.BLOCK + Style.NORMAL
            + Fore.RESET + get_string('rig_identifier')
            + Style.BRIGHT + Fore.YELLOW + ", ".join(rig_identifier))

    print(
        Style.DIM + Fore.MAGENTA
        + Settings.BLOCK + Style.NORMAL
        + Fore.RESET + get_string("using_config")
        + Style.BRIGHT + Fore.YELLOW 
        + str(Settings.DATA_DIR + '/Settings.cfg'))

    print(
        Style.DIM + Fore.MAGENTA
        + Settings.BLOCK + Style.NORMAL
        + Fore.RESET + str(greeting) + ', '
        + Style.BRIGHT + Fore.YELLOW
        + str(username) + '!\n')


def init_rich_presence():
    # Initialize Discord rich presence
    global RPC
    try:
        RPC = Presence(905158274490441808)
        RPC.connect()
        Thread(target=update_rich_presence).start()
    except Exception as e:
        #print("Error launching Discord RPC thread: " + str(e))
        pass


def update_rich_presence():
    startTime = int(time())
    while True:
        try:
            total_hashrate = get_prefix("H/s", sum(hashrate_list), 2)
            RPC.update(details="Hashrate: " + str(total_hashrate),
                       start=mining_start_time,
                       state=str(shares[0]) + "/"
                       + str(shares[0] + shares[1])
                       + " accepted shares",
                       large_image="avrminer",
                       large_text="Duino-Coin, "
                       + "a coin that can be mined with almost everything"
                       + ", including AVR boards",
                       buttons=[{"label": "Visit duinocoin.com",
                                 "url": "https://duinocoin.com"},
                                {"label": "Join the Discord",
                                 "url": "https://discord.gg/k48Ht5y"}])
        except Exception as e:
            print("Error updating Discord RPC thread: " + str(e))

        sleep(15)


def pretty_print(sender: str = "sys0",
                 msg: str = None,
                 state: str = "success"):
    """
    Produces nicely formatted CLI output for messages:
    HH:MM:S |sender| msg
    """
    if sender.startswith("net"):
        bg_color = Back.BLUE
    elif sender.startswith("avr"):
        bg_color = Back.MAGENTA
    else:
        bg_color = Back.GREEN

    if state == "success":
        fg_color = Fore.GREEN
    elif state == "info":
        fg_color = Fore.BLUE
    elif state == "error":
        fg_color = Fore.RED
    else:
        fg_color = Fore.YELLOW

    with thread_lock():
        printlock.acquire()
        print(Fore.WHITE + datetime.now().strftime(Style.DIM + "%H:%M:%S ")
              + bg_color + Style.BRIGHT + " " + sender + " "
              + Back.RESET + " " + fg_color + msg.strip())
        printlock.release()

def worker_print(com, **kwargs):

    text = ""
    for key in kwargs:
        text += "%s %s . " % (key, kwargs.get(key))
    with thread_lock():
        printlock.acquire()
        print(Fore.WHITE + datetime.now().strftime(Style.DIM + "%H:%M:%S ")
              + Fore.WHITE + Style.BRIGHT + Back.MAGENTA + Fore.RESET
              + " avr" + port_num(com) + " " + Back.RESET + " "
              + "worker capability report -> "
              + text)
        printlock.release()

def share_print(id, type, accept, reject, thread_hashrate,
                total_hashrate, computetime, diff, ping, reject_cause=None, iot_data=None):
    """
    Produces nicely formatted CLI output for shares:
    HH:MM:S |avrN| ⛏ Accepted 0/0 (100%) ∙ 0.0s ∙ 0 kH/s ⚙ diff 0 k ∙ ping 0ms
    """
    try:
        thread_hashrate = get_prefix("H/s", thread_hashrate, 2)
    except:
        thread_hashrate = "? H/s"

    try:
        total_hashrate = get_prefix("H/s", total_hashrate, 2)
    except:
        total_hashrate = "? H/s"

    if type == "accept":
        share_str = get_string("accepted")
        fg_color = Fore.GREEN
    elif type == "block":
        share_str = get_string("block_found")
        fg_color = Fore.YELLOW
    else:
        share_str = get_string("rejected")
        if reject_cause:
            share_str += f"{Style.NORMAL}({reject_cause}) "
        fg_color = Fore.RED

    iot_text = ""
    if iot_data:
        (temperature, humidity) = iot_data.split("@")
        iot_text = f"{temperature}° . "

    with thread_lock():
        printlock.acquire()
        print(Fore.WHITE + datetime.now().strftime(Style.DIM + "%H:%M:%S ")
              + Style.RESET_ALL + Fore.WHITE + Style.BRIGHT + Back.MAGENTA
              + " avr" + str(id) + " " + Style.RESET_ALL + fg_color 
              + Settings.PICK + share_str + Fore.RESET
              + str(accept) + "/" + str(accept + reject) + Fore.MAGENTA
              + " (" + str(round(accept / (accept + reject) * 100)) + "%)"
              + Style.NORMAL + Fore.RESET
              + " ∙ " + str("%04.1f" % float(computetime)) + "s"
              + Style.NORMAL + " ∙ " + Fore.BLUE + Style.BRIGHT
              + f"{thread_hashrate}" + Style.DIM
              + f" ({total_hashrate} {get_string('hashrate_total')})" + Fore.RESET + Style.NORMAL
              + Settings.COG + f" {get_string('diff')} {diff} ∙ "
              + f"{iot_text}" + Fore.CYAN
              + f"ping {(int(ping))}ms")
        printlock.release()

def flush_i2c(i2c_bus,com,period=1):
    i2c_flush_start = time()
    with thread_lock():
        while True:
            i2c_read(i2c_bus, com)
        
            if (time() - i2c_flush_start) > period:
                break

def i2c_write(i2c_bus, com, i2c_data, wr_rddcy=-1):

    if wr_rddcy == -1:
        wr_rddcy = Settings.I2C_WR_RDDCY
    debug_output(com + f': i2c_wdata=[{i2c_data}]')
    
    with thread_lock():
        try:
            i2clock.acquire()
            for i in range(0, len(i2c_data)):
                if wr_rddcy == 1:
                    # write single byte i2c data
                    i2c_bus.write_byte(int(com, base=16), 
                                       ord(i2c_data[i]))
                elif wr_rddcy > 1:
                    # write repeated i2c data
                    # help the i2cs to get the msg
                    i2c_bus.write_i2c_block_data(int(com, base=16),
                                                 ord(i2c_data[i]),
                                                 [ord(i2c_data[i])]*(wr_rddcy-1))
                sleep(0.0002)
        except Exception as e:
            debug_output(com + f': {e}')
            pass
        finally:
            i2clock.release()

def i2c_read(i2c_bus, com):
    
    i2c_rdata = ""
    with thread_lock():
        try:
            i2clock.acquire()
            i2c_rdata = chr(i2c_bus.read_byte(int(com, base=16)))
        except Exception as e:
            debug_output(com + f': {e}')
            pass
        finally:
            i2clock.release()

    return i2c_rdata

def get_temperature(i2c_bus,com):
    i2c_cmd = "get,temp$"
    i2c_resp = "0.00"
    start_time = time()

    try:
        i2c_write(i2c_bus, com, i2c_cmd)

        i2c_resp = ""
        while True:
            i2c_rdata = i2c_read(i2c_bus, com)

            if (i2c_rdata.isalnum() or ('.' in i2c_rdata)):
                i2c_resp += i2c_rdata.strip()

            if ('\n' in i2c_rdata) and (len(i2c_resp)>0):
                break

            if (time() - start_time) > 1:
                i2c_resp = "0.00"
                break
    except Exception as e:
        debug_output(com + f': {e}')
        pass

    #debug_output(com + f': i2c_resp:[{i2c_resp}]')
    return i2c_resp

def get_humidity(i2c_bus,com):
    # place holder
    return "0.00"

def get_worker_i2cfreq(i2c_bus,com):
    i2c_cmd = "get,freq$"
    default_answer = "0"
    return send_worker_cmd(i2c_bus,com,i2c_cmd,default_answer)

def send_worker_cmd(i2c_bus,com,cmd,default):
    i2c_resp = default
    start_time = time()
    try:
        i2c_write(i2c_bus, com, cmd)

        i2c_resp = ""
        while True:
            i2c_rdata = i2c_read(i2c_bus, com)

            if (i2c_rdata.isalnum()):
                i2c_resp += i2c_rdata.strip()

            if ('\n' in i2c_rdata) and (len(i2c_resp)>0):
                break

            # shouldn't take more than 1s to get response
            if (time() - start_time) > 1:
                i2c_resp = "0"
                break
    except Exception as e:
        debug_output(com + f': {e}')
        pass

    #debug_output(com + f': i2c_resp:[{i2c_resp}]')
    try:
        i2c_resp = int(i2c_resp)
    except ValueError:
        pass
    return i2c_resp


def get_worker_crc8_status(i2c_bus,com):
    i2c_cmd = "get,crc8$"
    default_answer = "1"

    return send_worker_cmd(i2c_bus,com,i2c_cmd,default_answer)

def get_worker_baton_status(i2c_bus,com):
    i2c_cmd = "get,baton$"
    default_answer = "1"

    return send_worker_cmd(i2c_bus,com,i2c_cmd,default_answer)

def get_worker_core_status(i2c_bus,com):
    i2c_cmd = "get,singlecore$"
    default_answer = "0"

    return send_worker_cmd(i2c_bus,com,i2c_cmd,default_answer)

def get_worker_name(i2c_bus,com):
    i2c_cmd = "get,name$"
    default_answer = "unkn"

    return send_worker_cmd(i2c_bus,com,i2c_cmd,default_answer)

def crc8(data):
    crc = 0
    for i in range(len(data)):
        byte = data[i]
        for b in range(8):
            fb_bit = (crc ^ byte) & 0x01
            if fb_bit == 0x01:
                crc = crc ^ 0x18
            crc = (crc >> 1) & 0x7f
            if fb_bit == 0x01:
                crc = crc | 0x80
            byte = byte >> 1
    return crc

def is_subscript(c):
    if c.isdigit():
        try:
            int(c)
        except ValueError:
            return True
    return False

def debouncer(fname, i2c_bus, com):
    count=0
    max_retry=10
    while count < max_retry:
        result = eval(fname+'(i2c_bus,com)')
        sleep(0.2)
        _result = eval(fname+'(i2c_bus,com)')
        if result == _result:
            break
        sleep(0.2)
        count += 1
    return result

def get_worker_cfg_global(i2c_bus, com):
    worker_cfg_global["i2c_freq"] = get_worker_i2cfreq(i2c_bus, com)
    worker_cfg_global["crc8_en"] = debouncer("get_worker_crc8_status", i2c_bus, com)
    sensor_en = get_temperature(i2c_bus, com)
    worker_cfg_global["sensor_en"] = 1 if sensor_en != "0" else 0
    worker_cfg_global["baton_status"] = get_worker_baton_status(i2c_bus, com)
    worker_cfg_global["single_core_only"] = get_worker_core_status(i2c_bus, com)
    worker_cfg_global["worker_name"] = get_worker_name(i2c_bus, com)
    worker_cfg_global["valid"] = True

def mine_avr(com, threadid, fastest_pool, thread_rigid):
    global hashrate
    global bad_crc8
    global i2c_retry_count
    global hashrate_mean
    start_time = time()
    report_shares = 0
    last_report_share = 0
    last_bad_crc8 = 0
    last_i2c_retry_count = 0
    wr_rddcy = Settings.I2C_WR_RDDCY
    avr_timeout = Settings.AVR_TIMEOUT
    iot_data = None
    crc8_en = 1
    user_iot = Settings.IoT_EN
    ducoid = ""
    worker_type = "avr"
    worker_cfg_shared = True if Settings.WORKER_CFG_SHARED == "y" else False

    flush_i2c(i2c_bus, com)

    while worker_cfg_global["valid"] is not True and worker_cfg_shared:
        sleep(1)
    
    if worker_cfg_shared:
        i2c_freq = worker_cfg_global["i2c_freq"]
        crc8_en = worker_cfg_global["crc8_en"]
        sensor_en = worker_cfg_global["sensor_en"]
        baton_status = worker_cfg_global["baton_status"]
        single_core_only = worker_cfg_global["single_core_only"]
        worker_name = worker_cfg_global["worker_name"]
    else:
        i2c_freq = get_worker_i2cfreq(i2c_bus, com)
        crc8_en = debouncer("get_worker_crc8_status", i2c_bus, com)
        sensor_en = get_temperature(i2c_bus, com)
        sensor_en = 1 if sensor_en != "0" else 0
        baton_status = get_worker_baton_status(i2c_bus, com)
        single_core_only = get_worker_core_status(i2c_bus, com)
        worker_name = get_worker_name(i2c_bus, com)

    worker_print(com, i2c_clock=i2c_freq, crc8_en=crc8_en, 
                sensor_en=sensor_en, baton_status=baton_status,
                single_core_only=single_core_only, worker_name=worker_name, 
                shared_worker_cfg=str(worker_cfg_shared))

    if sensor_en == 0 and "y" in user_iot.lower():
        user_iot = "n"
        pretty_print("sys" + port_num(com), " worker do not have sensor enabled. Disabling IoT reporting", "warning")
    
    while True:
        
        retry_counter = 0
        while True:
            try:
                if retry_counter > 3:
                    fastest_pool = Client.fetch_pool()
                    retry_counter = 0

                debug_output(f'Connecting to {fastest_pool}')
                s = Client.connect(fastest_pool)
                server_version = Client.recv(s, 6)

                if threadid == 0:
                    if float(server_version) <= float(Settings.VER):
                        pretty_print(
                            'net0', get_string('connected')
                            + Style.NORMAL + Fore.RESET
                            + get_string('connected_server')
                            + str(server_version) + ")",
                            'success')
                    else:
                        pretty_print(
                            'sys0', f"{get_string('miner_is_outdated')} (v{Settings.VER}) -"
                            + get_string('server_is_on_version')
                            + server_version + Style.NORMAL
                            + Fore.RESET + get_string('update_warning'),
                            'warning')
                        sleep(10)

                    Client.send(s, "MOTD")
                    motd = Client.recv(s, 1024)

                    if "\n" in motd:
                        motd = motd.replace("\n", "\n\t\t")

                    pretty_print("net" + str(threadid),
                                 get_string("motd") + Fore.RESET
                                 + Style.NORMAL + str(motd),
                                 "success")
                break
            except Exception as e:
                pretty_print('net0', get_string('connecting_error')
                             + Style.NORMAL + f' (connection err: {e})',
                             'error')
                retry_counter += 1
                sleep(10)

        pretty_print('sys' + port_num(com),
                     get_string('mining_start') + Style.NORMAL + Fore.RESET
                     + get_string('mining_algorithm') + str(com) + ')',
                     'success')

        flush_i2c(i2c_bus,com)
                
        while True:
            try:
            
                if config["AVR Miner"]["mining_key"] != "None":
                    key = b64.b64decode(config["AVR Miner"]["mining_key"]).decode('utf-8')
                else:
                    key = config["AVR Miner"]["mining_key"]
                    
                debug_output(com + ': Requesting job')
                job_request  = 'JOB'
                job_request += Settings.SEPARATOR
                job_request += str(username)
                job_request += Settings.SEPARATOR
                job_request += 'AVR'
                job_request += Settings.SEPARATOR
                job_request += str(key)

                if sensor_en and user_iot == "y":
                    job_request += Settings.SEPARATOR
                    iot_data  = get_temperature(i2c_bus,com)
                    iot_data += "@"
                    iot_data += get_humidity(i2c_bus,com)
                    job_request += iot_data

                debug_output(com + f": {job_request}") 
                
                Client.send(s, job_request)
                job = Client.recv(s, 128).split(Settings.SEPARATOR)
                debug_output(com + f": Received: {job[0]}")

                try:
                    diff = int(job[2])
                except:
                    pretty_print("sys" + port_num(com),
                                 f" Node message: {job[1]}", "warning")
                    sleep(3)
            except Exception as e:
                pretty_print('net' + port_num(com),
                             get_string('connecting_error')
                             + Style.NORMAL + Fore.RESET
                             + f' (err handling result: {e})', 'error')
                sleep(3)
                break

            retry_counter = 0
            while True:
                if retry_counter > 3:
                    flush_i2c(i2c_bus,com)
                    break

                try:
                    debug_output(com + ': Sending job to the board')
                    i2c_data = str(job[0]
                                    + Settings.SEPARATOR
                                    + job[1]
                                    + Settings.SEPARATOR
                                    + job[2])
                                    
                    if crc8_en :
                        i2c_data += Settings.SEPARATOR
                        i2c_data = str(i2c_data + str(crc8(i2c_data.encode())) + '\n')
                        debug_output(com + f': Job+crc8: {i2c_data}')
                    else:
                        i2c_data = str(i2c_data + '\n')
                        debug_output(com + f': Job: {i2c_data}')
                        
                    i2c_write(i2c_bus, com, i2c_data, wr_rddcy)
                    debug_output(com + ': Reading result from the board')
                    i2c_responses = ''
                    i2c_rdata = ''
                    substitute = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹","0123456789")
                    result = []
                    i2c_start_time = time()
                    sleep_en = True
                    while True:
                        i2c_rdata = i2c_read(i2c_bus, com)

                        if is_subscript(i2c_rdata):
                            # rare incident where MSB bit flipped
                            i2c_rdata = i2c_rdata.translate(substitute)
                            
                        if ('$' in i2c_rdata):
                            # worker cmd overflow into response area. dump it
                            i2c_responses = ''
                            
                        if ((i2c_rdata.isalnum()) or (',' in i2c_rdata)):
                            sleep_en = False
                            i2c_responses += i2c_rdata.strip()
                            
                        elif ('#' in i2c_rdata):
                            # i2cs received corrupted job
                            debug_output(com + f': Received response: {i2c_responses}')
                            debug_output(com + f': Retry Job: {job}')
                            debug_output(com + f': retransmission requested')
                            if wr_rddcy < 32:
                                if worker_type == "others": 
                                    wr_rddcy += 1
                                    debug_output(com + f': increment write redundancy bytes to {wr_rddcy}')
                            else:
                                debug_output(com + f': write redundancy maxed out at {wr_rddcy}')
                            raise Exception("I2C job corrupted")
                            
                        if sleep_en:
                            # pool less when worker is busy
                            # feel free to play around this number to find sweet spot for shares/s vs. stability
                            sleep(0.05)
                            
                        result = i2c_responses.split(',')
                        if (((len(result)==4 and crc8_en) or 
                            (len(result)==3 and not crc8_en)) and 
                            ('\n' in i2c_rdata)):
                            debug_output(com + " i2c_responses:" + f'{i2c_responses}')
                            break
                        
                        if (time() - i2c_start_time) > avr_timeout:
                            debug_output(com + f' I2C timed out after {avr_timeout}s')
                            raise Exception("I2C timed out")

                    if result[0] and result[1]:
                        _ = int(result[0])
                        if not _:
                            debug_output(com + ' Invalid result')
                            raise Exception("Invalid result")
                        _ = int(result[1])
                        if not result[2].isalnum() and len(ducoid) == 0:
                            debug_output(com + ' Corrupted DUCOID')
                            raise Exception("Corrupted DUCOID")
                        if not result[2].isalnum() and len(ducoid) > 0:
                            # ducoid corrupted
                            # use ducoid from previous response
                            result[2] = ducoid
                            # reconstruct i2c_responses
                            i2c_responses = str(result[0]
                                                + Settings.SEPARATOR
                                                + result[1]
                                                + Settings.SEPARATOR
                                                + result[2])
                        if int(crc8_en):
                            _resp = i2c_responses.rpartition(Settings.SEPARATOR)[0]+Settings.SEPARATOR
                            result_crc8 = crc8(_resp.encode())
                            if (int(result[3]) != result_crc8):
                                bad_crc8 += 1
                                debug_output(com + f': crc8:: expect:{result_crc8} measured:{result[3]}')
                                raise Exception("crc8 checksum failed")
                        break
                    else:
                        raise Exception("No data received from AVR")
                except Exception as e:
                    debug_output(com + f': Retrying data read: {e}')
                    retry_counter += 1
                    i2c_retry_count += 1
                    flush_i2c(i2c_bus,com,1)
                    continue

            try:
                computetime = round(int(result[1]) / 1000000, 5)
                num_res = int(result[0])
                hashrate_t = round(num_res / computetime, 2)

                # experimental: guess worker type. seems like larger wr_rddcy causes more harm than good on avr
                if hashrate_t < 400:
                    worker_type = "avr"
                    wr_rddcy = 1
                else:
                    worker_type = "others"

                _avr_timeout = int(((int(diff) * 100) / int(hashrate_t)) * 2)
                if _avr_timeout > avr_timeout:
                    debug_output(com + f': changing avr_timeout from {avr_timeout}s to {_avr_timeout}s')
                    avr_timeout = _avr_timeout

                hashrate_mean.append(hashrate_t)
                hashrate = mean(hashrate_mean)
                hashrate_list[threadid] = hashrate
                total_hashrate = sum(hashrate_list)
            except Exception as e:
                pretty_print('sys' + port_num(com),
                             get_string('mining_avr_connection_error')
                             + Style.NORMAL + Fore.RESET
                             + ' (no response from the board: '
                             + f'{e}, please check the connection, '
                             + 'port setting or reset the AVR)', 'warning')
                debug_output(com + f': Retry count: {retry_counter}')
                debug_output(com + f': Job: {job}')
                debug_output(com + f': Result: {result}')
                flush_i2c(i2c_bus,com)
                break
            ducoid = result[2]

            try:
                Client.send(s, str(num_res)
                            + Settings.SEPARATOR
                            + str(hashrate_t)
                            + Settings.SEPARATOR
                            + f'RPI I2C AVR Miner {Settings.VER}'
                            + Settings.SEPARATOR
                            + str(thread_rigid)
                            #+ str(port_num(com))
                            + Settings.SEPARATOR
                            + str(result[2]))

                responsetimetart = now()
                feedback = Client.recv(s, 64).split(",")
                responsetimestop = now()

                time_delta = (responsetimestop -
                              responsetimetart).microseconds
                ping_mean.append(round(time_delta / 1000))
                ping = mean(ping_mean)
                diff = get_prefix("", int(diff), 0)
                debug_output(com + f': retrieved feedback: {" ".join(feedback)}')
            except Exception as e:
                pretty_print('net' + port_num(com),
                             get_string('connecting_error')
                             + Style.NORMAL + Fore.RESET
                             + f' (err handling result: {e})', 'error')
                debug_output(com + f': error parsing response: {e}')
                sleep(5)
                break

            if feedback[0] == 'GOOD':
                shares[0] += 1
                share_print(port_num(com), "accept",
                            shares[0], shares[1], hashrate, total_hashrate,
                            computetime, diff, ping, None, iot_data)
            elif feedback[0] == 'BLOCK':
                shares[0] += 1
                shares[2] += 1
                share_print(port_num(com), "block",
                            shares[0], shares[1], hashrate, total_hashrate,
                            computetime, diff, ping, None, iot_data)
            elif feedback[0] == 'BAD':
                shares[1] += 1
                reason = feedback[1] if len(feedback) > 1 else None
                share_print(port_num(com), "reject",
                            shares[0], shares[1], hashrate_t, total_hashrate,
                            computetime, diff, ping, reason, iot_data)
            else:
                shares[1] += 1
                share_print(port_num(com), "reject",
                            shares[0], shares[1], hashrate_t, total_hashrate,
                            computetime, diff, ping, feedback, iot_data)
                debug_output(com + f': Job: {job}')
                debug_output(com + f': Result: {result}')
                flush_i2c(i2c_bus,com,5)
                
            if shares[0] % 100 == 0 and shares[0] > 1:
                pretty_print("sys0",
                            f"{get_string('surpassed')} {shares[0]} {get_string('surpassed_shares')}",
                            "success")

            title(get_string('duco_avr_miner') + str(Settings.VER)
                  + f') - {shares[0]}/{(shares[0] + shares[1])}'
                  + get_string('accepted_shares'))

            end_time = time()
            elapsed_time = end_time - start_time
            if threadid == 0 and elapsed_time >= Settings.REPORT_TIME:
                report_shares = shares[0] - last_report_share
                report_bad_crc8 = bad_crc8 - last_bad_crc8
                report_i2c_retry_count = i2c_retry_count - last_i2c_retry_count
                uptime = calculate_uptime(mining_start_time)
                pretty_print("net" + str(threadid),
                                 " POOL_INFO: " + Fore.RESET
                                 + Style.NORMAL + str(motd),
                                 "success")
                periodic_report(start_time, end_time, report_shares,
                                shares[2], hashrate, uptime, 
                                report_bad_crc8, report_i2c_retry_count)
                
                start_time = time()
                last_report_share = shares[0]
                last_bad_crc8 = bad_crc8
                last_i2c_retry_count = i2c_retry_count


def periodic_report(start_time, end_time, shares,
                    block, hashrate, uptime, bad_crc8, i2c_retry_count):
    seconds = round(end_time - start_time)
    pretty_print("sys0",
                 " " + get_string('periodic_mining_report')
                 + Fore.RESET + Style.NORMAL
                 + get_string('report_period')
                 + str(seconds) + get_string('report_time')
                 + get_string('report_body1')
                 + str(shares) + get_string('report_body2')
                 + str(round(shares/seconds, 1))
                 + get_string('report_body3')
                 + get_string('report_body7') + str(block)
                 + get_string('report_body4')
                 + str(int(hashrate)) + " H/s" + get_string('report_body5')
                 + str(int(hashrate*seconds)) + get_string('report_body6')
                 + get_string('total_mining_time') + str(uptime)
                 + "\n\t\t‖ CRC8 Error Rate: " + str(round(bad_crc8/seconds, 6)) + " E/s"
                 + "\n\t\t‖ I2C Retry Rate: " + str(round(i2c_retry_count/seconds, 6)) + " R/s", "success")


def calculate_uptime(start_time):
    uptime = time() - start_time
    if uptime >= 7200: # 2 hours, plural
        return str(uptime // 3600) + get_string('uptime_hours')
    elif uptime >= 3600: # 1 hour, not plural
        return str(uptime // 3600) + get_string('uptime_hour')
    elif uptime >= 120: # 2 minutes, plural
        return str(uptime // 60) + get_string('uptime_minutes')
    elif uptime >= 60: # 1 minute, not plural
        return str(uptime // 60) + get_string('uptime_minute')
    else: # less than 1 minute
        return str(round(uptime)) + get_string('uptime_seconds')


if __name__ == '__main__':
    init(autoreset=True)
    title(f"{get_string('duco_avr_miner')}{str(Settings.VER)})")

    if sys.platform == "win32":
        os.system('') # Enable VT100 Escape Sequence for WINDOWS 10 Ver. 1607
        
    try:
        load_config()
        debug_output('Config file loaded')
    except Exception as e:
        pretty_print(
            'sys0', get_string('load_config_error')
            + Settings.DATA_DIR + get_string('load_config_error_warning')
            + Style.NORMAL + Fore.RESET + f' ({e})', 'error')
        debug_output(f'Error reading configfile: {e}')
        sleep(10)
        _exit(1)

    try:
        greeting()
        debug_output('Greeting displayed')
    except Exception as e:
        debug_output(f'Error displaying greeting message: {e}')

    try:
        check_mining_key(config)
    except Exception as e:
        debug_output(f'Error checking miner key: {e}')
        
    if donation_level > 0:
        try:
            Donate.load(donation_level)
            Donate.start(donation_level)
        except Exception as e:
            debug_output(f'Error launching donation thread: {e}')

    try:
        i2c_bus = SMBus(i2c)
        fastest_pool = Client.fetch_pool()
        threadid = 0
        if Settings.WORKER_CFG_SHARED == "y":
            for port in avrport:
                get_worker_cfg_global(i2c_bus,port)
                if worker_cfg_global["valid"]: break
        for port in avrport:
            Thread(target=mine_avr,
                   args=(port, threadid,
                         fastest_pool, rig_identifier[threadid])).start()
            threadid += 1
            if ((len(avrport) > 1) and (threadid != len(avrport))):
                pretty_print('sys' + str(threadid),
                                f" Started {threadid}/{len(avrport)} worker(s). Next I2C AVR Miner starts in "
                                + str(Settings.DELAY_START)
                                + "s",
                                "success")
                sleep(Settings.DELAY_START)
            else:
                pretty_print('sys' + str(threadid),
                                f" All {threadid}/{len(avrport)} worker(s) started",
                                "success")
    except Exception as e:
        debug_output(f'Error launching AVR thread(s): {e}')

    if discord_presence == "y":
        try:
            init_rich_presence()
        except Exception as e:
            debug_output(f'Error launching Discord RPC thread: {e}')
            
