import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files
from zhongnan_tray.release import VERSION

root = Path(SPECPATH).parent
icon = root / 'build' / ('ZhongnanGym.icns' if sys.platform == 'darwin' else 'ZhongnanGym.ico')
a = Analysis(
    [str(root / 'launcher.py')],
    pathex=[str(root / 'src')],
    datas=collect_data_files('tzdata'),
    hiddenimports=[],
    excludes=['tkinter', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
if sys.platform == 'darwin':
    exe = EXE(
        pyz, a.scripts, [], exclude_binaries=True, name='ZhongnanGym',
        console=False, upx=False, icon=str(icon),
    )
    coll = COLLECT(exe, a.binaries, a.datas, name='ZhongnanGym', upx=False)
    app = BUNDLE(
        coll,
        name='终南健身.app',
        icon=str(icon),
        bundle_identifier='local.zhongnan.gym',
        version=VERSION,
        info_plist={
            'LSUIElement': True,
            'NSHighResolutionCapable': True,
            'CFBundleDisplayName': '终南健身',
            'NSPrincipalClass': 'NSApplication',
        },
    )
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas,
        name='ZhongnanGym-Windows-x64', console=False, upx=False, icon=str(icon),
    )
