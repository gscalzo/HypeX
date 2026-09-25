"""Exercise native PowerPoint export using only Python's standard test tools."""
import os
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
import zlib

APP = Path(__file__).resolve().parents[1] / ('build-macos/HypeX.app/Contents/MacOS/HypeX' if sys.platform == 'darwin' else 'build/hype')


# LibreOffice's command is soffice on macOS.
OFFICE = shutil.which('libreoffice') or shutil.which('soffice')

NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def image(path):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' +
                     chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0)) +
                     chunk(b'IDAT', zlib.compress((b'\0' + b'\x70\xa0\xf0' * 2) * 2)) +
                     chunk(b'IEND', b''))


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'images').mkdir()
        (self.root / 'videos').mkdir()
        image(self.root / 'images/photo.png')
        tools = self.root / 'tools'
        tools.mkdir()
        if sys.platform == 'darwin':
            # HypeX.app finds its Qt frameworks and source-highlight inside the bundle.
            self.app = APP
        else:
            self.app = tools / 'hype'
            shutil.copy2(APP, self.app)
        for tool in ['ffmpeg', 'ffprobe', 'source-highlight']:
            (tools / tool).symlink_to(shutil.which(tool))
        # The exported application cannot find Python, pip, or an external ZIP tool.
        self.env = dict(os.environ, PATH=str(tools), XDG_CONFIG_HOME=str(self.root / 'config'),
                        QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_STYLE_OVERRIDE='Fusion')
        self.output = self.root / 'talk.pptx'

    def movie(self, size='320x180', codec='libx264'):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        f'color=c=blue:s={size}:d=0.2', '-c:v', codec, '-pix_fmt', 'yuv420p',
                        str(self.root / 'videos/demo.mp4')], check=True)

    def export(self, markdown, success=True):
        source = self.root / 'presentation.md'
        source.write_text(markdown)
        result = subprocess.run([str(self.app), str(source), '--pptx', str(self.output)],
                                env=self.env, capture_output=True, text=True, timeout=30)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_still_slides_and_xml_escaping(self):
        self.export('---\ntitle: "A & B <C>"\n---\n\n# Hello\n\n---\n\n![](photo.png)\n')
        with zipfile.ZipFile(self.output) as archive:
            self.assertIsNone(archive.testzip())
            payload = self.output.read_bytes()
            for entry in archive.infolist():
                if entry.compress_type == zipfile.ZIP_STORED:
                    # LibreOffice rejects stored entries whose sizes exist only
                    # in data descriptors, even though Python can read them.
                    self.assertFalse(entry.flag_bits & 0x8)
                    sizes = struct.unpack_from('<III', payload, entry.header_offset + 14)
                    self.assertEqual(sizes, (entry.CRC, entry.compress_size, entry.file_size))
            presentation = ET.fromstring(archive.read('ppt/presentation.xml'))
            self.assertEqual(len(presentation.findall('p:sldIdLst/p:sldId', NS)), 2)
            self.assertEqual(presentation.get('autoCompressPictures'), '0')
            images = [name for name in archive.namelist() if name.endswith('.png')]
            self.assertEqual(len(images), 2)
            for name in images:
                self.assertEqual(struct.unpack('>II', archive.read(name)[16:24]), (3840, 2160))
            size = presentation.find('p:sldSz', NS)
            self.assertAlmostEqual(int(size.get('cx')) / int(size.get('cy')), 16 / 9, places=5)
            core = ET.fromstring(archive.read('docProps/core.xml'))
            self.assertEqual(core.find('{http://purl.org/dc/elements/1.1/}title').text, 'A & B <C>')
            for name in archive.namelist():
                if name.endswith(('.xml', '.rels')):
                    ET.fromstring(archive.read(name))

    def notes(self, slide=1):
        """Each notes paragraph as (list marker, level, [(text, style)])."""
        with zipfile.ZipFile(self.output) as archive:
            notes = ET.fromstring(archive.read(f'ppt/notesSlides/notesSlide{slide}.xml'))
            rels = ET.fromstring(archive.read(f'ppt/notesSlides/_rels/notesSlide{slide}.xml.rels'))
        links = {rel.get('Id'): rel.get('Target') for rel in rels}
        body = next(sp for sp in notes.iter('{%s}sp' % NS['p'])
                    if sp.find('.//p:ph', NS).get('type') == 'body')
        paragraphs = []
        for paragraph in body.findall('p:txBody/a:p', NS):
            marker, level = None, None
            properties = paragraph.find('a:pPr', NS)
            if properties is not None:
                level = int(properties.get('lvl'))
                bullet, number = properties.find('a:buChar', NS), properties.find('a:buAutoNum', NS)
                marker = bullet.get('char') if bullet is not None else \
                    (number.get('type'), int(number.get('startAt', '1')))
            runs = []
            for child in paragraph:
                if child.tag == '{%s}br' % NS['a']:
                    runs.append(('\n', ''))
                elif child.tag == '{%s}r' % NS['a']:
                    run = child.find('a:rPr', NS)
                    style = [name for name, attribute in [('bold', 'b'), ('italic', 'i'), ('underline', 'u'),
                                                          ('strike', 'strike')] if run.get(attribute)]
                    if run.get('sz'):
                        style.append('size' + run.get('sz'))
                    if run.find('a:latin', NS) is not None:
                        style.append(run.find('a:latin', NS).get('typeface'))
                    link = run.find('a:hlinkClick', NS)
                    if link is not None:
                        style.append(links[link.get('{%s}id' % NS['r'])])
                    runs.append((child.find('a:t', NS).text or '', ' '.join(style)))
            paragraphs.append((marker, level, runs))
        return paragraphs

    def test_speaker_notes(self):
        self.export('<!-- Open with a story & a pause -->\n\n# Hello\n\n<!-- Then:\n- ask a question -->\n'
                    '\n---\n\n# Quiet\n\n```html\n<!-- code, not a note -->\n```\n')
        with zipfile.ZipFile(self.output) as archive:
            names = archive.namelist()
            self.assertIn('ppt/notesMasters/notesMaster1.xml', names)
            self.assertIn('ppt/notesSlides/notesSlide1.xml', names)
            self.assertNotIn('ppt/notesSlides/notesSlide2.xml', names)
            rels = ET.fromstring(archive.read('ppt/slides/_rels/slide1.xml.rels'))
            self.assertIn('../notesSlides/notesSlide1.xml', [rel.get('Target') for rel in rels])
            rels = ET.fromstring(archive.read('ppt/notesSlides/_rels/notesSlide1.xml.rels'))
            self.assertEqual({rel.get('Target') for rel in rels},
                             {'../notesMasters/notesMaster1.xml', '../slides/slide1.xml'})
            presentation = ET.fromstring(archive.read('ppt/presentation.xml'))
            self.assertIsNotNone(presentation.find('p:notesMasterIdLst/p:notesMasterId', NS))
            types = archive.read('[Content_Types].xml').decode()
            self.assertIn('/ppt/notesSlides/notesSlide1.xml', types)
            self.assertIn('/ppt/notesMasters/notesMaster1.xml', types)
        self.assertEqual(self.notes(), [(None, None, [('Open with a story & a pause', '')]),
                                        (None, None, []),
                                        (None, None, [('Then:', '')]),
                                        ('•', 0, [('ask a question', '')])])
        self.export('# No notes\n')
        with zipfile.ZipFile(self.output) as archive:
            self.assertFalse([name for name in archive.namelist() if 'notes' in name])

    def test_speaker_notes_on_a_later_slide_only(self):
        self.export('# One\n\n---\n\n# Two\n\n<!-- Only here -->\n\n---\n\n# Three\n')
        with zipfile.ZipFile(self.output) as archive:
            names = archive.namelist()
            self.assertEqual([name for name in names if name.startswith('ppt/notesSlides/notesSlide')],
                             ['ppt/notesSlides/notesSlide2.xml'])
            for slide in (1, 3):
                rels = ET.fromstring(archive.read(f'ppt/slides/_rels/slide{slide}.xml.rels'))
                self.assertFalse([rel for rel in rels if 'notes' in rel.get('Target')])
        self.assertEqual(self.notes(2), [(None, None, [('Only here', '')])])

    def test_speaker_notes_markdown_and_html_formatting(self):
        self.export('<!-- A **bold** and <b>bold</b>, *italic* and <em>italic</em>\n'
                    '__under__ _line_ ***both*** <u>under</u> ~~gone~~ <del>gone</del>\n'
                    'Run `hype export` or <code>make</code>\n'
                    '<b>spans\nlines</b> but **not\nthis** -->\n\n# Hello\n')
        self.assertEqual(self.notes(), [
            (None, None, [('A ', ''), ('bold', 'bold'), (' and ', ''), ('bold', 'bold'), (', ', ''),
                          ('italic', 'italic'), (' and ', ''), ('italic', 'italic')]),
            (None, None, [('under', 'underline'), (' ', ''), ('line', 'underline'), (' ', ''),
                          ('both', 'bold italic'), (' ', ''), ('under', 'underline'), (' ', ''),
                          ('gone', 'strike'), (' ', ''), ('gone', 'strike')]),
            (None, None, [('Run ', ''), ('hype export', 'Courier New'), (' or ', ''),
                          ('make', 'Courier New')]),
            (None, None, [('spans', 'bold')]),
            (None, None, [('lines', 'bold'), (' but **not', '')]),
            (None, None, [('this**', '')])])

    def test_speaker_notes_lists_and_headings(self):
        self.export('<!--\n# Opening\n- point\n  - detail with **weight**\n    - deeper\n* star\n+ plus\n'
                    '3. third\n4. fourth\n\n1) paren\n2) paren again\nPlain again\n## Close ##\n-->\n\n# Hi\n')
        self.assertEqual(self.notes(), [
            (None, None, [('Opening', 'bold size1400')]),
            ('•', 0, [('point', '')]),
            ('•', 1, [('detail with ', ''), ('weight', 'bold')]),
            ('•', 2, [('deeper', '')]),
            ('•', 0, [('star', '')]),
            ('•', 0, [('plus', '')]),
            (('arabicPeriod', 3), 0, [('third', '')]),
            (('arabicPeriod', 3), 0, [('fourth', '')]),
            (None, None, []),
            (('arabicParenR', 1), 0, [('paren', '')]),
            (('arabicParenR', 1), 0, [('paren again', '')]),
            (None, None, [('Plain again', '')]),
            (None, None, [('Close', 'bold size1400')])])

    def test_speaker_notes_keep_what_is_not_formatting(self):
        self.export('<!-- 5 * 3 = 15 and 2 * 4, snake_case_name, \\*escaped\\*, **unclosed\n'
                    '<div>tag</div> <script>x</script> &lt;b&gt; &amp; &#x2192; &bogus; A&B\n'
                    'line<br>break, #hashtag, -dash, 1.5 -->\n\n# Hi\n')
        self.assertEqual(self.notes(), [
            (None, None, [('5 * 3 = 15 and 2 * 4, snake_case_name, *escaped*, **unclosed', '')]),
            (None, None, [('<div>tag</div> <script>x</script> <b> & → &bogus; A&B', '')]),
            (None, None, [('line', ''), ('\n', ''), ('break, #hashtag, -dash, 1.5', '')])])

    def test_speaker_notes_links(self):
        self.export('<!-- See [the docs](https://example.com/a?b=1&c=2) and [**mail**](mailto:me@example.com)\n'
                    'Again [docs](https://example.com/a?b=1&c=2), not [this](javascript:alert(1)) '
                    'or [that](file:///etc/passwd) -->\n\n# Hi\n')
        docs, mail = 'https://example.com/a?b=1&c=2', 'mailto:me@example.com'
        self.assertEqual(self.notes(), [
            (None, None, [('See ', ''), ('the docs', docs), (' and ', ''), ('mail', 'bold ' + mail)]),
            (None, None, [('Again ', ''), ('docs', docs), (', not this or that', '')])])
        with zipfile.ZipFile(self.output) as archive:
            rels = ET.fromstring(archive.read('ppt/notesSlides/_rels/notesSlide1.xml.rels'))
        external = [(rel.get('Target'), rel.get('TargetMode')) for rel in rels if rel.get('Type').endswith('/hyperlink')]
        self.assertEqual(external, [(docs, 'External'), (mail, 'External')])

    def test_speaker_notes_code_block(self):
        self.export('<!-- Show this:\n```\n**not bold** <b>x</b>\n  indented\n```\nDone **here** -->\n\n# Hi\n')
        self.assertEqual(self.notes(), [
            (None, None, [('Show this:', '')]),
            (None, None, [('**not bold** <b>x</b>', 'Courier New')]),
            (None, None, [('  indented', 'Courier New')]),
            (None, None, [('Done ', ''), ('here', 'bold')])])

    def test_package_parts_and_relationships_are_consistent(self):
        self.movie()
        self.export('<!-- Intro [link](https://example.com) -->\n\n# One\n\n---\n\n![loop](demo.mp4)\n\n'
                    '---\n\n# Three\n\n<!-- - last -->\n')
        with zipfile.ZipFile(self.output) as archive:
            names = set(archive.namelist())
            types = ET.fromstring(archive.read('[Content_Types].xml'))
            ct = '{http://schemas.openxmlformats.org/package/2006/content-types}'
            defaults = {d.get('Extension').lower() for d in types.iter(ct + 'Default')}
            overrides = {o.get('PartName') for o in types.iter(ct + 'Override')}
            for name in names - {'[Content_Types].xml'}:
                self.assertTrue('/' + name in overrides or name.rsplit('.', 1)[-1].lower() in defaults, name)
            for override in overrides:
                self.assertIn(override[1:], names)
            for rels in [name for name in names if name.endswith('.rels')]:
                base = rels.replace('_rels/', '').removesuffix('.rels')
                folder = os.path.dirname(base)
                for rel in ET.fromstring(archive.read(rels)):
                    if rel.get('TargetMode') == 'External':
                        continue
                    target = os.path.normpath(os.path.join(folder, rel.get('Target'))).lstrip('/')
                    self.assertIn(target, names, f'{rels} -> {rel.get("Target")}')
            for name in names:
                if name.endswith(('.xml', '.rels')):
                    ET.fromstring(archive.read(name))

    def test_repeated_movie_is_embedded_once(self):
        self.movie(codec='mpeg4')
        self.export('![fit](demo.mp4)\n---\n![span muted](demo.mp4)\n')
        with zipfile.ZipFile(self.output) as archive:
            movies = [name for name in archive.namelist() if name.endswith('.mp4')]
            self.assertEqual(len(movies), 1)
            targets = []
            for number in (1, 2):
                rels = ET.fromstring(archive.read(f'ppt/slides/_rels/slide{number}.xml.rels'))
                targets.append(next(rel.get('Target') for rel in rels if rel.get('Type').endswith('/video')))
            self.assertEqual(targets[0], targets[1])

    def test_movie_embedded_with_playback_flags(self):
        self.movie()
        self.export('![loop muted](demo.mp4)\n')
        with zipfile.ZipFile(self.output) as archive:
            movies = [name for name in archive.namelist() if name.endswith('.mp4')]
            self.assertEqual(len(movies), 1)
            self.assertEqual(archive.read(movies[0]), (self.root / 'videos/demo.mp4').read_bytes())
            xml = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
            node = xml.find('.//p:video/p:cMediaNode', NS)
            self.assertIsNotNone(node)
            self.assertEqual(node.get('vol'), '0')
            timing = node.find('p:cTn', NS)
            self.assertEqual(timing.get('repeatCount'), 'indefinite')
            self.assertEqual(timing.find('p:stCondLst/p:cond', NS).get('delay'), '0')
            self.assertNotIn(b'TargetMode="External"', archive.read('ppt/slides/_rels/slide1.xml.rels'))
        original = self.output.read_bytes()
        self.export('![](missing.mp4)', success=False)
        self.assertEqual(self.output.read_bytes(), original)

    def test_manual_playback_and_overlay_order(self):
        self.movie()
        self.export('![span autoplay=false](demo.mp4)\n\n# Headline\n')
        with zipfile.ZipFile(self.output) as archive:
            xml = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
            node = xml.find('.//p:video/p:cMediaNode', NS)
            self.assertEqual(node.get('vol'), '100000')
            timing = node.find('p:cTn', NS)
            self.assertIsNone(timing.get('repeatCount'))
            self.assertEqual(timing.find('p:stCondLst/p:cond', NS).get('delay'), 'indefinite')
            pictures = xml.findall('p:cSld/p:spTree/p:pic', NS)
            self.assertEqual(len(pictures), 3)
            self.assertIsNotNone(pictures[1].find('.//a:videoFile', NS))
            self.assertIsNone(pictures[2].find('.//a:videoFile', NS))

    def test_invalid_video_preserves_existing_export(self):
        self.export('# Original\n')
        original = self.output.read_bytes()
        self.movie(size='240x320')
        result = self.export('![span](demo.mp4)\n', success=False)
        self.assertIn('16:9', result.stderr)
        self.assertEqual(self.output.read_bytes(), original)
        self.export('![fit](demo.mp4)\n')
        original = self.output.read_bytes()
        self.movie(codec='mpeg4')
        source = (self.root / 'videos/demo.mp4').read_bytes()
        self.export('![](demo.mp4)\n')
        self.extracted_movie(size=(320, 180))
        self.assertEqual((self.root / 'videos/demo.mp4').read_bytes(), source)

    def test_webm_converts_video_and_audio_without_changing_original(self):
        source = self.root / 'videos/demo.webm'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:d=0.2',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.2',
                        '-c:v', 'libvpx-vp9', '-c:a', 'libopus', str(source)], check=True)
        original = source.read_bytes()
        self.export('![span](demo.webm)\n')
        movie, _, _ = self.extracted_movie(size=(320, 180), audio=True)
        info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                                                  '-of', 'json', str(movie)]))
        self.assertEqual([s['codec_name'] for s in info['streams']], ['h264', 'aac'])
        self.assertEqual(source.read_bytes(), original)

    def animation(self, extension):
        source = Path(__file__).parent / 'fixtures' / f'animated.{extension}'
        target = self.root / 'images' / f'demo.{extension}'
        shutil.copy2(source, target)
        return target

    def extracted_movie(self, size=(3840, 2160), audio=False):
        with zipfile.ZipFile(self.output) as archive:
            movies = [name for name in archive.namelist() if name.endswith('.mp4')]
            self.assertEqual(len(movies), 1)
            target = self.root / 'converted.mp4'
            target.write_bytes(archive.read(movies[0]))
            xml = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                                '-of', 'json', str(target)], capture_output=True, check=True)
        info = json.loads(probe.stdout)
        self.assertEqual(info['streams'][0]['codec_name'], 'h264')
        self.assertEqual(info['streams'][0]['pix_fmt'], 'yuv420p')
        self.assertEqual((info['streams'][0]['width'], info['streams'][0]['height']), size)
        self.assertEqual(len(info['streams']), 2 if audio else 1)
        return target, xml, info

    def movie_pixel(self, movie, time, x=96, y=54):
        result = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(time), '-i', str(movie),
                                 '-frames:v', '1', '-vf', 'scale=192:108', '-f', 'rawvideo',
                                 '-pix_fmt', 'rgb24', 'pipe:1'], capture_output=True, check=True)
        offset = (y * 192 + x) * 3
        self.assertEqual(len(result.stdout), 192 * 108 * 3)
        return tuple(result.stdout[offset:offset + 3])

    def assert_color(self, actual, expected):
        for channel, value in zip(actual, expected):
            self.assertAlmostEqual(channel, value, delta=12)

    def test_webp_conversion_preserves_motion_alpha_and_timing(self):
        source = self.animation('webp')
        original = source.read_bytes()
        self.export('![fit background=#123456](demo.webp)\n')
        movie, xml, info = self.extracted_movie()
        self.assertAlmostEqual(float(info['format']['duration']), 0.6, delta=0.04)
        self.assert_color(self.movie_pixel(movie, 0.05), (255, 0, 0))
        self.assert_color(self.movie_pixel(movie, 0.25), (0, 0, 255))
        self.assert_color(self.movie_pixel(movie, 0.45), (18, 52, 86))
        timing = xml.find('.//p:video/p:cMediaNode', NS)
        self.assertEqual(timing.get('vol'), '0')
        self.assertEqual(timing.find('p:cTn', NS).get('repeatCount'), 'indefinite')
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(list((self.root / 'videos').iterdir()), [])
        self.assertEqual(set((self.root / 'images').iterdir()), {self.root / 'images/photo.png', source})

    def test_gif_conversion_preserves_fit_layout_finite_loop_and_manual_playback(self):
        self.animation('gif')
        self.export('![fit background=#123456 autoplay=false](demo.gif)\n\n# Caption\n')
        movie, xml, info = self.extracted_movie()
        self.assertAlmostEqual(float(info['format']['duration']), 0.68, delta=0.04)
        self.assert_color(self.movie_pixel(movie, 0.05, 50, 54), (191, 0, 0))
        self.assert_color(self.movie_pixel(movie, 0.25, 50, 54), (0, 0, 191))
        self.assert_color(self.movie_pixel(movie, 0.55, 50, 54), (0, 96, 0))
        self.assert_color(self.movie_pixel(movie, 0.25, 180, 2), (13, 39, 64))
        timing = xml.find('.//p:video/p:cMediaNode/p:cTn', NS)
        self.assertEqual(timing.get('repeatCount'), '3000')
        self.assertEqual(timing.find('p:stCondLst/p:cond', NS).get('delay'), 'indefinite')
        # Arbitrary image aspect ratios can span a slide, unlike existing MP4s.
        self.export('![span loop](demo.gif)\n\n# Overlaid headline\n')
        movie, xml, _ = self.extracted_movie()
        self.assert_color(self.movie_pixel(movie, 0.25, 10, 10), (0, 0, 191))
        self.assertEqual(xml.find('.//p:video/p:cMediaNode/p:cTn', NS).get('repeatCount'), 'indefinite')

    def test_animation_conversion_failure_preserves_export(self):
        self.export('# Original\n')
        original = self.output.read_bytes()
        self.animation('webp')
        # A failing ffmpeg, first on the PATH: HypeX.app also searches Homebrew for a missing one.
        ffmpeg = self.root / 'tools/ffmpeg'
        ffmpeg.unlink()
        ffmpeg.write_text('#!/bin/sh\n/bin/cat >/dev/null\necho "ffmpeg: simulated failure" >&2\nexit 1\n')
        ffmpeg.chmod(0o755)
        result = self.export('![](demo.webp)\n', success=False)
        self.assertIn('Slide 1', result.stderr)
        self.assertIn('ffmpeg', result.stderr)
        self.assertEqual(self.output.read_bytes(), original)
        self.assertEqual(list((self.root / 'videos').iterdir()), [])

    @unittest.skipUnless(os.environ.get('HYPE_OFFICE_TESTS') and OFFICE,
                         'Set HYPE_OFFICE_TESTS=1 to verify with LibreOffice')
    def test_libreoffice_opens_export(self):
        self.movie()
        self.animation('webp')
        self.export('<!-- **Speaker** notes:\n- [link](https://example.com) -->\n\n# Hello\n\n---\n\n![loop muted](demo.mp4)\n\n---\n\n'
                    '![span](demo.mp4)\n\n# Overlaid headline\n\n---\n\n![](demo.webp)\n')
        output = self.root / 'pdf'
        output.mkdir()
        profile = (self.root / 'office-profile').as_uri()
        result = subprocess.run([OFFICE, f'-env:UserInstallation={profile}', '--headless',
                                 '--convert-to', 'pdf', '--outdir', str(output), str(self.output)],
                                env=dict(os.environ, SAL_USE_VCLPLUGIN='svp'),
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        pdf = output / 'talk.pdf'
        self.assertTrue(pdf.exists(), result.stdout + result.stderr)
        self.assertTrue(pdf.read_bytes().startswith(b'%PDF-'))


if __name__ == '__main__':
    unittest.main()
