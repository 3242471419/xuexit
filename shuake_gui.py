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
import queue
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from playwright.sync_api import sync_playwright

gui = {
    "log_q": queue.Queue(),
    "input_q": queue.Queue(),
    "input_result": queue.Queue(),
    "stop": threading.Event(),      
    "paused": threading.Event(),    
    "ready_click": threading.Event(),
    "api_token": None,       
    "browser_path": None,    
}

AGREEMENT_TEXT = """使用这个工具需要不许二开，如若想二开需经作者允许，并且得开源。
若因不合理操作而出现不良记录或学习行为异常，概不负责。
如作他用，所承受的法律责任一概与作者无关，仅作为学习使用，
本项目是第三方工具，与学习通等官方无隶属关系，使用即代表你同意上述观点。

可以前往 https://afdian.com/a/z_15963 获取密钥（选择网址之后可以右键复制）。

此工具调用AI生成，AI生成结果需自行效验；
无人值守的刷课可能会有异常学习记录。"""

def ask_agreement(root):

    top = tk.Toplevel(root)
    top.title("使用协议")
    top.transient(root)
    top.grab_set()                    
    top.geometry("480x400")
    top.resizable(False, False)

    agreed = {"ok": False}
    def on_agree():
        agreed["ok"] = True
        top.destroy()
    def on_refuse():
        agreed["ok"] = False
        top.destroy()

    btn_bar = tk.Frame(top)
    btn_bar.pack(side="bottom", fill="x", padx=10, pady=10)
    tk.Button(btn_bar, text="不同意，退出", command=on_refuse,
              bg="#cccccc", relief="flat", padx=14, pady=4).pack(side="left")
    tk.Button(btn_bar, text="我同意", command=on_agree,
              bg="#2f7df6", fg="white", relief="flat", padx=18, pady=4).pack(side="right")

    txt = tk.Text(top, wrap="word", font=("Microsoft YaHei UI", 10),
                  padx=12, pady=8, relief="flat", bg="#f7f7f7")
    txt.insert("1.0", AGREEMENT_TEXT)
    txt.configure(state="disabled")
    txt.pack(fill="both", expand=True, padx=10, pady=(10, 4))

    root.wait_window(top)   
    return agreed["ok"]

class PrintRedirector:
    def __init__(self, log_q):
        self.log_q = log_q
    def write(self, s):
        if s:                       
            self.log_q.put(s)
    def flush(self):
        pass

sys.stdout = PrintRedirector(gui["log_q"])
sys.stderr = PrintRedirector(gui["log_q"])

if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
try:
    profile_dir = os.path.join(base_dir, "chaoxing_profile")
    os.makedirs(profile_dir, exist_ok=True)
except:
    print("chaoxing_profile创建写入本地文件失败,如果继续使用可能会有不知道的错误")

TABLE_SECRET = "shuashuashua_youhehehedjqopwiahdoiasdw"

VERSION = "v2.1-aria优先防误判"

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

    token = gui.get("api_token") or ""
    return DEFAULT_API_BASE, token

API_BASE, API_KEY = load_api_config()

def gui_request_input(prompt, validate=None):

    gui["input_q"].put({"prompt": prompt, "validate": validate})
    try:
        return gui["input_result"].get(timeout=86400)   
    except queue.Empty:
        return None

def gui_pause_point():

    while gui["paused"].is_set() and not gui["stop"].is_set():
        time.sleep(0.5)
    return not gui["stop"].is_set()

def gui_sleep(sec):

    end = time.time() + sec
    while time.time() < end:
        if gui["stop"].is_set():
            return False
        if gui["paused"].is_set():
            if not gui_pause_point():     
                return False
            end = time.time() + sec       
        time.sleep(0.5)
    return True

def re_input_api_config():

    global API_BASE, API_KEY
    print("=== 重新输入令牌（key 无效或过期）===")
    token = gui_request_input("你的令牌（sk-开头，可前往https://afdian.com/a/z_15963获取）: ",
                              validate=lambda v: v.strip().startswith("sk-"))
    if token is None:
        print("用户取消输入，跳过本题")
        return
    API_BASE, API_KEY = API_BASE, token.strip()
    _save_api_config()
    print("配置已更新并保存")

def ask_ai(question_text, allow_retry=True, style="choice", retry_count=0):

    global API_BASE, API_KEY
    prompt = (f"回答这道题，直接输出答案文字，不要解释、不要编号、不要输出选项字母。题目：{question_text}"
              if style == "text"
              else f"回答这道题，只输出答案的选项字母，不要输出任何其他内容。单选输出1个字母（如A），多选直接连写字母（如ABD），判断题选“对”输出A、选“错”输出B：{question_text}")
    try:
        resp = requests.post(
            f"{API_BASE}/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": "deepseek-flash",
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=120,
            verify=False
        )
    except requests.exceptions.RequestException as e:
        print("网络连接失败:", e)
        print("当前地址:", API_BASE)

        if allow_retry:
            print("5秒后自动重试一次...")
            time.sleep(5)
            return ask_ai(question_text, allow_retry=False, style=style)
        return ""

    if resp.status_code == 401:
        print("密钥错误：你输入的令牌无效或已过期（服务器返回 401）")
        print("请重新输入正确的 key（可前往https://afdian.com/a/z_15963获取）")
        re_input_api_config()
        if allow_retry:
            return ask_ai(question_text, allow_retry=False, style=style)
        return ""
    if resp.status_code == 403:
        try:
            msg = resp.json().get("error", {}).get("message", "")
        except Exception:
            msg = resp.text[:200]
        print(f"次数用尽或 key 无效（服务器：{msg}）")
        print("找作者获得，可前往https://afdian.com/a/z_15963")

        if allow_retry:
            print("5秒后自动重试一次...")
            time.sleep(5)
            return ask_ai(question_text, allow_retry=False, style=style)
        return ""
    if resp.status_code == 429:

        if allow_retry and retry_count < 2:
            print(f"请求太频繁或额度已用完（429），10秒后自动重试（第{retry_count+1}次）...")
            time.sleep(10)
            return ask_ai(question_text, allow_retry=False, style=style, retry_count=retry_count + 1)
        print("429 多次重试仍失败，跳过本题")
        return ""
    if resp.status_code != 200:
        print(f"API 返回错误({resp.status_code}): {resp.text[:300]}")
        print("跳过本题")
        return ""
    return resp.json()["choices"][0]["message"]["content"]

def find_frame(page, selector):
    for f in page.frames:
        try:
            if f.locator(selector).count() > 0:
                return f
        except:
            pass
    return None

def get_text(loc):

    try:
        raw = loc.evaluate("e => encodeURIComponent(e.innerText)")
        return urllib.parse.unquote(raw).strip()
    except:
        return ""

_font_decrypt_map = {}        
_font_parsed_keys = set()     

def _keystream(key, iv, length):

    out = bytearray()
    block = 0
    while len(out) < length:
        out.extend(hashlib.sha256(key + iv + str(block).encode()).digest())
        block += 1
    return bytes(out[:length])

def _get_embedded_table():

    try:
        from enc_table import ENCRYPTED_TABLE
        return ENCRYPTED_TABLE
    except Exception:
        pass

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

    if float(v).is_integer():
        return int(v)
    return float(v)

def _typr_draw(glyf, name, cmds, crds):

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
        return {}   
    return mapping

def decrypt_text(text, mapping):

    if not mapping:
        return text
    return "".join(chr(mapping.get(ord(ch), ord(ch))) for ch in text)

def answer_question(page):
    frame = find_frame(page, ".questionLi") or find_frame(page, ".TiMu")
    if not frame:
        print("没找到题目（.questionLi 和 .TiMu 都没有）")
        return
    print("题目frame:", frame.url[:100])
    sel = ".questionLi" if frame.locator(".questionLi").count() > 0 else ".TiMu"
    questions = frame.locator(sel).all()
    print(f"找到{len(questions)}道题")

    global _font_decrypt_map, _font_parsed_keys
    import base64 as _b64
    if not _font_parsed_keys:
        time.sleep(2)   
    b64s, urls = [], []
    for f in page.frames:            
        r = extract_encrypted_fonts(f)
        b64s.extend(r.get("b64", []))
        urls.extend(r.get("url", []))
    for u in urls:   
        try:

            if not u.startswith("http://") and not u.startswith("https://"):
                u = urllib.parse.urljoin(page.url, u)
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

        opts = []
        opt_texts = []
        for sel_opt in ['[class*="before-after"]', ".answerBg", "td", "li"]:
            opts = q.locator(sel_opt).all()
            pairs = [(o, decrypt_text(get_text(o), _font_decrypt_map)) for o in opts]
            pairs = [(o, t) for o, t in pairs if t]   
            if pairs:
                opts = [o for o, _ in pairs]
                opt_texts = [t for _, t in pairs]
                break
        print("选项:", [t[:30] for t in opt_texts])
        ans_clean = re.sub(r"[。．.!！?？\s]+$", "", ans.strip())
        clicked = False

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

            inp = None
            for sel_inp in ["textarea", "input[type='text']", "div[contenteditable='true']"]:
                try:
                    if q.locator(sel_inp).count() > 0:
                        inp = q.locator(sel_inp).first
                        break
                except:
                    pass
            if inp is None:
                try:   
                    frame_el = q.locator("iframe").first
                    inner = frame_el.content_frame()
                    body = inner.locator("body[contenteditable='true']")
                    if body.count() > 0:
                        inp = body.first
                except:
                    pass
            if inp is not None:
                txt_ans = ask_ai(text, style="text").strip()
                print("简答题AI答案:", txt_ans[:80])
                if txt_ans:
                    try:
                        tag = inp.evaluate("e => e.tagName")
                        if tag in ("TEXTAREA", "INPUT"):
                            inp.fill(txt_ans, timeout=8000)
                        else:
                            inp.evaluate("(e, v) => { e.textContent = v; e.dispatchEvent(new Event('input', {bubbles:true})); }", txt_ans)
                        print("简答题答案已填入")
                        clicked = True
                    except Exception as e:
                        print("简答题填入失败:", str(e)[:80])

                        print("将等待60秒给用户输入，之后该题跳过，AI答案:", txt_ans[:80])
                        time.sleep(60)
                        print("等待完成，下一题")
            else:
                print("没匹配到选项，答案:", ans_clean[:40])

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

    if submitted:
        if not wait_task_finished(page, frame):
            print("  ⚠ 答题任务点未标记完成（可能提交未成功或服务端记录中），继续流程")

def inject_force_play(frame):

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
        print("已注入强制播放")
    except Exception as e:
        print("注入失败:", e)

def stop_all_force_play(page):

    try:

        for pg in page.context.pages:
            for f in pg.frames:
                try:
                    f.evaluate("""() => {
                        if (window.__abc_interval) { clearInterval(window.__abc_interval); window.__abc_interval = null; }
                        if (window.__abc_skip) { clearInterval(window.__abc_skip); window.__abc_skip = null; }
                    }""")
                except:
                    pass
    except:
        pass

def is_playing(page):
    frame = find_frame(page, "#video")
    if not frame:
        return False
    cls = frame.locator("#video").get_attribute("class") or ""
    return "vjs-playing" in cls

def ensure_playing(page, only_frames=None):

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

    try:
        v = vf.locator("video#video_html5_api").first
        info = v.evaluate("""(el) => {
            if (!el || !el.duration || el.duration <= 0 || isNaN(el.duration)) return {ok: false};
            if (el.ended) return {ok: true, reason: 'already_ended'};
            const target = el.duration - 2;
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

    start = time.time()

    while time.time() - start < timeout and not gui["stop"].is_set():
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

    global _enumerate_diag_done
    try:

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
                    continue   

                finished = bool(info.get("finished")) or video_progress_done(f)
                result.append((f, finished))
            except:
                pass

        if catalog_flags and len(catalog_flags) == len(result):
            for i, (f, fin) in enumerate(result):
                if catalog_flags[i]:
                    result[i] = (f, True)
        elif catalog_flags:
            print(f"[诊断] 目录完成标记{len(catalog_flags)}个 vs 视频任务点{len(result)}个，顺序不匹配，本次跳过目录判定")

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
                mark_info = page.evaluate(r"""() => {
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
                        return False    
        except:
            pass
    return any_video

def all_video_tasks_done(page):

    scan_js = """() => {
        const cts = document.querySelectorAll('.ans-attach-ct.videoContainer');
        if (!cts.length) return null;
        let anyTodo = false;
        for (const ct of cts) {
            const cc = (ct.className || '');
            if (cc.indexOf('ans-job-finished') !== -1 || cc.indexOf('icon_Completed') !== -1
                || ct.getAttribute('data-completed') === 'true' || ct.getAttribute('data-task-completed') === 'true') continue;
            if (ct.getAttribute('data-completed') === 'false') { anyTodo = true; continue; }
            const icon = ct.querySelector('.ans-job-icon');
            if (icon) {
                // aria 优先（2026-10-20 实测：视频未完成也带 id → 先看 aria 再兜底 id）
                const lbl = icon.getAttribute('aria-label');
                if (lbl === '任务点已完成') continue;
                if (lbl === '任务点未完成') { anyTodo = true; continue; }
                if (icon.hasAttribute('id')) continue;
            }
            anyTodo = true;
        }
        return anyTodo ? false : true;
    }"""
    frames = [page.main_frame]
    for f in page.frames:
        if f != page.main_frame:
            frames.append(f)
    for f in frames:
        try:
            r = f.evaluate(scan_js)
            if r is not None:
                return r
        except Exception:
            continue
    return None

def task_container_done(page, frame):

    f = frame
    for _ in range(12):          
        try:
            el = f.frame_element()      
        except Exception:
            break
        try:
            r = el.evaluate("""(el) => {
                const ct = el.closest('.ans-attach-ct,[data-course-task]');
                if (!ct) return null;
                const cc = (ct.className || '');
                // 完成标记（courseTaskComplete 集合）
                if (cc.indexOf('ans-job-finished') !== -1 || cc.indexOf('icon_Completed') !== -1
                    || ct.getAttribute('data-completed') === 'true' || ct.getAttribute('data-task-completed') === 'true') return true;
                if (ct.getAttribute('data-completed') === 'false') return false;
                // 短标签（courseTaskLabel）：容器内可见纯文本
                for (const t of ct.querySelectorAll('span,em,p,div')) {
                    if (t.children.length) continue;
                    const tx = (t.textContent || '').replace(/\\s+/g, '');
                    if (tx === '任务点已完成') return true;
                    if (tx === '任务点') return false;
                }
                // 图标：aria-label 优先（2026-10-20 实测：视频任务点未完成也带 id，如 ext-gen1051，
                //   不能只认 id；aria="任务点未完成" 时必须是未完成）
                //   aria 明确 → 按 aria；无 aria 才用 id 兜底（答题任务点实测：完成有 id、未完成无 id）
                const icon = ct.querySelector('.ans-job-icon');
                if (icon) {
                    const lbl = icon.getAttribute('aria-label');
                    if (lbl === '任务点已完成') return true;
                    if (lbl === '任务点未完成') return false;
                    if (icon.hasAttribute('id')) return true;
                    return false;
                }
                return null;
            }""")
            if r is not None:
                return r
        except Exception:
            pass
        f = f.parent_frame
        if not f:
            break
    return None

def job_task_done(page, frame):

    r = task_container_done(page, frame)
    if r is not None:
        return r

    try:
        txt = frame.locator(".testTit_status").first.text_content(timeout=2000)
        if txt and re.search(r"^\s*(已完成|已提交|提交成功)", txt.strip()):
            return True
    except Exception:
        pass
    return None

def wait_task_finished(page, frame, timeout=45):

    start = time.time()
    while time.time() - start < timeout and not gui["stop"].is_set():
        st = job_task_done(page, frame)
        if st is True:
            print("  ✔ 任务点已标记完成（ans-job-finished）")
            return True
        if st is None:      
            return True
        gui_sleep(3)
    return False

def click_next(page):
    sels = ["#prevNextFocusNext",
            ".jb_btn.jb_btn_92.fr.fs14.nextChapter",
            "text=下一节", "text=下一章",
            "a:has-text('下一节')", "a:has-text('下一章')",
            "button:has-text('下一节')", "button:has-text('下一章')"]

    for sel in sels:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(no_wait_after=True)
                print(f"点了下一节（{sel}）")
                return
        except:
            pass

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

def find_read_frame(page):

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

    ok = scroll_read_page(frame)
    if not ok:
        return False

    need = get_book_required_seconds(frame)
    if need > 0:
        print(f"计时阅读任务点：滚动完成，还需保持约 {need} 秒（请勿切换页面）")
        waited = 0
        while waited < need:
            time.sleep(5)
            waited += 5
        print("计时阅读完成")
    else:
        print("阅读页已处理完，等待任务记录完成...")
        time.sleep(1)
    return True

def scroll_read_page(frame):

    is_main = (frame == frame.page.main_frame)
    try:

        frame.evaluate("""() => {
            const bc = document.querySelector('.preview-section .book-mark .book-container');
            if (bc && bc.scrollHeight > bc.clientHeight + 5) { window.__rt = bc; return; }
            const els = Array.from(document.querySelectorAll('*'))
                .filter(e => e.scrollHeight > e.clientHeight + 5)
                .sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
            window.__rt = els.length ? els[0] : (document.scrollingElement || document.documentElement);
        }""")
        for _ in range(60):   

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

def run(context):

    for pg in context.pages:
        pg.on("dialog", lambda d: d.accept())

    last_url = [None]
    stuck = [0]

    while not gui["stop"].is_set():

        target = None
        for pg in context.pages:
            if find_frame(pg, "video#video_html5_api"):
                target = pg
                break

        if target:

            if last_url[0] != target.url:
                last_url[0] = target.url
                stuck[0] = 0
            else:
                stuck[0] += 1
            if stuck[0] >= 4:
                print("⚠ 同一页面已反复处理4轮，可能卡住了（下一节没跳转或任务没被记录）")
                print("  等待30秒让你手动检查浏览器...")
                gui_sleep(30)
                stuck[0] = 0

            all_frames = find_all_video_frames(target)
            if not all_frames:
                print("奇怪，该页面没找到视频，退出查找视频")
                gui_sleep(3)
                continue
            print(f"找到 {len(all_frames)} 个视频，逐个播放")
            processed_srcs = set()   
            played_count = 0

            while not gui["stop"].is_set():

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

                try:
                    presrc = vf.evaluate("() => { const v = document.querySelector('video'); return v ? (v.currentSrc || v.src || '') : ''; }")
                    if presrc:
                        processed_srcs.add(presrc)
                except:
                    pass

                if task_container_done(target, vf) is True:
                    print(f"第{played_count}个视频 任务点已完成（跳过播放）")
                    continue
                stop_all_force_play(target)   
                inject_force_play(vf)
                ensure_playing(target, only_frames=[vf])

                print("等待3秒让视频加载")
                gui_sleep(3)

                print(f"第{played_count}个视频 正常播放等待...")
                try:
                    dur = vf.locator("video#video_html5_api").first.evaluate("el => el.duration || 0") or 0
                except:
                    dur = 0
                wait_timeout = max(150, int(dur) * 2.5 + 60)
                wait_start = time.time()
                done_times = 0

                while not gui["stop"].is_set():
                    if time.time() - wait_start > wait_timeout:
                        print(f"  等待超过{int(wait_timeout)}秒（视频{dur}s），强制跳过")
                        break
                    if video_frame_ended(vf):
                        done_times += 1
                        if done_times >= 3:
                            break
                    else:
                        done_times = 0
                    if task_container_done(target, vf) is True:
                        print("  ✔ 任务点已标记完成（DOM 判定）")
                        break

                    try:
                        vf.evaluate("""() => {
                            document.querySelectorAll('video').forEach(v => {
                                if (v.paused && !v.ended) { v.muted = true; v.play().catch(()=>{}); }
                            });
                        }""")
                    except:

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
                    gui_sleep(2)

                print(f"第{played_count}个视频已播完")

                if not wait_task_finished(target, vf):
                    print(f"  ⚠ 第{played_count}个视频播完但任务点未标记完成，继续下一个（事后可在网页检查）")
            print("全部视频已播完")

            if all_video_tasks_done(target) is False:
                print("⚠ 仍有任务点未标记完成，等待服务端记录（最多30秒）...")
                for _ in range(10):
                    gui_sleep(3)
                    if all_video_tasks_done(target) is not False:
                        print("✔ 全部任务点已标记完成")
                        break

            rf = find_read_frame(target)
            if rf: 
                print("查找视频页中有阅读页...")
                print("发现阅读页（视频下方有滑动内容）:", rf.url[:70])
                try:
                    has_finish = rf.evaluate("() => typeof finishJob === 'function'")
                    if has_finish:
                        rf.evaluate("() => { try { finishJob(); } catch(e) {} }")
                        print("调用了 finishJob() 完成任务点（视频下方滑动内容）")
                        gui_sleep(3)
                    else:
                        process_read_page(rf)
                except:
                    process_read_page(rf)
            timu1=find_frame(target, ".questionLi")
            timu2=find_frame(target, ".TiMu")
            if timu1 or timu2:
                qf = timu1 or timu2

                if job_task_done(target, qf) is True:
                    print("该题目任务点已完成（ans-job-finished），跳过答题")
                else:
                    print("查找视频页中有题目页")
                    answer_question(target)
                    gui_sleep(2)

            print("当前页任务完成，进入下一节")
            click_next(target)
            gui_sleep(3)
            continue

        target = None
        qf = None
        for pg in context.pages:
            f = find_frame(pg, ".questionLi") or find_frame(pg, ".TiMu")
            if f:
                target, qf = pg, f
                break
        if target:

            _jd = job_task_done(target, qf)
            print("答题完成判定:", _jd, "（True=已完成跳过 / False=未完成答题 / None=页面无测验容器）")
            if _jd is True:
                print("该题目任务点已完成，跳过答题")
            else:
                print("找到题目，开始答题")
                answer_question(target)
            gui_sleep(2)
            click_next(target)
            gui_sleep(2)
            continue

        rf = None
        for pg in context.pages:
            rf = find_read_frame(pg)
            if rf:
                target = pg
                break
        if rf:

            if "knowledge/card" in rf.url or "screen/file" in rf.url:
                gui_sleep(3)
                if find_frame(target, "video#video_html5_api"):
                    print("该页面有视频，走视频流程")
                    gui_sleep(1)
                    continue
            print("发现阅读页:", rf.url[:70])
            process_read_page(rf)
            gui_sleep(2)
            timu1=find_frame(target, ".questionLi")
            timu2=find_frame(target, ".TiMu")
            if timu1 or timu2:
                qf = timu1 or timu2

                if job_task_done(target, qf) is True:
                    print("该题目任务点已完成（ans-job-finished），跳过答题")
                else:
                    print("查找阅读页中有题目页")
                    answer_question(target)
                    gui_sleep(2)
            print("阅读页已完成，下一节")
            click_next(target)
            gui_sleep(3)
            continue

        print("所有标签页都没有视频或题目，请打开视频页...")
        print("当前标签数:", len(context.pages), [p.url[:60] for p in context.pages])
        gui_sleep(5)

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

def pick_browser():

    if gui.get("browser_path"):
        return gui["browser_path"]
    for c in (CHROME_CANDIDATES + EDGE_CANDIDATES):
        if os.path.exists(c):
            print("自动探测到浏览器:", c)
            return c
    return None

def run_main():

    print("========== 刷课工具启动 ==========")
    print("版本:", VERSION)
    with sync_playwright() as p:
        exe = pick_browser()
        if exe:
            context = p.chromium.launch_persistent_context(user_data_dir=profile_dir, headless=False, executable_path=exe)
        else:
            print("未找到浏览器，使用 playwright 内置浏览器。")
            context = p.chromium.launch_persistent_context(user_data_dir=profile_dir, headless=False)

        def on_new_page(new_page):
            new_page.on("dialog", lambda d: d.accept())
            print("检测到新标签:", new_page.url[:80])
        context.on("page", on_new_page)

        page = context.pages[0]   
        page.goto("https://i.mooc.chaoxing.com/")
        print("请在浏览器里登录；登录后回到窗口点『登录完成，开始刷课』")

        gui["ready_click"].wait()
        if gui["stop"].is_set():
            print("已停止，浏览器关闭")
            return
        time.sleep(3)
        try:
            run(context)
        except KeyboardInterrupt:
            print("已手动停止")
        except Exception:
            import traceback
            traceback.print_exc()
            print("脚本异常退出，请把上面错误发给创作者")
    print("刷课线程已结束")

class ShuakeGUI:

    def __init__(self, root):
        self.root = root
        root.title("ai脚本助手")
        root.geometry("760x560")
        root.minsize(680, 500)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.worker = None
        self.running = False
        self.paused = False      

        cfg = tk.LabelFrame(root, text=" 配置 ", font=("Microsoft YaHei UI", 10), padx=8, pady=6)
        cfg.pack(fill="x", padx=10, pady=(10, 4))

        row1 = tk.Frame(cfg)
        row1.pack(fill="x", pady=2)
        tk.Label(row1, text="AI令牌(sk-开头):", font=("Microsoft YaHei UI", 9)).pack(side="left")
        self.token_var = tk.StringVar()
        tk.Entry(row1, textvariable=self.token_var, width=44, show="*").pack(side="left", padx=6)

        row2 = tk.Frame(cfg)
        row2.pack(fill="x", pady=2)
        tk.Label(row2, text="浏览器:", font=("Microsoft YaHei UI", 9)).pack(side="left")
        self.browser_var = tk.StringVar(value="chrome")
        tk.Radiobutton(row2, text="Chrome", variable=self.browser_var, value="chrome").pack(side="left")
        tk.Radiobutton(row2, text="Edge", variable=self.browser_var, value="edge").pack(side="left", padx=4)
        tk.Radiobutton(row2, text="自定义", variable=self.browser_var, value="custom").pack(side="left", padx=4)
        self.path_var = tk.StringVar()
        tk.Entry(row2, textvariable=self.path_var, width=34).pack(side="left", padx=6)
        self.path_hint = tk.Label(row2, text="（自定义时填 .exe 完整路径）", fg="#888888",
                                  font=("Microsoft YaHei UI", 8))
        self.path_hint.pack(side="left")

        btns = tk.Frame(root)
        btns.pack(fill="x", padx=10, pady=4)
        self.btn_start = tk.Button(btns, text="开始刷课", command=self.on_start,
                                   bg="#2f7df6", fg="white", relief="flat", padx=16, pady=4)
        self.btn_start.pack(side="left")
        self.btn_stop = tk.Button(btns, text="停止", command=self.on_stop,
                                  bg="#e74c3c", fg="white", relief="flat", padx=16, pady=4, state="disabled")
        self.btn_stop.pack(side="left", padx=8)
        self.btn_ready = tk.Button(btns, text="登录完成，开始刷课", command=self.on_ready,
                                   bg="#27ae60", fg="white", relief="flat", padx=16, pady=4, state="disabled")
        self.btn_ready.pack(side="left", padx=8)

        log_frame = tk.LabelFrame(root, text=" 运行日志 ", font=("Microsoft YaHei UI", 10), padx=6, pady=4)
        log_frame.pack(fill="both", expand=True, padx=10, pady=4)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap="word", state="disabled",
                                                  font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_configure("ok", foreground="#7ec699")
        self.log_text.tag_configure("err", foreground="#e06c75")
        self.log_text.tag_configure("warn", foreground="#e5c07b")
        self.log_text.tag_configure("info", foreground="#61afef")

        self.status_var = tk.StringVar(value="就绪：填好令牌 → 选浏览器 → 点『开始刷课』")
        tk.Label(root, textvariable=self.status_var, anchor="w", relief="sunken",
                 font=("Microsoft YaHei UI", 9)).pack(fill="x", side="bottom")

        try:
            cfg_path = os.path.join(base_dir, "api_config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, encoding="utf-8") as f:
                    saved = json.load(f)
                if saved.get("api_key", "").startswith("sk-"):
                    self.token_var.set(saved["api_key"])
        except:
            pass

        self.root.after(100, self.poll_queues)

    def append_log(self, msg):

        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg)

        if "⚠" in msg or "失败" in msg or "错误" in msg or "异常" in msg:
            self.log_text.tag_add("err", "end-%dc" % (len(msg) + 1), "end-1c")
        elif "完成" in msg or "成功" in msg or "已播完" in msg:
            self.log_text.tag_add("ok", "end-%dc" % (len(msg) + 1), "end-1c")
        elif "等待" in msg or "尝试" in msg or "重试" in msg:
            self.log_text.tag_add("warn", "end-%dc" % (len(msg) + 1), "end-1c")
        else:
            self.log_text.tag_add("info", "end-%dc" % (len(msg) + 1), "end-1c")
        self.log_text.see("end")

        if int(self.log_text.index("end-1c").split(".")[0]) > 4000:
            self.log_text.delete("1.0", "1500.0")
        self.log_text.configure(state="disabled")

    def poll_queues(self):

        try:
            while True:
                msg = gui["log_q"].get_nowait()
                self.append_log(msg)
        except queue.Empty:
            pass

        try:
            req = gui["input_q"].get_nowait()
            val = simpledialog.askstring("需要输入", req["prompt"], parent=self.root)
            validate = req.get("validate")
            while val is not None and validate and not validate(val):
                messagebox.showwarning("输入不合法", "格式不对，请重新输入（sk- 开头）", parent=self.root)
                val = simpledialog.askstring("需要输入", req["prompt"], parent=self.root)
            gui["input_result"].put(val if val is not None else None)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_queues)

    def detect_browser(self):

        choice = self.browser_var.get()
        if choice == "custom":
            p = self.path_var.get().strip()
            if p and os.path.exists(p):
                return p
            if p:
                messagebox.showwarning("路径不存在", f"没有找到：{p}\n将改用 Playwright 内置浏览器", parent=self.root)
            return None
        cands = CHROME_CANDIDATES if choice == "chrome" else EDGE_CANDIDATES
        for c in cands:
            if os.path.exists(c):
                return c
        messagebox.showwarning("未找到浏览器", f"未探测到{choice.title()}安装路径\n可改选其他浏览器或填自定义路径", parent=self.root)
        return None

    def on_start(self):

        if self.running and not self.paused:
            return
        if not self.running:

            token = self.token_var.get().strip()
            if not token.startswith("sk-"):
                messagebox.showwarning("令牌错误", "AI令牌需要以 sk- 开头（可前往https://afdian.com/a/z_15963获取）", parent=self.root)
                return
            global API_BASE, API_KEY
            gui["api_token"] = token
            API_BASE, API_KEY = DEFAULT_API_BASE, token
            try:
                _save_api_config()
            except:
                pass
            gui["browser_path"] = self.detect_browser()
            if not gui["browser_path"]:
                self.append_log("提示：未找到 Chrome/Edge，将使用 Playwright 内置浏览器（第一次会下载）\n")

            gui["stop"].clear()
            gui["paused"].clear()
            gui["ready_click"].clear()
            self.paused = False
            self.running = True
            self.append_log("========== 开始刷课 ==========\n")
            self.set_status("运行中：浏览器已启动，登录后点『登录完成，开始刷课』")
            self.btn_start.configure(state="disabled")
            self.btn_ready.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.worker = threading.Thread(target=run_main, daemon=True)
            self.worker.start()
        else:

            gui["paused"].clear()
            self.paused = False
            self.append_log("========== 继续刷课 ==========\n")
            self.set_status("运行中：已恢复刷课")
            self.btn_start.configure(text="开始刷课", state="disabled")
            self.btn_ready.configure(state="disabled")
            self.btn_stop.configure(state="normal")

    def on_ready(self):

        if self.running and not self.paused:
            gui["ready_click"].set()
            self.btn_ready.configure(state="disabled")
            self.btn_stop.configure(state="normal")   
            self.set_status("运行中：刷课循环已开始，可随时点『停止』")

    def on_stop(self):

        if not self.running or self.paused:
            return
        gui["paused"].set()
        self.paused = True
        self.append_log("---- 已停止（暂停）：刷课循环挂起，浏览器保持，可点『继续刷课』 ----\n")
        self.set_status("已停止（暂停）：浏览器保持，点『继续刷课』接着刷")
        self.btn_start.configure(text="继续刷课", state="normal")
        self.btn_stop.configure(state="disabled")

    def on_close(self):

        if self.running:
            gui["paused"].clear()      
            gui["stop"].set()
            gui["ready_click"].set()   
            if self.worker and self.worker.is_alive():
                self.worker.join(timeout=5)   
        self.root.destroy()

    def set_status(self, text):
        self.status_var.set(text)

def main():

    root = tk.Tk()
    app = ShuakeGUI(root)

    if not ask_agreement(root):
        root.destroy()
        return
    root.mainloop()

if __name__ == "__main__":
    main()
#（注：内容由AI生成）
