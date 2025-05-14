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

user_name = "" # Will be set after successful username negotiation

# Username acquisition phase
try:
    # Receive initial welcome (server sends this first)
    welcome_mes = clientSocket.recv(1024).decode()
    print(welcome_mes, end='') # end='' to handle server's optional newline
except (OSError, ConnectionResetError) as e:
    print(f"Error receiving welcome: {e}. Server might have closed connection.")
    clientSocket.close()
    sys.exit(1)

while True: # Username negotiation loop
    try:
        # Expecting "Please enter your username: " or a rejection message
        server_message = clientSocket.recv(1024).decode()
        if not server_message:
            print("Server closed connection during username setup.")
            clientSocket.close()
            sys.exit(1)
        
        print(server_message, end='') # Display server's message (prompt or rejection)

        # If it was just a rejection, the actual prompt might follow in the same message
        # or server sends it again. Our server sends prompt after rejection.
        # The `input()` below will use the prompt displayed by `print(server_message, end='')`
        
        attempted_name = input() # User types here, after seeing the server's prompt
        clientSocket.send(attempted_name.encode())

        # Wait for server's verdict on the *attempted_name*
        verdict = clientSocket.recv(1024).decode()
        print(verdict, end='') # Display server's response (e.g., "Username accepted." or "Username 'X' is taken...")

        if "accepted" in verdict.lower():
            user_name = attempted_name # Store the accepted username
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

# This print confirms setup on the client side before chat threads start.
# It should appear on a new line after the server's "Username ... accepted..." message.
print(f"--- Welcome, {user_name}! You are now in the chat. ---")

def print_incoming_message(incoming_msg):
    """Helper to print incoming messages cleanly, preserving user input line."""
    with stdout_lock:
        # Erase the current line (where the input prompt is)
        # \r moves to beginning, spaces overwrite, \r again.
        # The length of spaces should be enough to cover prompt + some user typing.
        sys.stdout.write('\r' + ' ' * (len(user_name) + 2 + 60) + '\r')
        
        # Print the incoming message
        print(incoming_msg)
        
        # Reprint the prompt for the user to continue typing
        #sys.stdout.write(f"{user_name}> ")
        #sys.stdout.flush()

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
        except (OSError, ConnectionResetError): # Connection issue
            # Only print if socket hasn't been closed by send_thread already
            if clientSocket.fileno() != -1 : # Check if socket is still open
                with stdout_lock:
                    sys.stdout.write('\r' + ' ' * (len(user_name) + 2 + 60) + '\r')
                    print("Connection lost. Press Enter to exit.")
            try:
                if clientSocket.fileno() != -1: clientSocket.close()
            except OSError: pass
            break # Exit recv thread

def message_send():
    """Handles sending messages from the client."""
    while True:
        try:
            # input() will display the prompt f"{user_name}> "
            message_to_send = input(f"{user_name}> ")

            # If recv_thread closed socket, input() might raise EOFError or OSError
            # or fileno check will catch it.

            with stdout_lock: # Brief lock for sending, ensure socket still open
                if clientSocket.fileno() == -1: # Socket closed (e.g., by recv_thread)
                    break
                clientSocket.send(message_to_send.encode())

            if message_to_send.lower() == "exit":
                # Server will handle broadcasting "left chat" and closing its end.
                # We close our end after sending "Exit".
                # recv_thread should then detect server closing connection.
                print("You are exiting the chat...") # Local feedback
                try:
                    # clientSocket.shutdown(SHUT_RDWR) # More forceful if needed
                    clientSocket.close()
                except OSError: pass # Socket might already be closed
                break # Exit send thread

        except EOFError: # User pressed Ctrl+D
            with stdout_lock:
                sys.stdout.write('\r' + ' ' * (len(user_name) + 2 + 60) + '\r')
                print("EOF detected. Sending 'Exit' and closing.")
            try:
                if clientSocket.fileno() != -1 : clientSocket.send("Exit".encode())
                if clientSocket.fileno() != -1 : clientSocket.close()
            except OSError: pass
            break
        except (OSError, ConnectionResetError): # Socket error during send or input() after socket closed
            # This means the socket is already bad, recv_thread probably handled message
            break # Exit send thread
        except KeyboardInterrupt:
            # This allows Ctrl+C during input() to be caught by the main try/except
            raise # Re-raise to be caught by the main handler


# Start chat threads
recv_thread = threading.Thread(target=message_recv)
recv_thread.daemon = True # So it exits if main thread exits unexpectedly
recv_thread.start()

send_thread = threading.Thread(target=message_send)
# send_thread is not daemon; main thread will wait for it to finish (e.g. user types "Exit")
send_thread.start()

# Main thread waits for send_thread (which handles user input and "Exit")
try:
    send_thread.join()
except KeyboardInterrupt: # Handle Ctrl+C pressed in the main thread context
    with stdout_lock:
        sys.stdout.write('\r' + ' ' * (len(user_name) + 2 + 70) + '\r') # Clear line
        print("\nCtrl+C detected. Sending 'Exit' and closing client.") # \n from Ctrl+C
    try:
        if clientSocket.fileno() != -1: # Check if socket is still valid
            clientSocket.send("Exit".encode()) # Attempt to notify server
    except OSError:
        pass # Ignore errors if socket is already problematic
    finally:
        try:
            if clientSocket.fileno() != -1: clientSocket.close() # Ensure our socket is closed
        except OSError:
            pass
finally:
    # Ensure recv_thread also gets a chance to terminate if it hasn't already.
    if recv_thread.is_alive():
        # print("Debug: Main thread waiting for recv_thread to join...")
        recv_thread.join(timeout=0.2) # Give a short timeout for it to stop
    with stdout_lock:
        sys.stdout.write('\r' + ' ' * (len(user_name) + 2 + 70) + '\r') # Final clear line
        print("Client has shut down.")