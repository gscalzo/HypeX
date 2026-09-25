.pragma library
// macOS spells shortcuts with symbols, and three of Hype's collide with the system:
// ⌘Space is Spotlight, ⌘H hides the app and ⌘M minimizes the window.
// Elsewhere every function returns its input, so Linux is untouched.
var mac = Qt.platform.os === "osx"

// The macOS port is HypeX; its files and commands keep Hype's names.
var appName = mac ? "HypeX" : "Hype"

// Shortcut sequences, as QML Shortcut expects them.
var present = mac ? ["F5", "Ctrl+Alt+P"] : ["F5", "Ctrl+Space"]
var headline = mac ? "Ctrl+1" : "Ctrl+H"
var overview = mac ? "Ctrl+0" : "Ctrl+M"
var deleteSlides = mac ? ["Delete", "Backspace"] : ["Delete"]

// Shortcut text in tooltips, menus and the overlay.
function label(text) {
    if (!mac || !text)
        return text
    return text
        .replace(/Ctrl\+Space/g, "⌥⌘P")
        .replace(/Ctrl\+H\b/g, "⌘1")
        .replace(/Ctrl\+M\b/g, "⌘0")
        .replace(/^(Delete|Del)$/, "⌫")
        .replace(/^Enter$/, "Return")
        .replace(/Ctrl\+Shift\+/g, "⇧⌘")
        .replace(/Ctrl\+/g, "⌘")
        .replace(/Shift\+/g, "⇧")
        .replace(/⌘Enter/g, "⌘↩")
}
