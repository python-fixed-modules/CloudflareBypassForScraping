import json
import re
import os
import urllib
import tempfile
from urllib.parse import urlparse

from CloudflareBypasser import CloudflareBypasser
from DrissionPage import ChromiumPage, ChromiumOptions
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from typing import Dict, Union, List
import argparse

# Chromium options arguments
arguments = [
    # "--remote-debugging-port=9222",  # Add this line for remote debugging
    "-no-first-run",
    "-force-color-profile=srgb",
    "-metrics-recording-only",
    "-password-store=basic",
    "-use-mock-keychain",
    "-export-tagged-pdf",
    "-no-default-browser-check",
    "-disable-background-mode",
    "-enable-features=NetworkService,NetworkServiceInProcess,LoadCryptoTokenExtension,PermuteTLSExtensions",
    "-disable-features=FlashDeprecationWarning,EnablePasswordsAccountStorage",
    "-deny-permission-prompts",
    "-disable-gpu",
    "-accept-lang=en-US",
    #"-incognito" # You can add this line to open the browser in incognito mode by default 
]

browser_path = "/usr/bin/google-chrome"
app = FastAPI()


# Pydantic model for the response
class CookieResponse(BaseModel):
    cookies: Dict[str, str]
    user_agent: str


# Function to check if the URL is safe
def is_safe_url(url: str) -> bool:
    parsed_url = urlparse(url)
    ip_pattern = re.compile(
        r"^(127\.0\.0\.1|localhost|0\.0\.0\.0|::1|10\.\d+\.\d+\.\d+|172\.1[6-9]\.\d+\.\d+|172\.2[0-9]\.\d+\.\d+|172\.3[0-1]\.\d+\.\d+|192\.168\.\d+\.\d+)$"
    )
    hostname = parsed_url.hostname
    if (hostname and ip_pattern.match(hostname)) or parsed_url.scheme == "file":
        return False
    return True

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
def bypass_cloudflare(url: str, retries: int, log: bool, timeout=60000, proxy=None) -> ChromiumPage:
    options = ChromiumOptions()
    options.set_argument("--auto-open-devtools-for-tabs", "true")
    #options.set_argument("--remote-debugging-port=9222")
    options.set_argument("--no-sandbox")  # Necessary for Docker
    options.set_argument("--disable-gpu")  # Optional, helps in some cases
    options.set_paths(browser_path=browser_path).headless(False)
    options.auto_port()

    # from https://github.com/FlareSolverr/FlareSolverr/blob/master/src/utils.py
    if proxy and all(key in proxy for key in ['url', 'username', 'password']):
        proxy_extension_dir = create_proxy_extension(proxy)
        #options.set_argument("--load-extension", os.path.abspath(proxy_extension_dir))
        options.add_extension(os.path.abspath(proxy_extension_dir))
    elif proxy and 'url' in proxy:
        proxy_url = proxy['url']
        # logging.debug("Using webdriver proxy: %s", proxy_url)
        options.set_argument("--proxy-server", proxy_url)
        
    driver = ChromiumPage(addr_or_opts=options)
    try:
        driver.get(url)
        cf_bypasser = CloudflareBypasser(driver, retries, log, timeout)
        cf_bypasser.bypass()
        return driver
    except Exception as e:
        driver.quit()
        raise e


# Endpoint to get cookies
@app.get("/cookies", response_model=CookieResponse)
async def get_cookies(url: str, retries: int = 5):
    if not is_safe_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL")
    try:
        driver = bypass_cloudflare(url, retries, log)
        cookies = driver.cookies(as_dict=True)
        user_agent = driver.user_agent
        driver.quit()
        return CookieResponse(cookies=cookies, user_agent=user_agent)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Endpoint to get HTML content and cookies
@app.get("/html")
async def get_html(url: str, retries: int = 5):
    if not is_safe_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL")
    try:
        driver = bypass_cloudflare(url, retries, log)
        html = driver.html
        cookies_json = json.dumps(driver.cookies(as_dict=True))

        response = Response(content=html, media_type="text/html")
        response.headers["cookies"] = cookies_json
        response.headers["user_agent"] = driver.user_agent
        driver.quit()
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RequestModel(BaseModel):
    cmd: str
    url: str
    maxTimeout: int
    proxy: Dict[str, str] = None

class ResponseModel(BaseModel):
    status: str
    message: str = None
    solution: Dict[str, Union[str, List[Dict[str, str]], Dict[str, str]]] = None

@app.post("/v1")
async def v1(payload: RequestModel):
    if payload.cmd != "request.get":
        raise HTTPException(status_code=500, detail="Unsupported cmd")
    try:
        #print(payload.proxy)
        driver = bypass_cloudflare(payload.url, 5, log, timeout=payload.maxTimeout, proxy=payload.proxy)
        html = driver.html
        cookies_json = driver.cookies(as_dict=True)
        try:
            driver.quit()
        except:
            pass
        return ResponseModel(status="ok", solution={"cookies": [{"name": a, "value":b} for a,b in cookies_json.items()], "kv_cookies": {a:b for a,b in cookies_json.items()}, "userAgent": driver.user_agent, "html": html})
    except Exception as e:
        return ResponseModel(status="failed", message=str(e))

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

    uvicorn.run(app, host="0.0.0.0", port=8000)
