import asyncio
import logging
import requests
import subprocess
import uuid
import socket

from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceServer, RTCConfiguration
from aiortc.sdp import grouplines, parse_attr

ICE_STUN_SERVER = "stun:global.stun.twilio.com:3478"

REQUEST_DEVICE_TOKEN_URL = "https://client.amplifi.com/api/deviceToken/mlRequestClientAccess"
ICE_CONFIG_URL = "https://client.amplifi.com/api/deviceToken/mlIceConfig"
SIGNALING_URL = "https://client.amplifi.com/api/deviceToken/mlClientConnect"

# Decides the device icon in the router control panel
DEVICE_PLATFORM = "iOS"

def _generate_wg_keys():
    privateKey = subprocess.check_output(["wg", "genkey"],
                                        encoding="utf8").strip()

    publicKeyProcess = subprocess.Popen(["wg", "pubkey"],
                                        stdout = subprocess.PIPE,
                                        stdin = subprocess.PIPE,
                                        encoding="utf8")

    publicKey = publicKeyProcess.communicate(input=privateKey)[0].strip()

    return privateKey, publicKey

def _get_device_name():
    return socket.gethostname()

def _make_request_headers(token):
    return {
        "x-devicetoken": token,
        "user-agent": "AmpliFiTeleport/7 CFNetwork/1220.1 Darwin/20.3.0",
    }

def _add_tunnel_info(sdp, friendlyName, platform, publicKey):
    parts = sdp.partition("s=-")
    info = "\r\n".join([
        f"a=tool:ubnt_webrtc version ",
        f"a=uca_acf5_amplifi_friendly_name:" + friendlyName,
        f"a=uca_acf5_amplifi_nomination_mode:slave",
        f"a=uca_acf5_amplifi_platform:" + platform,
        f"a=uca_acf5_amplifi_tunnel_pub_key:" + publicKey])
    return parts[0] + parts[1] + "\r\n" + info + parts[2]

def _get_remote_description(localDescription, deviceToken):
    headers = _make_request_headers(deviceToken)

    iceConfigResponse = requests.post(ICE_CONFIG_URL, headers=headers)

    logging.debug("Raw ICE config response: %s" % iceConfigResponse.text)

    iceConfig = iceConfigResponse.json()

    if not iceConfig["success"]:
        if iceConfig["error"]:
            raise Exception("ICE config request failed (%s)" % iceConfig["error"])
        else:
            raise Exception("ICE config request failed")

    iceServers = iceConfig["servers"]

    connectResponse = requests.post(
        SIGNALING_URL,
        json={
            "iceServers": iceServers,
            "offer": localDescription
        },
        headers=headers)

    logging.debug("Raw connect response: %s" % connectResponse.text)

    answerAndSuccess = connectResponse.json()

    if not answerAndSuccess["success"]:
        if answerAndSuccess["error"]:
            raise Exception("Connect request failed (%s)" % answerAndSuccess["error"])
        else:
            raise Exception("Connect request failed")

    answer = answerAndSuccess["answer"]
    return RTCSessionDescription(sdp=answer, type="answer")

def _generate_wg_config(pc, remoteDescription, privateKey):
    iceTransport = pc.sctp.transport.transport
    iceGatherer = iceTransport.iceGatherer
    connection = iceGatherer._connection

    logging.debug("Nominated peers: %s" % connection._nominated)

    if 1 not in connection._nominated:
        raise Exception("No nominated candidate peer")

    candidatePair = connection._nominated[1]

    logging.debug("Chosen candidate pair: %s" % candidatePair)

    localAddr = candidatePair.local_addr
    localPort = localAddr[1]

    remoteAddr = candidatePair.remote_addr
    remoteIp = remoteAddr[0]
    remotePort = remoteAddr[1]

    remoteSdp = remoteDescription.sdp
    session, _ = grouplines(remoteSdp)

    for line in session:
        if line.startswith("a="):
            attr, value = parse_attr(line)
            if attr == "uca_acf5_amplifi_ipv4_addr":
                interfaceAddress = value
            elif attr == "uca_acf5_amplifi_ipv4_dns_addr0":
                dnsAddress = value
            elif attr == "uca_acf5_amplifi_tunnel_pub_key":
                remotePublicKey = value

    wgConfigLines = [
        "[Interface]",
        "PrivateKey = %s" % privateKey,
        "ListenPort = %s" % localPort,
        "Address = %s/32" % interfaceAddress,
        "DNS = %s" % dnsAddress,
        "",
        "[Peer]",
        "PublicKey = %s" % remotePublicKey,
        "AllowedIPs = 0.0.0.0/0, ::/0", # Block untunneled traffic (kill-switch)
        "Endpoint = %s:%s"  % (remoteIp, remotePort)
    ]

    return "\n".join(wgConfigLines)

async def _connect_device_peer(pc, deviceToken):
    # A media channel or data channel is required
    # to create an offer, but it will not be used.
    pc.createDataChannel("chat")

    await pc.setLocalDescription(await pc.createOffer())

    privateKey, publicKey = _generate_wg_keys()
    deviceName = _get_device_name()
    platform = DEVICE_PLATFORM

    localDescription = _add_tunnel_info(
        pc.localDescription.sdp, deviceName, platform, publicKey)

    logging.debug("Sending local description: %s" % localDescription)

    try:
        remoteDescription = _get_remote_description(localDescription, deviceToken)

        logging.debug("Received remote description: %s" % remoteDescription)

        loop = asyncio.get_event_loop()
        configFuture = loop.create_future()

        @pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            logging.debug("ICE connection state is %s" % pc.iceConnectionState)

            if pc.iceConnectionState == "completed":
                try:
                    wgConfig = _generate_wg_config(pc, remoteDescription, privateKey)

                    logging.info("WireGuard config has been generated")
                    await pc.close()
                    configFuture.set_result(wgConfig)
                except Exception as e:
                    logging.error(e)
                    await pc.close()
                    configFuture.set_exception(e)

        await pc.setRemoteDescription(remoteDescription)

        return await configFuture
    except Exception as e:
        logging.error(e)
        await pc.close()

def generate_client_hint():
    return str(uuid.uuid4()).upper()

def get_device_token(clientHint, pin):
    clientAccessResponse = requests.post(
        REQUEST_DEVICE_TOKEN_URL,
        json={
            "client_hint": clientHint 
        },
        headers=_make_request_headers(pin))

    logging.debug("Raw client access response: %s" % clientAccessResponse.text)

    deviceTokenAndSuccess = clientAccessResponse.json()

    if not deviceTokenAndSuccess["success"]:
        if deviceTokenAndSuccess["error"]:
            raise Exception("Client access request failed (%s)" % deviceTokenAndSuccess["error"])
        else:
            raise Exception("Client access request failed")

    return deviceTokenAndSuccess["client_id"]

def connect_device(deviceToken):
    stun = RTCIceServer(urls=ICE_STUN_SERVER)
    config = RTCConfiguration([stun])
    pc = RTCPeerConnection(config)

    coro = _connect_device_peer(pc, deviceToken)

    loop = asyncio.get_event_loop()
    try:
        return loop.run_until_complete(coro)  
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(pc.close())
