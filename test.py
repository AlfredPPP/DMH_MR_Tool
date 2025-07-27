import requests

def get_ip_info():
    try:
        # 推荐使用这个 API，简单稳定
        response = requests.get("https://ipinfo.io/json", timeout=5)
        data = response.json()
        print("你的公网 IP:", data.get("ip"))
        print("归属地:", data.get("city"), data.get("region"), data.get("country"))
        print("ISP:", data.get("org"))
    except Exception as e:
        print("查询失败:", e)

get_ip_info()
