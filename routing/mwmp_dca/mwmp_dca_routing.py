import copy
import random
import simpy
from entities.packet import DataPacket, AckPacket
from simulator.log import logger
from utils import config
from utils.util_function import euclidean_distance_3d
from routing.dsdv.dsdv import Dsdv
from topology.mwmp_dca.cluster_packet import ClusterHelloPacket, ClusterAnnouncePacket, JoinRequestPacket, JoinAckPacket


class MwmpDcaRouting:
    def __init__(self, simulator, my_drone):
        self.simulator = simulator
        self.my_drone = my_drone
        self.rng_routing = random.Random(self.my_drone.identifier + self.my_drone.simulator.seed + 33)
        self.check_interval = 0.6 * 1e6
        self.waiting_list = []
        self.backbone_router = None
        self.backbone_router_role = None
        self.simulator.env.process(self.check_waiting_list())
        self.update_role(getattr(self.my_drone, 'cluster_role', 'CM'))

    def update_role(self, role):
        if role in ('CH', 'BS'):
            if self.backbone_router is None or self.backbone_router_role != role or not getattr(self.backbone_router, 'active', True):
                self.backbone_router = Dsdv(self.simulator, self.my_drone)
                self.backbone_router_role = role
        else:
            if self.backbone_router is not None:
                self.backbone_router.active = False

    def next_hop_selection(self, packet):
        if isinstance(packet, DataPacket):
            self._prepare_packet_state(packet)
            if self._is_backbone_node(self.my_drone):
                return self._select_backbone_next_hop(packet)

            if self.my_drone.cluster_role == 'CM':
                return self._select_cluster_member_next_hop(packet)

        if hasattr(packet, 'msg_type'):
            if packet.msg_type in ('cluster_hello', 'ch_announce'):
                packet.transmission_mode = 1
                return True, packet, False

        return False, packet, False

    def packet_reception(self, packet, src_drone_id):
        current_time = self.simulator.env.now
        yield self.simulator.env.timeout(0)

        if isinstance(packet, ClusterHelloPacket):
            self.my_drone.cluster_directory = getattr(self.my_drone, 'cluster_directory', {})
            self.my_drone.cluster_directory[packet.src_drone.identifier] = packet.src_drone
            return

        if isinstance(packet, ClusterAnnouncePacket):
            self.my_drone.cluster_directory = getattr(self.my_drone, 'cluster_directory', {})
            self.my_drone.cluster_directory[packet.src_drone.identifier] = packet.src_drone
            return

        if isinstance(packet, JoinRequestPacket):
            if self.my_drone.cluster_role == 'CH':
                packet.src_drone.cluster_head = self.my_drone
                packet.src_drone.cluster_id = self.my_drone.identifier
                ack_packet = JoinAckPacket(src_drone=self.my_drone,
                                           creation_time=current_time,
                                           packet_id=packet.packet_id,
                                           packet_length=config.HELLO_PACKET_LENGTH,
                                           simulator=self.simulator,
                                           channel_id=packet.channel_id,
                                           cluster_id=self.my_drone.identifier,
                                           payload={'cluster_head_id': self.my_drone.identifier})
                ack_packet.transmission_mode = 1
                self.my_drone.transmitting_queue.put(ack_packet)
            return

        if isinstance(packet, JoinAckPacket):
            packet.src_drone.cluster_head = self.simulator.drones[src_drone_id]
            packet.src_drone.cluster_id = src_drone_id
            return

        if isinstance(packet, DataPacket):
            packet_copy = copy.copy(packet)
            if packet_copy.dst_drone.identifier == self.my_drone.identifier:
                if packet_copy.packet_id not in self.simulator.metrics.datapacket_arrived:
                    self.simulator.metrics.calculate_metrics(packet_copy)
                self._reply_ack(packet_copy, src_drone_id)
            else:
                self.my_drone.transmitting_queue.put(packet_copy)
                self._reply_ack(packet_copy, src_drone_id)
            return

        if isinstance(packet, AckPacket):
            data_packet_acked = packet.ack_packet
            self.simulator.metrics.mac_delay.append((self.simulator.env.now - data_packet_acked.first_attempt_time) / 1e3)
            self.my_drone.remove_from_queue(data_packet_acked)
            key2 = ''.join(['wait_ack', str(self.my_drone.identifier), '_', str(data_packet_acked.packet_id)])
            if self.my_drone.mac_protocol.wait_ack_process_finish.get(key2, 0) == 0:
                if key2 in self.my_drone.mac_protocol.wait_ack_process_dict and \
                        not self.my_drone.mac_protocol.wait_ack_process_dict[key2].triggered:
                    self.my_drone.mac_protocol.wait_ack_process_finish[key2] = 1
                    self.my_drone.mac_protocol.wait_ack_process_dict[key2].interrupt()
            return

        if self.backbone_router is not None:
            return self.backbone_router.packet_reception(packet, src_drone_id)

    def _reply_ack(self, packet_copy, src_drone_id):
        self.simulator.env.process(self._reply_ack_process(packet_copy, src_drone_id))

    def _reply_ack_process(self, packet_copy, src_drone_id):
        yield self.simulator.env.timeout(config.SIFS_DURATION)
        config.GL_ID_ACK_PACKET += 1
        src_drone = self.simulator.drones[src_drone_id]
        ack_packet = AckPacket(src_drone=self.my_drone,
                               dst_drone=src_drone,
                               ack_packet_id=config.GL_ID_ACK_PACKET,
                               ack_packet_length=config.ACK_PACKET_LENGTH,
                               ack_packet=packet_copy,
                               simulator=self.simulator,
                               channel_id=packet_copy.channel_id)
        if not self.my_drone.sleep:
            ack_packet.increase_ttl()
            self.my_drone.mac_protocol.phy.unicast(ack_packet, src_drone_id)
            yield self.simulator.env.timeout(ack_packet.packet_length / config.BIT_RATE * 1e6)

    def check_waiting_list(self):
        while True:
            if self.my_drone.sleep:
                break
            yield self.simulator.env.timeout(self.check_interval)
            for waiting_pkd in list(self.my_drone.waiting_list):
                if self.simulator.env.now > waiting_pkd.creation_time + waiting_pkd.deadline:
                    self.my_drone.waiting_list.remove(waiting_pkd)
                    continue
                has_route, packet, enquire = self.next_hop_selection(waiting_pkd)
                if has_route:
                    self.my_drone.transmitting_queue.put(waiting_pkd)
                    self.my_drone.waiting_list.remove(waiting_pkd)

    def penalize(self, packet):
        self.my_drone.cluster_reselection_score = getattr(self.my_drone, 'cluster_reselection_score', 0) + 1

    def _select_cluster_member_next_hop(self, packet):
        cluster_head = getattr(self.my_drone, 'cluster_head', None)
        if cluster_head is None or cluster_head.identifier == self.my_drone.identifier:
            self._record_packet_event_once(packet, 'fallback_fail_missing_target_count')
            return False, packet, False

        if self._is_reachable_neighbor(cluster_head):
            packet.next_hop_id = cluster_head.identifier
            return True, packet, False

        backup_neighbor = self._choose_cm_local_backup(cluster_head, packet)
        if backup_neighbor is not None:
            self.simulator.metrics.record_routing_event('cm_local_backup_count')
            packet.next_hop_id = backup_neighbor.identifier
            return True, packet, False

        fallback_neighbor = self._choose_cm_fallback_neighbor(cluster_head, packet)
        if fallback_neighbor is not None:
            packet.next_hop_id = fallback_neighbor.identifier
            return True, packet, False

        return False, packet, False

    def _select_backbone_next_hop(self, packet):
        dst_cluster_head = getattr(packet.dst_drone, 'cluster_head', None)
        if dst_cluster_head is not None and dst_cluster_head.identifier == self.my_drone.identifier:
            if self._is_reachable_neighbor(packet.dst_drone):
                packet.next_hop_id = packet.dst_drone.identifier
                return True, packet, False
            return False, packet, False

        target_drone = self._resolve_backbone_target(packet)
        if target_drone is None:
            self._record_packet_event_once(packet, 'fallback_fail_missing_target_count')
            return False, packet, False

        if self._is_reachable_neighbor(target_drone):
            packet.next_hop_id = target_drone.identifier
            return True, packet, False

        self.update_role(self.my_drone.cluster_role)
        primary_next_hop = self._select_backbone_primary_next_hop(target_drone, packet)
        if primary_next_hop is not None:
            packet.next_hop_id = primary_next_hop.identifier
            return True, packet, False

        backup_neighbor = self._choose_backbone_local_backup(target_drone, packet)
        if backup_neighbor is not None:
            self.simulator.metrics.record_routing_event('backbone_local_backup_count')
            packet.next_hop_id = backup_neighbor.identifier
            return True, packet, False

        fallback_neighbor = self._choose_backbone_fallback_neighbor(target_drone, packet)
        if fallback_neighbor is not None:
            packet.next_hop_id = fallback_neighbor.identifier
            return True, packet, False

        return False, packet, False

    def _prepare_packet_state(self, packet):
        if self.my_drone.identifier not in packet.intermediate_drones:
            packet.intermediate_drones.append(self.my_drone.identifier)
        if not hasattr(packet, 'mwmp_recorded_events'):
            packet.mwmp_recorded_events = set()
        if not hasattr(packet, 'mwmp_fallback_used'):
            packet.mwmp_fallback_used = False

    def _resolve_backbone_target(self, packet):
        if getattr(packet.dst_drone, 'is_base_station', False):
            return packet.dst_drone
        dst_cluster_head = getattr(packet.dst_drone, 'cluster_head', None)
        if dst_cluster_head is not None:
            return dst_cluster_head
        return None

    def _select_backbone_primary_next_hop(self, target_drone, packet):
        if self.backbone_router is None:
            return None
        routing_table = getattr(self.backbone_router, 'routing_table', None)
        if routing_table is None:
            return None
        next_hop_id = routing_table.has_entry(target_drone.identifier)
        if next_hop_id == self.my_drone.identifier:
            return None
        if next_hop_id in packet.intermediate_drones:
            return None
        next_hop = self.simulator.drones[next_hop_id]
        if not self._is_reachable_neighbor(next_hop):
            return None
        if not self._is_backbone_node(next_hop) and next_hop.identifier != target_drone.identifier:
            return None
        return next_hop

    def _choose_cm_local_backup(self, cluster_head, packet):
        if not config.CH_ONLY_ENABLE_LOCAL_BACKUP:
            return None

        def is_candidate(candidate):
            if candidate.identifier in packet.intermediate_drones:
                return False
            candidate_head = getattr(candidate, 'cluster_head', None)
            if candidate_head is None:
                return False
            if candidate_head.identifier != cluster_head.identifier:
                return False
            return self._is_reachable_between(candidate, cluster_head)

        return self._select_best_neighbor(
            target_drone=cluster_head,
            packet=packet,
            predicate=is_candidate,
            prefer_backbone=False,
        )

    def _choose_cm_fallback_neighbor(self, cluster_head, packet):
        if not config.CH_ONLY_ENABLE_NEIGHBOR_FALLBACK:
            return None
        if self._mark_fallback_attempt(packet):
            return None

        def is_candidate(candidate):
            if candidate.identifier in packet.intermediate_drones:
                return False
            return self._is_backbone_node(candidate)

        neighbor = self._select_best_neighbor(
            target_drone=cluster_head,
            packet=packet,
            predicate=is_candidate,
            prefer_backbone=True,
        )
        if neighbor is None:
            self._record_packet_event_once(packet, 'fallback_fail_no_candidate_count')
            return None
        packet.mwmp_fallback_used = True
        self.simulator.metrics.record_routing_event('fallback_success_count')
        return neighbor

    def _choose_backbone_local_backup(self, target_drone, packet):
        if not config.CH_ONLY_ENABLE_LOCAL_BACKUP:
            return None

        def is_candidate(candidate):
            if candidate.identifier in packet.intermediate_drones:
                return False
            return self._is_backbone_node(candidate)

        return self._select_best_neighbor(
            target_drone=target_drone,
            packet=packet,
            predicate=is_candidate,
            prefer_backbone=True,
        )

    def _choose_backbone_fallback_neighbor(self, target_drone, packet):
        if not config.CH_ONLY_ENABLE_NEIGHBOR_FALLBACK:
            return None
        if self._mark_fallback_attempt(packet):
            return None

        def is_candidate(candidate):
            if candidate.identifier in packet.intermediate_drones:
                return False
            if (
                getattr(candidate, 'cluster_role', None) != 'CM'
                or getattr(candidate, 'is_backbone_connector', False)
            ):
                return False
            candidate_head = getattr(candidate, 'cluster_head', None)
            if candidate_head is None or candidate_head.identifier != target_drone.identifier:
                return False
            return self._is_reachable_between(candidate, target_drone)

        neighbor = self._select_best_neighbor(
            target_drone=target_drone,
            packet=packet,
            predicate=is_candidate,
            prefer_backbone=False,
        )
        if neighbor is None:
            self._record_packet_event_once(packet, 'fallback_fail_no_candidate_count')
            return None
        packet.mwmp_fallback_used = True
        self.simulator.metrics.record_routing_event('fallback_success_count')
        return neighbor

    def _mark_fallback_attempt(self, packet):
        self._record_packet_event_once(packet, 'fallback_attempt_count')
        if getattr(packet, 'mwmp_fallback_used', False):
            self._record_packet_event_once(packet, 'fallback_fail_already_used_count')
            return True
        return False

    def _record_packet_event_once(self, packet, event_name):
        event_key = (self.my_drone.identifier, event_name)
        if event_key in packet.mwmp_recorded_events:
            return False
        packet.mwmp_recorded_events.add(event_key)
        self.simulator.metrics.record_routing_event(event_name)
        return True

    def _select_best_neighbor(self, target_drone, packet, predicate, prefer_backbone):
        best_neighbor = None
        best_score = None
        current_distance = euclidean_distance_3d(self.my_drone.coords, target_drone.coords)
        for candidate in self._reachable_neighbors():
            if not predicate(candidate):
                continue
            candidate_distance = euclidean_distance_3d(candidate.coords, target_drone.coords)
            progress = current_distance - candidate_distance
            if candidate.identifier != target_drone.identifier and progress < config.CH_ONLY_PROGRESS_THRESHOLD:
                continue
            score = self._score_neighbor(candidate, target_drone, progress, prefer_backbone)
            if best_score is None or score > best_score:
                best_neighbor = candidate
                best_score = score
        return best_neighbor

    def _reachable_neighbors(self):
        neighbors = []
        for drone in self.simulator.drones:
            if drone.identifier == self.my_drone.identifier:
                continue
            if getattr(drone, 'sleep', False):
                continue
            if self._is_reachable_neighbor(drone):
                neighbors.append(drone)
        return neighbors

    def _score_neighbor(self, candidate, target_drone, progress, prefer_backbone):
        energy_ratio = getattr(candidate, 'residual_energy', 0.0) / max(1.0, float(config.INITIAL_ENERGY))
        let_score = float(getattr(candidate, 'avg_let', 0.0))
        distance_bonus = max(
            0.0,
            (config.COMMUNICATION_RANGE - euclidean_distance_3d(self.my_drone.coords, candidate.coords)) / max(1.0, config.COMMUNICATION_RANGE),
        )
        score = progress + 0.2 * energy_ratio + 0.05 * let_score + 0.1 * distance_bonus
        if candidate.identifier == target_drone.identifier:
            score += 100.0
        if prefer_backbone and self._is_backbone_node(candidate):
            score += 10.0
        return score

    @staticmethod
    def _is_backbone_node(drone):
        return (
            getattr(drone, 'cluster_role', None) in ('CH', 'BS')
            or getattr(drone, 'is_backbone_connector', False)
        )

    def _is_reachable_neighbor(self, drone):
        return self._is_reachable_between(self.my_drone, drone)

    def _is_reachable_between(self, src_drone, dst_drone):
        if getattr(src_drone, 'sleep', False) or getattr(dst_drone, 'sleep', False):
            return False
        return euclidean_distance_3d(src_drone.coords, dst_drone.coords) <= config.COMMUNICATION_RANGE
