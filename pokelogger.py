import json
import os
from datetime import datetime, timezone

class PokeLogger:
    def __init__(self, filename="pokebrain.log", max_bytes=10*1024*1024): # 10MB default
        self.filename = filename
        self.max_bytes = max_bytes
        self.file = open(self.filename, "a", encoding="utf-8")

    def log(self, state_data, total_reward, frame_reward):
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": state_data,
            "total_reward": total_reward,
            "frame_reward": frame_reward
        }
        
        # Write the line
        line = json.dumps(log_record) + "\n"
        self.file.write(line)
        self.file.flush() # Ensures data is saved even if the script crashes

        # Check if we need to rotate
        if self.file.tell() > self.max_bytes:
            self.rotate()

    def rotate(self):
        self.file.close()
        # Rename current log to include timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"pokebrain_{timestamp}.log"
        os.rename(self.filename, new_name)
        # Open a fresh file
        self.file = open(self.filename, "a", encoding="utf-8")
        print(f"Log rotated. Previous saved as {new_name}")

    def close(self):
        self.file.close()

# Initialize once at the start of your script
logger = PokeLogger(max_bytes=10*1024*1024)