# PyInstaller spec. One-folder on purpose: the LGPL libraries (libjupedsim, GEOS) stay separate,
# replaceable files next to the executable. Do not switch to --onefile.
from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata("jupedsim") + copy_metadata("jupedsim-scenarios")

a = Analysis(
    ["../runner_main.py"],
    datas=datas,
    # The CLI needs none of these; jupedsim pulls PySide6 and VTK for its visualizer.
    excludes=["PySide6", "shiboken6", "vtk", "vtkmodules", "tkinter", "IPython"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="jps-runner", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="jps-runner")
