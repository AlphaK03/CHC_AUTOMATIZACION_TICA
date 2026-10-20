"""CHC Workbench: bots independientes, Manifiestos y una sola ventana interactiva."""
import argparse
import os
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from demo import DemoBackend
from details_bridge import DetailsBridge
from batch_bridge import BatchBridge
from preferences import Preferences
from single_instance import SingleInstance
from monthly_bridge import MonthlyProgress
from sharepoint_bridge import SharePointBridge

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test', action='store_true', help='Comprobar navegación y simulación; salir sin abrir bots.')
    parser.add_argument('--capture', type=Path, help='Guardar una captura del panel y salir.')
    parser.add_argument('--page', default='overview', help='Vista para captura/demo: overview o ID de módulo. El inicio normal abre Vista general.')
    parser.add_argument('--collapsed', action='store_true', help='Iniciar con la barra lateral contraída.')
    parser.add_argument('--light', action='store_true', help='Iniciar en tema claro.')
    parser.add_argument('--sample', action='store_true', help='Preparar una simulación pausada en la vista de un módulo.')
    parser.add_argument('--demo', action='store_true', help='Desactivar motores reales y mostrar solo simulaciones.')
    parser.add_argument('--daily', action='store_true', help='Mostrar el modo diario del módulo seleccionado; no iniciar descargas automáticamente.')
    parser.add_argument('--details-storage', type=Path, help='Almacenamiento aislado para comprobaciones de Detalles.')
    parser.add_argument('--transit-storage', type=Path, help='Almacenamiento aislado para comprobaciones de Tránsito.')
    parser.add_argument('--talon-storage', type=Path, help='Almacenamiento aislado para comprobaciones de Talón.')
    parser.add_argument('--movements-storage', type=Path, help='Almacenamiento aislado para comprobaciones de XMovimientos.')
    parser.add_argument('--manifest-storage', type=Path, help='Almacenamiento aislado para Manifiestos.')
    parser.add_argument('--bls-storage', type=Path, help='Almacenamiento aislado para BLs.')
    args = parser.parse_args()
    if args.smoke_test or args.capture:
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        os.environ.setdefault('QT_QUICK_BACKEND', 'software')
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('CHC.Consultores.Workbench')
    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName('CHC Workbench')
    app.setOrganizationName('CHC Consultores')
    app.setWindowIcon(QIcon(str(HERE / 'assets/branding/chc.ico')))
    instance = SingleInstance()
    if not (args.smoke_test or args.capture) and not instance.acquire():
        return 0
    app.aboutToQuit.connect(instance.close)
    # La plataforma offscreen de Windows no descubre automáticamente fuentes.
    # Registrar las del sistema permite revisar capturas con el mismo diseño.
    if os.environ.get('QT_QPA_PLATFORM') == 'offscreen' and sys.platform == 'win32':
        font_folder = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        for name in ('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf', 'segoeuil.ttf', 'consola.ttf'):
            font_file = font_folder / name
            if font_file.is_file():
                QFontDatabase.addApplicationFont(str(font_file))
    app.setFont(QFont('Segoe UI', 10))
    QQuickStyle.setStyle('Basic')
    details = DetailsBridge(enabled=not (args.demo or args.smoke_test), storage_root=args.details_storage)
    transit = DetailsBridge(enabled=not (args.demo or args.smoke_test), storage_root=args.transit_storage, module_id='duas_transito')
    talon = DetailsBridge(enabled=not (args.demo or args.smoke_test), storage_root=args.talon_storage, module_id='talon')
    movements = DetailsBridge(enabled=not (args.demo or args.smoke_test), storage_root=args.movements_storage, module_id='xmovimientos')
    manifests = BatchBridge(enabled=not (args.demo or args.smoke_test), storage_root=args.manifest_storage)
    bls = BatchBridge(module_id='bls', enabled=not (args.demo or args.smoke_test), storage_root=args.bls_storage,
                      knowledge_root=args.manifest_storage)
    manifests.eventReceived.connect(lambda event: bls.refreshKnowledge() if
        event.get('flow')=='conocimientos' and event.get('event')=='idle' and
        event.get('command') in ('run','import_progress') else None)
    bridges = {'detalles': details, 'duas_transito': transit, 'talon': talon, 'xmovimientos': movements,
               'manifiestos': manifests, 'bls': bls}
    preferences = Preferences(HERE.parent / 'runtime' / 'workbench' / 'preferences.json', persist=not (args.smoke_test or args.capture))
    storage={'detalles':args.details_storage,'duas_transito':args.transit_storage,
             'talon':args.talon_storage,'xmovimientos':args.movements_storage,
             'manifiestos':args.manifest_storage,'bls':args.bls_storage}
    monthly=MonthlyProgress({key:root or HERE.parent/'bots'/key for key,root in storage.items()}
                            if not (args.demo or args.smoke_test) else {})
    backend = DemoBackend(HERE / 'modules.json', details, transit, talon, movements, manifests, bls, monthly)
    cloud = SharePointBridge(enabled=not (args.demo or args.smoke_test or args.capture))
    monthly.changed.connect(lambda: cloud.refreshMonthlyStatus() if not monthly.busy else None)
    cloud.toast.connect(backend.toast.emit)
    if cloud.storage.joinpath('destinations.json').exists() and cloud.enabled:
        cloud.refresh()
    app.aboutToQuit.connect(cloud.shutdown)
    app.aboutToQuit.connect(backend.monthLauncher.cancel)
    for bridge in bridges.values():
        bridge.toast.connect(backend.toast.emit)
    preferences.error.connect(backend.toast.emit)
    initial_page = args.page if (args.capture or args.smoke_test or args.demo) else 'overview'
    backend.navigate(initial_page)
    if args.sample and args.page != 'overview' and (args.page not in bridges or not details.enabled):
        backend.loadSample()
        backend.startDemo()
        for _ in range(24):
            backend._tick()
        backend.pauseDemo()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('demo', backend)
    engine.rootContext().setContextProperty('details', details)
    engine.rootContext().setContextProperty('transit', transit)
    engine.rootContext().setContextProperty('talon', talon)
    engine.rootContext().setContextProperty('movements', movements)
    engine.rootContext().setContextProperty('manifests', manifests)
    engine.rootContext().setContextProperty('bls', bls)
    engine.rootContext().setContextProperty('preferences', preferences)
    engine.rootContext().setContextProperty('sharepoint', cloud)
    engine.setInitialProperties({'sidebarExpanded': not args.collapsed, 'initialDark': False if args.light else preferences.dark})
    errors = []
    engine.warnings.connect(lambda warnings: errors.extend(warning.toString() for warning in warnings))
    engine.load(QUrl.fromLocalFile(str(HERE / 'qml' / 'Main.qml')))
    if not engine.rootObjects():
        print('\n'.join(errors), file=sys.stderr)
        return 1
    window = engine.rootObjects()[0]
    instance.window = window
    window.setProperty('demoBackend', backend)
    selected_bridge = bridges.get(args.page, details)
    if args.daily and selected_bridge.enabled and isinstance(selected_bridge, DetailsBridge):
        daily_selected = False
        def select_daily():
            nonlocal daily_selected
            if not daily_selected and selected_bridge.ready:
                page_name = {'detalles': 'detailsRealPage', 'duas_transito': 'transitRealPage'}.get(args.page, args.page + 'RealPage')
                page = window.findChild(QObject, page_name)
                if page:
                    from PySide6.QtCore import QMetaObject, Qt
                    QMetaObject.invokeMethod(page, 'selectDailyMode', Qt.DirectConnection)
                    daily_selected = True
        selected_bridge.changed.connect(select_daily)
        QTimer.singleShot(0, select_daily)
    if details.enabled:
        for bridge in bridges.values():
            # La ventana se crea primero. Cada QProcess prepara su propia base
            # sin esperar a los demás ni cambiar la ruta cuando responde.
            QTimer.singleShot(0, bridge.connectModule)
    if not args.smoke_test and not args.capture:
        available = app.primaryScreen().availableGeometry()
        window.setMinimumWidth(min(window.minimumWidth(), available.width() - 32))
        window.setMinimumHeight(min(window.minimumHeight(), available.height() - 48))
        window.setWidth(min(window.width(), available.width() - 32))
        window.setHeight(min(window.height(), available.height() - 48))
    if args.smoke_test:
        from PySide6.QtCore import QMetaObject, Qt

        def check():
            try:
                assert len(backend.modules) == 6
                for module in backend.modules:
                    backend.navigate(module['id'])
                    app.processEvents()
                    assert window.findChild(QObject, 'modulePage') is not None
                    backend.loadSample()
                    backend.startDemo()
                    backend._tick()
                    backend.pauseDemo()
                    assert backend.selectedModule['status'] == 'paused'
                    assert backend.selectedModule['progress'] > 0
                    backend.startDemo()
                    assert backend.selectedModule['status'] == 'running'
                    backend.pauseDemo()
                backend.navigate('bls')
                assert backend.selectedModule['status'] == 'paused'
                backend.resetDemo()
                assert not backend.selectedModule['loaded']
                backend.loadSample()
                backend.setWorkers(4)
                backend.startDemo()
                for _ in range(30):
                    backend._tick()
                assert backend.selectedModule['status'] == 'completed'
                assert backend.selectedModule['progress'] == 240
                assert all(row['status'] == 'Confirmado' for row in backend.previewRows)
                backend.search('tránsito')
                assert len(backend.filteredModules) == 1
                backend.search('ningún módulo')
                assert len(backend.filteredModules) == 0
                backend.search('')
                backend.navigate('overview')
                window.setProperty('sidebarExpanded', False)
                QMetaObject.invokeMethod(window, 'toggleTheme', Qt.DirectConnection)
                app.processEvents()
                bot_root = HERE.parent / 'bots'
                assert not any(
                    Path(module.__file__).resolve().is_relative_to(bot_root)
                    for module in sys.modules.values()
                    if getattr(module, '__file__', None)
                ), 'El panel importó fuentes de bots.'
                assert not errors, '\n'.join(errors)
                print('OK: QML, seis vistas, estado independiente, simulación, pausa, reinicio, búsqueda, barra lateral y tema.')
                app.exit(0)
            except Exception as error:
                print(f'ERROR: {error}', file=sys.stderr)
                app.exit(1)

        QTimer.singleShot(600, check)
    elif args.capture:
        capture_attempts = 0
        def capture():
            nonlocal capture_attempts
            if selected_bridge.enabled and not selected_bridge.ready and not selected_bridge.error and capture_attempts < 60:
                capture_attempts += 1
                QTimer.singleShot(500, capture)
                return
            args.capture.parent.mkdir(parents=True, exist_ok=True)
            saved = window.grabWindow().save(str(args.capture))
            print(f'Captura: {args.capture}; QML warnings: {len(errors)}; módulo listo: {selected_bridge.ready if selected_bridge.enabled else "demo"}')
            if errors:
                print('\n'.join(errors), file=sys.stderr)
            if details.enabled:
                ready = selected_bridge.ready
                def finish_capture():
                    if all(bridge.isClosed for bridge in bridges.values()):
                        app.exit(0 if saved and not errors and ready else 1)
                for bridge in bridges.values():
                    bridge.closed.connect(finish_capture)
                for bridge in bridges.values():
                    bridge.shutdown()
            else:
                app.exit(0 if saved and not errors else 1)

        QTimer.singleShot(900, capture)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
