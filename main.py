from src.client import connect_ib


ib = connect_ib()

print("Connected to IBKR API")




ib.disconnect()