"""Constants for the Rachio Run Times integration."""

DOMAIN = "rachio_run_times"

# Public Rachio API — used to enumerate devices and zones (zone name/id mapping)
RACHIO_API_BASE = "https://api.rach.io/1/public"

# Undocumented cloud-rest endpoint — returns per-zone stateData including
# lastRun, lastRunEndTime, and nextRun.  Rachio has stated this endpoint is
# allowed but unsupported; it may change without notice.
RACHIO_CLOUD_REST_BASE = "https://cloud-rest.rach.io"

# Config-entry keys
CONF_API_KEY = "api_key"

# How often to poll cloud-rest.  These timestamps only change when a schedule
# runs or is modified, so hourly is plenty and very conservative against the
# 1 700-call/day public-API rate limit.
DEFAULT_SCAN_INTERVAL_HOURS = 1

# Keys used in the coordinator data dict (keyed by zone_id)
KEY_LAST_RUN = "lastRun"
KEY_LAST_RUN_END = "lastRunEndTime"
KEY_NEXT_RUN = "nextRun"
KEY_ZONE_NAME = "zone_name"
KEY_DEVICE_NAME = "device_name"
