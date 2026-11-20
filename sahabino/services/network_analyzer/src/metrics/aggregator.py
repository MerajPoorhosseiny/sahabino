
from collections import defaultdict

from configs import WELL_KNOWN_PORTS
from metrics.models import PcapMetrics
from pcap.models import ParsedCapture


class PcapMetricsAggregator:
    """Calculate network metrics from parsed TCP/UDP flows."""

    def aggregate(self, capture: ParsedCapture) -> PcapMetrics:
        # Include TCP/UDP traffic and other captured frames.
        total_bytes = capture.other_frame_bytes
        payload_bytes = 0

        retransmissions = 0
        zero_windows = 0
        tcp_resets = 0
        handshake_rtts = []

        # Accumulate traffic for likely server ports.
        port_traffic = defaultdict(int)

        for flow in capture.flows:
            total_bytes += flow.total_frame_bytes
            payload_bytes += flow.payload_bytes

            retransmissions += flow.retransmission_count
            zero_windows += flow.zero_window_event_count
            tcp_resets += flow.reset_count

            if flow.handshake_rtt is not None:
                handshake_rtts.append(flow.handshake_rtt)

            endpoints = (
                flow.flow_key.first_endpoint,
                flow.flow_key.second_endpoint,
            )

            # Identify likely server ports using known service ports.
            for endpoint in endpoints:
                if endpoint.port in WELL_KNOWN_PORTS:
                    port_traffic[endpoint.port] += flow.total_frame_bytes

        # Average TCP handshake RTT in seconds.
        average_rtt = (
            sum(handshake_rtts) / len(handshake_rtts)
            if handshake_rtts else None
        )

        # Fraction of captured bytes that are not application payload.
        overhead_ratio = (
            (total_bytes - payload_bytes) / total_bytes
            if total_bytes > 0 else None
        )

        dominant_port = (
            max(port_traffic, key=port_traffic.get)
            if port_traffic else None
        )

        return PcapMetrics(
            handshake_rtt_avg=average_rtt,
            retransmission_count=retransmissions,
            zero_window_event_count=zero_windows,
            tcp_reset_drops=tcp_resets,
            total_transferred_bytes=total_bytes,
            total_payload_bytes=payload_bytes,
            overhead_ratio=overhead_ratio,
            dominant_server_port=dominant_port,
        )
