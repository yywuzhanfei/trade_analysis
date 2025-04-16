from ib_insync import IB
import os
from dotenv import load_dotenv

load_dotenv()

def connect_ib():
    ib = IB()
    host = os.getenv("IB_HOST", "127.0.0.1")
    port = int(os.getenv("IB_PORT", "4001"))
    client_id = int(os.getenv("IB_CLIENT_ID", "1"))
    ib.connect(host, port, clientId=client_id)
    return ib
