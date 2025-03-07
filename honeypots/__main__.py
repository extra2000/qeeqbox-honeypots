#!/usr/bin/env python

import time

from warnings import filterwarnings
filterwarnings(action='ignore', module='.*OpenSSL.*')
filterwarnings('ignore', category=RuntimeWarning, module='runpy')

all_servers = ['QDNSServer', 'QFTPServer', 'QHTTPProxyServer', 'QHTTPServer', 'QHTTPSServer', 'QIMAPServer', 'QMysqlServer', 'QPOP3Server', 'QPostgresServer', 'QRedisServer', 'QSMBServer', 'QSMTPServer', 'QSOCKS5Server', 'QSSHServer', 'QTelnetServer', 'QVNCServer', 'QElasticServer', 'QMSSQLServer', 'QLDAPServer']
temp_honeypots = []


from signal import signal, alarm, SIGALRM, SIG_IGN
from functools import wraps


def timeout(seconds=10):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def handle_timeout(signum, frame):
                raise Exception()
            signal(SIGALRM, handle_timeout)
            alarm(seconds)
            result = None
            try:
                result = func(*args, **kwargs)
            finally:
                alarm(0)
            return result
        return wrapper
    return decorator


def list_all_honeypots():
    for honeypot in all_servers:
        print(honeypot[1:].replace('Server', '').lower())


@timeout(5)
def server_timeout(object, name):
    try:
        print('[x] Start testing {}'.format(name))
        object.test_server()
    except BaseException:
        print('[x] Timeout {}'.format(name))
    print('[x] Done testing {}'.format(name))


def main_logic():

    from honeypots import QDNSServer, QFTPServer, QHTTPProxyServer, QHTTPServer, QHTTPSServer, QIMAPServer, QMysqlServer, QPOP3Server, QPostgresServer, QRedisServer, QSMBServer, QSMTPServer, QSOCKS5Server, QSSHServer, QTelnetServer, QVNCServer, QMSSQLServer, QElasticServer, QLDAPServer, server_arguments, clean_all, postgres_class, setup_logger, QBSniffer, get_running_servers
    from time import sleep
    from atexit import register
    from argparse import ArgumentParser, SUPPRESS
    from sys import stdout
    from subprocess import Popen
    from netifaces import ifaddresses, AF_INET, AF_LINK, interfaces
    from psutil import Process, net_io_counters
    from uuid import uuid4
    from json import JSONEncoder, dumps, load

    def exit_handler():
        print('[x] Cleaning')
        clean_all()
        sleep(1)

    class _ArgumentParser(ArgumentParser):
        def error(self, message):
            self.exit(2, 'Error: %s\n' % (message))

    ARG_PARSER = _ArgumentParser(description='Qeeqbox/honeypots customizable honeypots for monitoring network traffic, bots activities, and username\\password credentials', usage=SUPPRESS)
    ARG_PARSER._action_groups.pop()
    ARG_PARSER_SETUP = ARG_PARSER.add_argument_group("Arguments")
    ARG_PARSER_SETUP.add_argument('--setup', help='target honeypot E.g. ssh or you can have multiple E.g ssh,http,https', metavar='', default='')
    ARG_PARSER_SETUP.add_argument('--list', action='store_true', help='list all available honeypots')
    ARG_PARSER_SETUP.add_argument('--kill', action='store_true', help='kill all honeypots')
    ARG_PARSER_OPTIONAL = ARG_PARSER.add_argument_group("Optional")
    ARG_PARSER_OPTIONAL.add_argument('--ip', help='Override the IP', metavar='', default='')
    ARG_PARSER_OPTIONAL.add_argument('--port', help='Override the Port (Do not use on multiple!)', metavar='', default='')
    ARG_PARSER_OPTIONAL.add_argument('--username', help='Override the username', metavar='', default='')
    ARG_PARSER_OPTIONAL.add_argument('--password', help='Override the password', metavar='', default='')
    ARG_PARSER_OPTIONAL.add_argument('--config', help='Use a config file for honeypots settings', metavar='', default='')
    ARG_PARSER_OPTIONAL.add_argument('--test', action='store_true', help='Test a honeypot')
    ARG_PARSER_CHAMELEON = ARG_PARSER.add_argument_group("Chameleon")
    ARG_PARSER_CHAMELEON.add_argument('--chameleon', action='store_true', help='reserved for chameleon project')
    ARG_PARSER_CHAMELEON.add_argument('--sniffer', action='store_true', help='sniffer - reserved for chameleon project')
    ARG_PARSER_CHAMELEON.add_argument('--iptables', action='store_true', help='iptables - reserved for chameleon project')
    ARGV = ARG_PARSER.parse_args()
    if ARGV.list:
        list_all_honeypots()
    elif ARGV.kill:
        clean_all()
    elif ARGV.chameleon:
        print('[x] Chameleon mode')
        sniffer_filter = None
        interface = None
        honeypots = None
        if ARGV.setup != "":
            print('[!] This mode works with config.json, please remove --setup')
            exit()
        if ARGV.config == '':
            print('[!] You have to pass config.json')
            exit()
        with open(ARGV.config) as f:
            try:
                config_data = load(f)
                sniffer_filter = config_data['filter']
                interface = config_data['interface']
                honeypots = config_data['honeypots']
            except BaseException:
                print('[!] Unable to load or parse config.json file')
                exit()
        if sniffer_filter and interface:
            if not ARGV.test:
                if ARGV.sniffer:
                    current_interfaces = "unknown"
                    try:
                        current_interfaces = " ".join(interfaces())
                        if interface in current_interfaces:
                            print('[x] Your IP: {}'.format(ifaddresses(interface)[AF_INET][0]['addr']))
                            print('[x] Your MAC: {}'.format(ifaddresses(interface)[AF_LINK][0]['addr']))
                        else:
                            raise Exception()
                    except BaseException:
                        print('[!] Unable to detect IP or MAC for [{}] interface, current interfaces are [{}]'.format(interface, current_interfaces))
                        exit()
                    if ARGV.iptables:
                        try:
                            print('[x] Fixing iptables')
                            Popen('iptables -A OUTPUT -p tcp -m tcp --tcp-flags RST RST -j DROP', shell=True)
                        except BaseException:
                            pass
                    print('[x] Wait for 10 seconds..')
                    stdout.flush()
                    sleep(2)

            if ARGV.config != "":
                print('[x] Config.json file overrides --ip, --port, --username and --password')

            # Initiate chameleon db for the first time (If db is used)
            uuid = 'honeypotslogger' + '_' + 'main' + '_' + str(uuid4())[:8]
            print('[x] Setup Logger {}'.format(uuid))
            logs = setup_logger(uuid, ARGV.config, True)

            if isinstance(honeypots, dict):
                print('[x] Parsing honeypot [hard]')
                for honeypot in honeypots:
                    for _honeypot in all_servers:
                        if 'q{}server'.format(honeypot).lower() == _honeypot.lower():
                            if ARGV.port != "":
                                ARGV.port = int(ARGV.port)
                            x = locals()[_honeypot](ip=ARGV.ip, port=ARGV.port, username=ARGV.username, password=ARGV.password, config=ARGV.config)
                            if not ARGV.test:
                                x.run_server(process=True)
                            else:
                                server_timeout(x, _honeypot)
                                x.kill_server()
                            temp_honeypots.append(x)
            elif isinstance(honeypots, str):
                print('[x] Parsing honeypot [easy]')
                if ':' in honeypots:
                    print('[!] You cannot bind ports with [:] in this mode, use the honeypots dict instead')
                    exit()
                for server in honeypots.split(','):
                    for honeypot in all_servers:
                        if 'q{}server'.format(server).lower() == honeypot.lower():
                            if ARGV.port != "":
                                ARGV.port = int(ARGV.port)
                            x = locals()[honeypot](ip=ARGV.ip, port=ARGV.port, username=ARGV.username, password=ARGV.password, config=ARGV.config)
                            if not ARGV.test:
                                x.run_server(process=True)
                            else:
                                server_timeout(x, honeypot)
                                x.kill_server()
                            temp_honeypots.append(x)
            else:
                print('[!] Unable to parse honeypot from config.json file')
                exit()

            if ARGV.sniffer:
                print('[x] Start sniffer')
                x = locals()['QBSniffer'](filter=sniffer_filter, interface=interface, config=ARGV.config)
                x.run_sniffer(process=True)
                temp_honeypots.append(x)

            if not ARGV.test:
                print('[x] Everything looks good!')
                while True:
                    try:
                        _servers = {}
                        logs.info(['system', {'type': 'network', 'bytes_sent': net_io_counters().bytes_sent, 'bytes_recv': net_io_counters().bytes_recv, 'packets_sent': net_io_counters().packets_sent, 'packets_recv': net_io_counters().packets_recv}])
                        for server in temp_honeypots:
                            _servers[server.__class__.__name__] = {'memory': Process(server.process.pid).memory_percent(), 'cpu': Process(server.process.pid).cpu_percent()}
                        logs.info(['system', _servers])
                    except Exception as e:
                        pass
                    sleep(20)
            else:
                if len(temp_honeypots) > 0:
                    for server in temp_honeypots:
                        try:
                            print('[x] Killing {} tester'.format(server.__class__.__name__))
                            server.kill_server()
                        except BaseException:
                            pass
                    print('[x] Please wait few seconds')
                    sleep(5)
    elif ARGV.setup != '':
        print('[x] Use [Enter] to exit or python3 -m honeypots --kill')
        register(exit_handler)

        if ARGV.config != "":
            print('[x] config.json file overrides --ip, --port, --username and --password')

        if ARGV.setup == 'all':
            for honeypot in all_servers:
                x = locals()[honeypot](ip=ARGV.ip, username=ARGV.username, password=ARGV.password, config=ARGV.config)
                x.run_server(process=True, auto=True)
                temp_honeypots.append(x)
        else:
            servers = ARGV.setup.split(',')
            for server in servers:
                print('[x] Parsing honeypot [normal]')
                if ':' in server:
                    for honeypot in all_servers:
                        if 'q{}server'.format(server.split(':')[0]).lower() == honeypot.lower():
                            ARGV.port = int(server.split(':')[1])
                            x = locals()[honeypot](ip=ARGV.ip, port=ARGV.port, username=ARGV.username, password=ARGV.password, config=ARGV.config)
                            if not ARGV.test:
                                x.run_server(process=True)
                            else:
                                server_timeout(x, honeypot)
                                x.kill_server()
                            temp_honeypots.append(x)
                elif ARGV.port != "":
                    for honeypot in all_servers:
                        if 'q{}server'.format(server).lower() == honeypot.lower():
                            x = locals()[honeypot](ip=ARGV.ip, port=int(ARGV.port), username=ARGV.username, password=ARGV.password, config=ARGV.config)
                            if not ARGV.test:
                                x.run_server(process=True)
                            else:
                                server_timeout(x, honeypot)
                                x.kill_server()
                            temp_honeypots.append(x)
                else:
                    for honeypot in all_servers:
                        if 'q{}server'.format(server).lower() == honeypot.lower():
                            x = locals()[honeypot](ip=ARGV.ip, username=ARGV.username, password=ARGV.password, config=ARGV.config)
                            if not ARGV.test:
                                x.run_server(process=True, auto=True)
                            else:
                                print('[x] {} was configured with random port, unable to test..'.format(honeypot))
                            temp_honeypots.append(x)

        if len(temp_honeypots) > 0:
            print('[x] Everything looks good!')

            # Dirty hack to daemonize this script
            try:
                while True:
                    time.sleep(1000000)
            finally:
                print('Exiting...')

            for server in temp_honeypots:
                try:
                    if not ARGV.test:
                        print('[x] Killing {} honeypot'.format(server.__class__.__name__))
                    else:
                        print('[x] Killing {} tester'.format(server.__class__.__name__))
                    server.kill_server()
                except BaseException:
                    pass
            print('[x] Please wait few seconds')
            sleep(5)


if __name__ == '__main__':
    main_logic()
