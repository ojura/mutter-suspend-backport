# Filing the Launchpad bug

The title and the text are in `report/launchpad-bug.txt`. The browser steps
use the cdp-daemon (`http://127.0.0.1:7799`) through
`~/src/chrome-wayland-catch/bin/cdp_page.py` (open, nav, eval,
close) and `cdp_input.py` (real click, insert text). Fill a field by
clicking into it and inserting the text; press buttons with a real click.

```sh
B=~/src/chrome-wayland-catch/bin
python3 -I $B/cdp_page.py open '<url>' load        # prints targetId and sessionId
python3 -I $B/cdp_page.py eval <sessionId> launchpad/js/form-fields.js
python3 -I $B/cdp_input.py click <sessionId> <x> <y>
python3 -I $B/cdp_input.py text <sessionId> <file with the text>
python3 -I $B/cdp_page.py eval <sessionId> launchpad/js/page-text.js
python3 -I $B/cdp_page.py close <targetId> <sessionId>
```

## Step 1: file the bug with the client attached

The bug is filed as LP: #2174026, <https://bugs.launchpad.net/bugs/2174026>.

Form: <https://bugs.launchpad.net/ubuntu/+source/mutter/+filebug?no-redirect>.
Without `no-redirect`, Launchpad sends people filing Ubuntu bugs to the
`ubuntu-bug` guidance instead (`redirect_ubuntu_filebug` in
`lib/lp/bugs/browser/bugtarget.py` of Launchpad).

Attachment: `tests/client/suspend_client.c`, description
`suspend_client.c: the minimal client from the test plan`, with the patch
box left unchecked.

The login page, <https://launchpad.net/+login>, leads to
`https://login.launchpad.net/<token>/+decide` with the fields `id_email`
(name `email`), the radio buttons `id_new_user` and `id_returning_user`,
`id_password` (name `password`) and the button "Log in".

Not seen in the browser; read from Launchpad's source
(`lib/lp/bugs/browser/bugtarget.py`, `templates/bugtarget-filebug-search.pt`):

- The first page asks for `field.title` and continues with
  `field.actions.search` ("Continue"). Launchpad then lists bugs with similar
  titles with `field.actions.this_is_my_bug` for one of them; the source
  calls `field.actions.continue` the way on when none is a duplicate. The
  button texts on that page were not checked.
- The full form has `field.title`, `field.comment` (the description),
  `field.tags`, `field.security_related`, `field.filecontent` (the
  attachment), `field.patch`, `field.attachment_description`, and the
  button `field.actions.submit_bug` ("Submit Bug Report").
- A file input cannot take inserted text. CDP's `DOM.setFileInputFiles`
  sets it, for example through the daemon's `/cdp` endpoint with the
  input's `objectId` from `Runtime.evaluate` (`returnByValue: false`). This
  has not been tried on Launchpad.

After submitting, read the bug page back with `js/page-text.js`, reload it
and read it again, and check with
`python3 -I launchpad/lp_search.py mutter 'hidden subsurface'` that the bug
exists once.

## Step 2: make and attach the debdiff

```sh
python3 -I launchpad/make_sru_debdiff.py <bug number>
```

It writes `out/mutter_46.2-1ubuntu0.24.04.19.debdiff`: the source of commit
4caa013, from which the packages in `out/` were built and tested, with the
version 46.2-1ubuntu0.24.04.19, `(LP: #<bug number>)` in the changelog,
the current date in the changelog trailer, and a `Bug-Ubuntu:` line in each
of the six patches. It stops if anything else differs from the tested
source. It needs Ubuntu's source package of 46.2-1ubuntu0.24.04.18 in
`out/ubuntu-source/`, and dpkg-dev, devscripts and diffstat.

Attach it on <https://bugs.launchpad.net/ubuntu/+source/mutter/+bug/BUGNUMBER/+addcomment>
with the patch box checked. Field names, from Launchpad's source
(`lib/lp/bugs/interfaces/bugmessage.py`, not seen in the browser):
`field.subject`, `field.comment`, `field.filecontent`,
`field.attachment_url`, `field.patch`, `field.attachment_description`,
`field.email_me`, and the button `field.actions.save` ("Post Comment").

## Other scripts here

- `lp_search.py`, `lp_versions.py` and `lp_buildlog.py` query Launchpad's
  API without a login: bug search in every status, published mutter
  versions per series, and Ubuntu's own build log of 46.2-1ubuntu0.24.04.18.
- `js/` holds expressions for `cdp_page.py eval`: `page-text.js` (address,
  title and start of the page text), `form-fields.js` (inputs and buttons
  with their positions and whether Chrome autofilled them, never their
  values), `login-state.js`, `radio-state.js`, and the `gitlab-*.js` files
  that read merge requests, issue pages and issue searches on GNOME's GitLab.
