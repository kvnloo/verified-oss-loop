# Pages dest paths (paste into your own pages.yml)

This is **not** a site builder. VOL does not own Vite, Jekyll, or `build-pages.py`.
Paste the dest step into the workflow you already run. Deploy still follows
your existing rule (usually from `main`). Build whatever origin refs you
already build. The dest folder comes from `pages-url-map.py`.

Git channels stay `preview`, `nightly`, `dev`, `main`. Those names are not
URL paths. Feature scratch is `/wip/<slug>/` (`/` in the ref → `--`).

```yaml
# dest from the map, not a catch-all folder named after a git channel
- name: Pages dest from git ref
  id: dest
  run: |
    BRANCH="${GITHUB_REF_NAME}"
    dest=$(python3 scripts/pages-url-map.py path --branch "$BRANCH" --base /${{ github.event.repository.name }}/)
    echo "path=$dest" >> "$GITHUB_OUTPUT"
    if [ -z "$dest" ]; then
      echo "unpublished channel; skip upload"
    fi
```

Greenfield copy: `scripts/pages-url-map.py`. Mature copy:
`.verified-oss-loop/pages-url-map.py`. Override folders in
`.verified-oss-loop/pages-url-map.yml`.

`workflow_dispatch` jobs (including kit `promote-preview.yml`) only appear
in the Actions tab once the file exists on the **default branch**. Automation
yml is inert until a human lands it on `origin/main`.

Check (no network):

```bash
python3 scripts/pages-url-map.py check --root .
```
