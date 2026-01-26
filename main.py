import socket
import time
import json
import os
import re
import torch
import random
import numpy as np
import torch.nn.functional as F
from datetime import datetime, timezone
from pokelogger import PokeLogger, logger
from OverworldBrain import OverworldBrain
from BattleBrain import BattleBrain
from PokeBrain import PokeBrain
from ExperienceReplay import ExperienceReplay

# Configuration
HOST = '127.0.0.1'
PORT = 65432

replay_buffer = ExperienceReplay(capacity=10000)
replay_buffer_battle = ExperienceReplay(capacity=5000)

battleLogger = PokeLogger(filename="pokebrain_battle.log", max_bytes=10*1024*1024)
overworldLogger = PokeLogger(filename="pokebrain_overworld.log", max_bytes=10*1024*1024)

# Create the model structure
overworld_model = PokeBrain(input_size=9, num_actions=9)
battle_model = PokeBrain(input_size=11, num_actions=9)

# Hyperparameters for RL
GAMMA = 1  # Discount factor: how much we value future rewards vs immediate ones
BATCH_SIZE = 128
optimizer_overworld = torch.optim.Adam(overworld_model.parameters(), lr=0.0005)

# Hyperparameters for RL
GAMMA_BATTLE = 1  # Discount factor: how much we value future rewards vs immediate ones
BATCH_SIZE_BATTLE = 16
optimizer_battle = torch.optim.Adam(battle_model.parameters(), lr=0.0005)

# ONLY load if the file exists. 
# This way, it uses your "Evolved" model from yesterday.
if os.path.exists("overworld_model_evolved_placeholder.pth"):
    overworld_model.load_state_dict(torch.load("overworld_model_evolved.pth"))
    print("Loaded evolved brain.")
elif os.path.exists("overworld_model.pth"):
    checkpoint_overworld = torch.load("overworld_model.pth")
    if isinstance(checkpoint_overworld, dict) and "model_state_dict" in checkpoint_overworld:
        overworld_model.load_state_dict(checkpoint_overworld["model_state_dict"])
        # OPTIONAL: Resume your Epsilon and Optimizer too!
        optimizer_overworld.load_state_dict(checkpoint_overworld["optimizer_state_dict"])
        epsilon = checkpoint_overworld.get("epsilon", 0.1)     
        print("Resumed from advanced checkpoint.")

    else:
        overworld_model.load_state_dict(torch.load("overworld_model.pth"))
        print("Loaded initial overworld brain.")

    overworld_model.train()

if os.path.exists("battle_model_evolved_placeholder.pth"):
    battle_model.load_state_dict(torch.load("battle_model_evolved.pth"))
    print("Loaded evolved battle brain.")
elif os.path.exists("battle_model.pth"):
    checkpoint_battle = torch.load("battle_model.pth")
    if isinstance(checkpoint_battle, dict) and "model_state_dict" in checkpoint_battle:
        battle_model.load_state_dict(checkpoint_battle["model_state_dict"])
        # OPTIONAL: Resume your Epsilon and Optimizer too!
        optimizer_battle.load_state_dict(checkpoint_battle["optimizer_state_dict"])
        epsilon = checkpoint_battle.get("epsilon", 0.1)     
        print("Resumed from advanced battle checkpoint.")
    
    battle_model.train()
# battle_model = PokeBrain(input_size=11, num_actions=9)
# battle_model.load_state_dict(torch.load("battle_model.pth"))
# battle_model.eval()

previous_state = None
total_reward = 0

# Initialize both
explorer = OverworldBrain()
battle = BattleBrain()

ACTION_MAP = {0: "None", 1: "Up", 2: "Down", 3: "Left", 4: "Right", 5: "A", 6: "B", 7: "Start", 8: "Select"}
EPSILON_OVERWORLD = 1 # 100% chance to do something random
EPSILON_BATTLE = 0.25 # 25% chance to do something random in battle

import numpy as np

# Global settings for exploration
epsilon = 1.00        # Start high (if starting from scratch) or low (if pre-trained)
epsilon_min = 1.00   # Always keep 10% randomness to prevent getting stuck
epsilon_decay = 1.000 # decay per action taken

def get_action_epsilon_greedy(model, state_vector, num_actions=9):
    global epsilon
    
    # 1. Roll the dice: Explore or Exploit?
    if np.random.rand() <= epsilon:
        # EXPLORE: Pick a random button
        action_index = np.random.randint(0, num_actions)
    else:
        # EXPLOIT: Use the brain
        with torch.no_grad():
            state_t = torch.FloatTensor(state_vector).unsqueeze(0)
            q_values = model(state_t)
            action_index = torch.argmax(q_values).item()
    
    # 2. Decay epsilon so we explore less over time
    if epsilon > epsilon_min:
        epsilon *= epsilon_decay
        
    return action_index

def train_step_overworld(model, replay_buffer):
    if len(replay_buffer) < BATCH_SIZE:
        return # Not enough memories to learn yet

    # 1. Sample a random batch of memories
    states, actions, rewards, next_states = replay_buffer.sample(BATCH_SIZE)

    # 2. Get current Q-values from the model
    # (What the AI *thought* would happen)
    current_q_values = model(states).gather(1, actions.unsqueeze(1))

    # 3. Get the maximum Q-value for the NEXT state
    # (The AI's best guess for the future)
    with torch.no_grad():
        next_q_values = model(next_states).max(1)[0]
        expected_q_values = rewards + (GAMMA * next_q_values)

    # 4. Compute Loss (Difference between thought and reality)
    loss = F.smooth_l1_loss(current_q_values.squeeze(), expected_q_values)

    # 5. Optimize the model
    optimizer_overworld.zero_grad()
    loss.backward()
    optimizer_overworld.step()

    return loss.item()

def train_step_battle(model, replay_buffer_battle):
    if len(replay_buffer_battle) < BATCH_SIZE_BATTLE:
        return # Not enough memories to learn yet

    # 1. Sample a random batch of memories
    states, actions, rewards, next_states = replay_buffer_battle.sample(BATCH_SIZE_BATTLE)
    # 2. Get current Q-values from the model
    # (What the AI *thought* would happen)
    current_q_values = model(states).gather(1, actions.unsqueeze(1))

    # 3. Get the maximum Q-value for the NEXT state
    # (The AI's best guess for the future)
    with torch.no_grad():
        next_q_values = model(next_states).max(1)[0]
        expected_q_values = rewards + (GAMMA_BATTLE * next_q_values)

    # 4. Compute Loss (Difference between thought and reality)
    loss = F.smooth_l1_loss(current_q_values.squeeze(), expected_q_values)

    # 5. Optimize the model
    optimizer_battle.zero_grad()
    loss.backward()
    optimizer_battle.step()

    return loss.item()

def get_action(state):
    global prev_state_vec_battle, prev_state_vec_overworld, prev_action_battle, prev_action_overworld, prev_state_model_battle, prev_state_model_overworld

    is_battle = state.get("InBattle", 0) == 1

    # 2. Otherwise, use the appropriate brain
    if is_battle:

        # Use Battle Normalization from earlier
        # Use this for vector in data_processing AND vec in main.py
        vec = [
            state.get('currHP', 0) / 100,
            state.get('maxHP', 0) / 100,
            state.get('enemyHP', 0) / 100,
            state.get('enemyMaxHP', 0) / 100,
            state.get('userActivePokemon', 0) / 500, # Use same divisor as training (500)
            state.get('battleMenu', 0) / 10,
            state.get('cursorSlot', 0) / 4,
            state.get('move1PP', 0) / 40,
            state.get('move2PP', 0) / 40,
            state.get('move3PP', 0) / 40,
            state.get('move4PP', 0) / 40
        ]
        model = battle_model
        if prev_state_vec_battle is not None:
            frame_reward = state.get('frame_reward', 0)
            replay_buffer_battle.push(prev_state_vec_battle, prev_action_battle, frame_reward, vec)
    else:
        # Use Overworld Normalization
        vec = [
            state.get('X', 0) / 255,
            state.get('Y', 0) / 255,
            state.get('mapLocationId', 0) / 255,
            state.get('currHP', 0) / 100,
            state.get('maxHP', 0) / 100,
            state.get('inMenu', 0),
            state.get('needsClick', 0),
            state.get('Dialogue', 0),
            state.get('badgeData', 0) / 8
        ]
        model = overworld_model
        if prev_state_vec_overworld is not None:
            frame_reward = state.get('frame_reward', 0)
            replay_buffer.push(prev_state_vec_overworld, prev_action_overworld, frame_reward, vec)

    # 4. Decide the NEXT action (using epsilon-greedy for exploration)
    action_index = get_action_epsilon_greedy(model, vec, num_actions=9)
    action_name = ACTION_MAP[action_index]

    if is_battle:
        prev_state_vec_battle = vec
        prev_state_model_battle = state
        prev_action_battle = action_index
    else:
        prev_state_vec_overworld = vec
        prev_state_model_overworld = state
        prev_action_overworld = action_index

    if len(replay_buffer) >= 8000 and not is_battle:
        # Sample a batch and perform a training step
        train_step_overworld(model, replay_buffer)
    elif len(replay_buffer_battle) >= 2000 and not is_battle:
        train_step_battle(model, replay_buffer_battle)

    if state['frameCounter'] % 2900 == 0:
        checkpoint = {
            'model_state_dict': overworld_model.state_dict(),
            'optimizer_state_dict': optimizer_overworld.state_dict(),
            'epsilon': epsilon, # Save its current curiosity level!
            'frame_count': state['frameCounter']
        }
        checkpoint_battle = {
            'model_state_dict': battle_model.state_dict(),
            'optimizer_state_dict': optimizer_battle.state_dict(),
            'epsilon': epsilon, # Save its current curiosity level!
            'frame_count': state['frameCounter']
        }
        torch.save(checkpoint, "overworld_model_evolved.pth")
        torch.save(checkpoint_battle, "battle_model_evolved.pth")
        print("Checkpoint saved: The brain is growing!")

    return action_name
    # # Inference
    # with torch.no_grad():
    #     tensor = torch.FloatTensor(vec).unsqueeze(0)
    #     output = model(tensor)
    #     action_id = torch.argmax(output).item()
    
    # return ACTION_MAP[action_id]

def normalize_overworld(s):
    """
    Transforms Overworld state into a vector of 10 features.
    Matches 'pokebrain_overworld.log' structure.
    """
    return [
        s.get('X', 0) / 255.0,           # Coordinates 
        s.get('Y', 0) / 255.0,
        s.get('mapLocationId', 0) / 255.0,       # Map Identity 
        s.get('currHP', 0) / 100.0,      # Vitality [cite: 63]
        s.get('maxHP', 0) / 100.0,
        s.get('inMenu', 0),              # Binary UI state [cite: 91]
        s.get('needsClick', 0),          # Prompt state [cite: 161]
        s.get('Dialogue', 0),            # Conversation flag [cite: 151]
        s.get('badgeData', 0) / 8.0      # Progress [cite: 111]
    ]

def normalize_battle(s):
    """
    Transforms Battle state into a vector of 11 features.
    Matches 'pokebrain_battle.log' structure.
    """
    return [
        s.get('currHP', 0) / 100.0,       # Your Health 
        s.get('maxHP', 0) / 100.0,
        s.get('enemyHP', 0) / 100.0,     # Enemy Health 
        s.get('enemyMaxHP', 0) / 100.0,
        s.get('userActivePokemon', 0) / 411.0, # Species ID 
        s.get('battleMenu', 0) / 10.0,   # Current Menu Layer [cite: 507]
        s.get('cursorSlot', 0) / 4.0,    # Cursor Index [cite: 508]
        s.get('move1PP', 0) / 40.0,      # Resource Management 
        s.get('move2PP', 0) / 40.0,
        s.get('move3PP', 0) / 40.0,
        s.get('move4PP', 0) / 40.0
    ]

def load_max_move_id():
    """Parse MoveData.lua to find the largest move id present.
    Returns an int max id, or None if the file can't be read/parsed.
    """
    try:
        base = os.path.dirname(__file__)
        path = os.path.join(base, 'MoveData.lua')
        with open(path, 'r', encoding='utf-8') as f:
            data = f.read()
        ids = [int(m) for m in re.findall(r'id\s*=\s*"(\d+)"', data)]
        if not ids:
            return None
        return max(ids)
    except Exception as e:
        print(f"Warning: could not determine max move id from MoveData.lua: {e}")
        return None


# Largest valid move id found in MoveData.lua (used to filter bad frames)
MAX_MOVE_ID = load_max_move_id()

def update_brain_battle(state):
    global total_reward
    global previous_state
    previous_reward = total_reward    

    battleRewards = battle.calculate_battle_rewards(state, previous_state)
    if battleRewards != 0:
        total_reward += battleRewards  # Your existing logic
        battleRewards = 0  # Reset after applying

    if (state.get('frameCounter') % 1000) == 0:
        print(f'frameCounter: {state.get("frameCounter")}, total_reward: {total_reward}')
    if (state.get('frameCounter') is not None and state.get('frameCounter') >= 3000):
        total_reward -= 15  # Time penalty to encourage faster gameplay
        print("Time Penalty Applied: -15")
    
    # 3. Decide next action based on rewards
    # (This is where you'd pass 'reward' to your RL model)
    if total_reward != previous_reward:
        print(f"Frame Reward: {total_reward - previous_reward} | Total Reward: {total_reward}")

    # Log a filtered battle record to reduce noise
    battle_record = filtered_battle_record(state, previous_state)
    battleLogger.log(battle_record, total_reward, total_reward - previous_reward)

    previous_state = state

def update_brain_overworld(state):
    global total_reward
    global previous_state
    previous_reward = total_reward
    

    battleToOverworldFrame = state['InBattle'] == 0 and previous_state and previous_state['InBattle'] == 1
    # 2. Calculate Rewards
    explorationReward = explorer.calculate_exploration_reward(state)
    if explorationReward > 0:
        total_reward += explorationReward  # Exploration bonus
        explorationReward = 0  # Reset after applying

    progressReward = explorer.calculate_progress_reward(state)
    if progressReward != 0:
        total_reward += progressReward  # Your existing logic
        progressReward = 0  # Reset after applying

    # 3. HP Reward (only if not just transitioned from battle)
    hpReward = explorer.calculate_hp_reward(state, battleToOverworldFrame)
    if hpReward != 0:
        total_reward += hpReward  # Your existing logic
        hpReward = 0  # Reset after applying

    # ppReward = explorer.calculate_pp_reward(state)
    # if ppReward != 0:
    #     total_reward += ppReward  # Your existing logic
    #     ppReward = 0  # Reset after applying

    if (state.get('frameCounter') % 1000) == 0:
        print(f'frameCounter: {state.get("frameCounter")}, total_reward: {total_reward}, epsilon: {epsilon:.4f}, maplocation: {state.get("mapLocationId")}')
    if (state.get('frameCounter') is not None and state.get('frameCounter') >= 3000):
        total_reward -= 15  # Time penalty to encourage faster gameplay
        print("Time Penalty Applied: -15")

    # 3. Decide next action based on rewards
    # (This is where you'd pass 'reward' to your RL model)
    if total_reward != previous_reward:
        print(f"Frame Reward: {total_reward - previous_reward} | Total Reward: {total_reward}")
    # Log a filtered overworld record to reduce noise
    overworld_record = filtered_overworld_record(state, previous_state)
    overworldLogger.log(overworld_record, total_reward, total_reward - previous_reward)

    previous_state = state

def parse_state(data_string):
    """Turns 'X:10,Y:20,moves:33|45|0|0' into a Python dictionary"""
    state = {}
    try:
        # Split by comma to get the "Key:Value" pairs
        pairs = data_string.strip().split(',')
        for pair in pairs:
            if ':' in pair:
                key, value = pair.split(':')
                
                # SPECIAL HANDLING FOR MOVES
                if key == "moves":
                    # Split the pipe string and convert each ID to an int
                    state[key] = [int(m) for m in value.split('|')]
                # SPECIAL CASE: currentInput is a string, don't convert to int
                elif key == "currentInput" or key == "last_direction":
                    state[key] = value
                else:
                    # Standard integer conversion for everything else
                    state[key] = int(value)
                    
        # Validate moves against MoveData.lua's known max move id to avoid logging corrupt frames
        if "moves" in state and MAX_MOVE_ID is not None:
            invalid = [m for m in state["moves"] if m is not None and m > MAX_MOVE_ID]
            if invalid:
                # print(f"Skipping frame due to invalid move ids {invalid} (max known {MAX_MOVE_ID})")
                return None

        return state
    except Exception as e:
        print(f"Parsing error: {e} on data: {data_string}")
        return None


# Selective logging filters to reduce noise in the two log files
OVERWORLD_KEYS = {"X","Y","InBattle","Dialogue","mapLocationId","currHP","maxHP",
                  "pokemonLvl","poke2lvl","poke3lvl","poke4lvl","poke5lvl","poke6lvl", "firstPokemonID",
                  "inMenu","needsClick","currentInput","move1PP","move2PP","move3PP","move4PP","badgeData"}

BATTLE_KEYS = {"InBattle","battleMenu","cursorSlot","battleType","userActivePokemon","currHP","maxHP",
               "enemyHP","enemyMaxHP","enemy2HP","enemy2MaxHP","enemy3HP","enemy3MaxHP",
               "enemy4HP","enemy4MaxHP","enemy5HP","enemy5MaxHP","enemy6HP","enemy6MaxHP",
               "moves","move1PP","move2PP","move3PP","move4PP","e_type1","e_type2","currentInput"}


def filtered_overworld_record(state, previous_state):
    # Determine if we should include the full moves list (preserve order)
    include_moves = False
    if "moves" in state:
        if previous_state is None:
            include_moves = True
        else:
            if state.get("moves") != previous_state.get("moves"):
                include_moves = True
    # Also include if any PP changed
    for i in range(1,5):
        key = f"move{i}PP"
        if state.get(key) != (previous_state.get(key) if previous_state else None):
            include_moves = True
            break

    # Build record by iterating `state` keys to preserve their original ordering
    rec = {}
    for k in state:
        if k in OVERWORLD_KEYS or (k == "moves" and include_moves):
            rec[k] = state[k]

    return rec


def filtered_battle_record(state, previous_state):
    rec = {k: state[k] for k in BATTLE_KEYS if k in state}
    # Only include position/map on battle start to avoid repeating it every frame
    if previous_state is None or (previous_state.get("InBattle") == 0 and state.get("InBattle") == 1):
        for k in ("X","Y","mapLocationId"):
            if k in state:
                rec[k] = state[k]
    return rec

def main():
    global last_position, total_reward, previous_state, prev_state_vec_overworld, prev_state_vec_battle, prev_action_overworld, prev_action_battle, prev_state_model_overworld, prev_state_model_battle
    MAPS_FILE = "visited_maps.txt"
    RESET_EXPLORATION = True # Set to True to wipe the map history
    if RESET_EXPLORATION and os.path.exists(MAPS_FILE):
        os.remove(MAPS_FILE)
        print("Map history wiped for a fresh run.")

    prev_state_vec_overworld = None
    prev_action_overworld = None
    prev_state_model_overworld = None
    prev_state_model_battle = None
    prev_state_vec_battle = None
    prev_action_battle = None
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        s.bind((HOST, PORT))
        s.listen()
        print(f"Brain active. Waiting for BizHawk on {PORT}...")

        try:
            buffer = ""
            while True:
                try:
                    conn, addr = s.accept()
                    conn.settimeout(1.0)
                    with conn:
                        while True:
                            try:
                                chunk = conn.recv(4096)
                                if not chunk:
                                    break

                                buffer += chunk.decode('utf-8')
                                while "\n" in buffer:
                                    line, buffer = buffer.split("\n", 1)

                                if line.strip():
                                    # 3. Parse only one frame at a time
                                    state = parse_state(line)
                                if state is None or state == previous_state:
                                    continue
                                
                                if state.get('InBattle', 0) == 1:
                                    update_brain_battle(state)
                                else:
                                    update_brain_overworld(state)
                                # print(f"Received State: {state}")
                                action = get_action(state) + "\n"
                                conn.sendall(action.encode('utf-8'))
                            except socket.timeout:
                                continue
                except socket.timeout:
                    continue
        except KeyboardInterrupt:
            print("Interrupted by user, shutting down...")
        finally:
            logger.close()
            battleLogger.close()
            overworldLogger.close()

if __name__ == "__main__":
    main()