class ManagerStore:
    ADMIN_ID = 123456789  # Замени на ADMIN_CHAT_ID из config.py
    
    def __init__(self):
        self.is_monitoring = True
        self.check_interval = 300  # 5 минут