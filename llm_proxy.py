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
import select

def sanitize_filename(name):
    # Remove any characters that aren't alphanumeric, underscore, or hyphen
    sanitized = re.sub(r'[^\w\-.$@,]', lambda m: '~' if m.start() > 0 else m.group(), name)    
    # Limit to 24 characters
    return sanitized[:24]

def handle_client(client_socket, partner_socket, hello_message=None, transcript_file=None, session_name=None, mirror_stdout=False, max_messages=0, logger=None):
    persona_name = None
    
    # Wait for the /iam message
    while not persona_name:
        data = client_socket.recv(4096).decode('utf-8').strip()
        if data.startswith('/iam:'):
            logger.debug(f"Received /iam message: {data}")
            persona_name = data.split(':')[1].strip()
            logger.info(f"Received persona name: {persona_name}")
            break
    
    if hello_message:
        client_socket.send(hello_message.encode() + b'\n')
        logger.info(f"Sent hello message: {hello_message} to {client_socket.getpeername()}")
    
    return persona_name

def start_proxy(config, mirror_stdout, max_messages, logger, no_transcript):
    port = config['proxy']['port']
    host = config['proxy']['host']
    hello = config['proxy'].get('hello', '')
    
    while True:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server.bind((host, port))
        except socket.error as e:
            logger.error(f"Binding failed: {e}")
            sys.exit()

        server.listen(2)

        logger.info(f"Proxy listening on {host}:{port}")

        client1 = None
        client2 = None
        transcript_file = None

        try:
            client1, addr1 = server.accept()
            logger.info(f"Connection from {addr1[0]}:{addr1[1]}")

            client2, addr2 = server.accept()
            logger.info(f"Connection from {addr2[0]}:{addr2[1]}")

            iso_date = datetime.datetime.now().isoformat()
            
            send_hello_to_first = True # Alternatively use False or random.choice([True, False])
            persona1 = handle_client(client1, client2, hello if send_hello_to_first else None, None, None, mirror_stdout, max_messages, logger)
            persona2 = handle_client(client2, client1, hello if not send_hello_to_first else None, None, None, mirror_stdout, max_messages, logger)

            if not no_transcript:
                safe_persona1 = sanitize_filename(persona1)
                safe_persona2 = sanitize_filename(persona2)
                transcript_filename = f'transcripts/transcript_{iso_date}_{safe_persona1}---{safe_persona2}.md'
                
                transcript_file = open(transcript_filename, 'w', encoding='utf-8')
                transcript_file.write(f"| Message | Delta (s) | {persona1} | {persona2} |\n")
                transcript_file.write("|---------|-----------|")
                transcript_file.write("-" * len(persona1))
                transcript_file.write("|")
                transcript_file.write("-" * len(persona2))
                transcript_file.write("|\n")

            message_count = 0
            last_time = datetime.datetime.now()

            while True:
                ready_sockets, _, _ = select.select([client1, client2], [], [], 1.0)
                
                if not ready_sockets:
                    continue

                for ready_socket in ready_sockets:
                    try:
                        data = ready_socket.recv(4096)
                        if not data:
                            logger.warning(f"Client {ready_socket.getpeername()} disconnected")
                            raise Exception("Client disconnected")

                        current_time = datetime.datetime.now()
                        delta = int((current_time - last_time).total_seconds())
                        last_time = current_time

                        message = data.decode('utf-8').strip()
                        message = re.sub(r'\n+', ' ', message)

                        if ready_socket == client1:
                            if not no_transcript:
                                transcript_file.write(f"| {message_count} | {delta} | {message} | |\n")
                            client2.send(data)
                        else:
                            if not no_transcript:
                                transcript_file.write(f"| {message_count} | {delta} | | {message} |\n")
                            client1.send(data)

                        if not no_transcript:
                            transcript_file.flush()
                        if mirror_stdout:
                            print(f"({message_count}) Delta: {delta}s, {persona1 if ready_socket == client1 else persona2}: {message}")
                        
                        message_count += 1
                        if max_messages > 0 and message_count >= max_messages:
                            logger.info(f"Reached max messages: {max_messages}")
                            raise Exception("Max messages reached")

                    except Exception as e:
                        logger.debug(f"Error handling client: {e}")
                        raise

        except Exception as e:
            logger.exception(f"Connection ended: {e}")

        finally:
            if client1:
                client1.send(b'/stop\n')
                logger.info(f"Client1 {addr1[0]}:{addr1[1]} sent: /stop")
                client1.close()
            if client2:
                client2.send(b'/stop\n')
                logger.info(f"Client2 {addr2[0]}:{addr2[1]} sent: /stop")
                client2.close()
            if transcript_file:
                transcript_file.close()
            server.close()
            
        if not no_transcript:
            logger.info(f"Conversation ended. Transcript saved to {transcript_filename}")
        else:
            logger.info("Conversation ended. No transcript saved.")
        time.sleep(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='TCP Proxy with transcription')
    parser.add_argument('-m', '--mirror', action='store_true', help='Mirror transcript to stdout')
    parser.add_argument('-M', '--max-messages', type=int, default=10, help='Maximum number of messages to forward (0 for unlimited)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('-l', '--logfile', help='Specify a log file')
    parser.add_argument('-c', '--config', default='config/llm_proxy_config.yml', help='Specify a config file')
    parser.add_argument('-H','--host', default='127.0.0.1', help='Specify the host')
    parser.add_argument('-p','--port', type=int, default=18888, help='Specify the port')
    parser.add_argument('-q','--quiet', action='store_true', help='Enable quiet mode with minimal logging')
    parser.add_argument('-n','--no-transcript', action='store_true', help='Omit writing a transcript file')
    args = parser.parse_args()

    try:
        with open(args.config, 'r') as config_file:
            config = yaml.safe_load(config_file)
    except FileNotFoundError:
        config = {'proxy': {}}

    config['proxy']['mirror'] = args.mirror
    config['proxy']['max_messages'] = args.max_messages
    config['proxy']['verbose'] = args.verbose
    config['proxy']['logfile'] = args.logfile
    config['proxy']['host'] = args.host
    config['proxy']['port'] = args.port
    config['proxy']['no_transcript'] = args.no_transcript

    if args.quiet:
        log_level = logging.WARNING
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    if config['proxy'].get('logfile'):
        logging.basicConfig(filename=config['proxy']['logfile'], level=log_level, format=log_format)
    else:
        logging.basicConfig(level=log_level, format=log_format)
    logger = logging.getLogger('tcp_proxy')

    start_proxy(config, config['proxy'].get('mirror', False), config['proxy'].get('max_messages', 10), logger, config['proxy'].get('no_transcript', False))
