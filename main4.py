# import difflib
import os
import time
# from tkinter import *
from tkinter import Button , Message , Tk

from selenium import webdriver
from selenium.webdriver.common.by import By

options = webdriver.ChromeOptions ()

bmArr = ["企业发展策划部" , "调度运行部" , "生产技术部" , "基建部" , "安全保卫部" , "营销管理部"]
# options.add_argument ('headless')
# options.add_experimental_option ("excludeSwitches" , ["enable-logging"])
driver = webdriver.Chrome (options=options)
# driver.minimize_window ()

driver.get ("http://oa.tywatersupply.com:9500/login.jsp")
username = driver.find_element (
    by=By.CLASS_NAME , value="lui_login_input_username")
password = driver.find_element (
    by=By.CLASS_NAME , value="lui_login_input_password")
login_button = driver.find_element (
    by=By.CLASS_NAME , value="lui_login_button_div_c")
username.send_keys ("***REMOVED_OA_USERNAME***")
password.send_keys ("***REMOVED_PASSWORD***")

login_button.click ()

xxmhs = driver.find_elements (
    by=By.CLASS_NAME , value="lui_portal_header_menu_item_c")
xxmhs[1].click ()
time.sleep (3)
mores = driver.find_elements (
    by=By.CLASS_NAME , value="lui_portlet_operation_more")
mores[2].click ()

new_window = driver.window_handles[-1]
driver.switch_to.window (new_window)
driver.minimize_window ()
time.sleep (10)
infos = driver.find_elements (
    by=By.CLASS_NAME , value="lui_listview_rowtable_summary_content_box")
# for info in infos:
#     print (info.text)

last_first_message = ""

if os.path.exists ("info4.txt"):

    with open ("info4.txt" , "r") as f:
        old_infos = f.readlines ()

    if len (old_infos) == 0:
        with open ("info4.txt" , "w") as f:
            for info in infos:
                f.write (info.text.split ("点击率")[0] + '\r')

    else:
        last_first_message = old_infos[1].strip ()
        last_first_message_index = 0
        new_message = ""

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

        for k in range (last_first_message_index):
            print ("更新消息" + '\r' + infos[k].text)
            # 将新消息写入new_message
            new_message += "更新消息" + ":   " + infos[k].text + '\r'
            # for bm in bmArr:
            #     if bm in infos[k].text:
            #         new_message += "更新消息" + ":   " + infos[k].text + '\r'
        if len (new_message) > 0:
            root = Tk ()
            root.title ("通知公告")
            # root.geometry (str (len (new_message) * 5) +
            #                "x" + str (len (new_message)))
            # 窗口1900*1000
            # root.geometry ("1900x1000")·1

            Message (root , text=new_message , width=str (
                len (new_message) * 4)).pack ()
            # 去查看按钮点击打开一个新的Chrome窗口,并且执行open_new_window函数
            # Button (root , text="去查看" , command=open_new_window).pack ()
            # 置于顶部
            root.attributes ("-topmost" , True)
            root.mainloop ()

        with open ("info4.txt" , "w") as f:
            # 将原来的信息清空，重新写入
            f.truncate ()

            for info in infos:
                # print(info)
                f.write (info.text.split ("点击率")[0] + '\r')
else:
    with open ("info4.txt" , "w") as f:
        for info in infos:
            f.write (info.text.split ("点击率")[0] + '\r')

# 关闭页面
driver.close ()
# 关闭浏览器
driver.quit ()

