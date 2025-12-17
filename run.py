import socketio
import time
import os
from lib.ci_auto_trader import  CIAutoTrader
from dotenv import load_dotenv
load_dotenv()

HUB_URL = os.getenv("HUB_URL", None)
MACHINE_TOKEN = os.getenv("MACHINE", None)

sio = socketio.Client(reconnection=True, reconnection_attempts=0, logger=False, engineio_logger=False)


@sio.event(namespace="/machines")
def connect():
    print("[CRYPTO-INSIGHT] - CONNECTED")
    print("[CRYPTO-INSIGHT] - Waiting for commands...")

@sio.event(namespace="/machines")
def disconnect():
    print("Disconnected from crypto-insight")


@sio.on("command.run", namespace="/machines")
def on_command_run(data):
    trader = CIAutoTrader(data)
    result = trader.execute_action()
    if result:
        print("[CRYPTO-INSIGHT] - Sending report to server")
        sio.sleep(60)
        print("[CRYPTO-INSIGHT] - Report sent")
        sio.emit(
            "command.result",
            {"ex_order_id": result, "strategy": data['strategy']},
            namespace="/machines",
        )

@sio.event
def connect_error(data):
    print("connect_error:", data)

def main():
    while True:
        try:
            sio.connect(
                HUB_URL,
                namespaces=["/machines"],
                auth={"token": MACHINE_TOKEN},
                transports=["websocket"],
            )
            sio.wait()
        except Exception as e:
            print("Connect error:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()
