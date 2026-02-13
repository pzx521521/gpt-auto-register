import random

class FingerprintManager:
    def __init__(self, driver):
        self.driver = driver
        self.current_script_id = None

    def update_identity(self):
        """手动触发：更新浏览器指纹身份"""
        # 清理环境，确保切换彻底
        self.driver.delete_all_cookies()
        self.driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")

        # 1. 移除旧脚本
        if self.current_script_id:
            try:
                self.driver.execute_cdp_cmd("Page.removeScriptToEvaluateOnNewDocument", {
                    "identifier": self.current_script_id
                })
            except:
                pass

        # 2. 生成随机种子
        seed = random.random()
        print(f"Python 端生成的随机种子: {seed}")

        # 3. 重新注入伪造脚本
        # 增加对 toDataURL 的劫持，这是 FingerprintJS 的核心
        # 增加对 Audio 指纹的微调
        script_source = f"""
        (function() {{
            // 唯一标识符，防止 CDP 缓存脚本
            const scriptInstanceId = "{random.randint(1000, 9999)}";
            const seed = {seed};
            console.log("脚本实例: " + scriptInstanceId + " | 种子: " + seed);

            // --- 1. Canvas 劫持 (核心) ---
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {{
                const ctx = this.getContext('2d');
                if (ctx) {{
                    // 在画布左上角注入一个肉眼不可见的像素噪音
                    // 只要改动一个像素，整个 canvas 的 hash 就会彻底改变
                    ctx.fillStyle = "rgba(" + Math.floor(seed * 255) + ", 0, 0, 0.01)";
                    ctx.fillRect(0, 0, 1, 1);
                }}
                return originalToDataURL.apply(this, arguments);
            }};

            // --- 2. 字体偏好劫持 ---
            const originalOffsetWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth').get;
            Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {{
                get: function() {{
                    const w = originalOffsetWidth.call(this);
                    if (this.innerText === 'mmwwiiSSLL11ii77IIOO00') {{
                        return w + (seed * 0.1); 
                    }}
                    return w;
                }}
            }});

            // --- 3. 音频指纹劫持 (可选，增强随机性) ---
            const originalGetChannelData = AudioBuffer.prototype.getChannelData;
            AudioBuffer.prototype.getChannelData = function() {{
                const data = originalGetChannelData.apply(this, arguments);
                for (let i = 0; i < data.length; i += 100) {{
                    data[i] += (seed * 0.0000001); // 极其微小的噪音
                }}
                return data;
            }};

            // --- 4. 抹除自动化特征 ---
            Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});
        }})();
        """

        result = self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": script_source}
        )

        self.current_script_id = result['identifier']
        print(f"身份已更新，CDP 内部标识符: {self.current_script_id}")