import torch
import torch.nn as nn
import torch.optim as optim

# Define the Brain
class PokeBrain(nn.Module):
    def __init__(self, input_size, num_actions):
        super(PokeBrain, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, num_actions)
        )

    def forward(self, x):
        return self.network(x)

def train_model(dataset_path, model_name, input_size):
    if (dataset_path == 'overworld_dataset.pt'): # Temporarily (maybe permanent later) disable overworld training
        return
    
    # Load data
    data = torch.load(dataset_path)
    X = data['X']
    y = data['y']
    
    model = PokeBrain(input_size, num_actions=9) # 9 possible buttons
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    print(f"Training {model_name}...")
    for epoch in range(100): # Run for 100 passes through the data
        optimizer.zero_grad()
        outputs = model(X)
        loss = criterion(outputs, y)
        loss.backward()
        optimizer.step()
        
        if (epoch + 1) % 20 == 0:
            print(f'Epoch [{epoch+1}/100], Loss: {loss.item():.4f}')

    torch.save(model.state_dict(), f"{model_name}.pth")
    print(f"Saved {model_name}.pth\n")

# Train both based on your vector sizes from the previous step
#train_model('overworld_dataset.pt', 'overworld_model', input_size=10)
#train_model('battle_dataset.pt', 'battle_model', input_size=11)