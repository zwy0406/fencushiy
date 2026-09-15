class Poi:
    def __init__(self, poi_id, coords, speed=0.0):
        self.poi_id = poi_id
        self.coords = list(coords)
        self.speed = speed
        self.velocity = [0.0, 0.0, 0.0]
        self.history = []

