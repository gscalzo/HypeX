#include "filedialog.h"
#include <QDir>
#include <QFileDialog>
#include <QFileInfo>

// macOS has no desktop portal. Qt's static pickers show the native NSOpenPanel
// and NSSavePanel, with the same calling convention as the portal version.
QString FileDialog::choose(bool save, const QString &location, const QString &label,
                           const QStringList &patterns, QString *error) {
    error->clear();
    const QString filter = label + " (" + patterns.join(' ') + ")";
    if (save)
        return QFileDialog::getSaveFileName(nullptr, "Save File", location, filter);
    return QFileDialog::getOpenFileName(nullptr, "Open File", QDir(location).absolutePath(), filter);
}

// The portal's request plumbing has nothing to do here.
bool FileDialog::listen(const QString &) { return false; }
void FileDialog::disconnectRequest() {}
void FileDialog::response(uint, const QVariantMap &) {}
bool FileDialog::eventFilter(QObject *, QEvent *) { return false; }
