from pathlib import Path
import json
import subprocess
import zipfile

root=Path(__file__).parent
out=root/'deliverables'
out.mkdir(exist_ok=True,parents=True)
results=[]
for script in ['tests/core.test.js','tests/interface.test.js']:
    run=subprocess.run(['node',str(root/script)],capture_output=True,text=True,check=True)
    results.append(json.loads(run.stdout))
validation={'generated_at':'2026-11-04','model_executed':False,'visual_browser_tested':False,'tests':results}
(root/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2))
page=(root/'dist/index.html').read_text()
for filename in ['core.js','app.js']:
    script=(root/'dist'/filename).read_text().replace('</script','<\\/script')
    page=page.replace(f'<script src="{filename}"></script>',f'<script>\n{script}\n</script>')
page=page.replace('href="plan.html"','href="TerraScene_Development_Plan_2026-11-04.html"')
standalone=out/'TerraScene_Demo_UI_2026-11-04.html'
standalone.write_text(page)
plan=(root/'dist/plan.html').read_text().replace('href="index.html"','href="TerraScene_Demo_UI_2026-11-04.html"')
(out/'TerraScene_Development_Plan_2026-11-04.html').write_text(plan)
archive=out/'TerraScene_Demo_Package_2026-11-04.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for name in ['README.md','build_plan.py','package_deliverables.py','validation.json']:
        z.write(root/name,root.name+'/'+name)
    for folder in ['dist','tests']:
        for p in sorted((root/folder).rglob('*')):
            if p.is_file():z.write(p,root.name+'/'+str(p.relative_to(root)))
    z.write(standalone,root.name+'/standalone/'+standalone.name)
    z.write(out/'TerraScene_Development_Plan_2026-11-04.html',root.name+'/standalone/TerraScene_Development_Plan_2026-11-04.html')
for p in out.iterdir():
    print(p.name,p.stat().st_size)
