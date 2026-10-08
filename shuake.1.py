# ============================================================
# shuake 开源版 v1.0（shuake.1.py）｜ GPLv3
# 免责声明：仅用于学习交流。若因不合理操作出现不良记录或学习行为异常，概不负责。
#           如作他用，所承受的法律责任一概与作者无关，使用即代表你同意上述观点。
# ============================================================
import time
import os
import sys
import re
import json
import uuid
import hmac
import hashlib
import subprocess
import urllib.parse
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from playwright.sync_api import sync_playwright
print("使用这个工具需要遵循GPLv3协议，不许二开，如若想二开需经作者允许，并且得开源。")
print("若因不合理操作而出现不良记录或学习行为异常，概不负责。\n如作他用，所承受的法律责任一概与作者无关，使用即代表你同意上述观点\n")
print("可以前往https://afdian.com/a/z_15963?utm_source=copylink&utm_medium=link获取密钥（选择网址之后可以右键复制）")
while True:
    gpl=str(input("你需要输入：我同意上述内容"))
    if gpl=="我同意上述内容":
        break
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
profile_dir = os.path.join(base_dir, "chaoxing_profile")
os.makedirs(profile_dir, exist_ok=True)

# ============================================================
# 授权方式：key 由作者服务器分配（sk-开头），次数由服务器控制，无机器码绑定
# ============================================================
# ⚠️ 解密表密钥：发布前改成自己的随机串，和 gen_enc_table.py 配套（gen 会自动从这读取）
TABLE_SECRET = ""   # 开源版默认留空：发布前用 gen_enc_table.py 重新生成解密表并填入密钥；留空自动回退读取外部 table.json
# ============================================================
# ===== 服务器配置（地址默认指向作者服务器，key 首次输入并保存）=====
DEFAULT_API_BASE = "https://121.41.98.202"

def _save_api_config():
    cfg_path = os.path.join(base_dir, "api_config.json")
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"api_base": API_BASE, "api_key": API_KEY}, f, ensure_ascii=False)
    except:
        pass

def load_api_config():
    cfg_path = os.path.join(base_dir, "api_config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            if cfg.get("api_base") and cfg.get("api_key"):
                print("已读取配置:", cfg["api_base"])
                return cfg["api_base"], cfg["api_key"]
        except:
            pass
    api_base = DEFAULT_API_BASE
    token = input("你的令牌（sk-开头，找作者购买）: ").strip()
    while not token.startswith("sk-"):
        token = input("令牌格式应为 sk- 开头，重新输入: ").strip()
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"api_base": api_base, "api_key": token}, f, ensure_ascii=False)
        print("配置已保存:", cfg_path)
    except:
        pass
    return api_base, token

API_BASE, API_KEY = load_api_config()

# ===== AI =====
def re_input_api_config():
    """密钥无效时：只重新输入令牌，服务器地址保持不变"""
    global API_BASE, API_KEY
    print("=== 重新输入令牌（key 无效或过期）===")
    token = input("你的令牌（sk-开头，找作者购买/续费）: ").strip()
    while not token.startswith("sk-"):
        token = input("令牌格式应为 sk- 开头，重新输入: ").strip()
    API_BASE, API_KEY = API_BASE, token
    _save_api_config()
    print("配置已更新并保存")

def ask_ai(question_text, allow_retry=True):
    """调AI接口，带错误处理：
    - 401 → 密钥错误，提示并让用户重新输入
    - 429 → 请求超限/额度可能用完，稍候自动重试
    - 网络失败 → 提示检查地址/网络
    - 其他错误 → 提示并可重试/跳过
    """
    global API_BASE, API_KEY
    try:
        resp = requests.post(
            f"{API_BASE}/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": "deepseek-flash",
                  "messages": [{"role": "user",
                                "content": f"回答这道题。只输出答案的完整内容（选项文字），不要解释不要编号。如果是多选题，多个答案用顿号（、）分隔：{question_text}"}]},
            timeout=120,
            verify=False
        )
    except requests.exceptions.RequestException as e:
        print("网络连接失败:", e)
        print("当前地址:", API_BASE)
        if allow_retry:
            again = input("按回车用当前地址重试，输入新地址后回车（http/https 开头），输入 n 跳过本题: ").strip()
            low = again.lower()
            if low == "n":
                return ""
            if again.startswith("http://") or again.startswith("https://"):
                API_BASE = again.rstrip("/")
                _save_api_config()
                print("已切换到新地址:", API_BASE)
            return ask_ai(question_text, allow_retry=False)
        return ""

    if resp.status_code == 401:
        print("密钥错误：你输入的令牌无效或已过期（服务器返回 401）")
        print("请重新输入正确的 key（向作者购买/续费）")
        re_input_api_config()
        if allow_retry:
            return ask_ai(question_text, allow_retry=False)
        return ""
    if resp.status_code == 403:
        try:
            msg = resp.json().get("error", {}).get("message", "")
        except Exception:
            msg = resp.text[:200]
        print(f"次数用尽或 key 无效（服务器：{msg}）")
        print("请联系作者购买/续费新 key")
        if allow_retry:
            again = input("按回车重试，输入 n 跳过本题: ").strip().lower()
            if again != "n":
                return ask_ai(question_text, allow_retry=False)
        return ""
    if resp.status_code == 429:
        print("请求太频繁或额度已用完（429），10秒后自动重试...")
        time.sleep(10)
        return ask_ai(question_text, allow_retry=False)
    if resp.status_code != 200:
        print(f"API 返回错误({resp.status_code}): {resp.text[:300]}")
        if allow_retry:
            again = input("按回车重试，输入 n 跳过本题: ").strip().lower()
            if again != "n":
                return ask_ai(question_text, allow_retry=False)
        return ""
    return resp.json()["choices"][0]["message"]["content"]

# ===== 万能frame查找 =====
def find_frame(page, selector):
    for f in page.frames:
        try:
            if f.locator(selector).count() > 0:
                return f
        except:
            pass
    return None

# ===== 安全取文本：绕过GBK页面乱码 =====
def get_text(loc):
    """学习通页面是GBK编码，直接 inner_text() 会变成乱码（"劳动"→"劳損"）。
    办法：在浏览器内部先 encodeURIComponent 成纯ASCII再传回，回来再解码。
    浏览器内部的字符串是正确的，只有传输层会坏，所以这样绕过去。"""
    try:
        raw = loc.evaluate("e => encodeURIComponent(e.innerText)")
        return urllib.parse.unquote(raw).strip()
    except:
        return ""

# ===== 字体解密：学习通题干用加密字体，DOM里是乱码码点 =====
_font_decrypt_map = {}        # 累积解密表（跨页面合并，越用越全）
_font_parsed_keys = set()     # 已解析过的字体特征（b64前64字符），避免重复解析



def _keystream(key, iv, length):
    """CTR 式伪随机流：sha256(key + iv + 块号) 拼接"""
    out = bytearray()
    block = 0
    while len(out) < length:
        out.extend(hashlib.sha256(key + iv + str(block).encode()).digest())
        block += 1
    return bytes(out[:length])

def _get_embedded_table():
    """优先取内嵌密文（打包后无裸json），取不到就退回外部table.json"""
    # 1) 内嵌模块（pyinstaller/pyarmor 会分析 import 自动打进exe）
    try:
        from enc_table import ENCRYPTED_TABLE
        return ENCRYPTED_TABLE
    except Exception:
        pass
    # 2) 同目录 enc_table.py（源码调试/兜底）
    try:
        import importlib.util
        path = os.path.join(base_dir, "enc_table.py")
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("enc_table_local", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.ENCRYPTED_TABLE
    except Exception:
        pass
    return None

def _load_decrypt_table():
    """解密内嵌表 → dict{hash: 汉字码点}；失败返回空dict"""
    import base64 as _b64
    import json as _json
    enc = _get_embedded_table()
    if enc:
        try:
            raw = _b64.b64decode(enc)
            iv, body = raw[:16], raw[16:]
            key = hashlib.sha256(TABLE_SECRET.encode("utf-8")).digest()
            ks = _keystream(key, iv, len(body))
            data = bytes(b ^ k for b, k in zip(body, ks)).decode("utf-8")
            return _json.loads(data)
        except Exception:
            pass
    # 兜底：外部 table.json（调试）
    table_file = os.path.join(base_dir, "table.json")
    if os.path.exists(table_file):
        try:
            with open(table_file, encoding="utf-8") as f:
                return _json.load(f)
        except Exception:
            pass
    print("解密表加载失败：缺少内嵌表或外部 table.json")
    return {}

def extract_encrypted_fonts(frame):
    """提取frame里@font-face块内的字体：内嵌base64 + 外链ttf/woff url（只认字体，不误抓图片）"""
    try:
        return frame.evaluate("""() => {
            const out = {b64: [], url: []};
            for (const s of Array.from(document.querySelectorAll('style'))) {
                const t = s.textContent || '';
                // 只处理@font-face块，避免把背景图等大段base64误当字体
                const faceRe = /@font-face\\s*\\{[^}]*\\}/gi;
                let fm;
                while ((fm = faceRe.exec(t)) !== null) {
                    const block = fm[0];
                    const b64m = block.match(/base64,([A-Za-z0-9+/=]+)/);
                    if (b64m && b64m[1].length > 200) out.b64.push(b64m[1]);
                    const urlm = block.match(/url\\(['"]?([^'")]+?\\.(?:ttf|woff2?|otf)(?:\\?[^'")]*)?)['"]?\\)/i);
                    if (urlm) out.url.push(urlm[1]);
                }
            }
            return out;
        }""") or {"b64": [], "url": []}
    except:
        return {"b64": [], "url": []}

def _typr_num(v):
    """JS数字序列化：整数不带小数点"""
    if float(v).is_integer():
        return int(v)
    return float(v)

def _typr_draw(glyf, name, cmds, crds):
    """精确复刻ABC插件Typr库的字形→路径算法（M/L/Q/C/Z + 坐标数组）"""
    g = glyf[name]
    nc = g.numberOfContours
    if nc > 0:
        coords = g.coordinates
        flags = g.flags
        endpts = g.endPtsOfContours
        for c in range(nc):
            i0 = 0 if c == 0 else endpts[c-1] + 1
            il = endpts[c]
            for i in range(i0, il+1):
                pr = il if i == i0 else i - 1
                nx = i0 if i == il else i + 1
                onCurve = flags[i] & 1
                prOnCurve = flags[pr] & 1
                nxOnCurve = flags[nx] & 1
                x, y = coords[i][0], coords[i][1]
                if i == i0:
                    if onCurve:
                        if prOnCurve:
                            cmds.append("M"); crds.append(_typr_num(coords[pr][0])); crds.append(_typr_num(coords[pr][1]))
                        else:
                            cmds.append("M"); crds.append(_typr_num(x)); crds.append(_typr_num(y))
                            continue
                    else:
                        if prOnCurve:
                            cmds.append("M"); crds.append(_typr_num(coords[pr][0])); crds.append(_typr_num(coords[pr][1]))
                        else:
                            cmds.append("M"); crds.append(_typr_num((coords[pr][0]+x)/2)); crds.append(_typr_num((coords[pr][1]+y)/2))
                if onCurve:
                    if prOnCurve:
                        cmds.append("L"); crds.append(_typr_num(x)); crds.append(_typr_num(y))
                else:
                    if nxOnCurve:
                        cmds.append("Q"); crds.append(_typr_num(x)); crds.append(_typr_num(y)); crds.append(_typr_num(coords[nx][0])); crds.append(_typr_num(coords[nx][1]))
                    else:
                        cmds.append("Q"); crds.append(_typr_num(x)); crds.append(_typr_num(y)); crds.append(_typr_num((x+coords[nx][0])/2)); crds.append(_typr_num((y+coords[nx][1])/2))
            cmds.append("Z")
    elif nc < 0:
        for comp in g.components:
            sub_cmds, sub_crds = [], []
            _typr_draw(glyf, comp.glyphName, sub_cmds, sub_crds)
            m = comp.transform
            for i in range(0, len(sub_crds), 2):
                x, y = sub_crds[i], sub_crds[i+1]
                crds.append(_typr_num(m[0]*x + m[1]*y + m[4]))
                crds.append(_typr_num(m[2]*x + m[3]*y + m[5]))
            cmds.extend(sub_cmds)

def build_font_decrypt_map(b64):
    """单个字体b64 → 解密映射 dict（码点→真实字符）；非字体或失败返回 {}
    hash = md5(JSON.stringify({cmds,crds})).slice(24) → 查表得真实汉字"""
    import io
    import base64 as _b64
    import hashlib as _hl
    import json as _json
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        print("缺少fonttools库，题干无法解密：pip install fonttools")
        return {}
    table = _load_decrypt_table()
    if not table:
        return {}
    mapping = {}
    try:
        raw = _b64.b64decode(b64)
        # 存一份加密字体到本地，方便排查
        try:
            with open(os.path.join(base_dir, "enc_font_dump.ttf"), "wb") as fh:
                fh.write(raw)
        except:
            pass
        font = TTFont(io.BytesIO(raw))
        cmap = font.getBestCmap() or {}
        glyf = font["glyf"]
        hits = 0
        for code, name in cmap.items():
            if 0x4E00 <= code <= 0x9FFF or 0xE000 <= code <= 0xF8FF:
                cmds, crds = [], []
                _typr_draw(glyf, name, cmds, crds)
                path = {"cmds": cmds, "crds": crds}
                h = _hl.md5(_json.dumps(path, separators=(",", ":")).encode("utf-8")).hexdigest()[24:]
                real = table.get(h)
                if real is not None:
                    mapping[code] = int(real)
                    hits += 1
        print(f"加密字体码点数:{len(cmap)} 解密命中:{hits}")
    except Exception:
        return {}   # 非字体base64静默跳过
    return mapping

def decrypt_text(text, mapping):
    """把文本里的乱码码点替换成正常汉字"""
    if not mapping:
        return text
    return "".join(chr(mapping.get(ord(ch), ord(ch))) for ch in text)

# ===== 答题（支持两种：作业/考试=.questionLi，章节测验=.TiMu）=====
def answer_question(page):
    frame = find_frame(page, ".questionLi") or find_frame(page, ".TiMu")
    if not frame:
        print("没找到题目（.questionLi 和 .TiMu 都没有）")
        return
    print("题目frame:", frame.url[:100])
    sel = ".questionLi" if frame.locator(".questionLi").count() > 0 else ".TiMu"
    questions = frame.locator(sel).all()
    print(f"找到{len(questions)}道题")
    # 字体解密：累积式——已解析过的字体跳过，新字体并入全局表（跨章节安全）
    global _font_decrypt_map, _font_parsed_keys
    import base64 as _b64
    if not _font_parsed_keys:
        time.sleep(2)   # 只在第一次等页面JS把字体style注入完
    b64s, urls = [], []
    for f in page.frames:            # 字体style可能不在答题iframe里，全frame扫一遍
        r = extract_encrypted_fonts(f)
        b64s.extend(r.get("b64", []))
        urls.extend(r.get("url", []))
    for u in urls:   # 外链字体：下载下来当内嵌处理
        try:
            rr = requests.get(u, timeout=10)
            if rr.ok:
                b64s.append(_b64.b64encode(rr.content).decode())
        except:
            pass
    new_fonts = [b for b in b64s if b[:64] not in _font_parsed_keys]
    if new_fonts:
        print("发现加密字体，正在解密题干...")
        for b in new_fonts:
            _font_parsed_keys.add(b[:64])
            m = build_font_decrypt_map(b)
            if m:
                _font_decrypt_map.update(m)
        if _font_decrypt_map:
            print("解密映射累计:", len(_font_decrypt_map), "个字符")
        else:
            print("警告：提取到字体但全部解析失败")
    elif not b64s and not _font_decrypt_map:
        print("没提取到加密字体，打印页面诊断信息（发我定位）：")
        for f in page.frames:
            try:
                info = f.evaluate("""() => {
                    const ss = Array.from(document.querySelectorAll('style'));
                    return 'style数=' + ss.length + ' 含font-cxsecret=' + ss.some(s => (s.textContent||'').includes('font-cxsecret')) + ' 样例=' + (ss.length ? (ss[0].textContent || '').slice(0, 200) : '(无style)');
                }""")
                print(f"  [frame] {f.url[:50]} {info}")
            except:
                pass
    for q in questions:
        text = decrypt_text(get_text(q), _font_decrypt_map)
        ans = ask_ai(text)
        print("题目:", text[:50].replace(chr(10), " "))
        print("AI答案:", ans[:80])
        # 从题目容器内提取选项（不全局匹配，避免误命中）
        opts = []
        opt_texts = []
        for sel_opt in ['[class*="before-after"]', ".answerBg", "td", "li"]:
            opts = q.locator(sel_opt).all()
            pairs = [(o, decrypt_text(get_text(o), _font_decrypt_map)) for o in opts]
            pairs = [(o, t) for o, t in pairs if t]   # 过滤空选项，保持对应
            if pairs:
                opts = [o for o, _ in pairs]
                opt_texts = [t for _, t in pairs]
                break
        print("选项:", [t[:30] for t in opt_texts])
        ans_clean = re.sub(r"[。．.!！?？\s]+$", "", ans.strip())
        clicked = False
        # 策略1：答案与选项文字匹配（兼容去掉" A. "前缀、尾部标点）
        for o, t in zip(opts, opt_texts):
            pure = re.sub(r"^[A-H][\.、．\s:：]*", "", t).strip()
            pure = re.sub(r"[。．.!！?？\s]+$", "", pure)
            if ans_clean == t or ans_clean == pure or pure.startswith(ans_clean) or ans_clean in pure:
                try:
                    o.click(timeout=5000)
                    print("点了选项:", t[:30])
                    clicked = True
                except:
                    pass
                break
        # 策略2：AI返回多个选项文字拼接/顿号分隔（多选题）→ 答案里含哪个选项文字就点哪个
        if not clicked:
            for o, t in zip(opts, opt_texts):
                pure = re.sub(r"^[A-H][\.、．\s:：]*", "", t).strip()
                pure = re.sub(r"[。．.!！?？\s]+$", "", pure)
                if pure and pure in ans_clean:
                    try:
                        o.click(timeout=5000)
                        print("点了选项:", t[:30])
                        clicked = True
                    except:
                        pass
        # 策略3：答案是字母（如"C"、"B、D"）→ 按选项顺序定位 A/B/C/D（多选题点全部）
        if not clicked:
            letters = re.findall(r"[ABCDEFGH]", ans_clean)
            for L in letters:
                idx = "ABCDEFGH".index(L)
                if idx < len(opts):
                    try:
                        opts[idx].click(timeout=5000)
                        print("点了选项:", opt_texts[idx][:30])
                        clicked = True
                    except:
                        pass
        if not clicked:
            print("没匹配到选项，答案:", ans_clean[:40])
    # 提交：考试走 completeBtn，章节测验走iframe的JS提交函数（ABC插件同款）
    time.sleep(1)
    submitted = False
    try:
        if frame.locator("div.sub-button.fr a.completeBtn").count() > 0:
            frame.locator("div.sub-button.fr a.completeBtn").click(no_wait_after=True)
            print("点了提交按钮（考试/作业）")
            submitted = True
    except:
        pass
    if not submitted:
        try:
            frame.evaluate("() => { if (typeof btnBlueSubmit === 'function') btnBlueSubmit(); }")
            print("调用了提交函数 btnBlueSubmit()")
            time.sleep(2)
            frame.evaluate("() => { if (typeof submitCheckTimes === 'function') submitCheckTimes(); }")
            print("调用了确认函数 submitCheckTimes()")
            submitted = True
        except Exception as e:
            print("提交函数调用失败:", e)
    # 关闭/处理提交确认弹窗 #workpop（它在主框架，章节测验的确认框）
    try:
        pop = page.locator("#workpop")
        if pop.count() > 0 and pop.is_visible():
            done = False
            for sel in ["#workpop a[onclick*='submitCheckTimes']", "#workpop .bluebtn",
                        "#workpop a", "#workpop button", "text=确定", "text=确认"]:
                try:
                    b = page.locator(sel).first
                    if b.count() > 0 and b.is_visible():
                        b.click(timeout=3000)
                        print("点了提交确认弹窗按钮")
                        done = True
                        break
                except:
                    pass
            if not done:
                page.evaluate("() => { const p = document.querySelector('#workpop'); if (p) p.style.display = 'none'; }")
                print("确认弹窗已隐藏")
    except:
        pass
    # 兜底：找可见的"确定/确认"按钮（最多等5秒弹窗出现）
    time.sleep(1)
    clicked_confirm = False
    for _ in range(5):
        for scope in (frame, page):
            for btn_sel in ['text=确定', 'text=确认', 'button:has-text("确定")',
                            'button:has-text("确认")', '.ui-dialog-autofocus']:
                try:
                    b = scope.locator(btn_sel)
                    if b.count() > 0 and b.first.is_visible():
                        b.first.click(timeout=3000)
                        print("点了确定（提交确认）")
                        clicked_confirm = True
                        break
                except:
                    pass
            if clicked_confirm:
                break
        if clicked_confirm:
            break
        time.sleep(1)
    time.sleep(2)

# ===== 防暂停：按ABC脚本逻辑，鼠标移出导致暂停后强制恢复 =====
def inject_force_play(frame):
    """向视频所在frame注入JS（参考ABC插件，比之前激进）：
    1. 监听pause事件 → 300ms后立即强制play()（鼠标移出暂停立刻拉回）
    2. 500ms高频哨兵 → 学习通秒级暂停也拉得回来
    3. 静音播放（不设倍速、不快进，保持原速）
    4. 弹题直接跳过，视频继续播
    """
    try:
        frame.evaluate("""() => {
            const forcedPlay = () => {
                document.querySelectorAll('video').forEach(v => {
                    if (v.paused && !v.ended && v.readyState >= 2) {
                        v.muted = true;
                        v.play().catch(() => {});
                    }
                });
            };
            // 对当前已有的video注入监听（元素重建后重新注入）
            document.querySelectorAll('video').forEach(v => {
                if (v.__abc_forced) return;
                v.__abc_forced = true;
                v.muted = true;
                v.addEventListener('pause', () => setTimeout(forcedPlay, 300));
            });
            // 高频哨兵：先清旧哨兵再注入（只保留本frame最新的一个，防重复叠加）
            if (window.__abc_interval) { clearInterval(window.__abc_interval); window.__abc_interval = null; }
            if (window.__abc_skip) { clearInterval(window.__abc_skip); window.__abc_skip = null; }
            window.__abc_sentinel_on = false;
            window.__abc_sentinel_on = true;
            window.__abc_interval = setInterval(forcedPlay, 500);
            // 视频播放中间弹出的题目（弹题）直接跳过，视频继续播
            const skipQuiz = () => {
                const btn = document.querySelector('#videoquiz-submit');
                if (btn && btn.offsetParent !== null) {
                    const qc = document.querySelector('.ans-timelineobjects');
                    if (qc) qc.style.display = 'none';
                    const bg = document.querySelector('.ans-timelineobjectsbg');
                    if (bg) bg.style.display = 'none';
                    forcedPlay();
                }
            };
            window.__abc_skip = setInterval(skipQuiz, 2000);
        }""")
        print("已注入强制播放（鼠标移出也不会停）")
    except Exception as e:
        print("注入失败:", e)

def stop_all_force_play(page):
    """清除页面所有frame的强制播放哨兵（播下一个视频前调用，防多视频互相抢夺）"""
    try:
        for f in page.frames:
            try:
                f.evaluate("""() => {
                    if (window.__abc_interval) { clearInterval(window.__abc_interval); window.__abc_interval = null; }
                    if (window.__abc_skip) { clearInterval(window.__abc_skip); window.__abc_skip = null; }
                    window.__abc_sentinel_on = false;
                }""")
            except:
                pass
    except:
        pass


# ===== 播放状态 =====
def is_playing(page):
    frame = find_frame(page, "#video")
    if not frame:
        return False
    cls = frame.locator("#video").get_attribute("class") or ""
    return "vjs-playing" in cls

def ensure_playing(page, only_frames=None):
    """让视频开始播放（ABC插件同款：不点任何按钮，直接 muted+play() 反复拉回。
    点大播放按钮会导致 video-js 重建播放器/iframe重载 → 卡"重建中"，所以坚决不点）"""
    frames = []
    if only_frames is not None:
        frames = list(only_frames)
    else:
        for f in page.frames:
            try:
                if f.locator("#video").count() > 0 or f.locator("video#video_html5_api").count() > 0:
                    frames.append(f)
            except:
                pass
    if not frames:
        print("没找到视频frame")
        return
    for frame in frames:
        # JS强制播放：muted可绕过自动播放限制，ended 的不动（不重播）
        try:
            frame.evaluate("""() => {
                document.querySelectorAll('video').forEach(v => {
                    if (!v.ended) {
                        v.muted = true;
                        const p = v.play();
                        if (p && p.catch) p.catch(() => {});
                    }
                });
            }""")
        except:
            pass
    time.sleep(2)

def _deepest_video_frame(f):
    """从frame向下递归（含自身）找第一个有 video#video_html5_api 的frame。
    学习通视频iframe可能嵌套多层，只查当前层会漏。找不到返回None"""
    try:
        if f.locator("video#video_html5_api").count() > 0:
            return f
    except:
        pass
    for cf in f.child_frames:
        r = _deepest_video_frame(cf)
        if r:
            return r
    return None

def reacquire_video_frame(page):
    """重新扫描页面拿一个有效的视频frame（优先未完成的任务点，其次全frame）。
    学习通切课程/切视频会重建iframe，旧frame失效后用它换新frame"""
    tf = enumerate_task_frames(page)
    if tf:
        for f, fin in tf:
            if not fin:
                return f
    for f in page.frames:
        try:
            if f.locator("video#video_html5_api").count() > 0:
                return f
        except:
            pass
    return None

def current_video_target(context):
    """在所有标签页里找有视频的frame（学习通可能重建/跳转/新开标签）。
    不判断任务点完成状态（src去重由调用方处理），返回 (page, vf)；都没有返回 None"""
    for pg in context.pages:
        try:
            tfs = find_all_video_frames(pg)
        except:
            tfs = []
        if tfs:
            return pg, tfs[0]
    return None

_enumerate_diag_done = [False]

def try_seek_to_end(vf):
    """尝试把视频seek到末尾前0.5秒（等价手动拖进度条）。
    返回 True=seek成功（视频即将ended，秒过）；False=seek无效（未加载/被防快进拉回，需正常播放）。
    验证方式：设完currentTime等1.5秒，若currentTime真的到末尾附近说明进度条能跳。"""
    try:
        v = vf.locator("video#video_html5_api").first
        info = v.evaluate("""(el) => {
            if (!el || !el.duration || el.duration <= 0 || isNaN(el.duration)) return {ok: false};
            if (el.ended) return {ok: true, reason: 'already_ended'};
            const target = el.duration - 0.5;
            try { el.currentTime = target; } catch (e) { return {ok: false}; }
            return {ok: true, target: target};
        }""")
        if not info or not info.get("ok"):
            return False
        if info.get("reason") == "already_ended":
            return True
        time.sleep(1.5)
        after = v.evaluate("el => ({t: el.currentTime, d: el.duration})")
        if after and after.get("d") and after.get("t") is not None:
            if after["t"] >= after["d"] * 0.9 or after["t"] >= (info.get("target") or 0) - 2:
                return True
        return False
    except:
        return False


def wait_video_ended(vf, timeout=60):
    """等待vf里的视频全部ended（或已到末尾）。持续拉播放防暂停。返回True=结束/超时返回False"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            st = vf.evaluate("""() => {
                const vs = document.querySelectorAll('video');
                if (!vs.length) return null;
                for (const v of vs) {
                    if (!v.ended && (v.currentTime || 0) < (v.duration || 0) - 1) return false;
                }
                return true;
            }""")
            if st:
                return True
        except:
            pass
        try:
            vf.evaluate("""() => {
                document.querySelectorAll('video').forEach(v => {
                    if (!v.ended && v.paused) { v.muted = true; v.play().catch(()=>{}); }
                });
            }""")
        except:
            pass
        time.sleep(2)
    return False


def chapter_catalog_finished(page):
    """ABC插件同款章节级完成判定：读左侧目录当前激活章节容器。
    ① .posCatalog_active 内有 .icon_Completed（完成图标）
    ② 或 .jobUnfinishCount（未完成任务数）value==0
    返回 True=全部完成 / False=有未完成 / None=目录结构读不到（不干扰主流程）"""
    try:
        return page.evaluate("""() => {
            const act = document.querySelector('.posCatalog_active');
            if (!act) return null;
            if (act.querySelector('.icon_Completed')) return true;
            const u = act.querySelector('.jobUnfinishCount');
            if (u) {
                const n = parseInt(String(u.value || '').trim(), 10);
                if (Number.isFinite(n)) return n === 0;
            }
            return null;
        }""")
    except:
        return None


def enumerate_task_frames(page):
    """参考ABC插件：直接操作主页面iframe元素，元素→content_frame()，不依赖URL配对。
    任务点iframe判定：父链 class 含 ans-job-icon（老结构）或 fanyaPreview（新结构/本部署实际特征）。
    每个iframe检查：是任务点 → 是否有video → 是否已完成。
    finished 判定（三层）：
      ① iframe自身/父链/父容器子树 class 含 ans-job-finished
      ② 视频进度已到末尾（看过但没标记）
      ③ 左侧目录文字顺序关联：目录"任务点已完成/未完成"顺序 == 视频iframe顺序（数量一致时生效，
         学习通部分版本完成状态只写在目录文字/图标里）
    返回 [(frame, finished)]；找不到任务点返回 None。"""
    global _enumerate_diag_done
    try:
        # ③ 目录/章节完成标记：优先读章节容器（ABC同款 icon_Completed / jobUnfinishCount），
        #    其次目录文字（过滤弹窗 jobLimitTip/popWord2，避免"当前章节还有任务"误收）
        catalog_flags = []
        try:
            catalog_flags = page.evaluate("""() => {
                const flags = [];
                const act = document.querySelector('.posCatalog_active');
                if (act) {
                    if (act.querySelector('.icon_Completed')) { flags.push(true); return flags; }
                    const u = act.querySelector('.jobUnfinishCount');
                    if (u) {
                        const n = parseInt(String(u.value || '').trim(), 10);
                        if (Number.isFinite(n)) { flags.push(n === 0); return flags; }
                    }
                }
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                let nn;
                while ((nn = walker.nextNode())) {
                    const t = (nn.textContent || '').trim();
                    let bad = false;
                    let cur = nn.parentElement;
                    while (cur) {
                        const c = (cur.className || '').toString();
                        if (c.indexOf('jobLimitTip') !== -1 || c.indexOf('popWord2') !== -1) { bad = true; break; }
                        cur = cur.parentElement;
                    }
                    if (bad) continue;
                    if (t.indexOf('任务点已完成') !== -1) flags.push(true);
                    else if (t.indexOf('任务点未完成') !== -1) flags.push(false);
                }
                return flags;
            }""") or []
        except:
            catalog_flags = []
        handles = page.query_selector_all("iframe")
        result = []
        for h in handles:
            try:
                info = h.evaluate("""(el) => {
                    const clsOf = (node) => (node.className || '').toString();
                    const isTaskCls = (s) => s.indexOf('ans-job-icon') !== -1 || s.indexOf('fanyaPreview') !== -1;
                    const checkFinished = (node) => {
                        const c = clsOf(node);
                        if (c.indexOf('ans-job-finished') !== -1) return true;
                        if (node.querySelector && node.querySelector('.ans-job-finished')) return true;
                        return false;
                    };
                    let isTask = false;
                    let finished = false;
                    if (isTaskCls(clsOf(el))) isTask = true;
                    if (checkFinished(el)) finished = true;
                    let cur = el.parentElement;
                    while (cur && cur.tagName !== 'BODY') {
                        const c = clsOf(cur);
                        if (isTaskCls(c)) isTask = true;
                        if (checkFinished(cur)) finished = true;
                        if (isTask && finished) break;
                        cur = cur.parentElement;
                    }
                    return { isTask: isTask, finished: finished };
                }""")
                if not info or not info.get("isTask"):
                    continue
                f = _deepest_video_frame(h.content_frame())
                if f is None:
                    continue   # 这个任务点没有视频（文档/题目），跳过
                # ① + ②
                finished = bool(info.get("finished")) or video_progress_done(f)
                result.append((f, finished))
            except:
                pass
        # ③ 目录顺序关联：数量一致时按序补完成状态
        if catalog_flags and len(catalog_flags) == len(result):
            for i, (f, fin) in enumerate(result):
                if catalog_flags[i]:
                    result[i] = (f, True)
        elif catalog_flags:
            print(f"[诊断] 目录完成标记{len(catalog_flags)}个 vs 视频任务点{len(result)}个，顺序不匹配，本次跳过目录判定")
        # 首次调用打印：iframe父链class + src + 目录标记位置上下文，便于定位完成标记结构
        if not _enumerate_diag_done[0] and handles:
            _enumerate_diag_done[0] = True
            try:
                cls_info = page.evaluate("""() => {
                    const out = [];
                    document.querySelectorAll('iframe').forEach((el, i) => {
                        const chain = [];
                        let cur = el.parentElement;
                        let depth = 0;
                        while (cur && depth < 5) {
                            chain.push((cur.className || cur.tagName).toString());
                            cur = cur.parentElement;
                            depth++;
                        }
                        out.push('iframe#' + i + ' src="' + (el.src || '').slice(0, 60) + '" 父链class=[' + chain.join(' | ') + ']');
                    });
                    return out;
                }""")
                for line in (cls_info or [])[:15]:
                    print("  [诊断]" + line)
                mark_info = page.evaluate("""() => {
                    const out = [];
                    const act = document.querySelector('.posCatalog_active');
                    if (act) {
                        out.push('active章节class="' + (act.className || '') + '" id="' + (act.id || '') + '"');
                        out.push('含icon_Completed=' + !!act.querySelector('.icon_Completed'));
                        const u = act.querySelector('.jobUnfinishCount');
                        out.push('含jobUnfinishCount=' + !!u + (u ? ' value=' + (u.value || '') : ''));
                        out.push('章节HTML=' + act.outerHTML.slice(0, 2000).replace(/\s+/g, ' '));
                        out.push('章节内ans-job-icon=' + act.querySelectorAll('.ans-job-icon').length);
                        out.push('章节内.ans-job=' + act.querySelectorAll('.ans-job').length);
                        Array.from(act.querySelectorAll('.ans-job-icon, .ans-job, li')).slice(0, 12).forEach(function(el) {
                            const t = (el.textContent || '').trim().replace(/\s+/g, ' ');
                            if (t && t.length < 40) out.push('  目录项: ' + t);
                        });
                    } else {
                        out.push('未找到 .posCatalog_active');
                    }
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    let n;
                    while ((n = walker.nextNode())) {
                        const t = (n.textContent || '').trim();
                        if (t.indexOf('任务点已完成') !== -1 || t.indexOf('任务点未完成') !== -1) {
                            const p = n.parentElement;
                            const prev = p && p.previousElementSibling ? (p.previousElementSibling.textContent || '').trim().slice(0, 14) : '';
                            out.push('[' + t.slice(0, 10) + '] 容器class="' + (p ? (p.className || '').toString() : '') + '" 前兄弟="' + prev + '"');
                        }
                    }
                    return out;
                }""")
                for line in (mark_info or [])[:12]:
                    print("  [诊断]" + line)
            except:
                pass
        return result if result else None
    except:
        return None

def task_parents_finished(page, vframes):
    """检查vframes里所有frame对应的主页面父容器是否都带 ans-job-finished。
    返回 True=全部完成 / False=有未完成 / None=无法判定（一个iframe都没对上时返回None，
    让调用方退回video.ended判定，避免匹配不上就永远等死）"""
    try:
        srcs = [f.url for f in vframes]
        return page.evaluate("""(srcs) => {
            const els = document.querySelectorAll('iframe');
            let matched = 0;
            for (const el of els) {
                const src = (el.src || '').split('?')[0];
                let hit = false;
                for (const s of srcs) {
                    const base = (s || '').split('?')[0];
                    if (base && ((src && src.indexOf(base) === 0) || (base.indexOf(src) === 0))) { hit = true; break; }
                }
                if (hit) {
                    matched += 1;
                    if (!el.parentElement || el.parentElement.className.indexOf('ans-job-finished') === -1) return false;
                }
            }
            return matched > 0 ? true : null;
        }""", srcs)
    except:
        return None

def video_task_points_finished(page):
    """ABC插件同款最终判定：页面上所有'带视频的任务点'是否都 ans-job-finished（服务端确认）。
    阅读/文档任务点不计入（它们由process_read_page处理）。
    返回 True=全部完成 / False=有未完成 / None=页面上没有带视频的任务点（无法判定）"""
    try:
        return page.evaluate("""() => {
            const iframes = document.querySelectorAll('iframe');
            let videoTasks = 0;
            for (const el of Array.from(iframes)) {
                const p = el.parentElement;
                if (!p || !p.querySelector('.ans-job-icon')) continue;   // 不是任务点
                let hasVideo = false;
                try {
                    const d = el.contentDocument;
                    if (d) hasVideo = !!(d.querySelector('video'));
                } catch (e) {}
                if (!hasVideo) continue;
                videoTasks += 1;
                let cur = p;
                let found = false;
                while (cur && cur.tagName !== 'BODY') {
                    if ((cur.className || '').indexOf('ans-job-finished') !== -1) { found = true; break; }
                    cur = cur.parentElement;
                }
                if (!found) return false;
            }
            return videoTasks > 0 ? true : null;
        }""")
    except:
        return None

def task_parent_finished(page, vf):
    """单任务点版：指定vf（Playwright frame）对应的任务点是否已 ans-job-finished。
    URL配对主页面iframe（enumerate已用元素级直取，这里配对是兜底）；
    配对不上返回None（由调用方退回video.ended判定）。
    finished 查找范围：iframe自身 + 父链向上 + 父容器子树。"""
    try:
        src = (vf.url or "").split("?")[0]
        if not src:
            return None
        return page.evaluate("""(src) => {
            for (const el of document.querySelectorAll('iframe')) {
                const s = (el.src || '').split('?')[0];
                if (!s) continue;
                if (s === src || s.indexOf(src) === 0 || src.indexOf(s) === 0) {
                    const checkFinished = (node) => {
                        const c = node.className || '';
                        if (c.indexOf('ans-job-finished') !== -1) return true;
                        if (node.querySelector && node.querySelector('.ans-job-finished')) return true;
                        return false;
                    };
                    if (checkFinished(el)) return true;
                    let cur = el.parentElement;
                    while (cur && cur.tagName !== 'BODY') {
                        if (checkFinished(cur)) return true;
                        cur = cur.parentElement;
                    }
                    return false;
                }
            }
            return null;
        }""", src)
    except:
        return None

def video_frame_ended(vf):
    """严格版：vf里的所有video都ended才算True；没video/元素重建/异常一律False（继续等）"""
    try:
        vs = vf.locator("video#video_html5_api")
        if vs.count() == 0:
            return False
        for v in vs.all():
            try:
                if not v.evaluate("el => el.ended"):
                    return False
            except:
                return False
        return True
    except:
        return False

def video_progress_done(vf, ratio=0.97):
    """视频是否基本播完（学习通记住进度，已看完的任务点再次进入会从末尾加载）：
    ended 或 currentTime >= duration*ratio（duration>0）→ 算完成。
    用于枚举任务点时跳过'看过但没标记'的知识点"""
    try:
        vs = vf.locator("video#video_html5_api")
        if vs.count() == 0:
            return False
        for v in vs.all():
            try:
                st = v.evaluate("el => ({e: el.ended, t: el.currentTime||0, d: el.duration||0})")
                if st["e"]:
                    continue
                if st["d"] > 0 and st["t"] >= st["d"] * ratio:
                    continue
                return False
            except:
                return False
        return True
    except:
        return False

def video_state_text(page, vframes):
    """打印每个视频frame里视频的实时状态（播放/暂停/播完 + 进度），用于等待期间确认没卡死"""
    parts = []
    for i, f in enumerate(vframes):
        try:
            vs = f.locator("video#video_html5_api")
            if vs.count() > 0:
                v = vs.first
                st = v.evaluate("el => ({p: el.paused, e: el.ended, t: Math.floor(el.currentTime), d: Math.floor(el.duration||0)})")
                tag = "播完" if st["e"] else ("暂停" if st["p"] else "播放")
                parts.append(f"v{i}:{tag} {st['t']}/{st['d']}s")
            else:
                parts.append(f"v{i}:无video")
        except:
            parts.append(f"v{i}:重建中")
    return " | ".join(parts)

def all_videos_ended(page, vframes):
    """严格版：所有收集到的frame里，video全部ended才算完成。
    - 有video且未ended → 未完成
    - 有video且ended → 完成
    - 没有video（消失/还没加载）→ 未完成，继续等（防止误判跳走）
    返回 True 只发生在"确实看到过video且全部ended"时"""
    any_video = False
    for f in vframes:
        try:
            vs = f.locator("video#video_html5_api")
            if vs.count() > 0:
                any_video = True
                for v in vs.all():
                    try:
                        if not v.evaluate("el => el.ended"):
                            return False
                    except:
                        return False    # 元素刚被替换/重建，状态未知 → 继续等
        except:
            pass
    return any_video

def all_video_tasks_done(page):
    """参考ABC插件：完成判定看任务点容器 class 是否带 ans-job-finished
    （学习通服务端确认任务完成后才会加这个类，不受播放器重建影响，最可靠）
    返回：True=全部完成 / False=有未完成 / None=找不到容器（交由video判定）"""
    try:
        containers = page.locator(".ans-attach-ct.videoContainer")
        n = containers.count()
        if n == 0:
            return None
        for i in range(n):
            cls = containers.nth(i).get_attribute("class") or ""
            if "ans-job-finished" not in cls:
                return False
        return True
    except:
        return None

# ===== 点下一节 =====
def click_next(page):
    sels = ["#prevNextFocusNext",
            ".jb_btn.jb_btn_92.fr.fs14.nextChapter",
            "text=下一节", "text=下一章",
            "a:has-text('下一节')", "a:has-text('下一章')",
            "button:has-text('下一节')", "button:has-text('下一章')"]
    # 先主页面可见的
    for sel in sels:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(no_wait_after=True)
                print(f"点了下一节（{sel}）")
                return
        except:
            pass
    # 再全frame找
    for sel in sels:
        try:
            f = find_frame(page, sel)
            if f:
                loc = f.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(no_wait_after=True)
                    print(f"点了下一节（frame内 {sel}）")
                    return
        except:
            pass
    print("没找到下一节按钮（可能需要手动点）")

# ===== 阅读页（图片/文档/电子书任务点）：参考ABC插件 =====
def find_read_frame(page):
    """找阅读页 frame（滚动内容所在的那一层优先）：
    1. DOM特征优先：fileBox(滚动图片)/book-container(电子书)/imglook(图片查看器)/swiper(幻灯片)
    2. 内层URL优先：screen/v2/file（滚动图片的真实内容文档）
    3. 外层URL兜底：screen/file、knowledge/card（若内容在内层，滚动时再滚父页面）
    """
    for f in page.frames:
        try:
            if (f.locator(".fileBox").count() > 0
                    or f.locator('li[id^="anchor"]').count() > 0
                    or f.locator(".book-container").count() > 0
                    or f.locator("#img.imglook").count() > 0
                    or f.locator(".swiper-container").count() > 0):
                return f
        except:
            pass
    for f in page.frames:
        try:
            if "screen/v2/file" in f.url:
                return f
        except:
            pass
    for f in page.frames:
        try:
            if "screen/file" in f.url or "knowledge/card" in f.url:
                return f
        except:
            pass
    return None

def get_book_required_seconds(frame):
    """计时阅读任务点检测（参考ABC插件 getBookRequiredSeconds）：
    电子书 iframe[name="bookifame"] 的 src 带 timing=秒数 → 需在页面保持 N 秒才算完成"""
    try:
        src = frame.evaluate("""() => {
            const f = document.querySelector('iframe[name="bookifame"]');
            return f ? (f.getAttribute('src') || '') : '';
        }""") or ""
        if "timing" not in src:
            return 0
        m = re.search(r"[?&]timing=(\d+)", src)
        return int(m.group(1)) if m and int(m.group(1)) > 0 else 0
    except:
        return 0

def process_read_page(frame):
    """按ABC插件逻辑处理阅读任务点：
    1. 图片查看器(#img.imglook)/普通文档：有 finishJob() 函数 → 直接调用完成
    2. swiper幻灯片：循环 swiperNext() 翻完所有页
    3. 电子书/图文页：滚动到底 + 保持计时（timing秒）或等待服务端记录完成
    """
    # 1. 优先 finishJob()：图片查看器/文档任务点的一键完成入口
    try:
        has_finish = frame.evaluate("() => typeof finishJob === 'function'")
        is_viewer = frame.locator("#img.imglook").count() > 0
        has_slides = frame.locator(".swiper-container").count() > 0
        if has_finish and (is_viewer or not has_slides):
            frame.evaluate("() => { try { finishJob(); } catch(e) {} }")
            print("调用了 finishJob() 完成任务点")
            time.sleep(3)
            return True
    except:
        pass
    # 2. swiper 幻灯片：一页页翻完（学习通幻灯片任务点）
    try:
        if frame.locator(".swiper-container").count() > 0:
            slide_count = frame.locator(".swiper-container .swiper-slide").count()
            for _ in range(slide_count):
                frame.evaluate("() => { try { swiperNext(); } catch(e) {} }")
                time.sleep(1)
            print(f"已翻完 {slide_count} 张幻灯片")
            time.sleep(2)
            return True
    except:
        pass
    # 3. 电子书/图文：从头滚到尾
    ok = scroll_read_page(frame)
    if not ok:
        return False
    # 4. 任务确认（ABC插件机制）：
    #    计时任务点 → 滚动完还要保持 timing 秒；普通任务 → 等几秒让服务端记录完成
    need = get_book_required_seconds(frame)
    if need > 0:
        print(f"计时阅读任务点：滚动完成，还需保持约 {need} 秒（请勿切换页面）")
        waited = 0
        while waited < need:
            time.sleep(5)
            waited += 5
        print("计时阅读完成")
    else:
        print("阅读页已处理完，等待任务记录完成（2秒缓冲）...")
        time.sleep(2)
    return True

def scroll_read_page(frame):
    """把阅读页从头滚到尾（参考ABC插件）：优先电子书容器，其次任意最大可滚动元素，最后整页。
    若内容在iframe里但滚动条在父页面（iframe高度撑满内容），iframe滚完后再滚父页面。"""
    is_main = (frame == frame.page.main_frame)
    try:
        # 选定滚动目标
        frame.evaluate("""() => {
            const bc = document.querySelector('.preview-section .book-mark .book-container');
            if (bc && bc.scrollHeight > bc.clientHeight + 5) { window.__rt = bc; return; }
            const els = Array.from(document.querySelectorAll('*'))
                .filter(e => e.scrollHeight > e.clientHeight + 5)
                .sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
            window.__rt = els.length ? els[0] : (document.scrollingElement || document.documentElement);
        }""")
        for _ in range(60):   # 最多滚60步，每步1.5秒
            # 先判断是否已到底/无滚动内容
            info = frame.evaluate("""() => {
                const t = window.__rt || document.documentElement;
                const max = t.scrollHeight - t.clientHeight;
                if (max <= 0) return 'noscroll';
                const target = Math.min(t.scrollTop + Math.max(t.clientHeight * 0.8, 200), max);
                t.scrollTo({top: target, behavior: 'smooth'});
                return 'scrolling';
            }""")
            if info == 'noscroll':
                print("阅读页无滚动内容，直接过")
                break
            time.sleep(1.5)
            done = frame.evaluate("""() => {
                const t = window.__rt || document.documentElement;
                return t.scrollTop + t.clientHeight >= t.scrollHeight - 2;
            }""")
            if done:
                print("阅读页已滑到底")
                break
        else:
            print("滚动超时（60步还没到底），继续尝试")
        # iframe内容滚完后：父页面可能也要滚（滚动条在父页面）
        if not is_main:
            try:
                frame.page.main_frame.evaluate("""() => {
                    const t = document.scrollingElement || document.documentElement;
                    if (t.scrollHeight > t.clientHeight + 5) {
                        t.scrollTo({top: t.scrollHeight, behavior: 'smooth'});
                    }
                }""")
                time.sleep(1.5)
                print("父页面也已滚到底")
            except:
                pass
        return True
    except Exception as e:
        print("滚动阅读失败:", e)
        return False

def find_all_video_frames(page):
    """找到页面里所有带video的frame（不管任务点状态/完成标记）。
    遍历 page.frames（Playwright返回页面所有frame，含嵌套iframe），
    7个视频任务点并存时能全部收集到。"""
    frames = []
    try:
        for f in page.frames:
            try:
                if f.locator("video#video_html5_api").count() > 0:
                    frames.append(f)
            except:
                pass
    except:
        pass
    seen = set()
    out = []
    for f in frames:
        if id(f) not in seen:
            seen.add(id(f))
            out.append(f)
    return out


# ===== 主循环：监视所有标签页 =====
def run(context):
    # 所有页面都自动接受原生弹窗（alert/confirm），防止卡住
    for pg in context.pages:
        pg.on("dialog", lambda d: d.accept())
    # 防死循环状态：记录上一次处理的页面URL，同一URL反复处理说明卡住了
    # （不能用page对象比较：学习通切章节不换标签页，同一page对象正常会反复出现）
    last_url = [None]
    stuck = [0]
    while True:
        # 1. 在所有标签页里找有视频的
        target = None
        for pg in context.pages:
            if find_frame(pg, "video#video_html5_api"):
                target = pg
                break

        if target:
            # 防死循环：同一URL反复处理说明"下一节"没跳成功，警告并暂停等用户干预
            if last_url[0] != target.url:
                last_url[0] = target.url
                stuck[0] = 0
            else:
                stuck[0] += 1
            if stuck[0] >= 4:
                print("⚠ 同一页面已反复处理4轮，可能卡住了（下一节没跳转或任务没被记录）")
                print("  等待30秒让你手动检查浏览器...")
                time.sleep(30)
                stuck[0] = 0
            # 页面上可能有多个视频任务点（多个视频iframe）：全部强制播放，并行计时
            vframes = []
            for f in target.frames:
                try:
                    if f.locator("video#video_html5_api").count() > 0:
                        vframes.append(f)
                except:
                    pass
            # ===== 简单策略（用户拍板）：不管任务点完成状态，找到全部视频，一个一个播 =====
            # 每个视频先试"拖进度条到末尾"（seek）：拖得动→秒过；拖不动→正常播放等结束
            all_frames = find_all_video_frames(target)
            if not all_frames:
                print("该页面没找到视频，直接处理阅读/下一节")
                rf = find_read_frame(target)
                if rf:
                    process_read_page(rf)
                print("当前页任务完成，进入下一节")
                click_next(target)
                time.sleep(3)
                continue
            print(f"找到 {len(all_frames)} 个视频，逐个播放")
            processed_srcs = set()   # 已播完的视频src（学习通重建iframe后靠src区分新旧，防重复播）
            played_count = 0
            while True:
                # 每次播完都重新扫描页面所有视频（学习通完成任务点后会重建/切换iframe）
                cur_frames = find_all_video_frames(target)
                vf = None
                for f in cur_frames:
                    try:
                        src = f.evaluate("() => { const v = document.querySelector('video'); return v ? (v.currentSrc || v.src || '') : ''; }")
                    except:
                        src = ''
                    if src and src in processed_srcs:
                        continue
                    vf = f
                    break
                if vf is None:
                    # 当前页面没有"没播过"的视频了 → 全站看看有没有新视频（可能新开标签/跳转）
                    nv = current_video_target(context)
                    if nv:
                        npg, nvf = nv
                        try:
                            nsrc = nvf.evaluate("() => { const v = document.querySelector('video'); return v ? (v.currentSrc || v.src || '') : ''; }")
                        except:
                            nsrc = ''
                        if nsrc and nsrc in processed_srcs:
                            print("所有视频已播完")
                            break
                        target, vf = npg, nvf
                    else:
                        print("所有视频已播完")
                        break
                played_count += 1
                stop_all_force_play(target)   # 先停掉所有旧哨兵（防多视频互相抢夺）
                inject_force_play(vf)
                ensure_playing(target, only_frames=[vf])
                # 等2秒让视频加载出来（iframe刚重建时duration还是0，立即seek会误判）
                time.sleep(2)
                # 先测"拖到末尾"：能拖就秒过
                if try_seek_to_end(vf):
                    print(f"第{played_count}个视频 seek成功，判定已完成，等待结束...")
                    if wait_video_ended(vf, timeout=60):
                        print("  视频已结束")
                    else:
                        print("  等待结束超时，但seek已生效，视为完成")
                else:
                    # seek拖不动（没加载/防快进）→ 正常播放等它播完
                    print(f"第{played_count}个视频 seek无效，判定未完成，正常播放等待...")
                    try:
                        dur = vf.locator("video#video_html5_api").first.evaluate("el => el.duration || 0") or 0
                    except:
                        dur = 0
                    wait_timeout = max(150, int(dur) * 2.5 + 60)
                    wait_start = time.time()
                    done_times = 0
                    tick = 0
                    while True:
                        if time.time() - wait_start > wait_timeout:
                            print(f"  等待超过{int(wait_timeout)}秒（视频{dur}s），强制跳过")
                            break
                        if video_frame_ended(vf):
                            done_times += 1
                            if done_times >= 3:
                                break
                        else:
                            done_times = 0
                        # 持续防暂停（只拉回当前frame的视频）
                        try:
                            vf.evaluate("""() => {
                                document.querySelectorAll('video').forEach(v => {
                                    if (v.paused && !v.ended) { v.muted = true; v.play().catch(()=>{}); }
                                });
                            }""")
                        except:
                            # frame失效（重建）→ 全站重新定位
                            try:
                                nv = current_video_target(context)
                                if nv:
                                    npg, nvf = nv
                                    if npg != target or nvf != vf:
                                        target, vf = npg, nvf
                                        inject_force_play(vf)
                                        ensure_playing(target, only_frames=[vf])
                            except:
                                pass
                        time.sleep(2)
                        tick += 1

                # 记录已播完的src（防重建后重播同一个）
                try:
                    src1 = vf.evaluate("() => { const v = document.querySelector('video'); return v ? (v.currentSrc || v.src || '') : ''; }")
                    if src1:
                        processed_srcs.add(src1)
                except:
                    pass
                print(f"第{played_count}个视频已播完")
            print("全部视频已播完")
            # 视频下方可能还有滑动/图文任务点（滚动图片/图文）：
            # 优先调 finishJob() 一键完成（跟PDF页一样），没有才回退到滚动
            rf = find_read_frame(target)
            if rf:
                print("发现阅读页（视频下方有滑动内容）:", rf.url[:70])
                try:
                    has_finish = rf.evaluate("() => typeof finishJob === 'function'")
                    if has_finish:
                        rf.evaluate("() => { try { finishJob(); } catch(e) {} }")
                        print("调用了 finishJob() 完成任务点（视频下方滑动内容）")
                        time.sleep(3)
                    else:
                        process_read_page(rf)
                except:
                    process_read_page(rf)
            print("当前页任务完成，进入下一节")
            click_next(target)
            time.sleep(3)
            continue

        # 2. 找有题目的标签页（作业/考试=.questionLi，章节测验=.TiMu）
        for pg in context.pages:
            if find_frame(pg, ".questionLi") or find_frame(pg, ".TiMu"):
                target = pg
                break
        if target:
            print("找到题目，开始答题")
            answer_question(target)
            time.sleep(2)
            click_next(target)
            time.sleep(3)
            continue

        # 3. 找阅读页（图文/电子书：从头滑到尾才算通过）
        rf = None
        for pg in context.pages:
            rf = find_read_frame(pg)
            if rf:
                target = pg
                break
        if rf:
            # 保护：知识卡页面刚打开时视频还没加载，等3秒确认没有视频再当阅读页处理
            # （否则多视频页面会被误当成滑动页面，先滑动再下一节，视频实际没播）
            if "knowledge/card" in rf.url or "screen/file" in rf.url:
                time.sleep(3)
                if find_frame(target, "video#video_html5_api"):
                    print("该页面其实有视频，走视频流程")
                    time.sleep(1)
                    continue
            print("发现阅读页:", rf.url[:70])
            process_read_page(rf)
            time.sleep(2)
            click_next(target)
            time.sleep(3)
            continue

        # 4. 都没有 → 等你手动开视频
        print("所有标签页都没有视频或题目，请打开视频页...")
        print("当前标签数:", len(context.pages), [p.url[:60] for p in context.pages])
        time.sleep(5)

# ===== 浏览器选择：谷歌 / Edge（自动探测安装路径，找不到手动输入）=====
def pick_browser():
    CHROME_CANDIDATES = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    EDGE_CANDIDATES = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    print("选择浏览器：")
    print("  1. 谷歌 Chrome")
    print("  2. Microsoft Edge")
    choice = input("输入序号(回车默认1): ").strip()
    cands, name = (EDGE_CANDIDATES, "Edge") if choice == "2" else (CHROME_CANDIDATES, "Chrome")
    for c in cands:
        if os.path.exists(c):
            print(f"找到 {name}: {c}")
            return c
    path = input(f"未找到 {name} 安装路径，请手动输入完整路径(.exe): ").strip()
    if path and os.path.exists(path):
        return path
    if path:
        print("路径不存在，改用Playwright自带Chromium")
    return None

# ===== 主程序 =====
with sync_playwright() as p:
    exe = pick_browser()
    if exe:
        context = p.chromium.launch_persistent_context(user_data_dir=profile_dir, headless=False, executable_path=exe)
    else:
        context = p.chromium.launch_persistent_context(user_data_dir=profile_dir, headless=False)

    # 监听新开的标签页（学习通点课程会开新标签）
    def on_new_page(new_page):
        new_page.on("dialog", lambda d: d.accept())
        print("检测到新标签:", new_page.url[:80])
    context.on("page", on_new_page)

    page = context.pages[0]   # 初始标签页
    page.goto("https://i.mooc.chaoxing.com/")
    input("登录后点进课程-视频章节，看到播放器后按enter...")
    time.sleep(3)
    try:
        run(context)
    except KeyboardInterrupt:
        print("已手动停止")
    except Exception:
        import traceback
        traceback.print_exc()
        try:
            input("脚本异常退出，按回车关闭窗口（把上面错误发给创作者）...")
        except:
            pass
