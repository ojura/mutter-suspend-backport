/* Wayland test client for checking when a compositor marks a window as
 * suspended (the xdg_toplevel "suspended" state of xdg-shell version 6).
 *
 * It shows one opaque xdg_toplevel and prints every xdg_toplevel.configure
 * with the wall-clock time (as Unix time and as local time), the time since
 * it started and whether the activated and suspended states are set. Commands on standard input
 * change its subsurfaces while it runs.
 *
 * usage: suspend_client <title> [options]
 *   --size WxH                   window size (default 480x320)
 *   --fullscreen                 ask to be fullscreen and fill the size the
 *                                compositor configures
 *   --hidden-subsurface          before the window is first shown, add a
 *                                subsurface that never gets a buffer
 *   --mapped-subsurface X,Y,WxH  before the window is first shown, add a
 *                                subsurface with an opaque WxH buffer at X,Y
 *
 * Commands, one per line:
 *   add-hidden         add a subsurface without a buffer; the parent commit
 *                      that applies it has no buffer and no damage
 *   map-sub X,Y,WxH    give the newest subsurface an opaque WxH buffer at X,Y
 *   unmap-sub          remove the buffer of the newest subsurface
 *   destroy-sub        destroy the newest subsurface
 *   redraw             attach the window's buffer again with full damage
 *
 * The window geometry is always the main surface, so a subsurface outside
 * it does not change where the compositor places the window.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <poll.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <wayland-client.h>
#include "xdg-shell-client-protocol.h"

#define MAX_SUBSURFACES 8

struct subsurface {
    struct wl_surface *surface;
    struct wl_subsurface *subsurface;
    struct wl_buffer *buffer;
};

static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_subcompositor *subcompositor;
static struct wl_shm *shm;
static struct xdg_wm_base *wm_base;
static struct wl_surface *surface;
static struct xdg_surface *xdg_surface;
static struct wl_buffer *buffer;
static int buffer_width, buffer_height;
static int width = 480, height = 320;
static int configured_width, configured_height;
static const char *title;
static struct timespec start;
static struct subsurface subsurfaces[MAX_SUBSURFACES];
static int n_subsurfaces;

static void log_line(const char *format, ...) __attribute__((format(printf, 1, 2)));

static void log_line(const char *format, ...)
{
    struct timespec now, wall;
    struct tm tm;
    va_list args;

    clock_gettime(CLOCK_MONOTONIC, &now);
    clock_gettime(CLOCK_REALTIME, &wall);
    localtime_r(&wall.tv_sec, &tm);
    printf("%ld.%03ld %02d:%02d:%02d.%03ld %7.2f %s: ", (long) wall.tv_sec, wall.tv_nsec / 1000000,
           tm.tm_hour, tm.tm_min, tm.tm_sec, wall.tv_nsec / 1000000,
           (now.tv_sec - start.tv_sec) + (now.tv_nsec - start.tv_nsec) / 1e9, title);
    va_start(args, format);
    vprintf(format, args);
    va_end(args);
    putchar('\n');
    fflush(stdout);
}

static struct wl_buffer *create_buffer(int w, int h, uint32_t color)
{
    int stride = w * 4, size = stride * h;
    int fd = memfd_create("suspend-client", MFD_CLOEXEC);
    if (fd < 0 || ftruncate(fd, size) < 0) {
        perror("memfd");
        exit(1);
    }
    uint32_t *pixels = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (pixels == MAP_FAILED) {
        perror("mmap");
        exit(1);
    }
    for (int i = 0; i < w * h; i++)
        pixels[i] = color;
    munmap(pixels, size);
    struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, size);
    struct wl_buffer *result =
        wl_shm_pool_create_buffer(pool, 0, w, h, stride, WL_SHM_FORMAT_XRGB8888);
    wl_shm_pool_destroy(pool);
    close(fd);
    return result;
}

static void set_opaque(struct wl_surface *target, int w, int h)
{
    struct wl_region *region = wl_compositor_create_region(compositor);
    wl_region_add(region, 0, 0, w, h);
    wl_surface_set_opaque_region(target, region);
    wl_region_destroy(region);
}

static void draw_main_surface(void)
{
    if (!buffer || buffer_width != width || buffer_height != height) {
        if (buffer)
            wl_buffer_destroy(buffer);
        buffer = create_buffer(width, height, 0xff336699);
        buffer_width = width;
        buffer_height = height;
    }
    set_opaque(surface, width, height);
    xdg_surface_set_window_geometry(xdg_surface, 0, 0, width, height);
    wl_surface_attach(surface, buffer, 0, 0);
    wl_surface_damage_buffer(surface, 0, 0, width, height);
    wl_surface_commit(surface);
}

static struct subsurface *add_subsurface(void)
{
    if (n_subsurfaces == MAX_SUBSURFACES) {
        log_line("too many subsurfaces");
        return NULL;
    }
    struct subsurface *sub = &subsurfaces[n_subsurfaces++];
    sub->surface = wl_compositor_create_surface(compositor);
    sub->subsurface = wl_subcompositor_get_subsurface(subcompositor, sub->surface, surface);
    sub->buffer = NULL;
    return sub;
}

static void map_subsurface(struct subsurface *sub, int x, int y, int w, int h)
{
    if (sub->buffer)
        wl_buffer_destroy(sub->buffer);
    sub->buffer = create_buffer(w, h, 0xffcc6633);
    set_opaque(sub->surface, w, h);
    wl_subsurface_set_position(sub->subsurface, x, y);
    wl_surface_attach(sub->surface, sub->buffer, 0, 0);
    wl_surface_damage_buffer(sub->surface, 0, 0, w, h);
    wl_surface_commit(sub->surface);
}

static int parse_rect(const char *text, int *x, int *y, int *w, int *h)
{
    return sscanf(text, "%d,%d,%dx%d", x, y, w, h) == 4;
}

static void wm_base_ping(void *data, struct xdg_wm_base *base, uint32_t serial)
{
    xdg_wm_base_pong(base, serial);
}
static const struct xdg_wm_base_listener wm_base_listener = { .ping = wm_base_ping };

static void surface_configure(void *data, struct xdg_surface *target, uint32_t serial)
{
    xdg_surface_ack_configure(target, serial);
    if (configured_width > 0 && configured_height > 0) {
        width = configured_width;
        height = configured_height;
    }
    draw_main_surface();
}
static const struct xdg_surface_listener surface_listener = { .configure = surface_configure };

static void toplevel_configure(void *data, struct xdg_toplevel *toplevel, int32_t w, int32_t h,
                               struct wl_array *states)
{
    int suspended = 0, activated = 0, fullscreen = 0;
    uint32_t *state;
    wl_array_for_each(state, states) {
        if (*state == XDG_TOPLEVEL_STATE_SUSPENDED)
            suspended = 1;
        if (*state == XDG_TOPLEVEL_STATE_ACTIVATED)
            activated = 1;
        if (*state == XDG_TOPLEVEL_STATE_FULLSCREEN)
            fullscreen = 1;
    }
    configured_width = w;
    configured_height = h;
    log_line("configure activated=%d suspended=%d fullscreen=%d size=%dx%d",
             activated, suspended, fullscreen, w, h);
}
static void toplevel_close(void *data, struct xdg_toplevel *toplevel)
{
    log_line("close");
    exit(0);
}
static void toplevel_bounds(void *data, struct xdg_toplevel *toplevel, int32_t w, int32_t h) {}
static void toplevel_capabilities(void *data, struct xdg_toplevel *toplevel, struct wl_array *caps) {}
static const struct xdg_toplevel_listener toplevel_listener = {
    .configure = toplevel_configure,
    .close = toplevel_close,
    .configure_bounds = toplevel_bounds,
    .wm_capabilities = toplevel_capabilities,
};

static void registry_global(void *data, struct wl_registry *registry, uint32_t name,
                            const char *interface, uint32_t version)
{
    if (!strcmp(interface, wl_compositor_interface.name))
        compositor = wl_registry_bind(registry, name, &wl_compositor_interface, 4);
    else if (!strcmp(interface, wl_subcompositor_interface.name))
        subcompositor = wl_registry_bind(registry, name, &wl_subcompositor_interface, 1);
    else if (!strcmp(interface, wl_shm_interface.name))
        shm = wl_registry_bind(registry, name, &wl_shm_interface, 1);
    else if (!strcmp(interface, xdg_wm_base_interface.name)) {
        if (version < 6) {
            fprintf(stderr, "xdg_wm_base version %u does not have the suspended state\n", version);
            exit(1);
        }
        wm_base = wl_registry_bind(registry, name, &xdg_wm_base_interface, 6);
        xdg_wm_base_add_listener(wm_base, &wm_base_listener, NULL);
    }
}
static void registry_remove(void *data, struct wl_registry *registry, uint32_t name) {}
static const struct wl_registry_listener registry_listener = {
    .global = registry_global,
    .global_remove = registry_remove,
};

static void run_command(char *line)
{
    struct subsurface *newest = n_subsurfaces ? &subsurfaces[n_subsurfaces - 1] : NULL;
    int x, y, w, h;

    if (!strcmp(line, "add-hidden")) {
        struct subsurface *sub = add_subsurface();
        if (!sub)
            return;
        wl_surface_commit(sub->surface);
        wl_surface_commit(surface);
    } else if (!strncmp(line, "map-sub ", 8) && newest && parse_rect(line + 8, &x, &y, &w, &h)) {
        map_subsurface(newest, x, y, w, h);
        wl_surface_commit(surface);
    } else if (!strcmp(line, "unmap-sub") && newest) {
        wl_surface_attach(newest->surface, NULL, 0, 0);
        wl_surface_commit(newest->surface);
        wl_surface_commit(surface);
    } else if (!strcmp(line, "destroy-sub") && newest) {
        wl_subsurface_destroy(newest->subsurface);
        wl_surface_destroy(newest->surface);
        if (newest->buffer)
            wl_buffer_destroy(newest->buffer);
        n_subsurfaces--;
        wl_surface_commit(surface);
    } else if (!strcmp(line, "redraw")) {
        draw_main_surface();
    } else {
        log_line("unknown or inapplicable command '%s'", line);
        return;
    }
    wl_display_flush(display);
    log_line("command %s", line);
}

int main(int argc, char **argv)
{
    int fullscreen = 0, hidden_subsurface = 0, mapped_subsurface = 0;
    int sub_x = 0, sub_y = 0, sub_w = 0, sub_h = 0;

    if (argc < 2) {
        fprintf(stderr, "usage: %s <title> [--size WxH] [--fullscreen] [--hidden-subsurface]"
                        " [--mapped-subsurface X,Y,WxH]\n", argv[0]);
        return 2;
    }
    title = argv[1];
    for (int i = 2; i < argc; i++) {
        if (!strcmp(argv[i], "--size") && i + 1 < argc &&
            sscanf(argv[i + 1], "%dx%d", &width, &height) == 2)
            i++;
        else if (!strcmp(argv[i], "--fullscreen"))
            fullscreen = 1;
        else if (!strcmp(argv[i], "--hidden-subsurface"))
            hidden_subsurface = 1;
        else if (!strcmp(argv[i], "--mapped-subsurface") && i + 1 < argc &&
                 parse_rect(argv[i + 1], &sub_x, &sub_y, &sub_w, &sub_h)) {
            mapped_subsurface = 1;
            i++;
        } else {
            fprintf(stderr, "unknown or incomplete option %s\n", argv[i]);
            return 2;
        }
    }
    clock_gettime(CLOCK_MONOTONIC, &start);

    display = wl_display_connect(NULL);
    if (!display) {
        fprintf(stderr, "cannot connect to the Wayland display\n");
        return 1;
    }
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    wl_display_roundtrip(display);
    if (!compositor || !subcompositor || !shm || !wm_base) {
        fprintf(stderr, "a required global is missing\n");
        return 1;
    }

    surface = wl_compositor_create_surface(compositor);
    if (hidden_subsurface) {
        struct subsurface *sub = add_subsurface();
        wl_subsurface_set_position(sub->subsurface, 20, 20);
        wl_surface_commit(sub->surface);
    }
    if (mapped_subsurface)
        map_subsurface(add_subsurface(), sub_x, sub_y, sub_w, sub_h);

    xdg_surface = xdg_wm_base_get_xdg_surface(wm_base, surface);
    xdg_surface_add_listener(xdg_surface, &surface_listener, NULL);
    struct xdg_toplevel *toplevel = xdg_surface_get_toplevel(xdg_surface);
    xdg_toplevel_add_listener(toplevel, &toplevel_listener, NULL);
    xdg_toplevel_set_title(toplevel, title);
    if (fullscreen)
        xdg_toplevel_set_fullscreen(toplevel, NULL);
    wl_surface_commit(surface);

    log_line("started%s%s%s", fullscreen ? " fullscreen" : "",
             hidden_subsurface ? " with a hidden subsurface" : "",
             mapped_subsurface ? " with a mapped subsurface" : "");

    char input[4096];
    size_t input_len = 0;
    int stdin_open = 1;
    for (;;) {
        while (wl_display_prepare_read(display) != 0)
            if (wl_display_dispatch_pending(display) < 0)
                goto connection_lost;
        if (wl_display_flush(display) < 0 && errno != EAGAIN) {
            wl_display_cancel_read(display);
            goto connection_lost;
        }
        struct pollfd fds[2] = {
            { .fd = wl_display_get_fd(display), .events = POLLIN },
            { .fd = STDIN_FILENO, .events = POLLIN },
        };
        if (poll(fds, stdin_open ? 2 : 1, -1) < 0) {
            wl_display_cancel_read(display);
            if (errno == EINTR)
                continue;
            perror("poll");
            return 1;
        }
        if (fds[0].revents & (POLLIN | POLLERR | POLLHUP)) {
            if (wl_display_read_events(display) < 0)
                goto connection_lost;
        } else {
            wl_display_cancel_read(display);
        }
        if (wl_display_dispatch_pending(display) < 0)
            goto connection_lost;

        if (stdin_open && (fds[1].revents & (POLLIN | POLLHUP))) {
            ssize_t n = read(STDIN_FILENO, input + input_len, sizeof input - 1 - input_len);
            if (n <= 0) {
                stdin_open = 0;
                continue;
            }
            input_len += n;
            input[input_len] = '\0';
            char *line_start = input, *newline;
            while ((newline = strchr(line_start, '\n'))) {
                *newline = '\0';
                if (*line_start)
                    run_command(line_start);
                line_start = newline + 1;
            }
            input_len -= line_start - input;
            memmove(input, line_start, input_len);
        }
    }

connection_lost:
    log_line("connection to the compositor lost: %s", strerror(errno));
    return 1;
}
