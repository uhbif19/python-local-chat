import sys, os, atexit, pickle, pdb
import socket, socketserver
from concurrent.futures import ThreadPoolExecutor, wait

from dictdb import DictDB

PROMT = "%s> "
# Список текущих чат-клиентов. Key-Value БД формата port: username
peers_db = DictDB("peers.txt")

stop = False # Нужно ли останавливать потоки
peers = {} # Список чат-клиентов в сети
threads = []

# Вспомогательные классы и функции

class Event:
    """ Сообщения, которые можно передавать между процессами чатов. """

    def __init__(self, **kw):
        self.__dict__.update(kw)

    event_type = None # REGISTER, LEAVE или MESSAGE
    username = None # Имя пользователя для REGISTER и MESSAGE
    server_port = None # Адрес слушающего порта нового клиента для REGISTER
    message = None # Текст сообщения для MESSAGE

class ChatPeer:
    """ Участник чата. """

    def __init__(self, **kw):
        self.__dict__.update(kw)

    username = None
    port = None # Номер слушающего сокета
    socket = None # Открытый сокет к серверу этого пира

def create_socket(port):
    sock = socket.socket(socket.AF_INET)
    sock.connect(("localhost", port))
    return sock

def broadcast(event):
    """ Передать сообщение всем клиентам. """
    for peer in peers.values():
        peer.socket.send(pickle.dumps(event))

# Треды приема и передачи сообщений

def input_message_thread():
    """ Тред для ввода и рассылки сообщений. """
    while not stop:
        message = input()
        broadcast(Event(
            event_type="MESSAGE", username=username, message=message))

def read_data(rsock):
    CHUNK_SIZE = 16*1024
    data = b""
    chunk = rsock.recv(CHUNK_SIZE)
    return chunk #%HACK

def server_thread(sock):
    """ Тред, который слушает поступающие события и сообщения. """

    sock.listen(1)

    def process_event(event):
        if event.event_type == "REGISTER":
            port = event.server_port
            socket = create_socket(port)
            peers[port] = ChatPeer(
                username=event.username, server_port=port, socket=socket)
            print("Пользователь %s вошел в чат." % event.username)
        elif event.event_type == "MESSAGE":
            print(PROMT % event.username + event.message.strip())
        elif event.event_type == "LEAVE":
            peer = peers[event.server_port]
            print("Пользователь %s вышел из чата." % peer.username)
            peer.socket.close()
            del peers[event.server_port]
        else:
            raise RuntimeError("Пришло сообщение с некорректным типом %s" % event.event_type)
    
    def client_listen_thread(csock):
        while not stop:
            event = pickle.loads(read_data(csock))
            process_event(event)
            if event.event_type == "LEAVE":
                csock.close()
                break

    while not stop:
        csock, addr = sock.accept()
        thread = executor.submit(client_listen_thread, csock)
        threads.append(thread)

    sock.close()

# Управление поднятием и остановкой нашего чат-клиента

def input_username():
    """Определяем имя пользователя."""

    used_usernames = peers_db.keys()

    while True:
        username = input("Введите логин: ")

        # Проверяем, что оно не занято %TODO
        if username not in used_usernames:
            print("Добро пожаловать в наш скромный чат.")
            break
        else:
            print("Логин %s уже занят. Выберите другой." % username)

    return username

def connect_to_peers(server_port):
    """ Соединяемся с уже открытыми чат-клиентами и регистрируемся в сети. """

    # Соединяемся с пирами записанными в файле

    for port, user in list(peers_db.items()):
        port = int(port)
        try:
            socket = create_socket(port)
            peers[port] = ChatPeer(username = user,
                port = port,
                socket = socket)

        except ConnectionError:
            # Такого пира уже нет в сети
            del peers_db[str(port)]

    # Добавляем себя в список пиров
    peers_db[server_port] = username

    # Представляемся другим клиентам
    broadcast(Event(
        event_type="REGISTER", username=username, server_port = server_port))


def shutdown(server_port):
    # Удаляемся из списка пиров

    if str(server_port) in peers_db:
        del peers_db[str(server_port)]

    # Уведомляем всех о нашем закрытии
    broadcast(Event(event_type="LEAVE", server_port=server_port))

    # Останавливаемся
    stop = True
    sock.close()  
    for thread in threads:
        thread.cancel()
    executor.shutdown(wait=False)

if __name__ == "__main__":

    executor = ThreadPoolExecutor(max_workers=100)
    port = None

    try:
        
        # Спрашиваем имя юзера
        username = input_username()
        
        # Поднимаем сервер для приема сообщений
        sock = socket.socket()
        sock.bind(("localhost", 0))
        server_future = executor.submit(server_thread, sock)
        port = sock.getsockname()[1]

        # Представляемся пирам
        connect_to_peers(port)

        # Запускаем прием и отправку сообщений
        input_future = executor.submit(input_message_thread)

        threads.extend([server_future, input_future])
        wait([server_future, input_future])

    except (KeyboardInterrupt):
        print("Всего хорошего.")
    finally:
        shutdown(port)
        if os.name != "nt":
            os._exit(0)