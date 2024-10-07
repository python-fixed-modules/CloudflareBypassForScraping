import json
import re
import os
import urllib
import tempfile
import traceback
from urllib.parse import urlparse

from CloudflareBypasser import CloudflareBypasser
from DrissionPage import ChromiumPage, ChromiumOptions
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from typing import Dict, Union, List
import argparse, traceback

browser_path = "/usr/bin/google-chrome"
app = FastAPI()

javascript_code = """
const script = document.createElement('script');
script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onloadTurnstileCallback";
script.async = true;
script.defer = true;
document.head.appendChild(script);

const div = document.createElement('div');
div.id = "result";
div.style = "top: 0; z-index: 10010; position: absolute;"
document.body.appendChild(div);

window.onloadTurnstileCallback = function () {
  turnstile.render('#result', {
    sitekey: "<self.sitekey>",
    theme: 'dark',
    size: 'normal',
    callback: function(token) {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'cf-turnstile-response';
      input.value = token;
      document.querySelector('#result').prepend(input);
    },
  });
};
"""


# from https://github.com/FlareSolverr/FlareSolverr/blob/master/src/utils.py
def create_proxy_extension(proxy: dict) -> str:
    parsed_url = urllib.parse.urlparse(proxy['url'])
    scheme = parsed_url.scheme
    host = parsed_url.hostname
    port = parsed_url.port
    username = proxy['username']
    password = proxy['password']
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Chrome Proxy",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {"scripts": ["background.js"]},
        "minimum_chrome_version": "76.0.0"
    }
    """
    background_js = """
    var config = {
        mode: "fixed_servers",
        rules: {
            singleProxy: {
                scheme: "%s",
                host: "%s",
                port: %d
            },
            bypassList: ["localhost"]
        }
    };

    chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

    function callbackFn(details) {
        return {
            authCredentials: {
                username: "%s",
                password: "%s"
            }
        };
    }

    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        { urls: ["<all_urls>"] },
        ['blocking']
    );
    """ % (
        scheme,
        host,
        port,
        username,
        password
    )

    proxy_extension_dir = tempfile.mkdtemp()

    with open(os.path.join(proxy_extension_dir, "manifest.json"), "w") as f:
        f.write(manifest_json)

    with open(os.path.join(proxy_extension_dir, "background.js"), "w") as f:
        f.write(background_js)

    return proxy_extension_dir

# Function to bypass Cloudflare protection
def bypass_cloudflare(url: str, retries: int, log: bool, sitekey, timeout=60000, proxy=None) -> ChromiumPage:
    options = ChromiumOptions()
    options.set_argument("--auto-open-devtools-for-tabs", "true")
    #options.set_argument("--remote-debugging-port=9222")
    options.set_argument("--no-sandbox")  # Necessary for Docker
    options.set_argument("--disable-gpu")  # Optional, helps in some cases
    options.set_paths(browser_path=browser_path).headless(False)
    options.auto_port()

    # from https://github.com/FlareSolverr/FlareSolverr/blob/master/src/utils.py
    if proxy and "@" in proxy:
        proxy_dict = {
            "url": "http://{}".format(proxy.split("@")[1]),
            "username": proxy.split("://")[-1].split("@")[0].split(":")[0],
            "password": proxy.split("://")[-1].split("@")[0].split(":")[1]
        }
        proxy_extension_dir = create_proxy_extension(proxy_dict)
        options.add_extension(os.path.abspath(proxy_extension_dir))
    elif proxy:
        proxy_url = "http://{}".format(proxy.split("@")[1])
        options.set_argument("--proxy-server", proxy_url)
        
    driver = ChromiumPage(addr_or_opts=options)
    try:
        driver.get(url+ "/aubworubarwboab2urgu9fgobnjsfbjbasoigup") # random string to speed up load
        driver.run_js(javascript_code.replace("<self.sitekey>", sitekey))
        print("javascript is gone")
        cf_bypasser = CloudflareBypasser(driver, retries, log, timeout)
        result = cf_bypasser.bypass()
        driver.quit()
        return result
    except Exception as e:
        driver.quit()
        raise e

class RequestModel(BaseModel):
    sitekey: str
    url: str
    invisible: bool
    proxy: str = None

class ResponseModel(BaseModel):
    status: str
    token: Union[str, None]

@app.post("/solve")
async def solve(payload: RequestModel):
    try:
        result = bypass_cloudflare(payload.url, 15, log, payload.sitekey, proxy=payload.proxy)
        return ResponseModel(status="success", token=result)
    except Exception as e:
        traceback.print_exc()
        return ResponseModel(status="error", token=None)

# Main entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cloudflare bypass api")

    parser.add_argument("--nolog", action="store_true", help="Disable logging")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")

    args = parser.parse_args()
    if args.headless:
        from pyvirtualdisplay import Display

        display = Display(visible=0, size=(1920, 1080))
        display.start()
    if args.nolog:
        log = False
    else:
        log = True
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
