import socket
import time
import random
import json
from datetime import datetime, timezone
from pokelogger import PokeLogger, logger
from OverworldBrain import OverworldBrain
from BattleBrain import BattleBrain

# Configuration
HOST = '127.0.0.1'
PORT = 65432

battleLogger = PokeLogger(filename="pokebrain_battle.log", max_bytes=10*1024*1024)
overworldLogger = PokeLogger(filename="pokebrain_overworld.log", max_bytes=10*1024*1024)

# Initialize both
explorer = OverworldBrain()
battle = BattleBrain()

def update_brain_battle(state):
    global total_reward
    global previous_state
    previous_reward = total_reward    

    battleRewards = battle.calculate_battle_rewards(state, previous_state)
    if battleRewards != 0:
        total_reward += battleRewards  # Your existing logic
        battleRewards = 0  # Reset after applying
    
    # 3. Decide next action based on rewards
    # (This is where you'd pass 'reward' to your RL model)
    print(f"Frame Reward: {total_reward - previous_reward} | Total Reward: {total_reward}")

    battleLogger.log(state, total_reward, total_reward - previous_reward)

    previous_state = state

def update_brain_overworld(state):
    global total_reward
    global previous_state
    previous_reward = total_reward    

    # 2. Calculate Rewards
    explorationReward = explorer.calculate_exploration_reward(state)
    if explorationReward > 0:
        total_reward += explorationReward  # Exploration bonus
        explorationReward = 0  # Reset after applying

    progressReward = explorer.calculate_progress_reward(state)
    if progressReward != 0:
        total_reward += progressReward  # Your existing logic
        progressReward = 0  # Reset after applying
    
    # 3. Decide next action based on rewards
    # (This is where you'd pass 'reward' to your RL model)
    print(f"Frame Reward: {total_reward - previous_reward} | Total Reward: {total_reward}")

    overworldLogger.log(state, total_reward, total_reward - previous_reward)

    previous_state = state

def decide_action(state_data):
    # Example state_data: {"X": 10, "Y": 15, "InBattle": 0, "Dialogue": 1}
    # 1. Priority: Clear Text
    if state_data and state_data.get('Dialogue') == 1:
        return "B"
    
    # 2. Battle Logic
    if state_data and state_data.get('InBattle') == 1:
        return battle.get_battle_input(state_data)
        
    # 3. Exploration Logic (Pathfinding)
    return explorer.decide_overworld_action(state_data)

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
                else:
                    # Standard integer conversion for everything else
                    state[key] = int(value)
                    
        return state
    except Exception as e:
        print(f"Parsing error: {e} on data: {data_string}")
        return None

def main():
    global last_position, total_reward
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Brain active. Waiting for BizHawk on {PORT}...")

        conn, addr = s.accept()
        with conn:
            try:
                while True:
                    raw_data = socket.receive()
                    state = parse_state(raw_data)

                    if (state is None or state == previous_state):
                        continue  # Skip this loop if parsing failed or no state change
                    
                    if state['InBattle'] == 1:
                        # Pass the specialized battle data to the Battle Brain
                        action = battle.get_battle_input(state)
                        update_brain_battle(state)
                    else:
                        # Pass coordinate/map data to the Overworld Brain
                        action = explorer.decide_overworld_action(state)
                        update_brain_overworld(state)
                        
                    socket.send(action)
            finally:
                logger.close()