"""Una ventana interactiva por usuario; las capturas y pruebas son aisladas."""
import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def legacy_windows():
    if os.name != 'nt':
        return []
    user = ctypes.WinDLL('user32',use_last_error=True)
    result = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user.GetWindowTextW.argtypes = [wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    @callback_type
    def visit(handle, _):
        if user.IsWindowVisible(handle):
            text = ctypes.create_unicode_buffer(user.GetWindowTextLengthW(handle)+1)
            user.GetWindowTextW(handle,text,len(text))
            pid = wintypes.DWORD()
            user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
            if text.value == 'CHC Workbench' and pid.value != os.getpid():
                result.append((handle,pid.value))
        return True
    user.EnumWindows(visit,0)
    return result


def foreground(handle):
    if os.name == 'nt':
        user = ctypes.WinDLL('user32',use_last_error=True)
        user.ShowWindow.argtypes = [wintypes.HWND,ctypes.c_int]
        user.SetForegroundWindow.argtypes = [wintypes.HWND]
        user.ShowWindow(handle,9)
        user.SetForegroundWindow(handle)


class SingleInstance:
    def __init__(self, name=None):
        identity = hashlib.sha256((os.environ.get('USERNAME','user')+'@'+os.environ.get('USERDOMAIN','local')).encode()).hexdigest()[:16]
        self.name = name or 'CHC.Workbench.'+identity
        self.lock = QLockFile(str(Path(QStandardPaths.writableLocation(QStandardPaths.TempLocation))/(self.name+'.lock')))
        self.server = QLocalServer()
        self.window = None
        self.active = False

    def acquire(self, check_legacy=True):
        if not self.lock.tryLock(0):
            socket = QLocalSocket()
            socket.connectToServer(self.name)
            if socket.waitForConnected(1500):
                socket.write(b'activate\n')
                socket.waitForBytesWritten(1000)
                socket.disconnectFromServer()
            else:
                windows = legacy_windows()
                if windows:
                    foreground(windows[0][0])
            return False
        # Ventanas anteriores al protocolo también se reutilizan al actualizar.
        windows = legacy_windows() if check_legacy else []
        if windows:
            foreground(windows[0][0])
            self.lock.unlock()
            return False
        QLocalServer.removeServer(self.name)
        if not self.server.listen(self.name):
            self.lock.unlock()
            raise RuntimeError('No se pudo iniciar el control de instancia única.')
        self.server.newConnection.connect(self.activate)
        self.active = True
        return True

    def activate(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.disconnectFromServer()
            socket.deleteLater()
        if self.window:
            self.window.showNormal()
            self.window.raise_()
            self.window.requestActivate()
            foreground(int(self.window.winId()))

    def close(self):
        if self.active:
            self.server.close()
            self.lock.unlock()
            self.active = False
