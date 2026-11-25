"""python -m fake_plugin --scenario sysml-project --port 18740"""
import argparse
import time

from contract_constants import DEFAULT_PORT, SCENARIOS

from .server import FakePlugin


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m fake_plugin")
    parser.add_argument("--scenario", choices=SCENARIOS, default="sysml-project")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    fake = FakePlugin(args.scenario, port=args.port).start()
    print(f"fake plugin ({args.scenario}) listening on {fake.url}  (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        fake.stop()


main()
