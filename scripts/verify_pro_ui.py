"""Exercise the production web bundle against a disposable database.

Run with a Python environment containing requirements.txt and playwright; Chrome is required.
"""
import json
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from waitress import create_server
from tests.support import create_test_app as create_app


def run():
    root = Path(__file__).resolve().parents[1]
    evidence = root / 'instance' / 'pro-validation'
    evidence.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as directory:
        app = create_app({'FRONTEND_ENABLED': True}, instance_path=directory)
        server = create_server(app, host='127.0.0.1', port=0)
        Thread(target=server.run, daemon=True).start()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='chrome', headless=True)
            page = browser.new_page(viewport={'width':1440,'height':1000})
            page.set_default_timeout(10000)
            errors=[]
            page.on('pageerror', lambda error: errors.append(str(error)))
            base=f'http://127.0.0.1:{server.effective_port}'
            def nav(path):
                page.locator(f'a[href="{path}"]').first.click()
            def dialog():
                return page.get_by_role('dialog')
            def save():
                dialog().get_by_role('button',name='保 存',exact=True).click()
                expect(dialog()).to_have_count(0)
            def choose(label, text):
                dialog().get_by_label(label,exact=True).click()
                page.locator('.ant-select-dropdown:visible .ant-select-item-option-content').filter(has_text=re.compile('^'+re.escape(text)+'$')).click()
                dialog().get_by_label(label,exact=True).press('Escape')
            def date(label, value):
                control=dialog().get_by_label(label,exact=True)
                control.fill(value)
                control.press('Tab')
            def login(name):
                page.goto(base+'/login')
                page.get_by_label('账号',exact=True).fill(name)
                page.get_by_label('密码',exact=True).fill('Demo12345!')
                page.get_by_role('button',name='登 录',exact=True).click()
                page.get_by_text('项目台账',exact=True).wait_for()
            def logout():
                page.locator('.account-button').click()
                page.get_by_text('退出登录',exact=True).click()
                page.get_by_label('账号',exact=True).wait_for()
            try:
                login('manager')
                expect(page.locator('.ledger-project-row')).to_have_count(4)
                expect(page.locator('.ledger-task-row')).to_have_count(20)
                expect(page.locator('.account-button')).to_contain_text('默认团队')
                page.screenshot(path=str(evidence/'overview.png'),full_page=True)
                nav('/gantt')
                expect(page.locator('.gantt-row')).to_have_count(36)
                expect(page.locator('.gantt-row.task')).to_have_count(20)
                before=page.locator('.gantt-scroll').evaluate('(e)=>e.scrollLeft')
                axis=page.locator('.gantt-axis').bounding_box()
                page.mouse.move(650,axis['y']+40);page.mouse.down();page.mouse.move(850,axis['y']+40,steps=10);page.mouse.up()
                after=page.locator('.gantt-scroll').evaluate('(e)=>e.scrollLeft')
                assert after<before, (before,after)
                width=page.locator('.axis-date').first.evaluate('(e)=>e.getBoundingClientRect().width')
                page.set_viewport_size({'width':1920,'height':1080})
                assert page.locator('.axis-date').first.evaluate('(e)=>e.getBoundingClientRect().width')==width==24
                page.screenshot(path=str(evidence/'gantt.png'),full_page=True)
                page.get_by_role('button',name='全部收起').click()
                expect(page.locator('.gantt-row')).to_have_count(4)
                page.get_by_role('button',name='全部展开').click()
                expect(page.locator('.gantt-row.task')).to_have_count(20)
                print('PASS overview, navigation, Gantt scale / drag / expansion',flush=True)

                nav('/')
                page.get_by_role('button',name=re.compile('新建项目')).click()
                dialog().get_by_label('项目名称',exact=True).fill('浏览器验收项目')
                choose('项目类型','科研')
                date('开始日期','2026-11-01');date('结束日期','2028-12-31')
                choose('项目负责人','沈舟（lead）')
                save()
                row=page.get_by_role('row').filter(has=page.get_by_text('浏览器验收项目',exact=True)).first
                row.get_by_role('button',name='项目详情').click()
                page.get_by_role('tab',name='关键节点 0').click()
                page.get_by_role('button',name='新建节点').click()
                dialog().get_by_label('节点名称').fill('验收节点')
                date('计划日期','2026-12-31');save()
                page.get_by_role('tab',name='关键节点 1').click()
                expect(page.get_by_role('button',name='验收节点',exact=True)).to_be_visible()
                page.get_by_role('button',name='新建任务',exact=True).click()
                dialog().get_by_label('任务名称').fill('验收任务')
                choose('待办人','沈舟（lead）');choose('待办人','周宁（member）')
                expect(dialog().get_by_label('截止日期',exact=True)).to_have_value('2026-12-31')
                expect(dialog().locator('.task-calendar')).to_be_visible()
                expect(dialog().locator('.node-day')).to_have_count(1)
                save()
                page.get_by_role('tab',name='项目任务 1').click()
                row=page.get_by_role('row').filter(has=page.get_by_role('button',name='验收任务',exact=True))
                row.get_by_role('button',name='进行中',exact=True).click()
                dialog().get_by_label('说明').fill('浏览器完成状态更新');save()
                expect(page.get_by_text('浏览器完成状态更新',exact=True)).to_be_visible()
                page.get_by_role('button',name='验收任务',exact=True).click()
                dialog().get_by_label('任务名称').fill('验收任务已编辑');save()
                page.get_by_role('tab',name='关键节点 1').click()
                page.get_by_role('button',name='强制完成',exact=True).click()
                page.locator('.ant-popconfirm').get_by_role('button',name='确 定').click()
                page.get_by_role('tab',name='项目任务 1').click()
                expect(page.get_by_text('随节点强制完成。原说明：浏览器完成状态更新',exact=True)).to_be_visible()
                page.get_by_role('button',name='结 项',exact=True).click()
                page.locator('.ant-popconfirm').get_by_role('button',name='确 定').click()
                expect(page.get_by_text('已结项',exact=True)).to_be_visible()
                print('PASS project / milestone / multi-assignee task / status / edit / force completion / close',flush=True)

                nav('/accounts')
                page.get_by_role('button',name='新建账户').click()
                dialog().get_by_label('登录账号').fill('ui-user')
                dialog().get_by_label('姓名',exact=True).fill('验收人员')
                dialog().get_by_label('初始密码').fill('Demo12345!');save()
                expect(page.get_by_text('验收人员',exact=True)).to_be_visible()
                nav('/team/members')
                page.get_by_role('button',name='添加人员').click()
                choose('用户账户','验收人员（ui-user）');save()
                expect(page.get_by_text('验收人员',exact=True)).to_be_visible()
                nav('/teams')
                page.get_by_role('button',name='新建团队').click()
                dialog().get_by_label('团队名称').fill('浏览器验收组')
                choose('团队主管','林悦（manager）');save()
                page.get_by_role('button',name='关联项目').click()
                choose('项目','浏览器验收项目');save()
                page.locator('.account-button').click()
                page.get_by_role('menuitem',name='浏览器验收组',exact=True).click()
                expect(page.locator('.account-button')).to_contain_text('浏览器验收组')
                expect(page.get_by_text('浏览器验收项目',exact=True)).to_be_visible()
                expect(page.get_by_text('智能检测产线升级',exact=True)).to_have_count(0)
                nav('/gantt')
                expect(page.locator('.gantt-row.project')).to_have_count(1)
                page.reload()
                expect(page.locator('.gantt-row.project')).to_have_count(1)
                print('PASS accounts / team membership / project association / switch / refresh',flush=True)

                logout();login('member')
                expect(page.get_by_role('button',name='新建项目',exact=True)).to_have_count(0)
                nav('/todo')
                page.get_by_role('tab',name='全部',exact=True).click()
                taskrow=page.get_by_role('row').filter(has=page.get_by_text('完成方案评审',exact=True)).first
                taskrow.get_by_role('button',name='进行中',exact=True).click()
                dialog().get_by_label('说明').fill('成员维护任务');save()
                expect(page.get_by_text('成员维护任务',exact=True)).to_be_visible()
                logout();login('director')
                expect(page.get_by_role('button',name='新建项目',exact=True)).to_have_count(0)
                expect(page.get_by_role('button',name='更新进展',exact=True)).to_have_count(0)
                expect(page.get_by_role('button',name='进行中',exact=True)).to_have_count(0)
                page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path=str(evidence/'mobile.png'),full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                assert not errors, errors
                print('PASS member todo / director readonly / mobile / zero JS errors',flush=True)
                (evidence/'result.json').write_text(json.dumps({'passed':True,'javascript_errors':errors,'day_width':width},ensure_ascii=False,indent=2),encoding='utf-8')
            except Exception:
                print('FAIL URL',page.url,'BODY',page.locator('body').inner_text()[-4000:],flush=True)
                page.screenshot(path=str(evidence/'failure.png'),full_page=True)
                raise
            finally:
                browser.close()
                server.close()


if __name__=='__main__':
    run()
