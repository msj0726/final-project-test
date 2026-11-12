import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.report_tools'))
from playwright.sync_api import sync_playwright
OUT=ROOT/'results/vision_decision_study'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(next(OUT.glob('*.html')).as_uri(),wait_until='load')
 page.wait_for_function('document.querySelector("video").readyState>=2')
 assert page.locator('#clip option').count()==9
 assert page.locator('#gaze button').count()==50
 assert page.locator('#walkthroughJson').count()==1
 assert json.loads(page.locator('#walkthroughJson').text_content())==json.loads((OUT/'json'/'jack_65.json').read_text())
 page.screenshot(path=str(OUT/'desktop.png'))
 page.evaluate('scrollTo(0,document.querySelector("#walkthroughJson").offsetTop-650)')
 page.screenshot(path=str(OUT/'walkthrough.png'))
 page.evaluate('scrollTo(0,document.querySelector("#viewer").offsetTop-20)')
 page.screenshot(path=str(OUT/'viewer.png'))
 page.select_option('#clip','erik_10')
 actual=json.loads(page.locator('#json').text_content())
 assert actual['vision']['handStillSeconds'] is None
 assert actual['vision']['unobservableIntervalsStatus']=='GENERATED'
 assert actual['contextJudgments'][0]['verdict'] is None
 assert actual['isScoringReady'] is False
 with page.expect_download() as pending:page.click('#saveJson')
 pending.value.save_as(str(OUT/'browser_download.json'))
 assert json.loads((OUT/'browser_download.json').read_text())==actual
 page.locator('#gaze button').nth(25).click()
 page.wait_for_function('Math.abs(document.querySelector("video").currentTime-5)<.1')
 video=page.evaluate('async()=>{const v=document.querySelector("video");v.muted=true;await v.play();return {width:v.videoWidth,duration:v.duration}}')
 assert video['width']==960 and 9.9<=video['duration']<=10.1
 page.evaluate('document.querySelector("video").pause()')
 assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
 page.set_viewport_size({'width':390,'height':844});page.evaluate('scrollTo(0,0)')
 page.screenshot(path=str(OUT/'mobile.png'))
 assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
 assert not errors
 (OUT/'browser_validation.json').write_text(json.dumps(dict(result='PASS',javascriptErrors=errors,jsonDownload=True,videoPlayback=video,desktopAndMobileNoOverflow=True),indent=2))
 browser.close()
print('Browser checks PASS')
