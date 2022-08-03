import socket
import os
import sys
import time
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

IP = ""
PORT = ""
FOLDER_PATH = ""
TTU = ""
KEY = ""
UPDATED_TIME = ""
UPDATE_HISTORY = 0
CHANGED_SUB = ""


# Create a new request and send it to the server
def make_request(code, src_path, dst_path, getfile):
    global UPDATED_TIME
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((IP, int(PORT)))

    s.sendall(code.encode() + b'\n')
    s.sendall(KEY.encode() + b'\n')
    s.sendall(str(time.time()).encode() + b'\n')

    new_path = (src_path.split(FOLDER_PATH)[1])[1:]
    s.sendall(str(new_path).encode() + b'\n')

    if dst_path != "":
        new_path = (dst_path.split(FOLDER_PATH)[1])[1:]
        s.sendall(str(new_path).encode() + b'\n')

    if getfile == 1:
        send_file(src_path, s)

    s.close()
    UPDATED_TIME = time.time()


# Watchdog - when a file/folder is created then send a message to the server
def on_created(event):
    global UPDATE_HISTORY

    if event.is_directory:
        if UPDATE_HISTORY > 0:
            UPDATE_HISTORY -= 1
            return 1
        make_request("222", event.src_path, "", 0)
    else:
        tmp = os.path.splitext(event.src_path)[1]
        if tmp != ".tmp" and tmp[-1] != '#':
            if UPDATE_HISTORY > 0:
                UPDATE_HISTORY -= 1
                return 1
            make_request("333", event.src_path, "", 0)
            if os.stat(event.src_path).st_size != 0:
                make_request("777", event.src_path, "", 1)


# Watchdog - when a file/folder is deleted then send a message to the server
def on_deleted(event):
    global UPDATE_HISTORY

    if event.is_directory:
        if UPDATE_HISTORY > 0:
            UPDATE_HISTORY -= 1
            return 1
        make_request("444", event.src_path, "", 0)
    else:
        tmp = os.path.splitext(event.src_path)[1]
        if tmp != ".tmp" and tmp != "" and tmp[-1] != '#':
            if UPDATE_HISTORY > 0:
                UPDATE_HISTORY -= 1
                return 1
            make_request("555", event.src_path, "", 0)


# Watchdog - when a file/folder is modified then send a message to the server
def on_modified(event):
    global UPDATE_HISTORY

    # To avoid false alert the statement check if the event is not a temporary file
    if not event.is_directory:
        tmp = os.path.splitext(event.src_path)[1]
        if tmp != ".tmp" and tmp[-1] != '#':
            if UPDATE_HISTORY > 0:
                UPDATE_HISTORY -= 1
                return 1
            make_request("777", event.src_path, "", 1)


# Watchdog - when a file/folder is moved then send a message to the server
def on_moved(event):
    global UPDATE_HISTORY, CHANGED_SUB

    # Block recursive folder changes
    if CHANGED_SUB == "":
        CHANGED_SUB = event.src_path
    elif CHANGED_SUB in event.src_path:
        return 1
    else:
        CHANGED_SUB = event.src_path

    if not event.is_directory:
        tmp = os.path.splitext(event.src_path)[1]
        if tmp != ".tmp" and tmp[-1] != '#':
            if UPDATE_HISTORY > 0:
                UPDATE_HISTORY -= 1
                return 1
            make_request("666", event.src_path, event.key[2], 0)
    else:
        if UPDATE_HISTORY > 0:
            UPDATE_HISTORY -= 1
            return 1
        make_request("666", event.src_path, event.key[2], 0)


# The function create a list of folder / file names
def get_file_directory(path):
    all_files = []
    all_directories = []
    walk = [path]
    while walk:
        folder = walk.pop(0) + "/"
        all_directories.append(folder)
        items = os.listdir(folder)
        for i in items:
            i = folder + i
            (walk if os.path.isdir(i) else all_files).append(i)
    return all_files, all_directories[1:]


# Send directory names
def send_file(filename, sock):
    size = os.path.getsize(filename)
    sock.sendall(str(size).encode() + b'\n')

    with open(filename, 'rb') as f:
        sock.sendall(f.read())


# Send directory names
def send_list(data_list, sock):
    data = []
    for name in data_list:
        temp = (name.split(FOLDER_PATH)[1])[1:]
        data.append(temp)
    data = ','.join(data)

    sock.sendall(data.encode() + b'\n')


# The function upload a new dir to the server
def upload_dir(file_list, folder_list, sock):
    send_list(folder_list, sock)
    send_list(file_list, sock)

    for filename in file_list:
        send_file(filename, sock)


# The function get a list of file/folder names
def get_list(client_file):
    data_list = client_file.readline().strip().decode()
    data_list = data_list.split(',')
    return data_list


# The function download a file from the server
def download_file(filename, path, client_file):
    size = int(client_file.readline())
    data = client_file.read(size)
    with open(os.path.join(path, filename), 'wb') as f:
        f.write(data)


# The function download the entire dir from the server
def download_dir(cli_file):
    # Download the folder names and create the folders
    data = get_list(cli_file)
    for directory in data:
        new_path = os.path.join(FOLDER_PATH, directory)
        os.mkdir(new_path)

    # Download the file names and create the files
    data = get_list(cli_file)
    for filename in data:
        download_file(filename, FOLDER_PATH, cli_file)


# The function upload an existing folder from the client to the server
def new_client():
    global KEY
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((IP, int(PORT)))

    with s, s.makefile('rb') as client_file:
        s.sendall("000".encode() + b'\n')
        KEY = client_file.readline().strip().decode()
        file_list, folder_list = get_file_directory(FOLDER_PATH)
        upload_dir(file_list, folder_list, s)

    s.close()


# The function download an existing folder from the server to the client
def existing_client():
    # Create a new directory
    if not os.path.exists(FOLDER_PATH):
        os.mkdir(FOLDER_PATH)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((IP, int(PORT)))

    with s, s.makefile('rb') as client_file:
        s.sendall("111".encode() + b'\n')
        s.sendall(KEY.encode() + b'\n')
        download_dir(client_file)

    s.close()


# The function get the src_path, dst_path changes and download the file
def get_request(client_file, getdst, getfile):
    global UPDATE_HISTORY
    src_name = client_file.readline().strip().decode()
    src_full = os.path.join(FOLDER_PATH, src_name)
    dst_full = ""

    if getdst == 1:
        dst_full = os.path.join(FOLDER_PATH, client_file.readline().strip().decode())
    if getfile == 1:
        UPDATE_HISTORY += 3
        os.remove(src_full)
        download_file(src_name, FOLDER_PATH, client_file)

    return src_full, dst_full


def delete_folder(delete_path):
    global UPDATE_HISTORY
    file_list, folder_list = get_file_directory(delete_path)
    # Remove all files in the directory and sub-directories
    for file_path in file_list:
        UPDATE_HISTORY += 1
        os.remove(file_path)

    # Remove the sub-directories and the main directory
    folder_list.reverse()
    for folder_path in folder_list:
        UPDATE_HISTORY += 1
        os.rmdir(folder_path)

    UPDATE_HISTORY += 1
    os.rmdir(delete_path)


# The function ask for updates, if there is new updates it apply it
def check_update():
    global UPDATED_TIME, UPDATE_HISTORY
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((IP, int(PORT)))

    with s, s.makefile('rb') as client_file:
        # 888 - Get new updates
        s.sendall("888".encode() + b'\n')
        s.sendall(KEY.encode() + b'\n')
        s.sendall(str(UPDATED_TIME).encode() + b'\n')

        # NOU - stop if the is no more updates
        data = client_file.readline().strip().decode()
        while data != "NOU":
            # 222 - create a new folder
            if data == "222":
                src, dst = get_request(client_file, 0, 0)
                if not os.path.exists(src):
                    os.mkdir(src)
                    UPDATE_HISTORY += 1
            # 333 - Create a new file
            elif data == "333":
                src, dst = get_request(client_file, 0, 0)
                file = open(src, 'wb')
                file.close()
                UPDATE_HISTORY += 1
            # 444 - Remove a folder
            elif data == "444":
                src, dst = get_request(client_file, 0, 0)
                if os.path.exists(src):
                    delete_folder(src)
            # 555 - Remove a file
            elif data == "555":
                src, dst = get_request(client_file, 0, 0)
                os.remove(src)
                UPDATE_HISTORY += 1
            # 666 - Rename a file / folder
            elif data == "666":
                src, dst = get_request(client_file, 1, 0)
                os.rename(src, dst)
                UPDATE_HISTORY += 1
            # 777 - Get changes in a file
            elif data == "777":
                get_request(client_file, 0, 1)
            # Get the next update
            data = client_file.readline().strip().decode()

    s.close()
    UPDATED_TIME = time.time()


# The function start launch the observer and ask for update each TTU sec
def start():
    global UPDATED_TIME
    patterns = ["*"]
    ignore_patterns = None
    ignore_directories = False
    case_sensitive = True
    my_event_handler = PatternMatchingEventHandler(patterns, ignore_patterns, ignore_directories, case_sensitive)

    # Init the watchdog observer
    my_event_handler.on_created = on_created
    my_event_handler.on_deleted = on_deleted
    my_event_handler.on_modified = on_modified
    my_event_handler.on_moved = on_moved

    go_recursively = True
    my_observer = Observer()
    my_observer.schedule(my_event_handler, FOLDER_PATH, recursive=go_recursively)

    # Start the observer and update the current time
    my_observer.start()
    UPDATED_TIME = time.time()

    try:
        while True:
            # Get the newest update each TTU seconds
            time.sleep(int(TTU))
            check_update()
    except KeyboardInterrupt:
        my_observer.stop()
        my_observer.join()


if __name__ == "__main__":
    # New folder in the server - get a key from the server and upload the current folder
    if len(sys.argv) == 5:
        IP, PORT, FOLDER_PATH, TTU = sys.argv[1:]
        new_client()

    # Existing folder in the server - download a folder from the server
    elif len(sys.argv) == 6:
        IP, PORT, FOLDER_PATH, TTU, KEY = sys.argv[1:]
        existing_client()

    # Start - get update each 'TTU' sec, watch about changes and push changes to the server
    start()
