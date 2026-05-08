import pygame
import random
import sys

# ── Constants ──────────────────────────────────────────────
WINDOW      = 1000
CELL        = 100
GRID        = WINDOW // CELL          # 10x10
WALL_W      = 4
PLAYER_SZ   = 50
HALF        = PLAYER_SZ // 2
LERP_SPEED  = 1600                    # px/sec – primary slide
CURVE_SPEED = 100                     # px/sec – lateral drift
SUB_STEPS   = 4

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BLUE  = (0, 100, 255)
RED   = (255, 50, 50)


# ── Maze generation (recursive back-tracker) ──────────────
def generate_maze(w, h):
    cells = [
        [{"N": True, "E": True, "S": True, "W": True} for _ in range(w)]
        for _ in range(h)
    ]
    visited = [[False] * w for _ in range(h)]
    dirs = {
        "N": (0, -1, "S"), "S": (0, 1, "N"),
        "E": (1, 0, "W"),  "W": (-1, 0, "E"),
    }
    stack = [(0, 0)]
    visited[0][0] = True
    while stack:
        x, y = stack[-1]
        nbrs = []
        for d, (dx, dy, opp) in dirs.items():
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                nbrs.append((d, nx, ny, opp))
        if nbrs:
            d, nx, ny, opp = random.choice(nbrs)
            cells[y][x][d] = False
            cells[ny][nx][opp] = False
            visited[ny][nx] = True
            stack.append((nx, ny))
        else:
            stack.pop()
    return cells


# ── Player helpers ─────────────────────────────────────────
def make_player():
    cx = float(CELL // 2)
    cy = float(CELL // 2)
    return {
        "px": cx, "py": cy,
        "vx": 0.0, "vy": 0.0,
        "moving": False,
        "primary": None,       # 'x' or 'y'
    }


def _cell(v):
    """Pixel coord → clamped cell index."""
    return max(0, min(GRID - 1, int(v) // CELL))


def _rows(py):
    """Return (top_row, bot_row) the player currently spans."""
    return _cell(py - HALF), _cell(py + HALF - 0.001)


def _cols(px):
    """Return (left_col, right_col) the player currently spans."""
    return _cell(px - HALF), _cell(px + HALF - 0.001)


def _wall_in_rows(maze, col, wall, r0, r1):
    return any(maze[r][col][wall] for r in range(r0, r1 + 1))


def _wall_in_cols(maze, row, wall, c0, c1):
    return any(maze[row][c][wall] for c in range(c0, c1 + 1))


def update_player(maze, p, keys, curve, dt):
    if not p["moving"]:
        return

    # Set curve velocity from held perpendicular keys
    if p["primary"] == "x":
        neg, pos = curve["y"]
        p["vy"] = -CURVE_SPEED if keys[neg] else CURVE_SPEED if keys[pos] else 0.0
    else:
        neg, pos = curve["x"]
        p["vx"] = -CURVE_SPEED if keys[neg] else CURVE_SPEED if keys[pos] else 0.0

    sub_dt = dt / SUB_STEPS
    for _ in range(SUB_STEPS):
        if not p["moving"]:
            break

        npx = p["px"] + p["vx"] * sub_dt
        npy = p["py"] + p["vy"] * sub_dt

        cx = _cell(p["px"])
        cy = _cell(p["py"])
        r0, r1 = _rows(p["py"])

        # ── X collision ───────────────────────────────────
        hx = False
        if p["vx"] > 0:
            bnd = (cx + 1) * CELL
            if npx + HALF > bnd and _wall_in_rows(maze, cx, "E", r0, r1):
                npx = bnd - HALF; hx = True
        elif p["vx"] < 0:
            bnd = cx * CELL
            if npx - HALF < bnd and _wall_in_rows(maze, cx, "W", r0, r1):
                npx = bnd + HALF; hx = True
        p["px"] = npx

        c0, c1 = _cols(p["px"])

        # ── Y collision ───────────────────────────────────
        hy = False
        if p["vy"] > 0:
            bnd = (cy + 1) * CELL
            if npy + HALF > bnd and _wall_in_cols(maze, cy, "S", c0, c1):
                npy = bnd - HALF; hy = True
        elif p["vy"] < 0:
            bnd = cy * CELL
            if npy - HALF < bnd and _wall_in_cols(maze, cy, "N", c0, c1):
                npy = bnd + HALF; hy = True
        p["py"] = npy

        # Stop when primary axis hits a wall
        if (p["primary"] == "x" and hx) or (p["primary"] == "y" and hy):
            p["vx"] = 0.0; p["vy"] = 0.0; p["moving"] = False
            break


# ── Main loop ─────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW, WINDOW))
    pygame.display.set_caption("Maze")
    clock = pygame.time.Clock()

    maze = generate_maze(GRID, GRID)

    blue = make_player()
    red  = make_player()

    blue_launch = {
        pygame.K_w: (0, -1), pygame.K_s: (0, 1),
        pygame.K_a: (-1, 0), pygame.K_d: (1, 0),
    }
    red_launch = {
        pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1),
        pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0),
    }
    blue_curve = {"x": (pygame.K_a, pygame.K_d), "y": (pygame.K_w, pygame.K_s)}
    red_curve  = {"x": (pygame.K_LEFT, pygame.K_RIGHT), "y": (pygame.K_UP, pygame.K_DOWN)}

    def launch(p, dx, dy):
        if p["moving"]:
            return
        p["vx"] = dx * LERP_SPEED
        p["vy"] = dy * LERP_SPEED
        p["moving"] = True
        p["primary"] = "x" if dx != 0 else "y"

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                if ev.key in blue_launch:
                    dx, dy = blue_launch[ev.key]
                    launch(blue, dx, dy)
                if ev.key in red_launch:
                    dx, dy = red_launch[ev.key]
                    launch(red, dx, dy)

        keys = pygame.key.get_pressed()
        update_player(maze, blue, keys, blue_curve, dt)
        update_player(maze, red, keys, red_curve, dt)

        # ── Draw ──────────────────────────────────────────
        screen.fill(BLACK)

        for r in range(GRID):
            for c in range(GRID):
                cell = maze[r][c]
                x0, y0 = c * CELL, r * CELL
                x1, y1 = x0 + CELL, y0 + CELL
                if cell["N"]:
                    pygame.draw.line(screen, WHITE, (x0, y0), (x1, y0), WALL_W)
                if cell["S"]:
                    pygame.draw.line(screen, WHITE, (x0, y1), (x1, y1), WALL_W)
                if cell["E"]:
                    pygame.draw.line(screen, WHITE, (x1, y0), (x1, y1), WALL_W)
                if cell["W"]:
                    pygame.draw.line(screen, WHITE, (x0, y0), (x0, y1), WALL_W)

        for p, color in [(blue, BLUE), (red, RED)]:
            rect = pygame.Rect(int(p["px"]) - HALF, int(p["py"]) - HALF,
                               PLAYER_SZ, PLAYER_SZ)
            pygame.draw.rect(screen, color, rect)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
