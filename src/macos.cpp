#include "macos.h"
#include "deck.h"
#include <QCoreApplication>
#include <QDir>
#include <QFileOpenEvent>
#include <QStringList>
#include <CoreFoundation/CoreFoundation.h>

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
