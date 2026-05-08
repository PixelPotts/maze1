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
SUB_STEPS   = 4

BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
BLUE    = (0, 100, 255)
RED     = (255, 50, 50)
GRAY    = (40, 40, 40)
DKGRAY  = (25, 25, 25)
LTGRAY  = (120, 120, 120)

# ── Mutable settings ──────────────────────────────────────
settings = {
    "slide_speed": 1600,     # px/sec primary
    "curve_speed": 100,      # px/sec lateral
    "player_size": 50,       # px
    "wall_thick":  4,        # px
}

SLIDER_DEFS = [
    ("slide_speed", "Slide Speed",  200, 4000, "{:.0f} px/s"),
    ("curve_speed", "Curve Speed",  10,  500,  "{:.0f} px/s"),
    ("player_size", "Player Size",  10,  90,   "{:.0f} px"),
    ("wall_thick",  "Wall Width",   1,   20,   "{:.0f} px"),
]


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
        "primary": None,
    }


def _cell(v):
    return max(0, min(GRID - 1, int(v) // CELL))


def _wall_in_rows(maze, col, wall, py, half):
    r0 = _cell(py - half)
    r1 = _cell(py + half - 0.001)
    return any(maze[r][col][wall] for r in range(r0, r1 + 1))


def _wall_in_cols(maze, row, wall, px, half):
    c0 = _cell(px - half)
    c1 = _cell(px + half - 0.001)
    return any(maze[row][c][wall] for c in range(c0, c1 + 1))


def update_player(maze, p, keys, curve, dt):
    if not p["moving"]:
        return

    spd = settings["slide_speed"]
    crv = settings["curve_speed"]
    half = settings["player_size"] // 2

    if p["primary"] == "x":
        neg, pos = curve["y"]
        p["vy"] = -crv if keys[neg] else crv if keys[pos] else 0.0
    else:
        neg, pos = curve["x"]
        p["vx"] = -crv if keys[neg] else crv if keys[pos] else 0.0

    sub_dt = dt / SUB_STEPS
    for _ in range(SUB_STEPS):
        if not p["moving"]:
            break

        npx = p["px"] + p["vx"] * sub_dt
        npy = p["py"] + p["vy"] * sub_dt

        cx = _cell(p["px"])
        cy = _cell(p["py"])

        hx = False
        if p["vx"] > 0:
            bnd = (cx + 1) * CELL
            if npx + half > bnd and _wall_in_rows(maze, cx, "E", p["py"], half):
                npx = bnd - half; hx = True
        elif p["vx"] < 0:
            bnd = cx * CELL
            if npx - half < bnd and _wall_in_rows(maze, cx, "W", p["py"], half):
                npx = bnd + half; hx = True
        p["px"] = npx

        hy = False
        if p["vy"] > 0:
            bnd = (cy + 1) * CELL
            if npy + half > bnd and _wall_in_cols(maze, cy, "S", p["px"], half):
                npy = bnd - half; hy = True
        elif p["vy"] < 0:
            bnd = cy * CELL
            if npy - half < bnd and _wall_in_cols(maze, cy, "N", p["px"], half):
                npy = bnd + half; hy = True
        p["py"] = npy

        if (p["primary"] == "x" and hx) or (p["primary"] == "y" and hy):
            p["vx"] = 0.0; p["vy"] = 0.0; p["moving"] = False
            break


# ── Options menu ──────────────────────────────────────────
class Slider:
    def __init__(self, x, y, w, h, key, label, lo, hi, fmt):
        self.rect = pygame.Rect(x, y, w, h)
        self.key = key
        self.label = label
        self.lo = lo
        self.hi = hi
        self.fmt = fmt
        self.dragging = False

    @property
    def t(self):
        return (settings[self.key] - self.lo) / (self.hi - self.lo)

    def val_from_x(self, mx):
        t = max(0.0, min(1.0, (mx - self.rect.x) / self.rect.w))
        settings[self.key] = self.lo + t * (self.hi - self.lo)

    def handle_event(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.rect.collidepoint(ev.pos):
                self.dragging = True
                self.val_from_x(ev.pos[0])
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.dragging = False
        elif ev.type == pygame.MOUSEMOTION and self.dragging:
            self.val_from_x(ev.pos[0])

    def draw(self, surf, font):
        # Track background
        pygame.draw.rect(surf, DKGRAY, self.rect, border_radius=4)
        # Fill
        fill = pygame.Rect(self.rect.x, self.rect.y,
                           int(self.rect.w * self.t), self.rect.h)
        pygame.draw.rect(surf, LTGRAY, fill, border_radius=4)
        # Border
        pygame.draw.rect(surf, WHITE, self.rect, 1, border_radius=4)
        # Handle
        hx = self.rect.x + int(self.rect.w * self.t)
        handle = pygame.Rect(hx - 6, self.rect.y - 4, 12, self.rect.h + 8)
        pygame.draw.rect(surf, WHITE, handle, border_radius=3)
        # Label
        lbl = font.render(self.label, True, WHITE)
        surf.blit(lbl, (self.rect.x, self.rect.y - 28))
        # Value
        val = font.render(self.fmt.format(settings[self.key]), True, LTGRAY)
        surf.blit(val, (self.rect.right - val.get_width(), self.rect.y - 28))


def run_options(screen, clock):
    font = pygame.font.SysFont("monospace", 18)
    title_font = pygame.font.SysFont("monospace", 32, bold=True)

    panel_w, panel_h = 500, 380
    px = (WINDOW - panel_w) // 2
    py = (WINDOW - panel_h) // 2

    sliders = []
    sx = px + 40
    sw = panel_w - 80
    sy_start = py + 70
    for i, (key, label, lo, hi, fmt) in enumerate(SLIDER_DEFS):
        sy = sy_start + i * 75
        sliders.append(Slider(sx, sy, sw, 20, key, label, lo, hi, fmt))

    overlay = pygame.Surface((WINDOW, WINDOW), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return
                if ev.key == pygame.K_o and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    return
            for s in sliders:
                s.handle_event(ev)

        screen.blit(overlay, (0, 0))

        # Panel
        panel = pygame.Rect(px, py, panel_w, panel_h)
        pygame.draw.rect(screen, GRAY, panel, border_radius=8)
        pygame.draw.rect(screen, WHITE, panel, 1, border_radius=8)

        # Title
        ttl = title_font.render("OPTIONS", True, WHITE)
        screen.blit(ttl, (px + (panel_w - ttl.get_width()) // 2, py + 18))

        # Hint
        hint = font.render("Ctrl+O / Esc to close", True, LTGRAY)
        screen.blit(hint, (px + (panel_w - hint.get_width()) // 2, py + panel_h - 32))

        for s in sliders:
            s.draw(screen, font)

        pygame.display.flip()
        clock.tick(60)


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
        p["vx"] = dx * settings["slide_speed"]
        p["vy"] = dy * settings["slide_speed"]
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
                if ev.key == pygame.K_o and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    run_options(screen, clock)
                    continue
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

        wt = int(settings["wall_thick"])
        for r in range(GRID):
            for c in range(GRID):
                cell = maze[r][c]
                x0, y0 = c * CELL, r * CELL
                x1, y1 = x0 + CELL, y0 + CELL
                if cell["N"]:
                    pygame.draw.line(screen, WHITE, (x0, y0), (x1, y0), wt)
                if cell["S"]:
                    pygame.draw.line(screen, WHITE, (x0, y1), (x1, y1), wt)
                if cell["E"]:
                    pygame.draw.line(screen, WHITE, (x1, y0), (x1, y1), wt)
                if cell["W"]:
                    pygame.draw.line(screen, WHITE, (x0, y0), (x0, y1), wt)

        psz = int(settings["player_size"])
        ph = psz // 2
        for p, color in [(blue, BLUE), (red, RED)]:
            rect = pygame.Rect(int(p["px"]) - ph, int(p["py"]) - ph, psz, psz)
            pygame.draw.rect(screen, color, rect)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
