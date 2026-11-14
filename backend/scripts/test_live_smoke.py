"""Live smoke test verifying end-to-end integration across Vite proxy and FastAPI backend."""
import json
import urllib.request
import sys

def main():
    print("=== Testing Direct FastAPI Health (port 8000) ===")
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5) as r:
            assert r.status == 200
            health = json.loads(r.read().decode("utf-8"))
            print(f"Health Status: {r.status}, response: {health['status']}, version: {health['version']}")
            print(f"Cache stats: {health['cache']}")
    except Exception as e:
        print(f"FAILED direct backend check: {e}")
        sys.exit(1)

    print("\n=== Testing Proxied Health via Vite (port 5173) ===")
    try:
        with urllib.request.urlopen("http://localhost:5173/api/health", timeout=5) as r:
            assert r.status == 200
            proxy_health = json.loads(r.read().decode("utf-8"))
            print(f"Proxied Health Status: {r.status}, status: {proxy_health['status']}")
    except Exception as e:
        print(f"FAILED proxied health check: {e}")
        sys.exit(1)

    print("\n=== Testing Proxied /api/frames for WISE 0855 via Vite (port 5173) ===")
    try:
        url = "http://localhost:5173/api/frames?ra=133.795129&dec=-7.245147&band=SPHEREx-D6&size=0.05&max_frames=3"
        with urllib.request.urlopen(url, timeout=10) as r:
            assert r.status == 200
            data = json.loads(r.read().decode("utf-8"))
            print(f"Proxied /api/frames Status: {r.status}")
            print(f"Target: {data['target']['name']} (RA: {data['target']['ra']}, Dec: {data['target']['dec']})")
            print(f"Data Release: {data['dataRelease']}, Band: {data['band']}")
            print(f"Frame Count: {data['frameCount']}")
            print(f"WCS crval: {data['wcs']['crval']}, cdelt: {data['wcs']['cdelt']}")
            print(f"Markers: {data['markers']}")
            print("Frames:")
            for f in data["frames"]:
                print(f"  Frame {f['index']}: obsId={f['obsId']}, dateUtc={f['dateUtc']}, MJD={f['mjd']}, "
                      f"dims={f['width']}x{f['height']}, flux_elements={len(f['flux'])}, "
                      f"flags_elements={len(f['flags'])}, minFlux={f['minFlux']:.3f}, maxFlux={f['maxFlux']:.3f}")
    except Exception as e:
        print(f"FAILED proxied frames check: {e}")
        sys.exit(1)

    print("\n=== Testing Honest Error Handling via Vite (port 5173) ===")
    try:
        err_url = "http://localhost:5173/api/frames?ra=133.795&dec=-7.245&band=INVALID_BAND"
        try:
            with urllib.request.urlopen(err_url, timeout=5) as r:
                print(f"Unexpected success: {r.status}")
                sys.exit(1)
        except urllib.error.HTTPError as he:
            print(f"Expected HTTP Error handled honestly: HTTP {he.code} {he.reason}")
            body = json.loads(he.read().decode("utf-8"))
            print(f"Error detail: {body.get('detail')}")
            assert he.code == 400
            assert "Unsupported bandpass" in body.get("detail", "")
    except Exception as e:
        print(f"FAILED error handling check: {e}")
        sys.exit(1)

    print("\n>>> LIVE INTEGRATION SMOKE TEST PASSED FULLY! <<<")

if __name__ == "__main__":
    main()
