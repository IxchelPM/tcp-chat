from socket import *
import threading
import sys

stdout_lock = threading.Lock()

serverName = '127.0.0.1' # Or your server's actual IP if not localhost
serverPort = 12000

clientSocket = socket(AF_INET, SOCK_STREAM)
try:
    clientSocket.connect((serverName, serverPort))
except ConnectionRefusedError:
    print("Connection refused. Is the server running?")
    sys.exit(1)
except Exception as e:
    print(f"Error connecting to server: {e}")
    sys.exit(1)

user_name = "" 


try:
    welcome_mes = clientSocket.recv(1024).decode()
    print(welcome_mes, end='') 
except (OSError, ConnectionResetError) as e:
    print(f"Error receiving welcome: {e}. Server might have closed connection.")
    clientSocket.close()
    sys.exit(1)

while True: 
    try:
        server_message = clientSocket.recv(1024).decode()
        if not server_message:
            print("Server closed connection during username setup.")
            clientSocket.close()
            sys.exit(1)
        
        print(server_message, end='') 

        # The `input()` below will use the prompt displayed by `print(server_message, end='')`
        
        attempted_name = input() 
        clientSocket.send(attempted_name.encode())

        verdict = clientSocket.recv(1024).decode()
        print(verdict, end='')

        if "accepted" in verdict.lower():
            user_name = attempted_name 
            break # Exit loop, username is confirmed
        # If not accepted, loop continues. Server should send "Please enter username:" again.

    except (OSError, ConnectionResetError) as e:
        print(f"\nError during username setup: {e}. Server might have closed connection.")
        clientSocket.close()
        sys.exit(1)
    except EOFError: # User pressed Ctrl+D
        print("\nInput stream closed during username setup. Exiting.")
        clientSocket.close()
        sys.exit(1)

print(f"--- Welcome, {user_name}! You are now in the chat. ---")

def print_incoming_message(incoming_msg):
    """Helper to print incoming messages cleanly, preserving user input line."""
    with stdout_lock:
        sys.stdout.write('\r' + ' ' * (len(user_name) + 2 + 60) + '\r')
        
        # Print the incoming message
        print(incoming_msg)

def message_recv():
    """Handles receiving messages from the server."""
    while True:
        try:
            message = clientSocket.recv(1024).decode()
            if message:
                print_incoming_message(message)
            else: # Server likely closed connection
                with stdout_lock:
                    sys.stdout.write('\r' + ' ' * (len(user_name) + 2 + 60) + '\r')
                    print("Server has closed the connection. Press Enter to exit.")
                clientSocket.close() # Close our end
                break # Exit recv thread
        except (OSError, ConnectionResetError):
            if clientSocket.fileno() != -1 : 
                with stdout_lock:
                    sys.stdout.write('\r' + ' ' * (len(user_name) + 2 + 60) + '\r')
                    print("Connection lost. Press Enter to exit.")
            try:
                if clientSocket.fileno() != -1: clientSocket.close()
            except OSError: pass
            break 

def message_send():
    """Handles sending messages from the client."""
    while True:
        try:
            message_to_send = input(f"{user_name}> ")

            # If recv_thread closed socket, input() might raise EOFError or OSError
            # or fileno check will catch it.

            with stdout_lock: # Brief lock for sending, ensure socket still open
                if clientSocket.fileno() == -1: 
                    break
                clientSocket.send(message_to_send.encode())

            if message_to_send.lower() == "exit":
                # recv_thread should then detect server closing connection.
                print("You are exiting the chat...") 
                try:
                    clientSocket.close()
                except OSError: pass 
                break # Exit send thread

        except EOFError:
            with stdout_lock:
                sys.stdout.write('\r' + ' ' * (len(user_name) + 2 + 60) + '\r')
                print("EOF detected. Sending 'Exit' and closing.")
            try:
                if clientSocket.fileno() != -1 : clientSocket.send("Exit".encode())
                if clientSocket.fileno() != -1 : clientSocket.close()
            except OSError: pass
            break
        except (OSError, ConnectionResetError): # Socket error during send or input() after socket closed
            break # Exit send thread
        except KeyboardInterrupt:
            # This allows Ctrl+C during input() to be caught by the main try/except
            raise 


# Start chat threads
recv_thread = threading.Thread(target=message_recv)
recv_thread.daemon = True 
recv_thread.start()

send_thread = threading.Thread(target=message_send)
send_thread.start()

# Main thread waits for send_thread (which handles user input and "Exit")
try:
    send_thread.join()
except KeyboardInterrupt: 
    with stdout_lock:
        sys.stdout.write('\r' + ' ' * (len(user_name) + 2 + 70) + '\r') 
        print("\nCtrl+C detected. Sending 'Exit' and closing client.") 
    try:
        if clientSocket.fileno() != -1: 
            clientSocket.send("Exit".encode()) 
    except OSError:
        pass 
    finally:
        try:
            if clientSocket.fileno() != -1: clientSocket.close() # Ensure our socket is closed
        except OSError:
            pass
finally:
    if recv_thread.is_alive():
        recv_thread.join(timeout=0.2) # Give a short timeout for it to stop
    with stdout_lock:
        sys.stdout.write('\r' + ' ' * (len(user_name) + 2 + 70) + '\r') # Final clear line
        print("Client has shut down.")