import logging
from utils.ieee_802_11 import IeeeStandard

IEEE_802_11 = IeeeStandard().b_802_11

# --------------------- simulation parameters --------------------- #
MAP_LENGTH = 1000  # m, length of the map
MAP_WIDTH = 1000  # m, width of the map
MAP_HEIGHT = 300  # m, height of the map
SIM_TIME = 1000 * 1e6  # us, total simulation time
NUMBER_OF_DRONES = 10  # number of drones in the network
GRID_RESOLUTION = 20  # grid the map for path planning
STATIC_CASE = 0  # whether to simulate a static network
HETEROGENEOUS = 0  # heterogeneous network support (in terms of speed)
LOGGING_LEVEL = logging.INFO  # whether to print the detail information during simulation
DEFAULT_UAV_SPEED = 10
DATA_PACKET_RATE = 5  # packets per second per active UAV under Poisson traffic
MOBILITY_MODEL = 'GaussMarkov3D'
ROUTING_PROTOCOL = 'DSDV'  # DSDV or MWMP_DCA
ENABLE_VISUALIZATION = True
ENABLE_PLOTS = True
RESULTS_DIR = 'results'
EXPERIMENT_NAME = 'default'

# --------------------- MWMP-DCA parameters ---------------------- #
UAV_COUNT_LIST = [40, 60, 80]
UAV_SPEED_LIST = [10, 15, 20, 25, 30]
POI_COUNT_LIST = [100, 200, 300]
POI_SPEED_LIST = [0, 1, 3, 5, 10]
COMMUNICATION_RANGE = 200  # m, used by clustering and trajectory-based LET
CLUSTER_INTERVAL = 1 * 1e6  # us
TRAJECTORY_HISTORY_SIZE = 20
PREDICTION_HORIZON = 5  # seconds
BS_NODE_ID = 0
BS_POSITION = (500, 500, 150)
CH_MAX_LIFETIME = 60 * 1e6  # us
CH_MIN_ENERGY_RATIO = 0.25
CH_LET_DROP_RATIO = 0.55
CH_MAX_LOAD = 8
CH_ROTATION_WEIGHT_MARGIN = 0.08
CH_ROTATION_STABLE_ROUNDS = 3
GA_CH_PERSISTENCE_BONUS = 0.0
CH_MOBILITY_ROTATION_THRESHOLD = 0.75
TLET_SMOOTHING_ALPHA = 1.0
ADAPTIVE_CH_ROTATION = False
CH_ROTATION_STABILITY_MARGIN_BONUS = 0.0
CH_ROTATION_TLET_GAIN_MARGIN = 0.10
CH_ROTATION_SCORE_LOSS_TOLERANCE = 0.02
CLUSTER_BACKOFF_MAX = 0.25 * 1e6  # us
CLUSTER_ALGORITHM = 'MWMP_DCA'  # Includes MDCS and TDC_MOPSO recent baselines
MWMP_WEIGHT_PROFILE = 'W2'
ENGINEERING_MODE = 'conservative_core_v1'
PREDICTOR_POLICY = {
    'mode': 'kinematic',
    'lstm_enabled': False,
}
PREDICTOR_MODE = 'kinematic'  # kinematic or lstm
CH_ONLY_ENABLE_LOCAL_BACKUP = True
CH_ONLY_ENABLE_NEIGHBOR_FALLBACK = True
CH_ONLY_PROGRESS_THRESHOLD = 5.0  # m, require measurable progress toward the relay target
USE_LSTM_PREDICTOR = False
USE_GAT_FEATURE = True
USE_TLET = True
USE_MOBILITY_FACTOR = True
USE_HYBRID_WEIGHT = True
USE_BACKOFF_ELECTION = True
USE_CH_ROTATION = True
USE_BACKBONE_CONNECTORS = False
BACKBONE_RELAY_HOLD_ROUNDS = 0
USE_POI_AWARE_WEIGHT = True
POI_WEIGHT = 0.10
MWMP_WEIGHT_PROFILES = {
    'W1': {'energy': 0.30, 'link_quality': 0.20, 'density': 0.15, 'tlet': 0.30, 'mobility': -0.05, 'load': 0.00, 'poi': 0.00},
    'W2': {'energy': 0.25, 'link_quality': 0.20, 'density': 0.15, 'tlet': 0.30, 'mobility': -0.10, 'load': 0.00, 'poi': 0.00},
    'W3': {'energy': 0.30, 'link_quality': 0.10, 'density': 0.10, 'tlet': 0.35, 'mobility': -0.10, 'load': -0.05},
    'W4': {'energy': 0.20, 'link_quality': 0.20, 'density': 0.20, 'tlet': 0.30, 'mobility': -0.10, 'load': 0.00},
}
ENABLE_POI = False
POI_COUNT = 100
POI_MOVEMENT_MODEL = 'RandomWalk'
ALLOW_MODEL_FALLBACK = True
DATA_DIR = 'data'
MODELS_DIR = 'models'
MODELS_OUTPUT_DIR = 'results/models'
RESULTS_METRICS_DIRNAME = 'metrics'
RESULTS_FIGURES_DIRNAME = 'figures'
RESULTS_LOGS_DIRNAME = 'logs'
RESULTS_MODELS_DIRNAME = 'models'
LSTM_MODEL_PATH = 'models/lstm/best.pt'
LSTM_CONFIG_PATH = 'models/config/lstm_config.json'
GAT_MODEL_PATH = 'models/gat/best.pt'
GAT_CONFIG_PATH = 'models/config/gat_config.json'
MODEL_DEVICE = 'auto'  # auto, cpu, cuda
CUDA_DEVICE_INDEX = 0
GA_WEIGHT_FILE = 'models/config/ga_mp_dca_weights.json'
WEIGHT_SEARCH_OUTPUT_FILE = 'models/config/ga_mp_dca_weights.json'
MODEL_STATUS = {
    'lstm': 'disabled',
    'gat': 'disabled',
    'ga_mode': 'inactive',
}
LEACH_CLUSTER_HEAD_RATIO = 0.20
KMEANS_CLUSTER_DIVISOR = 8
TDC_MOPSO_SWARM_SIZE = 12
TDC_MOPSO_ITERATIONS = 8
TDC_MOPSO_ARCHIVE_SIZE = 24
TDC_MOPSO_INERTIA = 0.72
TDC_MOPSO_COGNITIVE = 1.45
TDC_MOPSO_SOCIAL = 1.45
TDC_MOPSO_MUTATION_RATE = 0.05
TDC_MOPSO_OBJECTIVE_WEIGHTS = [0.25, 0.25, 0.20, 0.20, 0.10]
GA_SCORE_WEIGHTS = {
    'w1_energy': 0.24,
    'w2_link_quality': 0.18,
    'w3_tlet': 0.30,
    'w4_topology': 0.20,
    'w5_mobility': 0.08,
}
GA_WEIGHT_SEARCH_SPACE = {
    'energy': [0.20, 0.24, 0.28],
    'link_quality': [0.14, 0.18, 0.22],
    'tlet': [0.24, 0.30, 0.36],
    'topology': [0.12, 0.18, 0.24],
    'mobility': [0.06, 0.08, 0.10],
}
EXPORT_DATASET = False
EXPORT_GRAPH_DATASET = False
EXPORT_TRAJECTORY_DATASET = False
DATASET_SCENARIO_TAG = 'default'
GRAPH_FEATURE_DIM = 4
GAT_EMBED_DIM = 8
GAT_HIDDEN_DIM = 16
GAT_HEADS = 2
LSTM_INPUT_DIM = 6
LSTM_HIDDEN_DIM = 64
LSTM_LAYERS = 2

# ---------- hardware parameters of drone (rotary-wing) -----------#
PROFILE_DRAG_COEFFICIENT = 0.012
AIR_DENSITY = 1.225  # kg/m^3
ROTOR_SOLIDITY = 0.05  # defined as the ratio of the total blade area to disc area
ROTOR_DISC_AREA = 0.79  # m^2
BLADE_ANGULAR_VELOCITY = 400  # radians/second
ROTOR_RADIUS = 0.5  # m
INCREMENTAL_CORRECTION_FACTOR = 0.1
AIRCRAFT_WEIGHT = 100  # Newton
ROTOR_BLADE_TIP_SPEED = 500
MEAN_ROTOR_VELOCITY = 7.2  # mean rotor induced velocity in hover
FUSELAGE_DRAG_RATIO = 0.3
INITIAL_ENERGY = 20 * 1e3  # in joule
ENERGY_THRESHOLD = 2000  # in joule
MAX_QUEUE_SIZE = 200  # maximum size of drone's queue

# ----------------------- radio parameters ----------------------- #
TRANSMITTING_POWER = 0.1  # in Watt
LIGHT_SPEED = 3 * 1e8  # light speed (m/s)
CARRIER_FREQUENCY = IEEE_802_11['carrier_frequency']  # carrier frequency (Hz)
NOISE_POWER = 4 * 1e-11  # noise power (Watt)
RADIO_SWITCHING_TIME = 100  # us, the switching time of the transceiver mode
SNR_THRESHOLD = IEEE_802_11['snr_threshold']

# ---------------------- packet parameters ----------------------- #
VARIABLE_PAYLOAD_LENGTH = 0  # whether to consider random payload length of data packet
AVERAGE_PAYLOAD_LENGTH = 1024 * 8  # in bit, 1024 bytes
MAXIMUM_PAYLOAD_VARIATION = 1600  # in bit
MAX_TTL = NUMBER_OF_DRONES + 1  # maximum time-to-live value
PACKET_LIFETIME = 10 * 1e6  # 10s
IP_HEADER_LENGTH = 20 * 8  # header length in network layer, 20 byte
MAC_HEADER_LENGTH = 14 * 8  # header length in mac layer, 14 byte

# ---------------------- physical layer -------------------------- #
PATH_LOSS_EXPONENT = 2  # for large-scale fading
PLCP_PREAMBLE = 128 + 16  # including synchronization and SFD (start frame delimiter)
PLCP_HEADER = 8 + 8 + 16 + 16  # including signal, service, length and HEC (header error check)
PHY_HEADER_LENGTH = PLCP_PREAMBLE + PLCP_HEADER  # header length in physical layer, PLCP preamble + PLCP header

ACK_HEADER_LENGTH = 16 * 8  # header length of ACK packet, 16 byte
ACK_PACKET_LENGTH = ACK_HEADER_LENGTH + 14 * 8  # bit

HELLO_PACKET_PAYLOAD_LENGTH = 256  # bit
HELLO_PACKET_LENGTH = IP_HEADER_LENGTH + MAC_HEADER_LENGTH + PHY_HEADER_LENGTH + HELLO_PACKET_PAYLOAD_LENGTH

# define the range of "id" of different types of packets
"""
|--------------|--------------|--------------|--------------|--------------|
0            10000          20000          30000          40000    
|   data pkt   |   hello pkt  |    ack pkt   |    vf pkt    |   grad msg   |
"""
GL_ID_DATA_PACKET = 0
GL_ID_HELLO_PACKET = 10000
GL_ID_ACK_PACKET = 20000
GL_ID_VF_PACKET = 30000
GL_ID_GRAD_MESSAGE = 40000

# ------------------ physical layer parameters ------------------- #
BIT_RATE = IEEE_802_11['bit_rate']
BIT_TRANSMISSION_TIME = 1/BIT_RATE * 1e6
BANDWIDTH = IEEE_802_11['bandwidth']
SENSING_RANGE = 750  # in meter, defines the area where a sending node can disturb a transmission from a third node

# --------------------- mac layer parameters --------------------- #
SLOT_DURATION = IEEE_802_11['slot_duration']
SIFS_DURATION = IEEE_802_11['SIFS']
DIFS_DURATION = SIFS_DURATION + (2 * SLOT_DURATION)
CW_MIN = 31  # initial contention window size
ACK_TIMEOUT = ACK_PACKET_LENGTH / BIT_RATE * 1e6 + SIFS_DURATION + 50  # maximum waiting time for ACK, in us
MAX_RETRANSMISSION_ATTEMPT = 5
