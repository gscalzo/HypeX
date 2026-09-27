# HypeX

HypeX is Hype's own code (parser, renderer, editor) built for macOS. The same
code still builds Hype on Linux: macOS-only changes sit behind `Q_OS_MACOS` in
C++, `macx {}` in `hype.pro`, and `MacKeys.mac` in QML.

## Build and test

```sh
bin/build-macos                 # build-macos/HypeX.app; the Python tests run this build
bin/test                        # Qt unit tests
HYPE_GUI_TESTS=1 bin/test       # adds the editor and Presenter View tests
python3 -m unittest tests.test_cli tests.test_shutdown tests.test_export
bin/install-macos               # install to /Applications and put hype on PATH
```

Rebuild with `bin/build-macos` before the Python tests, or they run the old app.
Opening, editing and saving a deck must leave the file byte-identical; the
round-trip tests hold it to that.

## Keep the docs and the skill in step

Three documents describe what HypeX does, for three readers. Any change a person
or an agent could notice updates all of them in the same commit:

- `README.md`, for people: the feature, how to use it, and its shortcut in the
  keyboard table.
- `src/format.md`, printed by `hype help format`: the complete slide format for
  agents. Every front matter key, `hype:` slide setting, media option, notes
  rule and command belongs here.
- `src/skill.md`, installed by `hype skill install`: the agent skill. It sends
  agents to `hype help format` for details, so it says where things go and how
  to work, not the full syntax.

That covers new or changed front matter keys, slide settings, media options,
Markdown behavior, `hype` commands and options, `hype check` warnings,
Presenter View and editor features, and export behavior. A change that is
invisible from the outside, such as a refactor or a speed-up, needs none of
them.

When `src/skill.md` changes, run `hype skill install` after `bin/install-macos`
so the installed copy matches.

## Compatibility with Hype on Omarchy

A deck written in HypeX must still open in stock Hype. Add new settings as keys
or `hype:` comments that Hype ignores, never as syntax Hype would show on the
slide, and say in the docs what Hype on Omarchy does with them.
