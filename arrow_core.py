"""Arrow puzzle core: board, rules, solvable level generator, hints."""
import random
import unittest

DIRS = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}


class Board:
    def __init__(self, rows, cols, cells=None):
        self.rows, self.cols = rows, cols
        self.cells = cells or {}  # (r, c) -> 'U'|'D'|'L'|'R'

    def ray(self, r, c):
        """Cells from (r, c) (exclusive) to the edge in the arrow's direction."""
        dr, dc = DIRS[self.cells[(r, c)]]
        r, c = r + dr, c + dc
        while 0 <= r < self.rows and 0 <= c < self.cols:
            yield (r, c)
            r, c = r + dr, c + dc

    def removable(self, r, c):
        return (r, c) in self.cells and all(p not in self.cells for p in self.ray(r, c))

    def removable_arrows(self):
        return [p for p in self.cells if self.removable(*p)]

    def solved(self):
        return not self.cells


def generate(rows, cols, n_arrows, chain_bias=0.6, seed=None):
    """Build a solvable board in reverse.

    Each new arrow is placed only where its ray is clear of existing arrows,
    so removing in reverse placement order always works. chain_bias raises
    the odds of placing a new arrow inside an existing arrow's lane
    (more blocking chains = harder level).
    """
    rng = random.Random(seed)
    board = Board(rows, cols)
    n_arrows = min(n_arrows, rows * cols)
    attempts = 0
    while len(board.cells) < n_arrows and attempts < n_arrows * 50:
        attempts += 1
        empty = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in board.cells]
        if not empty:
            break
        lanes = {p for q in board.cells for p in board.ray(*q)} & set(empty)
        pool = list(lanes) if lanes and rng.random() < chain_bias else empty
        r, c = rng.choice(pool)
        dirs = list(DIRS)
        rng.shuffle(dirs)
        for d in dirs:
            board.cells[(r, c)] = d
            if all(p not in board.cells for p in board.ray(r, c)):
                break
            del board.cells[(r, c)]
    return board


class Game:
    def __init__(self, board, hearts=3):
        self.board, self.hearts = board, hearts

    @property
    def lost(self):
        return self.hearts <= 0

    def tap(self, r, c):
        """Returns 'removed', 'blocked' (costs a heart), or 'ignored'."""
        if self.lost or self.board.solved() or (r, c) not in self.board.cells:
            return "ignored"
        if self.board.removable(r, c):
            del self.board.cells[(r, c)]
            return "removed"
        self.hearts -= 1
        return "blocked"

    def hint(self):
        """Any removable arrow is safe: removals only free paths, never block them."""
        options = self.board.removable_arrows()
        return min(options) if options else None


class Tests(unittest.TestCase):
    def test_ray_and_removable(self):
        b = Board(3, 3, {(1, 1): "R", (1, 2): "U"})
        self.assertFalse(b.removable(1, 1))  # blocked by (1,2)
        self.assertTrue(b.removable(1, 2))

    def test_tap_costs_heart(self):
        g = Game(Board(3, 3, {(1, 1): "R", (1, 2): "U"}), hearts=2)
        self.assertEqual(g.tap(1, 1), "blocked")
        self.assertEqual(g.hearts, 1)
        self.assertEqual(g.tap(1, 2), "removed")
        self.assertEqual(g.tap(1, 1), "removed")
        self.assertTrue(g.board.solved())

    def test_generated_levels_always_solvable(self):
        for seed in range(200):
            g = Game(generate(6, 6, 20, seed=seed))
            while not g.board.solved():
                h = g.hint()
                self.assertIsNotNone(h, f"stuck at seed {seed}")
                self.assertEqual(g.tap(*h), "removed")
            self.assertEqual(g.hearts, 3)

    def test_difficulty_bias_creates_chains(self):
        def blocked(b):
            return len(b.cells) - len(b.removable_arrows())
        hard = sum(blocked(generate(8, 8, 30, 0.9, s)) for s in range(50))
        easy = sum(blocked(generate(8, 8, 30, 0.0, s)) for s in range(50))
        self.assertGreater(hard, easy)


if __name__ == "__main__":
    unittest.main()
