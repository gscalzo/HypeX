QT += core gui qml quick quickcontrols2 multimedia concurrent dbus
# Like Qt's own modules, Hype never throws or catches. Without unwinding tables and with
# link-time optimization, the installed binary is about a quarter smaller.
CONFIG += c++17 release ltcg exceptions_off
TARGET = hype
TEMPLATE = app
HEADERS += src/deck.h src/renderer.h
SOURCES += src/main.cpp src/deck.cpp src/renderer.cpp
RESOURCES += src/resources.qrc

SOURCES += src/syntax.cpp
HEADERS += src/syntax.h
SOURCES += src/pptx.cpp
HEADERS += src/pptx.h
LIBS += -lz -lwebpdemux -lwebp

SOURCES += src/animationexport.cpp
HEADERS += src/animationexport.h

SOURCES += src/apptheme.cpp
HEADERS += src/apptheme.h
SOURCES += src/images.cpp
HEADERS += src/images.h
SOURCES += src/filedialog.cpp
HEADERS += src/filedialog.h
SOURCES += src/recovery.cpp
SOURCES += src/cli.cpp
HEADERS += src/cli.h
SOURCES += src/mermaid.cpp
HEADERS += src/mermaid.h

# macOS: a self-contained HypeX.app for drafting. PowerPoint export stays compiled
# but is unavailable; file dialogs are native instead of the desktop portal.
macx {
    TARGET = HypeX
    QT -= dbus
    QT += widgets
    SOURCES -= src/filedialog.cpp
    SOURCES += src/filedialog_mac.cpp src/macos.cpp
    HEADERS += src/macos.h
    INCLUDEPATH += /opt/homebrew/include
    LIBS += -L/opt/homebrew/lib
    QMAKE_INFO_PLIST = $$PWD/macos/Info.plist
    ICON = $$PWD/macos/HypeX.icns
    themes.files = $$PWD/themes
    themes.path = Contents/Resources
    QMAKE_BUNDLE_DATA += themes
}
