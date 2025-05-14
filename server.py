from socket import *
import threading

serverPort = 12000
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind(('', serverPort))
serverSocket.listen(50)
print('The server is ready to receive connections.')

client_list = []
client_list_lock = threading.Lock()

def get_username_by_socket(client_socket):
    with client_list_lock:
        for client_info in client_list:
            if client_info[0] == client_socket:
                return client_info[2]
    return None

def broadcast_message(sender_socket, message_content, sender_username):
    with client_list_lock:
        for client_info in client_list:
            client_conn, _, client_user = client_info
            if client_conn != sender_socket:
                try:
                    if message_content == "Exit" and sender_socket is not None:
                        full_message = f"{sender_username} has left the chat."
                    elif sender_socket is None or sender_username == "Server":
                        full_message = message_content # Message is already formatted
                    else:
                        full_message = f"{sender_username}: {message_content}"
                    client_conn.send(full_message.encode())
                except (OSError, BrokenPipeError):
                    print(f"Error sending to {client_user}, connection might be closed.")

def handle_client(client_socket, client_address):
    print(f"Accepted new connection from {client_address}")
    client_socket.send("Welcome to the Chat Room!\nType 'Exit' to leave.\n".encode())

    chosen_username = ""
    while True:
        try:
            client_socket.send("Please enter your username: ".encode()) 
            username_attempt = client_socket.recv(1024).decode().strip() 

            if not username_attempt: # Client disconnected or sent empty
                print(f"Client {client_address} sent empty username or disconnected during username selection.")
                client_socket.close()
                return

            is_taken = False
            with client_list_lock: # Check if username is already in use
                for _, _, existing_user in client_list:
                    if existing_user == username_attempt:
                        is_taken = True
                        break
            
            if is_taken:
                rejection_msg = f"Username '{username_attempt}' is already taken. Please try a different one.\n"
                client_socket.send(rejection_msg.encode())
                # Loop continues, server will send "Please enter your username: " again in next iteration
            else:
                # Username is unique
                chosen_username = username_attempt
                acceptance_msg = f"Username '{chosen_username}' accepted. You are now in the chat.\n"
                client_socket.send(acceptance_msg.encode()) 
                break 

        except (ConnectionResetError, OSError):
            print(f"Client {client_address} disconnected during username selection.")
            client_socket.close()
            return
        except Exception as e:
            print(f"Unexpected error during username selection for {client_address}: {e}")
            try:
                client_socket.send("An error occurred during username setup. Please try reconnecting.\n".encode())
            except OSError: pass 
            finally:
                client_socket.close()
            return
    
    username = chosen_username 
    print(f"{client_address} successfully set username to: {username}")

    with client_list_lock:
        client_list.append([client_socket, client_address, username])

    join_message = f"{username} has joined the chat."
    print(f"Server log: {join_message}")
    # Use None for sender_socket to indicate a server message, or a specific identifier
    broadcast_message(None, join_message, "Server")


    try:
        while True:
            message = client_socket.recv(1024).decode().strip()
            
            if not message:
                print(f"{username} ({client_address}) disconnected abruptly.")
                broadcast_message(client_socket, "Exit", username)
                break 

            print(f"Received from {username}: {message}")

            if message.lower() == "exit":
                print(f"{username} is leaving.")
                broadcast_message(client_socket, "Exit", username)
                break
            else:
                broadcast_message(client_socket, message, username)

    except (ConnectionResetError, OSError) as e:
        print(f"Connection error with {username} ({client_address}): {e}")
        broadcast_message(client_socket, "Exit", username)
    except Exception as e:
        print(f"Unexpected error with {username} ({client_address}): {e}")
        broadcast_message(client_socket, "Exit", username)
    finally:
        with client_list_lock:
            client_to_remove = None
            for c_info in client_list:
                if c_info[0] == client_socket:
                    client_to_remove = c_info
                    break
            if client_to_remove:
                client_list.remove(client_to_remove)
                print(f"Removed {username} ({client_address}) from active clients.")
        try:
            client_socket.close()
        except OSError:
            pass

# Main server loop
while True:
    connectionSocket, addr = serverSocket.accept()
    client_thread = threading.Thread(target=handle_client, args=(connectionSocket, addr))
    client_thread.daemon = True
    client_thread.start()