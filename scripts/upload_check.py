import httpx

# for image 1, should pass

url = ""
fields = {
    "Content-Type": "",
    "key": "",
    "x-amz-algorithm": "",
    "x-amz-credential": "",
    "x-amz-date": "",
    "policy": "",
    "x-amz-signature": "",
}

r = httpx.post(
    url, data=fields, files={"file": open("test-images/testimage3_small.jpg", "rb")}
)
print(r.status_code, r.text)
