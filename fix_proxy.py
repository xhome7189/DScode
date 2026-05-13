"""
代理修复工具
清除 Lingma / 其他AI助手的代理设置，避免干扰网络请求
"""
import os
import sys


def clear_proxy_env():
    """清除所有代理环境变量"""
    proxy_vars = [
        'http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY',
        'NO_PROXY', 'no_proxy', 'all_proxy', 'ALL_PROXY',
        'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE'
    ]
    cleared = []
    for var in proxy_vars:
        if var in os.environ:
            val = os.environ.pop(var, None)
            cleared.append(f"{var}={val}")
    return cleared


def disable_proxy_for_requests():
    """让requests库绕过代理"""
    os.environ['no_proxy'] = '*'
    os.environ['NO_PROXY'] = '*'

    # 设置requests不使用代理
    import requests
    # 修改默认session
    original_init = requests.Session.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.trust_env = False  # 忽略环境变量中的代理

    requests.Session.__init__ = patched_init

    # 修改get/post等快捷方法 - 保存原始引用避免递归
    _orig_methods = {}
    for method_name in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
        original_method = getattr(requests, method_name, None)
        if original_method:
            _orig_methods[method_name] = original_method

    for method_name, original_method in _orig_methods.items():
        def make_patched(m_name, orig_func):
            def patched(url, *a, **kw):
                kw.setdefault('proxies', {})
                kw['proxies'].update({
                    'http': None,
                    'https': None,
                })
                return orig_func(url, *a, **kw)
            return patched

        setattr(requests, method_name, make_patched(method_name, original_method))


def apply():
    """应用所有代理修复"""
    cleared = clear_proxy_env()
    if cleared:
        print(f"[fix_proxy] 已清除代理: {', '.join(cleared)}")
    try:
        disable_proxy_for_requests()
        print("[fix_proxy] requests代理已禁用")
    except ImportError:
        pass


if __name__ == '__main__':
    apply()
