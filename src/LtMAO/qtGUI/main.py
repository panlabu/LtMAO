from PySide6.QtCore import Qt, QEvent, QRect
from PySide6.QtGui import QPixmap, QMovie, QShortcut, QKeySequence
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStatusBar, QToolButton, QSizeGrip, QSystemTrayIcon

import requests, os
from . import helper, control
from .. import setting, hash_helper


app = None

def build_main():
    # build main window
    app.main = window = QMainWindow()
    geometry = setting.get('qtGUI.geometry', [0, 0, 1280, 800])
    window.setGeometry(*geometry)
    window.setWindowIcon(QPixmap(app.theme_paths['appicon']))
    window.setWindowFlags(Qt.Window|Qt.FramelessWindowHint|Qt.WindowMinMaxButtonsHint)
    #window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) this fuck up f3d for some reason
    window.setContentsMargins(0, 0, 0, 0)
    window.setStyleSheet(app.window_stylesheet)

    # build scale grips
    build_grips()

    # build background widget
    app.background_widget = background_widget = QLabel()
    background_widget.setObjectName('backgroundWidget')
    if setting.get('qtGUI.animated_background', True):
        movie = QMovie(app.theme_paths['background'])
        background_widget.setMovie(movie)
        background_widget.setScaledContents(True)
        movie.start()
    else:
        pixmap = QPixmap(app.theme_paths['background'])
        background_widget.setPixmap(pixmap)
        background_widget.setScaledContents(True)
    background_widget.setStyleSheet('#backgroundWidget { border: 1px solid black; }')

    # build background layout
    background_layout = QVBoxLayout()
    background_layout.setContentsMargins(0, 0, 0, 0)
    background_layout.setSpacing(0)
    background_widget.setLayout(background_layout)
    window.setCentralWidget(background_widget)

    # build title bar
    build_title_bar()
    background_layout.addWidget(app.title_bar_widget, stretch=5)
    
    # build mid content
    build_mid_content()
    background_layout.addWidget(app.mid_content_widget, stretch=93)

    # build status bars
    build_status_bar()
    background_layout.addWidget(app.status_bar_widget, stretch=2)

    # build controls
    control.app = app
    # init tab widgets to change stylesheet mid run
    app.tab_widgets = [] 
    for c in control.all:
        c.build_command(c.content)
    
    # events
    def changeEvent(event):
        if event.type() == QEvent.Type.WindowStateChange:
            if window.windowState() == Qt.WindowState.WindowNoState and app.main.remember_maximized_state:
                app.main.showMaximized()
                app.main.remember_maximized_state = False
            if window.windowState() == Qt.WindowState.WindowMaximized:
                app.nor_button.setVisible(True)
                app.max_button.setVisible(False)
            else:
                app.nor_button.setVisible(False)
                app.max_button.setVisible(True)
        event.accept()
    window.changeEvent = changeEvent
    
    # f12 to take screenshot
    def take_screenshot():
        screen = window.screen()

        fg = window.frameGeometry()
        pixmap = screen.grabWindow(0, fg.left(), fg.top(), fg.width(), fg.height())
        count = 0
        while True:
            png_file = f'screenshot_{count}.png'
            if os.path.exists(png_file):
                count += 1
            else:
                pixmap.save(png_file, 'png')
                print(f'qtGUI: Finish: Saved {png_file}.')
                break
    shortcut = QShortcut(QKeySequence('f12'), window)
    shortcut.activated.connect(take_screenshot)
    
    print('qtGUI: Finish: Build main window.')

    # after build
    helper.link_main_window(app.logbox, app.statusbar)
    control.on_page_id_changed(True, setting.get('qtGUI.page_id', 0))
    # check version
    def check_version(label):
        try:
            # read offline
            with open('version', 'r', encoding='utf-8') as f:
                version = f.read()
            title = f'LtMAO-pan V{version}'
            label.setText(title)
            # read online
            get = requests.get('https://raw.githubusercontent.com/panlabu/LtMAO/pan/version')
            get.raise_for_status()
            new_version = get.text
            if version != new_version:
                title += f' - New version found: {new_version}, redownload LtMAO to update.'
            label.setText(title)
        except Exception as e:
            print(f'qtGUI: check_version: Error: {str(e)}')
        print('qtGUI: Finish: Check version.')
    helper.SafeThread.start('check_version', lambda: check_version(app.title_label))
    # sync changelog
    def sync_changelog(changelog):
        local_file = r'.\pref\changelog.txt'
        try:
            # read online
            url=f'https://api.github.com/repos/panlabu/ltmao/commits?sha=pan&per_page=100'
            commits=requests.get(url).json()
            changelog_text = ''.join(
                f'[{commit["commit"]["author"]["date"]}] by {commit["commit"]["author"]["name"]}:\n{commit["commit"]["message"]}\n\n'
                for commit in commits
            )
            with open(local_file, 'w+', encoding='utf-8') as f:
                f.write(changelog_text)

        except Exception as e:
            print(f'sync_changelog: Error: {e}, switching to local file if exists.')
            if os.path.exists(local_file):
                # read offline
                with open(local_file, 'r', encoding='utf-8') as f:
                    changelog_text = f.read()
            else:
                changelog_text = 'sync_changelog: Error: No local changelog to read.'
        changelog.insertPlainText(changelog_text)
        print('qtGUI: Finish: Sync changelog.')
    helper.SafeThread.start('sync_changelog', lambda: sync_changelog(app.changelog))
    # sync hashes
    helper.SafeThread.start('sync_ctdb_hashes', hash_helper.sync_hashes)


def build_grips():
    def build_edge_grip(edge):
        edge_grip = QWidget(app.main)
        edge_grip.setStyleSheet('background-color: transparent')
        if edge == Qt.Edge.RightEdge:
            edge_grip.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            edge_grip.setCursor(Qt.CursorShape.SizeVerCursor)
        def mousePressEvent(event):
            if event.button() == Qt.MouseButton.LeftButton:
                edge_grip.mousePos = event.pos()
            event.accept()
        def mouseMoveEvent(event):
            if edge_grip.mousePos != None:
                delta = event.pos() - edge_grip.mousePos
                if edge == Qt.Edge.RightEdge:
                    window = edge_grip.window()
                    width = max(window.minimumWidth(), window.width() + delta.x())
                    window.resize(width, window.height())
                else:
                    window = edge_grip.window()
                    height = max(window.minimumHeight(), window.height() + delta.y())
                    window.resize(window.width(), height)
            event.accept()
        def mouseReleaseEvent(event):
            edge_grip.mousePos = None
            geometry = app.main.geometry()
            setting.set('qtGUI.geometry', [geometry.x(), geometry.y(), geometry.width(), geometry.height()])
            setting.save()
            event.accept()
        edge_grip.mousePressEvent = mousePressEvent
        edge_grip.mouseMoveEvent = mouseMoveEvent
        edge_grip.mouseReleaseEvent = mouseReleaseEvent
        return edge_grip

    def build_corner_grip():
        corner_grip = QSizeGrip(app.main)
        corner_grip.setFixedSize(grip_size, grip_size)
        corner_grip.setStyleSheet('background-color: transparent')
        def mouseReleaseEvent(event):
            geometry = app.main.geometry()
            setting.set('qtGUI.geometry', [geometry.x(), geometry.y(), geometry.width(), geometry.height()])
            setting.save()
            event.accept()
        corner_grip.mouseReleaseEvent = mouseReleaseEvent
        return corner_grip

    grip_size = 6
    right_edge_grip = build_edge_grip(Qt.Edge.RightEdge)
    bot_edge_grip = build_edge_grip(Qt.Edge.BottomEdge)
    bot_right_corner_grip = build_corner_grip()
    def resizeEvent(event):
        out_rect = app.main.rect()
        in_rect = out_rect.adjusted(grip_size, grip_size,-grip_size, -grip_size)
        right_edge_grip.setGeometry(in_rect.left() + in_rect.width(), in_rect.top(), grip_size, in_rect.height())
        bot_edge_grip.setGeometry(grip_size, in_rect.top() + in_rect.height(), in_rect.width(), grip_size)
        bot_right_corner_grip.setGeometry(QRect(out_rect.bottomRight(), in_rect.bottomRight()).normalized())
        right_edge_grip.raise_()
        bot_edge_grip.raise_()
        bot_right_corner_grip.raise_()
        event.accept()
    app.main.event
    app.main.resizeEvent = resizeEvent

    print('qtGUI: Finish: Build scale grips.')


def build_title_bar():
    # create title bar widget and layout
    app.title_bar_widget = QWidget()
    title_bar_layout = QHBoxLayout()
    app.title_bar_widget.setLayout(title_bar_layout)

    # create another smaller widget, layout inside that wrap everything
    title_layout = QHBoxLayout()
    title_layout.setContentsMargins(0, 0, 0, 0)
    title_widget = QWidget()
    title_widget.setLayout(title_layout)
    title_bar_layout.setContentsMargins(0, 0, 0, 0)
    title_bar_layout.addWidget(title_widget)

    # icon
    pixmap = QPixmap(app.theme_paths['titlebaricon']).scaled(118, 40, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    app.icon_label = icon_label = QLabel(pixmap=pixmap)
    title_layout.addWidget(icon_label, stretch=3)

    # label
    app.title_label = title_label = QLabel('LtMAO-pan')
    title_layout.addWidget(title_label, stretch=100)

    # buttons
    # tray
    app.tray_icon = tray_icon = QSystemTrayIcon()
    tray_icon.setIcon(QPixmap(app.theme_paths['appicon']))
    tray_button = QToolButton()
    tray_button.setText('🟣 Tray')
    tray_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    title_layout.addWidget(tray_button, stretch=3)
    def show_tray_cmd(reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            app.main.show()
            tray_icon.hide()
    tray_icon.activated.connect(show_tray_cmd)
    def hide_tray_cmd(event):
        app.main.hide()
        tray_icon.show()
    tray_button.clicked.connect(hide_tray_cmd)
    # min
    min_button = QToolButton()
    min_button.setText('🟢 Minimize')
    min_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    app.main.remember_maximized_state = False
    def min_button_cmd(event):
        if app.main.windowState() == Qt.WindowState.WindowMaximized:
            app.main.showNormal()
            app.main.remember_maximized_state = True
        app.main.showMinimized()
    min_button.clicked.connect(min_button_cmd)
    title_layout.addWidget(min_button, stretch=3)
    # nor
    app.nor_button = nor_button = QToolButton()
    nor_button.setText('🟡 Restore')
    nor_button.setVisible(False)
    nor_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    nor_button.clicked.connect(app.main.showNormal)
    title_layout.addWidget(nor_button, stretch=3)
    # max
    app.max_button = max_button = QToolButton()
    max_button.setText('🔵 Maximize')
    max_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    max_button.clicked.connect(app.main.showMaximized)
    title_layout.addWidget(max_button, stretch=3)
    # close
    close_button = QToolButton()
    close_button.setText('🔴 Close')
    close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    close_button.clicked.connect(app.quit)
    title_layout.addWidget(close_button, stretch=3)

    # events
    def mousePressEvent(event):
        if event.button() == Qt.MouseButton.LeftButton:
            title_widget.initial_pos = event.position().toPoint()
        event.accept()
    title_widget.mousePressEvent = mousePressEvent
    
    def mouseMoveEvent(event):
        if title_widget.initial_pos is not None:
            delta = event.position().toPoint() - title_widget.initial_pos
            title_widget.window().move(
                title_widget.window().x() + delta.x(),
                title_widget.window().y() + delta.y(),
            )
        event.accept()
    title_widget.mouseMoveEvent = mouseMoveEvent

    def mouseReleaseEvent(event):
        title_widget.initial_pos = None
        geometry = app.main.geometry()
        setting.set('qtGUI.geometry', [geometry.x(), geometry.y(), geometry.width(), geometry.height()])
        setting.save()
        event.accept()
    title_widget.mouseReleaseEvent = mouseReleaseEvent

    def mouseDoubleClickEvent(event):
        if app.main.isMaximized():
            app.main.showNormal()
        else:
            app.main.showMaximized()
        event.accept()
    title_widget.mouseDoubleClickEvent = mouseDoubleClickEvent

    print('qtGUI: Finish: Build title bar.')
    
def build_mid_content():
    app.content_layout = layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    app.mid_content_widget = QWidget()
    app.mid_content_widget.setLayout(app.content_layout)

    widget = QWidget()
    control_layout = QVBoxLayout()
    control_layout.setContentsMargins(0, 0, 0, 0)
    widget.setLayout(control_layout)
    layout.addWidget(widget, stretch=1)
    # build controls
    for c in control.all:
        # create control
        control_button = QToolButton()
        control_button.setText(c.name)
        control_button.setMinimumWidth(120)
        control_button.setCheckable(True)
        c.widget = control_button
        control_button.clicked.connect(lambda event, page_id=c.page_id: control.on_page_id_changed(event, page_id))
        control_layout.addWidget(control_button, stretch=1)
        # create content
        content_widget = QWidget()
        content_widget.setVisible(False)
        c.content = content_widget  
        layout.addWidget(content_widget, stretch=99)
        print(f'qtGUI: Finish: Build {c.name}.')
    control_layout.addStretch()

    print('qtGUI: Finish: Build mid content.')
    
def build_status_bar():
    # create status bar widget and layout
    app.status_bar_widget = QWidget()
    status_bar_layout = QHBoxLayout()
    status_bar_layout.setContentsMargins(0, 0, 0, 0)
    app.status_bar_widget.setLayout(status_bar_layout)

    # create another smaller widget, layout inside that wrap everything
    status_layout = QHBoxLayout()
    status_layout.setContentsMargins(0, 0, 0, 0)
    status_widget = QWidget()
    status_widget.setLayout(status_layout)
    status_bar_layout.addWidget(status_widget)
    
    # status bar
    app.statusbar = statusbar = QStatusBar(sizeGripEnabled=False)
    status_layout.addWidget(statusbar, stretch=94)
    # build logbox and control after status bar
    content_widget = QWidget()
    content_widget.setVisible(False)
    app.content_layout.addWidget(content_widget, stretch=99)
    c = control.Control('', 100, lambda widget: control.build_logbox(widget))
    c.widget = statusbar
    c.content = content_widget
    control.all.append(c)
    def mousePressEvent(event):
        if event.button() == Qt.MouseButton.LeftButton:
            control.on_page_id_changed(True, 100)
        event.accept()
    statusbar.mousePressEvent = mousePressEvent

    # buttons
    # changelog 
    changelog_button = QToolButton()
    changelog_button.setText('📑 Changelog')
    changelog_button.setCheckable(True)
    status_layout.addWidget(changelog_button, stretch=3)
    # build changelog and control after changelog button
    content_widget = QWidget()
    content_widget.setVisible(False)
    app.content_layout.addWidget(content_widget, stretch=99)
    c = control.Control('', 101, lambda widget: control.build_changelog(widget))
    c.widget = changelog_button
    c.content = content_widget
    control.all.append(c)
    changelog_button.clicked.connect(lambda event, page_id=101: control.on_page_id_changed(event, page_id))
    # setting
    setting_button = QToolButton()
    setting_button.setText('⚙️ Setting')
    setting_button.setCheckable(True)
    status_layout.addWidget(setting_button, stretch=3)
    # build setting and control after setting button
    content_widget = QWidget()
    content_widget.setVisible(False)
    app.content_layout.addWidget(content_widget, stretch=99)
    c = control.Control('', 102, lambda widget: control.build_setting(widget))
    c.widget = setting_button
    c.content = content_widget
    control.all.append(c)
    setting_button.clicked.connect(lambda event, page_id=102: control.on_page_id_changed(event, page_id))

    print('qtGUI: Finish: Build status bar.')