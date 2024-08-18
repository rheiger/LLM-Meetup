import socket
import threading
import sys
import random
import datetime
import re
import argparse
import logging
import yaml
import time

def handle_client(client_socket, partner_socket, hello_message=None, transcript_file=None, session_name=None, mirror_stdout=False, max_messages=0, logger=None):
    persona_name = None
    
    # Wait for the /iam message
    while not persona_name:
        data = client_socket.recv(4096).decode('utf-8').strip()
        if data.startswith('/iam:'):
            persona_name = data.split(':')[1].strip()
            logger.info(f"Received persona name: {persona_name}")
            break
    
    if hello_message:
        client_socket.send(hello_message.encode() + b'\n')
        logger.info(f"Sent hello message: {hello_message} to {client_socket.getpeername()}")
    
    message_count = 0
    while True:
        try:
            data = client_socket.recv(4096)
            if not data:
                logger.warning(f"Client {client_socket.getpeername()} disconnected")
                break
            partner_socket.send(data)
            if transcript_file:
                lines = data.decode('utf-8').strip()
                lines = re.sub(r'\n+', '\n', lines)
                transcript_content = f"{persona_name}:\n{lines}\n----------\n"
                transcript_file.write(transcript_content)
                transcript_file.flush()
                if mirror_stdout:
                    print(f"({message_count}) {transcript_content}", end='')
            
            message_count += 1
            if max_messages > 0 and message_count >= max_messages:
                logger.warning(f"Reached max messages: {max_messages}")
                break
        except:
            break

    if(hello_message):
        client_socket.send(b'/end\n')
        partner_socket.send(b'/end\n')
        logger.info(f"Sent '/end' message to {client_socket.getpeername()} and {partner_socket.getpeername()}")
    client_socket.close()
    partner_socket.close()

def start_proxy(config, mirror_stdout, max_messages, logger):
    port1 = config['proxy']['port1']
    port2 = config['proxy']['port2']
    host = config['proxy']['host']
    hello = config['proxy'].get('hello', '')
    
    while True:
        server1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        server1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server1.bind((host, port1))
            server2.bind((host, port2))
        except socket.error as e:
            logger.error(f"Binding failed: {e}")
            sys.exit()

        server1.listen(1)
        server2.listen(1)

        logger.info(f"Proxy listening on {host}:{port1} and {host}:{port2}")

        try:
            client1, addr1 = server1.accept()
            logger.info(f"Connection from {addr1[0]}:{addr1[1]} on port {port1}")

            client2, addr2 = server2.accept()
            logger.info(f"Connection from {addr2[0]}:{addr2[1]} on port {port2}")

            iso_date = datetime.datetime.now().isoformat()
            transcript_filename = f'transcript_{iso_date}_{addr1[0]}-{addr2[0]}.txt'
            
            with open(transcript_filename, 'w', encoding='utf-8') as transcript_file:
                if hello:
                    if random.choice([True, False]):
                        t1 = threading.Thread(target=handle_client, args=(client1, client2, hello, transcript_file, None, mirror_stdout, max_messages, logger))
                        t2 = threading.Thread(target=handle_client, args=(client2, client1, None, transcript_file, None, mirror_stdout, max_messages, logger))
                    else:
                        t1 = threading.Thread(target=handle_client, args=(client1, client2, None, transcript_file, None, mirror_stdout, max_messages, logger))
                        t2 = threading.Thread(target=handle_client, args=(client2, client1, hello, transcript_file, None, mirror_stdout, max_messages, logger))
                else:
                    t1 = threading.Thread(target=handle_client, args=(client1, client2, None, transcript_file, None, mirror_stdout, max_messages, logger))
                    t2 = threading.Thread(target=handle_client, args=(client2, client1, None, transcript_file, None, mirror_stdout, max_messages, logger))

                t1.start()
                t2.start()

                # Wait for both threads to complete
                t1.join()
                t2.join()

            logger.info(f"Conversation ended. Transcript saved to {transcript_filename}")

        finally:
            # Close the client sockets
            client1.close()
            client2.close()
            # Close the server sockets
            server1.close()
            server2.close()
            
        # Add a small delay before starting the next iteration
        time.sleep(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='TCP Proxy with transcription')
    parser.add_argument('-m', '--mirror', action='store_true', help='Mirror transcript to stdout')
    parser.add_argument('-M', '--max-messages', type=int, default=10, help='Maximum number of messages to forward (0 for unlimited)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('-l', '--logfile', help='Specify a log file')
    parser.add_argument('-c', '--config', default='llm_proxy_config.yml', help='Specify a config file')
    parser.add_argument('--host', default='127.0.0.1', help='Specify the host')
    parser.add_argument('--port1', type=int, default=18888, help='Specify port1')
    parser.add_argument('--port2', type=int, default=19999, help='Specify port2')
    args = parser.parse_args()

    try:
        with open(args.config, 'r') as config_file:
            config = yaml.safe_load(config_file)
    except FileNotFoundError:
        config = {'proxy': {}}

    # Override config with command line arguments
    config['proxy']['mirror'] = args.mirror
    config['proxy']['max_messages'] = args.max_messages
    config['proxy']['verbose'] = args.verbose
    config['proxy']['logfile'] = args.logfile
    config['proxy']['host'] = args.host
    config['proxy']['port1'] = args.port1
    config['proxy']['port2'] = args.port2

    # Setup logging
    log_level = logging.DEBUG if config['proxy'].get('verbose', False) else logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    if config['proxy'].get('logfile'):
        logging.basicConfig(filename=config['proxy']['logfile'], level=log_level, format=log_format)
    else:
        logging.basicConfig(level=log_level, format=log_format)
    logger = logging.getLogger('tcp_proxy')

    start_proxy(config, config['proxy'].get('mirror', False), config['proxy'].get('max_messages', 10), logger)
