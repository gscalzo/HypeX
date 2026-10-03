---
name: hype
description: |
  Make and edit slide presentations with Hype, which turns one Markdown file into
  slides, PDF, PowerPoint, and (on macOS) Keynote. Use for ANY request to create, change, review, or
  export a presentation, deck, slides, talk, or keynote, and for any .md file
  that is a Hype presentation.
---

# Hype

A Hype presentation is one Markdown file with `images/` and `videos/` beside it.
You write the file with your ordinary editing tools; the `hype` command starts,
checks, renders, and exports it. No command needs a display.

Run `hype help format` first. It prints the whole slide format, including front
matter, slide separators, image and video options, and Mermaid flowchart
diagrams, for this version of Hype.

## Workflow

1. Start: `hype new talk/presentation.md --title "My talk"` (`hype themes` lists
   themes for `--theme`). For an existing presentation, `hype slides <file>`
   prints an outline with each slide's number and lines.
2. Edit the Markdown file directly. Put media in `images/` or `videos/` and
   reference it by filename only.
3. Check: `hype check <file> --json` reports every problem with its slide and
   line. Fix errors, and treat a cramped-text warning as a cue to say less or
   split the slide.
4. Look: `hype render <file> --slide N -o /tmp/slide.png`, then view the PNG.
   Do this for slides whose layout matters: images, code, long text.
5. Export when asked: `hype export <file> talk.pdf`, `talk.pptx`, or on macOS
   `talk.key`. A `.pptx` or `.key` carries the speaker notes, formatted; its
   slides are pictures, so changes go in the Markdown, followed by a new export.

## Where things go

`hype help format` has the details; this is where to look for them.

- What the speaker says: `<!-- comments -->` on the slide. They appear in
  Presenter View and on the PowerPoint and Keynote notes pages, never on the
  slide.
- The talk's length: `<!-- hype: duration="20m" -->` on the first slide, for
  Presenter View's countdown.
- The deck's look: `theme`, `font`, and `color_*` in the front matter. For bold
  words in their own style, such as a heavier face in red, `bold_font` and
  `bold_color`; `**bold**` in the text then uses them. Do not use HTML or inline
  styles for this.
- Where text sits, such as top left: `alignment` and `vertical_alignment` in the
  front matter for the whole deck, or in one slide's `hype:` comment.
- Readable text on or beside an image: the slide's `layout` setting reserves
  separate regions; `image-full` gives a fitted image the whole canvas.
  `image_blur` controls whether artwork stays sharp; `image_blur="text"` keeps
  it sharp and blurs only a panel under the text, tuned with `panel_blur`,
  `panel_color`, `panel_opacity` and `panel_radius`. Use `fit` to keep the
  whole image or `span` to fill its region. See `hype help format`.
- One slide's colors: `<!-- hype: background="#000000" -->`, `foreground`.
- Prefer fonts Omarchy installs (JetBrains Mono, Noto, iA Writer); `hype check`
  warns about others, so mention it if the person asked for one.

## Working with the person

- If they have the presentation open in the Hype editor, your saved edits appear
  there at once and the editor stays on the slide they are viewing. `hype open
  <file>` opens the editor for them; it needs their desktop, so do not wait on it.
- Slides are for an audience: a headline, a few bullets, or one image each. Prefer
  more slides over fuller ones.
- Every command takes `--json`, exits 0 on success and 1 on failure, and writes
  errors to stderr. `hype help <command>` lists a command's options.
- This skill comes with Hype. After updating Hype, `hype skill install` refreshes
  the installed copy.
