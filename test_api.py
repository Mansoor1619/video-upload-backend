import urllib.request, json
data = json.dumps({
    "location": '{"x":1.0,"y":2.0,"z":3.0}',
    "date": "2026-05-08",
    "length": "10.5",
    "width": "5.2",
    "video_data": "test_video_data"
}).encode()
r = urllib.request.Request("http://127.0.0.1:8000/upload", data=data, headers={"Content-Type": "application/json"})
print(urllib.request.urlopen(r).read().decode())

r2 = urllib.request.urlopen("http://127.0.0.1:8000/data")
print(json.dumps(json.loads(r2.read()), indent=2))
