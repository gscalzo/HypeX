#pragma once
class Deck;
class QString;

// Make the bundled source-highlight and Homebrew's ffmpeg reachable. Apps opened
// from Finder inherit only /usr/bin:/bin:/usr/sbin:/sbin.
void prepareMacEnvironment();
// Open files dropped on the Dock icon or chosen with Finder's Open With.
void openFinderFiles(Deck *deck);
// Fonts a stock Omarchy install provides, so a deck drafted here renders the same there.
bool isOmarchyFont(const QString &family);
