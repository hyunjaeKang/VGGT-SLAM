from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
from collections import Counter
class Page(HTMLParser):
 def __init__(self):super().__init__();self.ids=[];self.links=[];self.external=[];self.script=False;self.scripts=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id'in a:self.ids.append(a['id'])
  if tag=='a'and 'href'in a:self.links.append(a['href'])
  if tag in ('script','link','img','iframe') and (a.get('src','').startswith('http') or a.get('href','').startswith('http')):self.external.append(a)
  if tag=='script':self.script=True
 def handle_endtag(self,tag):
  if tag=='script':self.script=False
 def handle_data(self,data):
  if self.script:self.scripts.append(data)
p=Path('26.11.09.VGGT_SLAM.Plan.html');page=Page();page.feed(p.read_text());errors=[]
for ident,n in Counter(page.ids).items():
 if n>1:errors.append('duplicate '+ident)
for link in page.links:
 u=urlsplit(link)
 if u.scheme or u.netloc:continue
 if u.path and not (p.parent/unquote(u.path)).exists():errors.append('missing file '+link)
 if not u.path and u.fragment not in page.ids:errors.append('missing anchor '+link)
assert not errors,errors
assert len([i for i in page.ids if len(i)==3 and i.startswith('S')])==41
assert not page.external,page.external
Path('/private/tmp/vggt_plan_check.js').write_text('\n'.join(page.scripts))
print('HTML valid: unique IDs / all local links and anchors / 41 source rows / no external runtime dependencies')
# Verify new continuation links without changing historical experiment links.
required=['docs/SESSION_HANDOFF.md','docs/CURRENT_STATUS.md','26.11.09.VGGT_SLAM.Plan.html']
for f in required:assert Path(f).stat().st_size>1000
for f in ['AGENTS.md','README.md','temp_VGGT_SLAM_Plans.26.10.30.md','temp_VGGT_SLAM_Prompt.26.10.30.md']:
 assert 'SESSION_HANDOFF.md'in Path(f).read_text(),f
print('Resume entry points present')
