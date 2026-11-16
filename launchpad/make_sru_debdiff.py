#!/usr/bin/python3
"""Makes the debdiff to attach to the Launchpad bug.

usage: launchpad/make_sru_debdiff.py <bug number> [tested commit]

It exports mutter/ from the tested commit (default 4caa013, the commit the
packages in out/ were built and tested from), and changes only what an
upload to noble needs:

- the version of the top changelog entry becomes 46.2-1ubuntu0.24.04.19,
  its first item gets "(LP: #<bug number>)", and its date becomes now;
- each patch the tested commit added gets a "Bug-Ubuntu:" header line.

It then checks that nothing else differs from the tested source, builds the
source package on the host and writes out/mutter_46.2-1ubuntu0.24.04.19.debdiff
against Ubuntu's 46.2-1ubuntu0.24.04.18 in out/ubuntu-source/.
"""
import email.utils
import filecmp
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
UBUNTU = REPO / 'out' / 'ubuntu-source'
VERSION = '46.2-1ubuntu0.24.04.19'
TESTED_VERSION = '46.2-1ubuntu0.24.04.18+local2'
PATCHES = [
    'window-actor-Track-state-affecting-suspend-inhibation-ex.patch',
    'window-actor-Handle-visibility-condition-for-suspending-w.patch',
    'tests-wayland-toplevel-suspend-Add-test-for-suspending-on.patch',
    'tests-toplevel-suspend-Test-windows-with-a-hidden-subsurface.patch',
    'window-actor-Disconnect-notify-mapped-when-disconnecting.patch',
    'tests-toplevel-suspend-Test-reusing-a-wl_surface-for-a-toplevel.patch',
]


def export(commit, target):
    archive = subprocess.run(['git', '-C', str(REPO), 'archive', commit, 'mutter'],
                             check=True, capture_output=True).stdout
    subprocess.run(['tar', '-x', '-C', str(target)], input=archive, check=True)
    return target / 'mutter'


def edit_changelog(path, bug):
    lines = path.read_text().split('\n')
    head = f'mutter ({TESTED_VERSION}) noble; urgency=medium'
    if lines[0] != head:
        raise SystemExit(f'unexpected first changelog line: {lines[0]}')
    lines[0] = f'mutter ({VERSION}) noble; urgency=medium'
    # The first item runs from its "  * " line to the line that ends with ":"
    # before the list of patches.
    start = 2
    end = start
    while not lines[end].endswith(':'):
        end += 1
    text = ' '.join(line.strip() for line in lines[start:end + 1])
    old = '* Suspend a covered window that has a hidden subsurface.'
    if not text.startswith(old):
        raise SystemExit(f'unexpected first changelog item: {text[:80]}')
    text = text[2:].replace('hidden subsurface.', f'hidden subsurface (LP: #{bug}).', 1)
    item = textwrap.wrap(text, width=76, initial_indent='  * ', subsequent_indent='    ',
                         break_long_words=False, break_on_hyphens=False)
    lines[start:end + 1] = item
    for i, line in enumerate(lines):
        if line.startswith(' -- '):
            name = line[4:].split('  ')[0]
            lines[i] = f' -- {name}  {email.utils.format_datetime(email.utils.localtime())}'
            break
    path.write_text('\n'.join(lines))


def add_bug_header(path, bug):
    lines = path.read_text().split('\n')
    end = lines.index('---')
    lines.insert(end, f'Bug-Ubuntu: https://bugs.launchpad.net/bugs/{bug}')
    path.write_text('\n'.join(lines))


def check_only_expected_changes(tested, changed, bug):
    differing = []

    def walk(comparison, prefix=''):
        differing.extend(prefix + name for name in comparison.diff_files)
        differing.extend(prefix + name for name in comparison.left_only + comparison.right_only)
        for name, sub in comparison.subdirs.items():
            walk(sub, f'{prefix}{name}/')
    walk(filecmp.dircmp(tested, changed))
    expected = {'debian/changelog'} | {f'debian/patches/{p}' for p in PATCHES}
    if set(differing) != expected:
        raise SystemExit(f'unexpected differences: {sorted(set(differing) ^ expected)}')
    header = f'Bug-Ubuntu: https://bugs.launchpad.net/bugs/{bug}\n'
    for p in PATCHES:
        old = (tested / 'debian' / 'patches' / p).read_text()
        new = (changed / 'debian' / 'patches' / p).read_text()
        if new.replace(header, '', 1) != old:
            raise SystemExit(f'{p} differs from the tested patch by more than its Bug-Ubuntu line')


def main():
    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        raise SystemExit(__doc__)
    bug = sys.argv[1]
    commit = sys.argv[2] if len(sys.argv) > 2 else '4caa013'
    with tempfile.TemporaryDirectory(prefix='mutter-sru-') as work:
        work = Path(work)
        (work / 'tested').mkdir()
        (work / 'sru').mkdir()
        tested = export(commit, work / 'tested')
        source = export(commit, work / 'sru')
        edit_changelog(source / 'debian' / 'changelog', bug)
        for p in PATCHES:
            add_bug_header(source / 'debian' / 'patches' / p, bug)
        check_only_expected_changes(tested, source, bug)
        shutil.copy(UBUNTU / 'mutter_46.2.orig.tar.xz', work / 'sru')
        subprocess.run(['dpkg-source', '-b', 'mutter'], cwd=work / 'sru', check=True,
                       stdout=subprocess.DEVNULL)
        out = REPO / 'out' / f'mutter_{VERSION}.debdiff'
        result = subprocess.run(['debdiff', str(UBUNTU / 'mutter_46.2-1ubuntu0.24.04.18.dsc'),
                                 str(work / 'sru' / f'mutter_{VERSION}.dsc')],
                                capture_output=True, text=True)
        # debdiff exits with 1 when it found differences.
        if result.returncode != 1 or not result.stdout:
            raise SystemExit(f'debdiff failed ({result.returncode}): {result.stderr}')
        out.write_text(result.stdout)
    print(out)
    subprocess.run(['diffstat', str(out)])
    print('\n'.join(result.stdout.split('\n')[:20]))


if __name__ == '__main__':
    main()
