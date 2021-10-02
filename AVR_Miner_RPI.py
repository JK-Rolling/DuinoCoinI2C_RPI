#!/usr/bin/env python3
"""
RPI I2C AVR Miner
Modified by JK-Rolling
20210919

Full credit belong to
https://duinocoin.com
https://github.com/revoxhere/duino-coin
Duino-Coin Team & Community 2019-2021
"""

from os import _exit, execl, mkdir
from os import name as osname
from os import path
from os import system as ossystem
from platform import machine as osprocessor
from platform import system
import sys

from configparser import ConfigParser
from pathlib import Path

from json import load as jsonload
from locale import LC_ALL, getdefaultlocale, getlocale, setlocale

from re import sub
from socket import socket
from datetime import datetime
from statistics import mean
from signal import SIGINT, signal
from time import ctime, sleep, strptime, time
from random import choice
import select
import pip

from subprocess import DEVNULL, Popen, check_call, call
from threading import Thread as thrThread
from threading import Lock as thread_lock


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
    return com


class Settings:
    VER = '2.73'
    SOC_TIMEOUT = 45
    REPORT_TIME = 60
    AVR_TIMEOUT = 4  # diff 6 * 100 / 196 h/s = 3.06
    DATA_DIR = "Duino-Coin AVR Miner " + str(VER)
    SEPARATOR = ","
    ENCODING = "utf-8"
    BLOCK = "  "
    PICK = ""
    COG = " @"
    if osname != "nt":
        # Windows' cmd does not support emojis, shame!
        PICK = " "
        COG = " "


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
                         "warning")
            try:
                response = requests.get(
                    "https://server.duinocoin.com/getPool").json()
                if response["success"] == True:
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
                pretty_print("net0",
                             f"Error fetching mining node: {e}"
                             + ", retrying in 15s", "error")
                sleep(15)


class Donate:
    def load(donation_level):
        if donation_level > 0:
            if osname == 'nt':
                if not Path(
                        f"{Settings.DATA_DIR}/Donate.exe").is_file():
                    url = ('https://server.duinocoin.com/'
                           + 'donations/DonateExecutableWindows.exe')
                    r = requests.get(url)
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
                    r = requests.get(url)
                    with open(f"{Settings.DATA_DIR}/Donate",
                              "wb") as f:
                        f.write(r.content)

    def start(donation_level):
        if osname == 'nt':
            cmd = (f'cd "{Settings.DATA_DIR}" & Donate.exe '
                   + '-o stratum+tcp://xmg.minerclaim.net:3333 '
                   + f'-u revox.donate -p x -s 4 -e {donation_level*5}')
        elif osname == 'posix':
            cmd = (f'cd "{Settings.DATA_DIR}" && chmod +x Donate '
                   + '&& nice -20 ./Donate -o '
                   + 'stratum+tcp://xmg.minerclaim.net:3333 '
                   + f'-u revox.donate -p x -s 4 -e {donation_level*5}')

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
                         'warning')


shares = [0, 0, 0]
hashrate_mean = []
ping_mean = []
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

if not path.exists(Settings.DATA_DIR):
    mkdir(Settings.DATA_DIR)

if not Path(Settings.DATA_DIR + '/Translations.json').is_file():
    url = ('https://raw.githubusercontent.com/'
           + 'revoxhere/'
           + 'duino-coin/master/Resources/'
           + 'AVR_Miner_langs.json')
    r = requests.get(url)
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
        elif locale.startswith('fr'):
            lang = 'french'
        elif locale.startswith('tr'):
            lang = 'turkish'
        elif locale.startswith('pt'):
            lang = 'portuguese'
        elif locale.startswith('zh'):
            lang = 'chinese_simplified'
        elif locale.startswith('th'):
            lang = 'thai'
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
        return ' String not found: ' + string_name


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
        print('\33]0;' + title + '\a', end='')
        sys.stdout.flush()


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

        username = input(
            Style.RESET_ALL + Fore.YELLOW
            + get_string('ask_username')
            + Fore.RESET + Style.BRIGHT)
            
        i2c = input(
            Style.RESET_ALL + Fore.YELLOW
            + 'Enter your choice of I2C bus (e.g. 1): '
            + Fore.RESET + Style.BRIGHT)
        i2c = int(i2c)

        if ossystem(f'i2cdetect -y {i2c}') != 0:
            print(Style.RESET_ALL + Fore.RED
                    + 'I2C is disabled. Exiting..')
        else :
            print(Style.RESET_ALL + Fore.YELLOW
                + 'i2cdetect has found I2C addresses above')
                
        avrport = ''
        while True:
            current_port = input(
                Style.RESET_ALL + Fore.YELLOW
                + 'Enter your I2C slave address (e.g. 3): '
                + Fore.RESET + Style.BRIGHT)

            avrport += current_port
            confirmation = input(
                Style.RESET_ALL + Fore.YELLOW
                + get_string('ask_anotherport')
                + Fore.RESET + Style.BRIGHT)

            if confirmation == 'y' or confirmation == 'Y':
                avrport += ','
            else:
                break
                

        rig_identifier = input(
            Style.RESET_ALL + Fore.YELLOW
            + get_string('ask_rig_identifier')
            + Fore.RESET + Style.BRIGHT)
        if rig_identifier == 'y' or rig_identifier == 'Y':
            rig_identifier = input(
                Style.RESET_ALL + Fore.YELLOW
                + get_string('ask_rig_name')
                + Fore.RESET + Style.BRIGHT)
        else:
            rig_identifier = 'None'

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
            "avr_timeout":      10,
            "discord_presence": "y",
            "periodic_report":  60,
            "shuffle_ports":    "y",
            "i2c":              i2c}

        with open(str(Settings.DATA_DIR)
                  + '/Settings.cfg', 'w') as configfile:
            config.write(configfile)

        avrport = avrport.split(',')
        print(Style.RESET_ALL + get_string('config_saved'))

    else:
        config.read(str(Settings.DATA_DIR) + '/Settings.cfg')
        username = config["AVR Miner"]['username']
        avrport = config["AVR Miner"]['avrport']
        avrport = avrport.replace(" ", "").split(',')
        donation_level = int(config["AVR Miner"]['donate'])
        debug = config["AVR Miner"]['debug']
        rig_identifier = config["AVR Miner"]['identifier']
        Settings.SOC_TIMEOUT = int(config["AVR Miner"]["soc_timeout"])
        Settings.AVR_TIMEOUT = float(config["AVR Miner"]["avr_timeout"])
        discord_presence = config["AVR Miner"]["discord_presence"]
        shuffle_ports = config["AVR Miner"]["shuffle_ports"]
        Settings.REPORT_TIME = int(config["AVR Miner"]["periodic_report"])
        i2c = int(config["AVR Miner"]["i2c"])


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
        + Style.BRIGHT + '\n  Unofficial Duino-Coin RPI I2C  AVR Miner'
        + Style.RESET_ALL + Fore.MAGENTA
        + f' {Settings.VER}' + Fore.RESET
        + ' 2021')

    print(
        Style.DIM + Fore.MAGENTA
        + Settings.BLOCK + Style.NORMAL + Fore.MAGENTA
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
        + ' '.join(avrport))

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
        + 'DUCO-S1A  AVR diff')

    if rig_identifier != "None":
        print(
            Style.DIM + Fore.MAGENTA
            + Settings.BLOCK + Style.NORMAL
            + Fore.RESET + get_string('rig_identifier')
            + Style.BRIGHT + Fore.YELLOW + rig_identifier)

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
        RPC = Presence(808045598447632384)
        RPC.connect()
        Thread(target=Discord_rp.update).start()
    except Exception as e:
        #print("Error launching Discord RPC thread: " + str(e))
        pass


def update_rich_presence():
    startTime = int(time())
    while True:
        try:
            total_hashrate = get_prefix("H/s", sum(hashrate.values()), 2)
            RPC.update(details="Hashrate: " + str(total_hashrate),
                       start=mining_start_time,
                       state=str(accept.value) + "/"
                       + str(reject.value + accept.value)
                       + " accepted shares",
                       large_image="ducol",
                       large_text="Duino-Coin, "
                       + "a coin that can be mined with almost everything"
                       + ", including AVR boards",
                       buttons=[{"label": "Visit duinocoin.com",
                                 "url": "https://duinocoin.com"},
                                {"label": "Join the Discord",
                                 "url": "https://discord.gg/k48Ht5y"}])
        except Exception as e:
            #print("Error updating Discord RPC thread: " + str(e))
            pass
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
    elif sender.startswith("sys"):
        bg_color = Back.GREEN

    if state == "success":
        fg_color = Fore.GREEN
    elif state == "error":
        fg_color = Fore.RED
    else:
        fg_color = Fore.YELLOW

    with thread_lock():
        print(Fore.WHITE + datetime.now().strftime(Style.DIM + "%H:%M:%S ")
              + bg_color + Style.BRIGHT + " " + sender + " "
              + Back.RESET + " " + fg_color + msg.strip())


def share_print(id, type, accept, reject, total_hashrate,
                computetime, diff, ping):
    """
    Produces nicely formatted CLI output for shares:
    HH:MM:S |avrN|  Accepted 0/0 (100%)  0.0s  0 kH/s  diff 0 k  ping 0ms
    """
    try:
        diff = get_prefix("", int(diff), 0)
    except:
        diff = "?"

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
        fg_color = Fore.RED

    with thread_lock():
        print(Fore.WHITE + datetime.now().strftime(Style.DIM + "%H:%M:%S ")
              + Fore.WHITE + Style.BRIGHT + Back.MAGENTA + Fore.RESET
              + " avr" + str(id) + " " + Back.RESET
              + fg_color + Settings.PICK + share_str + Fore.RESET
              + str(accept) + "/" + str(accept + reject) + Fore.YELLOW
              + " (" + str(round(accept / (accept + reject) * 100)) + "%)"
              + Style.NORMAL + Fore.RESET
              + "  " + str("%04.1f" % float(computetime)) + "s"
              + Style.NORMAL + "  " + Fore.BLUE + Style.BRIGHT
              + str(total_hashrate) + Fore.RESET + Style.NORMAL
              + Settings.COG + f" diff {diff}  " + Fore.CYAN
              + f"ping {(int(ping))}ms")

def flush_i2c(i2c_bus,com,period=2):
    i2c_flush_start = time()
    with thread_lock():
        while True:
            try:
                i2c_bus.read_byte(int(com, base=16))
            except:
                pass
            
            i2c_flush_end = time()
            if (i2c_flush_end - i2c_flush_start) > period:
                break

def mine_avr(com, threadid, fastest_pool):
    global hashrate
    start_time = time()
    report_shares = 0
    last_report_share = 0
    
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
                            'sys0', f' Miner is outdated (v{Settings.VER}) -'
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
                                 " MOTD: " + Fore.RESET
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
                debug_output(com + ': Requesting job')
                Client.send(s, 'JOB'
                            + Settings.SEPARATOR
                            + str(username)
                            + Settings.SEPARATOR
                            + 'AVR')
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
                if retry_counter > 10:
                    flush_i2c(i2c_bus,com)
                    break

                try:
                    debug_output(com + ': Sending job to the board')
                    i2c_data = str(job[0]
                                    + Settings.SEPARATOR
                                    + job[1]
                                    + Settings.SEPARATOR
                                    + job[2]
                                    + Settings.SEPARATOR
                                    + '\n')
                                    
                    with thread_lock():
                        for i in range(0, len(i2c_data)):
                            i2c_bus.write_byte(int(com, base=16),ord(i2c_data[i]))
                    debug_output(com + ': Reading result from the board')
                    i2c_responses = ''
                    result = []
                    i2c_start_time = time()
                    while True:
                        with thread_lock():
                            i2c_rdata = chr(i2c_bus.read_byte(int(com, base=16)))
                        if ((i2c_rdata.isalnum()) or (',' in i2c_rdata)):
                            i2c_responses += i2c_rdata.strip()
                        elif ('#' in i2c_rdata):
                            flush_i2c(i2c_bus,com)
                            debug_output(com + f': Retry Job: {job}')
                            raise Exception("I2C data corrupted")
                        else:
                            sleep(0.01)
                            
                        result = i2c_responses.split(',')
                        if ((len(result)==3) and ('\n' in i2c_rdata)):
                            break
                            
                        i2c_end_time = time()
                        if (i2c_end_time - i2c_start_time) > Settings.AVR_TIMEOUT:
                            flush_i2c(i2c_bus,com)
                            raise Exception("I2C timed out")

                    if result[0] and result[1]:
                        _ = int(result[0])
                        if not _:
                            raise Exception("Invalid result")
                        _ = int(result[1])
                        if not result[2].isalnum():
                            raise Exception("Corrupted DUCOID")
                        debug_output(com + f': Result: {result}')
                        break
                    else:
                        raise Exception("No data received from AVR")
                except Exception as e:
                    debug_output(com + f': Retrying data read: {e}')
                    retry_counter += 1
                    continue

            try:
                computetime = round(int(result[1]) / 1000000, 3)
                num_res = int(result[0])
                hashrate_t = round(num_res / computetime, 2)

                hashrate_mean.append(hashrate_t)
                hashrate = mean(hashrate_mean[-5:])
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

            try:
                Client.send(s, str(num_res)
                            + Settings.SEPARATOR
                            + str(hashrate_t)
                            + Settings.SEPARATOR
                            + f'RPI I2C AVR Miner {Settings.VER}'
                            + Settings.SEPARATOR
                            + str(rig_identifier)
                            + str(port_num(com))
                            + Settings.SEPARATOR
                            + str(result[2]))

                responsetimetart = now()
                feedback = Client.recv(s, 64)
                responsetimestop = now()

                time_delta = (responsetimestop -
                              responsetimetart).microseconds
                ping_mean.append(round(time_delta / 1000))
                ping = mean(ping_mean[-10:])
                diff = get_prefix("", int(diff), 0)
                debug_output(com + f': retrieved feedback: {feedback}')
            except Exception as e:
                pretty_print('net' + port_num(com),
                             get_string('connecting_error')
                             + Style.NORMAL + Fore.RESET
                             + f' (err handling result: {e})', 'error')
                debug_output(com + f': error parsing response: {e}')
                sleep(5)
                break

            if feedback == 'GOOD':
                shares[0] += 1
                share_print(port_num(com), "accept",
                            shares[0], shares[1], hashrate,
                            computetime, diff, ping)
            elif feedback == 'BLOCK':
                shares[0] += 1
                shares[2] += 1
                share_print(port_num(com), "block",
                            shares[0], shares[1], hashrate,
                            computetime, diff, ping)
            else:
                shares[1] += 1
                share_print(port_num(com), "reject",
                            shares[0], shares[1], hashrate,
                            computetime, diff, ping)
                debug_output(com + f': Job: {job}')
                debug_output(com + f': Result: {result}')
                flush_i2c(i2c_bus,com,5)

            title(get_string('duco_avr_miner') + str(Settings.VER)
                  + f') - {shares[0]}/{(shares[0] + shares[1])}'
                  + get_string('accepted_shares'))

            end_time = time()
            elapsed_time = end_time - start_time
            if threadid == 0 and elapsed_time >= Settings.REPORT_TIME:
                report_shares = shares[0] - last_report_share
                uptime = calculate_uptime(mining_start_time)
                pretty_print("net" + str(threadid),
                                 " POOL_INFO: " + Fore.RESET
                                 + Style.NORMAL + str(motd),
                                 "success")
                periodic_report(start_time, end_time, report_shares,
                                shares[2], hashrate, uptime)
                
                start_time = time()
                last_report_share = shares[0]


def periodic_report(start_time, end_time, shares,
                    block, hashrate, uptime):
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
                 + "\n\t\t‖ Block found: " + str(block)
                 + get_string('report_body4')
                 + str(int(hashrate)) + " H/s" + get_string('report_body5')
                 + str(int(hashrate*seconds)) + get_string('report_body6')
                 + get_string('total_mining_time') + str(uptime), "success")


def calculate_uptime(start_time):
    uptime = time() - start_time
    if uptime <= 59:
        return str(round(uptime)) + get_string('uptime_seconds')
    elif uptime == 60:
        return str(round(uptime // 60)) + get_string('uptime_minute')
    elif uptime >= 60:
        return str(round(uptime // 60)) + get_string('uptime_minutes')
    elif uptime == 3600:
        return str(round(uptime // 3600)) + get_string('uptime_hour')
    elif uptime >= 3600:
        return str(round(uptime // 3600)) + get_string('uptime_hours')


if __name__ == '__main__':
    init(autoreset=True)
    title(f"{get_string('duco_avr_miner')}{str(Settings.VER)})")

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
        for port in avrport:
            thrThread(target=mine_avr,
                      args=(port, threadid,
                            fastest_pool)).start()
            threadid += 1
    except Exception as e:
        debug_output(f'Error launching AVR thread(s): {e}')

    if discord_presence == "y":
        try:
            init_rich_presence()
            thrThread(
                target=update_rich_presence).start()
        except Exception as e:
            debug_output(f'Error launching Discord RPC thread: {e}')
