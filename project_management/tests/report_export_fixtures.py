HTML = b"""<!doctype html><html lang="en"><body>
<h1>Sample standup</h1>
<p>Manual &lt;script&gt; &amp; literal | text.</p>
<ul><li>AR: @Alice review the validation result.</li></ul>
<table><thead><tr><th>Ticket</th><th>Updates</th></tr></thead><tbody>
<tr><td><a href="https://tracker.example.test/browse/ALPHA-1">ALPHA-1</a></td>
<td><p><strong>ww44.1(Fixed):</strong> <span style="color:#aa0000;">Initial update.</span></p>
<p>ww44.2(Fixed): Human follow-up.</p></td></tr>
<tr><td>ALPHA-2</td><td>=HYPERLINK("https://outside.example.test","run")</td></tr>
<tr><td>15000000003</td><td>ww44.2(In Analysis): Confirm the owner.</td></tr>
</tbody></table></body></html>"""


def html_cell(text):
    return f'<!doctype html><html lang="en"><body><table><tr><td>{text}</td></tr></table></body></html>'.encode()
