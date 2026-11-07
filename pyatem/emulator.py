import argparse
import socket
import struct

from pyatem.field import ManualField
from pyatem.protocol import AtemProtocol
from pyatem.transport import Packet, Sequence, UdpProtocol


class AtemClient:
    STATE_CLOSED = 0
    STATE_HANDSHAKE = 1
    STATE_CONNECTED = 2

    STRUCT_FIELD = struct.Struct('!H2x 4s')

    def __init__(self, emulator, addr, client_id):
        self.emulator = emulator
        self.sock = emulator.sock
        self.addr = addr
        self.client_id = client_id
        self.session = client_id + 0x8000

        self.state = AtemClient.STATE_CLOSED

        self.local_sequence_number = 0
        self.local_ack_number = 0
        self.remote_sequence_number = 0
        self.remote_ack_number = 0

    def send_packet(self, data, flags=0, session=None, client_packet_id=None, ack=None):
        packet = Packet()
        packet.emulator = True
        packet.flags = flags
        packet.data = data

        if client_packet_id:
            packet.remote_sequence_number = client_packet_id

        if session:
            packet.session = session
        else:
            packet.session = self.session

        if ack is not None:
            packet.acknowledgement_number = ack
            self.local_ack_number = ack

        if not packet.flags & UdpProtocol.FLAG_SYN:
            packet.sequence_number = (self.local_sequence_number + 1) % Sequence.MODULUS
        raw = packet.to_bytes()
        self.sock.sendto(raw, self.addr)

        if packet.flags & (UdpProtocol.FLAG_SYN) == 0:
            self.local_sequence_number = (self.local_sequence_number + 1) % Sequence.MODULUS

    def decode_packet(self, data):
        offset = 0
        while offset < len(data):
            datalen, cmd = self.STRUCT_FIELD.unpack_from(data, offset)

            # A zero length header is not possible, this occurs when the transport layer has corruption, mark the
            # connection closed to restart and recover state
            if datalen == 0:
                raise ConnectionError()

            raw = data[offset + 8:offset + datalen]
            yield (cmd, raw)
            offset += datalen

    def send_fields(self, fields):
        data = b''
        for field in fields:
            data += field.make_packet()

        if len(data) > 1450:
            raise ValueError("Field list too long for UDP packet")

        self.send_packet(data, flags=UdpProtocol.FLAG_RELIABLE)

    def _flatten(self, idict):
        result = []
        if isinstance(idict, list):
            return idict
        for key in idict:
            if isinstance(idict[key], dict):
                result.extend(self._flatten(idict[key]))
            elif isinstance(idict[key], list):
                result.extend(idict[key])
            else:
                result.append(idict[key])
        return result

    def send_initial_state(self):
        fields = self.emulator.mixerstate
        fields = self._flatten(fields)

        # for i in range(0, len(fields)):
        #     f = fields[i]
        #     if f.CODE == 'InPr' and f.index == 1:
        #         fields[i].short_name = 'PRXY'
        #         fields[i].update()
        #         pass

        buffer = []
        size = 0

        for field in fields:
            if isinstance(field, bytes):
                continue
            fsize = len(field.raw) + 8
            if size + fsize > 1408:
                self.send_fields(buffer)
                buffer = []
                size = 0
            buffer.append(field)
            size += fsize
        self.send_fields(buffer)

        # Flag should be 0x11
        self.send_packet(b'', flags=(UdpProtocol.FLAG_RELIABLE | UdpProtocol.FLAG_ACK))

    def on_init(self, packet):
        if self.state != AtemClient.STATE_CLOSED:
            print("Re-initializing connection")
            self.remote_ack_number = 0
            self.local_ack_number = 0
            self.remote_sequence_number = 0
            self.local_sequence_number = 0

        self.state = AtemClient.STATE_HANDSHAKE
        raw = struct.pack('!2H 4x', 0x0200, self.client_id)
        self.send_packet(raw, flags=UdpProtocol.FLAG_SYN, session=packet.session, client_packet_id=0xad)

    def on_packet(self, raw):
        packet = Packet.from_bytes(raw)
        packet.emulator = True

        if packet.flags & UdpProtocol.FLAG_SYN:
            state_cmd = packet.data[0]
            if state_cmd == 0x01:
                print("INIT connection")
                self.on_init(packet)
            elif state_cmd == 0x04:
                print("CLOSE connection")
            else:
                print("UNKNOWN session management command")

        elif self.state == AtemClient.STATE_HANDSHAKE:
            print("Handshake complete, session is now {}".format(self.session))
            self.state = AtemClient.STATE_CONNECTED
            # Handshake done, start dumping state
            self.send_initial_state()
        else:
            response = []
            for pkt in self.decode_packet(packet.data):
                print("Client {}: {}".format(self.client_id, pkt))
            if len(response) == 0:
                self.send_packet(b'', flags=UdpProtocol.FLAG_ACK, session=packet.session, ack=packet.sequence_number)


class AtemEmulator:
    def __init__(self, host=None, port=9910):
        if host is None:
            host = ''
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.clients = {}
        self.mixerstate = {}

    def listen(self):
        self.sock.bind((self.host, self.port))
        while True:
            raw, addr = self.sock.recvfrom(9000)
            if addr not in self.clients:
                self.on_connect(addr)
            self.clients[addr].on_packet(raw)

    def on_connect(self, addr):
        print("New client on {}".format(addr))
        self.clients[addr] = AtemClient(self, addr, len(self.clients))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="ATEM protocol proxy")
    parser.add_argument('ip', help='IP of ATEM device to proxy')
    args = parser.parse_args()


    def passthrough_done():
        print("Passthrough initialized, ready for proxy connections")
        emulator.mixerstate = proxy_state
        emulator.listen()


    def proxy_state_change(key, raw):
        if not isinstance(raw, bytes):
            proxy_state.append(raw)
        else:
            proxy_state.append(ManualField(key, raw))


    proxy_state = []
    emulator = AtemEmulator()

    pt = AtemProtocol(ip=args.ip)
    pt.on('change', proxy_state_change)
    pt.on('connected', passthrough_done)
    pt.connect()
    print("Connecting to passthrough device")
    while True:
        pt.loop()
