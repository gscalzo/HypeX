#include "keynote.h"
#include <QFile>
#include <QProcess>
#include <QRegularExpression>
#include <CoreServices/CoreServices.h>

namespace {
constexpr auto keynoteId = "com.apple.Keynote";

bool keynoteInstalled() {
    const CFStringRef identifier = QString(keynoteId).toCFString();
    const CFArrayRef apps = LSCopyApplicationURLsForBundleIdentifier(identifier, nullptr);
    CFRelease(identifier);
    if (!apps)
        return false;
    const bool found = CFArrayGetCount(apps) > 0;
    CFRelease(apps);
    return found;
}

// Keynote's AppleScript opens a .pptx as a new presentation and saves it as a .key.
// A Keynote the export started is quit again; one the user had open is left alone.
// A Keynote still quitting from the last export opens nothing, so opening retries.
// Paths arrive as arguments, so no quoting reaches the script.
const char *script = R"(on run argv
    set source to POSIX file (item 1 of argv)
    set destination to POSIX file (item 2 of argv)
    set wasRunning to application id "com.apple.Keynote" is running
    tell application id "com.apple.Keynote"
        with timeout of 3600 seconds
            set theDeck to missing value
            repeat 10 times
                set theDeck to open source
                if theDeck is not missing value then exit repeat
                delay 1
            end repeat
            if theDeck is missing value then error "Keynote did not open the PowerPoint file."
            try
                save theDeck in destination
            on error message number code
                close theDeck saving no
                error message number code
            end try
            close theDeck saving no
        end timeout
        if not wasRunning then quit
    end tell
end run)";

// osascript reports "script: execution error: Keynote got an error: <message> (<code>)".
QString readableError(const QString &output) {
    static const QRegularExpression code(R"(\((-?\d+)\)\s*$)");
    const auto match = code.match(output.trimmed());
    if (match.hasMatch() && match.captured(1) == "-1743")
        return "HypeX may not control Keynote. Allow it in System Settings → Privacy & Security → "
               "Automation, then export again.";
    QString message = output.trimmed();
    const qsizetype start = message.indexOf("execution error: ");
    if (start >= 0)
        message = message.mid(start + 17);
    message.remove(code);
    return "Keynote could not convert the presentation: " + message.trimmed();
}
}

bool convertToKeynote(const QString &pptx, const QString &destination, QString *error) {
    if (!keynoteInstalled()) {
        if (error) *error = "Keynote is not installed. It is free on the Mac App Store.";
        return false;
    }
    QFile::remove(destination);
    QProcess osascript;
    osascript.start("/usr/bin/osascript", {"-e", script, pptx, destination});
    // Keynote asks for permission the first time, and a large deck takes a while.
    osascript.waitForFinished(-1);
    if (osascript.exitStatus() != QProcess::NormalExit || osascript.exitCode() != 0 ||
        !QFile::exists(destination)) {
        if (error) {
            const QString output = QString::fromUtf8(osascript.readAllStandardError());
            *error = output.trimmed().isEmpty() ? "Keynote did not save the presentation."
                                                : readableError(output);
        }
        return false;
    }
    return true;
}
