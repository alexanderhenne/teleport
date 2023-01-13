import os
import argparse
import logging

from teleport import generate_client_hint, get_device_token, connect_device

parser = argparse.ArgumentParser(description="Unofficial AmpliFi Teleport client")

parser.add_argument("--pin",
    help="PIN from the AmpliFi app, eg. AB123")
parser.add_argument("--uuid-file", default="teleport_uuid",
    help="File to store client UUID in. Can be shared between different tokens. (default: teleport_uuid)")
parser.add_argument("--token-file", default="teleport_token_0",
    help="File to store router token in (default: teleport_token_0)")
parser.add_argument("--verbose", "-v", action="count")

args = parser.parse_args()

if args.verbose:
    logging.basicConfig(level=logging.DEBUG)

if os.path.isfile(args.token_file):
    if args.pin:
        logging.error("Token file %s already exists, please choose a different "
                        "output file if you want to generate a new token or omit --pin."
                        % args.token_file)
    else:
        with open(args.token_file) as f:
            deviceToken = f.readlines()[0]

        print(connect_device(deviceToken))
else:
    if args.pin:
        if os.path.isfile(args.uuid_file):
            with open(args.uuid_file) as f:
                clientHint = f.readlines()[0]
        else:
            with open(args.uuid_file, mode="w") as f:
                clientHint = generate_client_hint()
                f.write(clientHint)

        try:
            deviceToken = get_device_token(clientHint, args.pin)

            with open(args.token_file, mode="w") as f:
                f.write(deviceToken)

            print(connect_device(deviceToken))
        except Exception as e:
            logging.error(e)
    else:
        logging.error("Missing token file, please enter a new PIN using --pin.")
