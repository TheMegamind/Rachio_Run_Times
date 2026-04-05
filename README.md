# Rachio Run Times

A lightweight Home Assistant custom integration that exposes per-zone run timestamps from the Rachio irrigation API — data the core Rachio integration does not surface.

## What It Provides

For every enabled zone on your Rachio controller, three `timestamp` sensors are created:

| Sensor | Description |
|---|---|
| `sensor.rachio_<zone>_last_run` | When the last scheduled run **started** |
| `sensor.rachio_<zone>_last_run_end` | When the last scheduled run **ended** |
| `sensor.rachio_<zone>_next_run` | When the next scheduled run **starts** |

All sensors use `device_class: timestamp`, so Home Assistant automatically converts UTC values to your local time zone in the UI and in automations.

## How It Works

The core Rachio integration uses only the public `api.rach.io/1` API, which does not expose next/last run timestamps at the zone level. This integration supplements it by calling the `cloud-rest.rach.io/device/getDeviceState/{deviceId}` endpoint — the same endpoint used by the Rachio mobile app and the [Rachio Community Hubitat integration](https://github.com/lnjustin/Rachio-Community).

> **Note:** `cloud-rest.rach.io` is an undocumented internal Rachio endpoint. Rachio has stated its use is permitted but provides no support or stability guarantee. This integration is designed to fail gracefully if the endpoint changes.

## Installation

### HACS (Recommended)

1. Open HACS → **Integrations** → ⋮ menu → **Custom Repositories**
2. Add `https://github.com/TheMegamind/Rachio_Run_Times` as category **Integration**
3. Install **Rachio Run Times** and restart Home Assistant

### Manual

Copy the `custom_components/rachio_run_times` folder into your `config/custom_components/` directory and restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Rachio Run Times**
3. Enter your Rachio API key (same key used by the core Rachio integration)
   - Find it at [app.rach.io](https://app.rach.io) → Account Settings → Get API Key

## Polling Interval

Sensors update **every hour**. Run timestamps only change when a schedule fires or is modified, so hourly polling is more than sufficient and uses only ~2 API calls per cycle — well within Rachio's 1,700-call/day limit.

## Coexistence with Core Integration

This integration is completely independent of the core HA Rachio integration. They share the same API key but have no shared state and no conflicts. Both can run simultaneously.

## Troubleshooting

Enable debug logging to see raw API responses:

```yaml
logger:
  logs:
    custom_components.rachio_run_times: debug
```

If sensors show `Unknown` after installation, check the logs for warnings about the `cloud-rest` payload shape — Rachio may have changed the response structure.
