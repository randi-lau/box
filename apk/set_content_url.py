#!/usr/bin/env python3
# 用法:
#   python apk/set_content_url.py <user/repo>
#   python apk/set_content_url.py <完整基础URL>
# 例:
#   python apk/set_content_url.py alice/study-apps
#   python apk/set_content_url.py https://cdn.jsdelivr.net/gh/alice/study-apps@main
#   python apk/set_content_url.py https://my-bucket.oss-cn-beijing.aliyuncs.com/study
#
# 作用：把内容 JSON 的真实网址（合并后统一为 content.json，manifest 或单文件均可）一次性写进 6 个 HTML 的 CONTENT_URL 和 2 个安卓 strings.xml 的 content_url。
import sys, io, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 仓库根目录


def build_base(arg):
    arg = arg.strip().rstrip('/')
    if arg.endswith('.json'):
        arg = arg[: arg.rfind('/')]            # 允许直接传完整 json 网址
    if re.match(r'^[\w.-]+/[\w.-]+$', arg):   # user/repo -> jsDelivr
        return 'https://cdn.jsdelivr.net/gh/' + arg + '@main'
    if arg.startswith('http://') or arg.startswith('https://'):
        return arg
    print('无法识别参数:', arg)
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    base = build_base(sys.argv[1]).rstrip('/')
    url = base + '/content.json'   # 合并为单一中性应用后，所有平台共用同一份内容（manifest 或单文件）

    html_files = [
        os.path.join(ROOT, 'study_workspace_g6.html'),
        os.path.join(ROOT, 'study_workspace.html'),
        os.path.join(ROOT, 'apk', 'girl', 'index.html'),
        os.path.join(ROOT, 'apk', 'boy', 'index.html'),
        os.path.join(ROOT, 'apk', 'android-girl', 'app', 'src', 'main', 'assets', 'index.html'),
        os.path.join(ROOT, 'apk', 'android-boy', 'app', 'src', 'main', 'assets', 'index.html'),
        os.path.join(ROOT, 'app_package', 'android', 'app', 'src', 'main', 'assets', 'index.html'),
        os.path.join(ROOT, 'app_package', 'pwa', 'index.html'),
    ]
    hpat = re.compile(r"(const CONTENT_URL = ')[^']*(';)")
    for f in html_files:
        s = io.open(f, encoding='utf-8').read()
        new, n = hpat.subn(lambda m, r=url: m.group(1) + r + m.group(2), s, count=1)
        assert n == 1, (f, n)
        io.open(f, 'w', encoding='utf-8').write(new)
        print('updated HTML:', os.path.relpath(f, ROOT), '->', url)

    xml_files = [
        (os.path.join(ROOT, 'apk', 'android-girl', 'app', 'src', 'main', 'res', 'values', 'strings.xml'), url),
        (os.path.join(ROOT, 'apk', 'android-boy', 'app', 'src', 'main', 'res', 'values', 'strings.xml'), url),
    ]
    xpat = re.compile(r'(<string name="content_url">)[^<]*(</string>)')
    for f, repl in xml_files:
        s = io.open(f, encoding='utf-8').read()
        new, n = xpat.subn(lambda m, r=repl: m.group(1) + r + m.group(2), s, count=1)
        assert n == 1, (f, n)
        io.open(f, 'w', encoding='utf-8').write(new)
        print('updated XML :', os.path.relpath(f, ROOT), '->', repl)
    print('DONE. 记得把改动提交并推送到 GitHub（见 README 第四节）。')


if __name__ == '__main__':
    main()
