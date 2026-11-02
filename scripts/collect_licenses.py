"""Writes the third-party notices of everything bundled into dist/jps-runner.

Run with the build environment's Python. For every installed distribution that ends up in the
binary it copies *all* its license files (wheels often carry several: shapely ships the GEOS
license next to its own, h5py the HDF5 one, numpy and pillow those of their native libraries) to
licenses/<name>-<version>/, and writes THIRD_PARTY_LICENSES.txt: a summary table, then every text.
"""

import pathlib
import re
import shutil
import sys
from importlib.metadata import distributions

# Installed in the build environment but not in the binary: the build tools, and what
# packaging/jps-runner.spec excludes (jupedsim pulls Qt and VTK for its visualizer).
# Keep in step with the spec's `excludes`.
NOT_BUNDLED = {
    "pip", "setuptools", "wheel", "pyinstaller", "pyinstaller-hooks-contrib", "altgraph",
    "macholib", "pefile", "pywin32-ctypes",
    "pyside6", "pyside6-addons", "pyside6-essentials", "pyside6-pdf", "pyside6-webengine",
    "shiboken6", "vtk",
}

LICENSE_FILE = re.compile(r"(licen[cs]e|copying|notice|authors)", re.IGNORECASE)


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def main(out_dir: str) -> None:
    out = pathlib.Path(out_dir)
    licenses_dir = out / "licenses"
    if licenses_dir.exists():
        shutil.rmtree(licenses_dir)
    licenses_dir.mkdir(parents=True)

    entries = []
    for dist in distributions():
        name = dist.metadata["Name"]
        if not name or normalise(name) in NOT_BUNDLED:
            continue
        version = dist.version
        licence = dist.metadata.get("License-Expression") or "; ".join(
            c.split("::")[-1].strip() for c in dist.metadata.get_all("Classifier") or [] if c.startswith("License ::"))
        if not licence:
            raw = (dist.metadata.get("License") or "").strip()
            licence = raw.splitlines()[0] if raw else "see text"
        # Everything under the dist-info's licenses/ folder (PEP 639; h5py's HDF5 text is
        # licenses/licenses/hdf5.txt — no "license" in the file name), plus LICENSE/COPYING/...
        # files directly in the dist-info of older wheels.
        files = [f for f in (dist.files or [])
                 if ".dist-info" in str(f)
                 and ("licenses" in [p.lower() for p in f.parts] or LICENSE_FILE.search(f.name))]
        target = licenses_dir / f"{name}-{version}"
        texts = []
        for f in files:
            src = pathlib.Path(dist.locate_file(f))
            if not src.is_file():
                continue
            rel = pathlib.Path(*[p for p in f.parts if not p.endswith(".dist-info")])
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            texts.append((str(rel), src.read_text(encoding="utf-8", errors="replace")))
        entries.append((name, version, licence, texts))

    # The interpreter itself is bundled too (libpython); its license sits in the standard library.
    import sysconfig
    stdlib_licence = pathlib.Path(sysconfig.get_paths()["stdlib"]) / "LICENSE.txt"
    if stdlib_licence.is_file():
        version = sys.version.split()[0]
        dest = licenses_dir / f"Python-{version}" / "LICENSE.txt"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(stdlib_licence, dest)
        entries.append(("Python", version, "PSF-2.0",
                        [("LICENSE.txt", stdlib_licence.read_text(encoding="utf-8", errors="replace"))]))
    else:
        print("warning: the interpreter's LICENSE.txt was not found; Python is missing from the notices")

    entries.sort(key=lambda e: e[0].lower())
    with open(out / "THIRD_PARTY_LICENSES.txt", "w", encoding="utf-8") as fh:
        fh.write("Third-party software bundled in jps-runner\n")
        fh.write("==========================================\n\n")
        fh.write("The same texts are in the licenses/ folder, one subfolder per package.\n\n")
        for name, version, licence, texts in entries:
            fh.write(f"{name} {version}  —  {licence}\n")
        for name, version, licence, texts in entries:
            fh.write("\n\n" + "=" * 78 + f"\n{name} {version}\n" + "=" * 78 + "\n")
            if not texts:
                fh.write(f"(no license file in the package; declared license: {licence})\n")
            for rel, text in texts:
                fh.write(f"\n--- {rel} ---\n\n{text}\n")
    missing = [n for n, _, _, t in entries if not t]
    print(f"{len(entries)} packages, {sum(len(t) for *_, t in entries)} license files"
          + (f"; without a license file: {', '.join(missing)}" if missing else ""))


if __name__ == "__main__":
    main(sys.argv[1])
