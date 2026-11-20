import enum
import socket
import struct
from pathlib import Path
from typing import BinaryIO

import dpkt
from pcap.errors import PcapParseError
from pcap.models import FlowKey, FlowRecord, ParsedCapture

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class DatalinkType(enum.IntEnum):
    """DLT (datalink type) stored in the libpcap file header: it says what precedes the IP packet in each record.

    ETHERNET (1): a 14-byte Ethernet header precedes the IP packet — captures made on a physical network card.
    RAW_IP (101): the IP packet starts at byte zero — captures made on tun/VPN interfaces. The pcap file
        format always stores 101 for raw IP; 12/14 are BSD-era values that never appear in capture files.
    LINUX_SLL (113): a 16-byte Linux cooked header precedes the IP packet — captures made with `tcpdump -i any`.
    """

    ETHERNET = 1
    RAW_IP = 101
    LINUX_SLL = 113



class _FlowAccumulator:
    """Collect packet statistics for one bidirectional TCP/UDP flow."""

    def __init__(self, flow_key: FlowKey) -> None:
        self.flow_key = flow_key
        self.total_frame_bytes = 0
        self.payload_bytes = 0
        self.retransmission_count = 0
        self.zero_window_event_count = 0
        self.reset_count = 0
        self.handshake_rtt: float | None = None
        self._syn_timestamp: float | None = None
        self._sent_ranges: dict[str, list[tuple[int, int]]] = {}

    def add_tcp_segment(
        self,
        timestamp: float,
        segment: dpkt.tcp.TCP,
        frame_length: int,
        source_ip: str,
    ) -> None:
        """Process a TCP segment and update flow statistics."""

        # Count captured bytes and application payload.
        self.total_frame_bytes += frame_length
        payload_length = len(segment.data)
        self.payload_bytes += payload_length

        # Count TCP reset packets.
        if segment.flags & dpkt.tcp.TH_RST:
            self.reset_count += 1

        # Count TCP zero-window advertisements.
        if segment.win == 0:
            self.zero_window_event_count += 1

        # Estimate handshake RTT using SYN and SYN-ACK timestamps.
        if (segment.flags & dpkt.tcp.TH_SYN) and not (
            segment.flags & dpkt.tcp.TH_ACK
        ):
            self._syn_timestamp = timestamp

        elif (
            segment.flags & dpkt.tcp.TH_SYN
            and segment.flags & dpkt.tcp.TH_ACK
            and self._syn_timestamp is not None
        ):
            self.handshake_rtt = timestamp - self._syn_timestamp
            self._syn_timestamp = None

        # Detect overlapping TCP payload sequence ranges.
        if payload_length > 0:
            start = segment.seq
            end = start + payload_length

            sent_ranges = self._sent_ranges.setdefault(source_ip, [])

            if any(
                start < previous_end and end > previous_start
                for previous_start, previous_end in sent_ranges
            ):
                self.retransmission_count += 1

            sent_ranges.append((start, end))

    def add_udp_datagram(
        self, datagram: dpkt.udp.UDP, frame_length: int
    ) -> None:
        """Count UDP frame bytes and application payload bytes."""

        self.total_frame_bytes += frame_length
        self.payload_bytes += len(datagram.data)

    def record(self) -> FlowRecord:
        """Convert accumulated statistics into an immutable flow record."""

        return FlowRecord(
            flow_key=self.flow_key,
            total_frame_bytes=self.total_frame_bytes,
            payload_bytes=self.payload_bytes,
            retransmission_count=self.retransmission_count,
            zero_window_event_count=self.zero_window_event_count,
            reset_count=self.reset_count,
            handshake_rtt=self.handshake_rtt,
        )




class PcapParser:
    """Parses pcap/pcapng captures into per-flow records using dpkt (no external tools)."""

    DISSECTION_ERRORS: tuple[type[Exception], ...] = (dpkt.UnpackError, struct.error, IndexError)

    def parse(self, pcap_path: Path) -> ParsedCapture:
        """Dissect a capture into one record per TCP/UDP flow, plus the non-flow byte total.

        Flows are keyed by their canonical five-tuple, so both directions of a flow and both
        protocols on the same four-tuple are handled. Non-flow traffic (ARP, ICMP, ...) only
        counts its frame bytes. Individually malformed packets are skipped and counted; an
        unreadable file raises PcapParseError.
        """
        try:
            capture = self._parse(pcap_path)
        except OSError as error:
            raise PcapParseError(f"cannot read {pcap_path}: {error}") from error
        if capture.malformed_packet_count:
            logger.warning("%s: skipped %d malformed packet(s).", pcap_path.name, capture.malformed_packet_count)
        return capture


    def _parse(self, pcap_path: Path) -> ParsedCapture:
        """Read a PCAP/PCAPNG file and group TCP/UDP packets into flows."""

        flows: dict[FlowKey, _FlowAccumulator] = {}
        other_frame_bytes = 0
        malformed_packet_count = 0

        with pcap_path.open("rb") as handle:
            # Detect classic PCAP or PCAPNG from the file header.
            magic = handle.read(4)
            handle.seek(0)

            try:
                if magic == b"\x0a\x0d\x0d\x0a":
                    reader = dpkt.pcapng.Reader(handle)
                else:
                    reader = dpkt.pcap.Reader(handle)

                linktype = reader.datalink()
            except (ValueError, dpkt.Error, struct.error) as error:
                raise PcapParseError(
                    f"Invalid PCAP header: {error}"
                ) from error

            if linktype not in (
                DatalinkType.ETHERNET,
                DatalinkType.RAW_IP,
                DatalinkType.LINUX_SLL,
            ):
                raise PcapParseError(
                    f"Unsupported datalink type: {linktype}"
                )

            try:
                for timestamp, packet_data in reader:
                    frame_length = len(packet_data)

                    try:
                        # Decode the packet based on its link type.
                        if linktype == DatalinkType.ETHERNET:
                            frame = dpkt.ethernet.Ethernet(packet_data)
                            ip_packet = frame.data

                        elif linktype == DatalinkType.LINUX_SLL:
                            frame = dpkt.sll.SLL(packet_data)
                            ip_packet = frame.data

                        else:
                            # RAW_IP has no Ethernet header.
                            version = packet_data[0] >> 4
                            if version == 4:
                                ip_packet = dpkt.ip.IP(packet_data)
                            elif version == 6:
                                ip_packet = dpkt.ip6.IP6(packet_data)
                            else:
                                raise ValueError("Invalid IP version")

                        # ARP and other non-IP traffic.
                        if not isinstance(
                            ip_packet, (dpkt.ip.IP, dpkt.ip6.IP6)
                        ):
                            other_frame_bytes += frame_length
                            continue

                        source_ip = socket.inet_ntop(
                            socket.AF_INET
                            if isinstance(ip_packet, dpkt.ip.IP)
                            else socket.AF_INET6,
                            ip_packet.src,
                        )
                        destination_ip = socket.inet_ntop(
                            socket.AF_INET
                            if isinstance(ip_packet, dpkt.ip.IP)
                            else socket.AF_INET6,
                            ip_packet.dst,
                        )

                        transport = ip_packet.data

                        if isinstance(transport, dpkt.tcp.TCP):
                            protocol = "TCP"
                        elif isinstance(transport, dpkt.udp.UDP):
                            protocol = "UDP"
                        else:
                            other_frame_bytes += frame_length
                            continue

                        flow_key = FlowKey.from_packet(
                            protocol,
                            source_ip,
                            transport.sport,
                            destination_ip,
                            transport.dport,
                        )

                        if flow_key not in flows:
                            flows[flow_key] = _FlowAccumulator(flow_key)

                        accumulator = flows[flow_key]

                        if protocol == "TCP":
                            accumulator.add_tcp_segment(
                                timestamp,
                                transport,
                                frame_length,
                                source_ip,
                            )
                        else:
                            accumulator.add_udp_datagram(
                                transport,
                                frame_length,
                            )

                    except (
                        dpkt.UnpackError,
                        struct.error,
                        IndexError,
                        ValueError,
                        AttributeError,
                    ):
                        # Skip an invalid packet, not the entire file.
                        malformed_packet_count += 1

            except (dpkt.Error, struct.error) as error:
                raise PcapParseError(
                    f"Corrupted PCAP file: {error}"
                ) from error

        return ParsedCapture(
            flows=tuple(flow.record() for flow in flows.values()),
            other_frame_bytes=other_frame_bytes,
            malformed_packet_count=malformed_packet_count,
        )
