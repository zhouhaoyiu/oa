# import difflib
import os
import time

import ntchat
from selenium import webdriver
from selenium.webdriver.common.by import By

ntchat.set_wechat_exe_path (wechat_version='3.6.0.18')
OA_LOGIN_URL = os.environ.get("OA_LOGIN_URL", "http://oa.tywatersupply.com:9500/login.jsp")
OA_USERNAME = os.environ["OA_USERNAME"]
OA_PASSWORD = os.environ["OA_PASSWORD"]

options = webdriver.ChromeOptions ()
# 不显示ChromeDriver的控制台窗口

options.add_argument ('headless')
options.add_experimental_option ("excludeSwitches" , ["enable-logging"])
driver = webdriver.Chrome (options=options)
driver.minimize_window ()

driver.get (OA_LOGIN_URL)
username = driver.find_element (
    by=By.CLASS_NAME , value="lui_login_input_username")
password = driver.find_element (
    by=By.CLASS_NAME , value="lui_login_input_password")
login_button = driver.find_element (
    by=By.CLASS_NAME , value="lui_login_button_div_c")
username.send_keys (OA_USERNAME)
password.send_keys (OA_PASSWORD)

login_button.click ()

xxmhs = driver.find_elements (
    by=By.CLASS_NAME , value="lui_portal_header_menu_item_c")
xxmhs[1].click ()
time.sleep (3)
mores = driver.find_elements (
    by=By.CLASS_NAME , value="lui_portlet_operation_more")
mores[0].click ()

new_window = driver.window_handles[-1]
driver.switch_to.window (new_window)
driver.minimize_window ()
time.sleep (10)
infos = driver.find_elements (
    by=By.CLASS_NAME , value="lui_listview_rowtable_summary_content_box")
# for info in infos:
#     print (info.text)

last_first_message = ""

if os.path.exists ("info.txt"):

    with open ("info.txt" , "r") as f:
        old_infos = f.readlines ()

    if len (old_infos) == 0:
        with open ("info.txt" , "w") as f:
            for info in infos:
                f.write (info.text.split ("点击率")[0] + '\r')

    else:
        last_first_message = old_infos[1].strip ()
        last_first_message_index = 0
        new_message = []
        wechat = ""
        for i in range (len (infos)):
            # print (i)
            if (infos[i].text.split ("点击率")[0].splitlines ()[0].strip () != old_infos[0 + i * 3].strip ()) | (
                    infos[i].text.split ("点击率")[0].splitlines ()[1].strip () != old_infos[1 + i * 3].strip ()) | (
                    infos[i].text.split ("点击率")[0].splitlines ()[2].strip () != old_infos[2 + i * 3].strip ()):
                print ("有新消息")
                break
        for j in range (len (infos)):
            if infos[j].text.split ("点击率")[0].splitlines ()[1].strip () == last_first_message:
                if j == 0:
                    last_first_message_index = j
                    break
                print ("本次更新了" + str (j) + "条消息")
                last_first_message_index = j
                break
        if last_first_message_index > 0:
            wechat = ntchat.WeChat ()
            wechat.open (smart=True)
            wechat.wait_login ()
        for k in range (last_first_message_index):
            print ("更新消息" + ":   " + infos[k].text)
            # 将新消息写入new_message
            new_message.append ("更新消息" + str (k + 1) + ":   " + infos[k].text)
            wechat.send_text (to_wxid="shiqinhui0404", content="更新消息" + ":   " + infos[k].text)
            # wechat.send_text (to_wxid="zhouhaoyu2989", content="更新消息" + ":   " + infos[k].text)
        ntchat.exit_ ()
        with open ("info.txt" , "w") as f:
            # 将原来的信息清空，重新写入
            f.truncate ()

            for info in infos:
                # print(info)
                f.write (info.text.split ("点击率")[0] + '\r')
else:
    with open ("info.txt" , "w") as f:
        for info in infos:
            f.write (info.text.split ("点击率")[0] + '\r')

# 关闭页面
driver.close ()
# 关闭浏览器
driver.quit ()

# def send2wechat(AgentId , Secret , CompanyId , message):
#     """
#     :param AgentId: 应用ID
#     :param Secret: 应用Secret
#     :param CompanyId: 企业ID
#     """
#     # 通行密钥
#     ACCESS_TOKEN = None
#     # 如果本地保存的有通行密钥且时间不超过两小时，就用本地的通行密钥
#     if os.path.exists ('ACCESS_TOKEN.txt'):
#         txt_last_edit_time = os.stat ('ACCESS_TOKEN.txt').st_mtime
#         now_time = time.time ()
#         print ('ACCESS_TOKEN_time:' , int (now_time - txt_last_edit_time))
#         if now_time - txt_last_edit_time < 7200:  # 官方说通行密钥2小时刷新
#             with open ('ACCESS_TOKEN.txt' , 'r') as f:
#                 ACCESS_TOKEN = f.read ()
#                 # print(ACCESS_TOKEN)
#     # 如果不存在本地通行密钥，通过企业ID和应用Secret获取
#     if not ACCESS_TOKEN:
#         r = requests.post (
#             f'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CompanyId}&corpsecret={Secret}').json ()
#         ACCESS_TOKEN = r["access_token"]
#         # print(ACCESS_TOKEN)
#         # 保存通行密钥到本地ACCESS_TOKEN.txt
#         with open ('ACCESS_TOKEN.txt' , 'w' , encoding='utf-8') as f:
#             f.write (ACCESS_TOKEN)
#     # 要发送的信息格式
#     data = {
#         "touser": "@all" ,
#         "msgtype": "text" ,
#         "agentid": f"{AgentId}" ,
#         "text": {"content": f"{message}"}
#     }
#     # 字典转成json，不然会报错
#     data = json.dumps (data)
#     # 发送消息
#     r = requests.post (f'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={ACCESS_TOKEN}' , data=data)
#     print (r.json ())
