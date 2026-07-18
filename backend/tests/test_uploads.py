import io


async def test_html_upload_rejected(client):
    r = await client.post("/api/upload",
                          files={"file": ("evil.html", io.BytesIO(b"<script>"), "text/html")})
    assert r.status_code == 415


async def test_exe_upload_rejected(client):
    r = await client.post("/api/upload",
                          files={"file": ("x.exe", io.BytesIO(b"MZ"), "application/octet-stream")})
    assert r.status_code == 415


async def test_oversized_upload_rejected(client):
    big = b"\xff" * (16 * 1024 * 1024)
    r = await client.post("/api/upload",
                          files={"file": ("big.jpg", io.BytesIO(big), "image/jpeg")})
    assert r.status_code == 413


async def test_valid_upload_accepted(client):
    # 1x1 px GIF
    gif = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
           b"\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
    r = await client.post("/api/upload",
                          files={"file": ("dot.gif", io.BytesIO(gif), "image/gif")})
    assert r.status_code == 200
    body = r.json()
    assert "id" in body and body["url"].startswith("/api/uploads/")
    # cleanup
    await client.delete(f"/api/uploads/{body['id']}")
