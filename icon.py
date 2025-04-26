import requests
import os

def download_icon():
    # 下载一个邮件图标
    icon_url = "https://raw.githubusercontent.com/google/material-design-icons/master/png/communication/mail/materialicons/48dp/2x/baseline_mail_black_48dp.png"
    response = requests.get(icon_url)
    
    if response.status_code == 200:
        with open("mail_icon.png", "wb") as f:
            f.write(response.content)
        print("图标下载成功")
    else:
        print("图标下载失败")

if __name__ == "__main__":
    download_icon() 