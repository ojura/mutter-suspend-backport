# Builds the test client. Needs libwayland-dev, wayland-protocols and
# wayland-scanner (package libwayland-bin).
XDG_SHELL_XML = /usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml
CFLAGS ?= -O2 -g -Wall -Wextra -Wno-unused-parameter

suspend_client: suspend_client.c xdg-shell-client-protocol.h xdg-shell-protocol.c
	$(CC) $(CFLAGS) -o $@ suspend_client.c xdg-shell-protocol.c $$(pkg-config --cflags --libs wayland-client)

xdg-shell-client-protocol.h: $(XDG_SHELL_XML)
	wayland-scanner client-header $< $@

xdg-shell-protocol.c: $(XDG_SHELL_XML)
	wayland-scanner private-code $< $@

clean:
	rm -f suspend_client xdg-shell-client-protocol.h xdg-shell-protocol.c
