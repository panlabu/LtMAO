from PySide6.QtWidgets import QApplication 
from PySide6.QtGui import QFontDatabase, QFont, QBrush, QColor
import modern_colorthief

def build_app():
    # set app theme
    from qdarktheme import enable_hi_dpi, setup_theme
    enable_hi_dpi()
    global app
    app = QApplication([])
    setup_theme('dark')
    
    # 1st load
    from .. import stash
    stash.init()

    # set font
    id = QFontDatabase.addApplicationFont('./res/font.ttf')
    family = QFontDatabase.applicationFontFamilies(id)[0] if id > -1 else 'Consolas'
    app.setFont(QFont(family, weight=15))

    # set theme func and init theme
    app.init_theme = init_theme
    app.init_theme(stash.fetch('qtGUI.theme_name', 'raora'))

    # build splash first
    from . import splash
    splash.app = app
    splash.build_splash()

    # show plash
    app.splash.show()
    app.splash.activateWindow()

    # 2nd load
    from .. import no_skin, cslmao, hash_helper, winLT, bnk_tool, wiwawe, infinityQT
    no_skin.init()
    cslmao.init()
    hash_helper.init()
    bnk_tool.init()
    wiwawe.init()
    infinityQT.init()
    winLT.create_launch(app.theme_paths['appicon'])

    # build main
    from . import main
    main.app = app
    main.build_main()

    # close splash show main
    app.splash.close()
    app.main.show()
    app.main.activateWindow()

    app.exec()


def init_theme(theme_name):
    # set theme paths
    app.theme_paths = {
        'splash': f'./res/themes/{theme_name}/splash.png',
        'background': f'./res/themes/{theme_name}/background.gif',
        'titlebaricon': f'./res/themes/{theme_name}/titlebaricon.png',
        'appicon': f'./res/themes/{theme_name}/appicon.ico'
    }
    # get accent color from background image
    if '_' in theme_name:
        colors = modern_colorthief.get_palette(app.theme_paths['background'], quality=1, color_count=2)
        r1, g1, b1 = colors[0]
        f = 255*0.7 / max(r1, g1, b1)
        r1, g1, b1 = (int(r1*f), int(g1*f), int(b1*f))
        r2, g2, b2 = colors[1]
        f = 255*0.7 / max(r2, g2, b2)
        r2, g2, b2 = (int(r2*f), int(g2*f), int(b2*f))
        app.accent_color = f'qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0.0 #{r1:02x}{g1:02x}{b1:02x}, stop: 1.0 #{r2:02x}{g2:02x}{b2:02x})'
        app.accent_brush = QBrush(QColor(r1, g1, b1))
    else:
        r, g, b = modern_colorthief.get_color(app.theme_paths['background'], quality=1)
        f = 255*0.7 / max(r, g, b)
        r, g, b = (int(r*f), int(g*f), int(b*f))
        app.accent_color = f'rgb({r}, {g}, {b})'
        app.accent_brush = QBrush(QColor(r, g, b))
    # stylesheets
    app.window_stylesheet = f"""
        QWidget {{
            background-color: rgba(0, 0, 0, 127);    
        }}  
        QWidget#Round {{
            border-radius: 8;
        }}
        QLabel {{
            background-color: transparent;

        }}  
        QScrollBar:handle {{
            background-color: {app.accent_color}; 
            border-radius: 3;
        }}
        QScrollArea {{
            border: none;
            background-color: transparent;
        }}         
        QToolButton {{
            min-height: 30;
            border-bottom: 2px solid {app.accent_color};
            border-radius: 8;
        }}
        QToolButton:hover {{ 
            background-color: {app.accent_color}; 
        }}
        QToolButton:checked {{ 
            background-color: {app.accent_color}; 
        }}
        QCheckBox {{
            min-height: 30;
            border-radius: 8;
        }}
        QCheckBox:hover {{
            border-bottom-color: {app.accent_color};  
        }} 
        QLineEdit {{
            min-height: 30;
            selection-background-color: {app.accent_color};
            border-radius: 8;
        }}
        QLineEdit:focus {{
            border-color: {app.accent_color};  
        }}
        QPlainTextEdit {{
            selection-background-color: {app.accent_color};
            border-radius: 8;
        }}
        QPlainTextEdit:focus {{
            border-color: {app.accent_color};  
        }}
        QComboBox {{
            border-radius: 8;
        }}
        QComboBox:hover, QComboBox:selected, QComboBox:on {{
            border-color: {app.accent_color};
        }}
        QComboBox QAbstractItemView {{
            border-color: {app.accent_color};
            border-radius: 8;
        }}
        QComboBox QAbstractItemView:item {{
            border-radius: 8;
        }}
        QComboBox QAbstractItemView:item:hover, QComboBox QAbstractItemView:item:selected {{
            background-color: {app.accent_color};    
        }}
        QTabWidget:pane {{
            border: none;
        }}   
        QTabWidget:tab-bar {{
            background-color: rgba(0, 0, 0, 127);        
        }}    
        QTabBar:tab {{
            min-height: 30;
            min-width: 120;
            background-color: rgba(0, 0, 0, 127);        
            border-radius: 8;
        }}
        QTabBar:tab:selected {{
            color: #ffffff;
            border-bottom-color: {app.accent_color};
            background-color: {app.accent_color};
        }}
        QTabBar:scroller {{
            width: 50px; 
        }}
        QTableView {{
            selection-background-color: {app.accent_color};
            border-radius: 8;
        }}
        QHeaderView:section {{
            background-color: transparent;
        }}
        QTableView QTableCornerButton::section {{
            background-color: rgba(0, 0, 0, 127);  
        }}
        QHeaderView:section:checked {{
            color: #ffffff;
            background-color: {app.accent_color};
        }}
        QTreeView {{
            border-radius: 8;
        }}
        QTreeView:item:selected  {{
            background-color: {app.accent_color};
        }}
        QToolTip {{
            background-color: rgba(0, 0, 0, 127);
            border: none;   
        }}
        QSlider:handle {{
            background-color: {app.accent_color};
            border: none;
        }}
        QSlider:sub-page {{
            background-color: {app.accent_color};
        }}
        QMessageBox {{
            background-color: black;
            border: 2px solid {app.accent_color};
        }}
        QDialogButtonBox > QPushButton[text="&Yes"] {{
            min-height: 30;
            color: white;
            background-color: rgb(0, 255, 0);
            border-bottom: 2px solid {app.accent_color};
        }}
        QDialogButtonBox > QPushButton[text="&No"] {{
            min-height: 30;
            color: white;
            background-color: rgb(255, 0, 0);
            border-bottom: 2px solid {app.accent_color};
        }}
        QStatusBar {{
            border-radius: 8;
        }}
    """
    app.tab_stylesheet = f"""
        QWidget {{
            background-color: transparent;
        }}     
        QWidget#Round {{
            border-radius: 8;
        }}
        QToolButton {{
            min-height: 30;
            background-color: rgba(0, 0, 0, 127);
            border-bottom: 2px solid {app.accent_color};
            border-radius: 8;
        }}
        QLabel {{
            background-color: transparent;
        }}
        QLineEdit {{
            min-height: 30;
            background-color: rgba(0, 0, 0, 127);
            border-radius: 8;
        }}
        QPlainTextEdit {{
            background-color: rgba(0, 0, 0, 127);
            border-radius: 8;
        }}
        QToolButton:hover {{ 
            background-color: {app.accent_color}; 
        }}
        QToolButton:checked {{ 
            background-color: {app.accent_color}; 
        }}
        QTabBar::tab {{
            border-bottom: 2px solid {app.accent_color};
            border-radius: 8;
        }}
        QComboBox {{
            background-color: rgba(0, 0, 0, 127);
            border-radius: 8;
        }}
        QComboBox QAbstractItemView {{
            background-color: rgba(0, 0, 0, 255);
            border-radius: 8;
        }}
    """
    app.mod_enable_stylesheet = f"""
        QWidget#CslmaoModWidgetEnable {{ 
            border: 2px solid {app.accent_color}; 
            border-radius: 8; 
        }} 
        QLabel#CslmaoModWidgetEnable {{ 
            background-color: {app.accent_color}; 
            border-radius: 8; 
        }}
    """
    app.mod_disable_stylesheet = f"""
        QWidget#CslmaoModWidgetDisable {{ 
            border: 2px solid rgb(0, 0, 0); 
            border-radius: 8; 
        }} 
        QLabel#CslmaoModWidgetDisable {{ 
            background-color: rgb(0, 0, 0); 
            border-radius: 8; 
        }}
    """





