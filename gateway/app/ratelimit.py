import time
from fastapi import HTTPException

# api_key_id -> (minute_bucket, count)
_BUCKETS: dict[int, tuple[int, int]] = {}

def enforce_rpm_limit(api_key_id: int, rpm_limit: int):
    """
    Enforce requests-per-minute per API key.
    rpm_limit = 0 => unlimited
    """
    if rpm_limit <= 0:
        return

    now_min = int(time.time() // 60)
    minute_bucket, count = _BUCKETS.get(api_key_id, (now_min, 0))

    # nuovo minuto
    if minute_bucket != now_min:
        _BUCKETS[api_key_id] = (now_min, 1)
        return

    if count >= rpm_limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    _BUCKETS[api_key_id] = (minute_bucket, count + 1)
