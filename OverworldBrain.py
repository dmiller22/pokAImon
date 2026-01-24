import random
import os

__all__ = ["OverworldBrain"]
MAPS_FILE = "visited_maps.txt"
START_MAP = "2"

class OverworldBrain:
    def load_visited_maps(self):
        if os.path.exists(MAPS_FILE):
            with open(MAPS_FILE, "r") as f:
                # Read lines and strip the newline characters
                return set(line.strip() for line in f if line.strip())
        return set()

    def save_visited_maps(self, visited_set):
        with open(MAPS_FILE, "w") as f:
            for map_name in sorted(list(visited_set)):
                f.write(f"{map_name}\n")

    def __init__(self):
        self.visited_maps = self.load_visited_maps()
        self.prev_hp = None
        self.prev_max_hp = 0
        self.prev_lvl_total = 0
        self.prev_first_pokemon_id = None
        self.prev_active_pokemon = None
        self.map_buffer = []
        self.current_confirmed_map = 2
        self.last_position = None
        self.prev_badge_data = None
        self.prev_move1_pp = None
        self.prev_move2_pp = None
        self.prev_move3_pp = None
        self.prev_move4_pp = None        
    

    def calculate_exploration_reward(self, state):        
        mapId = state.get('mapLocationId')
        map_key = f"{mapId}"
        if map_key not in self.visited_maps:
            self.visited_maps.add(map_key)
            self.save_visited_maps(self.visited_maps)
            if map_key != START_MAP:
                print(f"NEW AREA DISCOVERED: {map_key}! +500 Reward.")
                return 500
        return 0
    
    def calculate_hp_reward(self, state, just_transitioned_from_battle):
        # 2. SURVIVAL PENALTY (Negative)
        # We want the AI to avoid losing hp to poison damage.
        reward = 0

        if just_transitioned_from_battle:
            self.prev_hp = state['currHP']
            return 0

        # 3. HP CHANGE REWARD/PENALTY - Don't count if pokemon switched
        if self.prev_hp is None or (self.prev_first_pokemon_id != state.get('partyFirstPokemonID') and state['InBattle'] == 0 ) or (self.prev_active_pokemon != state.get('userActivePokemon') and state['InBattle'] == 1):
            self.prev_hp = state['currHP']
            self.prev_first_pokemon_id = state.get('partyFirstPokemonID')
            self.prev_active_pokemon = state.get('userActivePokemon')
            return 0
        if state['currHP'] < self.prev_hp:
            loss = self.prev_hp - state['currHP']
            reward -= (loss/self.prev_max_hp * 10)
            print(f"Taken Damage! Lost {loss} HP. Penalty: -{loss/self.prev_max_hp * 10}")

        elif state['currHP'] > self.prev_hp:
            gain = state['currHP'] - self.prev_hp
            reward += (gain/self.prev_max_hp * 5)
            print(f"Healed! Gained {gain} HP. Reward: +{gain/self.prev_max_hp * 5}")

        self.prev_hp = state['currHP']
        self.prev_max_hp = state['maxHP']
        return reward
    
    def calculate_pp_reward(self, state):
        # PP REWARD/PENALTY
        reward = 0

        if self.prev_move1_pp is None:
            self.prev_move1_pp = state['move1PP']
            self.prev_move2_pp = state['move2PP']
            self.prev_move3_pp = state['move3PP']
            self.prev_move4_pp = state['move4PP']
            return 0

        if ( state['move1PP'] == 0 and self.prev_move1_pp > 0):
            reward -= 20
            print(f"Move 1 PP Depleted! Penalty: -20")
        if (state['move2PP'] == 0 and self.prev_move2_pp > 0):
            reward -= 20
            print(f"Move 2 PP Depleted! Penalty: -20")
        if (state['move3PP'] == 0 and self.prev_move3_pp > 0):
            reward -= 20
            print(f"Move 3 PP Depleted! Penalty: -20")
        if (state['move4PP'] == 0 and self.prev_move4_pp > 0):
            reward -= 20
            print(f"Move 4 PP Depleted! Penalty: -20")

        if state['move1PP'] > self.prev_move1_pp:
            gain = state['move1PP'] - self.prev_move1_pp
            reward += gain
            print(f"Move 1 PP Restored by {gain}! Reward: +{gain}")
        if state['move2PP'] > self.prev_move2_pp:
            gain = state['move2PP'] - self.prev_move2_pp
            reward += gain
            print(f"Move 2 PP Restored by {gain}! Reward: +{gain}")
        if state['move3PP'] > self.prev_move3_pp:
            gain = state['move3PP'] - self.prev_move3_pp
            reward += gain
            print(f"Move 3 PP Restored by {gain}! Reward: +{gain}")
        if state['move4PP'] > self.prev_move4_pp:
            gain = state['move4PP'] - self.prev_move4_pp
            reward += gain
            print(f"Move 4 PP Restored by {gain}! Reward: +{gain}")

        self.prev_move1_pp = state['move1PP']
        self.prev_move2_pp = state['move2PP']
        self.prev_move3_pp = state['move3PP']
        self.prev_move4_pp = state['move4PP']

        return reward

    # 3. PROGRESS REWARD (Positive) calculated as total level increase across party
    def calculate_progress_reward(self, state):
        current_poke1lvl = state.get('pokemonLvl', 0)
        current_poke2lvl = state.get('poke2lvl', 0)
        current_poke3lvl = state.get('poke3lvl', 0)
        current_poke4lvl = state.get('poke4lvl', 0)
        current_poke5lvl = state.get('poke5lvl', 0)
        current_poke6lvl = state.get('poke6lvl', 0)
        current_lvl_total = current_poke1lvl + current_poke2lvl + current_poke3lvl + current_poke4lvl + current_poke5lvl + current_poke6lvl

        reward = 0
        if self.prev_lvl_total == 0:
            self.prev_lvl_total = current_lvl_total
            return 0
        if current_lvl_total > self.prev_lvl_total:
            reward = 1000*(current_lvl_total - self.prev_lvl_total)
            print(f"LEVEL UP DETECTED! Level: {self.prev_lvl_total} -> {current_lvl_total}. Reward: {reward}")
        self.prev_lvl_total = current_lvl_total

        # 4. BADGE REWARD (Positive)
        badge_reward = 0
        if self.prev_badge_data is not None and self.prev_badge_data != state.get('badgeData'):
            badge_reward = state.get('badgeData') * 5000
            reward += badge_reward
            print(f"BADGE REWARD DETECTED! Badges: {state.get('badgeData')}. Reward: {badge_reward}")
        self.prev_badge_data = state.get('badgeData')

        return reward

    def decide_overworld_action(self, state):
        self.last_position = state.copy() if isinstance(state, dict) else None
        if not state:
            return random.choice(["Up", "Down", "Left", "Right"])
        if state.get('needsClick', 0) != 0:
            return "A"
        return random.choice(["Up", "Down", "Left", "Right"])