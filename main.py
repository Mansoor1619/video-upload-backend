import base64
import json
import base64
from fastapi import FastAPI, Depends, HTTPException, Request, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Any
from sqlalchemy.orm import Session
from database import engine, get_db, Base
from models import GameData

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Unreal Engine Data API", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

pending_chunks: dict = {}


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pixel Stream + Upload</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 100%; height: 100%; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #000; color: #eee; }

  #streamWrap { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; }
  #streamWrap iframe { width: 100%; height: 100%; border: none; }

  #uploadToggle {
    position: fixed; bottom: 30px; right: 30px; z-index: 100;
    padding: 14px 28px; background: #e94560; border: none; border-radius: 8px;
    color: #fff; font-size: 15px; font-weight: 600; cursor: pointer;
    transition: .3s; font-family: inherit;
  }
  #uploadToggle:hover { background: #d63851; }

  #overlay {
    display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,.75); z-index: 200; justify-content: center; align-items: center;
  }
  #overlay.open { display: flex; }

  #panel {
    background: #16213e; padding: 40px; border-radius: 16px; width: 480px;
    max-width: 90vw; box-shadow: 0 8px 32px rgba(0,0,0,.5);
  }
  #panel h2 { font-size: 22px; margin-bottom: 6px; color: #e94560; }
  #panel .sub { color: #888; font-size: 13px; margin-bottom: 20px; }

  .drop-zone {
    border: 2px dashed #444; border-radius: 12px; padding: 36px; text-align: center;
    cursor: pointer; transition: .3s; margin-bottom: 14px;
  }
  .drop-zone:hover, .drop-zone.dragover { border-color: #e94560; background: rgba(233,69,96,.06); }
  .drop-zone input { display: none; }
  .drop-zone .dz-icon { font-size: 40px; margin-bottom: 8px; }
  .drop-zone .dz-text { color: #aaa; }
  .drop-zone .dz-file { color: #e94560; font-weight: 600; margin-top: 8px; display: none; }
  .drop-zone.has-file { border-color: #0f3460; }
  .drop-zone.has-file .dz-text { display: none; }
  .drop-zone.has-file .dz-file { display: block; }

  .actions { display: flex; gap: 10px; }
  .actions button {
    flex: 1; padding: 13px; border: none; border-radius: 8px;
    font-size: 15px; font-weight: 600; cursor: pointer; font-family: inherit; transition: .3s;
  }
  .actions .btn-up { background: #e94560; color: #fff; }
  .actions .btn-up:hover { background: #d63851; }
  .actions .btn-up:disabled { background: #444; cursor: not-allowed; }
  .actions .btn-cancel { background: #333; color: #aaa; }
  .actions .btn-cancel:hover { background: #444; }

  .progress-wrap { margin-top: 14px; display: none; }
  .progress-wrap.active { display: block; }
  .progress-bar { height: 6px; background: #0f3460; border-radius: 4px; overflow: hidden; }
  .progress-bar .fill { height: 100%; width: 0%; background: #e94560; transition: width .3s; border-radius: 4px; }
  .status { margin-top: 8px; font-size: 13px; color: #aaa; text-align: center; }
  .status.ok { color: #4caf50; }
  .status.err { color: #e94560; }
  .resp { margin-top: 10px; padding: 10px; background: #0f3460; border-radius: 8px; font-size: 12px; color: #aaa; display: none; word-break: break-all; }
  .resp.show { display: block; }
</style>
</head>
<body>

<div id="streamWrap">
  <iframe
    id="streamIframe"
    src="https://share.streampixel.io/69fed8dba099e03c0053eca1"
    allow="autoplay; fullscreen; microphone; camera"
    allowfullscreen
  ></iframe>
</div>

<button id="uploadToggle">Upload Video</button>

<div id="overlay">
  <div id="panel">
    <h2>Upload Video</h2>
    <p class="sub">Upload a video file to the server</p>

    <div class="drop-zone" id="dropZone">
      <input type="file" id="fileInput" accept=".mp4,.mov,.avi,.mkv,.webm">
      <div class="dz-icon">&#128249;</div>
      <div class="dz-text">Click or drag a video file here</div>
      <div class="dz-file" id="fileName"></div>
    </div>

    <div class="progress-wrap" id="progressWrap">
      <div class="progress-bar"><div class="fill" id="progressFill"></div></div>
      <div class="status" id="statusText"></div>
    </div>

    <div class="resp" id="responseBox"><pre id="responseText" style="margin:0;white-space:pre-wrap"></pre></div>

    <div class="actions">
      <button class="btn-up" id="uploadBtn" disabled>Upload</button>
      <button class="btn-cancel" id="cancelBtn">Cancel</button>
    </div>
  </div>
</div>

<script>
const iframe = document.getElementById('streamIframe');
const toggleBtn = document.getElementById('uploadToggle');
const overlay = document.getElementById('overlay');
const cancelBtn = document.getElementById('cancelBtn');
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const uploadBtn = document.getElementById('uploadBtn');
const progressWrap = document.getElementById('progressWrap');
const progressFill = document.getElementById('progressFill');
const statusText = document.getElementById('statusText');
const responseBox = document.getElementById('responseBox');
const responseText = document.getElementById('responseText');

let selectedFile = null;

toggleBtn.addEventListener('click', () => overlay.classList.add('open'));
cancelBtn.addEventListener('click', () => overlay.classList.remove('open'));

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => { if (fileInput.files.length) handleFile(fileInput.files[0]); });

function handleFile(file) {
  if (!file.type.startsWith('video/')) { alert('Please select a video file'); return; }
  selectedFile = file;
  fileName.textContent = file.name + ' (' + (file.size / 1024 / 1024).toFixed(1) + ' MB)';
  dropZone.classList.add('has-file');
  uploadBtn.disabled = false;
}

uploadBtn.addEventListener('click', uploadFile);

function sendToUE(data) {
  try { iframe.contentWindow.postMessage(data, 'https://share.streampixel.io'); } catch {}
}

async function uploadFile() {
  if (!selectedFile) return;

  uploadBtn.disabled = true;
  progressWrap.classList.add('active');
  statusText.textContent = 'Uploading...';
  statusText.className = 'status';
  responseBox.classList.remove('show');
  progressFill.style.width = '0%';

  const formData = new FormData();
  formData.append('video', selectedFile);
  formData.append('filename', selectedFile.name);

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/upload-video-form');

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      progressFill.style.width = Math.round((e.loaded / e.total) * 100) + '%';
    }
  };

  xhr.onload = () => {
    progressFill.style.width = '100%';
    if (xhr.status >= 200 && xhr.status < 300) {
      statusText.textContent = 'Upload successful!';
      statusText.className = 'status ok';
      try {
        const json = JSON.parse(xhr.responseText);
        responseText.textContent = JSON.stringify(json, null, 2);
        responseBox.classList.add('show');
        sendToUE({ type: 'uploadComplete', id: json.id, filename: selectedFile.name, size: selectedFile.size });
      } catch {}
    } else {
      statusText.textContent = 'Upload failed (HTTP ' + xhr.status + ')';
      statusText.className = 'status err';
      responseText.textContent = xhr.responseText || 'No response';
      responseBox.classList.add('show');
    }
    uploadBtn.disabled = false;
  };

  xhr.onerror = () => {
    statusText.textContent = 'Network error';
    statusText.className = 'status err';
    uploadBtn.disabled = false;
  };

  xhr.send(formData);
}

window.addEventListener('message', (event) => {
  if (event.origin !== 'https://share.streampixel.io') return;
  if (event.data === 'loadingComplete') console.log('Stream loaded');
});
</script>
</body>
</html>"""


@app.get("/")
def root():
    return HTMLResponse(content=HTML_PAGE)


@app.post("/upload-video-form")
async def upload_video_form(
    video: UploadFile = File(...),
    filename: str = Form(None),
    location: str = Form(None),
    date: str = Form(None),
    length: str = Form(None),
    width: str = Form(None),
    db: Session = Depends(get_db),
):
    contents = await video.read()
    encoded = base64.b64encode(contents).decode("utf-8")
    loc = None
    if location:
        try:
            loc = json.loads(location)
        except Exception:
            loc = location
    record = GameData(
        location=loc,
        date=date,
        length=float(length) if length else None,
        width=float(width) if width else None,
        video_data=encoded,
        payload={"original_filename": filename or video.filename},
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "message": "Video uploaded successfully",
        "filename": filename or video.filename,
        "size_bytes": len(contents),
    }


@app.post("/upload")
def upload(data: DataPayload, db: Session = Depends(get_db)):
    loc = None
    if data.location:
        try:
            loc = json.loads(data.location)
        except Exception:
            loc = data.location
    record = GameData(
        location=loc,
        date=data.date,
        length=float(data.length) if data.length else None,
        width=float(data.width) if data.width else None,
        video_data=data.video_data,
        payload=data.payload,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "message": "Data stored successfully"}


@app.post("/upload-form")
async def upload_form(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    fields = {k: v for k, v in form_data.items()}

    video_data = None
    if "video" in fields:
        file_obj = fields["video"]
        if hasattr(file_obj, "read"):
            video_bytes = await file_obj.read()
            video_data = base64.b64encode(video_bytes).decode("ascii")

    loc = None
    loc_raw = fields.get("location") or fields.get("location_json")
    if loc_raw:
        try:
            loc = json.loads(str(loc_raw))
        except Exception:
            loc = str(loc_raw)

    record = GameData(
        location=loc,
        date=fields.get("date"),
        length=float(fields["length"]) if fields.get("length") else None,
        width=float(fields["width"]) if fields.get("width") else None,
        video_data=video_data,
        payload=json.dumps(dict(fields)) if fields else None,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return JSONResponse({"id": record.id, "message": "Video uploaded successfully", "size_bytes": len(video_data) if video_data else 0})


@app.post("/upload-video")
async def upload_video(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    text = body.decode("utf-8")
    data = json.loads(text)
    loc = None
    if data.get("location"):
        try:
            loc = json.loads(data["location"])
        except Exception:
            loc = data["location"]
    record = GameData(
        location=loc,
        date=data.get("date"),
        length=float(data["length"]) if data.get("length") else None,
        width=float(data["width"]) if data.get("width") else None,
        video_data=data.get("video_data"),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "message": "Video uploaded successfully"}


@app.post("/upload-chunk")
def upload_chunk(data: ChunkUpload, db: Session = Depends(get_db)):
    key = data.record_id if data.record_id else 0

    if key not in pending_chunks:
        pending_chunks[key] = {"chunks": {}, "meta": {}}

    pending_chunks[key]["chunks"][data.chunk_index] = data.chunk_data

    if data.location is not None:
        pending_chunks[key]["meta"]["location"] = data.location
    if data.date is not None:
        pending_chunks[key]["meta"]["date"] = data.date
    if data.length is not None:
        pending_chunks[key]["meta"]["length"] = data.length
    if data.width is not None:
        pending_chunks[key]["meta"]["width"] = data.width

    received = len(pending_chunks[key]["chunks"])
    total = data.total_chunks

    if total and received >= total:
        full_video = "".join(
            pending_chunks[key]["chunks"][i] for i in sorted(pending_chunks[key]["chunks"].keys())
        )
        meta = pending_chunks[key]["meta"]
        loc = None
        if meta.get("location"):
            try:
                loc = json.loads(meta["location"])
            except Exception:
                loc = meta["location"]

        record = GameData(
            location=loc,
            date=meta.get("date"),
            length=float(meta["length"]) if meta.get("length") else None,
            width=float(meta["width"]) if meta.get("width") else None,
            video_data=full_video,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        del pending_chunks[key]
        return {"id": record.id, "message": "Video uploaded successfully", "chunks": received}

    return {"status": "receiving", "chunk": data.chunk_index, "received": received, "total": total}


@app.get("/data")
def list_data(limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(GameData)
    return query.order_by(GameData.created_at.desc()).limit(limit).all()


@app.get("/data/{data_id}")
def get_data(data_id: int, db: Session = Depends(get_db)):
    record = db.query(GameData).filter(GameData.id == data_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
    return record