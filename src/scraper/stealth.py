"""反自动化检测脚本 — 覆盖京东环境指纹检查点。"""

STEALTH_SCRIPT = r"""
// 1. 隐藏 webdriver 标记
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. 伪造 chrome 运行时
window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {} };

// 3. 伪造插件列表 (PDF/Flash)
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5]
});
Object.defineProperty(navigator, 'mimeTypes', {
    get: () => [1, 2]
});

// 4. 权限查询返回 prompt (非 denied)
const origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission, onchange: null }) :
        origQuery(parameters)
);

// 5. 语言和平台
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });

// 6. 硬件信息
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

// 7. 屏幕尺寸填充
Object.defineProperty(screen, 'availWidth', { get: () => screen.width });
Object.defineProperty(screen, 'availHeight', { get: () => screen.height });

// 8. 移除 headless 特有的 CSS 差异
document.documentElement.style.setProperty('--headless', '0');
"""
