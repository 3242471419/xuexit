# 学习通刷课助手（windows版）

个人学习辅助脚本：自动播放视频任务点、自动答题、自动翻页跳转下一节。

> ⚠️ 免责声明：仅供个人学习研究使用。若因不合理操作出现不良记录或学习行为异常，概不负责。如作他用，所承受的法律责任一概与作者无关。使用即代表你同意上述观点。
> 并且你需要遵守GPLv3协议，不许二开，如若想二开需经作者允许，并且得开源。获取密钥赞助地址https://afdian.com/a/z_15963?utm_source=copylink&utm_medium=link

## 使用

Windows 用户可直接双击 **`shuake_xuexi.exe`** 运行（已打包 Playwright，无需装 Python）。

源码运行需要 Python 3.9+ 和 Playwright（驱动本机 Chrome/Edge）：

```bash
pip install playwright
playwright install
python shuake.1.py
```
如果想只使用除了自动刷题之外的功能，只需要在让你填入令牌的时候随意填写即可，后续获得令牌时可通过修改api_config.json文件中的api_key的值来使用
首次运行会询问你的令牌（`sk-` 开头，找作者），也可随意填写，之后自动保存配置。
如果连接不上服务器请找作者要新的地址。（如若不需要自动刷题可跳过这条内容）

## 功能

- 自动播放视频任务点（防暂停，播完自动下一个）
- 自动答题（解密题干 + AI 作答 + 提交）
- 阅读页自动滑动到底并 `finishJob()`
- 自动跳转下一节

## 项目结构

| 文件 | 说明 |
|---|---|
| `shuake_xuexi.exe` | Windows 免安装版，双击即用 |
| `shuake.1.py` |
| `body.json` | API 请求体测试示例 |

直接下载 `shuake_xuexi.exe` 即可使用；令牌找作者进行赞助可得：https://afdian.com/a/z_15963?utm_source=copylink&utm_medium=link。

## 许可证

本项目以 **GPLv3** 许可证开源。详见 [LICENSE](https://www.gnu.org/licenses/gpl-3.0.html)。
