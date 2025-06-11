# Teleport

This is an unofficial tool which generates WireGuard VPN configurations for AmpliFi Teleport-enabled routers so you can access your local network from the outside. It was made because there is no AmpliFi Teleport desktop tool available yet, only mobile apps.

Steps to use it:
 1. Install WireGuard (https://www.wireguard.com/install/) - `wg` needs to be accessible from the terminal.
 2. `pip install -r requirements.txt`
 3. Generate a PIN from within the AmpliFi app.
 4. `python main.py --pin AB123`, replacing AB123 with the PIN from step 2.
 5. Paste the outputted WireGuard config into a WireGuard client and connect.
 6. Repeat steps 3 and 4 everytime you want to connect, but without the `--pin` argument.
