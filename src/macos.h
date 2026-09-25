#pragma once
class Deck;
class QString;

// Finder, Spotlight and the Dock start the app with no arguments, which on the
// command line means "print help"; LaunchServices marks those launches.
bool launchedAsApp();
// Make the bundled source-highlight and Homebrew's ffmpeg reachable. Apps opened
// from Finder inherit only /usr/bin:/bin:/usr/sbin:/sbin.
void prepareMacEnvironment();
// Open files dropped on the Dock icon or chosen with Finder's Open With.
void openFinderFiles(Deck *deck);
// Fonts a stock Omarchy install provides, so a deck drafted here renders the same there.
bool isOmarchyFont(const QString &family);
// Diagnostics for the editor: Qt messages, navigation keys (never typed text),
// slide changes and displays go to ~/Library/Logs/HypeX/hypex.log, replaced at each launch.
void startMacLog(Deck *deck);
