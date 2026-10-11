# OA 本地提醒

采集公司文件或通知公告，保存到本机 SQLite 未读队列。不发送微信或企业微信消息。关闭窗口不会清除未读记录，只有“标为已读”会更新阅读状态。

## 安装和启动

需要 Python 3.10 及以上、Chrome 和 Selenium。Tkinter 使用 Python 自带版本；Linux 可能需要额外安装系统的 python3-tk 包。

```sh
python -m venv .venv
python -m pip install -r requirements.txt
python main2.py
```

安装依赖前先激活 `.venv`。Windows 可运行 `oa.bat`；任务计划程序应使用所选虚拟环境中的 Python。脚本每次抓取一次，不自动创建定时任务。

`main2.py` 抓取公司文件；`main4.py` 抓取通知公告；`main3.py` 保留原有部门关键词过滤。`main.py` 兼容入口也仅作本地提醒。`wx.py`、`wechat.py` 已禁用外部发送。

## 本机配置

通过环境变量设置配置，不要把账号密码写入源码、提交 Git 或发到聊天中：

- `OA_LOGIN_URL`：经确认的完整登录地址，默认只接受 HTTPS。代码不假定原服务已支持 HTTPS。
- `OA_USERNAME`、`OA_PASSWORD`：本机凭据。
- `OA_NEXT_SELECTOR`：列表中“下一页”控件的 CSS 选择器。末页必须能通过 disabled、aria-disabled 或 disabled 类名识别。
- `OA_SINGLE_PAGE=1`：仅在确认列表确实不分页时使用。不能用它绕过未知分页结构。
- `OA_ROW_SELECTOR`：默认 `.lui_listview_rowtable_summary_content_box`。
- `OA_LINK_SELECTOR`：默认 `a[href]`，每条记录必须唯一匹配带标题的详情链接。先查摘要元素，再查其所在表格行；不解析任意 onclick JavaScript。
- `OA_STATE_DIR`：可选，指定本机状态目录。
- `OA_ALLOW_INSECURE_HTTP=1`：只有明确接受明文传输风险时才能使用旧 HTTP 服务；不要在不可信网络中启用。

现有门户入口仍沿用原代码的第二个菜单、公司文件第一个更多入口和通知公告第三个更多入口，并增加了显式等待。真实系统未在本轮登录验证，正式使用前须核对这三个入口、详情链接和分页选择器。不能识别列表时会停止抓取并保留旧记录。

## 进度和恢复

Windows 默认写入 `%LOCALAPPDATA%/OAReader`，其他平台写入 `~/.local/share/oa-reader`。`monitor.sqlite3` 保存公告历史、未读状态和最后一次成功扫描；`monitor.log` 记录运行结果，不记录密码或公告正文。数据库包含内部公告，请保护本机权限。

不同 OA 服务或账号必须设置不同的 `OA_STATE_DIR`，不要共用状态目录。自定义目录的访问权限由用户管理。

旧 `info.txt`、`info4.txt` 保留不动。它们没有稳定公告 ID，不能安全推断哪些具体公告已读；新版首次完整抓取会将所有取得的公告列为未读，用户可多选后标记。

```sh
python main2.py --history
python main4.py --history
python main2.py --no-ui
python -m unittest discover -s tests -v
```

`--history` 只读取本地数据库，不联网。`--no-ui` 不弹窗，但所有新记录仍保留为未读。抓取非空完整列表后才提交一个数据库事务；空列表、失败分页、重复页、冲突记录、超过分页上限都不更新进度。单实例锁阻止多个提醒窗口并发运行。

修改过标题或摘要的同一详情链接会生成新未读版本。系统只比较列表摘要，不声称检测原文正文或附件的全部变化。所有运行均错过、且随后已从服务器删除的公告也无法追回。

## 验证边界

本地回归测试覆盖去重、置顶、同名公告、分页、空抓取、事务回滚、状态恢复和禁用微信。浏览器适配可以用合成页面测试；实际 OA 的认证、栏目身份及分页结构仍需在授权环境中验收。
