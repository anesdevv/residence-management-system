#!/usr/bin/env python3
"""fal.ai client for the charles-arcade-assets skill (Python standard library only).

  fal.py image  --prompt "..." [--ref a.png --ref b.png] [--aspect 9:16] [--res 2K] --out art/scene.png
  fal.py video  --image art/scene.png [--end art/scene_b.png] --prompt "..." [--model minimax] [--duration 5] --out clips/fight.mp4
  fal.py rmbg   --image art/raw.png --out art/cut.png
  fal.py raw    <endpoint_id> <input.json> --out out/name.ext

Local paths in --ref/--image/--end are uploaded to fal storage automatically.
FAL_KEY comes from the environment or the nearest .env (cwd upward, then this repo).
A request that matches the sidecar <out>.fal.json is skipped unless --force.
Every paid call appends an estimate to costs.jsonl next to the output.
"""
import argparse, hashlib, json, mimetypes, os, re, sys, time, urllib.error, urllib.request
from pathlib import Path

IMAGE_MODEL = "fal-ai/nano-banana-pro"
VIDEO_MODELS = {
    # name: (endpoint, $ per second, image field, end field)
    "minimax": ("minimax/h3-max/image-to-video", 0.0325, "image_url", "end_image_url"),
    "kling": ("kling/v4/image-to-video", 0.157, "start_image_url", "end_image_url"),
    "gemini": ("google/gemini-omni-flash/v1.1/image-to-video", 0.03, "image_url", "end_image_url"),
}
PRICE = {IMAGE_MODEL: 0.15, IMAGE_MODEL + "/edit": 0.15, "fal-ai/bria/background/remove": 0.018}


def find_key():
    if os.environ.get("FAL_KEY"):
        return os.environ["FAL_KEY"]
    for start in (Path.cwd(), Path(__file__).resolve()):
        for d in [start, *start.parents]:
            env = d / ".env"
            if env.is_file():
                m = re.search(r"^FAL_KEY=(.+)$", env.read_text(), re.M)
                if m:
                    return m.group(1).strip().strip('"').strip("'")
    sys.exit("FAL_KEY not found: set it in the environment or in a .env file")


KEY = None


def http(url, body=None, method=None, headers=None, timeout=120):
    h = {"Authorization": f"Key {KEY}"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} from {url}: {e.read().decode()[:1200]}")


def upload(path):
    """Upload a local file to fal storage and return its URL (cached by content hash)."""
    p = Path(path)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    cache = Path.home() / ".cache" / "arcade-fal-uploads.json"
    known = json.loads(cache.read_text()) if cache.is_file() else {}
    if digest in known:
        return known[digest]
    ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    init = http("https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3",
                {"content_type": ctype, "file_name": p.name})
    put = urllib.request.Request(init["upload_url"], data=p.read_bytes(), headers={"Content-Type": ctype}, method="PUT")
    urllib.request.urlopen(put, timeout=300).read()
    known[digest] = init["file_url"]
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(known))
    return init["file_url"]


def as_url(x):
    return x if re.match(r"^https?://", x) else upload(x)


def run(endpoint, payload, out, force=False, est=None):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sidecar = out.with_name(out.name + ".fal.json")
    if not force and out.exists() and sidecar.is_file():
        prev = json.loads(sidecar.read_text())
        if prev.get("endpoint") == endpoint and prev.get("input") == payload:
            print(f"cached: {out}")
            return out
    started = time.time()
    job = http(f"https://queue.fal.run/{endpoint}", payload)
    while True:
        status = http(job["status_url"])
        if status.get("status") == "COMPLETED":
            break
        if time.time() - started > 1500:
            sys.exit(f"timed out waiting for {endpoint} (last status {status.get('status')})")
        time.sleep(3)
    result = http(job["response_url"])
    urls = re.findall(r'"url":\s*"(https://[^"]+)"', json.dumps(result))
    if not urls:
        sys.exit(f"no output file in result: {json.dumps(result)[:800]}")
    saved = []
    for i, url in enumerate(urls):
        target = out if i == 0 else out.with_name(f"{out.stem}_{i}{out.suffix}")
        urllib.request.urlretrieve(url, target)
        saved.append(str(target))
    sidecar.write_text(json.dumps({"endpoint": endpoint, "input": payload, "result": result}, indent=1))
    secs = time.time() - started
    if est is not None:
        with open(out.parent / "costs.jsonl", "a") as f:
            f.write(json.dumps({"endpoint": endpoint, "out": str(out), "usd_est": round(est, 3), "secs": round(secs)}) + "\n")
    print(f"saved: {', '.join(saved)}  ({secs:.0f}s, ~${est or 0:.2f})")
    return out


def main():
    global KEY
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("image", help="text-to-image, or edit when --ref is given (Nano Banana Pro)")
    a.add_argument("--prompt", required=True)
    a.add_argument("--ref", action="append", default=[], help="reference image (path or URL); repeatable")
    a.add_argument("--aspect", default="9:16", help="9:16, 16:9, 1:1, 4:5, 5:4, 3:4, 4:3, 2:3, 3:2, 21:9")
    a.add_argument("--res", default="2K", choices=["1K", "2K", "4K"])
    a.add_argument("--out", required=True)
    a.add_argument("--force", action="store_true")

    v = sub.add_parser("video", help="image-to-video")
    v.add_argument("--image", required=True)
    v.add_argument("--end", help="end frame (minimax/kling)")
    v.add_argument("--prompt", required=True)
    v.add_argument("--model", default="minimax", choices=list(VIDEO_MODELS))
    v.add_argument("--duration", type=int, default=5)
    v.add_argument("--out", required=True)
    v.add_argument("--force", action="store_true")

    r = sub.add_parser("rmbg", help="background removal (Bria RMBG 2.0)")
    r.add_argument("--image", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--force", action="store_true")

    w = sub.add_parser("raw", help="any endpoint with a JSON input file")
    w.add_argument("endpoint")
    w.add_argument("input")
    w.add_argument("--out", required=True)
    w.add_argument("--force", action="store_true")

    args = ap.parse_args()
    KEY = find_key()

    if args.cmd == "image":
        payload = {"prompt": args.prompt, "aspect_ratio": args.aspect, "resolution": args.res,
                   "output_format": "png", "num_images": 1}
        endpoint = IMAGE_MODEL
        if args.ref:
            endpoint += "/edit"
            payload["image_urls"] = [as_url(x) for x in args.ref]
        run(endpoint, payload, args.out, args.force, PRICE[endpoint])
    elif args.cmd == "video":
        endpoint, per_sec, img_field, end_field = VIDEO_MODELS[args.model]
        payload = {"prompt": args.prompt, img_field: as_url(args.image), "duration": args.duration}
        if args.end:
            payload[end_field] = as_url(args.end)
        if args.model == "minimax":
            payload.update(resolution="1080P", prompt_expansion_mode="balanced")
        elif args.model == "kling":
            payload["resolution"] = "1080p"
        else:
            payload.update(aspect_ratio="9:16", resolution="1080p")
        run(endpoint, payload, args.out, args.force, per_sec * args.duration)
    elif args.cmd == "rmbg":
        endpoint = "fal-ai/bria/background/remove"
        run(endpoint, {"image_url": as_url(args.image)}, args.out, args.force, PRICE[endpoint])
    else:
        payload = json.loads(Path(args.input).read_text())
        run(args.endpoint, payload, args.out, args.force, PRICE.get(args.endpoint))


if __name__ == "__main__":
    main()
