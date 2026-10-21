# nesterlog AdSense Autopost

`nesterlog.com` (Google Blogger)용 **애드센스 승인 특화** 자동 초안 생성기입니다.

원본: [pushkar708/blogger-autopost](https://github.com/pushkar708/blogger-autopost)  
개조 포인트: 한국어, 초안 기본, 니치 고정, 하루 1회, 주제 목록 지원

## 비개발자용

**[설정가이드.md](./설정가이드.md)** 를 위에서부터 그대로 따라하세요.

## 동작

1. GitHub Actions가 매일 1회 실행 (PC 꺼져 있어도 OK)
2. Gemini가 한국어 글 생성
3. Blogger **초안**으로 저장
4. 본인이 검수 후 발행

## 로컬 테스트

```powershell
cd D:\cursorcode\adsenblog
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# .env 값 채운 뒤
python main.py
```

## 라이선스

원본과 동일하게 MIT 취지로 사용·수정 가능합니다.
