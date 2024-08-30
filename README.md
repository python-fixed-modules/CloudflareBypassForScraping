
# Cloudflare Turnstile Page & Captcha Bypass for Scraping

**We love scraping, don't we?** But sometimes, we face Cloudflare protection. This script is designed to bypass the Cloudflare protection on websites, allowing you to interact with them programmatically. 



# How does this script work?

If you use Selenium, you may have noticed that it is not possible to bypass Cloudflare protection with it. Even you click the "I'm not a robot" button, you will still be stuck in the "Checking your browser before accessing" page.
This is because Cloudflare protection is able to detect the automation tools and block them, which puts the webdriver infinitely in the "Checking your browser before accessing" page.

As you realize, the script uses the DrissionPage, which is a controller for the browser itself. This way, the browser is not detected as a webdriver and the Cloudflare protection is bypassed.


## Installation

You can install the required packages by running the following command:

```bash
pip install -r requirements.txt
```

## Demo
![](https://cdn.sarperavci.com/xWhiMOmD/vzJylR.gif)

## Usage

Create a new instance of the `CloudflareBypass` class and call the `bypass` method when you need to bypass the Cloudflare protection.

```python
from CloudflareBypasser import CloudflareBypasser

driver = ChromiumPage()
driver.get('https://nopecha.com/demo/cloudflare')

cf_bypasser = CloudflareBypasser(driver)
cf_bypasser.bypass()
```

You can run the test script to see how it works:

```bash
python test.py
```

# Introducing Server Mode

Recently, [@frederik-uni](https://github.com/frederik-uni) has introduced a new feature called "Server Mode". This feature allows you to bypass the Cloudflare protection remotely, either you can get the cookies or the HTML content of the website.

## Installation

You can install the required packages by running the following command:

```bash
pip install -r server_requirements.txt
```

## Usage

Start the server by running the following command:

```bash
python server.py
```

Two endpoints are available:

- `/cookies?url=<URL>&retries=<>`: This endpoint returns the cookies of the website (including the Cloudflare cookies).
- `/html?url=<URL>&retries=<>`: This endpoint returns the HTML content of the website.
- `/v1`: (POST) This endpoint returns the cookies of the website but you can send request same with [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) one. and Supports proxy :P

Send a GET request to the desired endpoint with the URL of the website you want to bypass the Cloudflare protection.

```bash
root@localhost:~# curl -X POST http://localhost:8000/v1 -H "Content-Type: application/json" -d '{"cmd": "request.get", "url": "https://nowsecure.nl", "maxTimeout": 30000}'
{
    "status": "ok",
    "solution": {
        "cookies": [
            {
                "name": "cf_clearance",
                "value":"SJHuYhHrTZpXDUe8iMuzEUpJxocmOW8ougQVS0.aK5g-1723665177-1.0.1.1-5_NOoP19LQZw4TQ4BLwJmtrXBoX8JbKF5ZqsAOxRNOnW2rmDUwv4hQ7BztnsOfB9DQ06xR5hR_hsg3n8xteUCw"
            }
        ],
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }
}
```

# What is this not?

This script is not related to bring a solution to bypass if your IP is blocked by Cloudflare. If you are blocked by Cloudflare, you need a clean IP to access the website. This script is designed to bypass the Cloudflare protection, not to bypass the IP block.
