#!/usr/bin/python3
"""Runs the suspend test cases, each in its own isolated headless gnome-shell.

usage: run_cases.py <library set> <results dir> [case ...]

<library set> is "stock" for the mutter libraries installed on the host, or
"patched=<dir>", where <dir> holds the extracted libmutter-14-0 package of a
build; the directory of its libmutter-14.so.0 goes into LD_LIBRARY_PATH, and
the clutter, cogl and mtk libraries stay the installed ones. Each case starts a
shell with the test control extension, starts test clients, and holds a
series of phases. For each window and phase it records the expected state
at the end of the phase for the stock and the patched libraries, and the
evaluation compares the state that the client was last configured with
before the phase ended. A window expected to be active fails the phase if it
was suspended at any time during the phase after having been active in it.

Results go to <results dir>/<case>/: one log per client, the shell log, the
driver's own log with the phase times, the mutter libraries mapped by the
shell, and summary.txt and summary.json for the case. <results dir>/summary.txt
collects all cases.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLIENT = HERE / 'client' / 'suspend_client'
EXTENSION = HERE / 'suspend-test-control@juraj'
LIBDIR = 'usr/lib/x86_64-linux-gnu'

ACTIVE, SUSPENDED = 'active', 'suspended'


class Run:
    def __init__(self, case, library_set, results):
        self.case = case
        self.library_set = library_set
        self.label = 'stock' if library_set == 'stock' else 'patched'
        self.results = results / case
        self.results.mkdir(parents=True, exist_ok=True)
        self.scratch = Path(tempfile.mkdtemp(prefix=f'mutter-suspend-{case}-', dir='/tmp'))
        self.clients = {}
        self.phases = []
        self.log = open(self.results / 'driver.log', 'w')
        self.shell = None
        self.shell_pid = None

    def note(self, text):
        now = time.time()
        stamp = time.strftime('%H:%M:%S', time.localtime(now)) + f'.{int(now % 1 * 1000):03d}'
        self.log.write(f'{now:.3f} {stamp} {text}\n')
        self.log.flush()
        print(f'[{self.label} {self.case}] {stamp} {text}', flush=True)

    def start_shell(self):
        env = os.environ.copy()
        env.pop('LD_LIBRARY_PATH', None)
        if self.library_set != 'stock':
            root = Path(self.library_set.split('=', 1)[1]).resolve()
            if not (root / LIBDIR / 'libmutter-14.so.0').exists():
                raise SystemExit(f'{root / LIBDIR}/libmutter-14.so.0 does not exist')
            # Only libmutter-14.so.0 comes from the build. GObject introspection
            # opens the clutter, cogl and mtk libraries by their full path in
            # /usr/lib/x86_64-linux-gnu/mutter-14, so taking those from the build
            # as well would load two copies and register every Clutter type twice.
            env['LD_LIBRARY_PATH'] = str(root / LIBDIR)
        self.note(f'starting the shell, LD_LIBRARY_PATH={env.get("LD_LIBRARY_PATH", "")}')
        self.shell = subprocess.Popen(
            [str(HERE / 'headless_shell.sh'), str(self.scratch), str(EXTENSION)],
            env=env, stdout=open(self.results / 'headless_shell.out', 'w'),
            stderr=subprocess.STDOUT, start_new_session=True)
        shell_log = self.scratch / 'shell.log'
        socket = self.scratch / 'runtime' / 'wayland-test'
        deadline = time.time() + 60
        while time.time() < deadline:
            if socket.exists() and shell_log.exists() and \
                    b'GNOME Shell started' in shell_log.read_bytes():
                break
            if self.shell.poll() is not None:
                raise RuntimeError('the headless shell exited during startup')
            time.sleep(0.2)
        else:
            raise RuntimeError('the headless shell did not start within 60 seconds')
        self.shell_pid = int((self.scratch / 'shell.pid').read_text())
        cmdline = Path(f'/proc/{self.shell_pid}/cmdline').read_bytes().split(b'\0')
        maps = sorted({line.split()[-1] for line in
                       Path(f'/proc/{self.shell_pid}/maps').read_text().splitlines()
                       if 'libmutter' in line})
        (self.results / 'maps.txt').write_text(
            f'shell pid {self.shell_pid}: {b" ".join(cmdline).decode()}\n' +
            ''.join(f'{path}\n' for path in maps))
        self.note(f'shell pid {self.shell_pid} maps ' + ' '.join(maps))
        deadline = time.time() + 30
        while time.time() < deadline:
            result = self.call('Describe', check=False)
            if result.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError('the test control extension did not answer within 30 seconds')
        # Let the startup animation and the overview hide finish.
        time.sleep(3)
        self.note('shell ready: ' + self.describe())

    def client_command(self, *command):
        return [str(HERE / 'client_env.sh'), str(self.scratch), *command]

    def call(self, method, *args, check=True):
        def literal(arg):
            return str(arg) if isinstance(arg, int) else "'" + arg + "'"
        result = subprocess.run(
            self.client_command('gdbus', 'call', '--session', '--dest', 'org.gnome.Shell',
                                '--object-path', '/org/gnome/Shell/SuspendTest',
                                '--method', f'org.gnome.Shell.SuspendTest.{method}',
                                *[literal(a) for a in args]),
            capture_output=True, text=True, timeout=20)
        if check:
            if result.returncode != 0 or 'error:' in result.stdout:
                raise RuntimeError(f'{method}{args}: {result.stdout}{result.stderr}')
            self.note(f'{method} {" ".join(map(str, args))}: {result.stdout.strip()}')
        return result

    def describe(self):
        return self.call('Describe', check=False).stdout.strip()

    def client(self, title, *options):
        log_path = self.results / f'{title}.log'
        process = subprocess.Popen(self.client_command(str(CLIENT), title, *options),
                                   stdin=subprocess.PIPE, stdout=open(log_path, 'w'),
                                   stderr=subprocess.STDOUT, text=True)
        self.clients[title] = process
        self.note(f'started client {title} {" ".join(options)} (pid {process.pid})')
        deadline = time.time() + 15
        while time.time() < deadline:
            if log_path.read_text().count(' configure ') >= 1:
                break
            if process.poll() is not None:
                raise RuntimeError(f'client {title} exited: {log_path.read_text()}')
            time.sleep(0.1)
        else:
            raise RuntimeError(f'client {title} was not configured within 15 seconds')
        time.sleep(1.0)

    def send(self, title, command):
        self.note(f'client {title}: {command}')
        self.clients[title].stdin.write(command + '\n')
        self.clients[title].stdin.flush()
        time.sleep(0.2)

    def stop_client(self, title):
        process = self.clients.pop(title)
        process.terminate()
        process.wait(10)
        self.note(f'stopped client {title}')

    def phase(self, name, seconds, expect, change=False):
        """Holds the current situation for <seconds>. <expect> maps a window
        title to (expected state with stock libraries, with patched ones).
        change=True marks a phase whose expectation differs between the two
        on purpose, beyond the defect being fixed."""
        start = time.time()
        self.note(f'phase "{name}" for {seconds} s')
        time.sleep(seconds)
        end = time.time()
        self.note(f'phase "{name}" ends; {self.describe()}')
        self.phases.append({'name': name, 'start': start, 'end': end,
                            'expect': {k: v for k, v in expect.items()}, 'change': change})

    def stop(self):
        for title in list(self.clients):
            self.stop_client(title)
        if self.shell_pid and Path(f'/proc/{self.shell_pid}').exists():
            cmdline = Path(f'/proc/{self.shell_pid}/cmdline').read_bytes()
            if cmdline.startswith(b'gnome-shell\0--headless'):
                os.kill(self.shell_pid, signal.SIGTERM)
            else:
                self.note(f'pid {self.shell_pid} is not the headless test shell: {cmdline!r}')
        if self.shell:
            try:
                self.shell.wait(30)
            except subprocess.TimeoutExpired:
                self.note('the headless shell did not exit within 30 seconds')
                raise
        self.note('shell stopped')
        for name in ('shell.log',):
            if (self.scratch / name).exists():
                shutil.copy(self.scratch / name, self.results / name)
        shutil.rmtree(self.scratch)
        self.log.close()


def client_states(path):
    """Returns [(unix time, suspended)] for the configure events in a client log."""
    events = []
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) > 4 and fields[4] == 'configure':
            suspended = 'suspended=1' in fields
            events.append((float(fields[0]), suspended))
    return events


def evaluate(run):
    rows = []
    for phase in run.phases:
        for title, (stock, patched) in phase['expect'].items():
            expected = stock if run.label == 'stock' else patched
            events = client_states(run.results / f'{title}.log')
            before = [s for t, s in events if t <= phase['start']]
            during = [(t, s) for t, s in events if phase['start'] < t <= phase['end']]
            state = before[-1] if before else None
            changes = []
            became_suspended_after_active = False
            for t, s in during:
                if s != state:
                    changes.append(f'{SUSPENDED if s else ACTIVE} at +{t - phase["start"]:.2f} s')
                    if s and state is False:
                        became_suspended_after_active = True
                    state = s
            observed = None if state is None else (SUSPENDED if state else ACTIVE)
            ok = observed == expected
            if expected == ACTIVE and became_suspended_after_active:
                ok = False
            rows.append({'case': run.case, 'phase': phase['name'], 'window': title,
                         'expected': expected, 'observed': observed, 'ok': ok,
                         'changes': changes, 'behaviour_change': phase['change'],
                         'stock_expectation': stock, 'patched_expectation': patched})
    return rows


def format_rows(label, rows):
    lines = []
    for r in rows:
        mark = 'PASS' if r['ok'] else 'FAIL'
        note = ' (intended difference between stock and patched)' if r['behaviour_change'] else ''
        changes = ', '.join(r['changes']) or 'no change'
        lines.append(f'{mark} {label} {r["case"]} / {r["phase"]} / {r["window"]}: '
                     f'expected {r["expected"]}, observed {r["observed"]}; '
                     f'during the phase: {changes}{note}')
    return lines


# The cases. Each function gets a started Run. Windows are 480x320 unless
# stated; the virtual monitor is 1280x800.

def case_covered_plain(r):
    r.client('target')
    r.call('Move', 'target', 100, 100)
    r.phase('shown', 8, {'target': (ACTIVE, ACTIVE)})
    r.client('cover', '--fullscreen')
    r.phase('covered by a fullscreen window', 10, {'target': (SUSPENDED, SUSPENDED)})
    r.stop_client('cover')
    r.phase('uncovered', 8, {'target': (ACTIVE, ACTIVE)})


def case_covered_hidden_subsurface(r):
    r.client('target', '--hidden-subsurface')
    r.call('Move', 'target', 100, 100)
    r.phase('shown', 12, {'target': (ACTIVE, ACTIVE)})
    r.client('cover', '--fullscreen')
    r.phase('covered by a fullscreen window', 12, {'target': (ACTIVE, SUSPENDED)})
    r.stop_client('cover')
    r.phase('uncovered', 8, {'target': (ACTIVE, ACTIVE)})


def case_partly_covered(r):
    r.client('plain')
    r.call('Move', 'plain', 100, 100)
    r.client('hidden-sub', '--hidden-subsurface')
    r.call('Move', 'hidden-sub', 700, 100)
    both_active = {'plain': (ACTIVE, ACTIVE), 'hidden-sub': (ACTIVE, ACTIVE)}
    r.phase('shown', 6, both_active)
    r.client('cover-a', '--size', '240x320')
    r.call('Move', 'cover-a', 100, 100)
    r.client('cover-b', '--size', '240x320')
    r.call('Move', 'cover-b', 700, 100)
    r.phase('left half of each window covered', 12, both_active)
    r.client('cover', '--fullscreen')
    r.phase('covered by a fullscreen window', 10,
            {'plain': (SUSPENDED, SUSPENDED), 'hidden-sub': (ACTIVE, SUSPENDED)})
    r.stop_client('cover')
    r.phase('left half covered again', 8, both_active)


def case_mapped_subsurface(r):
    # "outside" has a mapped subsurface to the right of its main surface,
    # "inside" has one within its main surface.
    r.client('outside', '--mapped-subsurface', '500,0,200x200')
    r.call('Move', 'outside', 100, 100)
    r.client('inside', '--mapped-subsurface', '20,20,200x200')
    r.call('Move', 'inside', 100, 450)
    both_active = {'outside': (ACTIVE, ACTIVE), 'inside': (ACTIVE, ACTIVE)}
    r.phase('shown', 6, both_active)
    r.client('cover-main-1', '--size', '480x320')
    r.call('Move', 'cover-main-1', 100, 100)
    r.client('cover-main-2', '--size', '480x320')
    r.call('Move', 'cover-main-2', 100, 450)
    r.phase('main surfaces covered, outside subsurface visible', 12,
            {'outside': (ACTIVE, ACTIVE), 'inside': (SUSPENDED, SUSPENDED)})
    r.client('cover', '--fullscreen')
    r.phase('covered by a fullscreen window', 10,
            {'outside': (SUSPENDED, SUSPENDED), 'inside': (SUSPENDED, SUSPENDED)})
    for title in ('cover', 'cover-main-1', 'cover-main-2'):
        r.stop_client(title)
    r.phase('uncovered', 8, both_active)


def case_overview(r):
    r.client('plain')
    r.call('Move', 'plain', 100, 100)
    r.client('hidden-sub', '--hidden-subsurface')
    r.call('Move', 'hidden-sub', 700, 100)
    r.phase('shown', 6, {'plain': (ACTIVE, ACTIVE), 'hidden-sub': (ACTIVE, ACTIVE)})
    r.client('cover', '--fullscreen')
    covered = {'plain': (SUSPENDED, SUSPENDED), 'hidden-sub': (ACTIVE, SUSPENDED)}
    r.phase('covered by a fullscreen window', 10, covered)
    r.call('ShowOverview')
    r.phase('overview shown, windows visible as clones', 10,
            {'plain': (ACTIVE, ACTIVE), 'hidden-sub': (ACTIVE, ACTIVE)})
    r.call('HideOverview')
    r.phase('overview hidden, covered again', 10, covered)


def case_minimized(r):
    r.client('plain')
    r.call('Move', 'plain', 100, 100)
    r.client('hidden-sub', '--hidden-subsurface')
    r.call('Move', 'hidden-sub', 700, 100)
    both_active = {'plain': (ACTIVE, ACTIVE), 'hidden-sub': (ACTIVE, ACTIVE)}
    r.phase('shown', 6, both_active)
    r.call('Minimize', 'plain')
    r.call('Minimize', 'hidden-sub')
    r.phase('minimized', 10, {'plain': (SUSPENDED, SUSPENDED),
                              'hidden-sub': (SUSPENDED, SUSPENDED)})
    r.call('Unminimize', 'plain')
    r.call('Unminimize', 'hidden-sub')
    r.phase('unminimized', 8, both_active)


def case_other_workspace(r):
    r.client('plain')
    r.call('Move', 'plain', 100, 100)
    r.client('hidden-sub', '--hidden-subsurface')
    r.call('Move', 'hidden-sub', 700, 100)
    r.phase('shown', 6, {'plain': (ACTIVE, ACTIVE), 'hidden-sub': (ACTIVE, ACTIVE)})
    r.call('MoveToWorkspace', 'plain', 1)
    r.call('MoveToWorkspace', 'hidden-sub', 1)
    elsewhere = {'plain': (SUSPENDED, SUSPENDED), 'hidden-sub': (SUSPENDED, SUSPENDED)}
    r.phase('moved to another workspace', 10, elsewhere)
    r.call('ShowOverview')
    r.phase('overview shown, windows of the other workspace visible as clones', 10,
            {'plain': (SUSPENDED, ACTIVE), 'hidden-sub': (SUSPENDED, ACTIVE)}, change=True)
    r.call('HideOverview')
    r.phase('overview hidden', 10, elsewhere)


def case_lock_screen(r):
    r.client('plain')
    r.call('Move', 'plain', 100, 100)
    r.client('hidden-sub', '--hidden-subsurface')
    r.call('Move', 'hidden-sub', 700, 100)
    both_active = {'plain': (ACTIVE, ACTIVE), 'hidden-sub': (ACTIVE, ACTIVE)}
    r.phase('shown', 6, both_active)
    r.call('Lock')
    r.phase('screen locked', 12, {'plain': (ACTIVE, SUSPENDED),
                                  'hidden-sub': (ACTIVE, SUSPENDED)}, change=True)
    r.call('Unlock')
    r.phase('unlocked', 8, both_active)


def case_subsurface_changes(r):
    t = 'target'
    active = {t: (ACTIVE, ACTIVE)}
    r.client(t)
    r.call('Move', t, 100, 100)
    r.phase('shown', 6, active)
    r.send(t, 'add-hidden')
    r.phase('hidden subsurface added, nothing else redrawn', 12, active)
    r.send(t, 'map-sub 20,20,200x200')
    r.phase('subsurface mapped', 6, active)
    r.client('cover-small', '--size', '240x240')
    r.call('Move', 'cover-small', 100, 100)
    r.phase('subsurface covered, rest of the window visible', 8, active)
    r.send(t, 'unmap-sub')
    r.phase('covered subsurface unmapped', 12, active)
    r.stop_client('cover-small')
    r.client('cover', '--fullscreen')
    r.phase('covered by a fullscreen window with a hidden subsurface', 10,
            {t: (ACTIVE, SUSPENDED)})
    r.send(t, 'map-sub 20,20,200x200')
    r.phase('covered, subsurface mapped', 10, {t: (SUSPENDED, SUSPENDED)})
    r.send(t, 'unmap-sub')
    r.phase('covered, subsurface unmapped again', 10, {t: (ACTIVE, SUSPENDED)})
    r.stop_client('cover')
    r.phase('uncovered', 8, active)
    r.send(t, 'destroy-sub')
    r.phase('subsurface destroyed', 6, active)


CASES = {
    'covered-plain': case_covered_plain,
    'covered-hidden-subsurface': case_covered_hidden_subsurface,
    'partly-covered': case_partly_covered,
    'mapped-subsurface': case_mapped_subsurface,
    'overview': case_overview,
    'minimized': case_minimized,
    'other-workspace': case_other_workspace,
    'lock-screen': case_lock_screen,
    'subsurface-changes': case_subsurface_changes,
}


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    library_set = sys.argv[1]
    results = Path(sys.argv[2]).resolve()
    names = sys.argv[3:] or list(CASES)
    results.mkdir(parents=True, exist_ok=True)
    all_lines = []
    for name in names:
        run = Run(name, library_set, results)
        try:
            run.start_shell()
            CASES[name](run)
        except Exception as e:
            run.note(f'case aborted: {e!r}')
            all_lines.append(f'ERROR {run.label} {name}: {e!r}')
        finally:
            run.stop()
        rows = evaluate(run)
        lines = format_rows(run.label, rows)
        (run.results / 'summary.json').write_text(json.dumps(rows, indent=1) + '\n')
        (run.results / 'summary.txt').write_text('\n'.join(lines) + '\n')
        all_lines += lines
        print('\n'.join(lines), flush=True)
    (results / 'summary.txt').write_text('\n'.join(all_lines) + '\n')
    failures = [line for line in all_lines if not line.startswith('PASS')]
    print(f'{len(all_lines) - len(failures)} passed, {len(failures)} failed or aborted')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
