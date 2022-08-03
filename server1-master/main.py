import os
import random
import socket
import string
import sys

HISTORY = {}


# Create a new request and send it to the server
def make_request(code, src_path, dst_path, getfile, key, sock):
    sock.sendall(code.encode() + b'\n')

    new_path = (src_path.split(key)[1])[1:]
    sock.sendall(str(new_path).encode() + b'\n')

    if dst_path != "":
        new_path = (dst_path.split(key)[1])[1:]
        sock.sendall(str(new_path).encode() + b'\n')

    if getfile == 1:
        send_file(src_path, sock)


# Generate a key of 128B contain just numbers, lowercase and uppercase
def generate_key():
    result = ""
    pattern = string.digits + string.ascii_lowercase + string.ascii_uppercase
    for i in range(0, 128):
        result = result + random.choice(pattern)
    return result


# The function get a list of file/folder names
def get_list(cli_file):
    data_list = cli_file.readline().strip().decode()
    data_list = data_list.split(',')
    return data_list


# The function download a file from the server
def download_file(filename, path, cli_file):
    size = int(cli_file.readline())
    to_write = cli_file.read(size)
    with open(os.path.join(path, filename), 'wb') as f:
        f.write(to_write)


# Send directory names
def send_file(filename, sock):
    size = os.path.getsize(filename)
    sock.sendall(str(size).encode() + b'\n')

    with open(filename, 'rb') as f:
        sock.sendall(f.read())


# Download the folder names and create the folders
def download_dir(path, cli_file):
    data_list = get_list(cli_file)
    for directory in data_list:
        if directory != "":
            new_path = os.path.join(path, directory)
            os.mkdir(new_path)

    # Download the file names and create the files
    data_list = get_list(cli_file)
    for filename in data_list:
        if filename != "":
            download_file(filename, path, cli_file)


# Create a new account - Download the entire dir from the client
def new_account(sock, cli_file):
    # Generate and sent a key to the new client
    key = generate_key()
    sock.sendall(key.encode() + b'\n')
    HISTORY[key] = []
    print(key)

    # Open a folder for the new client - the folder name is the key
    os.mkdir(key)
    download_dir(key, cli_file)


# Send directory names
def send_list(data_list, sock, path):
    res = []
    for name in data_list:
        temp = (name.split(path)[1])[1:]
        res.append(temp)
    res = ','.join(res)
    sock.sendall(res.encode() + b'\n')


# The function upload a new dir to the server
def upload_dir(file_list, folder_list, sock, key):
    send_list(folder_list, sock, key)
    send_list(file_list, sock, key)

    for filename in file_list:
        send_file(filename, sock)


# The function create a list of folder / file names
def get_file_directory(path):
    all_files = []
    all_directories = []
    walk = [path]
    while walk:
        folder = walk.pop(0) + "/"
        all_directories.append(folder)
        # items = folders + files
        items = os.listdir(folder)
        for i in items:
            i = folder + i
            (walk if os.path.isdir(i) else all_files).append(i)
    return all_files, all_directories[1:]


# The function upload the entire folder and file
def existing_account(sock):
    key = client_file.readline().strip().decode()
    file_list, folder_list = get_file_directory(key)
    upload_dir(file_list, folder_list, sock, key)


def get_request(code, cli_file, str1, getfile):
    # Get the key, last time of updates and the src name
    key = client_file.readline().strip().decode()
    ltu = float(client_file.readline())
    src_name = client_file.readline().strip().decode()
    src_full = os.path.join(key, src_name)

    dst_full = ""
    if str1 != "":
        dst_full = os.path.join(key, client_file.readline().strip().decode())
    if getfile == 1:
        os.remove(src_full)
        download_file(src_name, key, cli_file)

    # Add the request to the history
    user_history = HISTORY[key]
    op = code + "?" + src_full + "?" + dst_full
    temp = [float(ltu), op]
    user_history.append(temp)

    return src_full, dst_full


def update_client(sock, cli_file):
    # Get the key and the last time of updates
    key = cli_file.readline().strip().decode()
    last_update = float(cli_file.readline())
    user_history = HISTORY[key]

    for event in user_history:
        # Check if the current event is newer than the last update on the client
        if last_update < float(event[0]):
            # opp = the command number
            comm = event[1].split('?')
            opp = comm[0]
            src_full = comm[1]

            if opp == "222":
                # 222 - Create a new folder
                make_request("222", src_full, "", 0, key, sock)
            elif opp == "333":
                # 333 - Create a new file
                make_request("333", src_full, "", 0, key, sock)
            elif opp == "444":
                # 444 - Remove a folder
                make_request("444", src_full, "", 0, key, sock)
            elif opp == "555":
                # 555 - Remove a file
                make_request("555", src_full, "", 0, key, sock)
            elif opp == "666":
                # 666 - Rename a file / folder
                dst_full = comm[2]
                make_request("666", src_full, dst_full, 0, key, sock)
            elif opp == "777":
                # 777 - Get changes in a file
                make_request("777", src_full, "", 1, key, sock)
    # If there is no more updates
    sock.sendall("NOU".encode() + b'\n')


def delete_folder(delete_path):
    file_list, folder_list = get_file_directory(delete_path)
    # Remove all files in the directory and sub-directories
    for file_path in file_list:
        os.remove(file_path)

    # Remove the sub-directories and the main directory
    folder_list.reverse()
    for folder_path in folder_list:
        os.rmdir(folder_path)
    os.rmdir(delete_path)


if __name__ == '__main__':
    globals()
    HISTORY['123a'] = []

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('', int(sys.argv[1])))
    server.listen(5)

    while True:
        client_socket, client_address = server.accept()
        with client_socket, client_socket.makefile('rb') as client_file:

            data = client_file.readline()
            if not data:
                break
            data = data.strip().decode()

            if data == "000":
                # New account - create a new folder on the server and download the content
                new_account(client_socket, client_file)
            elif data == "111":
                # Existing account - create a new folder on the client and download the content
                existing_account(client_socket)
            elif data == "222":
                # 222 - create a new folder
                src, dst = get_request(data, client_file, "", 0)
                os.mkdir(src)
            elif data == "333":
                # 333 - Create a new file
                src, dst = get_request(data, client_file, "", 0)
                file = open(src, 'wb')
                file.close()
            elif data == "444":
                # 444 - Remove a folder
                src, dst = get_request(data, client_file, "", 0)
                if os.path.exists(src):
                    delete_folder(src)
            elif data == "555":
                # 555 - Remove a file
                src, dst = get_request(data, client_file, "", 0)
                os.remove(src)
            elif data == "666":
                # 666 - Rename a file / folder
                src, dst = get_request(data, client_file, "NAD", 0)
                if os.path.exists(src):
                    os.rename(src, dst)
            elif data == "777":
                # 777 - Get changes in a file
                src, dst = get_request(data, client_file, "", 1)
            elif data == "888":
                # 888 - Get updates
                update_client(client_socket, client_file)

        client_socket.close()
