"""Version-neutral Altium discovery and persisted executable selection."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import winreg

from .catalog import save_json


def file_version(path: Path) -> str:
    api=ctypes.WinDLL('version',use_last_error=True)
    api.GetFileVersionInfoSizeW.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(wintypes.DWORD)]
    api.GetFileVersionInfoW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p]
    api.VerQueryValueW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(wintypes.UINT)]
    handle=wintypes.DWORD()
    size=api.GetFileVersionInfoSizeW(str(path),ctypes.byref(handle))
    if not size:
        return ''
    buffer=ctypes.create_string_buffer(size)
    if not api.GetFileVersionInfoW(str(path),0,size,buffer):
        return ''
    pointer=ctypes.c_void_p()
    length=wintypes.UINT()
    if not api.VerQueryValueW(buffer,'\\',ctypes.byref(pointer),ctypes.byref(length)) or length.value<52:
        return ''
    values=ctypes.cast(pointer,ctypes.POINTER(wintypes.DWORD))
    ms,ls=values[2],values[3]
    return f'{ms>>16}.{ms&65535}.{ls>>16}.{ls&65535}'


def discover_altium() -> list[Path]:
    candidates=[Path(r'E:\AD24\X2.EXE')]
    uninstall=r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive,uninstall,0,winreg.KEY_READ|view) as root:
                    for index in range(winreg.QueryInfoKey(root)[0]):
                        try:
                            with winreg.OpenKey(root,winreg.EnumKey(root,index)) as key:
                                name=winreg.QueryValueEx(key,'DisplayName')[0]
                                if 'altium' not in str(name).lower():
                                    continue
                                for field in ('InstallLocation','DisplayIcon'):
                                    try:
                                        value=str(winreg.QueryValueEx(key,field)[0]).strip('" ')
                                        if field=='InstallLocation':
                                            candidates.append(Path(value)/'X2.EXE')
                                        elif '.exe' in value.lower():
                                            value=value[:value.lower().index('.exe')+4].strip('"')
                                            if Path(value).name.lower()=='x2.exe':
                                                candidates.append(Path(value))
                                    except OSError:
                                        pass
                        except OSError:
                            pass
            except OSError:
                pass
    for env in ('ProgramFiles','ProgramFiles(x86)'):
        base=Path(os.environ.get(env,r'C:\Program Files'))/'Altium'
        if base.is_dir():
            candidates.extend(base.glob('*/X2.EXE'))
    unique={str(p.resolve()).lower():p.resolve() for p in candidates if p.is_file()}
    def key(path):
        return tuple(int(n) for n in (file_version(path) or '0').split('.'))
    return sorted(unique.values(),key=key,reverse=True)


def load_altium(config: Path, candidates=None) -> Path:
    try:
        path=Path(json.loads(config.read_text(encoding='utf-8'))['altium_exe'])
        if path.is_file():
            return path
    except (OSError,ValueError,KeyError,TypeError):
        pass
    candidates=discover_altium() if candidates is None else candidates
    return next((p for p in candidates if p.is_file()),Path(r'E:\AD24\X2.EXE'))


def save_altium(config: Path, executable: Path):
    if not executable.is_file() or executable.name.lower()!='x2.exe':
        raise ValueError('请选择 Altium 安装目录中的 X2.EXE')
    save_json(config,{'altium_exe':str(executable.resolve())})
