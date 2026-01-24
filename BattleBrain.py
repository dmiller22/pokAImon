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
        if (prev_state is None):
            return 0  # No previous state to compare with
        if not prev_state or 'enemyHP' not in prev_state or 'enemyHP' not in state:
            return 0
        
        reward = 0
        
        # 1. SURVIVAL PENALTY (Negative)
        # We want the AI to avoid getting hit.
        if state['currHP'] < prev_state['currHP']:
            loss = prev_state['currHP'] - state['currHP']
            reward -= (loss/prev_state['maxHP'] * 10)
            print(f"Taken Damage! Lost {loss} HP. Penalty: -{loss/prev_state['maxHP'] * 10}")

        if (state.get('battleType') == 4):
            return reward # don't reward attacking if it's a wild. we may apply something here later once time penalty is implmented

        # 2. DAMAGE DEALT REWARD (Positive)
        # We want to reward the AI for making the enemy HP go down.
        if state['enemyHP'] < prev_state['enemyHP']:
            damage = prev_state['enemyHP'] - state['enemyHP']
            reward += (damage/prev_state['enemyMaxHP'] * 15) # High incentive to attack
            print(f"Direct Hit! Dealt {damage} damage. Reward: +{damage/prev_state['enemyMaxHP'] * 15}")        

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

    def navigate_to_target(self, current, target):
        # Grid: 0=TL, 1=TR, 2=BL, 3=BR
        if current == 0: return "Right" if target in [1, 3] else "Down"
        if current == 1: return "Left" if target in [0, 2] else "Down"
        if current == 2: return "Up" if target in [0, 1] else "Right"
        if current == 3: return "Up" if target in [0, 2] else "Left"
        return "A"