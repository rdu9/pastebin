import httpx

# for image 1, should pass

url = "http://localhost:3900/pastebin"

fields = {
    "Content-Type": "image/png",
    "key": "images/2ad36f30-5f41-49aa-9929-f07f77913514/a76ffac3-27a8-4192-baf8-5171c71ddcb1",
    "x-amz-algorithm": "AWS4-HMAC-SHA256",
    "x-amz-credential": "GK0bf5ae6f5c0b6df918644e2fe691e6d2/20261026/garage/s3/aws4_request",
    "x-amz-date": "20261026T003800Z",
    "policy": "eyJleHBpcmF0aW9uIjogIjIwMjYtMTAtMjZUMDA6NDM6MDBaIiwgImNvbmRpdGlvbnMiOiBbWyJjb250ZW50LWxlbmd0aC1yYW5nZSIsIDEsIDUyNDI4ODBdLCB7IkNvbnRlbnQtVHlwZSI6ICJpbWFnZS9wbmcifSwgeyJidWNrZXQiOiAicGFzdGViaW4ifSwgeyJrZXkiOiAiaW1hZ2VzLzJhZDM2ZjMwLTVmNDEtNDlhYS05OTI5LWYwN2Y3NzkxMzUxNC9hNzZmZmFjMy0yN2E4LTQxOTItYmFmOC01MTcxYzcxZGRjYjEifSwgeyJ4LWFtei1hbGdvcml0aG0iOiAiQVdTNC1ITUFDLVNIQTI1NiJ9LCB7IngtYW16LWNyZWRlbnRpYWwiOiAiR0swYmY1YWU2ZjVjMGI2ZGY5MTg2NDRlMmZlNjkxZTZkMi8yMDI2MTAyNi9nYXJhZ2UvczMvYXdzNF9yZXF1ZXN0In0sIHsieC1hbXotZGF0ZSI6ICIyMDI2MTAyNlQwMDM4MDBaIn1dfQ==",
    "x-amz-signature": "18f48d1f99d5e5baa316c59cabd92a0bdc5e93b0708630db37763d000d0b9062",
}

# for image 2, shouldnt pass ( over 5mb )

url2 = "http://localhost:3900/pastebin"
fields2 = {
    "Content-Type": "image/png",
    "key": "images/2ad36f30-5f41-49aa-9929-f07f77913514/284058ff-7dfa-4f46-a3ab-d953701a1bca",
    "x-amz-algorithm": "AWS4-HMAC-SHA256",
    "x-amz-credential": "GK0bf5ae6f5c0b6df918644e2fe691e6d2/20261026/garage/s3/aws4_request",
    "x-amz-date": "20261026T004532Z",
    "policy": "eyJleHBpcmF0aW9uIjogIjIwMjYtMTAtMjZUMDA6NTA6MzJaIiwgImNvbmRpdGlvbnMiOiBbWyJjb250ZW50LWxlbmd0aC1yYW5nZSIsIDEsIDUyNDI4ODBdLCB7IkNvbnRlbnQtVHlwZSI6ICJpbWFnZS9wbmcifSwgeyJidWNrZXQiOiAicGFzdGViaW4ifSwgeyJrZXkiOiAiaW1hZ2VzLzJhZDM2ZjMwLTVmNDEtNDlhYS05OTI5LWYwN2Y3NzkxMzUxNC8yODQwNThmZi03ZGZhLTRmNDYtYTNhYi1kOTUzNzAxYTFiY2EifSwgeyJ4LWFtei1hbGdvcml0aG0iOiAiQVdTNC1ITUFDLVNIQTI1NiJ9LCB7IngtYW16LWNyZWRlbnRpYWwiOiAiR0swYmY1YWU2ZjVjMGI2ZGY5MTg2NDRlMmZlNjkxZTZkMi8yMDI2MTAyNi9nYXJhZ2UvczMvYXdzNF9yZXF1ZXN0In0sIHsieC1hbXotZGF0ZSI6ICIyMDI2MTAyNlQwMDQ1MzJaIn1dfQ==",
    "x-amz-signature": "012d6cb08021129286a57aec7e15556a9ef6207a0837d8fc458eca1a92d38a72",
}


r = httpx.post(url2, data=fields2, files={"file": open("testimage2.png", "rb")})
print(r.status_code, r.text)
