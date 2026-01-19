import random

__all__ = ["OverworldBrain"]

class OverworldBrain:
    def __init__(self):
        self.visited_maps = set()
        self.prev_hp = None
        self.prev_max_hp = 0
        self.map_buffer = []
        self.current_confirmed_map = "3-1"
        self.last_position = None

    def calculate_exploration_reward(self, state):
        print('Calculating exploration reward...')
        bank = state.get('mapBank')
        map_num = state.get('mapID')
        map_key = f"{bank}-{map_num}"
        if map_key not in self.visited_maps:
            self.visited_maps.add(map_key)
            print(f"NEW AREA DISCOVERED: {map_key}! +500 Reward.")
            return 500
        return 0

    def calculate_progress_reward(self, state):
        print('Calculating progress reward...')
        current_max_hp = state.get('maxHP', 0)
        reward = 0
        if self.prev_max_hp == 0:
            self.prev_max_hp = current_max_hp
            return 0
        if current_max_hp > self.prev_max_hp:
            reward = 5000
            print(f"LEVEL UP DETECTED! Max HP: {self.prev_max_hp} -> {current_max_hp}. Reward: {reward}")
        self.prev_max_hp = current_max_hp
        return reward

    def decide_overworld_action(self, state):
        self.last_position = state.copy() if isinstance(state, dict) else None
        if not state:
            return random.choice(["Up", "Down", "Left", "Right"])
        if state.get('needsClick', 0) != 0:
            return "A"
        return random.choice(["Up", "Down", "Left", "Right"])