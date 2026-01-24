import socket
import time
import random
import json
from datetime import datetime, timezone
from pokelogger import PokeLogger











# brain.py








    

last_position = {"X": 0, "Y": 0, "mapBank": 0, "mapID": 0}





# Create a persistent target outside your loop so it stays the same
# until the move is actually executed.
target_move = None 

battle_frame_counter = 0
target_move_slot = None
ACTION_THRESHOLD = 30 # Act every 30 frames (0.5 seconds at 60fps)

MAIN_MENU = 1  # Verify if 1 is your Fight/Bag/Run screen
MOVE_MENU = 2  # Your logs confirmed 2 is Move Selection





def start_brain():
    global last_position, total_reward
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Brain active. Waiting for BizHawk on {PORT}...")
        
        conn, addr = s.accept()
        with conn:
            try:
                while True:
                    data = conn.recv(1024).decode('utf-8')
                    if not data:
                        break
                    
                    # 'data' will be the RAM values sent from Lua (e.g., "PlayerX,PlayerY,InBattle")

                    # SIMPLE LOGIC: If InBattle (1), press A. Otherwise, move Right.
                    # In a real AI, this is where your model.predict() goes.
                    state_data = parse_state(data)
                    if (state_data is None or state_data == previous_state):
                        continue  # Skip this loop if parsing failed or no state change
                    print(f'state: {state_data}')
                    previous_total = total_reward
                    update_brain(state_data)
                    frame_reward = total_reward - previous_total                    
                    logger.log(state_data, total_reward, frame_reward)

                    #print('battle mode: ', state_data.get('battleType'))
                    command = decide_action(state_data) + '\n'
                    conn.sendall(command.encode('utf-8'))
            finally:
                logger.close()

if __name__ == "__main__":
    start_brain()
