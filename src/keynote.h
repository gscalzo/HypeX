#pragma once
#include <QString>

// Has Keynote open a PowerPoint file and save it as a Keynote presentation. The
// slide pictures, videos and notes are moved across as they are, so the result
// looks exactly like the PowerPoint export. Needs Keynote and, the first time,
// the user's permission for HypeX to control it.
bool convertToKeynote(const QString &pptx, const QString &destination, QString *error);
