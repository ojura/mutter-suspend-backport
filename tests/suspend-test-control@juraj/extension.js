// Test helper for the isolated headless gnome-shell only. It leaves the
// Activities overview that a plain GNOME session starts in, keeps every
// window whose title starts with "cover" above the others, and exports
// org.gnome.Shell.SuspendTest on the session bus at
// /org/gnome/Shell/SuspendTest, so that a test driver can move, minimize
// and activate windows, open and close the overview, switch workspaces and
// lock the screen. Each call is logged with the window stack.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const IFACE = `
<node>
  <interface name="org.gnome.Shell.SuspendTest">
    <method name="Move">
      <arg type="s" direction="in" name="title"/>
      <arg type="i" direction="in" name="x"/>
      <arg type="i" direction="in" name="y"/>
      <arg type="s" direction="out" name="result"/>
    </method>
    <method name="Minimize">
      <arg type="s" direction="in" name="title"/>
      <arg type="s" direction="out" name="result"/>
    </method>
    <method name="Unminimize">
      <arg type="s" direction="in" name="title"/>
      <arg type="s" direction="out" name="result"/>
    </method>
    <method name="Activate">
      <arg type="s" direction="in" name="title"/>
      <arg type="s" direction="out" name="result"/>
    </method>
    <method name="MoveToWorkspace">
      <arg type="s" direction="in" name="title"/>
      <arg type="i" direction="in" name="index"/>
      <arg type="s" direction="out" name="result"/>
    </method>
    <method name="ShowOverview">
      <arg type="s" direction="out" name="result"/>
    </method>
    <method name="HideOverview">
      <arg type="s" direction="out" name="result"/>
    </method>
    <method name="Lock">
      <arg type="s" direction="out" name="result"/>
    </method>
    <method name="Unlock">
      <arg type="s" direction="out" name="result"/>
    </method>
    <method name="Describe">
      <arg type="s" direction="out" name="result"/>
    </method>
  </interface>
</node>`;

function findWindow(title) {
    const window = global.get_window_actors()
        .map(actor => actor.meta_window)
        .find(w => w.get_title() === title);
    if (!window)
        throw new Error(`no window titled ${title}`);
    return window;
}

function describe() {
    const stack = global.display.sort_windows_by_stacking(
        global.get_window_actors().map(actor => actor.meta_window));
    const windows = stack.map(window => {
        const rect = window.get_frame_rect();
        const actor = window.get_compositor_private();
        return `${window.get_title()} ${rect.width}x${rect.height}+${rect.x}+${rect.y}` +
            ` ws${window.get_workspace()?.index() ?? '-'}` +
            `${window.is_above() ? ' above' : ''}${window.is_fullscreen() ? ' fullscreen' : ''}` +
            `${window.minimized ? ' minimized' : ''}${window.is_hidden() ? ' hidden' : ''}` +
            `${actor?.is_mapped() ? ' actor-mapped' : ' actor-unmapped'}` +
            `${window.has_focus() ? ' focused' : ''}`;
    });
    const workspace = global.workspace_manager.get_active_workspace_index();
    return `overview ${Main.overview.visible ? 'shown' : 'hidden'}; ` +
        `window group ${global.window_group.is_mapped() ? 'mapped' : 'unmapped'}; ` +
        `session mode ${Main.sessionMode.currentMode}; active workspace ${workspace}; ` +
        `stack bottom to top: ${windows.join(' | ')}`;
}

export default class SuspendTestControl extends Extension {
    enable() {
        if (Main.layoutManager._startingUp)
            this._startupId = Main.layoutManager.connect('startup-complete', () => Main.overview.hide());
        else
            Main.overview.hide();

        this._createdId = global.display.connect('window-created', (_display, window) => {
            const place = () => {
                if (window.get_title()?.startsWith('cover') && !window.is_above()) {
                    window.make_above();
                    window.raise();
                    console.log(`suspend-test-control: ${window.get_title()} placed above`);
                }
            };
            window.connect('notify::title', place);
            window.connect('shown', place);
            place();
        });

        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 5, () => {
            console.log(`suspend-test-control: ${describe()}`);
            return GLib.SOURCE_CONTINUE;
        });

        this._dbus = Gio.DBusExportedObject.wrapJSObject(IFACE, this);
        this._dbus.export(Gio.DBus.session, '/org/gnome/Shell/SuspendTest');
    }

    disable() {
        this._dbus.unexport();
        global.display.disconnect(this._createdId);
        if (this._startupId)
            Main.layoutManager.disconnect(this._startupId);
        GLib.source_remove(this._timer);
    }

    _run(name, action) {
        let result;
        try {
            result = `${action() ?? 'done'}`;
        } catch (e) {
            result = `error: ${e.message}`;
        }
        console.log(`suspend-test-control: ${name}: ${result}`);
        return result;
    }

    Move(title, x, y) {
        return this._run(`Move ${title} ${x} ${y}`, () => findWindow(title).move_frame(true, x, y));
    }

    Minimize(title) {
        return this._run(`Minimize ${title}`, () => findWindow(title).minimize());
    }

    Unminimize(title) {
        return this._run(`Unminimize ${title}`, () => findWindow(title).unminimize());
    }

    Activate(title) {
        return this._run(`Activate ${title}`,
            () => findWindow(title).activate(global.get_current_time()));
    }

    MoveToWorkspace(title, index) {
        return this._run(`MoveToWorkspace ${title} ${index}`,
            () => findWindow(title).change_workspace_by_index(index, false));
    }

    ShowOverview() {
        return this._run('ShowOverview', () => Main.overview.show());
    }

    HideOverview() {
        return this._run('HideOverview', () => Main.overview.hide());
    }

    Lock() {
        return this._run('Lock', () => {
            if (!Main.screenShield)
                throw new Error('this session has no screen shield');
            Main.screenShield.lock(false);
            return `locked=${Main.screenShield.locked}`;
        });
    }

    Unlock() {
        return this._run('Unlock', () => {
            Main.screenShield.deactivate(false);
            return `locked=${Main.screenShield.locked}`;
        });
    }

    Describe() {
        return describe();
    }
}
