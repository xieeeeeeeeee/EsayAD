class Selection:
    """Reject old background responses after selection/search changes."""
    def __init__(self):
        self.generation = 0
        self.raw = self.export = self.lcsc = None

    def reset(self):
        self.generation += 1
        self.raw = self.export = self.lcsc = None
        return self.generation

    def accept(self, generation, lcsc, raw):
        if generation != self.generation:
            return False
        self.lcsc, self.raw = lcsc, raw
        return True
