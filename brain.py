import socket
import time
import random

# Configuration
HOST = '127.0.0.1'
PORT = 65432

previous_state = None
total_reward = 0

visited_maps = set() # Stores strings like "Bank-Map" (e.g., "3-1")

def calculate_exploration_reward(state):
    print('Calculating exploration reward...')
    global visited_maps
    
    bank = state.get('mapBank')
    map_num = state.get('mapID')
    map_key = f"{bank}-{map_num}"
    
    # Check if this is a brand new discovery
    if map_key not in visited_maps:
        visited_maps.add(map_key)
        print(f"NEW AREA DISCOVERED: {map_key}! +500 Reward.")
        return 500
    
    return 0

prev_hp = None

# brain.py

def calculate_battle_rewards(state, prev_state):
    if (prev_state is None):
        return 0  # No previous state to compare with
    if not prev_state or 'enemyHP' not in prev_state or 'enemyHP' not in state:
        return 0
    
    if (state['battleType'] == 4):
        return 0 #return 0 if it's a wild. we may apply something here later once time penalty is implmented
        
    

    print('Calculating battle rewards...')
    reward = 0
    
    # 1. DAMAGE DEALT REWARD (Positive)
    # We want to reward the AI for making the enemy HP go down.
    if state['enemyHP'] < prev_state['enemyHP']:
        damage = prev_state['enemyHP'] - state['enemyHP']
        reward += (damage/prev_state['enemyMaxHP'] * 15) # High incentive to attack
        print(f"Direct Hit! Dealt {damage} damage. Reward: +{damage/prev_state['enemyMaxHP'] * 15}")

    # 2. SURVIVAL PENALTY (Negative)
    # We want the AI to avoid getting hit.
    if state['currHP'] < prev_state['currHP']:
        loss = prev_state['currHP'] - state['currHP']
        reward -= (loss/prev_state['maxHP'] * 10) 
        print(f"Taken Damage! Lost {loss} HP. Penalty: -{loss/prev_state['maxHP'] * 10}")

    # 3. KNOCKOUT BONUS
    # If enemy HP hits 0, that's a huge win.
    if state['enemyHP'] == 0 and prev_state['enemyHP'] > 0:
        reward += 1000
        print("Enemy Fainted! Massive Bonus: +1000")

    # # 4. LEVEL UP (MAX HP PROXY)
    # if state['maxHP'] > prev_state['maxHP'] and prev_state['maxHP'] > 0:
    #     reward += 5000
    #     print("LEVEL UP! Progress Bonus: +5000")

    return reward

prev_max_hp = 0

def calculate_progress_reward(state):
    print('Calculating progress reward...')
    global prev_max_hp
    current_max_hp = state.get('maxHP', 0)
    reward = 0

    # Initialize on first run
    if prev_max_hp == 0:
        prev_max_hp = current_max_hp
        return 0

    # Detection of Level Up
    if current_max_hp > prev_max_hp:
        # A jump in Max HP is a definitive Level Up
        reward = 5000 
        print(f"LEVEL UP DETECTED! Max HP: {prev_max_hp} -> {current_max_hp}. Reward: {reward}")
    
    prev_max_hp = current_max_hp
    return reward

map_buffer = []
current_confirmed_map = "3-1"

def update_brain(state):
    global total_reward
    global previous_state
    previous_reward = total_reward

    # 2. Calculate Rewards
    explorationReward = calculate_exploration_reward(state)
    if explorationReward > 0:
        total_reward += explorationReward  # Exploration bonus
        explorationReward = 0  # Reset after applying
    
    battleRewards = calculate_battle_rewards(state, previous_state)
    if battleRewards != 0:
        total_reward += battleRewards  # Your existing logic
        battleRewards = 0  # Reset after applying

    progressReward = calculate_progress_reward(state)
    if progressReward != 0:
        total_reward += progressReward  # Your existing logic
        progressReward = 0  # Reset after applying
    
    # 3. Decide next action based on rewards
    # (This is where you'd pass 'reward' to your RL model)
    print(f"Frame Reward: {total_reward - previous_reward} | Total Reward: {total_reward}")
    previous_state = state

def parse_state(data_string):
    """Turns 'X:10,Y:20,InBattle:0,Dialogue:1' into a Python dictionary"""
    state = {}
    try:
        # Split by comma, then split each pair by the colon
        pairs = data_string.strip().split(',')
        for pair in pairs:
            key, value = pair.split(':')
            state[key] = int(value) # Convert the numbers to actual integers
        return state
    except Exception as e:
        print(f"Parsing error: {e} on data: {data_string}")
        return None
    

last_position = {"X": 0, "Y": 0, "mapBank": 0, "mapID": 0}

def decide_overworld_action(state):
    global last_position
    last_position = state.copy()

    #if is_character_stuck(state):
        # If stuck, pick a random direction to try and clear the obstacle
    return random.choice(["Up", "Down", "Left", "Right"])
    # Otherwise, head toward a goal (e.g., walk Right to leave Pallet Town)
    # if state['X'] < 20:
    #     return "Right"
    # else:
    #     return "Up"

def decide_action(state_data):
    # Example state_data: {"X": 10, "Y": 15, "InBattle": 0, "Dialogue": 1}
    print('battleMenu:', state_data.get('battleMenu'))
    print('cursorSlot:', state_data.get('cursorSlot'))
    # 1. Priority: Clear Text
    if state_data and state_data.get('Dialogue') == 1:
        return "B"
    
    # 2. Battle Logic
    if state_data and state_data.get('InBattle') == 1:
        return get_battle_input(state_data)
        
    # 3. Exploration Logic (Pathfinding)
    return decide_overworld_action(state_data)

# Create a persistent target outside your loop so it stays the same
# until the move is actually executed.
target_move = None 

battle_frame_counter = 0
target_move_slot = None
ACTION_THRESHOLD = 30 # Act every 30 frames (0.5 seconds at 60fps)

MAIN_MENU = 1  # Verify if 1 is your Fight/Bag/Run screen
MOVE_MENU = 2  # Your logs confirmed 2 is Move Selection

def get_battle_input(state_data):
    global battle_frame_counter, target_move_slot
    
    # # 1. Cooldown logic
    # battle_frame_counter += 1
    # if battle_frame_counter < 5: # Increased to 40 for stability
    #     return "None"
    
    battle_frame_counter = 0
    
    menu = state_data.get('battleMenu')
    cursor = state_data.get('cursorSlot') 

    # CASE: Main Battle Menu (Fight/Bag/Pokemon/Run)
    if menu == 1:
        target_move_slot = None 
        print("At Main Menu: Pressing A to enter Fight")
        return "A"

    # CASE: Move Selection (Confirmed as 2 by your logs)
    elif menu == 2:
        if target_move_slot is None:
            target_move_slot = random.randint(0, 3)
            print(f"New Turn: Targeting Move Slot {target_move_slot}")

        if cursor == target_move_slot:
            print(f"Confirmed Slot {target_move_slot}! Pressing A.")
            # target_move_slot = None # Keep the target until menu changes
            return "A"
        else:
            action = navigate_to_target(cursor, target_move_slot)
            print(f"Navigating: {action} (Current: {cursor}, Target: {target_move_slot})")
            return action
        
    elif menu == 4 or menu == 0 or menu == 5:
        target_move_slot = None
        return "A"  # Continue through dialogue or results

    # IMPORTANT: Do not return "A" here. Return "None".
    # This prevents mashing during transitions or text boxes.
    return "None"

def navigate_to_target(current, target):
    # Grid: 0=TL, 1=TR, 2=BL, 3=BR
    if current == 0: return "Right" if target in [1, 3] else "Down"
    if current == 1: return "Left" if target in [0, 2] else "Down"
    if current == 2: return "Up" if target in [0, 1] else "Right"
    if current == 3: return "Up" if target in [0, 2] else "Left"
    return "A"

def start_brain():
    global last_position
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Brain active. Waiting for BizHawk on {PORT}...")
        
        conn, addr = s.accept()
        with conn:
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
                update_brain(state_data)
                #print('battle mode: ', state_data.get('battleType'))
                command = decide_action(state_data) + '\n'
                conn.sendall(command.encode('utf-8'))                

if __name__ == "__main__":
    start_brain()
