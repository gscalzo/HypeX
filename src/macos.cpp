#include "macos.h"
#include "deck.h"
#include <QCoreApplication>
#include <QDir>
#include <QDateTime>
#include <QFile>
#include <QFileOpenEvent>
#include <QGuiApplication>
#include <QKeyEvent>
#include <QMutex>
#include <QRect>
#include <QScreen>
#include <QWindow>
#include <QStringList>
#include <CoreFoundation/CoreFoundation.h>
#include <memory>

bool launchedAsApp() {
    // A terminal exports its own identifier (com.apple.Terminal, ...) to the shells it starts.
    const QByteArray launcher = qgetenv("__CFBundleIdentifier");
    const CFStringRef identifier = CFBundleGetIdentifier(CFBundleGetMainBundle());
    return identifier && !launcher.isEmpty() &&
           launcher == QString::fromCFString(identifier).toUtf8();
}

void prepareMacEnvironment() {
    // The inherited PATH comes first, so a terminal's choices still win.
    const QString bundled = QCoreApplication::applicationDirPath();
    QStringList path = qEnvironmentVariable("PATH").split(':', Qt::SkipEmptyParts);
    for (const QString &entry : {bundled, QString("/opt/homebrew/bin"), QString("/usr/local/bin")})
        if (!path.contains(entry))
            path << entry;
    qputenv("PATH", path.join(':').toUtf8());
    const QString languages = QDir(bundled + "/../Resources/source-highlight").canonicalPath();
    if (!languages.isEmpty())
        qputenv("SOURCE_HIGHLIGHT_DATADIR", languages.toUtf8());
}

namespace {
class FinderFiles : public QObject {
  public:
    explicit FinderFiles(Deck *deck) : QObject(deck), m_deck(deck) {}
    bool eventFilter(QObject *object, QEvent *event) override {
        if (event->type() != QEvent::FileOpen)
            return QObject::eventFilter(object, event);
        m_deck->openPath(static_cast<QFileOpenEvent *>(event)->file());
        return true;
    }
  private:
    Deck *m_deck;
};
}

void openFinderFiles(Deck *deck) { QCoreApplication::instance()->installEventFilter(new FinderFiles(deck)); }

bool isOmarchyFont(const QString &family) {
    // JetBrainsMono Nerd Font is Omarchy's system font; Hype's default names the plain family.
    // Noto and iA Writer ship in the base install (noto-fonts, ttf-ia-writer).
    for (const char *prefix : {"JetBrains Mono", "JetBrainsMono Nerd Font", "Noto ", "iA Writer "})
        if (family.startsWith(QLatin1String(prefix)))
            return true;
    return false;
}

namespace {
QFile *logFile = nullptr;
QtMessageHandler previousHandler = nullptr;
void writeLog(QtMsgType type, const QMessageLogContext &context, const QString &message) {
    static QMutex mutex;
    {
        QMutexLocker lock(&mutex);
        if (logFile) {
            static const char *levels[] = {"debug", "warning", "critical", "fatal", "info"};
            const QString line = QDateTime::currentDateTime().toString("HH:mm:ss.zzz") + ' ' +
                                 levels[qBound(0, int(type), 4)] + ' ' + message + '\n';
            logFile->write(line.toUtf8());
            logFile->flush();
        }
    }
    if (previousHandler)
        previousHandler(type, context, message);
}
QString describe(const QScreen *screen) {
    const QRect g = screen->geometry();
    return QString("'%1' model='%2' %3x%4 at %5,%6 scale %7%8")
        .arg(screen->name(), screen->model()).arg(g.width()).arg(g.height()).arg(g.x()).arg(g.y())
        .arg(screen->devicePixelRatio())
        .arg(screen == QGuiApplication::primaryScreen() ? " primary" : "");
}
void logScreens(const char *why) {
    qInfo("[HypeX] displays (%s): %d", why, int(QGuiApplication::screens().size()));
    for (const QScreen *screen : QGuiApplication::screens())
        qInfo("[HypeX]   %s", qPrintable(describe(screen)));
}
class KeyLog : public QObject {
  public:
    using QObject::QObject;
    bool eventFilter(QObject *object, QEvent *event) override {
        // Windows see every key once, before Shortcuts or items handle it.
        if ((event->type() == QEvent::ShortcutOverride || event->type() == QEvent::KeyPress) &&
            object->isWindowType()) {
            const auto *key = static_cast<QKeyEvent *>(event);
            qInfo("[HypeX] key %s: key=0x%x text='%s' modifiers=0x%x native=0x%x%s window='%s'",
                  event->type() == QEvent::KeyPress ? "press" : "override", key->key(),
                  qPrintable(key->text().toHtmlEscaped()), uint(key->modifiers()),
                  key->nativeVirtualKey(), key->isAutoRepeat() ? " repeat" : "",
                  qPrintable(static_cast<QWindow *>(object)->title()));
        }
        return QObject::eventFilter(object, event);
    }
};
}

void startMacLog(Deck *deck) {
    const QString directory = QDir::homePath() + "/Library/Logs/HypeX";
    QDir().mkpath(directory);
    logFile = new QFile(directory + "/hypex.log", deck);
    if (!logFile->open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text)) {
        delete logFile;
        logFile = nullptr;
        return;
    }
    previousHandler = qInstallMessageHandler(writeLog);
    qInfo("[HypeX] started %s", qPrintable(QCoreApplication::applicationFilePath()));
    logScreens("at launch");
    auto *app = qobject_cast<QGuiApplication *>(QCoreApplication::instance());
    QObject::connect(app, &QGuiApplication::screenAdded, deck, [](QScreen *) { logScreens("added"); });
    QObject::connect(app, &QGuiApplication::screenRemoved, deck, [](QScreen *) { logScreens("removed"); });
    QObject::connect(app, &QGuiApplication::focusWindowChanged, deck, [](QWindow *window) {
        qInfo("[HypeX] focus window: '%s'", window ? qPrintable(window->title()) : "none");
    });
    app->installEventFilter(new KeyLog(deck));
    auto last = std::make_shared<int>(deck->selected());
    QObject::connect(deck, &Deck::changed, deck, [deck, last] {
        if (deck->selected() != *last)
            qInfo("[HypeX] slide %d -> %d of %d", *last + 1, deck->selected() + 1, deck->count());
        *last = deck->selected();
    });
}
