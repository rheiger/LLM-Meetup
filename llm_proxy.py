import socket
import threading
import configparser
import sys
import random

def handle_client(client_socket, partner_socket, hello_message=None):
    if hello_message:
        client_socket.send(hello_message.encode() + b'\n')
    
    while True:
        try:
            data = client_socket.recv(4096)
            if not data:
                break
            partner_socket.send(data)
        except:
            break
    
    client_socket.close()
    partner_socket.close()

def start_proxy(config):
    port1 = config.getint('Proxy', 'port1')
    port2 = config.getint('Proxy', 'port2')
    host = config.get('Proxy', 'host')
    hello = config.get('Proxy', 'hello', fallback='')
    
    server1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        server1.bind((host, port1))
        server2.bind((host, port2))
    except socket.error as e:
        print(f"Binding failed: {e}")
        sys.exit()

    server1.listen(1)
    server2.listen(1)

    print(f"Proxy listening on {host}:{port1} and {host}:{port2}")

    while True:
        client1, addr1 = server1.accept()
        print(f"Connection from {addr1[0]}:{addr1[1]} on port {port1}")

        client2, addr2 = server2.accept()
        print(f"Connection from {addr2[0]}:{addr2[1]} on port {port2}")

        if hello:
            if random.choice([True, False]):
                t1 = threading.Thread(target=handle_client, args=(client1, client2, hello))
                t2 = threading.Thread(target=handle_client, args=(client2, client1))
            else:
                t1 = threading.Thread(target=handle_client, args=(client1, client2))
                t2 = threading.Thread(target=handle_client, args=(client2, client1, hello))
        else:
            t1 = threading.Thread(target=handle_client, args=(client1, client2))
            t2 = threading.Thread(target=handle_client, args=(client2, client1))

        t1.start()
        t2.start()

if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read('proxy_config.ini')

    start_proxy(config)
