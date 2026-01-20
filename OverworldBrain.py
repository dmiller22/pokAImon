import random

__all__ = ["OverworldBrain"]

class OverworldBrain:
    def __init__(self):
        self.visited_maps = set()
        self.prev_hp = None
        self.prev_max_hp = 0
        self.prev_lvl_total = 0
        self.map_buffer = []
        self.current_confirmed_map = "3-1"
        self.last_position = None

    def calculate_exploration_reward(self, state):
        bank = state.get('mapBank')
        map_num = state.get('mapID')
        map_key = f"{bank}-{map_num}"
        if map_key not in self.visited_maps:
            self.visited_maps.add(map_key)
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

        if self.prev_hp is None:
            self.prev_hp = state['currHP']
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
        return reward

    def decide_overworld_action(self, state):
        self.last_position = state.copy() if isinstance(state, dict) else None
        if not state:
            return random.choice(["Up", "Down", "Left", "Right"])
        if state.get('needsClick', 0) != 0:
            return "A"
        return random.choice(["Up", "Down", "Left", "Right"])