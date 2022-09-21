import json
import socket
import ssl

import gevent
from gevent import monkey
from gevent.select import select
from typing import Optional, Dict

monkey.patch_all()

client_conf: Optional[Dict] = None


def conn_handler(conn_socket):
    global client_conf

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client_socket = ssl.wrap_socket(client_socket, keyfile=client_conf.get("client_key"),
                                    certfile=client_conf.get("client_cert"))
    try:
        client_socket.connect((client_conf.get("server_host"), client_conf.get("server_port")))
    except ConnectionRefusedError as ex:
        conn_socket.send(b"ConnectionRefusedError")
        conn_socket.close()
        return
    except TimeoutError as ex:
        conn_socket.send(b"TimeoutError")
        conn_socket.close()
        return
    except Exception as ex:
        conn_socket.send(str(ex).encode(encoding="ascii", errors="ignore"))
        conn_socket.close()
        return

    while True:
        read_fds, _, error_fds = select([conn_socket, client_socket], [], [conn_socket, client_socket])
        if conn_socket in error_fds or client_socket in error_fds:
            conn_socket.close()
            client_socket.close()
            return

        if conn_socket in read_fds:
            data = conn_socket.recv(1024 * 1024)
            if not data:
                break
            client_socket.send(data)

        if client_socket in read_fds:
            data = client_socket.recv(1024 * 1024)
            if not data:
                break
            conn_socket.send(data)


def load_client_conf(conf_file):
    global client_conf

    f = open(conf_file)
    s = f.read(1024 * 1024)
    client_conf = json.loads(s)
    assert client_conf is not None and client_conf.get("listen_host") is not None and client_conf.get(
        "listen_port") is not None and client_conf.get("server_host") is not None and client_conf.get(
        "server_port") is not None and client_conf.get(
        "client_key") is not None and client_conf.get("client_cert") is not None


def run_client():
    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    listen_socket.bind((client_conf.get("listen_host"), client_conf.get("listen_port")))
    listen_socket.listen(0)

    while True:
        connect_socket, _ = listen_socket.accept()
        gevent.spawn(conn_handler, connect_socket)


if __name__ == "__main__":
    load_client_conf("client.json")
    run_client()