# PyInstaller spec для упаковки backend.exe
# ВАЖНО: запускать из чистого venv с только backend зависимостями:
#   python -m venv .venv-build && .venv-build\Scripts\pip install -e .[build]
#   .venv-build\Scripts\python -m PyInstaller --clean --noconfirm build.spec
# При первом запуске backend.exe распаковывает себя в %TEMP%\_MEI<random> — задержка 1-2 сек.
# Electron main должен ждать /health через waitForUrl с timeout 30s.
import os

icon_path = os.path.join('..', 'desktop', 'icon.ico')
icon = icon_path if os.path.exists(icon_path) else None

a = Analysis(
    ['app/main_cli.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('app', 'app'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'aiosqlite',
        'sse_starlette',
        'pydantic',
        'pydantic_settings',
    ],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='backend',
    console=False,
    onefile=True,
    icon=icon,
)
