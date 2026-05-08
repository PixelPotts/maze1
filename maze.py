import pygame
import random
import sys

# ── Constants ──────────────────────────────────────────────
WINDOW     = 1000
CELL       = 100
GRID       = WINDOW // CELL          # 10x10
WALL_W     = 4
PLAYER_SZ  = 50
LERP_SPEED = 1600                    # px/sec – fast slide

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BLUE  = (0, 100, 255)
RED   = (255, 50, 50)


# ── Maze generation (recursive back-tracker) ──────────────
def generate_maze(w, h):
    """Return 2-D list of cells; each cell is a dict with wall flags."""
    cells = [
        [{"N": True, "E": True, "S": True, "W": True} for _ in range(w)]
        for _ in range(h)
    ]
    visited = [[False] * w for _ in range(h)]

    dirs = {
        "N": (0, -1, "S"),
        "S": (0,  1, "N"),
        "E": (1,  0, "W"),
        "W": (-1, 0, "E"),
    }

    stack = [(0, 0)]
    visited[0][0] = True

    while stack:
        x, y = stack[-1]
        neighbours = []
        for d, (dx, dy, opp) in dirs.items():
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                neighbours.append((d, nx, ny, opp))
        if neighbours:
            d, nx, ny, opp = random.choice(neighbours)
            cells[y][x][d] = False
            cells[ny][nx][opp] = False
            visited[ny][nx] = True
            stack.append((nx, ny))
        else:
            stack.pop()

    return cells


# ── Helper: how far can we slide? ─────────────────────────
def slide_target(maze, gx, gy, dx, dy):
    """Walk from (gx,gy) in direction (dx,dy) until a wall blocks."""
    wall_map = {
        (1, 0):  "E",
        (-1, 0): "W",
        (0, -1): "N",
        (0, 1):  "S",
    }
    wall_key = wall_map[(dx, dy)]

    cx, cy = gx, gy
    while True:
        if maze[cy][cx][wall_key]:
            break
        nx, ny = cx + dx, cy + dy
        if nx < 0 or nx >= GRID or ny < 0 or ny >= GRID:
            break
        cx, cy = nx, ny
    return cx, cy


# ── Main loop ─────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW, WINDOW))
    pygame.display.set_caption("Maze")
    clock = pygame.time.Clock()

    maze = generate_maze(GRID, GRID)

    # Per-player state: [grid_x, grid_y, pixel_x, pixel_y, target_x, target_y, moving]
    def make_player():
        cx = float(0 * CELL + CELL // 2)
        cy = float(0 * CELL + CELL // 2)
        return {"gx": 0, "gy": 0, "px": cx, "py": cy, "tx": cx, "ty": cy, "moving": False}

    blue = make_player()   # WASD
    red  = make_player()   # Arrow keys

    # Key bindings per player
    blue_keys = {pygame.K_w: (0, -1), pygame.K_s: (0, 1),
                 pygame.K_a: (-1, 0), pygame.K_d: (1, 0)}
    red_keys  = {pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1),
                 pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0)}

    def try_move(p, dx, dy):
        if p["moving"]:
            return
        nx, ny = slide_target(maze, p["gx"], p["gy"], dx, dy)
        if nx != p["gx"] or ny != p["gy"]:
            p["gx"], p["gy"] = nx, ny
            p["tx"] = float(nx * CELL + CELL // 2)
            p["ty"] = float(ny * CELL + CELL // 2)
            p["moving"] = True

    def lerp_player(p, dt):
        if not p["moving"]:
            return
        ddx = p["tx"] - p["px"]
        ddy = p["ty"] - p["py"]
        dist = (ddx * ddx + ddy * ddy) ** 0.5
        step = LERP_SPEED * dt
        if step >= dist or dist < 1:
            p["px"], p["py"] = p["tx"], p["ty"]
            p["moving"] = False
        else:
            p["px"] += ddx / dist * step
            p["py"] += ddy / dist * step

    def draw_player(p, color):
        half = PLAYER_SZ // 2
        rect = pygame.Rect(int(p["px"]) - half, int(p["py"]) - half, PLAYER_SZ, PLAYER_SZ)
        pygame.draw.rect(screen, color, rect)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                if ev.key in blue_keys:
                    dx, dy = blue_keys[ev.key]
                    try_move(blue, dx, dy)
                if ev.key in red_keys:
                    dx, dy = red_keys[ev.key]
                    try_move(red, dx, dy)

        # ── Lerp ──────────────────────────────────────────
        lerp_player(blue, dt)
        lerp_player(red, dt)

        # ── Draw ──────────────────────────────────────────
        screen.fill(BLACK)

        # Walls
        for r in range(GRID):
            for c in range(GRID):
                cell = maze[r][c]
                x0 = c * CELL
                y0 = r * CELL
                x1 = x0 + CELL
                y1 = y0 + CELL
                if cell["N"]:
                    pygame.draw.line(screen, WHITE, (x0, y0), (x1, y0), WALL_W)
                if cell["S"]:
                    pygame.draw.line(screen, WHITE, (x0, y1), (x1, y1), WALL_W)
                if cell["E"]:
                    pygame.draw.line(screen, WHITE, (x1, y0), (x1, y1), WALL_W)
                if cell["W"]:
                    pygame.draw.line(screen, WHITE, (x0, y0), (x0, y1), WALL_W)

        # Blue first, red on top
        draw_player(blue, BLUE)
        draw_player(red, RED)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
