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

previous_state = None
total_reward = 0

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

    # 3. Decide next action based on rewards
    # (This is where you'd pass 'reward' to your RL model)
    if total_reward != previous_reward:
        print(f"Frame Reward: {total_reward - previous_reward} | Total Reward: {total_reward}")
    # Log a filtered overworld record to reduce noise
    overworld_record = filtered_overworld_record(state, previous_state)
    overworldLogger.log(overworld_record, total_reward, total_reward - previous_reward)

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
                # SPECIAL CASE: currentInput is a string, don't convert to int
                elif key == "currentInput":
                    state[key] = value
                else:
                    # Standard integer conversion for everything else
                    state[key] = int(value)
                    
        return state
    except Exception as e:
        print(f"Parsing error: {e} on data: {data_string}")
        return None


# Selective logging filters to reduce noise in the two log files
OVERWORLD_KEYS = {"X","Y","InBattle","Dialogue","mapBank","mapID","currHP","maxHP",
                  "pokemonLvl","poke2lvl","poke3lvl","poke4lvl","poke5lvl","poke6lvl",
                  "inMenu","needsClick","currentInput","move1PP","move2PP","move3PP","move4PP"}

BATTLE_KEYS = {"InBattle","battleMenu","cursorSlot","battleType","currHP","maxHP",
               "enemyHP","enemyMaxHP","enemy2HP","enemy2MaxHP","enemy3HP","enemy3MaxHP",
               "enemy4HP","enemy4MaxHP","enemy5HP","enemy5MaxHP","enemy6HP","enemy6MaxHP",
               "moves","move1PP","move2PP","move3PP","move4PP","e_type1","e_type2","currentInput"}


def filtered_overworld_record(state, previous_state):
    rec = {k: state[k] for k in OVERWORLD_KEYS if k in state}
    # Include moves list (and thus implicitly move IDs) when it changed or on first record
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
    if include_moves and "moves" in state:
        rec["moves"] = state["moves"]
    return rec


def filtered_battle_record(state, previous_state):
    rec = {k: state[k] for k in BATTLE_KEYS if k in state}
    # Only include position/map on battle start to avoid repeating it every frame
    if previous_state is None or (previous_state.get("InBattle") == 0 and state.get("InBattle") == 1):
        for k in ("X","Y","mapBank","mapID"):
            if k in state:
                rec[k] = state[k]
    return rec

def main():
    global last_position, total_reward, previous_state
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        s.bind((HOST, PORT))
        s.listen()
        print(f"Brain active. Waiting for BizHawk on {PORT}...")

        try:
            while True:
                try:
                    conn, addr = s.accept()
                    conn.settimeout(1.0)
                    with conn:
                        while True:
                            try:
                                raw_data = conn.recv(1024)
                                if not raw_data:
                                    break
                                state = parse_state(raw_data.decode('utf-8'))
                                if state is None or state == previous_state:
                                    continue
                                print(f"Received State: {state}")
                                if state['InBattle'] == 1:
                                    action = battle.get_battle_input(state)
                                    update_brain_battle(state)
                                else:
                                    action = explorer.decide_overworld_action(state)
                                    update_brain_overworld(state)
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