"""
Blogger API용 Google 로그인 토큰을 받는 프로그램입니다.
PC에서 한 번만 실행하면 됩니다.
필요 파일: Google Cloud에서 받은 client_secret.json (이 폴더에 저장)
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/blogger"]


def get_refresh_token():
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n========== 아래 값을 복사하세요 ==========")
    print(f"G_REFRESH_TOKEN={creds.refresh_token}")
    print(f"G_CLIENT_ID={creds.client_id}")
    print(f"G_CLIENT_SECRET={creds.client_secret}")
    print("==========================================\n")
    print("이 값들은 GitHub Secrets 와 .env 파일에 넣습니다.")


if __name__ == "__main__":
    get_refresh_token()
