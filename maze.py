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

    # Player state
    gx, gy = 0, 0                          # grid cell
    px = float(gx * CELL + CELL // 2)      # pixel centre
    py = float(gy * CELL + CELL // 2)
    tx, ty = px, py                         # lerp target
    moving = False

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                if not moving:
                    dx, dy = 0, 0
                    if ev.key == pygame.K_w or ev.key == pygame.K_UP:
                        dy = -1
                    elif ev.key == pygame.K_s or ev.key == pygame.K_DOWN:
                        dy = 1
                    elif ev.key == pygame.K_a or ev.key == pygame.K_LEFT:
                        dx = -1
                    elif ev.key == pygame.K_d or ev.key == pygame.K_RIGHT:
                        dx = 1
                    if dx or dy:
                        nx, ny = slide_target(maze, gx, gy, dx, dy)
                        if nx != gx or ny != gy:
                            gx, gy = nx, ny
                            tx = float(gx * CELL + CELL // 2)
                            ty = float(gy * CELL + CELL // 2)
                            moving = True

        # ── Lerp ──────────────────────────────────────────
        if moving:
            ddx = tx - px
            ddy = ty - py
            dist = (ddx * ddx + ddy * ddy) ** 0.5
            step = LERP_SPEED * dt
            if step >= dist or dist < 1:
                px, py = tx, ty
                moving = False
            else:
                px += ddx / dist * step
                py += ddy / dist * step

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

        # Player
        half = PLAYER_SZ // 2
        rect = pygame.Rect(int(px) - half, int(py) - half, PLAYER_SZ, PLAYER_SZ)
        pygame.draw.rect(screen, WHITE, rect)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
