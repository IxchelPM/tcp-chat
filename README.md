# Python TCP Chat 

A simple multi-user chat built with Python using TCP sockets and threading.

## Features

*   Client-Server architecture.
*   Handles multiple concurrent clients.
*   Unique username enforcement for clients.
*   Message broadcasting to all other clients.
*   Join and leave notifications.
*   Clients can exit by typing "Exit".

## Running

1.  **Run the Server:**
   
       Open a terminal and run:
   
       python server.py

    The server will start and print "The server is ready to receive connections."

3.  **Run Clients:**
   
       Open one or more new terminal windows. In each, run:
       
       python client.py

    *   Each client will be prompted with a welcome message and then asked to enter a unique username.
    *   Once a username is accepted, you can start sending messages.

5.  **Chatting:**
    *   Type messages in any client terminal and press Enter.
    *   The message will be broadcast to all other connected clients.
    *   To leave the chat, type `Exit` and press Enter.

## Project Files

 `server.py`: The chat server script.
 `client.py`: The chat client script.
