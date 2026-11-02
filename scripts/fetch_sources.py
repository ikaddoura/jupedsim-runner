"""Downloads the source archives of the LGPL components bundled in the runner, for the release.

The LGPL asks that the source of exactly the shipped versions be available from where the binary
is offered; attaching it to every GitHub release keeps it there even if upstream moves things.

    python scripts/fetch_sources.py <out-dir>

- JuPedSim: the sdist of the version pinned in requirements.txt, from PyPI, checked against the
  SHA-256 PyPI publishes.
- GEOS: the release tarball of the version shapely bundles (asked from the installed shapely),
  from download.osgeo.org. GEOS publishes no checksums there; the computed one is recorded.

Writes SOURCES.sha256 (shasum -c format) next to the archives. Uses only the standard library (and shapely, to learn
the GEOS version).
"""

import hashlib
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent


def pinned(requirement_file: str, name: str) -> str:
    for line in (ROOT / requirement_file).read_text().splitlines():
        m = re.match(rf"^{re.escape(name)}==([^\s#]+)", line.strip(), re.IGNORECASE)
        if m:
            return m.group(1)
    raise SystemExit(f"{name} is not pinned in {requirement_file}")


def download(url: str, target: pathlib.Path) -> str:
    sha = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=120) as response, open(target, "wb") as out:
        while chunk := response.read(1 << 20):
            sha.update(chunk)
            out.write(chunk)
    return sha.hexdigest()


def main(out_dir: str) -> None:
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    lines = []

    version = pinned("requirements.txt", "jupedsim")
    with urllib.request.urlopen(f"https://pypi.org/pypi/jupedsim/{version}/json", timeout=60) as r:
        sdists = [u for u in json.load(r)["urls"] if u["packagetype"] == "sdist"]
    if not sdists:
        raise SystemExit(f"PyPI has no source archive for jupedsim {version}")
    sdist = sdists[0]
    digest = download(sdist["url"], out / sdist["filename"])
    if digest != sdist["digests"]["sha256"]:
        raise SystemExit(f"{sdist['filename']}: SHA-256 {digest} does not match PyPI's {sdist['digests']['sha256']}")
    lines.append(f"{digest}  {sdist['filename']}")
    print(f"{sdist['filename']}: SHA-256 matches PyPI")

    import shapely  # the version pinned in constraints.txt, installed by the caller

    geos = shapely.geos_version_string
    name = f"geos-{geos}.tar.bz2"
    digest = download(f"https://download.osgeo.org/geos/{name}", out / name)
    lines.append(f"{digest}  {name}")
    print(f"{name}: downloaded (download.osgeo.org publishes no checksum; SHA-256 recorded)")

    # Plain "<sha256>  <file>" lines, so `shasum -a 256 -c SOURCES.sha256` checks them.
    (out / "SOURCES.sha256").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
