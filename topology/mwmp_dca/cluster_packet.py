from entities.packet import Packet


class ClusterPacket(Packet):
    def __init__(self, src_drone, creation_time, packet_id, packet_length, simulator, channel_id,
                 msg_type, cluster_id=None, payload=None):
        super().__init__(packet_id, packet_length, creation_time, simulator, channel_id)
        self.src_drone = src_drone
        self.msg_type = msg_type
        self.cluster_id = cluster_id
        self.payload = payload or {}
        self.transmission_mode = 1


class ClusterHelloPacket(ClusterPacket):
    def __init__(self, src_drone, creation_time, packet_id, packet_length, simulator, channel_id, payload=None):
        super().__init__(src_drone, creation_time, packet_id, packet_length, simulator, channel_id,
                         msg_type='cluster_hello', cluster_id=getattr(src_drone, 'cluster_id', None), payload=payload)


class ClusterAnnouncePacket(ClusterPacket):
    def __init__(self, src_drone, creation_time, packet_id, packet_length, simulator, channel_id, payload=None):
        super().__init__(src_drone, creation_time, packet_id, packet_length, simulator, channel_id,
                         msg_type='ch_announce', cluster_id=getattr(src_drone, 'cluster_id', None), payload=payload)


class JoinRequestPacket(ClusterPacket):
    def __init__(self, src_drone, creation_time, packet_id, packet_length, simulator, channel_id, cluster_id=None,
                 payload=None):
        super().__init__(src_drone, creation_time, packet_id, packet_length, simulator, channel_id,
                         msg_type='join_request', cluster_id=cluster_id, payload=payload)


class JoinAckPacket(ClusterPacket):
    def __init__(self, src_drone, creation_time, packet_id, packet_length, simulator, channel_id, cluster_id=None,
                 payload=None):
        super().__init__(src_drone, creation_time, packet_id, packet_length, simulator, channel_id,
                         msg_type='join_ack', cluster_id=cluster_id, payload=payload)

