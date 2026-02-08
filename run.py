import socketio
import time
from lib.ci_auto_trader import CIAutoTrader
from config import HUB_URL, MACHINE_TOKEN
from lib.logger import Logger

logger = Logger("Main")
sio = socketio.Client(reconnection=True, reconnection_attempts=0, logger=False, engineio_logger=False)


@sio.event(namespace="/machines")
def connect():
    logger.info("CONNECTED to crypto-insight")
    logger.info("Waiting for commands...")


@sio.event(namespace="/machines")
def disconnect():
    logger.info("Disconnected from crypto-insight")


@sio.on("command.run", namespace="/machines")
def on_command_run(data):
    trader = CIAutoTrader(data)
    result = trader.execute_action()
    if result:
        logger.info("Sending report to server", extra={"order_id": result})
        sio.sleep(60)
        logger.info("Report sent")
        sio.emit(
            "command.result",
            {"ex_order_id": result, "strategy": data['strategy']},
            namespace="/machines",
        )


@sio.event
def connect_error(data):
    logger.error("connect_error", extra={"data": data})


def main():
    # Check API connectivity and time synchronization at startup
    try:
        logger.info("Checking Binance API connectivity and time sync...")
        trader = CIAutoTrader({})
        trader.get_position_mode()
        logger.info("API Check: OK")
    except Exception as e:
        logger.error(f"Initial API check failed: {e}")

    while True:
        try:
            logger.info(f"Connecting to {HUB_URL}...")
            sio.connect(
                HUB_URL,
                namespaces=["/machines"],
                auth={"token": MACHINE_TOKEN},
                transports=["websocket"],
            )
            sio.wait()
        except Exception as e:
            logger.error("Connect error", extra={"error": str(e)})
            time.sleep(5)


if __name__ == "__main__":
    from config import UNIQUE_ID, ENV_UNIQUE_ID, LOCAL_UNIQUE_ID
    print("==========================================")
    print(f"           UNIQUE_ID: {UNIQUE_ID}")
    print(f"       SET_UNIQUE_ID: {ENV_UNIQUE_ID}")
    print(f" GENERATED_UNIQUE_ID: {LOCAL_UNIQUE_ID}")
    print("==========================================")
    main()
