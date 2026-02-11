import time

class CooldownManager:
    def __init__(self):
        self.cooldowns = {}

    def set_cooldown(self, user_id, duration):
        self.cooldowns[user_id] = time.time() + duration

    def is_on_cooldown(self, user_id):
        if user_id in self.cooldowns:
            if time.time() < self.cooldowns[user_id]:
                return True
            else:
                del self.cooldowns[user_id]
        return False

    def get_remaining_time(self, user_id):
        if user_id in self.cooldowns:
            return max(0, self.cooldowns[user_id] - time.time())
        return 0

# Example usage:
# cooldown_manager = CooldownManager()
# cooldown_manager.set_cooldown('user123', 10)  # 10-second cooldown
# if cooldown_manager.is_on_cooldown('user123'): 
#     print(f'User is on cooldown for {cooldown_manager.get_remaining_time('user123')} seconds')