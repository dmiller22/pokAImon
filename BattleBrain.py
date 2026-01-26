import random

__all__ = ["BattleBrain"]

class BattleBrain:
    TYPE_MAP = {
        0: "Normal", 1: "Fighting", 2: "Flying", 3: "Poison", 4: "Ground",
        5: "Rock", 6: "Bug", 7: "Ghost", 8: "Steel", 9: "Mystery",
        10: "Fire", 11: "Water", 12: "Grass", 13: "Electric", 14: "Psychic",
        15: "Ice", 16: "Dragon", 17: "Dark"
    }

    def __init__(self):
        self.battle_frame_counter = 0
        self.target_move_slot = None

    def calculate_battle_rewards(self, state, prev_state):
        if prev_state is None or 'currHP' not in state:
            return 0 
        
        reward = 0
        
        # 1. SURVIVAL PENALTY
        curr_hp = state.get('currHP', 0)
        prev_hp = prev_state.get('currHP', 0)
        if curr_hp < prev_hp:
            loss = prev_hp - curr_hp
            reward -= (loss / max(1, prev_state.get('maxHP', 20))) * 10
            print(f"Player took {loss} damage.")

        # 2. ENEMY PROGRESSION
        for i in range(1, 7):
            hp_key = 'enemyHP' if i == 1 else f'enemy{i}HP'
            max_hp_key = 'enemyMaxHP' if i == 1 else f'enemy{i}MaxHP'
            
            e_curr = state.get(hp_key, 0)
            e_prev = prev_state.get(hp_key, 0)
            e_max = prev_state.get(max_hp_key, 1)

            # CHECK A: DAMAGE (Apply this if HP dropped at all)
            if e_curr < e_prev:
                damage = e_prev - e_curr
                dmg_reward = (damage / e_max) * 150
                reward += dmg_reward
                print(f"Dealt {damage} damage to Enemy {i}. Reward: +{dmg_reward}")

            # CHECK B: KNOCKOUT (Independent check)
            if e_prev > 0 and e_curr == 0:
                reward += 250
                print(f"!!! KNOCKOUT DETECTED !!! +250")

        return reward

    def navigate_to_target(self, current, target):
        # Grid: 0=TL, 1=TR, 2=BL, 3=BR
        if current == 0: return "Right" if target in [1, 3] else "Down"
        if current == 1: return "Left" if target in [0, 2] else "Down"
        if current == 2: return "Up" if target in [0, 1] else "Right"
        if current == 3: return "Up" if target in [0, 2] else "Left"
        return "A"