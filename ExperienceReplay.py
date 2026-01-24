import random
import collections
import torch
import numpy as np

class ExperienceReplay:
    def __init__(self, capacity=10000):
        # deque automatically "pushes out" the oldest memories when it gets full
        self.buffer = collections.deque(maxlen=capacity)

    def push(self, state, action, reward, next_state):
        """Saves a transition."""
        self.buffer.append((state, action, reward, next_state))

    def sample(self, batch_size):
        """Randomly picks a batch of memories to learn from."""
        batch = random.sample(self.buffer, batch_size)
        state, action, reward, next_state = zip(*batch)
        
        return (
            torch.FloatTensor(np.array(state)),
            torch.LongTensor(action),
            torch.FloatTensor(reward),
            torch.FloatTensor(np.array(next_state)),
        )

    def __len__(self):
        return len(self.buffer)