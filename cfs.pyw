"""Windows 10 2004+ / Windows 11 的 WebView2 窗口示例。

安装：py -m pip install "pywebview==6.2.1"
运行：双击本文件，或执行 pythonw cfs.pyw
需要 Microsoft Edge WebView2 Runtime；不需要额外安装 Chrome。
仅对本进程与窗口控件请求禁用 IME，不修改系统输入法配置；仍可粘贴中文。
WebView2 的独立进程与第三方输入法是否遵循设置，需要在实际环境验证。
捕获排除不是安全隔离，必须用实际的截图/录屏软件验证。
"""

import ctypes
from ctypes import wintypes
import sys
from urllib.parse import urlsplit


WDA_EXCLUDEFROMCAPTURE = 0x00000011
TITLE = "WebView2 捕获排除示例"
START_PAGE = """<!doctype html>
<html lang="zh-CN"><meta charset="utf-8">
<title>开始浏览</title>
<style>
body { max-width: 680px; margin: 72px auto; padding: 24px;
       font: 17px/1.8 'Microsoft YaHei UI', sans-serif; color: #253044; }
h1 { font-size: 28px; }
</style>
<h1>内嵌 Chromium 网页窗口</h1>
<p>等待标题栏显示“已设置捕获排除”，然后在上方输入完整的 HTTP / HTTPS 网址。</p>
<p>窗口不显示任务栏图标。点击右上角关闭按钮退出。</p>
<p>已对本进程和窗口控件请求禁用系统输入法；仍可输入英文、粘贴中文。
请分别测试地址栏与网页输入框。WebView2 独立进程及第三方输入法可能不遵循设置；
若仍出现候选词窗口，请勿在录屏时使用它。</p>
<p><strong>请先用你的录屏软件测试。</strong>系统接受设置不代表所有捕获方式都受限。
网页之外的系统对话框、外部应用不在保护范围内。</p>
<p>新窗口链接会尝试在当前窗口打开；部分弹窗登录流程可能不兼容。
此示例不提供下载功能，也不继承 Chrome 的登录状态。</p>
</html>"""


def validate_url(text):
    url = text.strip()
    if any(char.isspace() for char in url):
        raise ValueError("网址不能含空白字符，请输入完整的 HTTP / HTTPS 网址。")
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("请输入以 http:// 或 https:// 开头的完整网址。")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("请在网页中登录，不要在网址里填写账号或密码。")
    # 访问 port 属性，让 urllib 检查端口格式及范围。
    parsed.port
    return url


def set_capture_exclusion(user32, hwnd):
    if not user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
        raise ctypes.WinError(ctypes.get_last_error())
    actual = wintypes.DWORD()
    if not user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(actual)):
        raise ctypes.WinError(ctypes.get_last_error())
    if actual.value != WDA_EXCLUDEFROMCAPTURE:
        raise RuntimeError("系统返回的窗口捕获属性与请求不一致。")


def set_tool_window_style(user32, hwnd):
    # 不设置 Form.ShowInTaskbar：它会重建 HWND，干扰正在初始化的 WebView2。
    # GWL_EXSTYLE：添加 TOOLWINDOW、移除 APPWINDOW；GWL_STYLE：移除最小化按钮。
    for index, remove_bits, add_bits in ((-20, 0x00040000, 0x00000080),
                                         (-16, 0x00020000, 0)):
        ctypes.set_last_error(0)
        style = user32.GetWindowLongW(hwnd, index)
        error = ctypes.get_last_error()
        if style == 0 and error:
            raise ctypes.WinError(error)
        updated = (style & ~remove_bits) | add_bits
        if updated != style:
            ctypes.set_last_error(0)
            previous = user32.SetWindowLongW(hwnd, index, updated)
            error = ctypes.get_last_error()
            if previous == 0 and error:
                raise ctypes.WinError(error)
    # 刷新非客户区，但不移动、缩放、激活或重建窗口。
    if not user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0037):
        raise ctypes.WinError(ctypes.get_last_error())


def show_error(text):
    if sys.platform != "win32":
        print(text, file=sys.stderr)
        return
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.MessageBoxW.argtypes = [
        wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT
    ]
    user32.MessageBoxW.restype = ctypes.c_int
    user32.MessageBoxW(None, text, TITLE, 0x10)


def main():
    if sys.platform != "win32":
        raise RuntimeError("此示例只能在 Windows 上运行。")
    if sys.getwindowsversion().build < 19041:
        raise RuntimeError("需要 Windows 10 2004（内部版本 19041）或更高版本。")

    # 必须早于 GUI 导入和首个顶层窗口创建；-1 只作用于当前进程的线程。
    imm32 = ctypes.WinDLL("imm32", use_last_error=True)
    imm32.ImmDisableIME.argtypes = [wintypes.DWORD]
    imm32.ImmDisableIME.restype = wintypes.BOOL
    if not imm32.ImmDisableIME(0xFFFFFFFF):
        raise RuntimeError("Windows 拒绝禁用本进程的输入法，窗口未启动。")

    try:
        import webview
    except ImportError as error:
        raise RuntimeError(
            '请先安装依赖：\npy -m pip install "pywebview==6.2.1"'
        ) from error

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    user32.GetWindowDisplayAffinity.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
    ]
    user32.GetWindowDisplayAffinity.restype = wintypes.BOOL
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    user32.SetWindowLongW.restype = wintypes.LONG
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL

    # 不把新窗口链接交给外部浏览器，也不向网页暴露 Python js_api。
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    webview.settings["ALLOW_DOWNLOADS"] = False
    webview.settings["ALLOW_FILE_URLS"] = False
    window = webview.create_window(
        TITLE,
        html=START_PAGE,
        width=1080,
        height=760,
        min_size=(720, 480),
        text_select=True,
    )

    def before_show(window):
        # 此同步事件在 WinForms UI 线程、窗口首次显示之前执行。
        from System.Drawing import ContentAlignment
        from System.Windows.Forms import (
            Button, DockStyle, ImeMode, Keys, Label, Padding, Panel, TextBox,
        )

        form = window.native
        form.ImeMode = ImeMode.Disable
        if webview.renderer != "edgechromium":
            form.webview.Visible = False
            form.Text = "未启用 WebView2，请安装 Microsoft Edge WebView2 Runtime 后重启"
            show_error("未找到可用的 WebView2 渲染器；不会使用旧版 IE 内核加载网页。")
            return

        browser = form.webview
        # 设置宿主控件，不通过重建 HWND 或修改系统键盘布局实现。
        browser.ImeMode = ImeMode.Disable
        toolbar = Panel()
        toolbar.Dock = DockStyle.Top
        toolbar.Padding = Padding(10, 8, 10, 8)
        toolbar.Enabled = False
        address = TextBox()
        address.ImeMode = ImeMode.Disable
        address.Dock = DockStyle.Fill
        address.ReadOnly = False
        address.TabStop = True
        address.TabIndex = 0
        toolbar.Height = address.PreferredHeight + 16
        label = Label()
        label.Text = "网址"
        label.Dock = DockStyle.Left
        label.Width = 44
        label.TextAlign = ContentAlignment.MiddleLeft
        open_button = Button()
        open_button.Text = "打开"
        open_button.Dock = DockStyle.Right
        open_button.Width = 76
        open_button.TabIndex = 1
        toolbar.Controls.Add(address)
        toolbar.Controls.Add(label)
        toolbar.Controls.Add(open_button)
        form.Controls.Add(toolbar)
        # 先布局地址栏，再让浏览器填充剩余空间，避免覆盖输入框。
        browser.BringToFront()
        state = {"protected": False, "ready": False, "init_error": None}

        def focus_address(sender=None, args=None):
            if state["protected"]:
                address.Focus()

        def protect(sender=None, args=None):
            try:
                hwnd = form.Handle.ToInt64()
                set_tool_window_style(user32, hwnd)
                set_capture_exclusion(user32, hwnd)
            except Exception as error:
                state["protected"] = False
                toolbar.Enabled = False
                browser.Visible = False
                form.Text = f"窗口保护设置失败，网页已隐藏：{error}"
                return
            state["protected"] = True
            browser.Visible = True
            # 允许先输入网址；只有真正导航时才检查 WebView2 是否就绪。
            toolbar.Enabled = True
            status = "就绪" if state["ready"] else "初始化中"
            form.Text = f"ctf-fuck-screenrecorder — WebView2 {status}"

        def navigate(sender=None, args=None):
            if not state["protected"]:
                return
            try:
                url = validate_url(str(address.Text))
                if browser.CoreWebView2 is None:
                    if state["init_error"]:
                        form.Text = f"WebView2 初始化失败：{state['init_error']}"
                    else:
                        form.Text = "浏览器正在初始化，网址已保留，请稍后再点击打开"
                    return
                if not webview_ready():
                    return
                browser.CoreWebView2.Navigate(url)
                browser.Focus()
            except Exception as error:
                form.Text = f"无法打开网址：{error}"

        def key_down(sender, args):
            if args.KeyCode == Keys.Enter:
                args.SuppressKeyPress = True
                navigate()

        def navigation_starting(sender, args):
            uri = str(args.Uri)
            if uri == "about:blank":
                return
            try:
                validate_url(uri)
                if not state["protected"]:
                    raise RuntimeError("尚未成功设置捕获排除。")
            except (ValueError, RuntimeError) as error:
                args.Cancel = True
                form.Text = f"已阻止导航：{error}"

        def source_changed(sender, args):
            uri = str(browser.Source)
            if not address.Focused and uri.startswith(("http://", "https://")):
                address.Text = uri

        def webview_ready(sender=None, args=None):
            if args is not None and not args.IsSuccess:
                state["init_error"] = str(args.InitializationException)
                form.Text = f"WebView2 初始化失败：{state['init_error']}"
                return False
            core = browser.CoreWebView2
            if core is None:
                return False
            try:
                # JS 对话框另属原生窗口，示例禁用它们；不影响网页自身的 HTML 弹层。
                core.Settings.AreDefaultScriptDialogsEnabled = False
                if not state["ready"]:
                    core.SourceChanged += source_changed
                    state["ready"] = True
            except Exception as error:
                form.Text = f"WebView2 配置失败：{error}"
                return False
            state["init_error"] = None
            if state["protected"]:
                form.Text = "ctf-fuck-screenrecorder — WebView2 就绪"
            return True

        # pywebview 的 Shown 处理会先聚焦网页；之后再将焦点交给地址栏。
        form.Shown += focus_address
        # WinForms 若重建顶层 HWND，重新设置并核验捕获策略。
        form.HandleCreated += protect
        address.KeyDown += key_down
        open_button.Click += navigate
        browser.NavigationStarting += navigation_starting
        browser.CoreWebView2InitializationCompleted += webview_ready
        if browser.CoreWebView2 is not None:
            webview_ready()
        protect()

    def configure_window(window):
        try:
            before_show(window)
        except Exception as error:
            # pywebview 会记录并吞掉事件异常；显式隐藏内容，避免带错继续浏览。
            if window.native is not None:
                window.native.webview.Visible = False
                window.native.Text = "窗口初始化失败，请关闭后检查依赖"
            show_error(f"窗口初始化失败：\n{error}")

    window.events.before_show += configure_window
    webview.start(gui="edgechromium", debug=False, private_mode=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        show_error(
            f"启动失败：\n{error}\n\n"
            '依赖安装：py -m pip install "pywebview==6.2.1"\n'
            "还需要 Microsoft Edge WebView2 Runtime。"
        )
