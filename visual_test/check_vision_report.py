"""Browser smoke checks for the generated standalone report."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.report_tools'))
from playwright.sync_api import sync_playwright
OUT=ROOT/'results/vision_study'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1000})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto((OUT/'ProPitch_Vision_실측_실험보고서.html').as_uri(),wait_until='load',timeout=60000)
 page.wait_for_function('document.querySelector("video").readyState >= 2')
 assert page.locator('#clipSelect option').count()==9
 assert page.locator('#modeSelect option').count()==4
 assert page.locator('#gazeTimeline button').count()==50
 assert page.locator('#handTimeline button').count()==50
 assert page.locator('#next-contract').count()==1
 assert page.locator('#recommendation').count()==1
 assert page.locator('#proposed-json').count()==1
 assert page.locator('#api-changes').count()==1
 assert page.locator('#decisions').count()==1
 page.screenshot(path=str(OUT/'report_desktop.png'))
 page.evaluate("scrollTo(0,document.querySelector('#viewer').offsetTop-20)")
 page.screenshot(path=str(OUT/'report_viewer.png'))
 page.select_option('#clipSelect','erik_10')
 parsed=json.loads(page.locator('#jsonView').text_content())
 assert parsed['vision']['handStillSeconds'] is None
 with page.expect_download() as info:page.click('#downloadJson')
 download=info.value;download.save_as(str(OUT/'browser_download_check.json'))
 assert json.loads((OUT/'browser_download_check.json').read_text())==parsed
 page.select_option('#modeSelect','open')
 page.wait_for_function('document.querySelector("video").readyState>=2')
 page.locator('#gazeTimeline button').nth(25).click()
 page.wait_for_function('Math.abs(document.querySelector("video").currentTime - 5)<.1')
 play=page.evaluate('async()=>{const v=document.querySelector("video");v.muted=true;await v.play();return {duration:v.duration,width:v.videoWidth,height:v.videoHeight}}')
 assert 9.9<=play['duration']<=10.1 and play['width']==960
 page.evaluate('document.querySelector("video").pause()')
 desktop_overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
 page.evaluate("scrollTo(0,document.querySelector('#next-contract').offsetTop-20)")
 page.screenshot(path=str(OUT/'report_appendix.png'))
 page.set_viewport_size({'width':390,'height':844})
 page.evaluate('scrollTo(0,0)')
 page.screenshot(path=str(OUT/'report_mobile.png'))
 mobile_overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
 assert not desktop_overflow and not mobile_overflow
 assert not errors,errors
 (OUT/'browser_validation.json').write_text(json.dumps(dict(result='PASS',javascriptErrors=errors,clips=9,modes=4,timelineCells=100,jsonDownloadValidated=True,videoPlayback=play,desktopOverflow=desktop_overflow,mobileOverflow=mobile_overflow),indent=2))
 browser.close()
print('Browser checks PASS')
